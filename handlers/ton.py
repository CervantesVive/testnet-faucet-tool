import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class TonHandler(BaseHandler):
    """Handler for TON chains (native TON only — no token assets in registry).

    Uses the TON Center HTTP API (v2) directly via aiohttp since tonsdk and
    pytonlib are not installed.

    The TON Center API provides a JSON wrapper around TON node methods:
      GET  {rpc_url}getAddressBalance?address=<addr>
      POST {rpc_url}sendBoc   (serialised BoC)

    Constructing a signed TON transfer BoC requires secp256k1 (or ed25519 for
    wallets that use ed25519) and the TON cell serialisation format.
    Full BoC construction is complex; when tonsdk is unavailable we raise
    NotImplementedError from _drip_native so that the outer drip() handler
    converts it to a DripResult(success=False, error=...) rather than crashing.
    """

    def _get_private_key_bytes(self) -> bytes:
        """Return the 32-byte private key from env vars.

        Resolution order:
        1. FAUCET_PRIVATE_KEY — 64-char hex private key (ed25519 seed)
        2. FAUCET_MNEMONIC    — 24-word TON mnemonic (requires tonsdk)
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            return bytes.fromhex(private_key.removeprefix("0x"))

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            try:
                from tonsdk.crypto import mnemonic_to_wallet_key
                pub, priv = mnemonic_to_wallet_key(mnemonic.split())
                return priv
            except ImportError:
                raise RuntimeError(
                    "TON mnemonic derivation requires tonsdk — "
                    "set FAUCET_PRIVATE_KEY (hex ed25519 seed) instead"
                )

        raise RuntimeError(
            "TON wallet not configured: set FAUCET_PRIVATE_KEY or FAUCET_MNEMONIC"
        )

    def _get_wallet_address(self, priv_bytes: bytes) -> str:
        """Derive the TON wallet address string from an ed25519 private key.

        Attempts to use tonsdk.  Falls back to returning the public key as a
        raw hex string if tonsdk is unavailable.
        """
        try:
            from tonsdk.contract.wallet import WalletVersionEnum, Wallets
            from tonsdk.crypto import keys_from_private_key

            pub, priv = keys_from_private_key(priv_bytes)
            _mnemo, _pub, _priv, wallet = Wallets.from_private_key(
                priv_bytes, version=WalletVersionEnum.v4r2, workchain=0
            )
            return wallet.address.to_string(True, True, False)
        except ImportError:
            # Derive the public key via cryptography and return a raw address
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                priv = Ed25519PrivateKey.from_private_bytes(priv_bytes[:32])
                pub_bytes = priv.public_key().public_bytes_raw()
                return f"0:{pub_bytes.hex()}"
            except Exception as exc:
                raise RuntimeError(f"Cannot derive TON address: {exc}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet TON to *address*.

        All exceptions are caught and returned as a failed DripResult.
        TON has only native assets in the registry, so we always call
        _drip_native.
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
        """Return True if *address* is a plausible TON address.

        Accepted formats:
        - Raw:     0:<64 hex chars>
        - Base64url (EQ…/UQ…): 48 base64url characters
        - Hex:     64 raw hex chars (no prefix)
        """
        if not address:
            return False
        if re.match(r'^0:[0-9a-fA-F]{64}$', address):
            return True
        if re.match(r'^[0-9a-fA-F]{64}$', address):
            return True
        if re.match(r'^[A-Za-z0-9_-]{48}$', address):
            return True
        return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet TON balance.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "TON")
        try:
            try:
                priv_bytes = self._get_private_key_bytes()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            wallet_address = self._get_wallet_address(priv_bytes)
            rpc_url = self.config["rpc_url"].rstrip("/") + "/"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url}getAddressBalance",
                    params={"address": wallet_address},
                ) as resp:
                    data = await resp.json()

            if not data.get("ok"):
                return {asset_id: f"error: {data.get('error', 'unknown')}"}

            # Balance is in nanoTON (10^9)
            nano = int(data["result"])
            decimals = self.config.get("decimals", 9)
            formatted = f"{nano / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'ton'."""
        return [k for k, v in load_registry().items() if v.get("family") == "ton"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send native TON using a signed BoC via the TON Center API.

        Attempts to use tonsdk for BoC construction.  If tonsdk is not
        available, raises NotImplementedError so the caller can surface a
        clean error message.
        """
        priv_bytes = self._get_private_key_bytes()
        rpc_url = self.config["rpc_url"].rstrip("/") + "/"
        decimals = self.config.get("decimals", 9)
        nano_amount = int(float(amount) * (10 ** decimals))

        try:
            from tonsdk.contract.wallet import WalletVersionEnum, Wallets
            from tonsdk.utils import bytes_to_b64str
            import time

            _mnemo, _pub, _priv, wallet = Wallets.from_private_key(
                priv_bytes, version=WalletVersionEnum.v4r2, workchain=0
            )

            # Fetch seqno
            wallet_address = wallet.address.to_string(True, True, False)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url}runGetMethod",
                    params={
                        "address": wallet_address,
                        "method": "seqno",
                        "stack": "[]",
                    },
                ) as resp:
                    seqno_data = await resp.json()

            if seqno_data.get("ok") and seqno_data["result"]["exit_code"] == 0:
                seqno = int(seqno_data["result"]["stack"][0][1], 16)
            else:
                seqno = 0

            transfer = wallet.create_transfer_message(
                to_addr=address,
                amount=nano_amount,
                seqno=seqno,
                payload="",
            )
            boc = bytes_to_b64str(transfer["message"].to_boc(False))

        except ImportError:
            raise NotImplementedError(
                "TON native transfer requires tonsdk — "
                "install it with: pip install tonsdk"
            )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{rpc_url}sendBoc",
                json={"boc": boc},
            ) as resp:
                result = await resp.json()

        if not result.get("ok"):
            raise RuntimeError(f"TON sendBoc failed: {result.get('error', result)}")

        # TON Center does not return a tx hash from sendBoc synchronously;
        # we use a placeholder and note that explorers can find it by address.
        tx_hash = result.get("result", {}).get("@extra", None)
        if not tx_hash:
            tx_hash = None

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
        """TON has no token assets in the registry — this should never be called."""
        return DripResult(
            success=False,
            tx_hash=None,
            explorer_url=None,
            error=f"{asset_id} not yet deployed (TBD)",
            amount=amount,
            asset=asset_id,
        )
