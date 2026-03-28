"""Tests for the faucet dashboard command."""

from click.testing import CliRunner
from cli import main
from unittest.mock import patch, AsyncMock, MagicMock


def _make_assets(overrides=None):
    """Helper to build a single-asset dict for testing."""
    base = {
        "HTETH": {
            "family": "evm",
            "blockchain": "Ethereum",
            "native_asset": True,
            "drip_amount": "0.05",
            "decimals": 18,
            "network": "holesky",
        }
    }
    if overrides:
        base.update(overrides)
    return base


def _run_dashboard(monkeypatch, tmp_path, assets, handler, args=None):
    """Run the dashboard command with mocked assets and handler."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    with patch("cli.get_all_assets", return_value=assets):
        with patch("cli.get_handler", return_value=handler):
            runner = CliRunner()
            result = runner.invoke(main, args or ["dashboard"])
    return result


def test_dashboard_funded(tmp_path, monkeypatch):
    """Funded asset shows FUNDED status."""
    handler = MagicMock()
    handler.get_faucet_balance = AsyncMock(return_value={"HTETH": "5.0"})

    result = _run_dashboard(monkeypatch, tmp_path, _make_assets(), handler)
    assert result.exit_code == 0
    assert "FUNDED" in result.output or "funded" in result.output
    assert "HTETH" in result.output
    assert "1 funded" in result.output


def test_dashboard_low_balance(tmp_path, monkeypatch):
    """Balance below 2x drip_amount shows LOW status."""
    handler = MagicMock()
    # drip_amount is 0.05, threshold is 0.10, balance 0.05 < 0.10 => LOW
    handler.get_faucet_balance = AsyncMock(return_value={"HTETH": "0.05"})

    result = _run_dashboard(monkeypatch, tmp_path, _make_assets(), handler)
    assert result.exit_code == 0
    assert "LOW" in result.output or "low" in result.output
    assert "1 low" in result.output


def test_dashboard_handler_exception(tmp_path, monkeypatch):
    """Handler raising exception shows ERROR status."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    with patch("cli.get_all_assets", return_value=_make_assets()):
        with patch("cli.get_handler", side_effect=NotImplementedError("no handler")):
            runner = CliRunner()
            result = runner.invoke(main, ["dashboard"])

    assert result.exit_code == 0
    assert "ERROR" in result.output or "error" in result.output
    assert "1 error" in result.output


def test_dashboard_no_wallet(tmp_path, monkeypatch):
    """Non-numeric balance string shows ERROR status."""
    handler = MagicMock()
    handler.get_faucet_balance = AsyncMock(return_value={"HTETH": "no wallet configured"})

    result = _run_dashboard(monkeypatch, tmp_path, _make_assets(), handler)
    assert result.exit_code == 0
    assert "ERROR" in result.output or "error" in result.output
    assert "no wallet configured" in result.output


def test_dashboard_family_filter(tmp_path, monkeypatch):
    """--family flag filters to matching family only."""
    assets = _make_assets({
        "TSOL": {
            "family": "solana",
            "blockchain": "Solana",
            "native_asset": True,
            "drip_amount": "1.0",
            "decimals": 9,
            "network": "devnet",
        }
    })
    handler = MagicMock()
    handler.get_faucet_balance = AsyncMock(return_value={"TSOL": "10.0"})

    result = _run_dashboard(monkeypatch, tmp_path, assets, handler, ["dashboard", "--family", "solana"])
    assert result.exit_code == 0
    assert "TSOL" in result.output
    assert "HTETH" not in result.output


def test_dashboard_empty(tmp_path, monkeypatch):
    """No native assets produces empty dashboard."""
    assets = {
        "TOKEN": {"family": "evm", "blockchain": "Ethereum", "native_asset": False}
    }
    handler = MagicMock()

    result = _run_dashboard(monkeypatch, tmp_path, assets, handler)
    assert result.exit_code == 0
    assert "0 funded, 0 low, 0 error" in result.output


def test_dashboard_mixed_statuses(tmp_path, monkeypatch):
    """Mixed statuses show correct summary counts."""
    assets = {
        "HTETH": {
            "family": "evm",
            "blockchain": "Ethereum",
            "native_asset": True,
            "drip_amount": "0.05",
            "decimals": 18,
            "network": "holesky",
        },
        "TSOL": {
            "family": "solana",
            "blockchain": "Solana",
            "native_asset": True,
            "drip_amount": "1.0",
            "decimals": 9,
            "network": "devnet",
        },
        "TXRP": {
            "family": "xrp",
            "blockchain": "XRP",
            "native_asset": True,
            "drip_amount": "10.0",
            "decimals": 6,
            "network": "testnet",
        },
    }

    def handler_for(asset_id):
        h = MagicMock()
        if asset_id == "HTETH":
            h.get_faucet_balance = AsyncMock(return_value={"HTETH": "5.0"})
        elif asset_id == "TSOL":
            h.get_faucet_balance = AsyncMock(return_value={"TSOL": "0.5"})
        else:
            h.get_faucet_balance = AsyncMock(return_value={"TXRP": "no wallet configured"})
        return h

    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    with patch("cli.get_all_assets", return_value=assets):
        with patch("cli.get_handler", side_effect=handler_for):
            runner = CliRunner()
            result = runner.invoke(main, ["dashboard"])

    assert result.exit_code == 0
    assert "1 funded" in result.output
    assert "1 low" in result.output
    assert "1 error" in result.output
