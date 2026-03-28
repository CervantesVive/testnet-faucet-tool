import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from handlers.evm import EvmHandler
from handlers.base import DripResult

# ---------------------------------------------------------------------------
# Fixtures / shared config
# ---------------------------------------------------------------------------

NATIVE_CONFIG = {
    "family": "evm",
    "blockchain": "Ethereum",
    "network": "holesky",
    "rpc_url": "https://rpc.holesky.ethpandaops.io",
    "explorer": "https://holesky.etherscan.io/tx/{tx_hash}",
    "native_asset": True,
    "drip_amount": "0.05",
    "decimals": 18,
}

TOKEN_CONFIG = {
    "family": "evm",
    "blockchain": "Ethereum",
    "network": "holesky",
    "rpc_url": "https://rpc.holesky.ethpandaops.io",
    "explorer": "https://holesky.etherscan.io/tx/{tx_hash}",
    "native_asset": False,
    "contract_address": "0x1234567890123456789012345678901234567890",
    "drip_amount": "10",
    "decimals": 18,
}

TBD_TOKEN_CONFIG = {
    **TOKEN_CONFIG,
    "contract_address": "TBD",
}

TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_MNEMONIC = "test test test test test test test test test test test junk"
# BIP-44 m/44'/60'/0'/0/0 address for the test mnemonic above
MNEMONIC_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

FAKE_TX_HASH = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


# ---------------------------------------------------------------------------
# Helper to build a minimal Web3 mock suitable for native transfers
# ---------------------------------------------------------------------------

def _make_web3_mock(
    *,
    chain_id: int = 17000,
    gas_price: int = 10**9,
    nonce: int = 0,
    tx_hash: bytes | None = None,
    receipt_status: int = 1,
    faucet_balance: int = 10**18,
    recipient_balance: int = 10**17,
):
    if tx_hash is None:
        tx_hash = bytes.fromhex(FAKE_TX_HASH[2:])

    w3 = MagicMock()
    w3.eth.chain_id = chain_id
    w3.eth.gas_price = gas_price
    w3.eth.get_transaction_count.return_value = nonce
    w3.eth.send_raw_transaction.return_value = tx_hash
    w3.eth.wait_for_transaction_receipt.return_value = MagicMock(status=receipt_status)
    w3.to_wei.side_effect = lambda amount, unit: int(float(amount) * 10**18)
    w3.from_wei.side_effect = lambda val, unit: val / 10**18

    # get_balance: first call is faucet, subsequent calls are recipient
    w3.eth.get_balance.side_effect = [faucet_balance, recipient_balance]

    # eth.account.sign_transaction returns an object with .raw_transaction
    signed_tx = MagicMock()
    signed_tx.raw_transaction = b"\x00" * 32
    w3.eth.account.sign_transaction.return_value = signed_tx

    return w3


# ---------------------------------------------------------------------------
# 1. validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_validate_address_valid_checksummed(self):
        handler = EvmHandler(NATIVE_CONFIG)
        assert handler.validate_address(TEST_ADDRESS) is True

    def test_validate_address_valid_lowercase(self):
        handler = EvmHandler(NATIVE_CONFIG)
        assert handler.validate_address(TEST_ADDRESS.lower()) is True

    def test_validate_address_invalid(self):
        handler = EvmHandler(NATIVE_CONFIG)
        assert handler.validate_address("not-an-address") is False

    def test_validate_address_empty(self):
        handler = EvmHandler(NATIVE_CONFIG)
        assert handler.validate_address("") is False


# ---------------------------------------------------------------------------
# 2. supported_assets
# ---------------------------------------------------------------------------

class TestSupportedAssets:
    def test_supported_assets_returns_evm_assets(self):
        mock_registry = {
            "HTETH": {"family": "evm", "blockchain": "Ethereum"},
            "TSOL": {"family": "solana", "blockchain": "Solana"},
            "TAVAXP": {"family": "avalanche_p", "blockchain": "Avalanche"},
            "HTUSDCE": {"family": "evm", "blockchain": "Ethereum"},
        }
        with patch("handlers.evm.load_registry", return_value=mock_registry):
            handler = EvmHandler(NATIVE_CONFIG)
            assets = handler.supported_assets()

        assert len(assets) >= 1
        assert "HTETH" in assets
        assert "HTUSDCE" in assets
        assert "TSOL" not in assets
        assert "TAVAXP" not in assets


# ---------------------------------------------------------------------------
# 3. Native transfer (mock Web3)
# ---------------------------------------------------------------------------

class TestDripNative:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_native_success(self):
        w3 = _make_web3_mock(receipt_status=1)

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(NATIVE_CONFIG)
            result = await handler.drip(TEST_ADDRESS, "HTETH", "0.05")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.tx_hash.startswith("0x")
        assert result.explorer_url is not None
        assert result.tx_hash in result.explorer_url
        assert result.error is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_native_transaction_reverted(self):
        w3 = _make_web3_mock(receipt_status=0)

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(NATIVE_CONFIG)
            result = await handler.drip(TEST_ADDRESS, "HTETH", "0.05")

        assert result.success is False
        assert result.error is not None
        assert "reverted" in result.error.lower() or "Transaction reverted" in result.error

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_native_rpc_error(self):
        w3 = _make_web3_mock()
        w3.eth.send_raw_transaction.side_effect = Exception("RPC error")

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(NATIVE_CONFIG)
            result = await handler.drip(TEST_ADDRESS, "HTETH", "0.05")

        assert result.success is False
        assert result.error is not None
        assert "RPC error" in result.error


