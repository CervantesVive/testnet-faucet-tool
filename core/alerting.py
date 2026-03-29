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
ALERTS_LOG_PATH = Path(
    os.environ.get("FAUCET_ALERTS_LOG", Path.home() / ".testnet-faucet" / "alerts.log")
)


def _load_config() -> dict:
    """Load alerts.yaml. Returns empty dict if the file does not exist."""
    if not ALERTS_CONFIG_PATH.exists():
        return {}
    with open(ALERTS_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def _get_alert_logger(log_cfg: dict) -> logging.Logger:
    """Return (and lazily configure) the rotating file logger."""
    path_str = log_cfg.get("path", str(ALERTS_LOG_PATH))
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
