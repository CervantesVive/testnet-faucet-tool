"""Unit tests for handlers/hedera.py (HederaHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "hedera",
    "blockchain": "Hedera",
    "network": "testnet",
    "rpc_url": "https://testnet.mirrornode.hedera.com",
    "explorer": "https://hashscan.io/testnet/transaction/{tx_hash}",
    "native_asset": True,
    "drip_amount": "100",
    "decimals": 8,
}

TOKEN_CONFIG = {
    "family": "hedera",
    "blockchain": "Hedera",
    "network": "testnet",
    "rpc_url": "https://testnet.mirrornode.hedera.com",
    "explorer": "https://hashscan.io/testnet/transaction/{tx_hash}",
    "native_asset": False,
    "token_id": "TBD",
    "drip_amount": "10",
    "decimals": 6,
}


# ---------------------------------------------------------------------------
# aiohttp mock helper
# ---------------------------------------------------------------------------

def _mock_aiohttp_session(response_json):
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=response_json)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    return MagicMock(return_value=mock_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(NATIVE_CONFIG)
        assert handler.validate_address("0.0.12345") is True

    def test_invalid_two_parts(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(NATIVE_CONFIG)
        assert handler.validate_address("0.12345") is False

    def test_invalid_alpha(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(NATIVE_CONFIG)
        assert handler.validate_address("abc") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_native_no_sdk(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(NATIVE_CONFIG)
        result = await handler.drip("0.0.12345", "THBAR", "100")
        assert result.success is False
        assert "hedera-sdk-py" in result.error

    @pytest.mark.asyncio
    async def test_drip_token_tbd(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(TOKEN_CONFIG)
        result = await handler.drip("0.0.12345", "THBAR:USDC", "10")
        assert result.success is False
        assert "token_id not yet configured" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_no_wallet(self, monkeypatch):
        from handlers.hedera import HederaHandler

        monkeypatch.delenv("FAUCET_HEDERA_ACCOUNT_ID", raising=False)
        handler = HederaHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert balance["Hedera"] == "no wallet configured"

    @pytest.mark.asyncio
    @patch("handlers.hedera.aiohttp.ClientSession")
    async def test_with_account(self, mock_cs, monkeypatch):
        from handlers.hedera import HederaHandler

        monkeypatch.setenv("FAUCET_HEDERA_ACCOUNT_ID", "0.0.99999")
        mock_cs_instance = _mock_aiohttp_session(
            {"balance": {"balance": 100000000}}
        )
        mock_cs.side_effect = mock_cs_instance.side_effect
        mock_cs.return_value = mock_cs_instance.return_value

        handler = HederaHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        # 100000000 / 10^8 = 1.00000000
        assert balance["Hedera"] == "1.00000000"


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.hedera import HederaHandler

        handler = HederaHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "THBAR" in assets
