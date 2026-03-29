# Wallet Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scheduled balance monitoring that auto-tops eligible wallets and alerts via Slack, email, webhook, and log when wallets are low.

**Architecture:** Two new `core/` modules (`alerting.py`, `monitor.py`) keep alert dispatch and check-and-act logic separate. Two new CLI commands (`check` one-shot, `monitor` daemon) share the same underlying `run_check()` function. All data lives in `~/.testnet-faucet/` (renamed from `~/.Custodian-faucet/`).

**Tech Stack:** Python stdlib only (no new deps) — `logging.handlers.TimedRotatingFileHandler` for rotating logs, `urllib.request` for HTTP channels, `smtplib` for email, `time.sleep` for the daemon loop.

---

## File Map

| File | Change | Responsibility |
|------|--------|----------------|
| `core/rate_limiter.py` | Modify | Rename default path and env var |
| `core/logger.py` | Modify | Rename default path and env var |
| `tests/conftest.py` | Modify | Update stale comment |
| `core/alerting.py` | Create | Config loading + alert dispatch (log/Slack/webhook/email) |
| `config/alerts.yaml.example` | Create | Committed schema template |
| `handlers/base.py` | Modify | Add `get_faucet_address() -> str \| None` |
| `core/monitor.py` | Create | `_parse_interval`, `check_all`, `run_check`, `_auto_top` |
| `cli.py` | Modify | Add `check` and `monitor` commands |
| `config/chains.yaml` | Modify | Add `refill_source: airdrop` to TSOL |
| `tests/test_alerting.py` | Create | Unit tests for all alert channels |
| `tests/test_monitor.py` | Create | Unit tests for check/auto-top logic |
| `tests/test_check_command.py` | Create | CLI integration tests |
| `CLAUDE.md` | Modify | Document new paths, env vars, commands |

---

## Task 1: Rename data directory paths

**Files:**
- Modify: `core/rate_limiter.py`
- Modify: `core/logger.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Run existing tests to establish baseline**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass (531 tests).

- [ ] **Step 2: Update `core/rate_limiter.py`**

Change line 6 from:
```python
DB_PATH = Path(os.environ.get("Custodian_FAUCET_DB_PATH", Path.home() / ".Custodian-faucet" / "rate_limits.db"))
```
To:
```python
DB_PATH = Path(os.environ.get("FAUCET_DB_PATH", Path.home() / ".testnet-faucet" / "rate_limits.db"))
```

- [ ] **Step 3: Update `core/logger.py`**

Change line 7 from:
```python
LOG_PATH = Path(os.environ.get("Custodian_FAUCET_LOG_PATH", Path.home() / ".Custodian-faucet" / "history.log"))
```
To:
```python
LOG_PATH = Path(os.environ.get("FAUCET_LOG_PATH", Path.home() / ".testnet-faucet" / "history.log"))
```

- [ ] **Step 4: Update the stale comment in `tests/conftest.py`**

Change the comment on line 28 from:
```python
    """Redirect drip history log to a temp file so tests don't write to ~/.Custodian-faucet/."""
```
To:
```python
    """Redirect drip history log to a temp file so tests don't write to ~/.testnet-faucet/."""
```

- [ ] **Step 5: Run tests — confirm no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: same count passes (531). The tests monkeypatch the module-level variable, not the path string, so they are unaffected.

- [ ] **Step 6: Commit**

```bash
git add core/rate_limiter.py core/logger.py tests/conftest.py
git commit -m "refactor: rename data dir from .Custodian-faucet to .testnet-faucet"
```

---

## Task 2: `core/alerting.py` — config loading and log channel

**Files:**
- Create: `core/alerting.py`
- Create: `tests/test_alerting.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_alerting.py`:

```python
"""Tests for core/alerting.py — alert channel dispatch."""
import logging
import pytest
import yaml
import core.alerting as alerting_mod
from core.alerting import send_alert


@pytest.fixture(autouse=True)
def reset_alert_logger():
    """Clear logger handlers between tests to prevent cross-test pollution."""
    logger = logging.getLogger("testnet_faucet.alerts")
    logger.handlers.clear()
    yield
    logger.handlers.clear()


@pytest.fixture()
def alerts_config(tmp_path, monkeypatch):
    """Write a minimal alerts.yaml to tmp_path and point ALERTS_CONFIG_PATH at it."""
    cfg_file = tmp_path / "alerts.yaml"
    monkeypatch.setattr(alerting_mod, "ALERTS_CONFIG_PATH", cfg_file)
    return cfg_file


def _write_log_only_config(cfg_file, log_path):
    cfg_file.write_text(yaml.dump({
        "alerts": {
            "log": {"enabled": True, "path": str(log_path), "backup_count": 5},
        }
    }))


