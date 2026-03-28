"""Unit tests for handlers/stellar.py (StellarHandler)."""

import os
import pytest
from unittest.mock import MagicMock, patch

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "stellar",
    "blockchain": "Stellar",
    "network": "testnet",
    "rpc_url": "https://horizon-testnet.stellar.org",
    "faucet_url": "https://friendbot.stellar.org",
    "explorer": "https://stellar.expert/explorer/testnet/tx/{tx_hash}",
    "native_asset": True,
    "drip_amount": "100",
    "decimals": 7,
}

TBD_TOKEN_CONFIG = {
    "family": "stellar",
    "native_asset": False,
    "asset_code": "USDC",
    "issuer": "TBD",
    "rpc_url": "https://horizon-testnet.stellar.org",
    "explorer": "https://stellar.expert/explorer/testnet/tx/{tx_hash}",
    "drip_amount": "10",
    "decimals": 7,
}

TOKEN_CONFIG = {
    "family": "stellar",
    "native_asset": False,
    "asset_code": "USDC",
    "issuer": "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5",
    "rpc_url": "https://horizon-testnet.stellar.org",
    "explorer": "https://stellar.expert/explorer/testnet/tx/{tx_hash}",
    "drip_amount": "10",
    "decimals": 7,
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Valid Stellar public key (G...) — used as faucet wallet address
FAUCET_STELLAR_ADDRESS = "GD6GKRABNDVYDETEZJQEPS7IBQMERCN44R5RCI4LJNX6BMYQM2KPTURZ"

INVALID_STELLAR_ADDRESS = "not-a-valid-stellar-address"

TEST_TX_HASH = "stellar_hash_abc123def456"
TEST_PRIVATE_KEY = "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stellar_mock(*, tx_hash=TEST_TX_HASH, submit_error=None):
    """Build mock objects for Stellar Server and TransactionBuilder."""
    mock_account = MagicMock()
    mock_account.sequence = 1

    mock_server = MagicMock()
    mock_server.load_account = MagicMock(return_value=mock_account)
    mock_server.fetch_base_fee = MagicMock(return_value=100)
    if submit_error:
        mock_server.submit_transaction = MagicMock(side_effect=submit_error)
    else:
        mock_server.submit_transaction = MagicMock(return_value={"hash": tx_hash})

    mock_transaction = MagicMock()
    mock_transaction.sign = MagicMock()

    mock_tx_builder = MagicMock()
    mock_tx_builder.append_payment_op = MagicMock(return_value=mock_tx_builder)
    mock_tx_builder.build = MagicMock(return_value=mock_transaction)

    return mock_server, mock_tx_builder, mock_transaction


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_stellar_address(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        # Use a well-known valid Stellar testnet address format
        valid_addr = "GAHJJJKMOKYE4RVPZEWZTKH5FVI4PA3VL7GK2LFNUBSGBVS4ZM27PGIP"
        # We rely on the real Keypair validation
        from stellar_sdk import Keypair
        # Generate a fresh keypair for a guaranteed-valid address
        kp = Keypair.random()
        assert handler.validate_address(kp.public_key) is True

    def test_invalid_address_returns_false(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_STELLAR_ADDRESS) is False

    def test_empty_address_returns_false(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_xrp_address_returns_false(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        assert handler.validate_address("rN7n3473SaZBCG4dFL83w7PB9zBQMDQV3m") is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_returns_4(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 4, f"Expected 4 Stellar assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_stellar_family(self):
        from handlers.stellar import StellarHandler
        from core.registry import load_registry
        handler = StellarHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "stellar", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'stellar'"
            )

    def test_supported_assets_contains_txlm(self):
        from handlers.stellar import StellarHandler
        handler = StellarHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TXLM" in assets


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"}, clear=False)
    async def test_drip_native_success(self):
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        mock_server, mock_tx_builder, mock_transaction = _make_stellar_mock()
        faucet_kp = Keypair.random()

        with patch("handlers.stellar.Server", return_value=mock_server), \
             patch("handlers.stellar.TransactionBuilder", return_value=mock_tx_builder), \
             patch("handlers.stellar.Keypair") as mock_keypair_cls:
            mock_keypair_cls.from_secret.return_value = faucet_kp
            handler = StellarHandler(NATIVE_CONFIG)
            result = await handler.drip(Keypair.random().public_key, "TXLM", "100")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == TEST_TX_HASH
        assert result.explorer_url is not None
        assert TEST_TX_HASH in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"}, clear=False)
    async def test_drip_native_failure(self):
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        mock_server, mock_tx_builder, _ = _make_stellar_mock(submit_error=Exception("horizon error"))
        faucet_kp = Keypair.random()

        with patch("handlers.stellar.Server", return_value=mock_server), \
             patch("handlers.stellar.TransactionBuilder", return_value=mock_tx_builder), \
             patch("handlers.stellar.Keypair") as mock_keypair_cls:
            mock_keypair_cls.from_secret.return_value = faucet_kp
            handler = StellarHandler(NATIVE_CONFIG)
            result = await handler.drip(Keypair.random().public_key, "TXLM", "100")

        assert result.success is False
        assert result.error is not None
        assert "horizon error" in result.error


# ---------------------------------------------------------------------------
# 4. drip token TBD
# ---------------------------------------------------------------------------

class TestDripToken:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_issuer(self):
        """Token with issuer='TBD' should fail immediately without a network call."""
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        handler = StellarHandler(TBD_TOKEN_CONFIG)
        result = await handler.drip(Keypair.random().public_key, "TXLM:USDC", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"}, clear=False)
    async def test_drip_token_success(self):
        """Non-TBD token should succeed with mocked Server."""
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        mock_server, mock_tx_builder, mock_transaction = _make_stellar_mock()
        faucet_kp = Keypair.random()

        with patch("handlers.stellar.Server", return_value=mock_server), \
             patch("handlers.stellar.TransactionBuilder", return_value=mock_tx_builder), \
             patch("handlers.stellar.Keypair") as mock_keypair_cls:
            mock_keypair_cls.from_secret.return_value = faucet_kp
            handler = StellarHandler(TOKEN_CONFIG)
            result = await handler.drip(Keypair.random().public_key, "TXLM:USDC", "10")

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
        from handlers.stellar import StellarHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = StellarHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert (
            "no wallet" in all_values
            or "not configured" in all_values
            or "configure" in all_values
        ), f"Expected 'no wallet' indicator but got: {balance}"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"}, clear=False)
    async def test_get_faucet_balance_with_wallet(self):
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        faucet_kp = Keypair.random()

        mock_server = MagicMock()
        mock_account_data = {
            "balances": [
                {"asset_type": "native", "balance": "9876.5432100"},
                {"asset_type": "credit_alphanum4", "asset_code": "USDC", "balance": "100.0000000"},
            ]
        }
        mock_server.accounts.return_value.account_id.return_value.call.return_value = mock_account_data

        with patch("handlers.stellar.Server", return_value=mock_server), \
             patch("handlers.stellar.Keypair") as mock_keypair_cls:
            mock_keypair_cls.from_secret.return_value = faucet_kp
            handler = StellarHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        for val in balance.values():
            assert isinstance(val, str), f"Expected string balance, got {type(val)}"
        all_values = " ".join(balance.values())
        assert "9876" in all_values

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": "SCMWQBXKADMJVPRFNCHUKJHOXWKJKFZZSMBPACVHZKJZXQPQ7ZQNQPQD"}, clear=False)
    async def test_get_faucet_balance_no_native_balance(self):
        """If no native balance entry, should return '0'."""
        from handlers.stellar import StellarHandler
        from stellar_sdk import Keypair

        faucet_kp = Keypair.random()

        mock_server = MagicMock()
        mock_account_data = {
            "balances": [
                {"asset_type": "credit_alphanum4", "asset_code": "USDC", "balance": "50.0"},
            ]
        }
        mock_server.accounts.return_value.account_id.return_value.call.return_value = mock_account_data

        with patch("handlers.stellar.Server", return_value=mock_server), \
             patch("handlers.stellar.Keypair") as mock_keypair_cls:
            mock_keypair_cls.from_secret.return_value = faucet_kp
            handler = StellarHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        all_values = " ".join(balance.values())
        assert "0" in all_values
