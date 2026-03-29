"""StatusBar — shows last refresh time, countdown, and summary counts."""
from datetime import datetime

from textual.widgets import Static


class StatusBar(Static):
    """Footer-style bar showing refresh state and balance summary counts."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("Initializing...", **kwargs)
        self._ok = 0
        self._low = 0
        self._error = 0
        self._last_refresh: str = "never"
        self._refreshing: bool = False

    def set_refreshing(self, refreshing: bool) -> None:
        self._refreshing = refreshing
        self._redraw()

    def update_counts(self, results: list[dict]) -> None:
        self._ok = sum(1 for r in results if r.get("status") == "OK")
        self._low = sum(1 for r in results if r.get("status") == "LOW")
        self._error = sum(1 for r in results if r.get("status") == "ERROR")
        self._last_refresh = datetime.now().strftime("%H:%M:%S")
        self._refreshing = False
        self._redraw()

    def _redraw(self) -> None:
        if self._refreshing:
            state = "Refreshing..."
        else:
            state = f"Last refresh: {self._last_refresh}"
        msg = (
            f"{state}  |  OK: {self._ok} LOW: {self._low} ERROR: {self._error}"
        )
        self.update(msg)