def test_load_config_missing_file(tmp_path, monkeypatch):
    """Missing config file returns empty dict — no crash."""
    monkeypatch.setattr(alerting_mod, "ALERTS_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    config = alerting_mod._load_config()
    assert config == {}


def test_send_alert_creates_log_file(tmp_path, alerts_config):
    """send_alert() creates the log file."""
    log_path = tmp_path / "alerts.log"
    _write_log_only_config(alerts_config, log_path)
    send_alert("test message", [])
    assert log_path.exists()


def test_send_alert_log_contains_message(tmp_path, alerts_config):
    """Log file contains the alert message."""
    log_path = tmp_path / "alerts.log"
    _write_log_only_config(alerts_config, log_path)
    send_alert("wallets need attention", [])
    content = log_path.read_text()
    assert "wallets need attention" in content


def test_send_alert_log_entry_is_timestamped(tmp_path, alerts_config):
    """Log entry starts with an ISO-8601 UTC timestamp."""
    log_path = tmp_path / "alerts.log"
    _write_log_only_config(alerts_config, log_path)
    send_alert("timestamp test", [])
    line = log_path.read_text().strip().split("\n")[0]
    # e.g. "2026-03-28T14:32:01Z [INFO] timestamp test"
    assert "T" in line and "Z [INFO]" in line


def test_send_alert_no_config_file_falls_back_to_log(tmp_path, monkeypatch):
    """No config file → log-only fallback writes to default path without crashing."""
    monkeypatch.setattr(alerting_mod, "ALERTS_CONFIG_PATH", tmp_path / "missing.yaml")
    # Should not raise
    send_alert("fallback test", [])


def test_format_body_includes_asset_details():
    """_format_body() lists asset_id, balance, threshold, status, auto_top_result."""
    low_assets = [
        {"asset_id": "HTETH", "balance": 0.02, "threshold": 0.10,
         "status": "LOW", "auto_top_result": "N/A"},
    ]
    body = alerting_mod._format_body("header", low_assets)
    assert "HTETH" in body
    assert "0.02" in body
    assert "0.1" in body
    assert "LOW" in body
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_alerting.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.alerting'`

- [ ] **Step 3: Create `core/alerting.py`**

```python
"""Alert dispatch for the testnet faucet monitor."""
import json
import logging
import logging.handlers
import os
import smtplib
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

import yaml

ALERTS_CONFIG_PATH = Path(
    os.environ.get("FAUCET_ALERTS_CONFIG", Path.home() / ".testnet-faucet" / "alerts.yaml")
)


def _load_config() -> dict:
    """Load alerts.yaml. Returns empty dict if the file does not exist."""
    if not ALERTS_CONFIG_PATH.exists():
        return {}
    with open(ALERTS_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def _get_alert_logger(log_cfg: dict) -> logging.Logger:
    """Return (and lazily configure) the rotating file logger."""
    path_str = log_cfg.get("path", str(Path.home() / ".testnet-faucet" / "alerts.log"))
    log_path = Path(os.path.expanduser(path_str))
    backup_count = int(log_cfg.get("backup_count", 30))

    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("testnet_faucet.alerts")

    # Reset handlers if the target file has changed (e.g. between tests)
    file_handlers = [h for h in logger.handlers if hasattr(h, "baseFilename")]
    if file_handlers and file_handlers[0].baseFilename != str(log_path):
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()

    if not logger.handlers:
        handler = logging.handlers.TimedRotatingFileHandler(
            log_path, when="midnight", backupCount=backup_count, utc=True
        )
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        formatter.converter = time.gmtime  # UTC
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger


def _format_body(message: str, low_assets: list[dict]) -> str:
    """Format a human-readable alert body."""
    lines = [message, ""]
    for asset in low_assets:
        asset_id = asset.get("asset_id", "")
        balance = asset.get("balance")
        threshold = asset.get("threshold")
        status = asset.get("status", "LOW")
        auto_top = asset.get("auto_top_result", "N/A")
        bal_str = f"{balance:.4g}" if balance is not None else "N/A"
        thr_str = f"{threshold:.4g}" if threshold is not None else "N/A"
        lines.append(
            f"  {status} — {asset_id}: balance {bal_str} / threshold {thr_str}"
            f" — auto-top: {auto_top}"
        )
    return "\n".join(lines)


def _send_slack(cfg: dict, body: str) -> None:
    payload = json.dumps({"text": body}).encode()
    req = urllib.request.Request(
        cfg["webhook_url"],
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10):
        pass


def _send_webhook(cfg: dict, body: str) -> None:
    headers = dict(cfg.get("headers") or {})
    headers["Content-Type"] = "application/json"
    payload = json.dumps({"text": body}).encode()
    req = urllib.request.Request(
        cfg["url"],
        data=payload,
        headers=headers,
        method=cfg.get("method", "POST"),
    )
    with urllib.request.urlopen(req, timeout=10):
        pass


def _send_email(cfg: dict, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "[testnet-faucet] Wallet balance alert"
    msg["From"] = cfg["from"]
    recipients = cfg["to"]
    msg["To"] = ", ".join(recipients) if isinstance(recipients, list) else recipients
    msg.set_content(body)
    with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as smtp:
        smtp.starttls()
        smtp.login(cfg["username"], cfg["password"])
        smtp.send_message(msg)


def send_alert(message: str, low_assets: list[dict]) -> None:
    """Dispatch alert to all enabled channels. Per-channel failures are logged, not raised."""
    config = _load_config()
    alerts_cfg = config.get("alerts", {})
    body = _format_body(message, low_assets)

    # Log channel — enabled unless explicitly set to false
    log_cfg = alerts_cfg.get("log", {"enabled": True})
    logger = _get_alert_logger(log_cfg)
    if log_cfg.get("enabled", True):
        logger.info(message)

    # Slack
    slack_cfg = alerts_cfg.get("slack", {})
    if slack_cfg.get("enabled") and slack_cfg.get("webhook_url"):
        try:
            _send_slack(slack_cfg, body)
        except Exception as exc:
            logger.warning(f"Slack alert failed: {exc}")

    # Webhook
    webhook_cfg = alerts_cfg.get("webhook", {})
    if webhook_cfg.get("enabled") and webhook_cfg.get("url"):
        try:
            _send_webhook(webhook_cfg, body)
        except Exception as exc:
            logger.warning(f"Webhook alert failed: {exc}")

    # Email
    email_cfg = alerts_cfg.get("email", {})
    if email_cfg.get("enabled") and email_cfg.get("smtp_host"):
        try:
            _send_email(email_cfg, body)
        except Exception as exc:
            logger.warning(f"Email alert failed: {exc}")
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_alerting.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Run full suite — no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 538 tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/alerting.py tests/test_alerting.py
git commit -m "feat: add alerting module with log channel"
```

---

## Task 3: `core/alerting.py` — Slack, webhook, and email channels

**Files:**
- Modify: `tests/test_alerting.py` (add tests)
- No code changes to `core/alerting.py` — implementation was already written in Task 2

- [ ] **Step 1: Write failing tests for external channels**

Append to `tests/test_alerting.py`:

```python
from unittest.mock import patch, MagicMock


def _write_full_config(cfg_file, log_path, extra_channels: dict):
    """Write alerts.yaml with log channel + extra channels."""
    channels = {"log": {"enabled": True, "path": str(log_path), "backup_count": 5}}
    channels.update(extra_channels)
    cfg_file.write_text(yaml.dump({"alerts": channels}))


def test_send_alert_calls_slack(tmp_path, alerts_config):
    """Slack channel is called with correct payload when enabled."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"},
    })
    with patch("core.alerting._send_slack") as mock_slack:
        send_alert("slack test", [])
    mock_slack.assert_called_once()
    _cfg, body = mock_slack.call_args[0]
    assert "slack test" in body


def test_send_alert_skips_slack_when_disabled(tmp_path, alerts_config):
    """Disabled Slack channel is not called."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "slack": {"enabled": False, "webhook_url": "https://hooks.slack.com/test"},
    })
    with patch("core.alerting._send_slack") as mock_slack:
        send_alert("msg", [])
    mock_slack.assert_not_called()


def test_send_alert_calls_webhook(tmp_path, alerts_config):
    """Webhook channel is called when enabled."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "webhook": {"enabled": True, "url": "https://example.com/hook"},
    })
    with patch("core.alerting._send_webhook") as mock_wh:
        send_alert("webhook test", [])
    mock_wh.assert_called_once()


def test_send_alert_calls_email(tmp_path, alerts_config):
    """Email channel is called when enabled."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "email": {
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "username": "user",
            "password": "pass",
            "from": "faucet@example.com",
            "to": ["ops@example.com"],
        },
    })
    with patch("core.alerting._send_email") as mock_email:
        send_alert("email test", [])
    mock_email.assert_called_once()


def test_send_alert_slack_failure_does_not_block_other_channels(tmp_path, alerts_config):
    """If Slack fails, webhook and email still fire."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"},
        "webhook": {"enabled": True, "url": "https://example.com/hook"},
    })
    with patch("core.alerting._send_slack", side_effect=Exception("timeout")):
        with patch("core.alerting._send_webhook") as mock_wh:
            send_alert("msg", [])
    mock_wh.assert_called_once()


def test_send_alert_webhook_custom_headers(tmp_path, alerts_config):
    """Custom headers are included in webhook request."""
    log_path = tmp_path / "alerts.log"
    _write_full_config(alerts_config, log_path, {
        "webhook": {
            "enabled": True,
            "url": "https://example.com/hook",
            "headers": {"Authorization": "Bearer tok123"},
        },
    })
    captured = {}
    with patch("core.alerting._send_webhook") as mock_wh:
        send_alert("msg", [])
    cfg_arg = mock_wh.call_args[0][0]
    assert cfg_arg.get("headers", {}).get("Authorization") == "Bearer tok123"


def test_send_email_builds_correct_message(tmp_path, alerts_config):
    """_send_email() constructs EmailMessage with correct To/From/Subject."""
    log_path = tmp_path / "alerts.log"
    email_cfg = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "username": "u",
        "password": "p",
        "from": "faucet@example.com",
        "to": ["a@example.com", "b@example.com"],
    }
    sent_msgs = []

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent_msgs.append(msg)

    with patch("smtplib.SMTP", FakeSMTP):
        alerting_mod._send_email(email_cfg, "body text")

    assert len(sent_msgs) == 1
    msg = sent_msgs[0]
    assert msg["Subject"] == "[testnet-faucet] Wallet balance alert"
    assert "a@example.com" in msg["To"]
    assert msg["From"] == "faucet@example.com"
```

- [ ] **Step 2: Run new tests — confirm they pass**

(The implementation already exists from Task 2.)

```bash
.venv/bin/python -m pytest tests/test_alerting.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 545 tests pass.

- [ ] **Step 4: Create `config/alerts.yaml.example`**

```yaml
# Alert channel configuration for the testnet faucet monitor.
# Copy to ~/.testnet-faucet/alerts.yaml and edit as needed.
# Override location with: FAUCET_ALERTS_CONFIG=/path/to/alerts.yaml

alerts:
  # Log channel — always-on by default. Rotates daily, retains 30 days.
  log:
    enabled: true
    path: ~/.testnet-faucet/alerts.log
    backup_count: 30

  # Slack incoming webhook — post to a channel when wallets are low.
  slack:
    enabled: false
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL

  # Generic webhook — covers Discord, PagerDuty, custom endpoints.
  webhook:
    enabled: false
    url: https://your-service.example.com/hook
    method: POST
    headers:               # optional
      Authorization: Bearer YOUR_TOKEN

  # Email via SMTP.
  email:
    enabled: false
    smtp_host: smtp.example.com
    smtp_port: 587
    username: faucet@example.com
    password: YOUR_SMTP_PASSWORD
    from: faucet@example.com
    to:
      - ops@example.com
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_alerting.py config/alerts.yaml.example
git commit -m "feat: add Slack, webhook, and email alert channels"
```

---

## Task 4: `handlers/base.py` — add `get_faucet_address()`

**Files:**
- Modify: `handlers/base.py`
- Modify: `tests/test_base_handler.py`

- [ ] **Step 1: Write failing test**

Read `tests/test_base_handler.py` first to understand the existing test structure, then append:

```python
def test_get_faucet_address_returns_none_by_default():
    """BaseHandler.get_faucet_address() returns None — subclasses override it."""
    class ConcreteHandler(BaseHandler):
        async def drip(self, address, asset_id, amount): ...
        def validate_address(self, address): return True
        async def get_faucet_balance(self): return {}
        def supported_assets(self): return []

    handler = ConcreteHandler({})
    assert handler.get_faucet_address() is None
```

- [ ] **Step 2: Run test — confirm it fails**

```bash
.venv/bin/python -m pytest tests/test_base_handler.py::test_get_faucet_address_returns_none_by_default -v
```

Expected: `AttributeError: 'ConcreteHandler' object has no attribute 'get_faucet_address'`

- [ ] **Step 3: Add method to `handlers/base.py`**

After the `supported_assets` abstract method, add:

```python
    def get_faucet_address(self) -> str | None:
        """Return the faucet's own address for auto-refill, or None if not configured.

        Override in handlers that support auto-top. The monitor calls this to determine
        the recipient address for self-drip refills.
        """
        return None
```

- [ ] **Step 4: Run test — confirm it passes**

```bash
.venv/bin/python -m pytest tests/test_base_handler.py -v
```

Expected: all base handler tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: same count passes.

- [ ] **Step 6: Commit**

```bash
git add handlers/base.py tests/test_base_handler.py
git commit -m "feat: add get_faucet_address() hook to BaseHandler"
```

---

## Task 5: `core/monitor.py` — `_parse_interval` and `check_all`

**Files:**
- Create: `core/monitor.py`
- Create: `tests/test_monitor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_monitor.py`:

```python
"""Tests for core/monitor.py — balance check logic."""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from handlers.base import DripResult


# ---------------------------------------------------------------------------
# _parse_interval
# ---------------------------------------------------------------------------

def test_parse_interval_minutes():
    from core.monitor import _parse_interval
    assert _parse_interval("30m") == 1800


def test_parse_interval_hours():
    from core.monitor import _parse_interval
    assert _parse_interval("1h") == 3600


def test_parse_interval_days():
    from core.monitor import _parse_interval
    assert _parse_interval("1d") == 86400


def test_parse_interval_multi_digit():
    from core.monitor import _parse_interval
    assert _parse_interval("12h") == 43200


def test_parse_interval_invalid_raises():
    from core.monitor import _parse_interval
    with pytest.raises(ValueError, match="Invalid interval"):
        _parse_interval("2x")


def test_parse_interval_empty_raises():
    from core.monitor import _parse_interval
    with pytest.raises(ValueError):
        _parse_interval("")


# ---------------------------------------------------------------------------
# check_all
# ---------------------------------------------------------------------------

def _make_handler(balance_dict=None, side_effect=None):
    h = MagicMock()
    h.get_faucet_address.return_value = None
    if side_effect:
        h.get_faucet_balance = AsyncMock(side_effect=side_effect)
    else:
        h.get_faucet_balance = AsyncMock(return_value=balance_dict or {"native": "5.0"})
    return h


def _assets(drip="0.05", family="evm", refill_source=None):
    cfg = {
        "native_asset": True,
        "family": family,
        "blockchain": "TestChain",
        "drip_amount": drip,
    }
    if refill_source:
        cfg["refill_source"] = refill_source
    return {"TTEST": cfg}


def test_check_all_ok_status():
    """Balance >= 2x drip_amount → OK."""
    from core.monitor import check_all
    handler = _make_handler({"native": "1.0"})  # 1.0 >= 2*0.05=0.1 → OK
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(_assets(drip="0.05"))
    assert len(results) == 1
    assert results[0]["status"] == "OK"
    assert results[0]["balance"] == 1.0


def test_check_all_low_status():
    """Balance < 2x drip_amount → LOW."""
    from core.monitor import check_all
    handler = _make_handler({"native": "0.05"})  # 0.05 < 0.1 → LOW
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(_assets(drip="0.05"))
    assert results[0]["status"] == "LOW"


def test_check_all_error_non_numeric_balance():
    """Non-numeric balance string → ERROR."""
    from core.monitor import check_all
    handler = _make_handler({"native": "no wallet configured"})
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(_assets())
    assert results[0]["status"] == "ERROR"
    assert "Non-numeric" in results[0]["error"]


def test_check_all_error_handler_exception():
    """Handler exception → ERROR."""
    from core.monitor import check_all
    handler = _make_handler(side_effect=RuntimeError("network down"))
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(_assets())
    assert results[0]["status"] == "ERROR"
    assert "network down" in results[0]["error"]


def test_check_all_threshold_override():
    """threshold_override replaces 2x drip_amount calculation."""
    from core.monitor import check_all
    handler = _make_handler({"native": "1.0"})  # 1.0 < threshold=5.0 → LOW
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(_assets(drip="0.05"), threshold_override=5.0)
    assert results[0]["status"] == "LOW"
    assert results[0]["threshold"] == 5.0


def test_check_all_family_filter():
    """family filter excludes non-matching assets."""
    from core.monitor import check_all
    assets = {
        "TETH": {"native_asset": True, "family": "evm", "blockchain": "Eth",
                 "drip_amount": "0.05"},
        "TSOL": {"native_asset": True, "family": "solana", "blockchain": "Sol",
                 "drip_amount": "1.0"},
    }
    handler = _make_handler({"native": "5.0"})
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(assets, family="solana")
    assert len(results) == 1
    assert results[0]["asset_id"] == "TSOL"


def test_check_all_skips_non_native_assets():
    """Assets without native_asset: true are excluded."""
    from core.monitor import check_all
    assets = {
        "TTEST": {"native_asset": False, "family": "evm", "blockchain": "X",
                  "drip_amount": "0.05"},
    }
    results = check_all(assets)
    assert results == []


def test_check_all_result_includes_refill_source():
    """Result dict carries refill_source from chains config."""
    from core.monitor import check_all
    handler = _make_handler({"native": "0.0"})
    assets = _assets(drip="0.05", refill_source="airdrop")
    with patch("core.monitor.get_handler", return_value=handler):
        results = check_all(assets)
    assert results[0]["refill_source"] == "airdrop"
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_monitor.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.monitor'`

- [ ] **Step 3: Create `core/monitor.py`** (initial version — no `run_check` yet)

```python
"""Balance check and auto-top logic for the testnet faucet monitor."""
import asyncio
import re

from core.registry import get_all_assets, get_handler


def _parse_interval(s: str) -> int:
    """Convert '30m', '1h', '6h', '1d' to seconds. Raises ValueError on invalid input."""
    m = re.fullmatch(r"(\d+)([mhd])", s.strip())
    if not m:
        raise ValueError(f"Invalid interval {s!r}. Use e.g. '30m', '1h', '1d'.")
    value, unit = int(m.group(1)), m.group(2)
    return value * {"m": 60, "h": 3600, "d": 86400}[unit]


def check_all(
    assets: dict,
    threshold_override: float | None = None,
    family: str | None = None,
) -> list[dict]:
    """Check balances for all native assets. Returns list of result dicts.

    Each dict has: asset_id, blockchain, family, threshold, balance (float|None),
    status ('OK'|'LOW'|'ERROR'), error (str|None), refill_source (str|None),
    auto_top_attempted (bool), auto_top_succeeded (bool).
    """
    native = {k: v for k, v in assets.items() if v.get("native_asset")}
    if family:
        native = {k: v for k, v in native.items() if v.get("family") == family}

    results = []
    for asset_id in sorted(native):
        cfg = native[asset_id]
        drip_amount = float(cfg.get("drip_amount", "0"))
        threshold = threshold_override if threshold_override is not None else 2.0 * drip_amount

        r: dict = {
            "asset_id": asset_id,
            "blockchain": cfg.get("blockchain", ""),
            "family": cfg.get("family", ""),
            "threshold": threshold,
            "balance": None,
            "status": "ERROR",
            "error": None,
            "refill_source": cfg.get("refill_source"),
            "auto_top_attempted": False,
            "auto_top_succeeded": False,
        }

        balance_str = "N/A"
        try:
            handler = get_handler(asset_id)
            balances = asyncio.run(handler.get_faucet_balance())
            balance_str = next(iter(balances.values()), "N/A") if balances else "N/A"
            balance_val = float(balance_str)
            r["balance"] = balance_val
            r["status"] = "OK" if balance_val >= threshold else "LOW"
        except (ValueError, TypeError):
            r["error"] = f"Non-numeric balance: {balance_str}"
        except Exception as exc:
            r["error"] = str(exc)

        results.append(r)

    return results
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_monitor.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 559 tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/monitor.py tests/test_monitor.py
git commit -m "feat: add monitor module with _parse_interval and check_all"
```

---

## Task 6: `core/monitor.py` — `run_check` with auto-top and alert dispatch

**Files:**
- Modify: `core/monitor.py`
- Modify: `tests/test_monitor.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_monitor.py`:

```python
# ---------------------------------------------------------------------------
# run_check
# ---------------------------------------------------------------------------

def test_run_check_no_alert_when_all_ok():
    """No alert when all wallets are OK."""
    from core.monitor import run_check
    ok_result = [{"asset_id": "TTEST", "status": "OK", "balance": 5.0,
                  "threshold": 0.1, "refill_source": None,
                  "auto_top_attempted": False, "auto_top_succeeded": False,
                  "error": None}]
    with patch("core.monitor.get_all_assets", return_value={}):
        with patch("core.monitor.check_all", return_value=ok_result):
            with patch("core.monitor.send_alert") as mock_alert:
                run_check()
    mock_alert.assert_not_called()


def test_run_check_sends_alert_when_low():
    """Alert is dispatched when any wallet is LOW."""
    from core.monitor import run_check
    low_result = [{"asset_id": "TTEST", "status": "LOW", "balance": 0.01,
                   "threshold": 0.1, "refill_source": None,
                   "auto_top_attempted": False, "auto_top_succeeded": False,
                   "error": None}]
    with patch("core.monitor.get_all_assets", return_value={"TTEST": {}}):
        with patch("core.monitor.check_all", return_value=low_result):
            with patch("core.monitor.send_alert") as mock_alert:
                run_check()
    mock_alert.assert_called_once()
    message, alert_assets = mock_alert.call_args[0]
    assert "TTEST" in str(alert_assets)
    assert "testnet-faucet" in message


def test_run_check_sends_alert_when_error():
    """Alert is dispatched when any wallet has ERROR status."""
    from core.monitor import run_check
    err_result = [{"asset_id": "TTEST", "status": "ERROR", "balance": None,
                   "threshold": 0.1, "refill_source": None,
                   "auto_top_attempted": False, "auto_top_succeeded": False,
                   "error": "network down"}]
    with patch("core.monitor.get_all_assets", return_value={"TTEST": {}}):
        with patch("core.monitor.check_all", return_value=err_result):
            with patch("core.monitor.send_alert") as mock_alert:
                run_check()
    mock_alert.assert_called_once()


def test_run_check_attempts_auto_top_when_refill_source_set():
    """Auto-top is attempted for LOW wallets with refill_source."""
    from core.monitor import run_check
    low_result = [{"asset_id": "TTEST", "status": "LOW", "balance": 0.0,
                   "threshold": 0.1, "refill_source": "airdrop",
                   "auto_top_attempted": False, "auto_top_succeeded": False,
                   "error": None}]
    assets = {"TTEST": {"drip_amount": "0.05", "native_asset": True,
                        "family": "solana", "blockchain": "Sol", "refill_source": "airdrop"}}
    mock_handler = MagicMock()
    mock_handler.get_faucet_address.return_value = "FakeAddr123"
    mock_handler.drip = AsyncMock(return_value=DripResult(
        success=True, tx_hash="txabc", explorer_url=None, error=None,
        amount="0.05", asset="TTEST"
    ))
    with patch("core.monitor.get_all_assets", return_value=assets):
        with patch("core.monitor.check_all", return_value=low_result):
            with patch("core.monitor.get_handler", return_value=mock_handler):
                with patch("core.monitor.send_alert"):
                    results = run_check()
    assert results[0]["auto_top_attempted"] is True
    assert results[0]["auto_top_succeeded"] is True


def test_run_check_skips_auto_top_when_no_faucet_address():
    """Auto-top is skipped when get_faucet_address() returns None."""
    from core.monitor import run_check
    low_result = [{"asset_id": "TTEST", "status": "LOW", "balance": 0.0,
                   "threshold": 0.1, "refill_source": "airdrop",
                   "auto_top_attempted": False, "auto_top_succeeded": False,
                   "error": None}]
    assets = {"TTEST": {"drip_amount": "0.05", "native_asset": True,
                        "family": "evm", "blockchain": "Eth", "refill_source": "airdrop"}}
    mock_handler = MagicMock()
    mock_handler.get_faucet_address.return_value = None
    with patch("core.monitor.get_all_assets", return_value=assets):
        with patch("core.monitor.check_all", return_value=low_result):
            with patch("core.monitor.get_handler", return_value=mock_handler):
                with patch("core.monitor.send_alert"):
                    results = run_check()
    assert results[0]["auto_top_attempted"] is True
    assert results[0]["auto_top_succeeded"] is False


def test_run_check_auto_top_result_in_alert_payload():
    """Alert payload reflects auto-top outcome."""
    from core.monitor import run_check
    low_result = [{"asset_id": "TTEST", "status": "LOW", "balance": 0.0,
                   "threshold": 0.1, "refill_source": "airdrop",
                   "auto_top_attempted": False, "auto_top_succeeded": False,
                   "error": None}]
    assets = {"TTEST": {"drip_amount": "0.05", "native_asset": True,
                        "family": "solana", "blockchain": "Sol", "refill_source": "airdrop"}}
    mock_handler = MagicMock()
    mock_handler.get_faucet_address.return_value = "Addr"
    mock_handler.drip = AsyncMock(return_value=DripResult(
        success=True, tx_hash="tx", explorer_url=None, error=None,
        amount="0.05", asset="TTEST"
    ))
    with patch("core.monitor.get_all_assets", return_value=assets):
        with patch("core.monitor.check_all", return_value=low_result):
            with patch("core.monitor.get_handler", return_value=mock_handler):
                with patch("core.monitor.send_alert") as mock_alert:
                    run_check()
    _msg, alert_assets = mock_alert.call_args[0]
    assert alert_assets[0]["auto_top_result"] == "succeeded"
```

- [ ] **Step 2: Run new tests — confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_monitor.py::test_run_check_no_alert_when_all_ok -v
```

Expected: `ImportError` or `AttributeError` (run_check not yet defined).

- [ ] **Step 3: Add `run_check` and `_auto_top` to `core/monitor.py`**

Append to `core/monitor.py` (after the existing `check_all` function):

```python
async def _auto_top(asset_id: str, cfg: dict, handler) -> bool:
    """Attempt to drip to the faucet's own address. Returns True if the drip succeeded."""
    faucet_address = handler.get_faucet_address()
    if not faucet_address:
        return False
    drip_amount = cfg.get("drip_amount", "0")
    result = await handler.drip(faucet_address, asset_id, drip_amount)
    return result.success


def run_check(
    threshold_override: float | None = None,
    family: str | None = None,
) -> list[dict]:
    """Full check pass: balance check → auto-top → alert. Returns results list.

    Exits cleanly if no wallets are LOW or ERROR (no alert sent).
    """
    from datetime import datetime, timezone
    from core.alerting import send_alert

    assets = get_all_assets()
    results = check_all(assets, threshold_override, family)

    # Attempt auto-top for LOW wallets that have a refill_source configured
    for r in results:
        if r["status"] == "LOW" and r.get("refill_source"):
            r["auto_top_attempted"] = True
            try:
                handler = get_handler(r["asset_id"])
                r["auto_top_succeeded"] = asyncio.run(
                    _auto_top(r["asset_id"], assets[r["asset_id"]], handler)
                )
            except Exception:
                r["auto_top_succeeded"] = False

    # Send one batched alert if any wallets need attention
    low_or_error = [r for r in results if r["status"] in ("LOW", "ERROR")]
    if low_or_error:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        message = f"[testnet-faucet] {len(low_or_error)} wallet(s) need attention ({ts})"
        alert_assets = [
            {
                "asset_id": r["asset_id"],
                "balance": r["balance"],
                "threshold": r["threshold"],
                "status": r["status"],
                "auto_top_result": (
                    ("succeeded" if r["auto_top_succeeded"] else "failed")
                    if r["auto_top_attempted"]
                    else "N/A"
                ),
                "error": r.get("error"),
            }
            for r in low_or_error
        ]
        send_alert(message, alert_assets)

    return results
```

Also add the import at the top of the file (update the existing imports block):

```python
from core.alerting import send_alert
from core.registry import get_all_assets, get_handler
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_monitor.py -v
```

Expected: all 19 tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 565 tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/monitor.py tests/test_monitor.py
git commit -m "feat: add run_check with auto-top and alert dispatch"
```

---

## Task 7: CLI `check` command

**Files:**
- Modify: `cli.py`
- Create: `tests/test_check_command.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_check_command.py`:

```python
"""Integration tests for the `faucet check` CLI command."""
import pytest
from click.testing import CliRunner
from unittest.mock import patch
from cli import main


def _ok_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "OK",
             "balance": 5.0, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": None}]


def _low_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "LOW",
             "balance": 0.01, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": None}]


def _error_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "ERROR",
             "balance": None, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": "oops"}]


def test_check_exits_0_when_all_ok():
    """Exit code 0 when all wallets are OK."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 0


def test_check_exits_1_when_any_low():
    """Exit code 1 when any wallet is LOW."""
    with patch("cli.run_check", return_value=_low_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 1


def test_check_exits_1_when_any_error():
    """Exit code 1 when any wallet has ERROR status."""
    with patch("cli.run_check", return_value=_error_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 1


def test_check_output_contains_summary():
    """Output includes summary line with counts."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert "1 OK" in result.output
    assert "0 LOW" in result.output
    assert "0 ERROR" in result.output


def test_check_output_shows_asset_row():
    """Output includes a row with the asset ID."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert "TTEST" in result.output


def test_check_threshold_flag_passed_to_run_check():
    """--threshold flag is forwarded to run_check."""
    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        CliRunner().invoke(main, ["check", "--threshold", "5.0"])
    mock_rc.assert_called_once_with(threshold_override=5.0, family=None)


def test_check_family_flag_passed_to_run_check():
    """--family flag is forwarded to run_check."""
    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        CliRunner().invoke(main, ["check", "--family", "evm"])
    mock_rc.assert_called_once_with(threshold_override=None, family="evm")


def test_check_auto_top_succeeded_shown_in_output():
    """When auto-top succeeded, output reflects it."""
    results = [{"asset_id": "TSOL", "blockchain": "Solana", "status": "LOW",
                "balance": 0.0, "threshold": 2.0, "refill_source": "airdrop",
                "auto_top_attempted": True, "auto_top_succeeded": True, "error": None}]
    with patch("cli.run_check", return_value=results):
        result = CliRunner().invoke(main, ["check"])
    assert "succeeded" in result.output
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_check_command.py -v
```

Expected: tests fail (no `check` command in CLI yet, `run_check` not imported).

- [ ] **Step 3: Add `check` command to `cli.py`**

Add the following import at the top of `cli.py` (after existing imports):

```python
from core.monitor import run_check
```

Add the following command to `cli.py` (after the existing `refill` command):

```python
@main.command()
@click.option("--family", help="Filter by chain family")
@click.option("--threshold", type=float, default=None,
              help="Low-balance threshold (default: 2x drip_amount per asset)")
def check(family, threshold):
    """Check faucet balances, auto-top where possible, and alert on LOW/ERROR wallets.

    Exits with code 1 if any wallet is LOW or ERROR — useful for cron alerting.
    """
    import sys
    from rich.table import Table

    results = run_check(threshold_override=threshold, family=family)

    table = Table(title="Balance Check")
    table.add_column("Asset", style="cyan")
    table.add_column("Blockchain")
    table.add_column("Balance")
    table.add_column("Threshold")
    table.add_column("Status")
    table.add_column("Auto-top")

    ok = low = errors = 0
    for r in results:
        if r["status"] == "OK":
            ok += 1
            status_cell = "[green]OK[/green]"
        elif r["status"] == "LOW":
            low += 1
            status_cell = "[yellow]LOW[/yellow]"
        else:
            errors += 1
            status_cell = "[red]ERROR[/red]"

        if r.get("auto_top_attempted"):
            auto_top_cell = (
                "[green]succeeded[/green]" if r["auto_top_succeeded"]
                else "[red]failed[/red]"
            )
        elif r.get("refill_source"):
            auto_top_cell = "[dim]no address[/dim]"
        else:
            auto_top_cell = ""

        balance_str = (
            f"{r['balance']:.4g}" if r["balance"] is not None
            else (r.get("error") or "N/A")
        )
        table.add_row(
            r["asset_id"], r["blockchain"], balance_str,
            f"{r['threshold']:.4g}", status_cell, auto_top_cell,
        )

    console.print(table)
    console.print(f"\nSummary: {ok} OK, {low} LOW, {errors} ERROR")

    if low > 0 or errors > 0:
        sys.exit(1)
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_check_command.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 574 tests pass.

- [ ] **Step 6: Commit**

```bash
git add cli.py tests/test_check_command.py
git commit -m "feat: add faucet check CLI command with exit-code signaling"
```

---

## Task 8: CLI `monitor` command (daemon)

**Files:**
- Modify: `cli.py`
- Modify: `tests/test_check_command.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_check_command.py`:

```python
import time as time_mod


def test_monitor_invalid_interval_shows_error():
    """Invalid --interval value prints error and exits cleanly."""
    result = CliRunner().invoke(main, ["monitor", "--interval", "bad"])
    assert result.exit_code == 0
    assert "Invalid interval" in result.output


def test_monitor_runs_one_pass_and_stops_on_keyboard_interrupt():
    """Monitor runs one check pass, then stops when sleep is interrupted."""
    ok_results = _ok_results()
    call_count = {"n": 0}

    def fake_sleep(secs):
        call_count["n"] += 1
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=ok_results):
        with patch("cli.time.sleep", side_effect=fake_sleep):
            result = CliRunner().invoke(main, ["monitor", "--interval", "1h"])

    assert call_count["n"] == 1
    assert result.exit_code == 0


