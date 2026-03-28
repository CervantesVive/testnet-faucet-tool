"""Unit tests for handlers/near.py (NearHandler)."""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult


# ---------------------------------------------------------------------------
# Helpers: mock cryptography module (not installed in test env)
# ---------------------------------------------------------------------------

def _make_crypto_modules():
    """Return a dict of sys.modules patches for the cryptography package."""
    mock_pub_key = MagicMock()
    mock_pub_key.public_bytes_raw.return_value = bytes(32)  # 32 zero bytes

    mock_priv_key = MagicMock()
    mock_priv_key.public_key.return_value = mock_pub_key
    mock_priv_key.sign.return_value = bytes(64)  # 64-byte fake signature

    mock_ed25519_priv_cls = MagicMock()
    mock_ed25519_priv_cls.from_private_bytes.return_value = mock_priv_key

    mock_ed25519_mod = MagicMock()
    mock_ed25519_mod.Ed25519PrivateKey = mock_ed25519_priv_cls

    mock_hazmat_prim_asym_ed = MagicMock()
    mock_hazmat_prim_asym_ed.Ed25519PrivateKey = mock_ed25519_priv_cls

    modules = {
        "cryptography": MagicMock(),
        "cryptography.hazmat": MagicMock(),
        "cryptography.hazmat.primitives": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric.ed25519": mock_hazmat_prim_asym_ed,
        "cryptography.hazmat.primitives.asymmetric.ec": MagicMock(),
        "cryptography.hazmat.primitives.serialization": MagicMock(),
        "cryptography.hazmat.backends": MagicMock(),
        "cryptography.hazmat.primitives.hashes": MagicMock(),
    }
    return modules, mock_priv_key, mock_pub_key

# ---------------------------------------------------------------------------
# Config fixtures (mirroring actual chains.yaml entries)
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "near",
    "blockchain": "NEAR",
    "network": "testnet",
    "rpc_url": "https://rpc.testnet.near.org",
    "faucet_url": "https://helper.testnet.near.org/account",
    "explorer": "https://testnet.nearblocks.io/txns/{tx_hash}",
    "native_asset": True,
    "drip_amount": "1",
    "decimals": 24,
}

TOKEN_TBD_CONFIG = {
    "family": "near",
    "native_asset": False,
    "contract_id": "TBD",
    "rpc_url": "https://rpc.testnet.near.org",
    "explorer": "https://testnet.nearblocks.io/txns/{tx_hash}",
    "drip_amount": "10",
    "decimals": 6,
}

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# A valid 64-hex-char implicit NEAR account ID
VALID_IMPLICIT_ADDRESS = "a" * 64
# A valid named NEAR account
VALID_NAMED_ADDRESS = "alice.testnet"
# A valid 2-char minimum
VALID_MIN_ADDRESS = "ab"

# ---------------------------------------------------------------------------
# Helper: build aiohttp mock
# ---------------------------------------------------------------------------

