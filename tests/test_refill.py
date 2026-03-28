"""Tests for the faucet refill command."""

from click.testing import CliRunner
from cli import main
from unittest.mock import patch, AsyncMock, MagicMock


def _make_handler(balance_return):
    """Create a mock handler with the given get_faucet_balance return value."""
    handler = MagicMock()
    handler.get_faucet_balance = AsyncMock(return_value=balance_return)
    return handler


def _asset_config(drip_amount="0.05", family="evm", blockchain="Ethereum"):
    return {
        "drip_amount": drip_amount,
        "native_asset": True,
        "family": family,
        "blockchain": blockchain,
    }


def test_refill_ok(tmp_path, monkeypatch):
    """Balance above threshold shows OK."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_handler = _make_handler({"HTETH": "5.0"})

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "OK" in result.output
            assert "1 OK" in result.output
            assert "0 LOW" in result.output
            assert "0 ERROR" in result.output


def test_refill_low_balance(tmp_path, monkeypatch):
    """Balance below threshold shows LOW."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    # drip_amount=0.05, threshold=0.1, balance=0.01 -> LOW
    mock_handler = _make_handler({"HTETH": "0.01"})

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "LOW" in result.output
            assert "0 OK" in result.output
            assert "1 LOW" in result.output
            assert "0 ERROR" in result.output


def test_refill_no_wallet_configured(tmp_path, monkeypatch):
    """Non-numeric balance string like 'no wallet configured' shows ERROR."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_handler = _make_handler({"HTETH": "no wallet configured"})

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "ERROR" in result.output
            assert "ERROR hteth" in result.output
            assert "1 ERROR" in result.output


def test_refill_handler_exception(tmp_path, monkeypatch):
    """Handler that raises an exception shows ERROR."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_handler = MagicMock()
    mock_handler.get_faucet_balance = AsyncMock(side_effect=RuntimeError("connection failed"))

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "ERROR" in result.output
            assert "1 ERROR" in result.output


def test_refill_threshold_override(tmp_path, monkeypatch):
    """--threshold flag overrides the default 2x drip_amount."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    # Balance 1.0, default threshold would be 0.1 (2*0.05) -> OK
    # But with --threshold 10.0 -> LOW
    mock_handler = _make_handler({"HTETH": "1.0"})

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill", "--threshold", "10.0"])
            assert result.exit_code == 0
            assert "LOW" in result.output
            assert "1 LOW" in result.output


def test_refill_family_filter(tmp_path, monkeypatch):
    """--family flag filters to only matching assets."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_handler = _make_handler({"TSOL": "5.0"})

    assets = {
        "hteth": _asset_config(family="evm", blockchain="Ethereum"),
        "tsol": _asset_config(family="solana", blockchain="Solana"),
    }

    with patch("cli.get_all_assets", return_value=assets):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill", "--family", "solana"])
            assert result.exit_code == 0
            # Only solana asset should appear, not evm
            assert "1 OK" in result.output
            assert "Solana" in result.output


def test_refill_get_handler_raises(tmp_path, monkeypatch):
    """get_handler raising NotImplementedError shows ERROR."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", side_effect=NotImplementedError("no handler")):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "ERROR" in result.output
            assert "1 ERROR" in result.output


def test_refill_multiple_assets_mixed(tmp_path, monkeypatch):
    """Multiple assets with mixed statuses."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    assets = {
        "hteth": _asset_config(drip_amount="0.05", family="evm", blockchain="Ethereum"),
        "tsol": _asset_config(drip_amount="1.0", family="solana", blockchain="Solana"),
        "tatom": _asset_config(drip_amount="0.5", family="cosmos", blockchain="Cosmos Hub"),
    }

    def mock_get_handler(asset_id):
        if asset_id == "hteth":
            return _make_handler({"HTETH": "5.0"})  # OK (5.0 >= 0.1)
        elif asset_id == "tsol":
            return _make_handler({"TSOL": "0.5"})  # LOW (0.5 < 2.0)
        elif asset_id == "tatom":
            return _make_handler({"TATOM": "no wallet configured"})  # ERROR
        raise NotImplementedError(f"no handler for {asset_id}")

    with patch("cli.get_all_assets", return_value=assets):
        with patch("cli.get_handler", side_effect=mock_get_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "1 OK" in result.output
            assert "1 LOW" in result.output
            assert "1 ERROR" in result.output


def test_refill_summary_line(tmp_path, monkeypatch):
    """Summary line is printed at the end."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_handler = _make_handler({"HTETH": "5.0"})

    with patch("cli.get_all_assets", return_value={"hteth": _asset_config()}):
        with patch("cli.get_handler", return_value=mock_handler):
            runner = CliRunner()
            result = runner.invoke(main, ["refill"])
            assert result.exit_code == 0
            assert "Summary:" in result.output