def test_monitor_output_contains_pass_started():
    """Monitor output includes pass-started messages."""
    def fake_sleep(_):
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=_ok_results()):
        with patch("cli.time.sleep", side_effect=fake_sleep):
            result = CliRunner().invoke(main, ["monitor", "--interval", "1h"])

    assert "Pass started" in result.output


def test_monitor_threshold_flag_forwarded():
    """--threshold is passed to run_check inside monitor loop."""
    def fake_sleep(_):
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        with patch("cli.time.sleep", side_effect=fake_sleep):
            CliRunner().invoke(main, ["monitor", "--interval", "1h", "--threshold", "9.0"])

    mock_rc.assert_called_with(threshold_override=9.0, family=None)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_check_command.py::test_monitor_invalid_interval_shows_error -v
```

Expected: `UsageError` or similar (no `monitor` command yet).

- [ ] **Step 3: Add `monitor` command and `time` import to `cli.py`**

Add `import time` near the top of `cli.py` (after existing imports).

Add the following command to `cli.py` (after the `check` command):

```python
@main.command()
@click.option("--interval", default="1h",
              help="Check interval. Accepts: 30m, 1h, 6h, 1d (default: 1h)")
@click.option("--family", help="Filter by chain family")
@click.option("--threshold", type=float, default=None,
              help="Low-balance threshold (default: 2x drip_amount per asset)")
