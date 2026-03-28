"""Unit tests for handlers/bittensor.py (BittensorHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "bittensor",
    "blockchain": "Bittensor",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "0.1",
    "decimals": 9,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        assert handler.validate_address(
            "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        ) is True

    def test_invalid_1abc(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        assert handler.validate_address("1abcdefg") is False

    def test_invalid_empty(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_tbd(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        result = await handler.drip(
            "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", "TTAO", "0.1"
        )
        assert result.success is False
        assert "TBD" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_tbd(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "rpc_url not yet configured (TBD)" in balance["Bittensor"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.bittensor import BittensorHandler

        handler = BittensorHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TTAO" in assets
