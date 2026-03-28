"""Unit tests for handlers/cardano.py (CardanoHandler)."""

import pytest
from handlers.base import DripResult


NATIVE_CONFIG = {
    "family": "cardano",
    "blockchain": "Cardano",
    "network": "preprod",
    "rpc_url": "TBD",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "5",
    "decimals": 6,
}


class TestValidateAddress:
    def test_valid(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        assert handler.validate_address(
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3jcu5d8ps7zex2k2xt3uqxgjqnnj83ws8lhrn648jjxtwq2ytjqp"
        ) is True

    def test_invalid_addr1(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        assert handler.validate_address("addr1xyz") is False

    def test_invalid_empty(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_tbd(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        result = await handler.drip("addr_test1abc", "TADA", "5")
        assert result.success is False
        assert "TBD" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_tbd(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert "rpc_url not yet configured (TBD)" in balance["Cardano"]


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.cardano import CardanoHandler

        handler = CardanoHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TADA" in assets