def monitor(interval, family, threshold):
    """Run continuous balance monitoring. Press Ctrl-C to stop.

    Runs one check immediately, then repeats every --interval. Alerts are
    dispatched via channels configured in ~/.testnet-faucet/alerts.yaml.
    """
    from core.monitor import _parse_interval
    from datetime import datetime, timezone

    try:
        interval_secs = _parse_interval(interval)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    console.print(f"[cyan]Monitor started[/cyan] — checking every {interval}")

    try:
        while True:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            console.print(f"[dim]{ts} Pass started[/dim]")

            results = run_check(threshold_override=threshold, family=family)

            ok = sum(1 for r in results if r["status"] == "OK")
            low = sum(1 for r in results if r["status"] == "LOW")
            errs = sum(1 for r in results if r["status"] == "ERROR")

            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            console.print(
                f"[dim]{ts} Pass complete: {ok} OK, {low} LOW, {errs} ERROR[/dim]"
            )

            time.sleep(interval_secs)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/yellow]")
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_check_command.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 578 tests pass.

- [ ] **Step 6: Commit**

```bash
git add cli.py tests/test_check_command.py
git commit -m "feat: add faucet monitor daemon command"
```

---

## Task 9: `chains.yaml` — add `refill_source` + update `CLAUDE.md`

