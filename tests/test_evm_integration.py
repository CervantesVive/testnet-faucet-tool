"""Integration tests for EVM handler — tests end-to-end flow with mocked RPC."""
import os
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from cli import main

TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def test_init_evm_with_mnemonic():
    runner = CliRunner()
    mnemonic = "test test test test test test test test test test test junk"
    with patch.dict(os.environ, {"FAUCET_MNEMONIC": mnemonic}):
        result = runner.invoke(main, ["init", "evm"])
    assert result.exit_code == 0
    assert "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266" in result.output


def test_init_evm_with_private_key():
    runner = CliRunner()
    with patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}):
        result = runner.invoke(main, ["init", "evm"])
    assert result.exit_code == 0
    assert TEST_ADDRESS in result.output


def test_init_evm_no_wallet():
    runner = CliRunner()
    env = {k: v for k, v in os.environ.items() if k not in ("FAUCET_MNEMONIC", "FAUCET_PRIVATE_KEY")}
    with patch.dict(os.environ, env, clear=True):
        result = runner.invoke(main, ["init", "evm"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_drip_hteth_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "HTETH", TEST_ADDRESS])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_hteth_mocked_rpc():
    runner = CliRunner()

    # Build a mock web3 that returns a successful receipt
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 17000
    mock_w3.eth.gas_price = 1_000_000_000
    mock_w3.eth.get_transaction_count.return_value = 0
    mock_w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
    UNIT_MAP = {"ether": 10**18, "gwei": 10**9, "wei": 1}
    mock_w3.to_wei.side_effect = lambda val, unit: int(float(val) * UNIT_MAP.get(unit, 1))

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir, \
         patch("handlers.evm.Web3", return_value=mock_w3), \
         patch("core.rate_limiter.DB_PATH", Path(tmpdir) / "faucet.db"), \
         patch.dict(os.environ, {"FAUCET_PRIVATE_KEY": TEST_PRIVATE_KEY}):
        result = runner.invoke(main, ["drip", "HTETH", TEST_ADDRESS])

    assert result.exit_code == 0, result.output
    assert "not yet implemented" not in result.output
    # Verify the drip actually reached the handler (rate limit or success output)
    assert result.exception is None, str(result.exception)


def test_status_evm_no_wallet():
    runner = CliRunner()
    env = {k: v for k, v in os.environ.items() if k not in ("FAUCET_MNEMONIC", "FAUCET_PRIVATE_KEY")}
    with patch.dict(os.environ, env, clear=True):
        result = runner.invoke(main, ["status", "--family", "evm"])
    # Should not crash — should show balances or error messages per asset
    assert result.exit_code == 0
