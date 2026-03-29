"""Tests for tui/data.py — thread-safe data wrappers."""
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import core.registry as reg
from core import alerting
import tui.data as data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RESULT = [
    {
        "asset_id": "TTEST",
        "blockchain": "TestChain",
        "family": "evm",
        "threshold": 0.1,
        "balance": 1.0,
        "status": "OK",
        "error": None,
        "refill_source": None,
        "auto_top_attempted": False,
        "auto_top_succeeded": False,
    }
]

SAMPLE_ASSETS = {
    "TTEST": {
        "family": "evm",
        "blockchain": "TestChain",
        "network": "holesky",
        "native_asset": True,
        "drip_amount": "0.05",
        "decimals": 18,
    }
}


@pytest.fixture(autouse=True)
def reset_registry():
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()
    yield
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()


# ---------------------------------------------------------------------------
# fetch_dashboard_data
# ---------------------------------------------------------------------------

def test_fetch_dashboard_data_calls_check_all():
    with patch("tui.data.check_all", return_value=SAMPLE_RESULT) as mock_check, \
         patch("tui.data.get_all_assets", return_value=SAMPLE_ASSETS):
        result = data.fetch_dashboard_data()
    mock_check.assert_called_once_with(SAMPLE_ASSETS, family=None)
    assert result == SAMPLE_RESULT


def test_fetch_dashboard_data_family_filter():
    with patch("tui.data.check_all", return_value=SAMPLE_RESULT) as mock_check, \
         patch("tui.data.get_all_assets", return_value=SAMPLE_ASSETS):
        data.fetch_dashboard_data(family="evm")
    mock_check.assert_called_once_with(SAMPLE_ASSETS, family="evm")


# ---------------------------------------------------------------------------
# fetch_monitor_data
# ---------------------------------------------------------------------------

def test_fetch_monitor_data_calls_run_check():
    with patch("tui.data.run_check", return_value=SAMPLE_RESULT) as mock_run:
        result = data.fetch_monitor_data(threshold=0.5, family="evm")
    mock_run.assert_called_once_with(0.5, "evm")
    assert result == SAMPLE_RESULT


def test_fetch_monitor_data_defaults():
    with patch("tui.data.run_check", return_value=SAMPLE_RESULT) as mock_run:
        data.fetch_monitor_data()
    mock_run.assert_called_once_with(None, None)


# ---------------------------------------------------------------------------
# load_chains_yaml / save_chains_yaml
# ---------------------------------------------------------------------------

def test_load_chains_yaml_returns_dict(tmp_path, monkeypatch):
    yaml_path = tmp_path / "chains.yaml"
    yaml_path.write_text("TTEST:\n  family: evm\n")
    monkeypatch.setattr("core.registry._get_chains_yaml_path", lambda: yaml_path)
    result = data.load_chains_yaml()
    assert result == {"TTEST": {"family": "evm"}}


def test_save_chains_yaml_roundtrip(tmp_path, monkeypatch):
    yaml_path = tmp_path / "chains.yaml"
    monkeypatch.setattr("core.registry._get_chains_yaml_path", lambda: yaml_path)
    payload = {"TTEST": {"family": "evm", "drip_amount": "0.05"}}
    data.save_chains_yaml(payload)
    result = data.load_chains_yaml()
    assert result == payload


def test_save_chains_yaml_invalidates_cache(tmp_path, monkeypatch):
    yaml_path = tmp_path / "chains.yaml"
    monkeypatch.setattr("core.registry._get_chains_yaml_path", lambda: yaml_path)
    reg._REGISTRY = {"stale": {}}
    reg._HANDLER_CACHE["stale"] = MagicMock()
    data.save_chains_yaml({"fresh": {"family": "evm"}})
    assert reg._REGISTRY is None
    assert reg._HANDLER_CACHE == {}


# ---------------------------------------------------------------------------
# load_alerts_yaml / save_alerts_yaml
# ---------------------------------------------------------------------------

def test_load_alerts_yaml_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    result = data.load_alerts_yaml()
    assert result == {}


def test_load_alerts_yaml_existing(tmp_path, monkeypatch):
    alerts_path = tmp_path / "alerts.yaml"
    alerts_path.write_text("alerts:\n  log:\n    enabled: true\n")
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", alerts_path)
    result = data.load_alerts_yaml()
    assert result == {"alerts": {"log": {"enabled": True}}}


def test_save_alerts_yaml_creates_dir(tmp_path, monkeypatch):
    nested = tmp_path / "subdir" / "alerts.yaml"
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", nested)
    data.save_alerts_yaml({"alerts": {}})
    assert nested.exists()


def test_save_alerts_yaml_roundtrip(tmp_path, monkeypatch):
    alerts_path = tmp_path / "alerts.yaml"
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", alerts_path)
    payload = {"alerts": {"slack": {"enabled": False, "webhook_url": "https://x"}}}
    data.save_alerts_yaml(payload)
    result = data.load_alerts_yaml()
    assert result == payload
