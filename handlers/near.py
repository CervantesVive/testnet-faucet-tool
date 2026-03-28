import os
import re
import json
import base64

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class NearHandler(BaseHandler):
    """Handler for NEAR chains (native NEAR and NEP-141 token transfers).

    Uses the NEAR JSON-RPC API directly via aiohttp since py-near is not installed.
    Native transfers are performed by constructing and broadcasting a signed
    SendMoney action.  Token transfers are TBD.
    """

    _NEAR_YOCTO = 10 ** 24  # 1 NEAR = 10^24 yoctoNEAR

    def _get_account_id_and_key(self) -> tuple[str, bytes]:
        """Return (account_id, ed25519_private_key_bytes) from env vars.

        Resolution order:
        1. FAUCET_NEAR_ACCOUNT_ID + FAUCET_PRIVATE_KEY (hex ed25519 seed)
        2. FAUCET_PRIVATE_KEY alone (64-char hex treated as seed; account_id
           derived as the hex-encoded public key + '.testnet')
        """
        account_id = os.environ.get("FAUCET_NEAR_ACCOUNT_ID", "")
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")

        if not private_key:
            raise RuntimeError(
                "NEAR wallet not configured: set FAUCET_PRIVATE_KEY (hex ed25519 seed)"
            )

        key_bytes = bytes.fromhex(private_key.removeprefix("0x"))

        if not account_id:
            # Derive a deterministic implicit account_id from the 32-byte seed.
            # cryptography is available in the venv (used by other handlers).
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                priv = Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
                pub = priv.public_key().public_bytes_raw()
                account_id = pub.hex()
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot derive NEAR account_id; please set FAUCET_NEAR_ACCOUNT_ID: {exc}"
                )

        return account_id, key_bytes

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Dispatches to _drip_native or _drip_token based on config['native_asset'].
        All exceptions are caught and returned as a failed DripResult.
        """
        try:
            if self.config.get("native_asset"):
                return await self._drip_native(address, asset_id, amount)
            else:
                return await self._drip_token(address, asset_id, amount)
        except Exception as exc:
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=str(exc),
                amount=amount,
                asset=asset_id,
            )

    def validate_address(self, address: str) -> bool:
        """Return True if *address* is a valid NEAR account ID.

        NEAR account IDs:
        - 2–64 characters
        - Lowercase alphanumeric, underscores, hyphens, and dots
        - Named accounts end in .testnet, .near, etc.
        - Implicit accounts are exactly 64 hex chars
        """
        if not address or len(address) < 2 or len(address) > 64:
            return False
        return bool(re.match(r'^[a-z0-9._-]{2,64}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "NEAR")
        try:
            try:
                account_id, _ = self._get_account_id_and_key()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config["rpc_url"]
            payload = {
                "jsonrpc": "2.0",
                "id": "faucet",
                "method": "query",
                "params": {
                    "request_type": "view_account",
                    "finality": "final",
                    "account_id": account_id,
                },
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc_url, json=payload) as resp:
                    data = await resp.json()

            if "error" in data:
                return {asset_id: f"error: {data['error']}"}

            yocto = int(data["result"]["amount"])
            decimals = self.config.get("decimals", 24)
            formatted = f"{yocto / self._NEAR_YOCTO:.6f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'near'."""
        return [k for k, v in load_registry().items() if v.get("family") == "near"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native NEAR transfer using the NEAR JSON-RPC broadcast_tx_commit."""
        account_id, key_bytes = self._get_account_id_and_key()
        rpc_url = self.config["rpc_url"]

        # Build and sign transaction via cryptography library
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        seed = key_bytes[:32]
        priv = Ed25519PrivateKey.from_private_bytes(seed)
        pub_bytes = priv.public_key().public_bytes_raw()

        # Fetch nonce and block hash for the access key
        async with aiohttp.ClientSession() as session:
            nonce_payload = {
                "jsonrpc": "2.0",
                "id": "faucet",
                "method": "query",
                "params": {
                    "request_type": "view_access_key",
                    "finality": "final",
                    "account_id": account_id,
                    "public_key": f"ed25519:{base64.b64encode(pub_bytes).decode()}",
                },
            }
            async with session.post(rpc_url, json=nonce_payload) as resp:
                key_data = await resp.json()

            if "error" in key_data:
                # Fallback: fetch block hash without nonce
                nonce = 0
            else:
                nonce = key_data["result"]["nonce"] + 1

            # Fetch latest block hash
            block_payload = {
                "jsonrpc": "2.0",
                "id": "faucet",
                "method": "block",
                "params": {"finality": "final"},
            }
            async with session.post(rpc_url, json=block_payload) as resp:
                block_data = await resp.json()

            block_hash_b58 = block_data["result"]["header"]["hash"]

        # Decode block hash from base58
        block_hash_bytes = _b58decode(block_hash_b58)

        # Construct and sign the NEAR transaction (borsh-encoded)
        yocto_amount = int(float(amount) * self._NEAR_YOCTO)
        signed_tx_bytes = _build_near_tx(
            signer_id=account_id,
            pub_bytes=pub_bytes,
            nonce=nonce,
            receiver_id=address,
            block_hash=block_hash_bytes,
            yocto_amount=yocto_amount,
            priv=priv,
        )

        tx_b64 = base64.b64encode(signed_tx_bytes).decode()

        async with aiohttp.ClientSession() as session:
            broadcast_payload = {
                "jsonrpc": "2.0",
                "id": "faucet",
                "method": "broadcast_tx_commit",
                "params": [tx_b64],
            }
            async with session.post(rpc_url, json=broadcast_payload) as resp:
                result = await resp.json()

        if "error" in result:
            raise RuntimeError(f"NEAR RPC error: {result['error']}")

        tx_hash = result["result"].get("transaction", {}).get("hash") or result["result"].get("transaction_outcome", {}).get("id")

        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if explorer and tx_hash else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a NEP-141 token transfer.

        Returns a failed DripResult immediately if the contract_id is TBD.
        """
        if self.config.get("contract_id", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        # Full NEP-141 ft_transfer implementation would go here.
        raise NotImplementedError("NEAR NEP-141 token transfer not yet implemented")


# ---------------------------------------------------------------------------
# Minimal NEAR transaction serialisation (Borsh)
# ---------------------------------------------------------------------------

def _b58decode(s: str) -> bytes:
    """Decode a base58 string to bytes."""
    alphabet = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for char in s.encode():
        n = n * 58 + alphabet.index(char)
    result = []
    while n > 0:
        result.append(n & 0xFF)
        n >>= 8
    # Count leading 1s → leading zero bytes
    padding = len(s) - len(s.lstrip("1"))
    return bytes([0] * padding + result[::-1])


def _borsh_string(s: str) -> bytes:
    b = s.encode("utf-8")
    return len(b).to_bytes(4, "little") + b


def _borsh_u64(n: int) -> bytes:
    return n.to_bytes(8, "little")


def _borsh_u128(n: int) -> bytes:
    return n.to_bytes(16, "little")


def _build_near_tx(
    signer_id: str,
    pub_bytes: bytes,
    nonce: int,
    receiver_id: str,
    block_hash: bytes,
    yocto_amount: int,
    priv,
) -> bytes:
    """Build a minimal borsh-encoded SignedTransaction for a SendMoney action."""
    # Transaction body
    tx = b""
    tx += _borsh_string(signer_id)          # signer_id
    tx += b"\x00"                            # PublicKey type: ED25519
    tx += pub_bytes                          # 32-byte public key
    tx += _borsh_u64(nonce)                  # nonce
    tx += _borsh_string(receiver_id)         # receiver_id
    tx += block_hash                         # block_hash (32 bytes)
    tx += (1).to_bytes(4, "little")          # actions length = 1
    tx += b"\x03"                            # Action::Transfer variant
    tx += _borsh_u128(yocto_amount)          # deposit (u128)

    # Sign with ed25519
    import hashlib
    tx_hash = hashlib.sha256(tx).digest()
    signature = priv.sign(tx_hash)

    # SignedTransaction = Transaction + Signature
    signed = tx + b"\x00" + signature       # signature type 0 = ED25519, 64 bytes
    return signed
