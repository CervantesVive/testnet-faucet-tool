# Plan: TUI for Testnet Faucet Tool

## Context

The faucet CLI has static, one-shot commands (`dashboard`, `check`, `monitor`) that print to stdout and exit. Users want an interactive, htop-like experience: live-updating balances, in-place monitor display, and form-based config editing. The `textual` library is the right fit (same author as Rich, which is already a dependency).

The user has an existing plan at `docs/plans/TUI-for-Testnet-Faucet-Tool.md`. This refined plan addresses 10 issues found during review (overloaded phases, missing cache invalidation, stale registry after config saves, etc.) and splits the work into atomic, independently verifiable phases per CLAUDE.md requirements.

### Critical Design Constraint

`check_all()` and `run_check()` in `core/monitor.py` call `asyncio.run()` internally (lines 56, 98). Textual runs its own event loop. Nesting event loops would crash. **Solution:** `@work(thread=True)` runs these on a thread pool where each thread gets its own event loop context.

---

## Phase 1A: Data Layer

**Goal:** Thread-safe wrappers around core functions and YAML I/O, fully tested without any TUI dependency.

**Create:**
- `tui/__init__.py` (empty)
- `tui/data.py`:
  - `fetch_dashboard_data(family=None) -> list[dict]` — calls `check_all(get_all_assets(), family=family)`
  - `fetch_monitor_data(threshold=None, family=None) -> list[dict]` — calls `run_check(threshold, family)`
  - `load_chains_yaml() -> dict` — reads via `registry._get_chains_yaml_path()`
  - `save_chains_yaml(data: dict)` — writes with `yaml.safe_dump(sort_keys=False)`, then clears `registry._REGISTRY = None; registry._HANDLER_CACHE.clear()`
  - `load_alerts_yaml() -> dict` — reads from `alerting.ALERTS_CONFIG_PATH`
  - `save_alerts_yaml(data: dict)` — writes to `alerting.ALERTS_CONFIG_PATH`, creates parent dir
  - `FAMILY_EXTRA_FIELDS` — maps family names to non-standard fields
- `tests/test_tui_data.py` (10 tests)

**Tests first:**
1. `test_fetch_dashboard_data_calls_check_all` — mock `check_all` + `get_all_assets`
2. `test_fetch_dashboard_data_family_filter` — verify family kwarg passthrough
3. `test_fetch_monitor_data_calls_run_check` — mock `run_check`
4. `test_load_chains_yaml_returns_dict` — mock path to tmp yaml
5. `test_save_chains_yaml_roundtrip` — save then load
6. `test_save_chains_yaml_invalidates_cache` — verify `_REGISTRY` cleared
7. `test_load_alerts_yaml_missing_file` — returns empty dict
8. `test_load_alerts_yaml_existing` — reads correct structure
9. `test_save_alerts_yaml_creates_dir` — verify parent dir created
10. `test_save_alerts_yaml_roundtrip`

**Acceptance:** 10 new tests pass. All 531 existing tests pass. No textual import.
**Rollback:** Delete `tui/`, `tests/test_tui_data.py`

---

## Phase 1B: App Shell and CLI Wiring

**Goal:** Minimal `FaucetApp` that launches, shows 3 placeholder screens, switches via keybindings, exits cleanly.

**Create:**
- `tui/screens/__init__.py`, `tui/widgets/__init__.py`
- `tui/css/app.tcss` — minimal theme
- `tui/app.py` — `FaucetApp(App)` with Header, Footer, keybindings `1`/`2`/`3`/`q`
- `tui/screens/dashboard.py` — placeholder `Static("Dashboard")`
- `tui/screens/monitor.py` — placeholder `Static("Monitor")`
- `tui/screens/config_editor.py` — placeholder `Static("Config Editor")`

**Modify:**
- `pyproject.toml` — add `textual>=0.47` to deps, `"tui*"` to `packages.find.include`
- `cli.py` — add `@main.command() def tui(family, interval)` that imports and runs `FaucetApp`

**Tests first** (`tests/test_tui_app.py`, 7 tests):
1. `test_app_mounts`
2. `test_app_shows_dashboard_on_start`
3. `test_app_switch_to_monitor` — press `2`
4. `test_app_switch_to_config` — press `3`
5. `test_app_switch_back_to_dashboard` — press `1`
6. `test_app_quit` — press `q`
7. `test_cli_tui_command_exists` — CliRunner

**Acceptance:** `faucet tui` launches and exits. Screen switching works. All 548 tests pass.
**Rollback:** Delete created files, `git restore pyproject.toml cli.py`

---

## Phase 2: Balance Table Widget

**Goal:** Reusable `BalanceTable(DataTable)` with color-coded status cells. Isolated widget, no screen integration.

