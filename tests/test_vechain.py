"""Unit tests for handlers/vechain.py (VeChainHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.vechain import VeChainHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "vechain",
    "blockchain": "VeChain",
    "network": "testnet",
    "rpc_url": "https://testnet.veblocks.net",
    "explorer": "https://explore-testnet.vechain.org/transactions/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 18,
}

TOKEN_CONFIG = {
    "family": "vechain",
    "blockchain": "VeChain",
    "network": "testnet",
    "rpc_url": "https://testnet.veblocks.net",
    "explorer": "https://explore-testnet.vechain.org/transactions/{tx_hash}",
    "native_asset": False,
    "drip_amount": "10",
    "decimals": 18,
}

TBD_CONFIG = {
    "family": "vechain",
    "blockchain": "VeChain",
    "rpc_url": "TBD",
    "native_asset": True,
    "decimals": 18,
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
        handler = VeChainHandler(NATIVE_CONFIG)
        assert handler.validate_address("0x7567d83b7b8d80addcb281a71d54fc7b3364ffed") is True

    def test_validate_address_invalid_short(self):
        handler = VeChainHandler(NATIVE_CONFIG)
        assert handler.validate_address("0x123") is False

    def test_validate_address_invalid_no_prefix(self):
        handler = VeChainHandler(NATIVE_CONFIG)
        assert handler.validate_address("7567d83b7b8d80addcb281a71d54fc7b3364ffed") is False

    def test_validate_address_invalid_empty(self):
        handler = VeChainHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. drip
# ---------------------------------------------------------------------------

class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_native_no_sdk(self):
        handler = VeChainHandler(NATIVE_CONFIG)
        result = await handler.drip("0x7567d83b7b8d80addcb281a71d54fc7b3364ffed", "TVET", "1")
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "thor-devkit" in result.error

    @pytest.mark.asyncio
    async def test_drip_token_no_sdk(self):
        handler = VeChainHandler(TOKEN_CONFIG)
        result = await handler.drip("0x7567d83b7b8d80addcb281a71d54fc7b3364ffed", "TVET:VTHO", "10")
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "thor-devkit" in result.error

    @pytest.mark.asyncio
    async def test_drip_native_tbd_rpc(self):
        handler = VeChainHandler(TBD_CONFIG)
        result = await handler.drip("0x7567d83b7b8d80addcb281a71d54fc7b3364ffed", "TVET", "1")
        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 3. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        monkeypatch.delenv("FAUCET_VECHAIN_ADDRESS", raising=False)
        handler = VeChainHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    async def test_get_faucet_balance_with_address(self, monkeypatch):
        monkeypatch.setenv("FAUCET_VECHAIN_ADDRESS", "0x7567d83b7b8d80addcb281a71d54fc7b3364ffed")
        # 0xde0b6b3a7640000 = 1000000000000000000 = 1 VET (18 decimals)
        mock_session_cls = _mock_aiohttp_session({"balance": "0xde0b6b3a7640000"})

        with patch("handlers.vechain.aiohttp.ClientSession", mock_session_cls):
            handler = VeChainHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "1.000000000000000000" in val


# ---------------------------------------------------------------------------
# 4. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_contains_tvet(self):
        handler = VeChainHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TVET" in assets

    def test_supported_assets_all_vechain_family(self):
        from core.registry import load_registry
        handler = VeChainHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert registry[asset_id].get("family") == "vechain"
