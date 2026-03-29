"""Tests for ConfigEditorScreen — asset browser, editing, and adding."""
import pytest
from unittest.mock import patch, MagicMock

from tui.app import FaucetApp
from tui.screens.config_editor import ConfigEditorScreen


MOCK_CHAINS = {
    "TETH": {
        "family": "evm",
        "blockchain": "Ethereum",
        "network": "holesky",
        "native_asset": True,
        "drip_amount": "0.05",
        "decimals": 18,
        "rpc_url": "https://ethereum-holesky.example.com",
        "explorer": "https://holesky.etherscan.io/tx/{tx_hash}",
        "note": "Test asset",
    },
    "TSOL": {
        "family": "solana",
        "blockchain": "Solana",
        "network": "devnet",
        "native_asset": True,
        "drip_amount": "1.0",
        "decimals": 9,
        "rpc_url": "https://api.devnet.solana.com",
        "explorer": "TBD",
    },
    "TATOM": {
        "family": "cosmos",
        "blockchain": "Cosmos Hub",
        "network": "theta-testnet-001",
        "native_asset": True,
        "drip_amount": "1000000",
        "decimals": 6,
        "denom": "uatom",
        "bech32_prefix": "cosmos",
    },
}


@pytest.fixture(autouse=True)
def patch_chains():
    """Patch load_chains_yaml for all config tests."""
    with patch("tui.screens.config_editor.load_chains_yaml", return_value=MOCK_CHAINS):
        yield


# ---------------------------------------------------------------------------
# Phase 5A: Asset browser (read-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asset_list_populates():
    """Asset list shows one option per asset in the YAML."""
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        screen = app.screen
        assert isinstance(screen, ConfigEditorScreen)
        from textual.widgets import OptionList
        option_list = screen.query_one("#asset-list", OptionList)
        assert option_list.option_count == len(MOCK_CHAINS)


@pytest.mark.asyncio
async def test_asset_list_shows_all_assets():
    """Asset list includes non-native assets (all assets, not just native)."""
    all_asset_chains = {
        **MOCK_CHAINS,
        "TETH:USDC": {
            "family": "evm",
            "blockchain": "Ethereum",
            "network": "holesky",
            "native_asset": False,
            "drip_amount": "10",
            "decimals": 6,
            "contract_address": "0xabc",
        },
    }
    with patch("tui.screens.config_editor.load_chains_yaml", return_value=all_asset_chains):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause(0.3)
            from textual.widgets import OptionList
            option_list = app.screen.query_one("#asset-list", OptionList)
            assert option_list.option_count == 4


@pytest.mark.asyncio
async def test_asset_search_filters():
    """Setting the search box value filters the asset list."""
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        from textual.widgets import OptionList, Input
        search = app.screen.query_one("#asset-search", Input)
        # Set value directly — triggers on_input_changed
        search.value = "TETH"
        await pilot.pause(0.2)
        option_list = app.screen.query_one("#asset-list", OptionList)
        # Should only show TETH
        assert option_list.option_count == 1


@pytest.mark.asyncio
async def test_asset_selection_shows_fields():
    """Selecting an asset shows its fields in the detail panel."""
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        # Select the first item via down + enter
        from textual.widgets import OptionList
        option_list = app.screen.query_one("#asset-list", OptionList)
        option_list.focus()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause(0.3)
        from textual.widgets import Input
        # rpc_url field should be visible and populated
        rpc_input = app.screen.query_one("#field-rpc_url", Input)
        assert rpc_input is not None


# ---------------------------------------------------------------------------
# Phase 5B: Asset editing and adding
# ---------------------------------------------------------------------------

async def _select_first_asset(pilot, app):
    """Helper: navigate to config and select the first asset."""
    from textual.widgets import OptionList
    option_list = app.screen.query_one("#asset-list", OptionList)
    option_list.focus()
    await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause(0.3)


@pytest.mark.asyncio
async def test_edit_field_and_save():
    """Editing rpc_url and saving writes updated YAML."""
    saved = {}

    def mock_save(data):
        saved.update(data)

    with patch("tui.screens.config_editor.save_chains_yaml", side_effect=mock_save):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause(0.3)
            await _select_first_asset(pilot, app)
            from textual.widgets import Input, Button
            rpc_input = app.screen.query_one("#field-rpc_url", Input)
            rpc_input.value = "https://new-rpc.example.com"
            # Press the save button programmatically
            save_btn = app.screen.query_one("#save-asset", Button)
            save_btn.press()
            await pilot.pause(0.3)
            # Confirm the modal dialog
            confirm_btn = app.screen.query_one("#confirm-save", Button)
            confirm_btn.press()
            await pilot.pause(0.2)
    assert saved


@pytest.mark.asyncio
async def test_save_confirmation_dialog():
    """Save button shows a confirmation dialog before writing."""
    app = FaucetApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        await _select_first_asset(pilot, app)
        from textual.widgets import Button
        save_btn = app.screen.query_one("#save-asset", Button)
        save_btn.press()
        await pilot.pause(0.2)
        from textual.screen import ModalScreen
        assert isinstance(app.screen, ModalScreen)


@pytest.mark.asyncio
async def test_save_cancel_does_not_write():
    """Dismissing the save dialog does not call save_chains_yaml."""
    call_count = 0

    def mock_save(data):
        nonlocal call_count
        call_count += 1

    with patch("tui.screens.config_editor.save_chains_yaml", side_effect=mock_save):
        app = FaucetApp()
        async with app.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause(0.3)
            await _select_first_asset(pilot, app)
            from textual.widgets import Button
            save_btn = app.screen.query_one("#save-asset", Button)
            save_btn.press()
            await pilot.pause(0.2)
            cancel_btn = app.screen.query_one("#confirm-cancel", Button)
            cancel_btn.press()
            await pilot.pause(0.2)
    assert call_count == 0


@pytest.mark.asyncio
async def test_add_asset_required_fields_validation():
    """Adding an asset with missing required fields shows a validation error."""
    app = FaucetApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        from textual.widgets import Button
        add_btn = app.screen.query_one("#add-asset", Button)
        add_btn.press()
        await pilot.pause(0.2)
        # Try to save without filling in required fields
        save_btn = app.screen.query_one("#add-save", Button)
        save_btn.press()
        await pilot.pause(0.2)
        # Should not have closed the modal yet (validation error shown)
        from textual.screen import ModalScreen
        assert isinstance(app.screen, ModalScreen)


@pytest.mark.asyncio
async def test_add_asset_cosmos_shows_extra_fields():
    """Selecting cosmos family in add form shows denom and bech32_prefix fields."""
    app = FaucetApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        await pilot.click("#add-asset")
        await pilot.pause(0.2)
        # Select cosmos family
        from textual.widgets import Select
        family_select = app.screen.query_one("#add-family", Select)
        family_select.value = "cosmos"
        await pilot.pause(0.2)
        denom_field = app.screen.query("#add-denom")
        assert len(list(denom_field)) > 0


@pytest.mark.asyncio
async def test_add_asset_evm_non_native_shows_contract():
    """Selecting evm + non-native in add form shows contract_address field."""
    app = FaucetApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("3")
        await pilot.pause(0.3)
        await pilot.click("#add-asset")
        await pilot.pause(0.2)
        from textual.widgets import Select, Checkbox
        family_select = app.screen.query_one("#add-family", Select)
        family_select.value = "evm"
        await pilot.pause(0.1)
        native_cb = app.screen.query_one("#add-native", Checkbox)
        native_cb.value = False
        await pilot.pause(0.2)
        contract_field = app.screen.query("#add-contract_address")
        assert len(list(contract_field)) > 0
