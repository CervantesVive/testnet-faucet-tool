"""Unit tests for handlers/tron.py (TronHandler)."""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult


# ---------------------------------------------------------------------------
# Helpers: mock cryptography + _private_key_to_address
# ---------------------------------------------------------------------------

def _make_tron_crypto_modules():
    """Return sys.modules patches for the cryptography package (EC variant)."""
    mock_pub_bytes = b"\x04" + bytes(64)  # fake uncompressed EC pubkey

    mock_pub_key = MagicMock()
    mock_pub_key.public_bytes.return_value = mock_pub_bytes

    mock_priv_key = MagicMock()
    mock_priv_key.public_key.return_value = mock_pub_key

    mock_ec_mod = MagicMock()
    mock_ec_mod.SECP256K1.return_value = MagicMock()
    mock_ec_mod.derive_private_key.return_value = mock_priv_key
    mock_ec_mod.ECDSA = MagicMock()
    mock_ec_mod.EllipticCurvePrivateKey = MagicMock()

    mock_serialization = MagicMock()
    # Encoding.X962 and PublicFormat.UncompressedPoint are used as named attrs
    mock_encoding = MagicMock()
    mock_encoding.X962 = "X962"
    mock_pub_format = MagicMock()
    mock_pub_format.UncompressedPoint = "UncompressedPoint"
    mock_serialization.Encoding = mock_encoding
    mock_serialization.PublicFormat = mock_pub_format

    mock_hashes = MagicMock()
    mock_hashes.Prehashed.return_value = MagicMock()

    mock_dss_utils = MagicMock()
    mock_dss_utils.decode_dss_signature.return_value = (1, 1)

    modules = {
        "cryptography": MagicMock(),
        "cryptography.hazmat": MagicMock(),
        "cryptography.hazmat.primitives": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric.ec": mock_ec_mod,
        "cryptography.hazmat.primitives.asymmetric.ed25519": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric.utils": mock_dss_utils,
        "cryptography.hazmat.primitives.serialization": mock_serialization,
        "cryptography.hazmat.primitives.hashes": mock_hashes,
        "cryptography.hazmat.backends": MagicMock(),
    }
    return modules

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "tron",
    "blockchain": "Tron",
    "network": "nile",
    "rpc_url": "https://nile.trongrid.io",
    "explorer": "https://nile.tronscan.org/#/transaction/{tx_hash}",
    "native_asset": True,
    "drip_amount": "100",
    "decimals": 6,
}

