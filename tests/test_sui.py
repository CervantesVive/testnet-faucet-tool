"""Unit tests for handlers/sui.py (SuiHandler)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "sui",
    "blockchain": "Sui",
    "network": "devnet",
    "faucet_url": "https://faucet.devnet.sui.io/gas",
    "explorer": "https://suiexplorer.com/txblock/{tx_hash}?network=devnet",
    "native_asset": True,
    "drip_amount": "0.5",
    "decimals": 9,
    "rpc_url": "https://fullnode.devnet.sui.io",
}

TOKEN_TBD_CONFIG = {
    "family": "sui",
    "native_asset": False,
    "object_type": "TBD",
}

# ---------------------------------------------------------------------------
# Test addresses
# ---------------------------------------------------------------------------

VALID_SUI_ADDRESS = "0x" + "a" * 64
INVALID_SUI_ADDRESS_SHORT = "0x" + "a" * 63
INVALID_SUI_ADDRESS_NO_PREFIX = "a" * 64


# ---------------------------------------------------------------------------
# aiohttp mock helpers
# ---------------------------------------------------------------------------

def _make_post_session_mock(json_return_value):
    """Return a context-manager-compatible aiohttp.ClientSession mock for POST."""
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=json_return_value)
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_address(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_SUI_ADDRESS) is True

    def test_valid_address_mixed_case(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        addr = "0x" + "A" * 32 + "b" * 32
        assert handler.validate_address(addr) is True

    def test_invalid_address_too_short(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_SUI_ADDRESS_SHORT) is False

    def test_invalid_address_no_prefix(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_SUI_ADDRESS_NO_PREFIX) is False

    def test_invalid_address_empty(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_address_non_hex(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address("0x" + "g" * 64) is False

    def test_invalid_address_too_long(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assert handler.validate_address("0x" + "a" * 65) is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_count(self):
        from handlers.sui import SuiHandler
        handler = SuiHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 3, f"Expected 3 Sui assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_sui_family(self):
        from handlers.sui import SuiHandler
        from core.registry import load_registry
        handler = SuiHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "sui", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'sui'"
            )


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    async def test_drip_native_success_transferred_gas_objects(self):
        """Success path: response has transferredGasObjects list."""
        from handlers.sui import SuiHandler

        faucet_response = {
            "transferredGasObjects": [
                {"transferTxDigest": "abc123digest"}
            ],
            "error": None,
        }
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.sui.aiohttp.ClientSession", return_value=mock_session):
            handler = SuiHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_SUI_ADDRESS, "TSUI", "0.5")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == "abc123digest"
        assert result.explorer_url is not None
        assert "abc123digest" in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    async def test_drip_native_success_task_field(self):
        """Success path: async faucet returns 'task' field instead."""
        from handlers.sui import SuiHandler

        faucet_response = {"task": "task-uuid-xyz", "error": None}
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.sui.aiohttp.ClientSession", return_value=mock_session):
            handler = SuiHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_SUI_ADDRESS, "TSUI", "0.5")

        assert result.success is True
        assert result.tx_hash == "task-uuid-xyz"
        assert result.explorer_url is not None
        assert "task-uuid-xyz" in result.explorer_url

    @pytest.mark.asyncio
    async def test_drip_native_failure_exception(self):
        """Failure path: POST raises an exception."""
        from handlers.sui import SuiHandler

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(side_effect=Exception("connection refused"))

        with patch("handlers.sui.aiohttp.ClientSession", return_value=mock_session):
            handler = SuiHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_SUI_ADDRESS, "TSUI", "0.5")

        assert result.success is False
        assert result.error is not None
        assert "connection refused" in result.error

    @pytest.mark.asyncio
    async def test_drip_native_no_tx_hash_in_response(self):
        """If response has no recognizable tx hash fields, tx_hash is None but success is True."""
        from handlers.sui import SuiHandler

        faucet_response = {"error": None}
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.sui.aiohttp.ClientSession", return_value=mock_session):
            handler = SuiHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_SUI_ADDRESS, "TSUI", "0.5")

        assert result.success is True
        assert result.tx_hash is None
        assert result.explorer_url is None


# ---------------------------------------------------------------------------
# 4. drip token (TBD)
# ---------------------------------------------------------------------------

class TestDripToken:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_fails_immediately(self):
        """Token with object_type='TBD' should fail without any network call."""
        from handlers.sui import SuiHandler

        handler = SuiHandler(TOKEN_TBD_CONFIG)
        # No network mock — if a network call is made, the test will raise
        result = await handler.drip(VALID_SUI_ADDRESS, "TSUI:DEEP", "1")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error

    @pytest.mark.asyncio
    async def test_drip_token_wal_tbd_fails_immediately(self):
        """TSUI:WAL with object_type='TBD' should also fail immediately."""
        from handlers.sui import SuiHandler

        handler = SuiHandler(TOKEN_TBD_CONFIG)
        result = await handler.drip(VALID_SUI_ADDRESS, "TSUI:WAL", "1")

        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """With no wallet env vars, returns 'no wallet configured'."""
        from handlers.sui import SuiHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = SuiHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert "no wallet" in all_values, f"Expected 'no wallet configured', got: {balance}"

    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_rpc_url(self, monkeypatch):
        """With no rpc_url in config, returns 'no wallet configured'."""
        from handlers.sui import SuiHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        config_no_rpc = {**NATIVE_CONFIG}
        del config_no_rpc["rpc_url"]

        handler = SuiHandler(config_no_rpc)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert "no wallet" in all_values, f"Expected graceful message, got: {balance}"
