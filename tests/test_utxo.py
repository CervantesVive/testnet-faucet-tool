"""Unit tests for handlers/utxo.py (UtxoHandler)."""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.base import DripResult


# ---------------------------------------------------------------------------
# Helpers: mock cryptography module (not installed in test env)
# ---------------------------------------------------------------------------

def _make_utxo_crypto_modules():
    """Return sys.modules patches for the cryptography package (secp256k1 EC)."""
    mock_pub_compressed = bytes(33)  # fake 33-byte compressed pubkey

    mock_pub_key = MagicMock()
    mock_pub_key.public_bytes.return_value = mock_pub_compressed

    mock_priv_key = MagicMock()
    mock_priv_key.public_key.return_value = mock_pub_key
    # sign returns fake DER-encoded signature bytes
    mock_priv_key.sign.return_value = b"\x30\x06\x02\x01\x01\x02\x01\x01"

    mock_ec_mod = MagicMock()
    mock_ec_mod.SECP256K1.return_value = MagicMock()
    mock_ec_mod.derive_private_key.return_value = mock_priv_key
    mock_ec_mod.ECDSA = MagicMock()

    mock_serialization = MagicMock()
    mock_encoding = MagicMock()
    mock_encoding.X962 = "X962"
    mock_pub_format = MagicMock()
    mock_pub_format.CompressedPoint = "CompressedPoint"
    mock_serialization.Encoding = mock_encoding
    mock_serialization.PublicFormat = mock_pub_format

    mock_hashes = MagicMock()
    mock_hashes.Prehashed.return_value = MagicMock()
    mock_hashes.SHA256.return_value = MagicMock()

    mock_dss_utils = MagicMock()
    mock_dss_utils.decode_dss_signature.return_value = (1, 1)

    modules = {
        "cryptography": MagicMock(),
        "cryptography.hazmat": MagicMock(),
        "cryptography.hazmat.primitives": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        "cryptography.hazmat.primitives.asymmetric.ec": mock_ec_mod,
        "cryptography.hazmat.primitives.asymmetric.utils": mock_dss_utils,
        "cryptography.hazmat.primitives.serialization": mock_serialization,
        "cryptography.hazmat.primitives.hashes": mock_hashes,
        "cryptography.hazmat.backends": MagicMock(),
    }
    return modules


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

TBTC4_CONFIG = {
    "family": "utxo",
    "blockchain": "Bitcoin",
    "network": "testnet4",
    "rpc_url": "https://blockstream.info/testnet/api",
    "explorer": "https://blockstream.info/testnet/tx/{tx_hash}",
    "native_asset": True,
    "drip_amount": "0.001",
    "decimals": 8,
    "coin_type": 1,
}

TBD_BCH_CONFIG = {
    "family": "utxo",
    "blockchain": "Bitcoin Cash",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "",
    "native_asset": True,
    "drip_amount": "0.01",
    "decimals": 8,
    "coin_type": 145,
}

TBD_LTC_CONFIG = {
    "family": "utxo",
    "blockchain": "Litecoin",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "",
    "native_asset": True,
    "drip_amount": "0.1",
    "decimals": 8,
    "coin_type": 2,
}

TBD_DOGE_CONFIG = {
    "family": "utxo",
    "blockchain": "Dogecoin",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "",
    "native_asset": True,
    "drip_amount": "100",
    "decimals": 8,
    "coin_type": 3,
}

TBD_BTG_CONFIG = {
    "family": "utxo",
    "blockchain": "Bitcoin Gold",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "",
    "native_asset": True,
    "drip_amount": "0.01",
    "decimals": 8,
    "coin_type": 156,
}

TBD_DASH_CONFIG = {
    "family": "utxo",
    "blockchain": "Dash",
    "network": "testnet",
    "rpc_url": "TBD",
    "explorer": "",
    "native_asset": True,
    "drip_amount": "0.01",
    "decimals": 8,
    "coin_type": 5,
}

# Valid test private key (32 bytes)
VALID_PRIV_KEY_HEX = "aa" * 32