TOKEN_TBD_CONFIG = {
    "family": "tron",
    "native_asset": False,
    "contract_address": "TBD",
    "rpc_url": "https://nile.trongrid.io",
    "explorer": "https://nile.tronscan.org/#/transaction/{tx_hash}",
    "drip_amount": "10",
    "decimals": 6,
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Valid Tron addresses start with T and are 34 chars (base58)
VALID_TRON_ADDRESS = "TN9RRaXkCFtTXRso2GdTZxSxxwufzxLwKW"
# A known-invalid address
INVALID_TRON_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"

# A valid 32-byte private key (all 0xaa bytes)
VALID_PRIVATE_KEY_HEX = "aa" * 32

# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_tron_address(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_TRON_ADDRESS) is True

    def test_invalid_ethereum_address(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_TRON_ADDRESS) is False

    def test_invalid_too_short(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address("TN9RRaX") is False

    def test_invalid_too_long(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address("T" + "A" * 34) is False

    def test_invalid_wrong_prefix(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        # 34 chars but starts with something other than T
        assert handler.validate_address("AN9RRaXkCFtTXRso2GdTZxSxxwufzxLwKW") is False

    def test_invalid_empty(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_valid_address_format(self):
        """T + 33 alphanumeric chars = valid."""
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assert handler.validate_address("T" + "A" * 33) is True


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_count(self):
        from handlers.tron import TronHandler
        handler = TronHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 4, f"Expected 4 Tron assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_tron_family(self):
        from handlers.tron import TronHandler
        from core.registry import load_registry
        handler = TronHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry
            assert registry[asset_id].get("family") == "tron", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'tron'"
            )


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_drip_native_success(self):
        """Successful native TRX drip via createtransaction + broadcasttransaction."""
        from handlers.tron import TronHandler

        tx_id = "deadbeef" * 8  # 64-char hex txID

        create_tx_resp = {
            "txID": tx_id,
            "raw_data": {"contract": []},
            "raw_data_hex": "00",
        }
        broadcast_resp = {"result": True}

        sessions_created = []

        def make_session():
            idx = [0]
            responses_per_session = [
                [create_tx_resp],
                [broadcast_resp],
            ]
            session_num = len(sessions_created)
            responses = responses_per_session[min(session_num, len(responses_per_session) - 1)]

            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            resp_mocks = []
            for data in responses:
                r = AsyncMock()
                r.json = AsyncMock(return_value=data)
                r.__aenter__ = AsyncMock(return_value=r)
                r.__aexit__ = AsyncMock(return_value=None)
                resp_mocks.append(r)

            def post_side_effect(*args, **kwargs):
                i = idx[0]
                idx[0] += 1
                return resp_mocks[min(i, len(resp_mocks) - 1)]

            session.post = MagicMock(side_effect=post_side_effect)
            sessions_created.append(session)
            return session

        with patch("handlers.tron.TronHandler._private_key_to_address", return_value=VALID_TRON_ADDRESS), \
             patch("handlers.tron._sign_tron_tx", return_value={
                 "txID": tx_id, "signature": ["aa" * 65], "raw_data": {}
             }), \
             patch("handlers.tron.aiohttp.ClientSession", side_effect=make_session):
            handler = TronHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_TRON_ADDRESS, "TTRX", "100")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.explorer_url is not None
        assert result.tx_hash in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    async def test_drip_native_no_wallet(self, monkeypatch):
        """Missing private key results in failed DripResult."""
        from handlers.tron import TronHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = TronHandler(NATIVE_CONFIG)
        result = await handler.drip(VALID_TRON_ADDRESS, "TTRX", "100")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_drip_native_createtransaction_error(self):
        """createtransaction API error returns failed DripResult."""
        from handlers.tron import TronHandler

        error_resp = {"Error": "BANDWITH_ERROR"}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=error_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch("handlers.tron.aiohttp.ClientSession", return_value=mock_session):
            handler = TronHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_TRON_ADDRESS, "TTRX", "100")

        assert result.success is False
        assert result.error is not None


# ---------------------------------------------------------------------------
# 4. drip token TBD
# ---------------------------------------------------------------------------

class TestDripTokenTBD:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_contract(self):
        """Token with contract_address='TBD' should fail immediately without network call."""
        from handlers.tron import TronHandler

        handler = TronHandler(TOKEN_TBD_CONFIG)
        result = await handler.drip(VALID_TRON_ADDRESS, "TTRX:USDC", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """No wallet configured returns 'no wallet configured'."""
        from handlers.tron import TronHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = TronHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_get_faucet_balance_success(self):
        """Should return formatted TRX balance string."""
        from handlers.tron import TronHandler

        # 100 TRX = 100_000_000 SUN (decimals=6)
        balance_resp = {"balance": 100_000_000}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=balance_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch("handlers.tron.TronHandler._private_key_to_address", return_value=VALID_TRON_ADDRESS), \
             patch("handlers.tron.aiohttp.ClientSession", return_value=mock_session):
            handler = TronHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        # 100_000_000 / 10^6 = 100.000000
        assert "100" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_get_faucet_balance_zero_balance(self):
        """Account with zero balance (or not found) should return zero-formatted string."""
        from handlers.tron import TronHandler

        balance_resp = {}  # no 'balance' key -> defaults to 0

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=balance_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch("handlers.tron.TronHandler._private_key_to_address", return_value=VALID_TRON_ADDRESS), \
             patch("handlers.tron.aiohttp.ClientSession", return_value=mock_session):
            handler = TronHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "0" in val
