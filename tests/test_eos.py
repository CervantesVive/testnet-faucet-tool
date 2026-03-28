"""Unit tests for handlers/eos.py (EosHandler)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "eos",
    "blockchain": "EOS",
    "network": "jungle4",
    "rpc_url": "https://jungle4.cryptolions.io",
    "explorer": "TBD",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 4,
}

TOKEN_CONFIG = {
    "family": "eos",
    "blockchain": "EOS",
    "network": "jungle4",
    "rpc_url": "https://jungle4.cryptolions.io",
    "explorer": "TBD",
    "native_asset": False,
    "contract_account": "TBD",
    "drip_amount": "10",
    "decimals": 4,
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
    def test_valid_simple(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        assert handler.validate_address("eosio") is True

    def test_valid_dotted(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        assert handler.validate_address("user.name") is True

    def test_invalid_uppercase(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        assert handler.validate_address("UPPER") is False

    def test_invalid_too_long(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        assert handler.validate_address("toolongaccountname") is False


class TestDrip:
    @pytest.mark.asyncio
    async def test_drip_native_no_sdk(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        result = await handler.drip("eosio", "TEOS", "1")
        assert result.success is False
        assert "eospy" in result.error

    @pytest.mark.asyncio
    async def test_drip_token_not_configured(self):
        from handlers.eos import EosHandler

        handler = EosHandler(TOKEN_CONFIG)
        result = await handler.drip("eosio", "TEOS:BOX", "10")
        assert result.success is False
        assert "not yet configured" in result.error


class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_no_wallet(self, monkeypatch):
        from handlers.eos import EosHandler

        monkeypatch.delenv("FAUCET_EOS_ACCOUNT", raising=False)
        handler = EosHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert balance["EOS"] == "no wallet configured"

    @pytest.mark.asyncio
    @patch("handlers.eos.aiohttp.ClientSession")
    async def test_with_account(self, mock_cs, monkeypatch):
        from handlers.eos import EosHandler

        monkeypatch.setenv("FAUCET_EOS_ACCOUNT", "faucetacct11")
        mock_cs_instance = _mock_aiohttp_session(
            {"core_liquid_balance": "10.0000 EOS"}
        )
        mock_cs.side_effect = mock_cs_instance.side_effect
        mock_cs.return_value = mock_cs_instance.return_value

        handler = EosHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()
        assert balance["EOS"] == "10.0000"


class TestSupportedAssets:
    def test_contains_expected(self):
        from handlers.eos import EosHandler

        handler = EosHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert "TEOS" in assets
