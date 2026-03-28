"""Unit tests for handlers/ton.py (TonHandler)."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "ton",
    "blockchain": "TON",
    "network": "testnet",
    "rpc_url": "https://testnet.toncenter.com/api/v2/",
    "explorer": "https://testnet.tonscan.org/tx/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 9,
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Raw TON address format: 0:<64 hex chars>
VALID_RAW_ADDRESS = "0:" + "a" * 64
# Base64url friendly address (48 chars)
VALID_B64_ADDRESS = "EQD" + "A" * 45
# 64-char hex (no prefix)
VALID_HEX_ADDRESS = "b" * 64

INVALID_ADDRESS = "0xinvalid"

# A valid 32-byte private key (hex)
VALID_PRIVATE_KEY_HEX = "bb" * 32

# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_raw_address(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_RAW_ADDRESS) is True

    def test_valid_base64url_address(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        # 48 alphanumeric/dash/underscore chars
        addr = "A" * 48
        assert handler.validate_address(addr) is True

    def test_valid_hex_address_no_prefix(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_HEX_ADDRESS) is True

    def test_invalid_address(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_ADDRESS) is False

    def test_invalid_empty(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_raw_wrong_hex_length(self):
        """0: prefix with fewer than 64 hex chars should be invalid."""
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address("0:" + "a" * 32) is False

    def test_invalid_b64_wrong_length(self):
        """47-char base64url address should be invalid."""
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assert handler.validate_address("A" * 47) is False

    def test_valid_base64url_with_dashes(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        # 48 chars with dashes and underscores
        addr = "EQ" + "A" * 44 + "--"
        assert handler.validate_address(addr) is True


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_count(self):
        from handlers.ton import TonHandler
        handler = TonHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 1, f"Expected 1 TON asset, got {len(assets)}: {assets}"

    def test_supported_assets_all_ton_family(self):
        from handlers.ton import TonHandler
        from core.registry import load_registry
        handler = TonHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry
            assert registry[asset_id].get("family") == "ton", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'ton'"
            )


# ---------------------------------------------------------------------------
# 3. drip native (tonsdk unavailable)
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_drip_native_tonsdk_unavailable_returns_failure(self):
        """When tonsdk is not installed, drip() should return DripResult(success=False)."""
        from handlers.ton import TonHandler

        # The handler tries `from tonsdk.contract.wallet import ...` in _drip_native.
        # If tonsdk is unavailable it raises NotImplementedError, which the outer
        # drip() catches and wraps in a failed DripResult.
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("tonsdk"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            handler = TonHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_RAW_ADDRESS, "TTON", "1")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_drip_native_no_wallet(self, monkeypatch):
        """Missing private key results in failed DripResult."""
        from handlers.ton import TonHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = TonHandler(NATIVE_CONFIG)
        result = await handler.drip(VALID_RAW_ADDRESS, "TTON", "1")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_drip_native_with_tonsdk_success(self):
        """When tonsdk is available and sendBoc returns ok=True, drip() succeeds."""
        from handlers.ton import TonHandler

        sendBoc_resp = {"ok": True, "result": {"@extra": "abc123"}}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=sendBoc_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        seqno_resp = {
            "ok": True,
            "result": {
                "exit_code": 0,
                "stack": [["num", "0x0"]],
            },
        }
        seqno_mock = AsyncMock()
        seqno_mock.json = AsyncMock(return_value=seqno_resp)
        seqno_mock.__aenter__ = AsyncMock(return_value=seqno_mock)
        seqno_mock.__aexit__ = AsyncMock(return_value=None)

        sessions_created = []

        def make_session():
            idx = [0]
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            session.get = MagicMock(return_value=seqno_mock)
            session.post = MagicMock(return_value=mock_resp)
            sessions_created.append(session)
            return session

        # Mock tonsdk modules
        mock_wallet = MagicMock()
        mock_wallet.address.to_string.return_value = VALID_RAW_ADDRESS

        mock_transfer = MagicMock()
        mock_message = MagicMock()
        mock_message.to_boc.return_value = b"fakeboc"
        mock_transfer.__getitem__ = MagicMock(return_value=mock_message)
        mock_wallet.create_transfer_message.return_value = mock_transfer

        mock_wallets = MagicMock()
        mock_wallets.from_private_key.return_value = (None, None, None, mock_wallet)

        mock_wallet_version = MagicMock()
        mock_wallet_version.v4r2 = "v4r2"

        mock_tonsdk_contract_wallet = MagicMock()
        mock_tonsdk_contract_wallet.WalletVersionEnum = mock_wallet_version
        mock_tonsdk_contract_wallet.Wallets = mock_wallets

        mock_tonsdk_utils = MagicMock()
        mock_tonsdk_utils.bytes_to_b64str.return_value = "ZmFrZWJvYw=="

        import sys
        tonsdk_modules = {
            "tonsdk": MagicMock(),
            "tonsdk.contract": MagicMock(),
            "tonsdk.contract.wallet": mock_tonsdk_contract_wallet,
            "tonsdk.utils": mock_tonsdk_utils,
        }

        with patch.dict(sys.modules, tonsdk_modules), \
             patch("handlers.ton.aiohttp.ClientSession", side_effect=make_session):
            handler = TonHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_RAW_ADDRESS, "TTON", "1")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.error is None


# ---------------------------------------------------------------------------
# 4. drip token (defensive — _drip_token always returns TBD failure)
# ---------------------------------------------------------------------------

class TestDripTokenDefensive:
    @pytest.mark.asyncio
    async def test_drip_token_path_returns_tbd_failure(self):
        """Calling drip with native_asset=False triggers _drip_token which returns TBD error."""
        from handlers.ton import TonHandler

        non_native_config = {**NATIVE_CONFIG, "native_asset": False}
        handler = TonHandler(non_native_config)
        result = await handler.drip(VALID_RAW_ADDRESS, "TTON:FAKE", "1")

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
        from handlers.ton import TonHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = TonHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_get_faucet_balance_success(self):
        """Should return formatted TON balance string."""
        from handlers.ton import TonHandler

        # 1 TON = 10^9 nanoTON
        nano_ton = 10 ** 9
        balance_resp = {"ok": True, "result": str(nano_ton)}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=balance_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_resp)

        with patch("handlers.ton.TonHandler._get_wallet_address", return_value=VALID_RAW_ADDRESS), \
             patch("handlers.ton.aiohttp.ClientSession", return_value=mock_session):
            handler = TonHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        # 1_000_000_000 / 10^9 = 1.000000000
        assert "1" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIVATE_KEY_HEX}, clear=False)
    async def test_get_faucet_balance_api_error(self):
        """API error (ok=False) should return error message."""
        from handlers.ton import TonHandler

        error_resp = {"ok": False, "error": "Invalid address"}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=error_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_resp)

        with patch("handlers.ton.TonHandler._get_wallet_address", return_value=VALID_RAW_ADDRESS), \
             patch("handlers.ton.aiohttp.ClientSession", return_value=mock_session):
            handler = TonHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "error" in val
