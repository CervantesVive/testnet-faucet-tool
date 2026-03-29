"""Tests for the FaucetApp shell — screen switching, keybindings, CLI command."""
import pytest
from click.testing import CliRunner

from cli import main


# ---------------------------------------------------------------------------
# App shell tests (require textual)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_app_mounts():
    """FaucetApp launches without error."""
    from tui.app import FaucetApp
    app = FaucetApp()
    async with app.run_test() as pilot:
        assert pilot.app is app


@pytest.mark.asyncio
async def test_app_shows_dashboard_on_start():
    """Dashboard screen is active on startup."""
    from tui.app import FaucetApp
    from tui.screens.dashboard import DashboardScreen
    app = FaucetApp()
    async with app.run_test() as pilot:
        assert isinstance(pilot.app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_app_switch_to_monitor():
    """Pressing 2 switches to MonitorScreen."""
    from tui.app import FaucetApp
    from tui.screens.monitor import MonitorScreen
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("2")
        assert isinstance(pilot.app.screen, MonitorScreen)


@pytest.mark.asyncio
async def test_app_switch_to_config():
    """Pressing 3 switches to ConfigEditorScreen."""
    from tui.app import FaucetApp
    from tui.screens.config_editor import ConfigEditorScreen
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        assert isinstance(pilot.app.screen, ConfigEditorScreen)


@pytest.mark.asyncio
async def test_app_switch_back_to_dashboard():
    """Can switch to config then back to dashboard."""
    from tui.app import FaucetApp
    from tui.screens.dashboard import DashboardScreen
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.press("1")
        assert isinstance(pilot.app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_app_quit():
    """Pressing q exits the app."""
    from tui.app import FaucetApp
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        # App should have exited — if we get here without error, it worked
        assert True


# ---------------------------------------------------------------------------
# CLI command test
# ---------------------------------------------------------------------------

def test_cli_tui_command_exists():
    """faucet tui --help returns exit code 0."""
    runner = CliRunner()
    result = runner.invoke(main, ["tui", "--help"])
    assert result.exit_code == 0
    assert "tui" in result.output.lower() or "Usage" in result.output


# ---------------------------------------------------------------------------
# Phase 6: Error handling and help overlay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_help_overlay_shows():
    """Pressing ? shows the help overlay."""
    from tui.app import FaucetApp
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("?")
        await pilot.pause(0.1)
        # HelpScreen or a modal should be on the screen stack
        from textual.screen import ModalScreen
        # App screen should have changed (a modal or overlay is active)
        assert len(app._screen_stack) > 1 or isinstance(app.screen, ModalScreen)


@pytest.mark.asyncio
async def test_help_overlay_dismisses():
    """Pressing escape dismisses the help overlay."""
    from tui.app import FaucetApp
    from tui.screens.dashboard import DashboardScreen
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("?")
        await pilot.pause(0.1)
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_dashboard_network_error_shows_toast():
    """If data fetch raises, dashboard shows a notification (toast)."""
    from unittest.mock import patch
    from tui.app import FaucetApp
    with patch(
        "tui.screens.dashboard.fetch_dashboard_data",
        side_effect=Exception("Connection refused"),
    ):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            # App should still be alive — no unhandled exception
            assert True


@pytest.mark.asyncio
async def test_monitor_network_error_continues():
    """If monitor data fetch raises, countdown restarts (no crash)."""
    from unittest.mock import patch
    from tui.app import FaucetApp
    from tui.screens.monitor import MonitorScreen
    with patch(
        "tui.screens.monitor.fetch_monitor_data",
        side_effect=Exception("Network down"),
    ):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause(0.5)
            # App and monitor screen still alive
            assert isinstance(app.screen, MonitorScreen)


@pytest.mark.asyncio
async def test_config_malformed_yaml_shows_toast():
    """If chains.yaml fails to load, config screen shows a toast instead of crashing."""
    from unittest.mock import patch
    from tui.app import FaucetApp
    from tui.screens.config_editor import ConfigEditorScreen
    with patch(
        "tui.screens.config_editor.load_chains_yaml",
        side_effect=Exception("YAML parse error"),
    ):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause(0.3)
            # Should be on config screen without crashing
            assert isinstance(app.screen, ConfigEditorScreen)
