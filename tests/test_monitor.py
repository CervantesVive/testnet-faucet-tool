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
