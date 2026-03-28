"""Unit tests for handlers/substrate.py (SubstrateHandler)."""

import pytest
from unittest.mock import MagicMock

from handlers.substrate import SubstrateHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "substrate",
    "blockchain": "Polkadot",
    "network": "westend",
    "rpc_url": "wss://westend-rpc.polkadot.io",
    "explorer": "https://westend.subscan.io/extrinsic/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 12,
}

# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_validate_address_valid_5_prefix(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        # Standard SS58 address starting with 5, 48 chars total
        assert handler.validate_address("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY") is True

    def test_validate_address_valid_2_prefix(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        # Polymesh-style address starting with 2, 48 chars total
        addr = "2" + "a" * 47
        assert handler.validate_address(addr) is True

    def test_validate_address_invalid_1_prefix(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        assert handler.validate_address("1abc" + "a" * 44) is False

    def test_validate_address_invalid_short(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        assert handler.validate_address("5Grw") is False

    def test_validate_address_invalid_empty(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_validate_address_invalid_bad_chars(self):
        """SS58 excludes 0, O, I, l."""
        handler = SubstrateHandler(NATIVE_CONFIG)
        # Address with 'O' (uppercase O) which is excluded from base58
        addr = "5O" + "a" * 46
        assert handler.validate_address(addr) is False


# ---------------------------------------------------------------------------
# 2. drip
# ---------------------------------------------------------------------------

class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_no_sdk(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        result = await handler.drip(
            "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", "TDOT", "1"
        )
        assert isinstance(result, DripResult)
        assert result.success is False
        assert "substrate-interface" in result.error


# ---------------------------------------------------------------------------
# 3. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_stub(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "balance check requires substrate SDK" in val


# ---------------------------------------------------------------------------
# 4. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_contains_tdot(self):
        handler = SubstrateHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TDOT" in assets

    def test_supported_assets_all_substrate_family(self):
        from core.registry import load_registry
        handler = SubstrateHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert registry[asset_id].get("family") == "substrate"
