"""CountdownWidget — shows "Next check in: MM:SS" and posts CountdownFinished."""
from textual.message import Message
from textual.widgets import Static


class CountdownFinished(Message):
    """Posted when the countdown reaches zero."""


class CountdownWidget(Static):
    """Countdown timer that ticks down 1s at a time and posts CountdownFinished at zero."""

    DEFAULT_CSS = """
    CountdownWidget {
        height: 1;
        dock: bottom;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("Next check in: --:--", **kwargs)
        self._remaining: int = 0
        self._timer = None

    def start(self, seconds: int) -> None:
        """Start (or restart) the countdown from `seconds`."""
        self._remaining = seconds
        self._update_display()
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._remaining > 0:
            self._remaining -= 1
            self._update_display()
        if self._remaining == 0:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self.post_message(CountdownFinished())

    def _update_display(self) -> None:
        mins, secs = divmod(self._remaining, 60)
        self.update(f"Next check in: {mins:02d}:{secs:02d}")
