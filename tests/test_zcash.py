"""Unit tests for handlers/zcash.py (ZcashHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "zcash",
    "blockchain": "Zcash",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "0.01",
    "decimals": 8,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        assert handler.validate_address("tmBsTi7vSLp5FwMFUE4grJjTQ7tCzPgYn1A") is True

    def test_invalid_t1(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        assert handler.validate_address("t1abc") is False

    def test_invalid_empty(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_tbd(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        result = await handler.drip("tmBsTi7vSLp5FwMFUE4grJjTQ7tCzPgYn1A", "TZEC", "0.01")
        assert result.success is False
        assert "TBD" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_tbd(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "rpc_url not yet configured (TBD)" in balance["Zcash"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.zcash import ZcashHandler

        handler = ZcashHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TZEC" in assets