# ---------------------------------------------------------------------------
# 4. ERC-20 transfer (mock Web3)
# ---------------------------------------------------------------------------

def _make_erc20_web3_mock(
    *,
    receipt_status: int = 1,
    recipient_balance: int = 10**17,
):
    w3 = MagicMock()
    w3.eth.chain_id = 17000
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.to_wei.side_effect = lambda amount, unit: int(float(amount) * 10**18)
    w3.from_wei.side_effect = lambda val, unit: val / 10**18

    # _drip_erc20 calls get_balance once — for the recipient
    w3.eth.get_balance.return_value = recipient_balance

    # Build a signed tx
    signed_tx = MagicMock()
    signed_tx.raw_transaction = b"\x00" * 32
    w3.eth.account.sign_transaction.return_value = signed_tx

    tx_hash_bytes = bytes.fromhex(FAKE_TX_HASH[2:])
    w3.eth.send_raw_transaction.return_value = tx_hash_bytes
    w3.eth.wait_for_transaction_receipt.return_value = MagicMock(status=receipt_status)

    # ERC-20 contract mock
    contract = MagicMock()
    transfer_fn = MagicMock()
    transfer_fn.build_transaction.return_value = {
        "to": TOKEN_CONFIG["contract_address"],
        "data": "0x",
        "value": 0,
        "gas": 60000,
        "gasPrice": 10**9,
        "nonce": 0,
        "chainId": 17000,
    }
    contract.functions.transfer.return_value = transfer_fn
    w3.eth.contract.return_value = contract

    return w3


class TestDripERC20:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_erc20_success(self):
        w3 = _make_erc20_web3_mock(receipt_status=1, recipient_balance=10**17)

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(TOKEN_CONFIG)
            result = await handler.drip(TEST_ADDRESS, "HTUSDCE", "10")

        assert isinstance(result, DripResult)
        assert result.success is True
        assert result.tx_hash is not None
        assert result.tx_hash.startswith("0x")
        assert result.error is None
        # Verify gas estimation was called
        transfer_fn = w3.eth.contract.return_value.functions.transfer.return_value
        transfer_fn.estimate_gas.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_erc20_warns_no_recipient_gas(self, recwarn):
        w3 = _make_erc20_web3_mock(receipt_status=1, recipient_balance=0)

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(TOKEN_CONFIG)
            result = await handler.drip(TEST_ADDRESS, "HTUSDCE", "10")

        warning_messages = [str(w.message) for w in recwarn.list]
        has_gas_warning = any(
            "gas" in msg.lower() or "eth" in msg.lower() or "native" in msg.lower()
            for msg in warning_messages
        )
        assert has_gas_warning, f"Expected a gas warning but got: {warning_messages}"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_drip_erc20_tbd_contract(self):
        handler = EvmHandler(TBD_TOKEN_CONFIG)
        result = await handler.drip(TEST_ADDRESS, "HTUSDCE", "10")

        assert result.success is False
        assert result.error is not None
        assert "TBD" in result.error or "not yet deployed" in result.error.lower()


# ---------------------------------------------------------------------------
# 5. get_faucet_balance
# ---------------------------------------------------------------------------

class TestGetFaucetBalance:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=False)
    async def test_get_faucet_balance_native(self):
        w3 = MagicMock()
        w3.eth.get_balance.return_value = 5 * 10**17  # 0.5 ETH
        w3.from_wei.side_effect = lambda val, unit: val / 10**18

        with patch("handlers.evm.Web3", return_value=w3):
            handler = EvmHandler(NATIVE_CONFIG)
            balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        # All values should be strings (not error dicts or numbers)
        for key, val in balance.items():
            assert isinstance(val, str), f"Expected string balance for {key}, got {type(val)}"
            # A valid balance should not start with "error:"
            assert not val.startswith("error:"), f"Unexpected error in balance for {key}: {val}"

    @pytest.mark.asyncio
    async def test_get_faucet_balance_no_wallet(self, monkeypatch):
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)

        handler = EvmHandler(NATIVE_CONFIG)
        balance = await handler.get_faucet_balance()

        assert isinstance(balance, dict)
        assert len(balance) >= 1
        for key, val in balance.items():
            assert isinstance(val, str), f"Expected string for {key}"
            assert val.startswith("error:"), f"Expected error: prefix for {key}, got: {val}"


# ---------------------------------------------------------------------------
# 6. HD wallet derivation
# ---------------------------------------------------------------------------

class TestHDWallet:
    def test_hd_wallet_derives_correct_address(self, monkeypatch):
        monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
        monkeypatch.setenv("FAUCET_MNEMONIC", TEST_MNEMONIC)

        handler = EvmHandler(NATIVE_CONFIG)
        account = handler._get_account()

        assert account is not None
        assert account.address.lower() == MNEMONIC_ADDRESS.lower()
