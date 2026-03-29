"""MonitorScreen — in-place monitor with countdown timer and pass counter."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from textual._work_decorator import work
from tui.data import fetch_monitor_data
from tui.widgets.balance_table import BalanceTable
from tui.widgets.countdown import CountdownFinished, CountdownWidget

DEFAULT_INTERVAL = 60  # seconds between monitor checks


class MonitorScreen(Screen):
    """Continuous monitor view — runs check passes with a countdown between each."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.pass_count: int = 0

    def compose(self) -> ComposeResult:
        yield Static("Pass #0", id="pass-counter")
        yield BalanceTable(id="monitor-table")
        yield CountdownWidget(id="monitor-countdown")

    def on_mount(self) -> None:
        self._run_check()

    def on_countdown_finished(self, event: CountdownFinished) -> None:
        self._run_check()

    @work(thread=True, exclusive=True)
    def _run_check(self) -> None:
        family = getattr(self.app, "family", None)
        threshold = None
        try:
            results = fetch_monitor_data(threshold=threshold, family=family)
        except Exception as exc:
            self.app.call_from_thread(self._on_check_error, str(exc))
            return
        self.app.call_from_thread(self._on_check_done, results)

    def _on_check_done(self, results: list[dict]) -> None:
        self.pass_count += 1
        table = self.query_one(BalanceTable)
        table.update_from_results(results)
        counter = self.query_one("#pass-counter", Static)
        counter.update(f"Pass #{self.pass_count}")
        countdown = self.query_one(CountdownWidget)
        countdown.start(DEFAULT_INTERVAL)

    def _on_check_error(self, error: str) -> None:
        self.notify(f"Check failed: {error}", severity="error", timeout=5)
        countdown = self.query_one(CountdownWidget)
        countdown.start(DEFAULT_INTERVAL)
