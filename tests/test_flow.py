"""Unit tests for handlers/flow.py (FlowHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "flow",
    "blockchain": "Flow",
    "network": "testnet",
    "rpc_url": "access.devnet.nodes.onflow.org:9000",
    "explorer": "https://testnet.flowscan.org/transaction/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 8,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assert handler.validate_address("e467b9dd11fa00df") is True

    def test_valid_with_prefix(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assert handler.validate_address("0xe467b9dd11fa00df") is True

    def test_invalid_short(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assert handler.validate_address("short") is False

    def test_invalid_non_hex(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assert handler.validate_address("xyz") is False

    def test_invalid_empty(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        result = await handler.drip("e467b9dd11fa00df", "TFLOW", "1")
        assert result.success is False
        assert "Flow SDK" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_balance_not_implemented(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "balance check not yet implemented" in balance["Flow"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.flow import FlowHandler

        handler = FlowHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TFLOW" in assets