def _make_session_mock(responses: list[dict]) -> MagicMock:
    """Return a mock aiohttp.ClientSession that returns the given JSON responses in order."""
    call_count = [-1]

    def make_response(data):
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)
        return mock_resp

    resp_mocks = [make_response(d) for d in responses]

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    post_call_count = [-1]

    def post_side_effect(*args, **kwargs):
        post_call_count[0] += 1
        idx = post_call_count[0]
        if idx < len(resp_mocks):
            return resp_mocks[idx]
        return resp_mocks[-1]

    session.post = MagicMock(side_effect=post_side_effect)
    session.get = MagicMock(return_value=resp_mocks[0] if resp_mocks else AsyncMock())
    return session


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_implicit_64_hex(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_IMPLICIT_ADDRESS) is True

    def test_valid_named_account(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_NAMED_ADDRESS) is True

    def test_valid_min_length(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address(VALID_MIN_ADDRESS) is True

    def test_invalid_too_short(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("a") is False

    def test_invalid_too_long(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("a" * 65) is False

    def test_invalid_uppercase(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("Alice.testnet") is False

    def test_invalid_spaces(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("alice testnet") is False

    def test_invalid_empty(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False

    def test_valid_with_dots_and_hyphens(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assert handler.validate_address("my-wallet.testnet") is True


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_count(self):
        from handlers.near import NearHandler
        handler = NearHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 2, f"Expected 2 NEAR assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_near_family(self):
        from handlers.near import NearHandler
        from core.registry import load_registry
        handler = NearHandler(NATIVE_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry
            assert registry[asset_id].get("family") == "near", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'near'"
            )


# ---------------------------------------------------------------------------
# 3. drip native
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "FAUCET_NEAR_ACCOUNT_ID": "faucet.testnet",
        "FAUCET_PRIVATE_KEY": "a" * 64,
    }, clear=False)
    async def test_drip_native_success(self):
        from handlers.near import NearHandler

        # Three sessions used by _drip_native:
        # 1st session: view_access_key nonce query + block hash query (two posts)
        # 2nd session: broadcast_tx_commit

        nonce_resp = {"result": {"nonce": 5}}
        block_resp = {"result": {"header": {"hash": "11111111111111111111111111111111"}}}
        broadcast_resp = {
            "result": {
                "transaction": {"hash": "TESTHASH123"},
                "transaction_outcome": {"id": "TESTHASH123"},
            }
        }

        sessions_created = []

        def make_session():
            idx = [0]
            # Session 1 handles nonce+block, session 2 handles broadcast
            responses_per_session = [
                [nonce_resp, block_resp],  # session 1
                [broadcast_resp],           # session 2
            ]
            session_num = len(sessions_created)
            responses = responses_per_session[min(session_num, len(responses_per_session) - 1)]

            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            resp_mocks = []
            for data in responses:
                r = AsyncMock()
                r.json = AsyncMock(return_value=data)
                r.__aenter__ = AsyncMock(return_value=r)
                r.__aexit__ = AsyncMock(return_value=None)
                resp_mocks.append(r)

            def post_side_effect(*args, **kwargs):
                i = idx[0]
                idx[0] += 1
                return resp_mocks[min(i, len(resp_mocks) - 1)]

            session.post = MagicMock(side_effect=post_side_effect)
            sessions_created.append(session)
            return session

        crypto_modules, mock_priv, mock_pub = _make_crypto_modules()
        with patch.dict(sys.modules, crypto_modules), \
             patch("handlers.near.aiohttp.ClientSession", side_effect=make_session):
            handler = NearHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_NAMED_ADDRESS, "TNEAR", "1")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == "TESTHASH123"
        assert result.explorer_url is not None
        assert "TESTHASH123" in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    async def test_drip_native_no_wallet(self, monkeypatch):
        """Missing FAUCET_PRIVATE_KEY should result in a failed DripResult."""
        from handlers.near import NearHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_NEAR_ACCOUNT_ID", raising=False)

        handler = NearHandler(NATIVE_CONFIG)
        result = await handler.drip(VALID_NAMED_ADDRESS, "TNEAR", "1")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "FAUCET_NEAR_ACCOUNT_ID": "faucet.testnet",
        "FAUCET_PRIVATE_KEY": "a" * 64,
    }, clear=False)
    async def test_drip_native_rpc_error(self):
        """RPC error in broadcast_tx_commit should result in a failed DripResult."""
        from handlers.near import NearHandler

        nonce_resp = {"result": {"nonce": 5}}
        block_resp = {"result": {"header": {"hash": "11111111111111111111111111111111"}}}
        error_resp = {"error": {"code": -32000, "message": "TX invalid"}}

        sessions_created = []

        def make_session():
            idx = [0]
            responses_per_session = [
                [nonce_resp, block_resp],
                [error_resp],
            ]
            session_num = len(sessions_created)
            responses = responses_per_session[min(session_num, len(responses_per_session) - 1)]

            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            resp_mocks = []
            for data in responses:
                r = AsyncMock()
                r.json = AsyncMock(return_value=data)
                r.__aenter__ = AsyncMock(return_value=r)
                r.__aexit__ = AsyncMock(return_value=None)
                resp_mocks.append(r)

            def post_side_effect(*args, **kwargs):
                i = idx[0]
                idx[0] += 1
                return resp_mocks[min(i, len(resp_mocks) - 1)]

            session.post = MagicMock(side_effect=post_side_effect)
            sessions_created.append(session)
            return session

        crypto_modules, _, _ = _make_crypto_modules()
        with patch.dict(sys.modules, crypto_modules), \
             patch("handlers.near.aiohttp.ClientSession", side_effect=make_session):
            handler = NearHandler(NATIVE_CONFIG)
            result = await handler.drip(VALID_NAMED_ADDRESS, "TNEAR", "1")

        assert result.success is False
        assert result.error is not None


# ---------------------------------------------------------------------------
# 4. drip token TBD
# ---------------------------------------------------------------------------

class TestDripTokenTBD:
    @pytest.mark.asyncio
    async def test_drip_token_tbd_contract(self):
        """Token with contract_id='TBD' should fail immediately without network call."""
        from handlers.near import NearHandler

        handler = NearHandler(TOKEN_TBD_CONFIG)
        result = await handler.drip(VALID_NAMED_ADDRESS, "TNEAR:USDC", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """No wallet configured returns 'no wallet configured'."""
        from handlers.near import NearHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_NEAR_ACCOUNT_ID", raising=False)

        handler = NearHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "FAUCET_NEAR_ACCOUNT_ID": "faucet.testnet",
        "FAUCET_PRIVATE_KEY": "a" * 64,
    }, clear=False)
    async def test_get_faucet_balance_success(self):
        """Should return formatted NEAR balance string."""
        from handlers.near import NearHandler

        # 1 NEAR = 10^24 yoctoNEAR
        yocto_near = 10 ** 24
        balance_resp = {"result": {"amount": str(yocto_near)}}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=balance_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch("handlers.near.aiohttp.ClientSession", return_value=mock_session):
            handler = NearHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "1.000000" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "FAUCET_NEAR_ACCOUNT_ID": "faucet.testnet",
        "FAUCET_PRIVATE_KEY": "a" * 64,
    }, clear=False)
    async def test_get_faucet_balance_rpc_error(self):
        """RPC error should return error message."""
        from handlers.near import NearHandler

        error_resp = {"error": {"code": -32000, "message": "Account not found"}}

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=error_resp)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch("handlers.near.aiohttp.ClientSession", return_value=mock_session):
            handler = NearHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        val = list(balance.values())[0]
        assert "error" in val
