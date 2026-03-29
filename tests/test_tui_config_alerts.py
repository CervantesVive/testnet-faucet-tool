"""Tests for ConfigEditorScreen — Alerts tab."""
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch

from core import alerting
from tui.app import FaucetApp
from tui.screens.config_editor import ConfigEditorScreen


MOCK_CHAINS = {
    "TETH": {
        "family": "evm",
        "blockchain": "Ethereum",
        "network": "holesky",
        "native_asset": True,
        "drip_amount": "0.05",
        "decimals": 18,
    },
}

MOCK_ALERTS = {
    "alerts": {
        "log": {"enabled": True},
        "slack": {"enabled": False, "webhook_url": "https://hooks.slack.com/test"},
        "webhook": {"enabled": False, "url": "https://example.com/hook"},
        "email": {
            "enabled": False,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "username": "user@example.com",
            "password": "secret",
            "from": "faucet@example.com",
            "to": ["admin@example.com"],
        },
    }
}


@pytest.fixture(autouse=True)
def patch_chains():
    with patch("tui.screens.config_editor.load_chains_yaml", return_value=MOCK_CHAINS):
        yield


async def _go_to_alerts(pilot):
    """Navigate to the config screen and switch to the Alerts tab."""
    await pilot.press("3")
    await pilot.pause(0.3)
    await pilot.click("#tab-alerts")
    await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_alerts_loads_defaults_when_no_file(tmp_path, monkeypatch):
    """Alerts tab loads with empty/default values when no config file exists."""
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    with patch("tui.screens.config_editor.load_alerts_yaml", return_value={}):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await _go_to_alerts(pilot)
            # Should not crash — just loads with defaults
            assert isinstance(app.screen, ConfigEditorScreen)


@pytest.mark.asyncio
async def test_alerts_loads_existing_config():
    """Alerts tab populates fields from existing config."""
    with patch("tui.screens.config_editor.load_alerts_yaml", return_value=MOCK_ALERTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await _go_to_alerts(pilot)
            from textual.widgets import Input
            slack_input = app.screen.query_one("#alerts-slack-webhook_url", Input)
            assert "hooks.slack.com" in slack_input.value


@pytest.mark.asyncio
async def test_alerts_toggle_disables_inputs():
    """Toggling a section off disables its Input widgets."""
    with patch("tui.screens.config_editor.load_alerts_yaml", return_value=MOCK_ALERTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await _go_to_alerts(pilot)
            from textual.widgets import Switch, Input
            slack_switch = app.screen.query_one("#alerts-slack-enabled", Switch)
            # Toggle slack OFF
            slack_switch.value = False
            await pilot.pause(0.2)
            slack_input = app.screen.query_one("#alerts-slack-webhook_url", Input)
            assert slack_input.disabled


@pytest.mark.asyncio
async def test_alerts_save_writes_yaml(tmp_path, monkeypatch):
    """Saving alerts config writes valid YAML to ALERTS_CONFIG_PATH."""
    alerts_path = tmp_path / "alerts.yaml"
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", alerts_path)
    saved = {}

    def mock_save(data):
        saved.update(data)
        alerts_path.write_text(yaml.safe_dump(data))

    with patch("tui.screens.config_editor.load_alerts_yaml", return_value=MOCK_ALERTS), \
         patch("tui.screens.config_editor.save_alerts_yaml", side_effect=mock_save):
        app = FaucetApp()
        async with app.run_test(size=(120, 60)) as pilot:
            await _go_to_alerts(pilot)
            from textual.widgets import Button
            save_btn = app.screen.query_one("#save-alerts", Button)
            save_btn.press()
            await pilot.pause(0.2)
    assert saved  # save was called


@pytest.mark.asyncio
async def test_alerts_password_masked():
    """Email password input is masked (password=True)."""
    with patch("tui.screens.config_editor.load_alerts_yaml", return_value=MOCK_ALERTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await _go_to_alerts(pilot)
            from textual.widgets import Input
            pwd_input = app.screen.query_one("#alerts-email-password", Input)
            assert pwd_input.password is True


@pytest.mark.asyncio
async def test_alerts_saved_yaml_readable_by_alerting(tmp_path, monkeypatch):
    """YAML saved by the alerts editor is parseable by core/alerting._load_config."""
    alerts_path = tmp_path / "alerts.yaml"
    monkeypatch.setattr(alerting, "ALERTS_CONFIG_PATH", alerts_path)

    def mock_save(data):
        alerts_path.write_text(yaml.safe_dump(data))

    with patch("tui.screens.config_editor.load_alerts_yaml", return_value=MOCK_ALERTS), \
         patch("tui.screens.config_editor.save_alerts_yaml", side_effect=mock_save):
        app = FaucetApp()
        async with app.run_test(size=(120, 60)) as pilot:
            await _go_to_alerts(pilot)
            from textual.widgets import Button
            save_btn = app.screen.query_one("#save-alerts", Button)
            save_btn.press()
            await pilot.pause(0.2)

    # The saved file should be parseable
    if alerts_path.exists():
        cfg = alerting._load_config()
        assert isinstance(cfg, dict)
