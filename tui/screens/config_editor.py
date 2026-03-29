"""ConfigEditorScreen — TabbedContent with Assets and Alerts tabs."""
from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option
from textual.containers import Horizontal, ScrollableContainer, Vertical

from core.registry import REQUIRED_FIELDS, FAMILY_HANDLER_MAP
from tui.data import (
    FAMILY_EXTRA_FIELDS,
    load_alerts_yaml,
    load_chains_yaml,
    save_alerts_yaml,
    save_chains_yaml,
)


# Fields editable by the user (mutable config)
EDITABLE_FIELDS = ["rpc_url", "drip_amount", "explorer", "note", "refill_source"]
# Fields shown read-only
READONLY_FIELDS = ["family", "blockchain", "network", "native_asset", "decimals"]


# ---------------------------------------------------------------------------
# Save confirmation modal
# ---------------------------------------------------------------------------

class _SaveConfirmModal(ModalScreen):
    """Confirms save, warns about YAML comment loss."""

    DEFAULT_CSS = """
    _SaveConfirmModal {
        align: center middle;
    }
    _SaveConfirmModal > Vertical {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    _SaveConfirmModal Button { margin: 0 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                "[bold]Save changes?[/bold]\n\n"
                "Warning: comments in chains.yaml will be lost.",
                id="confirm-msg",
            )
            with Horizontal():
                yield Button("Save", variant="success", id="confirm-save")
                yield Button("Cancel", variant="default", id="confirm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-save")


# ---------------------------------------------------------------------------
# Add Asset modal
# ---------------------------------------------------------------------------

class _AddAssetModal(ModalScreen):
    """Form for adding a new asset to chains.yaml."""

    DEFAULT_CSS = """
    _AddAssetModal {
        align: center middle;
    }
    _AddAssetModal > ScrollableContainer {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 30;
    }
    _AddAssetModal Label { margin-top: 1; }
    _AddAssetModal Button { margin: 1 1 0 0; }
    """

    FAMILIES = sorted(FAMILY_HANDLER_MAP.keys())

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Label("[bold]Add New Asset[/bold]")
            yield Label("Asset ID:")
            yield Input(placeholder="e.g. TTEST", id="add-asset-id")
            yield Label("Family:")
            yield Select(
                [(f, f) for f in self.FAMILIES],
                id="add-family",
                prompt="Select family...",
            )
            yield Label("Blockchain:")
            yield Input(placeholder="e.g. Ethereum", id="add-blockchain")
            yield Label("Network:")
            yield Input(placeholder="e.g. holesky", id="add-network")
            yield Label("Native asset:")
            yield Checkbox("Native asset", True, id="add-native")
            yield Label("Drip amount:")
            yield Input(placeholder="e.g. 0.05", id="add-drip_amount")
            yield Label("Decimals:")
            yield Input(placeholder="e.g. 18", id="add-decimals")
            yield Label("RPC URL:")
            yield Input(placeholder="https://...", id="add-rpc_url")

            # Cosmos-specific fields
            yield Label("Denom (cosmos):", id="add-denom-label", classes="cosmos-field hidden")
            yield Input(placeholder="e.g. uatom", id="add-denom", classes="cosmos-field hidden")
            yield Label("Bech32 prefix (cosmos):", id="add-bech32-label", classes="cosmos-field hidden")
            yield Input(placeholder="e.g. cosmos", id="add-bech32_prefix", classes="cosmos-field hidden")

            # EVM token field
            yield Label("Contract address (evm token):", id="add-contract-label", classes="evm-token-field hidden")
            yield Input(placeholder="0x...", id="add-contract_address", classes="evm-token-field hidden")

            # Solana token field
            yield Label("Mint address (solana token):", id="add-mint-label", classes="solana-token-field hidden")
            yield Input(placeholder="base58...", id="add-mint_address", classes="solana-token-field hidden")

            yield Static("", id="add-error", classes="error-msg")
            with Horizontal():
                yield Button("Add", variant="success", id="add-save")
                yield Button("Cancel", variant="default", id="add-cancel")

    DEFAULT_CSS = """
    _AddAssetModal {
        align: center middle;
    }
    _AddAssetModal > ScrollableContainer {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 30;
    }
    _AddAssetModal Label { margin-top: 1; }
    _AddAssetModal Button { margin: 1 1 0 0; }
    _AddAssetModal .hidden { display: none; }
    """

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "add-family":
            self._update_family_fields(str(event.value) if event.value else "")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "add-native":
            family_select = self.query_one("#add-family", Select)
            fam = str(family_select.value) if family_select.value else ""
            self._update_family_fields(fam)

    def _update_family_fields(self, family: str) -> None:
        native_cb = self.query_one("#add-native", Checkbox)
        is_native = native_cb.value

        # Show/hide cosmos fields
        for w in self.query(".cosmos-field"):
            w.set_class(family != "cosmos", "hidden")

        # Show/hide evm token field
        for w in self.query(".evm-token-field"):
            w.set_class(not (family == "evm" and not is_native), "hidden")

        # Show/hide solana token field
        for w in self.query(".solana-token-field"):
            w.set_class(not (family == "solana" and not is_native), "hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-cancel":
            self.dismiss(None)
        elif event.button.id == "add-save":
            self._try_save()

    def _try_save(self) -> None:
        """Validate and build the new asset dict."""
        asset_id = self.query_one("#add-asset-id", Input).value.strip()
        family_sel = self.query_one("#add-family", Select)
        family = str(family_sel.value) if family_sel.value else ""
        blockchain = self.query_one("#add-blockchain", Input).value.strip()
        network = self.query_one("#add-network", Input).value.strip()
        drip_amount = self.query_one("#add-drip_amount", Input).value.strip()
        decimals = self.query_one("#add-decimals", Input).value.strip()
        is_native = self.query_one("#add-native", Checkbox).value

        errors = []
        if not asset_id:
            errors.append("Asset ID is required")
        if not family:
            errors.append("Family is required")
        if not blockchain:
            errors.append("Blockchain is required")
        if not network:
            errors.append("Network is required")
        if not drip_amount:
            errors.append("Drip amount is required")
        if not decimals:
            errors.append("Decimals is required")

        if errors:
            err = self.query_one("#add-error", Static)
            err.update("[red]" + "; ".join(errors) + "[/red]")
            return

        new_asset = {
            "family": family,
            "blockchain": blockchain,
            "network": network,
            "native_asset": is_native,
            "drip_amount": drip_amount,
            "decimals": int(decimals) if decimals.isdigit() else 18,
        }

        rpc_url = self.query_one("#add-rpc_url", Input).value.strip()
        if rpc_url:
            new_asset["rpc_url"] = rpc_url

        if family == "cosmos":
            denom = self.query_one("#add-denom", Input).value.strip()
            bech32 = self.query_one("#add-bech32_prefix", Input).value.strip()
            if denom:
                new_asset["denom"] = denom
            if bech32:
                new_asset["bech32_prefix"] = bech32
        elif family == "evm" and not is_native:
            contract = self.query_one("#add-contract_address", Input).value.strip()
            if contract:
                new_asset["contract_address"] = contract
        elif family == "solana" and not is_native:
            mint = self.query_one("#add-mint_address", Input).value.strip()
            if mint:
                new_asset["mint_address"] = mint

        self.dismiss((asset_id, new_asset))


# ---------------------------------------------------------------------------
# ConfigEditorScreen
# ---------------------------------------------------------------------------

class ConfigEditorScreen(Screen):
    """Asset and alerts configuration editor."""

    DEFAULT_CSS = """
    ConfigEditorScreen {
        layout: vertical;
    }
    #asset-pane {
        layout: horizontal;
    }
    #left-panel {
        width: 30;
        border-right: tall $primary-darken-2;
    }
    #right-panel {
        width: 1fr;
        padding: 0 1;
    }
    #asset-search {
        width: 100%;
    }
    #asset-list {
        height: 1fr;
    }
    .field-row { margin-bottom: 1; }
    .readonly-label { color: $text-muted; }
    #save-asset, #add-asset { margin: 1 0; }
    .alerts-section { margin-bottom: 1; }
    .alerts-row { layout: horizontal; height: auto; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._chains: dict = {}
        self._selected_asset_id: str | None = None

    def on_mount(self) -> None:
        try:
            self._chains = load_chains_yaml()
        except Exception as exc:
            self._chains = {}
            self.notify(f"Failed to load chains.yaml: {exc}", severity="error", timeout=8)
        self._populate_asset_list()
        self._load_alerts()

    def compose(self) -> ComposeResult:
        with TabbedContent(id="editor-tabs"):
            with TabPane("Assets", id="tab-assets"):
                with Horizontal(id="asset-pane"):
                    with Vertical(id="left-panel"):
                        yield Input(
                            placeholder="Search assets...",
                            id="asset-search",
                        )
                        yield OptionList(id="asset-list")
                    with ScrollableContainer(id="right-panel"):
                        yield Static(
                            "Select an asset to view/edit its fields.",
                            id="asset-detail-placeholder",
                        )
                        yield Vertical(id="asset-detail", classes="hidden")
                yield Button("Add Asset", id="add-asset")

            with TabPane("Alerts", id="tab-alerts"):
                with ScrollableContainer(id="alerts-content"):
                    yield self._compose_alerts()

    def _compose_alerts(self) -> Vertical:
        """Build the alerts form widgets."""
        return Vertical(
            # Log section
            Label("[bold]Log[/bold]"),
            Horizontal(
                Switch(True, id="alerts-log-enabled"),
                Label("Enabled"),
                classes="alerts-row",
            ),
            Input(placeholder="Path (optional)", id="alerts-log-path"),

            # Slack section
            Label("[bold]Slack[/bold]"),
            Horizontal(
                Switch(False, id="alerts-slack-enabled"),
                Label("Enabled"),
                classes="alerts-row",
            ),
            Input(
                placeholder="https://hooks.slack.com/...",
                id="alerts-slack-webhook_url",
                disabled=True,
            ),

            # Webhook section
            Label("[bold]Webhook[/bold]"),
            Horizontal(
                Switch(False, id="alerts-webhook-enabled"),
                Label("Enabled"),
                classes="alerts-row",
            ),
            Input(placeholder="https://...", id="alerts-webhook-url", disabled=True),

            # Email section
            Label("[bold]Email[/bold]"),
            Horizontal(
                Switch(False, id="alerts-email-enabled"),
                Label("Enabled"),
                classes="alerts-row",
            ),
            Input(
                placeholder="smtp.example.com",
                id="alerts-email-smtp_host",
                disabled=True,
            ),
            Input(placeholder="587", id="alerts-email-smtp_port", disabled=True),
            Input(
                placeholder="from@example.com",
                id="alerts-email-from",
                disabled=True,
            ),
            Input(
                placeholder="to@example.com",
                id="alerts-email-to",
                disabled=True,
            ),
            Input(
                placeholder="username",
                id="alerts-email-username",
                disabled=True,
            ),
            Input(
                placeholder="password",
                id="alerts-email-password",
                password=True,
                disabled=True,
            ),
            Button("Save Alerts", id="save-alerts"),
            id="alerts-form",
        )

    # ------------------------------------------------------------------
    # Asset list management
    # ------------------------------------------------------------------

    def _populate_asset_list(self, filter_text: str = "") -> None:
        option_list = self.query_one("#asset-list", OptionList)
        option_list.clear_options()
        for asset_id in sorted(self._chains):
            if filter_text.lower() in asset_id.lower():
                option_list.add_option(Option(asset_id, id=asset_id))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "asset-search":
            self._populate_asset_list(event.value)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        asset_id = str(event.option.id)
        self._selected_asset_id = asset_id
        self._show_asset_detail(asset_id)

    def _show_asset_detail(self, asset_id: str) -> None:
        cfg = self._chains.get(asset_id, {})
        placeholder = self.query_one("#asset-detail-placeholder", Static)
        placeholder.add_class("hidden")

        detail = self.query_one("#asset-detail", Vertical)
        detail.remove_class("hidden")
        detail.remove_children()

        # Readonly fields
        for key in READONLY_FIELDS:
            val = cfg.get(key, "")
            detail.mount(Label(f"[dim]{key}:[/dim] {val}", classes="readonly-label"))

        # Editable fields
        for key in EDITABLE_FIELDS:
            val = str(cfg.get(key, ""))
            detail.mount(Label(f"{key}:"))
            detail.mount(Input(value=val, id=f"field-{key}"))

        detail.mount(Button("Save", id="save-asset", variant="success"))

    # ------------------------------------------------------------------
    # Save asset
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-asset":
            self._confirm_save_asset()
        elif event.button.id == "add-asset":
            self._open_add_asset()
        elif event.button.id == "save-alerts":
            self._save_alerts()

    def _confirm_save_asset(self) -> None:
        def _on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._do_save_asset()

        self.app.push_screen(_SaveConfirmModal(), _on_confirm)

    def _do_save_asset(self) -> None:
        if not self._selected_asset_id:
            return
        cfg = dict(self._chains.get(self._selected_asset_id, {}))
        for key in EDITABLE_FIELDS:
            try:
                field = self.query_one(f"#field-{key}", Input)
                if field.value:
                    cfg[key] = field.value
                elif key in cfg:
                    del cfg[key]
            except Exception:
                pass
        self._chains[self._selected_asset_id] = cfg
        try:
            save_chains_yaml(self._chains)
            self.notify("Saved successfully.", severity="information", timeout=3)
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error", timeout=5)

    # ------------------------------------------------------------------
    # Add asset
    # ------------------------------------------------------------------

    def _open_add_asset(self) -> None:
        def _on_add(result) -> None:
            if result is None:
                return
            asset_id, new_asset = result
            self._chains[asset_id] = new_asset
            save_chains_yaml(self._chains)
            self._populate_asset_list()
            self.notify(f"Added {asset_id}.", severity="information", timeout=3)

        self.app.push_screen(_AddAssetModal(), _on_add)

    # ------------------------------------------------------------------
    # Alerts tab
    # ------------------------------------------------------------------

    def _load_alerts(self) -> None:
        cfg = load_alerts_yaml()
        alerts = cfg.get("alerts", {})

        def _set(widget_id: str, value) -> None:
            try:
                w = self.query_one(f"#{widget_id}")
                if hasattr(w, "value"):
                    w.value = value
            except Exception:
                pass

        # Log
        log = alerts.get("log", {})
        _set("alerts-log-enabled", log.get("enabled", True))
        _set("alerts-log-path", log.get("path", ""))

        # Slack
        slack = alerts.get("slack", {})
        _set("alerts-slack-enabled", slack.get("enabled", False))
        _set("alerts-slack-webhook_url", slack.get("webhook_url", ""))
        self._sync_section_enabled("slack", slack.get("enabled", False))

        # Webhook
        wh = alerts.get("webhook", {})
        _set("alerts-webhook-enabled", wh.get("enabled", False))
        _set("alerts-webhook-url", wh.get("url", ""))
        self._sync_section_enabled("webhook", wh.get("enabled", False))

        # Email
        em = alerts.get("email", {})
        _set("alerts-email-enabled", em.get("enabled", False))
        _set("alerts-email-smtp_host", em.get("smtp_host", ""))
        _set("alerts-email-smtp_port", str(em.get("smtp_port", "587")))
        _set("alerts-email-from", em.get("from", ""))
        to_val = em.get("to", [])
        if isinstance(to_val, list):
            to_val = ", ".join(to_val)
        _set("alerts-email-to", to_val)
        _set("alerts-email-username", em.get("username", ""))
        _set("alerts-email-password", em.get("password", ""))
        self._sync_section_enabled("email", em.get("enabled", False))

    def _sync_section_enabled(self, section: str, enabled: bool) -> None:
        """Enable/disable Input widgets for a section based on toggle state."""
        field_map = {
            "slack": ["alerts-slack-webhook_url"],
            "webhook": ["alerts-webhook-url"],
            "email": [
                "alerts-email-smtp_host",
                "alerts-email-smtp_port",
                "alerts-email-from",
                "alerts-email-to",
                "alerts-email-username",
                "alerts-email-password",
            ],
        }
        for field_id in field_map.get(section, []):
            try:
                w = self.query_one(f"#{field_id}", Input)
                w.disabled = not enabled
            except Exception:
                pass

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id: str = event.switch.id or ""
        if switch_id.startswith("alerts-"):
            parts = switch_id.split("-")
            if len(parts) >= 3:
                section = parts[1]
                self._sync_section_enabled(section, event.value)

    def _save_alerts(self) -> None:
        def _get(widget_id: str, default=""):
            try:
                w = self.query_one(f"#{widget_id}")
                return w.value
            except Exception:
                return default

        data = {
            "alerts": {
                "log": {
                    "enabled": _get("alerts-log-enabled", True),
                    "path": _get("alerts-log-path") or None,
                },
                "slack": {
                    "enabled": _get("alerts-slack-enabled", False),
                    "webhook_url": _get("alerts-slack-webhook_url"),
                },
                "webhook": {
                    "enabled": _get("alerts-webhook-enabled", False),
                    "url": _get("alerts-webhook-url"),
                },
                "email": {
                    "enabled": _get("alerts-email-enabled", False),
                    "smtp_host": _get("alerts-email-smtp_host"),
                    "smtp_port": int(_get("alerts-email-smtp_port") or 587),
                    "from": _get("alerts-email-from"),
                    "to": [t.strip() for t in _get("alerts-email-to").split(",") if t.strip()],
                    "username": _get("alerts-email-username"),
                    "password": _get("alerts-email-password"),
                },
            }
        }
        try:
            save_alerts_yaml(data)
            self.notify("Alerts saved.", severity="information", timeout=3)
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error", timeout=5)
