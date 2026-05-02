# TODO

Known gaps and future work. Items are grouped by effort and dependency.

---

## Faucet harvester — keep faucet wallets continuously topped off

A background job that hits external faucets on behalf of the tool's own wallets, so
balances never run dry between runs. Distinct from the existing `_auto_top` in
`core/monitor.py`, which only handles chains where the handler can self-drip (currently
just Solana `request_airdrop`). The harvester targets third-party faucet APIs that
accept a wallet address and dispense coins directly.

- [ ] Extend `chains.yaml` with an optional `harvest_url` field (alongside the existing
  `faucet_url` used for user-facing drips)
  - `harvest_url` points to a machine-callable endpoint that accepts a wallet address
    and tops it up (e.g. Holesky ETH faucets with API keys, Stellar Friendbot, XRP
    altnet faucet, Sui/Aptos devnet faucets)
  - Add `harvest_min_balance` (optional float) — only request a top-up when the wallet
    falls below this level; defaults to `2 × drip_amount` if absent

- [ ] Implement `core/harvester.py`
  - `harvest_asset(asset_id, cfg, handler) -> HarvestResult` — checks balance, skips if
    above threshold, POSTs to `harvest_url` with the faucet address, records outcome
  - `harvest_all(family=None) -> list[HarvestResult]` — iterates native assets with a
    `harvest_url`, calls `harvest_asset` for each, respects per-asset cooldown (store
    last-harvest timestamp in the rate-limit SQLite DB under a `harvests` table)
  - Cooldown should be at least 23 h for external faucets that enforce a 24 h window

- [ ] Add `faucet harvest [--family FAMILY] [--force]` CLI command in `cli.py`
  - `--force` bypasses the cooldown check (useful after a wallet is drained)
  - Prints a Rich table: asset | current balance | harvest result | next eligible time

- [ ] Integrate with the monitor daemon (`core/monitor.py` / `faucet monitor`)
  - Add `--harvest` flag to `faucet monitor`: after each check pass, call `harvest_all()`
    for any LOW wallet that has a `harvest_url` before firing the low-balance alert
  - This makes the daemon self-healing: alert only fires if the harvest also failed

- [ ] Tests
  - Unit-test `harvest_asset` by patching `aiohttp.ClientSession` (same pattern as
    Phase 4 handler tests in `tests/test_handlers_*.py`)
  - Integration-test the CLI via `CliRunner`, asserting the results table and exit code

---

## Refactoring

- [ ] Split `config/chains.yaml` (1662 lines) into one file per chain family
  - Create `config/chains/` directory with files like `evm.yaml`, `solana.yaml`, `cosmos.yaml`, `utxo.yaml`, etc.
  - Change `core/registry.py`'s `_get_chains_yaml_path()` to glob `config/chains/*.yaml` and merge all dicts
  - Update `conftest.py`'s restore fixture to handle the directory instead of the single file
  - Update `tui/data.py`'s `save_chains_yaml()` to write back the correct per-family file (look up asset's `family` field to pick the target file)
  - Benefit: each file becomes ~50-150 lines instead of 1662; edits are localised and git diffs are readable

---

## SDK stubs — handlers that drip but return "SDK not installed"

Each handler follows the same fix pattern: (1) add dep group to `pyproject.toml`, (2) `uv sync --extra <family>`,
(3) read the SDK's testnet transfer docs, (4) replace the stub error in `drip()` with real signing logic,
(5) write/update unit tests patching the SDK client. The `get_faucet_balance()` implementation is already
live for most of these — only `drip()` is stubbed.

- [ ] **Hedera** (`handlers/hedera.py`) — requires `hedera-sdk-py`
  - Implement using `TransferTransaction` from `hedera-sdk-py`; authenticate with `FAUCET_HEDERA_ACCOUNT_ID` + `FAUCET_MNEMONIC`
  - Hedera testnet explorer: https://hashscan.io/testnet

