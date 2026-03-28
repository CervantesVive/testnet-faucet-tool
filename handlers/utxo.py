import os
import re
import hashlib
import struct

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class UtxoHandler(BaseHandler):
    """Handler for UTXO-based chains (BTC, BCH, BTG, LTC, DOGE, DASH).

    Uses the Blockstream-style REST API directly via aiohttp.  No SDK is
    required for the API calls themselves.  Private-key derivation and
    transaction signing depend on the ``cryptography`` package (secp256k1).

    Chains whose ``rpc_url`` is still ``"TBD"`` will return a helpful error
    without making any network call.
    """

    # Map coin_type -> BIP-44 path index
    _COIN_TYPES = {1: 1, 145: 145, 156: 156, 2: 2, 3: 3, 5: 5}

    # ------------------------------------------------------------------
    # Wallet helpers
    # ------------------------------------------------------------------

    def _get_private_key_bytes(self) -> bytes:
        """Return the 32-byte private key from env vars.

        Resolution order:
        1. FAUCET_PRIVATE_KEY -- 64-char hex private key
        2. FAUCET_MNEMONIC    -- BIP-44 derivation (requires hdwallet)
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            hex_key = private_key.removeprefix("0x")
            return bytes.fromhex(hex_key)

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            try:
                from hdwallet import HDWallet

                coin_type = self.config.get("coin_type", 1)
                hdw = HDWallet(cryptocurrency="Bitcoin")
                hdw.from_mnemonic(mnemonic)
                hdw.from_path(f"m/44'/{coin_type}'/0'/0/0")
                hex_key = hdw.private_key()
                return bytes.fromhex(hex_key)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not derive UTXO key from mnemonic: {exc}"
                )

        raise RuntimeError(
            "UTXO wallet not configured: set FAUCET_PRIVATE_KEY or FAUCET_MNEMONIC"
        )

    def _get_faucet_address(self) -> str:
        """Derive the faucet address from the private key.

        For BTC testnet (coin_type 1) this produces a P2WPKH (tb1...) address.
        For other UTXO chains it produces a P2PKH address with the appropriate
        version byte.

        Requires ``cryptography`` for secp256k1 key derivation.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ec import (
                SECP256K1,
                derive_private_key,
            )
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                PublicFormat,
            )
        except ImportError as exc:
            raise RuntimeError(
                "cryptography package required for UTXO address derivation; "
                f"install with: pip install cryptography  ({exc})"
            )

        priv_bytes = self._get_private_key_bytes()
        priv_int = int.from_bytes(priv_bytes, "big")
        priv_obj = derive_private_key(priv_int, SECP256K1(), default_backend())
        pub_key = priv_obj.public_key()

        # Compressed public key (33 bytes)
        pub_compressed = pub_key.public_bytes(
            Encoding.X962, PublicFormat.CompressedPoint
        )

        coin_type = self.config.get("coin_type", 1)

        if coin_type == 1:
            # BTC testnet4: P2WPKH bech32 address (tb1...)
            return _pubkey_to_p2wpkh_testnet(pub_compressed)
        else:
            # Other UTXO chains: P2PKH with appropriate version byte
            version = _p2pkh_version_for_coin(coin_type)
            return _pubkey_to_p2pkh(pub_compressed, version)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet coins to *address*.

        All UTXO assets are native coins, so this always calls ``_drip_native``.
        All exceptions are caught and returned as a failed DripResult.
        """
        try:
            return await self._drip_native(address, asset_id, amount)
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
        """Return True if *address* looks valid for this UTXO chain.

        Dispatch is based on ``self.config["coin_type"]``.
        """
        coin_type = self.config.get("coin_type", 1)
        return _validate_utxo_address(address, coin_type)

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance.

        For TBD chains: ``{asset_id: "rpc_url not yet configured (TBD)"}``.
        On missing wallet: ``{asset_id: "no wallet configured"}``.
        """
        asset_id = self.config.get("blockchain", "BTC")

        rpc_url = self.config.get("rpc_url", "TBD")
        if rpc_url == "TBD":
            return {asset_id: "rpc_url not yet configured (TBD)"}

        try:
            try:
                faucet_address = self._get_faucet_address()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url.rstrip('/')}/address/{faucet_address}"
                ) as resp:
                    data = await resp.json()

            chain_stats = data.get("chain_stats", {})
            funded = chain_stats.get("funded_txo_sum", 0)
            spent = chain_stats.get("spent_txo_sum", 0)
            balance_sats = funded - spent

            decimals = self.config.get("decimals", 8)
            formatted = f"{balance_sats / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'utxo'."""
        return [k for k, v in load_registry().items() if v.get("family") == "utxo"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(
        self, address: str, asset_id: str, amount: str
    ) -> DripResult:
        """Send a native UTXO transfer.

        For chains with ``rpc_url == "TBD"`` this returns immediately with a
        helpful error message.  For TBTC4 (and eventually others) it builds a
        raw transaction, signs it, and broadcasts via the REST API.
        """
        rpc_url = self.config.get("rpc_url", "TBD")
        if rpc_url == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} rpc_url not yet configured (TBD)",
                amount=amount,
                asset=asset_id,
            )

        # Full UTXO flow: fetch UTXOs, build tx, sign, broadcast
        faucet_address = self._get_faucet_address()
        decimals = self.config.get("decimals", 8)
        sat_amount = int(float(amount) * (10 ** decimals))

        # Step 1: Fetch UTXOs for the faucet address
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{rpc_url.rstrip('/')}/address/{faucet_address}/utxo"
            ) as resp:
                utxos = await resp.json()

        if not utxos:
            raise RuntimeError("No UTXOs available for faucet address")

        # Step 2: Select UTXOs (simple greedy)
        selected, total_in = _select_utxos(utxos, sat_amount)

        # Estimate fee (rough: 10 sat/vbyte * ~250 vbytes for a simple tx)
        estimated_fee = 2500
        if total_in < sat_amount + estimated_fee:
            raise RuntimeError(
                f"Insufficient funds: have {total_in} sats, "
                f"need {sat_amount + estimated_fee} sats"
            )

        change = total_in - sat_amount - estimated_fee

        # Step 3: Build raw transaction
        priv_bytes = self._get_private_key_bytes()
        raw_tx = _build_and_sign_btc_tx(
            selected, address, sat_amount, faucet_address, change, priv_bytes
        )

        # Step 4: Broadcast
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{rpc_url.rstrip('/')}/tx",
                data=raw_tx.hex(),
                headers={"Content-Type": "text/plain"},
            ) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"Broadcast failed ({resp.status}): {resp_text}")
                tx_hash = resp_text.strip()

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


