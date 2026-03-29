"""Balance check and auto-top logic for the testnet faucet monitor."""
import asyncio
import re
from datetime import datetime, timezone

from core.alerting import send_alert
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
