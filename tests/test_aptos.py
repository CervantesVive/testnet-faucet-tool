"""Unit tests for handlers/aptos.py (AptosHandler)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "aptos",
    "blockchain": "Aptos",
    "network": "devnet",
    "faucet_url": "https://faucet.devnet.aptoslabs.com/fund",
    "rpc_url": "https://fullnode.devnet.aptoslabs.com/v1",
    "explorer": "https://explorer.aptoslabs.com/txn/{tx_hash}?network=devnet",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 8,
}

TOKEN_TBD_CONFIG = {
    "family": "aptos",
    "native_asset": False,
    "coin_type": "TBD",
}

# ---------------------------------------------------------------------------
# Test addresses
# ---------------------------------------------------------------------------

# Aptos addresses: 0x + 1-64 hex chars
VALID_APTOS_ADDRESS_FULL = "0x" + "a" * 64
VALID_APTOS_ADDRESS_SHORT = "0x1"
INVALID_APTOS_ADDRESS_NO_PREFIX = "a" * 64
INVALID_APTOS_ADDRESS_TOO_LONG = "0x" + "a" * 65
INVALID_APTOS_ADDRESS_NON_HEX = "0x" + "g" * 10


# ---------------------------------------------------------------------------
# aiohttp mock helpers
# ---------------------------------------------------------------------------

def _make_post_session_mock(json_return_value, *, raise_for_status=None):
    """Return a context-manager-compatible aiohttp.ClientSession mock for POST."""
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=json_return_value)
    if raise_for_status:
        mock_response.raise_for_status = MagicMock(side_effect=raise_for_status)
    else:
        mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


def _make_get_session_mock(json_return_value):
    """Return a context-manager-compatible aiohttp.ClientSession mock for GET."""
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=json_return_value)
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_address_full(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_APTOS_ADDRESS_FULL) is True

    def test_valid_address_short(self):
        """Aptos allows 1-64 hex chars after 0x."""
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_APTOS_ADDRESS_SHORT) is True

    def test_valid_address_mixed_case(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        addr = "0x" + "A" * 32 + "b" * 32
        assert handler.validate_address(addr) is True

    def test_invalid_address_no_prefix(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_APTOS_ADDRESS_NO_PREFIX) is False

    def test_invalid_address_too_long(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_APTOS_ADDRESS_TOO_LONG) is False

    def test_invalid_address_non_hex(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address(INVALID_APTOS_ADDRESS_NON_HEX) is False

    def test_invalid_address_empty(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_invalid_address_only_prefix(self):
        """0x alone (no hex chars) should be invalid."""
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assert handler.validate_address("0x") is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_count(self):
        from handlers.aptos import AptosHandler
        handler = AptosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 3, f"Expected 3 Aptos assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_aptos_family(self):
        from handlers.aptos import AptosHandler
        from core.registry import load_registry
        handler = AptosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry, f"{asset_id} not in registry"
            assert registry[asset_id].get("family") == "aptos", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'aptos'"
            )


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    async def test_drip_native_success_list_response(self):
        """Success path: Aptos faucet returns a list of tx hashes."""
        from handlers.aptos import AptosHandler

        faucet_response = ["txhash00001", "txhash00002"]
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session):
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == "txhash00001"
        assert result.explorer_url is not None
        assert "txhash00001" in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    async def test_drip_native_success_dict_response_txn_hash(self):
        """Success path: faucet returns dict with txn_hash field."""
        from handlers.aptos import AptosHandler

        faucet_response = {"txn_hash": "dicttxhash999"}
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session):
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        assert result.success is True
        assert result.tx_hash == "dicttxhash999"
        assert result.explorer_url is not None
        assert "dicttxhash999" in result.explorer_url

    @pytest.mark.asyncio
    async def test_drip_native_success_dict_response_hash(self):
        """Success path: faucet returns dict with hash field."""
        from handlers.aptos import AptosHandler

        faucet_response = {"hash": "hashfield111"}
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session):
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        assert result.success is True
        assert result.tx_hash == "hashfield111"

    @pytest.mark.asyncio
    async def test_drip_native_amount_conversion(self):
        """The handler should convert amount to octas (1 APT = 10^8 octas)."""
        from handlers.aptos import AptosHandler

        faucet_response = ["txhash_octas"]
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session) as mock_cls:
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        # Verify post was called with the correct octas amount (1 APT = 100_000_000 octas)
        call_kwargs = mock_session.post.call_args
        posted_payload = call_kwargs[1]["json"] if call_kwargs[1] else call_kwargs[0][1]
        assert posted_payload["amount"] == 100_000_000

    @pytest.mark.asyncio
    async def test_drip_native_failure_exception(self):
        """Failure path: POST raises an exception."""
        from handlers.aptos import AptosHandler

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(side_effect=Exception("network timeout"))

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session):
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        assert result.success is False
        assert result.error is not None
        assert "network timeout" in result.error

    @pytest.mark.asyncio
    async def test_drip_native_no_tx_hash_in_response(self):
        """If response has no recognizable tx hash fields, tx_hash is None but success is True."""
        from handlers.aptos import AptosHandler

        faucet_response = {}
        mock_session = _make_post_session_mock(faucet_response)

        with patch("handlers.aptos.aiohttp.ClientSession", return_value=mock_session):
            handler = AptosHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT", "1")

        assert result.success is True
        assert result.tx_hash is None
        assert result.explorer_url is None


# ---------------------------------------------------------------------------
# 4. drip token (TBD)
# ---------------------------------------------------------------------------

class TestDripToken:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_fails_immediately(self):
        """Token with coin_type='TBD' should fail without any network call."""
        from handlers.aptos import AptosHandler

        handler = AptosHandler(TOKEN_TBD_CONFIG)
        # No network mock — if a network call is made, the test will raise
        result = await handler.drip(VALID_APTOS_ADDRESS_FULL, "TAPT:USDT", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """With no wallet env vars, returns 'no wallet configured'."""
        from handlers.aptos import AptosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        handler = AptosHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert "no wallet" in all_values, f"Expected 'no wallet configured', got: {balance}"

    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_rpc_url(self, monkeypatch):
        """With no rpc_url in config, returns 'no wallet configured'."""
        from handlers.aptos import AptosHandler

        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)

        config_no_rpc = {k: v for k, v in NATIVE_CONFIG.items() if k != "rpc_url"}

        handler = AptosHandler(config_no_rpc)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        all_values = " ".join(str(v) for v in balance.values()).lower()
        assert "no wallet" in all_values, f"Expected graceful message, got: {balance}"