# ---------------------------------------------------------------------------
# Address validation helpers
# ---------------------------------------------------------------------------

def _validate_utxo_address(address: str, coin_type: int) -> bool:
    """Validate a UTXO address based on coin_type."""
    if not address:
        return False

    if coin_type == 1:
        # BTC testnet4: m, n, 2 (base58, 25-34 chars) or tb1 (bech32, up to 62 chars)
        if re.match(r'^[mn2][a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        if re.match(r'^tb1[a-z0-9]{8,78}$', address):
            return True
        return False

    if coin_type == 145:
        # BCH testnet: bchtest: prefix (cashaddr) or m, n (legacy base58)
        if address.startswith("bchtest:"):
            return len(address) >= 20
        if re.match(r'^[mn][a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        return False

    if coin_type == 156:
        # BTG testnet: m, n, 2 (base58)
        if re.match(r'^[mn2][a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        return False

    if coin_type == 2:
        # LTC testnet: m, n, Q (base58, 25-34 chars) or tltc1 (bech32)
        if re.match(r'^[mnQ][a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        if re.match(r'^tltc1[a-z0-9]{8,78}$', address):
            return True
        return False

    if coin_type == 3:
        # DOGE testnet: n, m (base58)
        if re.match(r'^[nm][a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        return False

    if coin_type == 5:
        # DASH testnet: y (base58)
        if re.match(r'^y[a-km-zA-HJ-NP-Z1-9]{24,33}$', address):
            return True
        return False

    return False


# ---------------------------------------------------------------------------
# Address derivation helpers
# ---------------------------------------------------------------------------

_P2PKH_VERSIONS = {
    1: 0x6F,    # BTC testnet
    145: 0x6F,  # BCH testnet
    156: 0x6F,  # BTG testnet
    2: 0x6F,    # LTC testnet
    3: 0x71,    # DOGE testnet
    5: 0x8C,    # DASH testnet (140 decimal)
}


def _p2pkh_version_for_coin(coin_type: int) -> int:
    """Return the P2PKH version byte for the given coin_type."""
    return _P2PKH_VERSIONS.get(coin_type, 0x6F)


def _pubkey_to_p2pkh(pub_compressed: bytes, version: int) -> str:
    """Derive a P2PKH address from a compressed public key."""
    sha = hashlib.sha256(pub_compressed).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    payload = bytes([version]) + ripe
    return _base58check_encode(payload)


def _pubkey_to_p2wpkh_testnet(pub_compressed: bytes) -> str:
    """Derive a P2WPKH bech32 address (tb1...) from a compressed public key."""
    sha = hashlib.sha256(pub_compressed).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    # witness version 0, 20-byte program
    return _bech32_encode("tb", 0, ripe)


def _base58check_encode(payload: bytes) -> str:
    """Encode bytes with a double-SHA256 checksum in base58."""
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


# ---------------------------------------------------------------------------
# Bech32 encoding (BIP-173)
# ---------------------------------------------------------------------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: list[int]) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: bytes, frombits: int, tobits: int, pad: bool = True) -> list[int]:
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def _bech32_encode(hrp: str, witver: int, witprog: bytes) -> str:
    data = [witver] + _convertbits(witprog, 8, 5)
    checksum = _bech32_create_checksum(hrp, data)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in data + checksum)


# ---------------------------------------------------------------------------
# Transaction building and signing (BTC testnet)
# ---------------------------------------------------------------------------

def _select_utxos(
    utxos: list[dict], target_sats: int
) -> tuple[list[dict], int]:
    """Greedily select UTXOs until we meet the target amount."""
    sorted_utxos = sorted(utxos, key=lambda u: u["value"], reverse=True)
    selected = []
    total = 0
    for utxo in sorted_utxos:
        selected.append(utxo)
        total += utxo["value"]
        if total >= target_sats:
            break
    return selected, total


def _build_and_sign_btc_tx(
    inputs: list[dict],
    dest_address: str,
    dest_amount: int,
    change_address: str,
    change_amount: int,
    priv_bytes: bytes,
) -> bytes:
    """Build and sign a raw Bitcoin transaction.

    This constructs a version 2 transaction with the provided inputs and
    outputs.  Signing uses ECDSA over secp256k1 via the ``cryptography``
    package.

    NOTE: This currently supports P2PKH signing.  SegWit (P2WPKH) signing
    requires witness serialisation which is a TODO.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ec import (
            SECP256K1,
            ECDSA,
            derive_private_key,
        )
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )
    except ImportError as exc:
        raise RuntimeError(
            f"cryptography package required for UTXO signing: {exc}"
        )

    priv_int = int.from_bytes(priv_bytes, "big")
    priv_obj = derive_private_key(priv_int, SECP256K1(), default_backend())
    pub_compressed = priv_obj.public_key().public_bytes(
        Encoding.X962, PublicFormat.CompressedPoint
    )

    # Build unsigned transaction
    version = struct.pack("<I", 2)
    locktime = struct.pack("<I", 0)

    # Encode inputs
    vin_count = _varint(len(inputs))
    vin_data = b""
    for inp in inputs:
        txid_bytes = bytes.fromhex(inp["txid"])[::-1]  # little-endian
        vout = struct.pack("<I", inp["vout"])
        vin_data += txid_bytes + vout + b"\x00" + b"\xff\xff\xff\xff"  # empty scriptSig, sequence

    # Encode outputs
    out_count = 1
    vout_data = b""
    vout_data += struct.pack("<q", dest_amount)
    dest_script = _address_to_scriptpubkey(dest_address)
    vout_data += _varint(len(dest_script)) + dest_script

    if change_amount > 0:
        out_count += 1
        vout_data += struct.pack("<q", change_amount)
        change_script = _address_to_scriptpubkey(change_address)
        vout_data += _varint(len(change_script)) + change_script

    vout_count = _varint(out_count)

    # For each input, create a signing digest (SIGHASH_ALL = 0x01)
    signed_vin_data = b""
    for idx, inp in enumerate(inputs):
        # Build the tx with scriptPubKey in the signing input, empty in others
        signing_tx = version + vin_count
        for j, jinp in enumerate(inputs):
            txid_bytes = bytes.fromhex(jinp["txid"])[::-1]
            vout = struct.pack("<I", jinp["vout"])
            if j == idx:
                # Insert the scriptPubKey of the input being signed
                # For P2PKH: OP_DUP OP_HASH160 <20-byte-hash> OP_EQUALVERIFY OP_CHECKSIG
                pubkey_hash = hashlib.new(
                    "ripemd160", hashlib.sha256(pub_compressed).digest()
                ).digest()
                script_code = (
                    b"\x76\xa9\x14" + pubkey_hash + b"\x88\xac"
                )
                signing_tx += txid_bytes + vout
                signing_tx += _varint(len(script_code)) + script_code
            else:
                signing_tx += txid_bytes + vout + b"\x00"
            signing_tx += b"\xff\xff\xff\xff"

        signing_tx += vout_count + vout_data + locktime
        signing_tx += struct.pack("<I", 1)  # SIGHASH_ALL

        # Double-SHA256
        sighash = hashlib.sha256(hashlib.sha256(signing_tx).digest()).digest()

        # Sign
        der_sig = priv_obj.sign(
            sighash, ECDSA(hashes.Prehashed(hashes.SHA256()))
        )
        r_val, s_val = decode_dss_signature(der_sig)

        # Encode as DER signature + SIGHASH byte
        sig_bytes = _encode_der_signature(r_val, s_val) + b"\x01"

        # Build scriptSig: <sig> <pubkey>
        script_sig = (
            bytes([len(sig_bytes)]) + sig_bytes +
            bytes([len(pub_compressed)]) + pub_compressed
        )

        txid_bytes = bytes.fromhex(inp["txid"])[::-1]
        vout_bytes = struct.pack("<I", inp["vout"])
        signed_vin_data += (
            txid_bytes + vout_bytes +
            _varint(len(script_sig)) + script_sig +
            b"\xff\xff\xff\xff"
        )

    return version + vin_count + signed_vin_data + vout_count + vout_data + locktime


def _encode_der_signature(r: int, s: int) -> bytes:
    """Encode (r, s) as a DER signature."""
    def _int_bytes(v: int) -> bytes:
        b = v.to_bytes((v.bit_length() + 8) // 8, "big")
        return b

    r_bytes = _int_bytes(r)
    s_bytes = _int_bytes(s)

    r_enc = b"\x02" + bytes([len(r_bytes)]) + r_bytes
    s_enc = b"\x02" + bytes([len(s_bytes)]) + s_bytes

    return b"\x30" + bytes([len(r_enc) + len(s_enc)]) + r_enc + s_enc


def _address_to_scriptpubkey(address: str) -> bytes:
    """Convert a Bitcoin address to its scriptPubKey."""
    if address.startswith("tb1") or address.startswith("tltc1"):
        # Bech32 P2WPKH: OP_0 <20-byte-hash>
        witprog = _bech32_decode_witness(address)
        return b"\x00\x14" + witprog
    else:
        # Base58 P2PKH: OP_DUP OP_HASH160 <20-byte-hash> OP_EQUALVERIFY OP_CHECKSIG
        payload = _base58check_decode(address)
        pubkey_hash = payload[1:]  # strip version byte
        return b"\x76\xa9\x14" + pubkey_hash + b"\x88\xac"


def _base58check_decode(address: str) -> bytes:
    """Decode a base58check-encoded address to raw bytes (including version)."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for char in address:
        n = n * 58 + alphabet.index(char)

    # Count leading '1's -> leading zero bytes
    padding = len(address) - len(address.lstrip("1"))
    data_len = 25  # version(1) + hash(20) + checksum(4)
    data = n.to_bytes(max(data_len, (n.bit_length() + 7) // 8), "big")

    # Trim to expected length if needed, preserving leading zeros
    if len(data) > data_len:
        data = data[-data_len:]

    data = b"\x00" * padding + data[padding:]

    payload, checksum = data[:-4], data[-4:]
    check = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if check != checksum:
        raise ValueError("Invalid base58check checksum")
    return payload


def _bech32_decode_witness(address: str) -> bytes:
    """Decode a bech32 address and return the witness program bytes."""
    # Find the separator
    pos = address.rfind("1")
    hrp = address[:pos]
    data_part = address[pos + 1:]

    decoded = [_BECH32_CHARSET.index(c) for c in data_part]
    # Strip checksum (last 6) and witness version (first 1)
    witver = decoded[0]
    data_5bit = decoded[1:-6]
    return bytes(_convertbits_decode(data_5bit, 5, 8, pad=False))


def _convertbits_decode(
    data: list[int], frombits: int, tobits: int, pad: bool = True
) -> list[int]:
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def _varint(n: int) -> bytes:
    """Encode an integer as a Bitcoin varint."""
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)
