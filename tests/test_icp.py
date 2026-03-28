"""Unit tests for handlers/icp.py (IcpHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "icp",
    "blockchain": "Internet Computer",
    "network": "mainnet",
    "rpc_url": "https://ic0.app",
    "explorer": "https://dashboard.internetcomputer.org/transaction/{tx_hash}",
    "native_asset": True,
    "drip_amount": "0.1",
    "decimals": 8,
}


class TestValidateAddress:
    def test_valid_hex(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        assert handler.validate_address("a" * 64) is True

    def test_valid_principal(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        assert handler.validate_address("rrkah-fqaaa-aaaaa-aaaaq-cai") is True

    def test_invalid_empty(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_short(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        assert handler.validate_address("x") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        result = await handler.drip("rrkah-fqaaa-aaaaa-aaaaq-cai", "TICP", "0.1")
        assert result.success is False
        assert "dfx" in result.error or "ic-py" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_balance_not_implemented(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "balance check not yet implemented" in balance["Internet Computer"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.icp import IcpHandler

        handler = IcpHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TICP" in assets
