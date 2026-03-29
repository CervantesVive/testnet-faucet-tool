"""FaucetApp — main Textual application entry point."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from tui.screens.config_editor import ConfigEditorScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.monitor import MonitorScreen


class _HelpScreen(ModalScreen):
    """Help overlay showing keybindings."""

    DEFAULT_CSS = """
    _HelpScreen {
        align: center middle;
    }
    _HelpScreen > Static {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Testnet Faucet TUI — Keybindings[/bold]\n\n"
            "  [bold]1[/bold]  Dashboard\n"
            "  [bold]2[/bold]  Monitor\n"
            "  [bold]3[/bold]  Config Editor\n"
            "  [bold]r[/bold]  Refresh (Dashboard)\n"
            "  [bold]?[/bold]  Help\n"
            "  [bold]q[/bold]  Quit\n\n"
            "Press [bold]Escape[/bold] to close",
        )


class FaucetApp(App):
    """Interactive TUI for the testnet faucet tool."""

    CSS_PATH = "css/app.tcss"

    BINDINGS = [
        Binding("1", "switch_screen('dashboard')", "Dashboard", show=True),
        Binding("2", "switch_screen('monitor')", "Monitor", show=True),
        Binding("3", "switch_screen('config')", "Config", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "monitor": MonitorScreen,
        "config": ConfigEditorScreen,
    }

    def __init__(self, family: str | None = None, interval: str = "1h") -> None:
        super().__init__()
        self.family = family
        self.interval = interval

    def on_mount(self) -> None:
        self.push_screen("dashboard")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def action_help(self) -> None:
        self.push_screen(_HelpScreen())
