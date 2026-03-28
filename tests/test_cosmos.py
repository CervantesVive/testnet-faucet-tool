"""Unit tests for handlers/cosmos.py (CosmosHandler)."""

import os
import pytest
from unittest.mock import MagicMock, patch

import bech32

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "cosmos",
    "blockchain": "Cosmos Hub",
    "network": "theta-testnet-001",
    "rpc_url": "https://rpc.sentry-01.theta-testnet.polypore.xyz",
    "explorer": "https://explorer.theta-testnet.polypore.xyz/transactions/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 6,
    "denom": "uatom",
    "bech32_prefix": "cosmos",
}

TOKEN_CONFIG = {
    "family": "cosmos",
    "blockchain": "Provenance",
    "network": "pio-testnet-1",
    "rpc_url": "https://rpc.test.provenance.io",
    "explorer": "https://explorer.test.provenance.io/txs/{tx_hash}",
    "native_asset": False,
    "drip_amount": "10",
    "decimals": 9,
    "denom": "nhash",
    "bech32_prefix": "tp",
}

TBD_TOKEN_CONFIG = {**TOKEN_CONFIG, "denom": "TBD"}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

TEST_MNEMONIC = "test test test test test test test test test test test junk"
MNEMONIC_COSMOS_ADDRESS = "cosmos15yk64u7zc9g9k2yr2wmzeva5qgwxps6yxj00e7"  # verified

TEST_PRIVATE_KEY_HEX = "34cdcc15d053a4afdee40419666766cbde7b7a3ce5ffdb4bbf78a50658347c8f"
TEST_PRIVATE_KEY_ADDRESS = "cosmos1pa2fxrul3em3tk2mkpxl6m52wclsz8vjpsm2hd"  # verified

VALID_COSMOS_ADDRESS = "cosmos15yk64u7zc9g9k2yr2wmzeva5qgwxps6yxj00e7"

# Generate a valid bech32 address with "tp" prefix
_tp_data = bech32.convertbits(b"test-address-bytes-123", 8, 5)
VALID_TP_ADDRESS = bech32.bech32_encode("tp", _tp_data)


# ---------------------------------------------------------------------------
# Helper: build LedgerClient mock (synchronous)
# ---------------------------------------------------------------------------

def _make_cosmos_client_mock(*, tx_hash="ABCD1234DEADBEEF", send_error=None, balance=1_000_000):
    """Build a MagicMock LedgerClient for testing."""
    mock_submitted = MagicMock()
    mock_submitted.tx_hash = tx_hash
    mock_submitted.wait_to_complete.return_value = mock_submitted

    mock_client = MagicMock()
    if send_error:
        mock_client.send_tokens.side_effect = send_error
    else:
        mock_client.send_tokens.return_value = mock_submitted
    mock_client.query_bank_balance.return_value = balance

    return mock_client


def _make_cosmos_wallet_mock(address=MNEMONIC_COSMOS_ADDRESS):
    mock_wallet = MagicMock()
    mock_wallet.address.return_value = address
    return mock_wallet


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_validate_address_valid_cosmos(self):
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_COSMOS_ADDRESS) is True

    def test_validate_address_wrong_prefix(self):
        """osmo1... address should fail when bech32_prefix is 'cosmos'."""
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(NATIVE_CONFIG)
        # Valid bech32 but wrong prefix
        _osmo_data = bech32.convertbits(b"some-address-bytes", 8, 5)
        osmo_address = bech32.bech32_encode("osmo", _osmo_data)
        assert handler.validate_address(osmo_address) is False

    def test_validate_address_invalid_string(self):
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(NATIVE_CONFIG)
        for addr in ["0xinvalid", "not-bech32"]:
            assert handler.validate_address(addr) is False, f"Expected False for {addr!r}"

    def test_validate_address_empty(self):
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_validate_address_valid_tp(self):
        """Address with 'tp' prefix should be valid for TOKEN_CONFIG (bech32_prefix='tp')."""
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(TOKEN_CONFIG)
        assert handler.validate_address(VALID_TP_ADDRESS) is True


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_returns_14(self):
        from handlers.cosmos import CosmosHandler
        handler = CosmosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 14, f"Expected 14 Cosmos assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_cosmos_family(self):
        from handlers.cosmos import CosmosHandler
        from core.registry import load_registry
        handler = CosmosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "cosmos", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'cosmos'"
            )


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_MNEMONIC": TEST_MNEMONIC}, clear=False)
    async def test_drip_native_success(self):
        from handlers.cosmos import CosmosHandler

        mock_client = _make_cosmos_client_mock()
        mock_wallet = _make_cosmos_wallet_mock()

        with patch("handlers.cosmos.LedgerClient", return_value=mock_client), \
             patch("handlers.cosmos.LocalWallet") as mock_lw_cls:
            mock_lw_cls.from_mnemonic.return_value = mock_wallet
            handler = CosmosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_COSMOS_ADDRESS, "TATOM", "1")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.explorer_url is not None
        assert result.tx_hash in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_MNEMONIC": TEST_MNEMONIC}, clear=False)
    async def test_drip_native_failure(self):
        from handlers.cosmos import CosmosHandler

        mock_client = _make_cosmos_client_mock(send_error=Exception("RPC timeout"))
        mock_wallet = _make_cosmos_wallet_mock()

        with patch("handlers.cosmos.LedgerClient", return_value=mock_client), \
             patch("handlers.cosmos.LocalWallet") as mock_lw_cls:
            mock_lw_cls.from_mnemonic.return_value = mock_wallet
            handler = CosmosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_COSMOS_ADDRESS, "TATOM", "1")

        assert result.success is False
        assert result.error is not None
        assert "RPC timeout" in result.error