**Create:**
- `tui/widgets/balance_table.py` — columns: Asset, Family, Blockchain, Balance, Status. `update_from_results(results: list[dict])` uses `update_cell()` for surgical updates. Status: green OK, yellow LOW, red ERROR.
- `tests/test_tui_balance_table.py` (5 tests)

**Tests first:**
1. `test_balance_table_initial_populate` — 3 results -> 3 rows
2. `test_balance_table_status_colors` — verify OK/LOW/ERROR styles
3. `test_balance_table_update_preserves_rows` — call twice, row count stable
4. `test_balance_table_balance_formatting` — None->"N/A", 0.001->"0.001"
5. `test_balance_table_empty_results` — no crash

**Acceptance:** Widget renders in headless test. Updates idempotent.
**Rollback:** Delete both files

---

## Phase 3: Live Dashboard Screen

**Goal:** Wire `BalanceTable` into `DashboardScreen` with 30s auto-refresh, manual `r` refresh, status bar.

**Create:**
- `tui/widgets/status_bar.py` — "Last refresh: HH:MM:SS | Next in: XXs | OK: N LOW: N ERROR: N"

**Modify:**
- `tui/screens/dashboard.py` — replace placeholder: `BalanceTable` + `StatusBar`, `on_mount` triggers fetch + `set_interval(30)`, `@work(thread=True, exclusive=True)` calling `data.fetch_dashboard_data()`

**Tests first** (`tests/test_tui_dashboard.py`, 5 tests):
1. `test_dashboard_populates_on_mount`
2. `test_dashboard_manual_refresh` — press `r`
3. `test_dashboard_status_bar_updates` — OK/LOW/ERROR counts
4. `test_dashboard_family_filter`
5. `test_dashboard_error_does_not_crash`

**Acceptance:** Dashboard shows data, auto-refreshes, no scroll position loss.
**Rollback:** Revert dashboard.py, delete new files

---

## Phase 4: Countdown Widget and Monitor Screen

**Goal:** In-place monitor with countdown timer, pass counter, automatic re-trigger.

**Create:**
- `tui/widgets/countdown.py` — `CountdownWidget(Static)` with `start(seconds)`, 1s tick, posts `CountdownFinished` message
- `tests/test_tui_monitor.py` (6 tests)

**Modify:**
- `tui/screens/monitor.py` — replace placeholder: `BalanceTable` + `CountdownWidget` + pass counter. `on_mount` runs immediate check, `on_countdown_finished` triggers next pass.

**Tests first:**
1. `test_monitor_initial_check_on_mount`
2. `test_countdown_ticks_down`
3. `test_countdown_fires_message`
4. `test_monitor_check_triggers_on_countdown`
5. `test_monitor_pass_counter_increments`
6. `test_monitor_results_update_table`

**Acceptance:** Immediate check on mount, countdown ticks, auto-triggers, no scrolling.
**Rollback:** Revert monitor.py, delete new files

---

## Phase 5A: Config Editor — Asset Browser (Read-Only)

**Goal:** Left panel with searchable asset list, right panel with read-only field display. Shows ALL assets (not just native).

**Modify:**
- `tui/screens/config_editor.py` — `TabbedContent` ("Assets" + "Alerts" placeholder). Assets tab: `OptionList` of sorted asset IDs + search `Input` + right panel showing fields.

**Create:**
- `tests/test_tui_config.py` (4 tests)

**Tests first:**
1. `test_asset_list_populates`
2. `test_asset_selection_shows_fields`
3. `test_asset_search_filters`
4. `test_asset_list_shows_all_assets` — all assets, not just native

**Acceptance:** Browse all assets, search, view fields.
**Rollback:** Revert config_editor.py, delete test file

---

## Phase 5B: Config Editor — Asset Editing and Adding

**Goal:** Editable fields for mutable config, save with confirmation, add-asset form.

**Modify:**
- `tui/screens/config_editor.py` — `Input` widgets for editable fields (`rpc_url`, `drip_amount`, `explorer`, `note`, `refill_source`). Read-only for `family`, `blockchain`, `network`, `native_asset`, `decimals`. "Save" with confirmation dialog (warns about comment loss). "Add Asset" modal with family dropdown -> conditional fields. Validates `REQUIRED_FIELDS`.

**Tests (6 additions to `tests/test_tui_config.py`):**
5. `test_edit_field_and_save`
6. `test_save_confirmation_dialog`
7. `test_save_cancel_does_not_write`
8. `test_add_asset_required_fields_validation`
9. `test_add_asset_cosmos_shows_extra_fields`
10. `test_add_asset_evm_non_native_shows_contract`

