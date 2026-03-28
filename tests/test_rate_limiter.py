import pytest
import time
from pathlib import Path
from core import rate_limiter


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(rate_limiter, "DB_PATH", tmp_path / "test_rate_limits.db")
    yield


def test_first_drip_is_allowed():
    allowed, remaining = rate_limiter.check_rate_limit("HTETH", "0xabc", "self_funded")
    assert allowed
    assert remaining == 0.0


def test_rate_limited_after_drip():
    rate_limiter.record_drip("HTETH", "0xabc", "self_funded")
    allowed, remaining = rate_limiter.check_rate_limit("HTETH", "0xabc", "self_funded")
    assert not allowed
    assert remaining > 0


def test_different_address_not_rate_limited():
    rate_limiter.record_drip("HTETH", "0xabc", "self_funded")
    allowed, _ = rate_limiter.check_rate_limit("HTETH", "0xdef", "self_funded")
    assert allowed


def test_different_asset_not_rate_limited():
    rate_limiter.record_drip("HTETH", "0xabc", "self_funded")
    allowed, _ = rate_limiter.check_rate_limit("TSOL", "0xabc", "self_funded")
    assert allowed


def test_external_faucet_ttl_is_24h():
    assert rate_limiter.get_ttl("external_faucet") == 86400


def test_airdrop_ttl_is_1min():
    assert rate_limiter.get_ttl("airdrop") == 60


def test_record_drip_updates_on_repeat():
    rate_limiter.record_drip("HTETH", "0xabc", "self_funded")
    allowed_1, remaining_1 = rate_limiter.check_rate_limit("HTETH", "0xabc", "self_funded")
    assert not allowed_1
    # Update the record — simulate a new drip attempt
    rate_limiter.record_drip("HTETH", "0xabc", "external_faucet")
    # Source type changed, remaining should still indicate blocked
    allowed_2, _ = rate_limiter.check_rate_limit("HTETH", "0xabc", "external_faucet")
    assert not allowed_2


def test_unknown_source_type_defaults_to_self_funded():
    ttl = rate_limiter.get_ttl("unknown_source")
    assert ttl == rate_limiter.DEFAULT_TTLS["self_funded"]
    assert ttl == 300
