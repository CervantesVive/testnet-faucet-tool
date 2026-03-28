"""Unit tests for handlers/xrp.py (XrpHandler)."""

import os
import pytest
from unittest.mock import MagicMock, patch

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "xrp",
    "blockchain": "XRP Ledger",
    "network": "testnet",
    "rpc_url": "https://s.altnet.rippletest.net:51234",
    "faucet_url": "https://faucet.altnet.rippletest.net/accounts",
    "explorer": "https://testnet.xrpl.org/transactions/{tx_hash}",
    "native_asset": True,
    "drip_amount": "100",
    "decimals": 6,
}

TBD_TOKEN_CONFIG = {
    "family": "xrp",
    "native_asset": False,
    "issuer": "TBD",
    "currency_code": "RLUSD",
    "rpc_url": "https://s.altnet.rippletest.net:51234",
    "explorer": "https://testnet.xrpl.org/transactions/{tx_hash}",
    "drip_amount": "10",
    "decimals": 6,
}

TOKEN_CONFIG = {
    "family": "xrp",
    "native_asset": False,
    "issuer": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
    "currency_code": "USD",
    "rpc_url": "https://s.altnet.rippletest.net:51234",
    "explorer": "https://testnet.xrpl.org/transactions/{tx_hash}",
    "drip_amount": "10",
    "decimals": 6,
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Well-known XRP genesis account (always valid classic address)
VALID_XRP_ADDRESS = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
# A different address used as the mock faucet wallet (must differ from destination)
FAUCET_XRP_ADDRESS = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
INVALID_XRP_ADDRESS = "not-a-valid-xrp-address"

TEST_TX_HASH = "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xrp_mock(*, tx_hash=TEST_TX_HASH, submit_error=None):
    """Build mock objects for XRP client/wallet/submit_and_wait."""
    mock_response = MagicMock()
    mock_response.result = {"hash": tx_hash}

    mock_client = MagicMock()

    mock_wallet = MagicMock()
    mock_wallet.classic_address = FAUCET_XRP_ADDRESS

    return mock_client, mock_wallet, mock_response, submit_error


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_classic_address(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_XRP_ADDRESS) is True

    def test_invalid_address_returns_false(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_XRP_ADDRESS) is False

    def test_empty_address_returns_false(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_ethereum_address_returns_false(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assert handler.validate_address("0xabcdef1234567890abcdef1234567890abcdef12") is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_returns_2(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 2, f"Expected 2 XRP assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_xrp_family(self):
        from handlers.xrp import XrpHandler
        from core.registry import load_registry
        handler = XrpHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "xrp", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'xrp'"
            )

    def test_supported_assets_contains_txrp(self):
        from handlers.xrp import XrpHandler
        handler = XrpHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TXRP" in assets


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "sEdTM1uX8pu2do5XvTnutH6HsouMaM2"}, clear=False)
    async def test_drip_native_success(self):
        from handlers.xrp import XrpHandler

        mock_client, mock_wallet, mock_response, _ = _make_xrp_mock()

        with patch("handlers.xrp.JsonRpcClient", return_value=mock_client), \
             patch("handlers.xrp.submit_and_wait", return_value=mock_response), \
             patch("handlers.xrp.Wallet") as mock_wallet_cls:
            mock_wallet_cls.from_seed.return_value = mock_wallet
            handler = XrpHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_XRP_ADDRESS, "TXRP", "100")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == TEST_TX_HASH
        assert result.explorer_url is not None
        assert TEST_TX_HASH in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "sEdTM1uX8pu2do5XvTnutH6HsouMaM2"}, clear=False)
    async def test_drip_native_failure(self):
        from handlers.xrp import XrpHandler

        mock_client, mock_wallet, _, _ = _make_xrp_mock()

        with patch("handlers.xrp.JsonRpcClient", return_value=mock_client), \
             patch("handlers.xrp.submit_and_wait", side_effect=Exception("network error")), \
             patch("handlers.xrp.Wallet") as mock_wallet_cls:
            mock_wallet_cls.from_seed.return_value = mock_wallet
            handler = XrpHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_XRP_ADDRESS, "TXRP", "100")

        assert result.success is False
        assert result.error is not None
        assert "network error" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "sEdTM1uX8pu2do5XvTnutH6HsouMaM2"}, clear=False)
    async def test_drip_native_hash_from_tx_json(self):
        """Hash should also be found in result.result['tx_json']['hash'] fallback."""
        from handlers.xrp import XrpHandler

        mock_response = MagicMock()
        # No top-level 'hash'; only in tx_json
        mock_response.result = {"tx_json": {"hash": TEST_TX_HASH}}
        mock_client, mock_wallet, _, _ = _make_xrp_mock()

        with patch("handlers.xrp.JsonRpcClient", return_value=mock_client), \
             patch("handlers.xrp.submit_and_wait", return_value=mock_response), \
             patch("handlers.xrp.Wallet") as mock_wallet_cls:
            mock_wallet_cls.from_seed.return_value = mock_wallet
            handler = XrpHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_XRP_ADDRESS, "TXRP", "100")

        assert result.success is True
        assert result.tx_hash == TEST_TX_HASH


# ---------------------------------------------------------------------------
# 4. drip token TBD
# ---------------------------------------------------------------------------

class TestDripToken:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_issuer(self):
        """Token with issuer='TBD' should fail immediately without a network call."""
        from handlers.xrp import XrpHandler

        handler = XrpHandler(TBD_TOKEN_CONFIG)
        result = await handler.drip(VALID_XRP_ADDRESS, "TXRP:RLUSD", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "sEdTM1uX8pu2do5XvTnutH6HsouMaM2"}, clear=False)
    async def test_drip_token_success(self):
        """Non-TBD token should succeed with mocked client."""
        from handlers.xrp import XrpHandler

        mock_client, mock_wallet, mock_response, _ = _make_xrp_mock()

        with patch("handlers.xrp.JsonRpcClient", return_value=mock_client), \
             patch("handlers.xrp.submit_and_wait", return_value=mock_response), \
             patch("handlers.xrp.Wallet") as mock_wallet_cls:
            mock_wallet_cls.from_seed.return_value = mock_wallet
            handler = XrpHandler(TOKEN_CONFIG)
            result = await handler.drip(VALID_XRP_ADDRESS, "TXRP:RLUSD", "10")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == TEST_TX_HASH
        assert result.error is None


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        from handlers.xrp import XrpHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = XrpHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert "no wallet" in all_values or "not configured" in all_values or "configure" in all_values, (
            f"Expected 'no wallet' indicator but got: {balance}"
        )

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "sEdTM1uX8pu2do5XvTnutH6HsouMaM2"}, clear=False)
    async def test_get_faucet_balance_with_wallet(self):
        from handlers.xrp import XrpHandler

        mock_client = MagicMock()
        mock_wallet = MagicMock()
        mock_wallet.classic_address = FAUCET_XRP_ADDRESS
        drops = 100_000_000  # 100 XRP in drops

        with patch("handlers.xrp.JsonRpcClient", return_value=mock_client), \
             patch("handlers.xrp.get_balance", return_value=drops), \
             patch("handlers.xrp.Wallet") as mock_wallet_cls:
            mock_wallet_cls.from_seed.return_value = mock_wallet
            handler = XrpHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        for val in balance.values():
            assert isinstance(val, str), f"Expected string balance, got {type(val)}"
        all_values = " ".join(balance.values())
        # 100_000_000 drops / 1_000_000 = 100.000000 XRP
        assert "100" in all_values
