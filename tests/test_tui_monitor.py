"""Tests for CountdownWidget and MonitorScreen."""
import pytest
from unittest.mock import patch

from textual.app import App, ComposeResult

from tui.app import FaucetApp
from tui.screens.monitor import MonitorScreen
from tui.widgets.balance_table import BalanceTable
from tui.widgets.countdown import CountdownWidget


MOCK_RESULTS = [
    {
        "asset_id": "TETH",
        "family": "evm",
        "blockchain": "Ethereum",
        "balance": 1.5,
        "status": "OK",
        "error": None,
        "refill_source": None,
        "auto_top_attempted": False,
        "auto_top_succeeded": False,
        "threshold": 0.1,
    },
]


class _CountdownApp(App):
    def compose(self) -> ComposeResult:
        yield CountdownWidget(id="countdown")


@pytest.mark.asyncio
async def test_monitor_initial_check_on_mount():
    """MonitorScreen fetches data immediately on mount."""
    call_count = 0

    def mock_fetch(threshold=None, family=None):
        nonlocal call_count
        call_count += 1
        return MOCK_RESULTS

    with patch("tui.screens.monitor.fetch_monitor_data", side_effect=mock_fetch):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause(0.5)
    assert call_count >= 1


@pytest.mark.asyncio
async def test_countdown_ticks_down():
    """CountdownWidget starts at N and decrements each second."""
    app = _CountdownApp()
    async with app.run_test() as pilot:
        countdown = app.query_one(CountdownWidget)
        countdown.start(5)
        await pilot.pause()
        text1 = str(countdown.content)
        await pilot.pause(1.1)
        text2 = str(countdown.content)
        assert text1 != text2


@pytest.mark.asyncio
async def test_countdown_fires_message():
    """CountdownWidget posts CountdownFinished when reaching zero."""
    from tui.widgets.countdown import CountdownFinished
    received = []

    class _App(App):
        def compose(self) -> ComposeResult:
            yield CountdownWidget(id="countdown")

        def on_countdown_finished(self, event: CountdownFinished) -> None:
            received.append(True)

    app = _App()
    async with app.run_test() as pilot:
        countdown = app.query_one(CountdownWidget)
        countdown.start(1)
        await pilot.pause(1.5)
    assert len(received) >= 1


@pytest.mark.asyncio
async def test_monitor_check_triggers_on_countdown():
    """MonitorScreen triggers a new check when countdown expires."""
    call_count = 0

    def mock_fetch(threshold=None, family=None):
        nonlocal call_count
        call_count += 1
        return MOCK_RESULTS

    with patch("tui.screens.monitor.fetch_monitor_data", side_effect=mock_fetch), \
         patch("tui.screens.monitor.DEFAULT_INTERVAL", 1):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            # Wait for initial check + countdown + next check
            await pilot.pause(3.0)
    assert call_count >= 2


@pytest.mark.asyncio
async def test_monitor_pass_counter_increments():
    """Pass counter increments each time a check completes."""
    with patch("tui.screens.monitor.fetch_monitor_data", return_value=MOCK_RESULTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause(0.5)
            screen = app.screen
            assert isinstance(screen, MonitorScreen)
            assert screen.pass_count >= 1


@pytest.mark.asyncio
async def test_monitor_results_update_table():
    """Check results are reflected in the BalanceTable."""
    with patch("tui.screens.monitor.fetch_monitor_data", return_value=MOCK_RESULTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause(0.5)
            table = app.screen.query_one(BalanceTable)
            assert table.row_count == 1
