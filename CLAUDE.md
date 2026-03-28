# BitGo Testnet Faucet Tool

## Environment
- Python venv: `.venv/` in project root — use absolute path, worktrees share it
- Run tests: `.venv/bin/python -m pytest tests/ -q`
- Install deps: `.venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[<extras>,dev]"`
- `config/chains.yaml` is auto-restored by `conftest.py` if deleted — don't worry about it

## Architecture
- Handlers in `handlers/<family>.py` extending `BaseHandler` (4 abstract methods: `drip`, `validate_address`, `get_faucet_balance`, `supported_assets`)
- Registry in `core/registry.py` maps family names to handler classes via `FAMILY_HANDLER_MAP`
- New handler: add to `FAMILY_HANDLER_MAP`, create `handlers/<family>.py`, add optional dep group to `pyproject.toml`

## Testing conventions
- Unit tests: patch client constructor at module level (e.g. `patch("handlers.cosmos.LedgerClient", ...)`)
- Integration tests: `CliRunner` + synchronous `def` (CLI calls `asyncio.run()` internally — no nesting)
- Rate limiter isolation: `monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")`
- Async tests use `@pytest.mark.asyncio` (mode set to `auto` in `pyproject.toml`)

## cosmpy gotchas (Cosmos handler)
- `NetworkConfig` URL must start with `rest+https://` or `grpc+https://` — prepend `rest+` to plain URLs
- `NetworkConfig` is in `cosmpy.aerial.config`, not `cosmpy.aerial.client`
- `SubmittedTx.tx_hash` (property) and `.wait_to_complete()` return the same `SubmittedTx`

## Rich + CliRunner
- `console.print(table)` truncates wide columns in narrow test terminals — print key values (addresses, hashes) on their own line before/after tables so tests can assert on them

## Phase completion
- Phases 1–4 done (EVM, Solana, Cosmos + sui/aptos/near/xrp/stellar/tron/ton) — 230 tests
- pyproject.toml optional-dep groups NOT yet added for Phase 4 — add if installing from scratch

## Phase 4 handler notes
- xrpl-py and stellar-sdk installed; pysui, aptos-sdk, py-near, tronpy, tonsdk NOT installed
- sui/aptos use aiohttp HTTP POST to public faucet URL (no SDK needed for native drip)
- near/tron/ton use aiohttp + cryptography for raw JSON-RPC; cryptography also NOT in venv
- near/tron/ton get_faucet_balance always returns "no wallet configured" (address derivation unavailable without cryptography)
- Stellar: network passphrase derived via _get_network_passphrase() from config["network"] — never hardcode Network.TESTNET_NETWORK_PASSPHRASE

## aiohttp async mock pattern (Phase 4 handlers)
- Patch at `handlers.<name>.aiohttp.ClientSession`; both session and response need `__aenter__`/`__aexit__` as AsyncMock
