"""Unit tests for handlers/solana.py (SolanaHandler)."""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from solders.hash import Hash
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "solana",
    "blockchain": "Solana",
    "network": "devnet",
    "rpc_url": "https://api.devnet.solana.com",
    "explorer": "https://explorer.solana.com/tx/{tx_hash}?cluster=devnet",
    "native_asset": True,
    "drip_amount": "0.5",
    "decimals": 9,
    "funding_method": "request_airdrop",
}

SPL_CONFIG = {
    "family": "solana",
    "blockchain": "Solana",
    "network": "devnet",
    "rpc_url": "https://api.devnet.solana.com",
    "explorer": "https://explorer.solana.com/tx/{tx_hash}?cluster=devnet",
    "native_asset": False,
    "mint_address": "So11111111111111111111111111111111111111112",  # Wrapped SOL mint (not TBD)
    "drip_amount": "0.1",
    "decimals": 9,
}

TBD_SPL_CONFIG = {
    **SPL_CONFIG,
    "mint_address": "TBD",
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

VALID_ADDRESS = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
INVALID_ADDRESSES = ["0xinvalid", "not-a-pubkey"]

TEST_MNEMONIC = "test test test test test test test test test test test junk"
MNEMONIC_PUBKEY = "G9r1RYmVnXptzCA2an46rNnHsCAQLvjyM6vR2mo3LpG1"

# Deterministic test keypair (from sha256("test-faucet-keypair") seed)
TEST_KEYPAIR_BASE58 = "5T6XxLda4A8PAGA6ZWuwRVyb21NEUpNBNEShrfbaiAH2QK4qcwvD9wtiaGJnknj3d62hmF2pGMECxdm2xZfqHjeL"
TEST_KEYPAIR_PUBKEY = "GU6b53zssNrytCiYUsnbXccfPZVnE9soGhjNNFkTN58p"


# ---------------------------------------------------------------------------
# Helper: build AsyncClient mock
# ---------------------------------------------------------------------------

def _make_async_client_mock(**method_overrides):
    """Return an AsyncClient mock suitable for use as an async context manager."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Sensible defaults
    mock_client.request_airdrop = AsyncMock(
        return_value=MagicMock(value=Signature.default())
    )
    mock_client.get_balance = AsyncMock(
        return_value=MagicMock(value=500_000_000)  # 0.5 SOL in lamports
    )
    mock_client.get_latest_blockhash = AsyncMock(
        return_value=MagicMock(value=MagicMock(blockhash=Hash.default()))
    )
    mock_client.send_transaction = AsyncMock(
        return_value=MagicMock(value=Signature.default())
    )
    mock_client.get_token_account_balance = AsyncMock(
        return_value=MagicMock(value=MagicMock(ui_amount_string="10.0"))
    )

    for method, value in method_overrides.items():
        setattr(mock_client, method, value)

    return mock_client


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_validate_address_valid(self):
        from handlers.solana import SolanaHandler
        handler = SolanaHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_ADDRESS) is True

    def test_validate_address_invalid(self):
        from handlers.solana import SolanaHandler
        handler = SolanaHandler(NATIVE_CONFIG)
        for addr in INVALID_ADDRESSES:
            assert handler.validate_address(addr) is False, f"Expected False for {addr!r}"

    def test_validate_address_empty(self):
        from handlers.solana import SolanaHandler
        handler = SolanaHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_returns_12(self):
        from handlers.solana import SolanaHandler
        handler = SolanaHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()

        assert len(assets) == 12, f"Expected 12 Solana assets, got {len(assets)}: {assets}"
        # All returned asset IDs must come from the registry with family='solana'
        from core.registry import load_registry
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "solana", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'solana'"
            )


# ---------------------------------------------------------------------------
# 3. drip native (requestAirdrop)
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    async def test_drip_native_success(self):
        from handlers.solana import SolanaHandler

        mock_client = _make_async_client_mock()

        with patch("handlers.solana.AsyncClient", return_value=mock_client):
            handler = SolanaHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_ADDRESS, "TSOL", "0.5")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.explorer_url is not None
        assert result.tx_hash in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    async def test_drip_native_failure(self):
        from handlers.solana import SolanaHandler

        mock_client = _make_async_client_mock(
            request_airdrop=AsyncMock(side_effect=Exception("RPC error"))
        )

        with patch("handlers.solana.AsyncClient", return_value=mock_client):
            handler = SolanaHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_ADDRESS, "TSOL", "0.5")

        assert result.success is False
        assert result.error is not None
        assert "RPC error" in result.error


# ---------------------------------------------------------------------------
# 4. drip SPL token
# ---------------------------------------------------------------------------

class TestDripSPL:
    @pytest.mark.asyncio
    async def test_drip_spl_tbd_mint(self):
        """SPL with mint_address='TBD' should fail immediately without an RPC call."""
        from handlers.solana import SolanaHandler

        handler = SolanaHandler(TBD_SPL_CONFIG)
        result = await handler.drip(VALID_ADDRESS, "TSOL-TOKEN", "0.1")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_SOLANA_KEYPAIR": TEST_KEYPAIR_BASE58}, clear=False)
    async def test_drip_spl_success(self):
        """SPL drip with a real (non-TBD) mint and a configured keypair."""
        from handlers.solana import SolanaHandler

        mock_client = _make_async_client_mock()

        with patch("handlers.solana.AsyncClient", return_value=mock_client):
            handler = SolanaHandler(SPL_CONFIG)
            result = await handler.drip(VALID_ADDRESS, "WSOL", "0.1")

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
        from handlers.solana import SolanaHandler

        mock_client = _make_async_client_mock(
            get_balance=AsyncMock(return_value=MagicMock(value=500_000_000))
        )

        with patch("handlers.solana.AsyncClient", return_value=mock_client):
            handler = SolanaHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        # SOL balance should be present and be a string
        sol_key = next((k for k in balance if "SOL" in k.upper()), None)
        assert sol_key is not None, f"Expected a SOL key in balance dict, got: {balance}"
        assert isinstance(balance[sol_key], str)
        # 500_000_000 lamports = 0.5 SOL
        assert "0.5" in balance[sol_key] or "500" in balance[sol_key]

    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """With no wallet configured, get_faucet_balance should not raise."""
        from handlers.solana import SolanaHandler

        monkeypatch.delenv("FAUCET_SOLANA_KEYPAIR", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = SolanaHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        # Should contain some indication that no wallet is configured
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert (
            "no wallet" in all_values
            or "not configured" in all_values
            or "error" in all_values
            or "configure" in all_values
        ), f"Expected 'no wallet' indicator but got: {balance}"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_MNEMONIC": TEST_MNEMONIC}, clear=False)
    async def test_get_faucet_balance_spl(self):
        """Balance dict should include both SOL and SPL token entries."""
        from handlers.solana import SolanaHandler

        mock_client = _make_async_client_mock(
            get_balance=AsyncMock(return_value=MagicMock(value=200_000_000)),
            get_token_account_balance=AsyncMock(
                return_value=MagicMock(value=MagicMock(ui_amount_string="25.0"))
            ),
        )

        with patch("handlers.solana.AsyncClient", return_value=mock_client):
            handler = SolanaHandler(SPL_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        for key, val in balance.items():
            assert isinstance(val, str), f"Expected string balance for {key}, got {type(val)}"


# ---------------------------------------------------------------------------
# 6. Keypair derivation
# ---------------------------------------------------------------------------

class TestKeypairDerivation:
    def test_keypair_from_mnemonic(self, monkeypatch):
        from handlers.solana import SolanaHandler

        monkeypatch.delenv("FAUCET_SOLANA_KEYPAIR", raising=False)
        monkeypatch.setenv("FAUCET_MNEMONIC", TEST_MNEMONIC)

        handler = SolanaHandler(NATIVE_CONFIG)
        keypair = handler._get_keypair()

        assert keypair is not None
        assert str(keypair.pubkey()) == MNEMONIC_PUBKEY

    def test_keypair_from_base58_env(self, monkeypatch):
        from handlers.solana import SolanaHandler

        monkeypatch.setenv("FAUCET_SOLANA_KEYPAIR", TEST_KEYPAIR_BASE58)

        handler = SolanaHandler(NATIVE_CONFIG)
        keypair = handler._get_keypair()

        assert keypair is not None
        assert str(keypair.pubkey()) == TEST_KEYPAIR_PUBKEY