# ---------------------------------------------------------------------------
# 4. drip token
# ---------------------------------------------------------------------------

class TestDripToken:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_denom(self):
        """Token with denom='TBD' should fail immediately without a network call."""
        from handlers.cosmos import CosmosHandler

        handler = CosmosHandler(TBD_TOKEN_CONFIG)
        result = await handler.drip(VALID_TP_ADDRESS, "THASH", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_MNEMONIC": TEST_MNEMONIC}, clear=False)
    async def test_drip_token_success(self):
        """Non-TBD token denom should succeed with a mocked LedgerClient."""
        from handlers.cosmos import CosmosHandler

        mock_client = _make_cosmos_client_mock()
        mock_wallet = _make_cosmos_wallet_mock(address="tp1qypqxpq9qcrsszg2pvxq6rs0zqg3yyc5xhp2hfa")

        with patch("handlers.cosmos.LedgerClient", return_value=mock_client), \
             patch("handlers.cosmos.LocalWallet") as mock_lw_cls:
            mock_lw_cls.from_mnemonic.return_value = mock_wallet
            handler = CosmosHandler(TOKEN_CONFIG)
            result = await handler.drip(VALID_TP_ADDRESS, "THASH", "10")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.error is None


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_MNEMONIC": TEST_MNEMONIC}, clear=False)
    async def test_get_faucet_balance_native(self):
        from handlers.cosmos import CosmosHandler

        mock_client = _make_cosmos_client_mock(balance=1_000_000)
        mock_wallet = _make_cosmos_wallet_mock()

        with patch("handlers.cosmos.LedgerClient", return_value=mock_client), \
             patch("handlers.cosmos.LocalWallet") as mock_lw_cls:
            mock_lw_cls.from_mnemonic.return_value = mock_wallet
            handler = CosmosHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        # The balance value should be a string
        for val in balance.values():
            assert isinstance(val, str), f"Expected string balance, got {type(val)}"
        # Should include the atom balance (1_000_000 uatom = 1.000000 ATOM)
        all_values = " ".join(balance.values())
        assert "1.000000" in all_values or "1000000" in all_values or "1.0" in all_values

    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """With no wallet configured, get_faucet_balance should return graceful message."""
        from handlers.cosmos import CosmosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = CosmosHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert (
            "no wallet" in all_values
            or "not configured" in all_values
            or "error" in all_values
            or "configure" in all_values
        ), f"Expected 'no wallet' indicator but got: {balance}"


# ---------------------------------------------------------------------------
# 6. Wallet derivation
# ---------------------------------------------------------------------------

class TestWalletDerivation:
    def test_wallet_from_mnemonic(self, monkeypatch):
        from handlers.cosmos import CosmosHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.setenv("FAUCET_MNEMONIC", TEST_MNEMONIC)

        handler = CosmosHandler(NATIVE_CONFIG)
        wallet = handler._get_wallet()

        assert wallet is not None
        assert str(wallet.address()) == MNEMONIC_COSMOS_ADDRESS

    def test_wallet_from_private_key(self, monkeypatch):
        from handlers.cosmos import CosmosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.setenv("FAUCET_PRIVATE_KEY", TEST_PRIVATE_KEY_HEX)

        handler = CosmosHandler(NATIVE_CONFIG)
        wallet = handler._get_wallet()

        assert wallet is not None
        assert str(wallet.address()) == TEST_PRIVATE_KEY_ADDRESS

    def test_wallet_missing_env_vars(self, monkeypatch):
        from handlers.cosmos import CosmosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = CosmosHandler(NATIVE_CONFIG)
        with pytest.raises(RuntimeError):
            handler._get_wallet()

    def test_private_key_with_0x_prefix(self, monkeypatch):
        """Handler should strip 0x prefix from private key."""
        from handlers.cosmos import CosmosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.setenv("FAUCET_PRIVATE_KEY", "0x" + TEST_PRIVATE_KEY_HEX)

        handler = CosmosHandler(NATIVE_CONFIG)
        wallet = handler._get_wallet()

        assert wallet is not None
        assert str(wallet.address()) == TEST_PRIVATE_KEY_ADDRESS
