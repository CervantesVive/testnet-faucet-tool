import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class TronHandler(BaseHandler):
    """Handler for Tron chains (native TRX and TRC-20 token transfers).

    Uses the Tron HTTP API directly via aiohttp since tronpy is not installed.
    Native transfers use /wallet/easytransfer (broadcast + wait) or the raw
    /wallet/createtransaction + /wallet/broadcasttransaction flow.
    """

    def _get_private_key_bytes(self) -> bytes:
        """Return the 32-byte private key from env vars.

        Resolution order:
        1. FAUCET_PRIVATE_KEY — 64-char hex private key
        2. FAUCET_MNEMONIC    — BIP-44 derivation (requires hdwallet)
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            hex_key = private_key.removeprefix("0x")
            return bytes.fromhex(hex_key)

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            try:
                from hdwallet import HDWallet
                from hdwallet.symbols import TRX

                hdw = HDWallet(symbol=TRX)
                hdw.from_mnemonic(mnemonic)
                hdw.from_path("m/44'/195'/0'/0/0")
                hex_key = hdw.private_key()
                return bytes.fromhex(hex_key)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not derive Tron key from mnemonic: {exc}"
                )

        raise RuntimeError(
            "Tron wallet not configured: set FAUCET_PRIVATE_KEY or FAUCET_MNEMONIC"
        )

    def _private_key_to_address(self, priv_bytes: bytes) -> str:
        """Derive the Tron base58check address from a 32-byte private key."""
        from cryptography.hazmat.primitives.asymmetric.ec import (
            SECP256K1,
            EllipticCurvePrivateKey,
            derive_private_key,
        )
        from cryptography.hazmat.backends import default_backend
        import hashlib

        priv_int = int.from_bytes(priv_bytes, "big")
        priv_obj = derive_private_key(priv_int, SECP256K1(), default_backend())
        pub_key = priv_obj.public_key()

        # Uncompressed public key (65 bytes: 04 || x || y)
        pub_bytes = pub_key.public_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.X962,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.UncompressedPoint,
        )

        # keccak256 of the 64-byte uncompressed coordinates (drop 0x04 prefix)
        keccak = _keccak256(pub_bytes[1:])

        # Take last 20 bytes, prepend 0x41 (Tron address prefix)
        addr_bytes = b"\x41" + keccak[-20:]

        return _base58check_encode(addr_bytes)

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
        """Return True if *address* looks like a valid Tron address.

        Tron addresses start with 'T' and are 34 base58 characters.
        """
        return bool(re.match(r'^T[A-Za-z0-9]{33}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet TRX balance.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "Tron")
        try:
            try:
                priv_bytes = self._get_private_key_bytes()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            faucet_address = self._private_key_to_address(priv_bytes)
            rpc_url = self.config["rpc_url"].rstrip("/")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{rpc_url}/wallet/getaccount",
                    json={"address": faucet_address, "visible": True},
                ) as resp:
                    data = await resp.json()

            balance_sun = data.get("balance", 0)
            decimals = self.config.get("decimals", 6)
            formatted = f"{balance_sun / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'tron'."""
        return [k for k, v in load_registry().items() if v.get("family") == "tron"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native TRX transfer using the Tron HTTP API."""
        priv_bytes = self._get_private_key_bytes()
        faucet_address = self._private_key_to_address(priv_bytes)
        rpc_url = self.config["rpc_url"].rstrip("/")

        decimals = self.config.get("decimals", 6)
        sun_amount = int(float(amount) * (10 ** decimals))

        async with aiohttp.ClientSession() as session:
            # Step 1: create unsigned transaction
            async with session.post(
                f"{rpc_url}/wallet/createtransaction",
                json={
                    "owner_address": faucet_address,
                    "to_address": address,
                    "amount": sun_amount,
                    "visible": True,
                },
            ) as resp:
                tx_data = await resp.json()

        if "Error" in tx_data or not tx_data.get("txID"):
            raise RuntimeError(f"Tron createtransaction failed: {tx_data}")

        # Step 2: sign transaction
        signed_tx = _sign_tron_tx(tx_data, priv_bytes)

        async with aiohttp.ClientSession() as session:
            # Step 3: broadcast
            async with session.post(
                f"{rpc_url}/wallet/broadcasttransaction",
                json=signed_tx,
            ) as resp:
                result = await resp.json()

        if not result.get("result"):
            raise RuntimeError(f"Tron broadcasttransaction failed: {result}")

        tx_hash = signed_tx["txID"]
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
        """Send a TRC-20 token transfer.

        Returns a failed DripResult immediately if the contract_address is TBD.
        """
        if self.config.get("contract_address", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        # Full TRC-20 triggersmartcontract implementation would go here.
        raise NotImplementedError("Tron TRC-20 token transfer not yet implemented")


# ---------------------------------------------------------------------------
# Crypto helpers (no external deps beyond cryptography)
# ---------------------------------------------------------------------------

def _keccak256(data: bytes) -> bytes:
    """Compute keccak-256 hash using pysha3 or pycryptodome if available,
    falling back to a pure-Python implementation."""
    try:
        import sha3  # pysha3
        h = sha3.keccak_256()
        h.update(data)
        return h.digest()
    except ImportError:
        pass
    try:
        from Crypto.Hash import keccak
        h = keccak.new(digest_bits=256)
        h.update(data)
        return h.digest()
    except ImportError:
        pass
    # Pure-Python fallback (slow but correct)
    return _keccak256_pure(data)


def _base58check_encode(payload: bytes) -> str:
    """Encode bytes with a double-SHA256 checksum in base58."""
    import hashlib
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    result = []
    while n > 0:
        n, r = divmod(n, 58)
        result.append(alphabet[r])
    padding = len(data) - len(data.lstrip(b"\x00"))
    return "1" * padding + "".join(reversed(result))


def _sign_tron_tx(tx_data: dict, priv_bytes: bytes) -> dict:
    """Sign a Tron transaction dict and return it with the 'signature' field."""
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1,
        derive_private_key,
        ECDSA,
    )
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes

    tx_id_bytes = bytes.fromhex(tx_data["txID"])

    priv_int = int.from_bytes(priv_bytes, "big")
    priv_obj = derive_private_key(priv_int, SECP256K1(), default_backend())

    # Sign the raw txID bytes (already a sha256 hash)
    # Tron expects a 65-byte (r, s, v) signature
    der_sig = priv_obj.sign(tx_id_bytes, ECDSA(hashes.Prehashed()))
    r, s = decode_dss_signature(der_sig)

    # Recovery id: try v=0 and v=1, pick the one whose public key matches
    pub_bytes_expected = priv_obj.public_key().public_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.X962,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.UncompressedPoint,
    )

    v = _recover_v(tx_id_bytes, r, s, pub_bytes_expected)
    sig_hex = f"{r:064x}{s:064x}{v:02x}"

    signed = dict(tx_data)
    signed["signature"] = [sig_hex]
    return signed


def _recover_v(msg_hash: bytes, r: int, s: int, expected_pub: bytes) -> int:
    """Determine the recovery id (0 or 1) for the given (r,s) signature."""
    for v in (0, 1):
        try:
            recovered = _ec_recover(msg_hash, r, s, v)
            if recovered == expected_pub:
                return v
        except Exception:
            pass
    return 0


def _ec_recover(msg_hash: bytes, r: int, s: int, v: int) -> bytes:
    """Recover the uncompressed public key from (hash, r, s, v)."""
    # Use coincurve if available (fastest)
    try:
        import coincurve
        sig_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v])
        pub = coincurve.PublicKey.from_signature_and_message(
            sig_bytes, msg_hash, hasher=None
        )
        return pub.format(compressed=False)
    except ImportError:
        pass

    # Manual secp256k1 recovery using cryptography primitives
    # This is best-effort; fall back to v=0 if it fails
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
    Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
    Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
    n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

    x = r + v * n
    if x >= p:
        raise ValueError("x out of range")

    # Compute y from x using secp256k1 curve equation: y^2 = x^3 + 7 (mod p)
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    if (y % 2) != (v % 2):
        y = p - y

    # R point
    R = (x, y)

    # Recover Q = r^-1 * (s*R - e*G)
    e = int.from_bytes(msg_hash, "big")
    r_inv = pow(r, n - 2, n)

    sR = _ec_mul(R, s, p, n, Gx, Gy)
    eG = _ec_mul((Gx, Gy), (-e) % n, p, n, Gx, Gy)
    Q = _ec_add(sR, eG, p)
    Q = _ec_mul(Q, r_inv, p, n, Gx, Gy)

    # Encode as uncompressed point
    return b"\x04" + Q[0].to_bytes(32, "big") + Q[1].to_bytes(32, "big")


def _ec_add(P, Q, p):
    if P is None:
        return Q
    if Q is None:
        return P
    if P[0] == Q[0]:
        if P[1] != Q[1]:
            return None
        return _ec_double(P, p)
    lam = (Q[1] - P[1]) * pow(Q[0] - P[0], p - 2, p) % p
    x = (lam * lam - P[0] - Q[0]) % p
    y = (lam * (P[0] - x) - P[1]) % p
    return (x, y)


def _ec_double(P, p):
    lam = (3 * P[0] * P[0]) * pow(2 * P[1], p - 2, p) % p
    x = (lam * lam - 2 * P[0]) % p
    y = (lam * (P[0] - x) - P[1]) % p
    return (x, y)


def _ec_mul(P, k, p, n, Gx, Gy):
    R = None
    Q = P
    while k > 0:
        if k & 1:
            R = _ec_add(R, Q, p)
        Q = _ec_double(Q, p)
        k >>= 1
    return R


# ---------------------------------------------------------------------------
# Pure-Python keccak-256 fallback
# ---------------------------------------------------------------------------

def _keccak256_pure(data: bytes) -> bytes:
    """Pure-Python keccak-256 (based on the reference implementation)."""
    # Round constants
    RC = [
        0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
        0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
        0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
        0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
        0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
        0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
    ]
    ROT = [
        [0, 36, 3, 41, 18],
        [1, 44, 10, 45, 2],
        [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56],
        [27, 20, 39, 8, 14],
    ]

    rate_bytes = 136  # keccak-256: rate = 1088 bits = 136 bytes

    # Padding
    msg = bytearray(data)
    msg.append(0x01)
    while len(msg) % rate_bytes != 0:
        msg.append(0x00)
    msg[-1] |= 0x80

    # State
    state = [[0] * 5 for _ in range(5)]

    def rot64(v, n):
        return ((v << n) | (v >> (64 - n))) & 0xFFFFFFFFFFFFFFFF

    def keccak_f(st):
        for _ in range(24):
            # Theta
            C = [st[x][0] ^ st[x][1] ^ st[x][2] ^ st[x][3] ^ st[x][4] for x in range(5)]
            D = [C[(x - 1) % 5] ^ rot64(C[(x + 1) % 5], 1) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    st[x][y] ^= D[x]
            # Rho + Pi
            B = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    B[y][(2 * x + 3 * y) % 5] = rot64(st[x][y], ROT[x][y])
            # Chi
            for x in range(5):
                for y in range(5):
                    st[x][y] = B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y])
            # Iota
            st[0][0] ^= RC[_]

    for block_start in range(0, len(msg), rate_bytes):
        block = msg[block_start:block_start + rate_bytes]
        for i in range(rate_bytes // 8):
            x, y = i % 5, i // 5
            word = int.from_bytes(block[i * 8:(i + 1) * 8], "little")
            state[x][y] ^= word
        keccak_f(state)

    output = b""
    for y in range(5):
        for x in range(5):
            output += state[x][y].to_bytes(8, "little")
            if len(output) >= 32:
                return output[:32]
    return output[:32]
