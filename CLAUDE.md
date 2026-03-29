# Testnet Faucet Tool

## Environment
- Python venv: `.venv/` in project root — use absolute path, worktrees share it
- Run tests: `.venv/bin/python -m pytest tests/ -q`
- Install deps: `.venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[<extras>,dev]"`
- `config/chains.yaml` is auto-restored by `conftest.py` if deleted — don't worry about it
- Outside pytest, run `git restore config/` first if config/ is missing — conftest only restores during test sessions

## Architecture
- Handlers in `handlers/<family>.py` extending `BaseHandler` (4 abstract methods: `drip`, `validate_address`, `get_faucet_balance`, `supported_assets`)
- Registry in `core/registry.py` maps family names to handler classes via `FAMILY_HANDLER_MAP`
- New handler: add to `FAMILY_HANDLER_MAP`, create `handlers/<family>.py`, add optional dep group to `pyproject.toml`

## Testing conventions
- Unit tests: patch client constructor at module level (e.g. `patch("handlers.cosmos.LedgerClient", ...)`)
- Integration tests: `CliRunner` + synchronous `def` (CLI calls `asyncio.run()` internally — no nesting)
- Rate limiter isolation: `monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")`
- History log isolation: `monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")`
- Async tests use `@pytest.mark.asyncio` (mode set to `auto` in `pyproject.toml`)

## cosmpy gotchas (Cosmos handler)
- `NetworkConfig` URL must start with `rest+https://` or `grpc+https://` — prepend `rest+` to plain URLs
- `NetworkConfig` is in `cosmpy.aerial.config`, not `cosmpy.aerial.client`
- `SubmittedTx.tx_hash` (property) and `.wait_to_complete()` return the same `SubmittedTx`

## Rich + CliRunner
- `console.print(table)` truncates wide columns in narrow test terminals — print key values (addresses, hashes) on their own line before/after tables so tests can assert on them

## Phase completion
- Phases 1–7 done (EVM, Solana, Cosmos, Phase 4 chains, UTXO, Remaining, Polish) — 531 tests
- pyproject.toml optional-dep groups NOT yet added for Phase 4 — add if installing from scratch

## Phase 4 handler notes
- xrpl-py and stellar-sdk installed; pysui, aptos-sdk, py-near, tronpy, tonsdk NOT installed
- sui/aptos use aiohttp HTTP POST to public faucet URL (no SDK needed for native drip)
- near/tron/ton use aiohttp + cryptography for raw JSON-RPC; cryptography also NOT in venv
- near/tron/ton get_faucet_balance always returns "no wallet configured" (address derivation unavailable without cryptography)
- Stellar: network passphrase derived via _get_network_passphrase() from config["network"] — never hardcode Network.TESTNET_NETWORK_PASSPHRASE

## Phase 5 handler notes (UTXO)
- bitcoinlib, bit NOT installed — utxo.py uses raw secp256k1 math (same pattern as tron.py)
- cryptography also NOT in venv — _get_faucet_address raises RuntimeError, handler returns "no wallet configured"
- 5 of 6 UTXO assets have `rpc_url: TBD` — `_drip_native` guards on this before any network call
- TBTC4 uses Blockstream API: UTXO fetch, raw tx build, broadcast via POST to /tx

## aiohttp async mock pattern (Phase 4 handlers)
- Patch at `handlers.<name>.aiohttp.ClientSession`; both session and response need `__aenter__`/`__aexit__` as AsyncMock

## Phase 6 handler notes (Remaining chains)
- 14 handlers: hedera, algorand, substrate, eos, stacks, flow, vechain, tezos, avalanche_p, icp, cardano, zcash, bittensor, canton
- No Phase 6 SDKs installed — all use aiohttp for balance queries, drip returns "SDK not installed" errors
- TBD handlers (cardano, zcash, bittensor, canton): guard on `rpc_url == "TBD"`, no network calls
- SDK-stub handlers (substrate, flow, icp, avalanche_p): drip returns "requires X SDK" error; balance returns static message
- Real-API handlers (hedera, algorand, eos, stacks, tezos, vechain): drip returns SDK error, but get_faucet_balance makes real API calls
- Wallet env vars per handler: FAUCET_HEDERA_ACCOUNT_ID, FAUCET_EOS_ACCOUNT, FAUCET_ALGORAND_ADDRESS, FAUCET_STACKS_ADDRESS, FAUCET_TEZOS_ADDRESS, FAUCET_VECHAIN_ADDRESS
- CLI init commands added for all 14 families in cli.py

## Phase 7 notes (Polish)
- New CLI commands: `batch`, `refill`, `dashboard`, `history`
- `core/retry.py` — `retry_drip()` with exponential backoff; only retries transient errors (not TBD/validation)
- `core/logger.py` — JSON lines logging to `~/.testnet-faucet/history.log`; `LOG_PATH` is monkeypatchable like `DB_PATH`
- History log isolation: `conftest.py` has autouse fixture redirecting `LOG_PATH` to `tmp_path`
- cli.py `list` command shadows Python builtin `list()` — use `next(iter(...))` instead of `list(...)` in cli.py module scope

## Naming conventions
- `chains.yaml` note fields saying "verify BitGo ID before implementing" are intentional — they reference BitGo's external asset ID system and should not be removed
- Error message strings in core/ are not test-covered — check for stale env var names when renaming variables (caught: BITGO_FAUCET_DB_PATH in rate_limiter.py error message survived Phase 8 rename)

## Monitoring (Phase 8)
- Data directory renamed: `~/.bitgo-faucet/` → `~/.testnet-faucet/`
- Env vars renamed: `BITGO_FAUCET_DB_PATH` → `FAUCET_DB_PATH`, `BITGO_FAUCET_LOG_PATH` → `FAUCET_LOG_PATH`
- Alert config: `~/.testnet-faucet/alerts.yaml` (or `FAUCET_ALERTS_CONFIG` env var); template at `config/alerts.yaml.example`
- New commands: `faucet check` (one-shot, exit 1 on LOW/ERROR), `faucet monitor --interval 1h` (daemon)
- `core/alerting.py` — `send_alert(message, low_assets)` dispatches to log/Slack/webhook/email; `ALERTS_LOG_PATH` monkeypatchable in tests
- `core/monitor.py` — `check_all()`, `run_check()`, `_parse_interval()`; monkeypatch `core.alerting.ALERTS_CONFIG_PATH` and `core.alerting.ALERTS_LOG_PATH` in tests
- Auto-top: set `refill_source: airdrop` (or `external_faucet`) in chains.yaml; handler must implement `get_faucet_address()` returning non-None
- Alert log rotation: `TimedRotatingFileHandler(when="midnight")`, `backup_count` days retained (default 30)
- Cron example: `0 * * * * /path/to/.venv/bin/python -m faucet check >> ~/.testnet-faucet/cron.log 2>&1`