# ---------------------------------------------------------------------------
# 1. TBD rpc_url tests
# ---------------------------------------------------------------------------

class TestDripTBD:
    @pytest.mark.asyncio
    async def test_drip_tbd_bch(self):
        """TBCH with TBD rpc_url returns failure with TBD in error."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_BCH_CONFIG)
        result = await handler.drip("mTestAddress1234567890123456789", "TBCH", "0.01")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert "TBD" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_ltc(self):
        """TLTC with TBD rpc_url returns failure with TBD in error."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_LTC_CONFIG)
        result = await handler.drip("mTestAddress1234567890123456789", "TLTC", "0.1")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert "TBD" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_doge(self):
        """TDOGE with TBD rpc_url returns failure with TBD in error."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_DOGE_CONFIG)
        result = await handler.drip("nTestAddress1234567890123456789", "TDOGE", "100")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert "TBD" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_btg(self):
        """TBTG with TBD rpc_url returns failure with TBD in error."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_BTG_CONFIG)
        result = await handler.drip("mTestAddress1234567890123456789", "TBTG", "0.01")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert "TBD" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbd_dash(self):
        """TDASH with TBD rpc_url returns failure with TBD in error."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_DASH_CONFIG)
        result = await handler.drip("yTestAddress1234567890123456789", "TDASH", "0.01")

        assert isinstance(result, DripResult)
        assert result.success is False
        assert "TBD" in result.error


# ---------------------------------------------------------------------------
# 2. TBTC4 drip success
# ---------------------------------------------------------------------------

class TestDripTBTC4:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIV_KEY_HEX}, clear=False)
    async def test_drip_tbtc4_success(self):
        """Successful TBTC4 drip: fetch UTXOs, build tx, broadcast."""
        from handlers.utxo import UtxoHandler

        fake_txid_in = "a" * 64
        fake_txid_out = "b" * 64

        utxo_resp_data = [{"txid": fake_txid_in, "vout": 0, "value": 200000}]

        # Session 1: GET for UTXOs
        utxo_resp = AsyncMock()
        utxo_resp.json = AsyncMock(return_value=utxo_resp_data)
        utxo_resp.__aenter__ = AsyncMock(return_value=utxo_resp)
        utxo_resp.__aexit__ = AsyncMock(return_value=None)

        # Session 2: POST for broadcast
        broadcast_resp = AsyncMock()
        broadcast_resp.text = AsyncMock(return_value=fake_txid_out)
        broadcast_resp.status = 200
        broadcast_resp.__aenter__ = AsyncMock(return_value=broadcast_resp)
        broadcast_resp.__aexit__ = AsyncMock(return_value=None)

        sessions_created = []

        def make_session():
            session_num = len(sessions_created)
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            if session_num == 0:
                # First session: GET UTXOs
                session.get = MagicMock(return_value=utxo_resp)
            else:
                # Second session: POST broadcast
                session.post = MagicMock(return_value=broadcast_resp)

            sessions_created.append(session)
            return session

        dest_addr = "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"
        fake_raw_tx = bytes.fromhex("0200000001" + "aa" * 100)

        with patch("handlers.utxo._build_and_sign_btc_tx", return_value=fake_raw_tx), \
             patch("handlers.utxo.aiohttp.ClientSession", side_effect=make_session):
            handler = UtxoHandler(TBTC4_CONFIG)
            handler._get_faucet_address = MagicMock(return_value="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx")
            handler._get_private_key_bytes = MagicMock(return_value=bytes(32))
            result = await handler.drip(dest_addr, "TBTC4", "0.001")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash == fake_txid_out
        assert result.explorer_url is not None
        assert fake_txid_out in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIV_KEY_HEX}, clear=False)
    async def test_drip_tbtc4_no_utxos(self):
        """No UTXOs available returns failed DripResult."""
        from handlers.utxo import UtxoHandler

        utxo_resp = AsyncMock()
        utxo_resp.json = AsyncMock(return_value=[])
        utxo_resp.__aenter__ = AsyncMock(return_value=utxo_resp)
        utxo_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=utxo_resp)

        with patch("handlers.utxo.aiohttp.ClientSession", return_value=mock_session):
            handler = UtxoHandler(TBTC4_CONFIG)
            handler._get_faucet_address = MagicMock(return_value="tb1qtest1234")
            handler._get_private_key_bytes = MagicMock(return_value=bytes(32))
            result = await handler.drip("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "TBTC4", "0.001")

        assert result.success is False
        assert "No UTXOs" in result.error

    @pytest.mark.asyncio
    async def test_drip_tbtc4_no_wallet(self, monkeypatch):
        """Missing wallet env vars returns failed DripResult."""
        from handlers.utxo import UtxoHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = UtxoHandler(TBTC4_CONFIG)
        result = await handler.drip("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "TBTC4", "0.001")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIV_KEY_HEX}, clear=False)
    async def test_drip_tbtc4_broadcast_failure(self):
        """Broadcast returning non-200 results in failed DripResult."""
        from handlers.utxo import UtxoHandler

        fake_txid_in = "a" * 64
        utxo_resp_data = [{"txid": fake_txid_in, "vout": 0, "value": 200000}]

        utxo_resp = AsyncMock()
        utxo_resp.json = AsyncMock(return_value=utxo_resp_data)
        utxo_resp.__aenter__ = AsyncMock(return_value=utxo_resp)
        utxo_resp.__aexit__ = AsyncMock(return_value=None)

        broadcast_resp = AsyncMock()
        broadcast_resp.text = AsyncMock(return_value="some error")
        broadcast_resp.status = 400
        broadcast_resp.__aenter__ = AsyncMock(return_value=broadcast_resp)
        broadcast_resp.__aexit__ = AsyncMock(return_value=None)

        sessions_created = []

        def make_session():
            session_num = len(sessions_created)
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            if session_num == 0:
                session.get = MagicMock(return_value=utxo_resp)
            else:
                session.post = MagicMock(return_value=broadcast_resp)

            sessions_created.append(session)
            return session

        fake_raw_tx = bytes.fromhex("0200000001" + "aa" * 100)

        with patch("handlers.utxo._build_and_sign_btc_tx", return_value=fake_raw_tx), \
             patch("handlers.utxo.aiohttp.ClientSession", side_effect=make_session):
            handler = UtxoHandler(TBTC4_CONFIG)
            handler._get_faucet_address = MagicMock(return_value="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx")
            handler._get_private_key_bytes = MagicMock(return_value=bytes(32))
            result = await handler.drip("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "TBTC4", "0.001")

        assert result.success is False
        assert "Broadcast failed" in result.error


# ---------------------------------------------------------------------------
# 3. validate_address tests
# ---------------------------------------------------------------------------

class TestValidateAddress:
    # --- BTC testnet (coin_type 1) ---
    def test_btc_valid_bech32(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assert handler.validate_address("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx") is True

    def test_btc_valid_base58_n(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assert handler.validate_address("n1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_btc_valid_base58_m(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assert handler.validate_address("m1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_btc_invalid_mainnet(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assert handler.validate_address("1abcDefGHJKLmnPQRSTuvWXyz1234567") is False

    def test_btc_invalid_empty(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assert handler.validate_address("") is False

    # --- BCH testnet (coin_type 145) ---
    def test_bch_valid_cashaddr(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BCH_CONFIG)
        assert handler.validate_address("bchtest:qp0k6fs6q2hzmpyps3acl7a2akr5kseqhge6h4wdgt") is True

    def test_bch_valid_base58_m(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BCH_CONFIG)
        assert handler.validate_address("m1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_bch_invalid_mainnet_cashaddr(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BCH_CONFIG)
        assert handler.validate_address("bitcoincash:qp0k6fs6q2hzmpyps3acl7a2akr5kseqhg") is False

    # --- BTG testnet (coin_type 156) ---
    def test_btg_valid_base58_m(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BTG_CONFIG)
        assert handler.validate_address("m1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_btg_valid_base58_n(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BTG_CONFIG)
        assert handler.validate_address("n1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_btg_valid_base58_2(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BTG_CONFIG)
        assert handler.validate_address("21abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_btg_invalid_tb1(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_BTG_CONFIG)
        assert handler.validate_address("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx") is False

    # --- LTC testnet (coin_type 2) ---
    def test_ltc_valid_bech32(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_LTC_CONFIG)
        assert handler.validate_address("tltc1qw508d6qejxtdg4y5r3zarvar234567") is True

    def test_ltc_valid_base58_m(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_LTC_CONFIG)
        assert handler.validate_address("m1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_ltc_valid_base58_Q(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_LTC_CONFIG)
        assert handler.validate_address("Q1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_ltc_invalid_mainnet(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_LTC_CONFIG)
        assert handler.validate_address("ltc1qw508d6qejxtdg4y5r3zarvar234567") is False

    # --- DOGE testnet (coin_type 3) ---
    def test_doge_valid_n(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_DOGE_CONFIG)
        assert handler.validate_address("n1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_doge_valid_m(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_DOGE_CONFIG)
        assert handler.validate_address("m1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_doge_invalid_mainnet(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_DOGE_CONFIG)
        assert handler.validate_address("D1abcDefGHJKLmnPQRSTuvWXyz123456") is False

    # --- DASH testnet (coin_type 5) ---
    def test_dash_valid_y(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_DASH_CONFIG)
        assert handler.validate_address("y1abcDefGHJKLmnPQRSTuvWXyz123456") is True

    def test_dash_invalid_X(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBD_DASH_CONFIG)
        assert handler.validate_address("X1abcDefGHJKLmnPQRSTuvWXyz123456") is False


# ---------------------------------------------------------------------------
# 4. get_faucet_balance tests
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        """_get_faucet_address raising RuntimeError -> 'no wallet configured'."""
        from handlers.utxo import UtxoHandler

        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = UtxoHandler(TBTC4_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "no wallet configured" in val

    @pytest.mark.asyncio
    async def test_get_faucet_balance_tbd(self):
        """TBD rpc_url returns 'rpc_url not yet configured (TBD)'."""
        from handlers.utxo import UtxoHandler

        handler = UtxoHandler(TBD_BCH_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        assert "rpc_url not yet configured (TBD)" in val

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": VALID_PRIV_KEY_HEX}, clear=False)
    async def test_get_faucet_balance_success(self):
        """Mock aiohttp response with chain_stats -> formatted balance."""
        from handlers.utxo import UtxoHandler

        balance_data = {
            "chain_stats": {
                "funded_txo_sum": 500000,
                "spent_txo_sum": 100000,
            }
        }

        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=balance_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_resp)

        with patch("handlers.utxo.aiohttp.ClientSession", return_value=mock_session):
            handler = UtxoHandler(TBTC4_CONFIG)
            handler._get_faucet_address = MagicMock(return_value="tb1qtest1234")
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) == 1
        val = list(balance.values())[0]
        # 400000 sats = 0.00400000 BTC
        assert "0.00400000" in val


# ---------------------------------------------------------------------------
# 5. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets(self):
        from handlers.utxo import UtxoHandler
        handler = UtxoHandler(TBTC4_CONFIG)
        assets = handler.supported_assets()
        assert len(assets) == 6, f"Expected 6 UTXO assets, got {len(assets)}: {assets}"

    def test_supported_assets_all_utxo_family(self):
        from handlers.utxo import UtxoHandler
        from core.registry import load_registry
        handler = UtxoHandler(TBTC4_CONFIG)
        assets = handler.supported_assets()
        registry = load_registry()
        for asset_id in assets:
            assert asset_id in registry
            assert registry[asset_id].get("family") == "utxo", (
                f"{asset_id} has family={registry[asset_id].get('family')!r}, expected 'utxo'"
            )
