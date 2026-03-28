"""Integration tests for Cosmos handler — tests end-to-end flow via CLI."""
import pytest
from click.testing import CliRunner
from cli import main


def test_init_cosmos_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "cosmos"])
    assert result.exit_code == 0
    assert "cosmos15yk64u7zc9g9k2yr2wmzeva5qgwxps6yxj00e7" in result.output


def test_init_cosmos_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "cosmos"])
    assert result.exit_code == 0
    assert "Error" in result.output


def test_drip_tatom_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "TATOM", "cosmos15yk64u7zc9g9k2yr2wmzeva5qgwxps6yxj00e7"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_tatom_mocked(monkeypatch, tmp_path):
    # Patch CosmosHandler.drip to return a success DripResult without hitting testnet
    # Note: test must be synchronous — CLI uses asyncio.run() which can't nest event loops
    from handlers.base import DripResult
    from handlers.cosmos import CosmosHandler

    async def mock_drip(self, address, asset_id, amount):
        return DripResult(
            success=True,
            tx_hash="CosmosTestHash123ABC",
            explorer_url="https://testnet.mintscan.io/cosmos-testnet/txs/CosmosTestHash123ABC",
            error=None,
            amount=amount,
            asset=asset_id,
        )

    monkeypatch.setattr(CosmosHandler, "drip", mock_drip)
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test_faucet.db")

    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TATOM", "cosmos15yk64u7zc9g9k2yr2wmzeva5qgwxps6yxj00e7"])
    assert result.exit_code == 0
    assert "CosmosTestHash123ABC" in result.output


def test_list_cosmos_shows_14_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "cosmos"])
    assert result.exit_code == 0
    assert "TATOM" in result.output
    # Count rows - should see at least 14 assets
    lines_with_cosmos = [l for l in result.output.splitlines() if "cosmos" in l.lower()]
    assert len(lines_with_cosmos) >= 14
