"""Integration tests for Phase 4 handlers (sui, aptos, near, xrp, stellar, tron, ton)."""
import pytest
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner
from cli import main
from handlers.base import DripResult


# ---------------------------------------------------------------------------
# faucet list --family <family>  tests
# ---------------------------------------------------------------------------

def test_list_sui_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "sui"])
    assert result.exit_code == 0
    assert "TSUI" in result.output
    sui_lines = [l for l in result.output.splitlines() if "sui" in l.lower()]
    assert len(sui_lines) >= 3


def test_list_aptos_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "aptos"])
    assert result.exit_code == 0
    assert "TAPT" in result.output
    aptos_lines = [l for l in result.output.splitlines() if "aptos" in l.lower()]
    assert len(aptos_lines) >= 3


def test_list_near_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "near"])
    assert result.exit_code == 0
    assert "TNEAR" in result.output
    near_lines = [l for l in result.output.splitlines() if "near" in l.lower()]
    assert len(near_lines) >= 2


def test_list_xrp_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "xrp"])
    assert result.exit_code == 0
    assert "TXRP" in result.output
    xrp_lines = [l for l in result.output.splitlines() if "xrp" in l.lower()]
    assert len(xrp_lines) >= 2


def test_list_stellar_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "stellar"])
    assert result.exit_code == 0
    assert "TXLM" in result.output
    stellar_lines = [l for l in result.output.splitlines() if "stellar" in l.lower()]
    assert len(stellar_lines) >= 4


def test_list_tron_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "tron"])
    assert result.exit_code == 0
    assert "TTRX" in result.output
    tron_lines = [l for l in result.output.splitlines() if "tron" in l.lower()]
    assert len(tron_lines) >= 4


def test_list_ton_assets():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "ton"])
    assert result.exit_code == 0
    assert "TTON" in result.output
    ton_lines = [l for l in result.output.splitlines() if "ton" in l.lower()]
    assert len(ton_lines) >= 1


# ---------------------------------------------------------------------------
# faucet drip --dry-run tests (one per family)
# ---------------------------------------------------------------------------

def test_drip_tsui_dry_run():
    runner = CliRunner()
    address = "0x" + "a" * 64
    result = runner.invoke(main, ["drip", "--dry-run", "TSUI", address])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_tapt_dry_run():
    runner = CliRunner()
    address = "0x" + "b" * 64
    result = runner.invoke(main, ["drip", "--dry-run", "TAPT", address])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_tnear_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "TNEAR", "alice.testnet"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_txrp_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "TXRP", "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_txlm_dry_run():
    runner = CliRunner()
    address = "GAIDEG3LUBJZB5IBTWH2ESFTU5S6NLWJA5YWMPCFDAB2A5EGZQVYDUBS"
    result = runner.invoke(main, ["drip", "--dry-run", "TXLM", address])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_ttrx_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "TTRX", "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


def test_drip_tton_dry_run():
    runner = CliRunner()
    address = "0:" + "a" * 64
    result = runner.invoke(main, ["drip", "--dry-run", "TTON", address])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry" in result.output.lower()


# ---------------------------------------------------------------------------
# Mocked drip tests (one per family)
# ---------------------------------------------------------------------------

def test_drip_tsui_mocked(tmp_path, monkeypatch):
    from handlers.sui import SuiHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="SuiTxHash123", explorer_url="https://suiscan.xyz/testnet/tx/SuiTxHash123",
        error=None, amount="0.5", asset="TSUI"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(SuiHandler, "drip", mock_drip)
    address = "0x" + "a" * 64
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TSUI", address])
    assert result.exit_code == 0
    assert "SuiTxHash123" in result.output


def test_drip_tapt_mocked(tmp_path, monkeypatch):
    from handlers.aptos import AptosHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="AptosTxHash456", explorer_url="https://explorer.aptoslabs.com/txn/AptosTxHash456",
        error=None, amount="0.5", asset="TAPT"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(AptosHandler, "drip", mock_drip)
    address = "0x" + "b" * 64
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TAPT", address])
    assert result.exit_code == 0
    assert "AptosTxHash456" in result.output


