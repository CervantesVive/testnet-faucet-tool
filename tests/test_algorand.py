"""Unit tests for handlers/algorand.py (AlgorandHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.algorand import AlgorandHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "algorand",
    "blockchain": "Algorand",
    "network": "testnet",
    "rpc_url": "https://testnet-api.algonode.cloud",
    "explorer": "https://testnet.algoexplorer.io/tx/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 6,
}

TBD_CONFIG = {
    "family": "algorand",
    "blockchain": "Algorand",
    "rpc_url": "TBD",
    "native_asset": True,
    "decimals": 6,
}

# ---------------------------------------------------------------------------
# aiohttp mock helper
# ---------------------------------------------------------------------------

def _mock_aiohttp_session(response_data, is_json=True):
    mock_resp = AsyncMock()
    if is_json:
        mock_resp.json = AsyncMock(return_value=response_data)
    mock_resp.text = AsyncMock(return_value=str(response_data) if not is_json else "")
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=mock_session)


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_validate_address_valid(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        # 58 uppercase A-Z2-7 characters
        assert handler.validate_address("A" * 58) is True

    def test_validate_address_valid_mixed(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        assert handler.validate_address("VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA") is True

    def test_validate_address_invalid_lowercase(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        assert handler.validate_address("a" * 58) is False

    def test_validate_address_invalid_wrong_length(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        assert handler.validate_address("A" * 57) is False
        assert handler.validate_address("A" * 59) is False

    def test_validate_address_invalid_empty(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. drip
# ---------------------------------------------------------------------------

class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        result = await handler.drip("A" * 58, "TALGO", "1")
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "py-algorand-sdk" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_rpc(self):
        handler = AlgorandHandler(TBD_CONFIG)
        result = await handler.drip("A" * 58, "TALGO", "1")
        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 3. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        monkeypatch.delenv("FAUCET_ALGORAND_ADDRESS", raising=False)
        handler = AlgorandHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    async def test_get_faucet_balance_with_address(self, monkeypatch):
        monkeypatch.setenv("FAUCET_ALGORAND_ADDRESS", "A" * 58)
        mock_session_cls = _mock_aiohttp_session({"amount": 1000000})

        with patch("handlers.algorand.aiohttp.ClientSession", mock_session_cls):
            handler = AlgorandHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        # 1000000 / 10^6 = 1.000000
        assert "1.000000" in val


# ---------------------------------------------------------------------------
# 4. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_contains_talgo(self):
        handler = AlgorandHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TALGO" in assets

    def test_supported_assets_all_algorand_family(self):
        from core.registry import load_registry
        handler = AlgorandHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert registry[asset_id].get("family") == "algorand"
