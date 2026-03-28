"""Tests for the faucet batch command."""
from unittest.mock import patch, AsyncMock, MagicMock

from click.testing import CliRunner
from handlers.base import DripResult
from cli import main


def _mock_handler(valid=True, success=True, tx_hash="0xabc123", error=None):
    handler = MagicMock()
    handler.validate_address.return_value = valid
    handler.drip = AsyncMock(return_value=DripResult(
        success=success,
        tx_hash=tx_hash if success else None,
        explorer_url=None,
        error=error,
        amount="0.05",
        asset="HTETH",
    ))
    return handler


def _write_csv(tmp_path, lines):
    csv_file = tmp_path / "batch.csv"
    csv_file.write_text("\n".join(lines) + "\n")
    return csv_file


def test_batch_two_column_csv(tmp_path, monkeypatch):
    """Two-column CSV with asset_id,address works."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "HTETH,0x1234567890abcdef1234567890abcdef12345678",
        "HTETH,0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    ])

    handler = _mock_handler()
    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "OK" in result.output
    assert "2 succeeded" in result.output
    assert handler.drip.call_count == 2


def test_batch_one_column_csv_with_asset_flag(tmp_path, monkeypatch):
    """Single-column CSV with --asset flag works."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "0x1234567890abcdef1234567890abcdef12345678",
        "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    ])

    handler = _mock_handler()
    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", "--asset", "HTETH", str(csv_file)])

    assert result.exit_code == 0
    assert "2 succeeded" in result.output


def test_batch_one_column_csv_without_asset_flag(tmp_path, monkeypatch):
    """Single-column CSV without --asset flag reports error per row."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "0x1234567890abcdef1234567890abcdef12345678",
    ])

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "--asset flag" in result.output


def test_batch_skips_comments_and_empty_lines(tmp_path, monkeypatch):
    """Comment lines and empty lines are skipped."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "# This is a comment",
        "",
        "HTETH,0x1234567890abcdef1234567890abcdef12345678",
        "# Another comment",
        "",
    ])

    handler = _mock_handler()
    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "1 succeeded" in result.output
    assert handler.drip.call_count == 1


def test_batch_unknown_asset(tmp_path, monkeypatch):
    """Unknown asset ID is reported as error and processing continues."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "BOGUS,0x1234567890abcdef1234567890abcdef12345678",
        "HTETH,0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    ])

    handler = _mock_handler()

    def fake_get_config(asset_id):
        if asset_id == "BOGUS":
            raise KeyError(f"Unknown asset: {asset_id}")
        return {"drip_amount": "0.05", "family": "evm"}

    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", side_effect=fake_get_config):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "1 succeeded, 1 failed" in result.output


def test_batch_invalid_address(tmp_path, monkeypatch):
    """Invalid address is reported as error."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "HTETH,not_a_valid_address",
    ])

    handler = _mock_handler(valid=False)
    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "Invalid address" in result.output


def test_batch_drip_failure(tmp_path, monkeypatch):
    """Failed drip is reported in summary."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "HTETH,0x1234567890abcdef1234567890abcdef12345678",
    ])

    handler = _mock_handler(success=False, error="insufficient funds")
    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "FAILED" in result.output
    assert "insufficient funds" in result.output


def test_batch_file_not_found():
    """Non-existent CSV file produces error."""
    runner = CliRunner()
    result = runner.invoke(main, ["batch", "/nonexistent/file.csv"])

    assert result.exit_code != 0


def test_batch_handler_not_implemented(tmp_path, monkeypatch):
    """NotImplementedError from get_handler is reported as SKIP."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "HTETH,0x1234567890abcdef1234567890abcdef12345678",
    ])

    with patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
        with patch("cli.get_handler", side_effect=NotImplementedError("No handler for evm")):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "SKIP" in result.output


def test_batch_empty_csv(tmp_path, monkeypatch):
    """Empty CSV file prints 'no valid rows' message."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, ["# only comments", ""])

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "No valid rows" in result.output


def test_batch_mixed_results(tmp_path, monkeypatch):
    """Mix of successes and failures produces correct summary counts."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    csv_file = _write_csv(tmp_path, [
        "HTETH,0x1111111111111111111111111111111111111111",
        "BOGUS,0x2222222222222222222222222222222222222222",
        "HTETH,0x3333333333333333333333333333333333333333",
    ])

    handler = _mock_handler()

    def fake_get_config(asset_id):
        if asset_id == "BOGUS":
            raise KeyError(f"Unknown asset: {asset_id}")
        return {"drip_amount": "0.05", "family": "evm"}

    with patch("cli.get_handler", return_value=handler):
        with patch("cli.get_asset_config", side_effect=fake_get_config):
            runner = CliRunner()
            result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0
    assert "2 succeeded, 1 failed" in result.output
