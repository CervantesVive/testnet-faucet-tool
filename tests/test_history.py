from click.testing import CliRunner
from cli import main


def test_history_empty(tmp_path, monkeypatch):
    import core.rate_limiter as rl
    import core.logger as logger_mod
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0
    assert "No drip history" in result.output


def test_history_shows_entries(tmp_path, monkeypatch):
    import core.rate_limiter as rl
    import core.logger as logger_mod
    from core.logger import log_drip
    from handlers.base import DripResult
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    # Log some drips
    log_drip("0x123", DripResult(success=True, tx_hash="0xabc", explorer_url=None,
                                  error=None, amount="0.05", asset="HTETH"))
    log_drip("0x456", DripResult(success=False, tx_hash=None, explorer_url=None,
                                  error="timeout", amount="1.0", asset="TSOL"))

    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0
    assert "HTETH" in result.output
    assert "TSOL" in result.output


def test_history_limit(tmp_path, monkeypatch):
    import core.rate_limiter as rl
    import core.logger as logger_mod
    from core.logger import log_drip
    from handlers.base import DripResult
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    for i in range(10):
        log_drip("0x123", DripResult(success=True, tx_hash=f"0x{i}", explorer_url=None,
                                      error=None, amount="0.05", asset="HTETH"))

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--limit", "3"])
    assert result.exit_code == 0
