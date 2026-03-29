# Wallet Monitor Design

**Date:** 2026-03-28
**Status:** Approved

## Overview

Automated balance monitoring for testnet faucet wallets. On a schedule, check every wallet balance against a threshold. Where a chain supports it, auto-request a top-up from the external faucet. For chains that require manual funding, dispatch alerts via configured channels (Slack, email, webhook, log file).

---

## Architecture

### New files

| File | Purpose |
|------|---------|
| `core/alerting.py` | Alert dispatcher — loads config, fans out to enabled channels |
| `core/monitor.py` | Check-and-act logic — balance check, auto-top, alert dispatch |
| `config/alerts.yaml.example` | Committed template showing full alert config schema |

### New CLI commands (added to `cli.py`)

| Command | Behaviour |
|---------|-----------|
| `faucet check [--family F] [--threshold N]` | One-shot pass: check balances, auto-top where possible, alert for the rest. Exit 0 if all OK, exit 1 if any LOW/ERROR. |
| `faucet monitor [--interval 1h] [--family F] [--threshold N]` | Daemon: runs `check` on a loop, sleeping between passes. |

`check` is the building block — `monitor` wraps it. Cron users only need `check`.

### Directory rename

All data files move from `~/.Custodian-faucet/` to `~/.testnet-faucet/`. The env var `Custodian_FAUCET_DB_PATH` is renamed to `FAUCET_DB_PATH`. Existing files in the old location are not migrated automatically — the new path is used on first run.

---

## Alert Configuration

Config file: `~/.testnet-faucet/alerts.yaml`
Override path: `FAUCET_ALERTS_CONFIG` environment variable
Fallback: if the file does not exist, log-only alerting is used (no crash).

```yaml
# ~/.testnet-faucet/alerts.yaml
alerts:
  log:
    enabled: true
    path: ~/.testnet-faucet/alerts.log
    backup_count: 30        # days of rotated logs to retain

  slack:
    enabled: true
    webhook_url: https://hooks.slack.com/services/...

  webhook:
    enabled: true
    url: https://your-service.example.com/hook
    method: POST            # default POST
    headers:                # optional
      Authorization: Bearer token123

  email:
    enabled: true
    smtp_host: smtp.example.com
    smtp_port: 587
    username: faucet@example.com
    password: secret
    from: faucet@example.com
    to:
      - ops@example.com
```

`core/alerting.py` exposes a single function:

```python
def send_alert(message: str, low_assets: list[dict]) -> None
```

Each channel is independently enabled. Failures in one channel (e.g., SMTP timeout) are logged but do not prevent other channels from firing.

---

## Check-and-Act Logic (`core/monitor.py`)

Per asset on each pass:

1. Call `handler.get_faucet_balance()`
2. Compare first balance value against threshold (`2× drip_amount` by default, globally overridable via `--threshold`)
3. **OK** — no action
4. **LOW** — attempt auto-top if `refill_source` is set in `chains.yaml`; otherwise queue for alert
5. **ERROR** (balance unreadable or handler exception) — queue for alert immediately

### Auto-top eligibility

Determined by an optional `refill_source` field in `chains.yaml` per asset:

```yaml
TSOL:
  family: solana
  refill_source: airdrop    # or: external_faucet
  ...
```

If absent, the asset requires manual funding. Auto-top reuses the handler's existing `drip()` method, calling it with the faucet's own address as the recipient. `core/monitor.py` calls `handler.drip()` directly — it does not go through `check_rate_limit` / `record_drip`, since self-refill is not a user-facing drip and should not consume rate limit quota.

### Alert batching

One summary alert is sent per `check` pass — not one per asset. The message lists all LOW/ERROR assets with balance, threshold, and auto-top outcome (attempted / succeeded / not available).

Example alert body:
```
[testnet-faucet] 2 wallets need attention (2026-03-28T14:00:00Z)

LOW — auto-top attempted:
  TSOL: balance 0.0 / threshold 0.1 — airdrop requested ✓

LOW — manual refill required:
  HTETH: balance 0.02 / threshold 0.10 — fund at https://holesky.etherscan.io
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All wallets OK |
| 1 | One or more LOW or ERROR |

---

## Monitor Daemon (`faucet monitor`)

```
faucet monitor [--interval 1h] [--family evm] [--threshold 2.0]
```

- `--interval` accepts human-friendly strings: `30m`, `1h`, `6h`, `1d` (default: `1h`)
- Runs one check immediately on startup, then sleeps between passes
- Logs pass start/end to the alerts log for audit trail even when all wallets are OK
- Graceful shutdown on `SIGINT` / `SIGTERM` — finishes current pass then exits
- Uses `time.sleep()` — no external scheduling library required

### Cron example

```cron
0 * * * *  /path/to/.venv/bin/python -m faucet check >> ~/.testnet-faucet/cron.log 2>&1
```

---

## Logging

All log entries from `core/alerting.py`:

- **Format:** `2026-03-28T14:32:01Z [INFO] Monitor pass completed: 2 OK, 1 LOW, 0 ERROR`
- **Timestamps:** ISO-8601 UTC
- **Rotation:** `TimedRotatingFileHandler(when="midnight")` — rotates at midnight, suffixes rotated files `alerts.log.2026-03-27`
- **Retention:** `backup_count` days (default 30, configurable in `alerts.yaml`)

Pass lifecycle entries logged regardless of alert channel config:
- `Monitor pass started`
- `Monitor pass completed: N OK, N LOW, N ERROR`

---

## Testing

Follow existing project conventions:

- Unit tests for `core/alerting.py`: mock each channel's outbound call (SMTP, HTTP), assert correct payload shape and that channel failures don't propagate
- Unit tests for `core/monitor.py`: mock `get_faucet_balance()` and `drip()`, verify correct branching (OK / LOW-auto-top / LOW-alert / ERROR)
- Integration tests for `check` and `monitor` CLI commands via `CliRunner`; monkeypatch `DB_PATH`, `LOG_PATH`, and the new `ALERTS_CONFIG_PATH` to `tmp_path`
- `monitor` daemon tested by injecting a mock interval and a stop condition after N passes

---

## Files Changed Summary

| File | Change |
|------|--------|
| `core/alerting.py` | New |
| `core/monitor.py` | New |
| `core/rate_limiter.py` | Rename `~/.Custodian-faucet/` → `~/.testnet-faucet/`, `Custodian_FAUCET_DB_PATH` → `FAUCET_DB_PATH` |
| `core/logger.py` | Rename `~/.Custodian-faucet/` → `~/.testnet-faucet/` |
| `cli.py` | Add `check` and `monitor` commands |
| `config/alerts.yaml.example` | New |
| `config/chains.yaml` | Add optional `refill_source` field to eligible assets |
| `CLAUDE.md` | Document new data dir, env vars, and monitoring commands |
