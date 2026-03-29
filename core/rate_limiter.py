import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(os.environ.get("FAUCET_DB_PATH", Path.home() / ".testnet-faucet" / "rate_limits.db"))

# Default TTL (seconds) per source type
DEFAULT_TTLS = {
    "self_funded": 300,       # 5 minutes between drips from our own wallet
    "external_faucet": 86400, # 24 hours for external faucet APIs (typical limit)
    "airdrop": 60,            # 1 minute for native airdrop APIs (e.g. Solana)
}


def _get_db() -> sqlite3.Connection:
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise RuntimeError(
            f"Cannot create rate limit database directory {DB_PATH.parent}: {e}\n"
            f"Set Custodian_FAUCET_DB_PATH environment variable to override."
        ) from e

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            key TEXT PRIMARY KEY,
            last_drip_ts REAL NOT NULL,
            source_type TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _make_key(asset_id: str, address: str) -> str:
    return f"{asset_id}:{address}"


def check_rate_limit(asset_id: str, address: str, source_type: str = "self_funded") -> tuple[bool, float]:
    """
    Check if a drip is allowed.
    Returns (allowed: bool, seconds_remaining: float).
    seconds_remaining is 0.0 if allowed.
    """
    ttl = DEFAULT_TTLS.get(source_type, DEFAULT_TTLS["self_funded"])
    key = _make_key(asset_id, address)
    now = datetime.now(timezone.utc).timestamp()

    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT last_drip_ts FROM rate_limits WHERE key = ?", (key,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return True, 0.0
    elapsed = now - row[0]
    if elapsed >= ttl:
        return True, 0.0
    return False, ttl - elapsed


def record_drip(asset_id: str, address: str, source_type: str = "self_funded") -> None:
    """Record a successful drip for rate limiting purposes."""
    key = _make_key(asset_id, address)
    now = datetime.now(timezone.utc).timestamp()

    conn = _get_db()
    try:
        conn.execute("""
            INSERT INTO rate_limits (key, last_drip_ts, source_type)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET last_drip_ts = excluded.last_drip_ts, source_type = excluded.source_type
        """, (key, now, source_type))
        conn.commit()
    finally:
        conn.close()


def get_ttl(source_type: str) -> int:
    """Return TTL in seconds for the given source type."""
    return DEFAULT_TTLS.get(source_type, DEFAULT_TTLS["self_funded"])
