"""Thread-safe data wrappers for the TUI.

All functions here are designed to run inside Textual @work(thread=True) workers,
where each thread has its own event loop context. This avoids nesting asyncio
event loops (check_all/run_check call asyncio.run() internally).
"""
import yaml
from pathlib import Path

from core import alerting
import core.registry as registry
from core.monitor import check_all, run_check
from core.registry import get_all_assets


# ---------------------------------------------------------------------------
# Family-specific extra fields beyond REQUIRED_FIELDS
# ---------------------------------------------------------------------------

FAMILY_EXTRA_FIELDS: dict[str, list[str]] = {
    "cosmos": ["denom", "bech32_prefix"],
    "solana": ["mint_address"],
    "evm": ["contract_address"],
    "hedera": ["token_id"],
}


# ---------------------------------------------------------------------------
# Balance check helpers
# ---------------------------------------------------------------------------

def fetch_dashboard_data(family: str | None = None) -> list[dict]:
    """Return check_all results for all native assets.

    Designed to run inside @work(thread=True) — asyncio.run() is safe here.
    """
    assets = get_all_assets()
    return check_all(assets, family=family)


def fetch_monitor_data(
    threshold: float | None = None,
    family: str | None = None,
) -> list[dict]:
    """Return run_check results (includes auto-top and alerts).

    Designed to run inside @work(thread=True) — asyncio.run() is safe here.
    """
    return run_check(threshold, family)


# ---------------------------------------------------------------------------
# chains.yaml I/O
# ---------------------------------------------------------------------------

def load_chains_yaml() -> dict:
    """Load the asset registry from chains.yaml as a raw dict."""
    path = registry._get_chains_yaml_path()
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_chains_yaml(data: dict) -> None:
    """Write data to chains.yaml and invalidate the in-memory registry cache.

    NOTE: Comments in chains.yaml will be lost — callers should warn users.
    """
    path = registry._get_chains_yaml_path()
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    # Invalidate stale cache so next registry access reflects the new file.
    registry._REGISTRY = None
    registry._HANDLER_CACHE.clear()


# ---------------------------------------------------------------------------
# alerts.yaml I/O
# ---------------------------------------------------------------------------

def load_alerts_yaml() -> dict:
    """Load the alerts configuration. Returns empty dict if file does not exist."""
    path = alerting.ALERTS_CONFIG_PATH
    if not Path(path).exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_alerts_yaml(data: dict) -> None:
    """Write data to ALERTS_CONFIG_PATH, creating parent directories as needed."""
    path = Path(alerting.ALERTS_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