**Files:**
- Modify: `config/chains.yaml`
- Modify: `CLAUDE.md`

No test changes needed — `check_all` tests already cover `refill_source` via mocked assets. This is a data-only change.

- [ ] **Step 1: Add `refill_source: airdrop` to TSOL in `config/chains.yaml`**

Find the TSOL block (search for `TSOL:`) and add the field:

```yaml
TSOL:
  family: solana
  blockchain: Solana
  network: devnet
  refill_source: airdrop    # <-- add this line
  ...
```

- [ ] **Step 2: Verify chains.yaml is valid YAML**

```bash
.venv/bin/python -c "import yaml; yaml.safe_load(open('config/chains.yaml'))"
```

Expected: no output (no error).

- [ ] **Step 3: Run tests to confirm no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: same count passes.

- [ ] **Step 4: Update `CLAUDE.md`**

Add a new section after the existing `## Phase 7 notes` section:

```markdown
## Monitoring (Phase 8)
- Data directory renamed: `~/.Custodian-faucet/` → `~/.testnet-faucet/`
- Env vars renamed: `Custodian_FAUCET_DB_PATH` → `FAUCET_DB_PATH`, `Custodian_FAUCET_LOG_PATH` → `FAUCET_LOG_PATH`
- Alert config: `~/.testnet-faucet/alerts.yaml` (or `FAUCET_ALERTS_CONFIG` env var); template at `config/alerts.yaml.example`
- New commands: `faucet check` (one-shot, exit 1 on LOW/ERROR), `faucet monitor --interval 1h` (daemon)
- `core/alerting.py` — `send_alert(message, low_assets)` dispatches to log/Slack/webhook/email
- `core/monitor.py` — `check_all()`, `run_check()`, `_parse_interval()`; monkeypatch `core.alerting.ALERTS_CONFIG_PATH` in tests
- Auto-top: set `refill_source: airdrop` (or `external_faucet`) in chains.yaml; handler must implement `get_faucet_address()` returning non-None
- Alert log rotation: `TimedRotatingFileHandler(when="midnight")`, `backup_count` days retained (default 30)
- Cron example: `0 * * * * /path/to/.venv/bin/python -m faucet check >> ~/.testnet-faucet/cron.log 2>&1`
```