def test_drip_tnear_mocked(tmp_path, monkeypatch):
    from handlers.near import NearHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="NearTxHash789", explorer_url="https://explorer.testnet.near.org/NearTxHash789",
        error=None, amount="1.0", asset="TNEAR"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(NearHandler, "drip", mock_drip)
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TNEAR", "alice.testnet"])
    assert result.exit_code == 0
    assert "NearTxHash789" in result.output


def test_drip_txrp_mocked(tmp_path, monkeypatch):
    from handlers.xrp import XrpHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="XrpTxHashABC", explorer_url="https://testnet.xrpl.org/transactions/XrpTxHashABC",
        error=None, amount="10", asset="TXRP"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(XrpHandler, "drip", mock_drip)
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TXRP", "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"])
    assert result.exit_code == 0
    assert "XrpTxHashABC" in result.output


def test_drip_txlm_mocked(tmp_path, monkeypatch):
    from handlers.stellar import StellarHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="StellarTxHashDEF", explorer_url="https://stellar.expert/explorer/testnet/tx/StellarTxHashDEF",
        error=None, amount="100", asset="TXLM"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(StellarHandler, "drip", mock_drip)
    address = "GAIDEG3LUBJZB5IBTWH2ESFTU5S6NLWJA5YWMPCFDAB2A5EGZQVYDUBS"
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TXLM", address])
    assert result.exit_code == 0
    assert "StellarTxHashDEF" in result.output


def test_drip_ttrx_mocked(tmp_path, monkeypatch):
    from handlers.tron import TronHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="TronTxHashGHI", explorer_url="https://nile.tronscan.org/#/transaction/TronTxHashGHI",
        error=None, amount="100", asset="TTRX"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(TronHandler, "drip", mock_drip)
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TTRX", "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9"])
    assert result.exit_code == 0
    assert "TronTxHashGHI" in result.output


def test_drip_tton_mocked(tmp_path, monkeypatch):
    from handlers.ton import TonHandler
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="TonTxHashJKL", explorer_url="https://testnet.tonscan.org/tx/TonTxHashJKL",
        error=None, amount="1.0", asset="TTON"
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(TonHandler, "drip", mock_drip)
    address = "0:" + "a" * 64
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "TTON", address])
    assert result.exit_code == 0
    assert "TonTxHashJKL" in result.output


# ---------------------------------------------------------------------------
# faucet init <family> — no wallet configured tests
# ---------------------------------------------------------------------------

def test_init_sui_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "sui"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_aptos_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "aptos"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_near_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "near"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_xrp_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "xrp"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_stellar_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "stellar"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_tron_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "tron"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


def test_init_ton_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "ton"])
    assert result.exit_code == 0
    assert "Error" in result.output or "FAUCET_MNEMONIC" in result.output


# ---------------------------------------------------------------------------
# faucet init <family> — with mnemonic configured tests
# ---------------------------------------------------------------------------

def test_init_sui_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "sui"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "sui" in result.output.lower()


def test_init_aptos_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "aptos"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "aptos" in result.output.lower()


def test_init_near_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "near"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "near" in result.output.lower()


def test_init_xrp_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "xrp"])
    assert result.exit_code == 0
    # Either shows address (if xrpl available) or configured message
    assert "xrp" in result.output.lower() or "configured" in result.output.lower()


def test_init_stellar_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "stellar"])
    assert result.exit_code == 0
    assert "stellar" in result.output.lower() or "configured" in result.output.lower()


def test_init_tron_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "tron"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "tron" in result.output.lower()


def test_init_ton_with_mnemonic(monkeypatch):
    monkeypatch.setenv("FAUCET_MNEMONIC", "test test test test test test test test test test test junk")
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "ton"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "ton" in result.output.lower()