**Acceptance:** Edit mutable fields, save with confirmation, add assets with validation.
**Rollback:** Revert to Phase 5A state

---

## Phase 5C: Config Editor — Alerts Tab

**Goal:** Form editor for all 4 alert channels (log, slack, webhook, email).

**Modify:**
- `tui/screens/config_editor.py` — Alerts tab with collapsible sections, `Switch` toggles, relevant `Input` fields. Disabled sections greyed out. Password masked. Save via `data.save_alerts_yaml()`.

**Create:**
- `tests/test_tui_config_alerts.py` (6 tests)

**Tests first:**
1. `test_alerts_loads_defaults_when_no_file`
2. `test_alerts_loads_existing_config`
3. `test_alerts_toggle_disables_inputs`
4. `test_alerts_save_writes_yaml`
5. `test_alerts_password_masked`
6. `test_alerts_saved_yaml_readable_by_alerting`

**Acceptance:** All 4 channels editable, toggles work, saved YAML compatible with `core/alerting.py`.
**Rollback:** Revert config_editor.py, delete test file

---

## Phase 6: Error Handling and Help Overlay

**Goal:** Resilient error handling, `?` help overlay, CSS polish.

**Modify:**
- `tui/app.py` — `?` keybinding for help modal
- `tui/screens/dashboard.py` — try/except in worker, toast on failure
- `tui/screens/monitor.py` — try/except in worker, restart countdown on failure
- `tui/screens/config_editor.py` — try/except on YAML parse, toast on error
- `tui/css/app.tcss` — responsive layout, consistent colors

**Tests (5 additions to `tests/test_tui_app.py`):**
8. `test_help_overlay_shows`
9. `test_help_overlay_dismisses`
10. `test_dashboard_network_error_shows_toast`
11. `test_monitor_network_error_continues`
12. `test_config_malformed_yaml_shows_toast`

**Acceptance:** No unhandled exceptions. Help overlay works. All ~585 tests pass.
**Rollback:** Revert all to Phase 5C state

---

## Phase 7: CLAUDE.md Update

**Modify:** `CLAUDE.md` — add TUI section: `faucet tui` command, thread-worker pattern, testing with `app.run_test()`, registry cache invalidation after config saves.

**Rollback:** `git restore CLAUDE.md`

---

## Critical Files to Reuse

| File | What to reuse |
|------|---------------|
| `core/monitor.py:19-68` | `check_all()` — consumed by `data.fetch_dashboard_data()` |
| `core/monitor.py:81-126` | `run_check()` — consumed by `data.fetch_monitor_data()` |
| `core/registry.py:5-6` | `_REGISTRY`, `_HANDLER_CACHE` — must clear after config saves |
| `core/registry.py:37-38` | `_get_chains_yaml_path()` — reuse for `load_chains_yaml()` |
| `core/registry.py:52` | `REQUIRED_FIELDS` — reuse for add-asset validation |
| `core/registry.py:66-67` | `get_all_assets()` — consumed by dashboard data layer |
| `core/alerting.py:14` | `ALERTS_CONFIG_PATH` — reuse for alerts load/save |
| `handlers/base.py` | `BaseHandler.get_faucet_balance() -> dict[str,str]` — return type reference |

## Key Risks

| Risk | Mitigation |
|------|-----------|
| `asyncio.run()` nesting | `@work(thread=True)` on all data fetches |
| 76 sequential network calls slow dashboard | `exclusive=True` prevents overlap; status bar shows "Refreshing..." |
| YAML comment loss on save | Confirmation dialog warns; no ruamel.yaml dep |
| `_REGISTRY` cache stale after config save | `save_chains_yaml()` explicitly clears both caches |
| `ALERTS_CONFIG_PATH` is env-var dynamic | Always read from `alerting.ALERTS_CONFIG_PATH`, never hardcode |

## Test Infrastructure

- All TUI tests use `async with app.run_test() as pilot:` (Textual headless testing)
- Autouse conftest fixture resets `reg._REGISTRY = None; reg._HANDLER_CACHE.clear()`
- Screen tests mock at `tui.data` layer; data tests mock at `core.monitor` layer
- Monkeypatch path constants per existing patterns

## Verification

1. `faucet tui` — launches, shows dashboard, switch screens with 1/2/3, quit with q
2. Dashboard — rows populate, 30s auto-refresh, `r` manual refresh, family filter
3. Monitor — countdown ticks, check at zero, results update in-place, pass counter
4. Config — edit asset rpc_url, save, verify with `cat config/chains.yaml`; edit alerts, save, verify
5. `.venv/bin/python -m pytest tests/ -q` — all tests pass (531 existing + ~54 new)
6. `faucet dashboard`, `faucet monitor`, `faucet check` — unchanged behavior
