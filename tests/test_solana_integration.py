"""Integration tests for Solana handler — tests end-to-end flow via CLI."""
import os
import pytest
from unittest.mock import patch
from click.testing import CliRunner
from cli import main


def test_init_solana_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_SOLANA_KEYPAIR", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "solana"])
    assert result.exit_code == 0
    assert "G9r1RYmVnXptzCA2an46rNnHsCAQLvjyM6vR2mo3LpG1" in result.output
    assert "solana airdrop" in result.output


def test_init_solana_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_SOLANA_KEYPAIR", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "solana"])
    assert result.exit_code == 0
    assert "Error" in result.output


def test_drip_tsol_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "TSOL", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_tsol_mocked(monkeypatch, tmp_path):
    # Patch SolanaHandler.drip to return a success DripResult without hitting devnet
    # Note: test must be synchronous — CLI uses asyncio.run() which can't nest event loops
    from handlers.base import DripResult
    from handlers.solana import SolanaHandler

    async def mock_drip(self, address, asset_id, amount):
        return DripResult(
            success=True,
            tx_hash="5xyzFakeSignature",
            explorer_url="https://explorer.solana.com/tx/5xyzFakeSignature?cluster=devnet",
            error=None,
            amount=amount,
            asset=asset_id,
        )

    monkeypatch.setattr(SolanaHandler, "drip", mock_drip)
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test_faucet.db")

    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TSOL", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"])
    assert result.exit_code == 0
    assert "5xyzFakeSignature" in result.output


def test_list_solana_shows_12_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "solana"])
    assert result.exit_code == 0
    assert "TSOL" in result.output
    # Count rows - should see 12 assets
    lines_with_solana = [l for l in result.output.splitlines() if "solana" in l.lower()]
    assert len(lines_with_solana) >= 12
