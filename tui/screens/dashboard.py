"""DashboardScreen — live balance table with 30s auto-refresh."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual._work_decorator import work

from tui.data import fetch_dashboard_data
from tui.widgets.balance_table import BalanceTable
from tui.widgets.status_bar import StatusBar


class DashboardScreen(Screen):
    """Live balance dashboard — auto-refreshes every 30 seconds."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield BalanceTable(id="balance-table")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self._do_refresh()
        self.set_interval(30, self._do_refresh)

    def action_refresh(self) -> None:
        self._do_refresh()

    def _do_refresh(self) -> None:
        bar = self.query_one(StatusBar)
        bar.set_refreshing(True)
        self._run_fetch()

    @work(thread=True, exclusive=True)
    def _run_fetch(self) -> None:
        family = getattr(self.app, "family", None)
        try:
            results = fetch_dashboard_data(family=family)
        except Exception as exc:
            self.app.call_from_thread(self._on_fetch_error, str(exc))
            return
        self.app.call_from_thread(self._on_fetch_done, results)

    def _on_fetch_done(self, results: list[dict]) -> None:
        table = self.query_one(BalanceTable)
        table.update_from_results(results)
        bar = self.query_one(StatusBar)
        bar.update_counts(results)

    def _on_fetch_error(self, error: str) -> None:
        bar = self.query_one(StatusBar)
        bar.set_refreshing(False)
        self.notify(f"Refresh failed: {error}", severity="error", timeout=5)
