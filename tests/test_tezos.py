"""Unit tests for handlers/tezos.py (TezosHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.tezos import TezosHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "tezos",
    "blockchain": "Tezos",
    "network": "ghostnet",
    "rpc_url": "https://rpc.ghostnet.teztnets.com",
    "explorer": "https://ghostnet.tzkt.io/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 6,
}

TBD_CONFIG = {
    "family": "tezos",
    "blockchain": "Tezos",
    "rpc_url": "TBD",
    "native_asset": True,
    "decimals": 6,
}

# ---------------------------------------------------------------------------
# aiohttp mock helper
# ---------------------------------------------------------------------------

def _mock_aiohttp_session_text(response_text):
    """Return a mock aiohttp session that returns text (not JSON) from resp.text()."""
    mock_resp = AsyncMock()
    mock_resp.text = AsyncMock(return_value=response_text)
    mock_resp.json = AsyncMock(return_value=response_text)
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
    def test_validate_address_valid_tz1(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assert handler.validate_address("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb") is True

    def test_validate_address_valid_kt1(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assert handler.validate_address("KT1PWx2mnDueood7fEmfbBDKx1D9BAnnXitn") is True

    def test_validate_address_invalid_tz4(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assert handler.validate_address("tz4VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb") is False

    def test_validate_address_invalid_short(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assert handler.validate_address("tz1abc") is False

    def test_validate_address_invalid_empty(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. drip
# ---------------------------------------------------------------------------

class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        handler = TezosHandler(NATIVE_CONFIG)
        result = await handler.drip("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb", "TXTZ", "1")
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "pytezos" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_rpc(self):
        handler = TezosHandler(TBD_CONFIG)
        result = await handler.drip("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb", "TXTZ", "1")
        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 3. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        monkeypatch.delenv("FAUCET_TEZOS_ADDRESS", raising=False)
        handler = TezosHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    async def test_get_faucet_balance_with_address(self, monkeypatch):
        monkeypatch.setenv("FAUCET_TEZOS_ADDRESS", "tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb")
        # Tezos RPC returns balance as a quoted string in mutez
        # 1000000 mutez = 1.000000 XTZ
        mock_session_cls = _mock_aiohttp_session_text('"1000000"')

        with patch("handlers.tezos.aiohttp.ClientSession", mock_session_cls):
            handler = TezosHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "1.000000" in val


# ---------------------------------------------------------------------------
# 4. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_contains_txtz(self):
        handler = TezosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TXTZ" in assets

    def test_supported_assets_all_tezos_family(self):
        from core.registry import load_registry
        handler = TezosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert registry[asset_id].get("family") == "tezos"
