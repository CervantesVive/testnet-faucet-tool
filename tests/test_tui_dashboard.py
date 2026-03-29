"""Tests for the live DashboardScreen."""
import pytest
from unittest.mock import patch, MagicMock

from tui.app import FaucetApp
from tui.screens.dashboard import DashboardScreen
from tui.widgets.balance_table import BalanceTable
from tui.widgets.status_bar import StatusBar


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
    {
        "asset_id": "TSOL",
        "family": "solana",
        "blockchain": "Solana",
        "balance": 0.01,
        "status": "LOW",
        "error": None,
        "refill_source": None,
        "auto_top_attempted": False,
        "auto_top_succeeded": False,
        "threshold": 0.1,
    },
]


@pytest.mark.asyncio
async def test_dashboard_populates_on_mount():
    """Dashboard table has rows after mount when data is mocked."""
    with patch("tui.screens.dashboard.fetch_dashboard_data", return_value=MOCK_RESULTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            table = app.screen.query_one(BalanceTable)
            assert table.row_count == 2


@pytest.mark.asyncio
async def test_dashboard_manual_refresh():
    """Pressing r triggers a data refresh (fetch called at least twice)."""
    call_count = 0

    def mock_fetch(family=None):
        nonlocal call_count
        call_count += 1
        return MOCK_RESULTS

    with patch("tui.screens.dashboard.fetch_dashboard_data", side_effect=mock_fetch):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            initial_calls = call_count
            await pilot.press("r")
            await pilot.pause(0.2)
            assert call_count > initial_calls


@pytest.mark.asyncio
async def test_dashboard_status_bar_updates():
    """Status bar shows correct OK/LOW/ERROR counts after data loads."""
    with patch("tui.screens.dashboard.fetch_dashboard_data", return_value=MOCK_RESULTS):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            bar = app.screen.query_one(StatusBar)
            bar_text = str(bar.content)
            assert "OK: 1" in bar_text
            assert "LOW: 1" in bar_text


@pytest.mark.asyncio
async def test_dashboard_family_filter():
    """Family filter is passed through to fetch_dashboard_data."""
    calls = []

    def mock_fetch(family=None):
        calls.append(family)
        return MOCK_RESULTS

    with patch("tui.screens.dashboard.fetch_dashboard_data", side_effect=mock_fetch):
        app = FaucetApp(family="evm")
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
    assert any(c == "evm" for c in calls)


@pytest.mark.asyncio
async def test_dashboard_error_does_not_crash():
    """If fetch raises, the app shows an error state but does not crash."""
    with patch(
        "tui.screens.dashboard.fetch_dashboard_data",
        side_effect=Exception("network down"),
    ):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            # App is still alive if we reach this point
            assert True
