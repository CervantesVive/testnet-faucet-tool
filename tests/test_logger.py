import json
from core.logger import log_drip, read_history
from handlers.base import DripResult


def test_log_drip_creates_file(tmp_path, monkeypatch):
    import core.logger as logger_mod
    log_file = tmp_path / "history.log"
    monkeypatch.setattr(logger_mod, "LOG_PATH", log_file)

    result = DripResult(success=True, tx_hash="0xabc", explorer_url=None,
                        error=None, amount="0.05", asset="HTETH")
    log_drip("0x123", result)

    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["asset_id"] == "HTETH"
    assert entry["success"] is True
    assert entry["tx_hash"] == "0xabc"
    assert entry["address"] == "0x123"


def test_log_drip_appends(tmp_path, monkeypatch):
    import core.logger as logger_mod
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    for i in range(3):
        result = DripResult(success=True, tx_hash=f"0x{i}", explorer_url=None,
                            error=None, amount="0.05", asset="HTETH")
        log_drip("0x123", result)

    entries = read_history(limit=10)
    assert len(entries) == 3


def test_read_history_limit(tmp_path, monkeypatch):
    import core.logger as logger_mod
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    for i in range(10):
        result = DripResult(success=True, tx_hash=f"0x{i}", explorer_url=None,
                            error=None, amount="0.05", asset="HTETH")
        log_drip("0x123", result)

    entries = read_history(limit=3)
    assert len(entries) == 3


def test_read_history_empty(tmp_path, monkeypatch):
    import core.logger as logger_mod
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "nonexistent.log")

    entries = read_history()
    assert entries == []


def test_log_drip_failed(tmp_path, monkeypatch):
    import core.logger as logger_mod
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")

    result = DripResult(success=False, tx_hash=None, explorer_url=None,
                        error="Connection timeout", amount="0.05", asset="HTETH")
    log_drip("0x123", result)

    entries = read_history()
    assert len(entries) == 1
    assert entries[0]["success"] is False
    assert entries[0]["error"] == "Connection timeout"


def test_log_creates_parent_directory(tmp_path, monkeypatch):
    import core.logger as logger_mod
    nested = tmp_path / "deep" / "nested" / "history.log"
    monkeypatch.setattr(logger_mod, "LOG_PATH", nested)

    result = DripResult(success=True, tx_hash="0xabc", explorer_url=None,
                        error=None, amount="0.05", asset="HTETH")
    log_drip("0x123", result)
    assert nested.exists()
