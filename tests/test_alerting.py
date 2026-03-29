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