- [ ] **Step 5: Commit**

```bash
git add config/chains.yaml config/alerts.yaml.example CLAUDE.md
git commit -m "docs: add refill_source to TSOL and document monitoring setup"
```

---

## Self-Review Checklist (do not skip)

After writing the plan, verify against the spec:

1. **Spec coverage:**
   - Directory rename → Task 1 ✓
   - Alert channels (Slack/email/webhook/log) → Tasks 2–3 ✓
   - Config file + fallback → Task 2 ✓
   - `check_all` balance check + threshold → Task 5 ✓
   - Auto-top via `drip()` + `get_faucet_address()` → Tasks 4, 6 ✓
   - Batched alerts (one per pass) → Task 6 ✓
   - Exit codes 0/1 → Task 7 ✓
   - `faucet check` one-shot → Task 7 ✓
   - `faucet monitor` daemon + interval → Task 8 ✓
   - Graceful shutdown on Ctrl-C → Task 8 ✓
   - Timestamped log entries (ISO-8601 UTC) → Task 2 ✓
   - Daily log rotation + backup_count → Task 2 ✓
   - `refill_source` field in chains.yaml → Task 9 ✓
   - CLAUDE.md update → Task 9 ✓

2. **No placeholders:** All code blocks are complete. No TBDs.

3. **Type consistency:**
   - `run_check()` returns `list[dict]` — same shape as `check_all()` returns, with `auto_top_attempted/succeeded` added in place
   - `send_alert(message: str, low_assets: list[dict])` — same signature used in Task 2 and called in Task 6
   - `_parse_interval(s: str) -> int` — consistent across Tasks 5 and 8
   - `get_faucet_address() -> str | None` — defined in Task 4, used in Task 6 (`_auto_top`)
