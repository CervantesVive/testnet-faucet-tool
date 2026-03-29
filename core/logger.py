import json
import os
from datetime import datetime, timezone
from pathlib import Path
from handlers.base import DripResult

LOG_PATH = Path(os.environ.get("FAUCET_LOG_PATH", Path.home() / ".testnet-faucet" / "history.log"))


def log_drip(address: str, result: DripResult) -> None:
    """Append a drip result as a JSON line to the history log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": result.asset,
        "address": address,
        "amount": result.amount,
        "success": result.success,
        "tx_hash": result.tx_hash,
        "error": result.error,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_history(limit: int = 20) -> list[dict]:
    """Read the last N entries from the history log."""
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text().strip().split("\n")
    lines = [l for l in lines if l.strip()]  # skip empty
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
