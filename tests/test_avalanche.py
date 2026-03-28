"""Unit tests for handlers/avalanche.py (AvalanchePHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "avalanche_p",
    "blockchain": "Avalanche P-Chain",
    "network": "fuji",
    "rpc_url": "https://api.avax-test.network",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "0.1",
    "decimals": 9,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        assert handler.validate_address("P-fuji1wycm8t4alm0relpjg0mxqjqn0szmkdpjhqvxy5") is True

    def test_invalid_x_prefix(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        assert handler.validate_address("X-fuji1wycm8t4alm0relpjg0mxqjqn0szmkdpjhqvxy5") is False

    def test_invalid_empty(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_no_prefix(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        assert handler.validate_address("fuji1wycm8t4alm0relpjg0mxqjqn0szmkdpjhqvxy5") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        result = await handler.drip("P-fuji1wycm8t4alm0relpjg0mxqjqn0szmkdpjhqvxy5", "TAVAXP", "0.1")
        assert result.success is False
        assert "avalanche SDK" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_balance_not_implemented(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "balance check not yet implemented" in balance["Avalanche P-Chain"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.avalanche import AvalanchePHandler

        handler = AvalanchePHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TAVAXP" in assets