- [ ] **Algorand** (`handlers/algorand.py`) — requires `py-algorand-sdk`
  - Implement using `algosdk.transaction.PaymentTxn`; sign with private key derived from `FAUCET_MNEMONIC`
  - Use the Algonode testnet node (`https://testnet-api.algonode.cloud`) already in `chains.yaml`

- [ ] **EOS** (`handlers/eos.py`) — requires `eospy`
  - Implement using `eospy.cleos.Cleos`; broadcast a `transfer` action on the `eosio.token` contract
  - EOS testnet faucet and node info: https://developers.eos.io/

- [ ] **Stacks** (`handlers/stacks.py`) — requires stacks SDK
  - Verify the correct PyPI package (`stacks-transactions` or similar) before installing
  - Implement STX transfer using the Stacks transaction builder; sign with key derived from `FAUCET_STACKS_ADDRESS`

- [ ] **VeChain** (`handlers/vechain.py`) — requires `thor-devkit`
  - Implement using `thor-devkit`'s `Transaction` builder; broadcast via the VeChain Thor REST API
  - Testnet node is already configured in `chains.yaml`

- [ ] **Tezos** (`handlers/tezos.py`) — requires `pytezos`
  - Implement using `pytezos.key.sign` + the Tezos RPC `injection/operation` endpoint
  - Use the Ghostnet testnet node already in `chains.yaml`

- [ ] **Substrate** (`handlers/substrate.py`) — requires `substrate-interface` (covers Polkadot, Polymesh)
  - Implement using `SubstrateInterface.compose_call("Balances", "transfer")` + `sign_and_submit_extrinsic`
  - Polkadot testnet (Westend) and Polymesh testnet nodes already in `chains.yaml`

- [ ] **Flow** (`handlers/flow.py`) — requires Flow SDK
  - Verify whether a Python Flow SDK exists on PyPI; if not, implement via the Flow REST API using `aiohttp` (same pattern as `sui.py`)
  - Flow testnet access tokens available at https://faucet.flow.com

- [ ] **ICP** (`handlers/icp.py`) — requires `ic-py` or `dfx` CLI
  - Prefer `ic-py` (pure Python); fall back to `dfx` subprocess if signing is unavailable
  - ICP ledger canister transfer docs: https://internetcomputer.org/docs/current/developer-docs/defi/icp-tokens/ledger-local-setup

- [ ] **Avalanche P-Chain** (`handlers/avalanche.py`) — requires avalanche SDK
  - Verify PyPI package name (`avalanche-python` or similar)
  - P-Chain transfers use the Avalanche platform API (`/ext/P`); Fuji testnet node already in `chains.yaml`

---

## Cryptography dependency — wallet address derivation blocked

The `cryptography` package is already used by the handlers but not installed. This is a single install
that unblocks address derivation for four families. Do this before working on those handlers' SDK stubs.

- [ ] Add `cryptography` dep groups to `pyproject.toml` first (see Packaging section above), then run:
  `uv sync --extra near --extra tron --extra ton --extra utxo`

- [ ] Verify address derivation works: run `faucet init near`, `faucet init tron`, `faucet init ton`, `faucet init utxo` — each should print a derived address instead of an error

- [ ] Verify balance queries work: run `faucet status --family near` (and tron/ton) — should return real on-chain balances instead of "no wallet configured"

---

## TBD assets — `rpc_url` not yet set (26 assets)

Pure research task — no code changes needed, only `chains.yaml` updates. For each asset, find the
chain's official public testnet RPC endpoint (check official docs, GitHub, or the chain's Discord
`#developer-resources` channel). Confirm the URL responds before committing it.

**EVM (12 assets)** — use a standard `eth_blockNumber` JSON-RPC call to verify any candidate URL:

- [ ] `THYPEEVM` — Hyperliquid EVM testnet; check https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/evm
- [ ] `TIP` — IoTeX testnet; check https://developers.iotex.io/ for testnet RPC
- [ ] `TJOVAYETH` — Jovay testnet; check Jovay official docs (chain is relatively new)
- [ ] `TMON` — Monad testnet; check https://docs.monad.xyz/ — Monad has had public testnet phases
- [ ] `TSONEIUM` — Soneium testnet (Sony's L2); check https://docs.soneium.org/
- [ ] `TSONIC` — Sonic testnet (formerly Fantom); check https://docs.soniclabs.com/
- [ ] `TWORLD` — World Chain testnet (Worldcoin L2); check https://docs.world.org/
- [ ] `TXPL` — XRP EVM sidechain testnet; check https://opensource.ripple.com/docs/evm-sidechain/intro-to-evm-sidechain/
- [ ] `TOG` — OG Chain testnet; check chain's official site for testnet node info
- [ ] `TJOVAYETH:USDCE` — blocked on `TJOVAYETH` rpc_url; resolve parent first, then find USDC.e contract address
- [ ] `TWORLD:USDC` — blocked on `TWORLD` rpc_url; resolve parent first, then find USDC contract address
- [ ] `TWORLD:WLD` — blocked on `TWORLD` rpc_url; resolve parent first, then find WLD contract address

**Cosmos (5 assets)** — verify candidate URLs with a `GET /cosmos/base/tendermint/v1beta1/blocks/latest` request:

- [ ] `TBLD` — Build chain testnet; check chain's GitHub or Cosmos chain registry (github.com/cosmos/chain-registry)
- [ ] `TCRONOS` — Cronos testnet; check https://docs.cronos.org/ — Cronos has a public testnet
- [ ] `TINITIA` — Initia testnet; check https://docs.initia.xyz/ — Initia has had active testnets
- [ ] `TBABY` — Baby chain testnet; check chain registry or chain's Discord for testnet node
- [ ] `TTHORCHAIN:RUNE` — THORChain stagenet; check https://docs.thorchain.org/ — stagenet is the public test environment

**UTXO (5 assets)** — verify candidate URLs with an address balance API call; most have public Electrum or REST APIs:

- [ ] `TBCH` — Bitcoin Cash testnet (chipnet); check https://docs.bitcoincashnode.org/ or use `chipnet.imaginary.cash` Fulcrum server
- [ ] `TBTG` — Bitcoin Gold testnet; check https://bitcoingold.org/ — less active chain, testnet may be unmaintained
- [ ] `TLTC` — Litecoin testnet; check https://litecoinspace.org/testnet for block explorer API
- [ ] `TDOGE` — Dogecoin testnet; check https://dogechain.info/ or use a public Electrum testnet server
- [ ] `TDASH` — Dash testnet; check https://docs.dash.org/ for testnet Insight API endpoint

**Phase 6 TBD handlers (no RPC + no SDK) — these need both an RPC URL and an SDK implementation:**

- [ ] `TTAO` — Bittensor testnet; check https://docs.bittensor.com/ for testnet node + Python SDK (`bittensor` on PyPI)
- [ ] `TCANTON` — Canton Network; enterprise/permissioned chain — check https://www.canton.network/ for testnet access
- [ ] `TADA` — Cardano testnet (Preprod); public RPC via Blockfrost (`https://cardano-preprod.blockfrost.io/api/v0`) — requires API key + `PyCardano` or `cardano-python`
- [ ] `TZEC` — Zcash testnet; check https://z.cash/ — lightwalletd server at `testnet.lightwalletd.com:9067`; requires `zcash-mini` or raw gRPC

---

## TBD assets — `contract_address` not yet set (38 EVM tokens + 3 Tron tokens)

For each token, find the verified testnet contract on the relevant block explorer. Many popular tokens
(USDT, USDC) have official testnet deployments; others may only exist on mainnet. If a testnet contract
genuinely does not exist, mark the entry with a comment in `chains.yaml` so it is not revisited.

- [ ] Audit all 38 EVM token entries with `contract_address: "TBD"`
  - Group by chain and work through one chain at a time
  - For each token, search the chain's testnet block explorer by token name (e.g. Holesky Etherscan → search "USDC")
  - Cross-reference with the token project's official docs for their testnet contract address
  - Reference block explorers by chain: Holesky → https://holesky.etherscan.io, Arbitrum Sepolia → https://sepolia.arbiscan.io, Base Sepolia → https://sepolia.basescan.org, etc.

- [ ] Audit 3 Tron token entries with `contract_address: "TBD"`
  - Use Tronscan Shasta testnet explorer: https://shasta.tronscan.org/
  - Tron testnet token contracts are often deployed by the projects themselves — check their docs

---

## TBD assets — `mint_address` not yet set (10 Solana SPL tokens)

For each SPL token, find its devnet mint address. Many projects publish their devnet deployment in docs
or Discord. If no devnet deployment exists, the entry should be commented out in `chains.yaml`.
Use `spl-token display <mint-address>` (Solana CLI) to confirm a candidate address is a valid mint.

- [ ] `TSOL:USDC` — Circle publishes official devnet USDC mint; check https://developers.circle.com/stablecoins/usdc-on-test-networks
- [ ] `TSOL:USDT` — Tether rarely deploys on devnet; check https://tether.to/en/supported-protocols/ or treat as mainnet-only
- [ ] `TSOL:USD1` — Check the USD1 project's docs for devnet deployment
- [ ] `TSOL:GMT` — STEPN/GMT; check https://docs.stepn.com/ or their Discord for devnet mint
- [ ] `TSOL:GARI` — Check Gari Network docs for devnet mint address
- [ ] `TSOL:ORCA` — Orca DEX; check https://docs.orca.so/ — Orca has a devnet deployment
- [ ] `TSOL:RAY` — Raydium; check https://docs.raydium.io/ for devnet token mint
- [ ] `TSOL:SLND` — Solend; check https://docs.solend.fi/ for devnet mint address
- [ ] `TSOL:SRM` — Serum (deprecated project); may not have an active devnet mint — consider removing
- [ ] `SOL:FORD` — Verify what chain/network this belongs to and whether a mint address exists; the non-`T` prefix suggests mainnet

---

## Future features

Quality-of-life improvements — none block core functionality. Each has a pointer to where the change lands in the codebase.

- [ ] `faucet tui` — Config Editor: support saving alert channel credentials (currently `alerts.yaml` is read-only in the TUI)
  - `tui/data.py` already has `save_chains_yaml()`; add a parallel `save_alerts_yaml()` function
  - Add form input widgets to `tui/screens/config_editor.py` for Slack webhook URL, email SMTP settings, etc.

- [ ] `faucet drip` — add `--gas-limit` override for EVM chains with non-standard gas requirements
  - Add optional `gas_limit: int` param to `handlers/evm.py`'s `drip()` signature (falls back to `estimate_gas`)
  - Thread the CLI flag through `cli.py`'s `drip` command → `registry.get_handler().drip()`

- [ ] `faucet batch` — add retry logic (currently no retries, unlike single `drip`)
  - In `cli.py`'s `batch` command loop, replace the bare `handler.drip()` call with `retry_drip()` from `core/retry.py`
  - Add a `--no-retry` flag to opt out for large batches where speed matters more than reliability

- [ ] `faucet check` — add `--format json` flag for CI pipeline integration
  - In `cli.py`'s `check` command, collect results into a list of dicts, then `json.dump()` instead of Rich table when `--format json` is passed
  - Useful for piping into monitoring systems or Slack bots

- [ ] Rate limiter — add `faucet rate-reset <asset> <address>` admin command to manually clear a cooldown
  - Add a `reset(asset_id, address)` method to `core/rate_limiter.py` that deletes the relevant row from SQLite
  - Wire up a new `rate-reset` Click command in `cli.py`

- [ ] Publish to PyPI so `uv tool install testnet-faucet` works without cloning the repo
  - Add a GitHub Actions workflow: on tag push, run `uv build` then `uv publish` using a PyPI token secret
  - Decide on the published package name (`testnet-faucet` is taken — check PyPI first)
  - Ensure all optional dep groups are in `pyproject.toml` before publishing (see Packaging section)
