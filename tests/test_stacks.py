"""Unit tests for handlers/stacks.py (StacksHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.stacks import StacksHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "stacks",
    "blockchain": "Stacks",
    "network": "testnet",
    "rpc_url": "https://stacks-node-api.testnet.stacks.co",
    "explorer": "https://explorer.stacks.co/txid/{tx_hash}?chain=testnet",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 6,
}

TBD_CONFIG = {
    "family": "stacks",
    "blockchain": "Stacks",
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
        handler = StacksHandler(NATIVE_CONFIG)
        assert handler.validate_address("ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG") is True

    def test_validate_address_invalid_mainnet(self):
        """SP prefix is mainnet, should be rejected."""
        handler = StacksHandler(NATIVE_CONFIG)
        assert handler.validate_address("SP2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG") is False

    def test_validate_address_invalid_short(self):
        handler = StacksHandler(NATIVE_CONFIG)
        assert handler.validate_address("ST123") is False

    def test_validate_address_invalid_empty(self):
        handler = StacksHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. drip
# ---------------------------------------------------------------------------

class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        handler = StacksHandler(NATIVE_CONFIG)
        result = await handler.drip("ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG", "TSTX", "1")
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "stacks SDK" in result.error.lower() or "stacks sdk" in result.error.lower()

    @pytest.mark.asyncio
    async def test_drip_tbd_rpc(self):
        handler = StacksHandler(TBD_CONFIG)
        result = await handler.drip("ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG", "TSTX", "1")
        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 3. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        monkeypatch.delenv("FAUCET_STACKS_ADDRESS", raising=False)
        handler = StacksHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    async def test_get_faucet_balance_with_address(self, monkeypatch):
        monkeypatch.setenv("FAUCET_STACKS_ADDRESS", "ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG")
        # balance "0x1" -> 1 in decimal -> 1 / 10^6 = 0.000001
        mock_session_cls = _mock_aiohttp_session({"balance": "0x1"})

        with patch("handlers.stacks.aiohttp.ClientSession", mock_session_cls):
            handler = StacksHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "0.000001" in val


# ---------------------------------------------------------------------------
# 4. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_contains_tstx(self):
        handler = StacksHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TSTX" in assets

    def test_supported_assets_all_stacks_family(self):
        from core.registry import load_registry
        handler = StacksHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert registry[asset_id].get("family") == "stacks"
