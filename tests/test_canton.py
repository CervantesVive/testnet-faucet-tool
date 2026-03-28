"""Unit tests for handlers/canton.py (CantonHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "canton",
    "blockchain": "Canton",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 10,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        assert handler.validate_address("some-canton-address") is True

    def test_invalid_empty(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_whitespace(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        assert handler.validate_address("   ") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_tbd(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        result = await handler.drip("some-canton-address", "TCANTON", "1")
        assert result.success is False
        assert "TBD" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_tbd(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "rpc_url not yet configured (TBD)" in balance["Canton"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.canton import CantonHandler

        handler = CantonHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TCANTON" in assets
