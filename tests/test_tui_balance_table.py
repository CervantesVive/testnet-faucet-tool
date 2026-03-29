"""Tests for the BalanceTable widget."""
import pytest
from textual.app import App, ComposeResult

from tui.widgets.balance_table import BalanceTable


SAMPLE_RESULTS = [
    {
        "asset_id": "TETH",
        "family": "evm",
        "blockchain": "Ethereum",
        "balance": 1.5,
        "status": "OK",
        "error": None,
    },
    {
        "asset_id": "TSOL",
        "family": "solana",
        "blockchain": "Solana",
        "balance": 0.04,
        "status": "LOW",
        "error": None,
    },
    {
        "asset_id": "TATOM",
        "family": "cosmos",
        "blockchain": "Cosmos Hub",
        "balance": None,
        "status": "ERROR",
        "error": "connection refused",
    },
]


class _TestApp(App):
    def compose(self) -> ComposeResult:
        yield BalanceTable()


@pytest.mark.asyncio
async def test_balance_table_initial_populate():
    """update_from_results with 3 items creates 3 rows."""
    app = _TestApp()
    async with app.run_test() as pilot:
        table = app.query_one(BalanceTable)
        table.update_from_results(SAMPLE_RESULTS)
        await pilot.pause()
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_balance_table_status_colors():
    """Status column text reflects OK/LOW/ERROR values."""
    app = _TestApp()
    async with app.run_test() as pilot:
        table = app.query_one(BalanceTable)
        table.update_from_results(SAMPLE_RESULTS)
        await pilot.pause()
        # Verify the rendered cell values contain status text
        ok_cell = table.get_cell("TETH", "status")
        low_cell = table.get_cell("TSOL", "status")
        err_cell = table.get_cell("TATOM", "status")
        assert "OK" in str(ok_cell)
        assert "LOW" in str(low_cell)
        assert "ERROR" in str(err_cell)


@pytest.mark.asyncio
async def test_balance_table_update_preserves_rows():
    """Calling update_from_results twice keeps the same row count (uses update_cell)."""
    app = _TestApp()
    async with app.run_test() as pilot:
        table = app.query_one(BalanceTable)
        table.update_from_results(SAMPLE_RESULTS)
        await pilot.pause()
        table.update_from_results(SAMPLE_RESULTS)
        await pilot.pause()
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_balance_table_balance_formatting():
    """None balance shows 'N/A'; numeric balance is formatted."""
    app = _TestApp()
    async with app.run_test() as pilot:
        table = app.query_one(BalanceTable)
        table.update_from_results(SAMPLE_RESULTS)
        await pilot.pause()
        none_cell = table.get_cell("TATOM", "balance")
        numeric_cell = table.get_cell("TETH", "balance")
        assert "N/A" in str(none_cell)
        assert "1.5" in str(numeric_cell) or "1.50" in str(numeric_cell)


@pytest.mark.asyncio
async def test_balance_table_empty_results():
    """Empty results list does not crash."""
    app = _TestApp()
    async with app.run_test() as pilot:
        table = app.query_one(BalanceTable)
        table.update_from_results([])
        await pilot.pause()
        assert table.row_count == 0
