"""Integration tests for Phase 5 UTXO handlers."""
import pytest
from click.testing import CliRunner
from cli import main
from handlers.base import DripResult
from core import rate_limiter as rl


# All 6 UTXO assets
UTXO_ASSETS = ["TBTC4", "TBCH", "TBTG", "TLTC", "TDOGE", "TDASH"]

# Valid test addresses per coin_type
UTXO_ADDRESSES = {
    "TBTC4": "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
    "TBCH": "mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef",
    "TBTG": "mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef",
    "TLTC": "mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef",
    "TDOGE": "nX4JjzPU1VPFwjDiLqnkUSrvMHMAdViCeP",
    "TDASH": "yPv7h2i8v3dJjfSH4L3x91JSJszjdbsJJA",
}


# ---------------------------------------------------------------------------
# faucet list --family utxo
# ---------------------------------------------------------------------------

def test_list_utxo():
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "utxo"])
    assert result.exit_code == 0
    for asset in UTXO_ASSETS:
        assert asset in result.output


# ---------------------------------------------------------------------------
# faucet drip --dry-run tests
# ---------------------------------------------------------------------------

def test_drip_tbtc4_dry_run():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["drip", "--dry-run", "TBTC4", "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert "TBTC4" in result.output


def test_drip_tbch_dry_run():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["drip", "--dry-run", "TBCH", "mzBc4XEFSdzCDcTxAgf6EZXgsZWpztRhef"],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output


# ---------------------------------------------------------------------------
# Mocked drip tests
# ---------------------------------------------------------------------------

def test_drip_tbtc4_mocked(tmp_path, monkeypatch):
    from handlers.utxo import UtxoHandler
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True,
        tx_hash="UtxoTxHash123abc",
        explorer_url="https://blockstream.info/testnet/tx/UtxoTxHash123abc",
        error=None,
        amount="0.001",
        asset="TBTC4",
    )

    async def mock_drip(self, address, asset_id, amount):
        return mock_result

    monkeypatch.setattr(UtxoHandler, "drip", mock_drip)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["drip", "TBTC4", "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"],
    )
    assert result.exit_code == 0
    assert "UtxoTxHash123abc" in result.output


def test_drip_each_utxo_asset_mocked(tmp_path, monkeypatch):
    from handlers.utxo import UtxoHandler
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    runner = CliRunner()

    for asset_id in UTXO_ASSETS:
        address = UTXO_ADDRESSES[asset_id]

        if asset_id == "TBTC4":
            mock_result = DripResult(
                success=True,
                tx_hash=f"TxHash_{asset_id}",
                explorer_url=f"https://explorer/{asset_id}",
                error=None,
                amount="0.001",
                asset=asset_id,
            )
        else:
            # TBD assets return failure with "TBD" in error
            mock_result = DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} rpc_url not yet configured (TBD)",
                amount="0.01",
                asset=asset_id,
            )

        async def mock_drip(self, addr, aid, amt, _result=mock_result):
            return _result

        monkeypatch.setattr(UtxoHandler, "drip", mock_drip)
        result = runner.invoke(main, ["drip", asset_id, address])
        assert result.exit_code == 0

        if asset_id == "TBTC4":
            assert f"TxHash_{asset_id}" in result.output
        else:
            assert "TBD" in result.output


# ---------------------------------------------------------------------------
# faucet init utxo
# ---------------------------------------------------------------------------

def test_init_utxo_no_wallet(monkeypatch):
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    monkeypatch.delenv("FAUCET_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "utxo"])
    assert result.exit_code == 0
    assert "Error" in result.output


def test_init_utxo_with_wallet(monkeypatch):
    monkeypatch.setenv("FAUCET_PRIVATE_KEY", "a" * 64)
    monkeypatch.delenv("FAUCET_MNEMONIC", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "utxo"])
    assert result.exit_code == 0
    assert "configured" in result.output.lower() or "utxo" in result.output.lower()
    # Table should contain asset info
    for asset in UTXO_ASSETS:
        assert asset in result.output
