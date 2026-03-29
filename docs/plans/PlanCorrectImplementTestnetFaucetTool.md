# Plan: Correct & Implement Testnet Faucet Tool

## Context

The FaucetFrameworkPlan.md was reviewed for implementation readiness. The architecture is strong (plugin-per-family, HD wallets, phased by ROI), but there are **5 high-severity issues** and **7 medium/low issues** that must be fixed before writing code. This plan corrects the design doc first, then provides atomic, session-independent phase instructions for implementation using parallel agents and adversarial review.

---

## Corrections to Apply to FaucetFrameworkPlan.md

### C1. Fix asset/chain counts (throughout)

| Section | Claims | Actual | Fix |
|---------|--------|--------|-----|
| Phase 1 / EVM | 32 chains, 66 assets | 34 native + 38 tokens = 72 | Update to "34 chains, 72 assets" |
| Phase 5 / UTXO | 5 chains, 7 assets | 7 entries, 6-7 chains | Update to "7 chains, 7 assets" |
| Remaining Standalone | 12 assets | 18 entries | Update to "18 assets" |
| Timeline table | Cumulative % | All wrong downstream | Recalculate all percentages |

### C2. Remove duplicates / fix naming collisions

- **TTON**: Remove duplicate from "Remaining Standalone Chains" (keep under "TON" section)
- **TUSDC in Stellar**: Rename to `TXLM:USDC` or verify actual Custodian asset ID
- **HTETH in Stellar**: Remove or replace with actual Stellar ETH asset ID (e.g., `TXLM:ETH`)
- **GHCN, GHDO, SOL:FORD**: Flag as "unconfirmed testnet assets — verify Custodian IDs before implementing"

### C3. Add missing TPOLYGON native coin

```yaml
TPOLYGON:
  family: evm
  blockchain: Polygon
  network: amoy
  rpc_url: TBD
  native_asset: true
  drip_amount: "0.1"
  decimals: 18
```

Note: `TMATIC` = ERC-20 on Ethereum, NOT Polygon native. Clarify in plan.

### C4. Move TAVAXP out of EVM family

Create `avalanche.py` handler for P-Chain. Keep TAVAXC in EVM handler. Move TAVAXP to Phase 6.

### C5. Resolve architecture decisions

- **Async**: `asyncio.run()` in Click command body
- **Wallet encryption**: `sops` with `age` backend
- **Funding preference**: Self-funded first, external faucet fallback (flip Section 3.5)
- **Rate limiter**: Add per-source TTL tracking for external APIs

### C6. Fix TCANTON classification

Move out of UTXO → Phase 6 standalone handler or defer.

### C7. Fix Phase 0 deliverable

Populate `chains.yaml` with all registry entries (metadata only) in Phase 0 so `faucet list` prints real data.

---

## Implementation Protocol

Each phase below is designed to be **executed atomically in a fresh session** with cleared context. Every phase has three sections:

- **BEFORE** — Context to load, decisions already made, entry criteria
- **WORK** — What to build, using parallel agents where tasks are independent
- **AFTER** — Adversarial review agent critiques the phase output

### Agent Strategy

- **Implementation agents**: Use `subagent-driven-development` pattern — dispatch parallel agents for independent tasks within each phase
- **Adversarial review agent**: After each phase, dispatch a `superpowers:code-reviewer` agent with explicit instructions to find flaws, missed edge cases, and deviations from the plan. It should be given the original plan AND the phase requirements as context.

---

## Phase 0 — Corrections + Skeleton

### BEFORE (Session Bootstrap)

```
Read these files to establish context:
- docs/plans/FaucetFrameworkPlan.md (the design doc)
- This plan file (for corrections C1-C7)

Entry criteria: None — this is the first phase.
Decisions already made:
- Async via asyncio.run() in Click commands
- Wallet encryption via sops + age
- Self-funded wallets preferred over external faucets
- Rate limiter tracks per-source TTLs
```

### WORK (Parallel Agents)

**Agent 1: Apply corrections to design doc**
- Apply corrections C1-C7 to `docs/plans/FaucetFrameworkPlan.md`
- Recount all asset IDs in Section 6 and update Section 5 timeline table
- Verify no duplicate asset IDs across sections
- Verify every token has a corresponding native coin entry

**Agent 2: Scaffold project structure**
- Create `pyproject.toml` with dependencies: `click`, `pyyaml`, `aiohttp`, `web3`, `sops` integration
- Create directory structure: `cli.py`, `config/`, `core/`, `handlers/`, `tests/`
- Implement `BaseHandler` abstract class in `handlers/base.py`
- Implement `DripResult` dataclass
- Implement `registry.py` — loads `chains.yaml`, resolves chain family → handler
- Implement Click CLI skeleton: `list`, `status`, `drip` (stubbed)

**Agent 3: Populate chains.yaml + rate limiter**
- Create `config/chains.yaml` with ALL asset entries (metadata only — RPC URLs, explorer templates, drip amounts, decimals)
- Research and fill RPC URLs for all chains (use public endpoints)
- Implement SQLite rate limiter in `core/rate_limiter.py` with per-source TTL tracking
- Create `config/wallets.yaml.example` template

### AFTER (Adversarial Review)

```
Dispatch code-reviewer agent with prompt:
"Review Phase 0 implementation against the corrected FaucetFrameworkPlan.md. Check:
1. Does `faucet list` print all assets from chains.yaml?
2. Are all corrections C1-C7 applied to the design doc?
3. Does chains.yaml have entries for every asset in Section 6?
4. Is BaseHandler interface exactly as specified (drip, validate_address, get_faucet_balance, supported_assets)?
5. Does the rate limiter support per-source TTLs?
6. Is TAVAXP absent from EVM family? Is TCANTON absent from UTXO?
7. Are there any import errors, missing __init__.py files, or broken CLI entrypoints?
Flag every deviation, no matter how small."
```

**Exit criteria**: `faucet list` runs and prints all assets. Design doc corrections verified. Rate limiter has tests.

---

## Phase 1 — EVM Family

### BEFORE (Session Bootstrap)

```
Read these files to establish context:
- docs/plans/FaucetFrameworkPlan.md (corrected in Phase 0)
- handlers/base.py (BaseHandler interface)
- core/registry.py (how chains.yaml maps to handlers)
- config/chains.yaml (EVM entries specifically)
- pyproject.toml (current dependencies)

Entry criteria: Phase 0 complete. `faucet list` works.
Key decisions:
- All EVM chains share one HD-derived address (same mnemonic, BIP-44 m/44'/60'/0'/0/0)
- ERC-20 transfers use standard transfer(address,uint256) ABI
- TPOLYGON native coin is included. TAVAXP is excluded (Phase 6).
- Async handlers wrapped with asyncio.run() in CLI
```

### WORK (Parallel Agents)

**Agent 1: EVM handler — native transfers**
- Implement `handlers/evm.py` with `EvmHandler(BaseHandler)`
- Native coin transfer via `web3.eth.send_transaction()`
- Address validation via `eth_utils.is_address()`
- Balance checking via `web3.eth.get_balance()`
- HD wallet derivation from mnemonic (BIP-44, coin type 60)
- `supported_assets()` returns all native EVM assets from registry
- Unit tests for address validation, tx construction (mocked web3)

**Agent 2: EVM handler — ERC-20 transfers**
- Add ERC-20 `transfer()` method to `EvmHandler`
- Standard ERC-20 ABI (just `transfer` and `balanceOf`)
- Gas estimation for token transfers
- `get_faucet_balance()` checks both native and token balances
- Registry lookup for `contract_address` field
- Unit tests for token transfer construction

**Agent 3: CLI integration + wallet init**
- Wire `EvmHandler` into `cli.py drip` command
- Implement `faucet init evm` — derive addresses, print for manual funding
- Implement `faucet drip HTETH <address>` end-to-end flow
- Implement `faucet status` showing EVM faucet wallet balances
- Integration test: drip flow with mocked RPC
- Verify token ordering: warn if recipient lacks native coin for gas when requesting ERC-20

### AFTER (Adversarial Review)

```
Dispatch code-reviewer agent with prompt:
"Review Phase 1 EVM implementation. Check:
1. Does EvmHandler implement ALL BaseHandler abstract methods?
2. Can `faucet drip HTETH <address>` execute end-to-end (with mocked RPC)?
3. Does ERC-20 transfer include gas estimation?
4. Does `faucet init evm` derive correct BIP-44 addresses?
5. Is TPOLYGON included? Is TAVAXP excluded?
6. Does the drip command warn when ERC-20 is requested but recipient has no native coin?
7. Are there any hardcoded RPC URLs that should come from chains.yaml?
8. Is error handling consistent (DripResult with success=False, not exceptions)?
9. Test coverage: are there tests for address validation, native transfer, ERC-20 transfer, gas check?
Flag every deviation from the plan."
```

**Exit criteria**: `faucet drip HTETH <address>` works with a real Holesky RPC (dry-run mode acceptable). All 72 EVM assets are registered and routed to EvmHandler.

---

## Phase 2 — Solana

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (Solana section)
- handlers/base.py, handlers/evm.py (pattern to follow)
- core/registry.py
- config/chains.yaml (Solana entries)

Entry criteria: Phase 1 complete. EVM drip works.
Key decisions:
- Native SOL uses requestAirdrop (no wallet needed)
- SPL tokens require a funded wallet + associated token accounts
- 12 assets total (1 native + 11 SPL tokens)
```

### WORK (Parallel Agents)

**Agent 1: Solana handler**
- Implement `handlers/solana.py` with `SolanaHandler(BaseHandler)`
- Native SOL: `requestAirdrop` RPC call
- SPL token transfers via `spl.token` instructions
- Address validation (base58, 32 bytes)
- Balance checking (native + SPL)
- Unit tests

**Agent 2: CLI integration + registry**
- Wire SolanaHandler into registry and CLI
- Verify all 12 Solana assets route correctly
- Integration test: `faucet drip TSOL <address>` with devnet
- Handle edge case: SPL token account creation if recipient doesn't have one

### AFTER (Adversarial Review)

```
Dispatch code-reviewer agent with prompt:
"Review Phase 2 Solana implementation. Check:
1. Does requestAirdrop work for TSOL without requiring a wallet?
2. Does SPL transfer handle missing associated token accounts?
3. Are all 12 Solana assets registered and routed?
4. Does the handler follow the same patterns as EvmHandler?
5. Is there proper error handling for Solana rate limits on airdrop?
6. Test coverage for both native and SPL paths?
Flag every deviation."
```

**Exit criteria**: `faucet drip TSOL <address>` works against Solana devnet.

---

## Phase 3 — Cosmos Family

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (Cosmos section)
- handlers/base.py, handlers/evm.py (patterns)
- config/chains.yaml (Cosmos entries)

Entry criteria: Phase 2 complete.
Key decisions:
- HD derivation from shared mnemonic, per-chain SLIP-44 coin types
- Each Cosmos chain has unique bech32 prefix and denom
- 14 assets across 8+ chains
- Some chains have external faucet APIs as fallback
```

### WORK (Parallel Agents)

**Agent 1: Cosmos handler**
- Implement `handlers/cosmos.py` with `CosmosHandler(BaseHandler)`
- Native transfers via Cosmos REST API (`/cosmos/bank/v1beta1/send`)
- Address validation (bech32 with chain-specific prefix from registry)
- HD derivation with per-chain coin types
- Balance checking via REST API
- Unit tests

**Agent 2: External faucet integration**
- Add fallback external faucet calls where available (e.g., Cosmos Hub theta testnet faucet)
- Implement retry logic: try self-funded first, fall back to external
- Wire all 14 assets into registry
- Integration tests

### AFTER (Adversarial Review)

```
"Review Phase 3 Cosmos implementation. Check:
1. Does bech32 address validation use per-chain prefix from registry?
2. Does HD derivation use correct SLIP-44 coin types per chain?
3. Are all 14 Cosmos assets registered?
4. Is TTHORCHAIN:RUNE handled? (Thorchain is Cosmos-based but architecturally different)
5. Is TCRONOS correctly targeted (Cosmos POS, not Cronos EVM)?
6. Does fallback logic try self-funded first, then external?
7. Test coverage for address validation, transfer, balance check?
Flag every deviation."
```

**Exit criteria**: `faucet drip TATOM <address>` works against Cosmos theta testnet.

---

## Phase 4 — Easy API Chains

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (Phase 4 section + external faucet table)
- handlers/base.py (patterns)
- handlers/evm.py, handlers/solana.py, handlers/cosmos.py (established patterns)
- core/registry.py

Entry criteria: Phase 3 complete.
Key decisions:
- Each chain gets its own handler file
- External faucet APIs are primary for chains that offer them (Sui, Aptos, NEAR, XRP, Stellar)
- Self-funded transfer needed for tokens on each chain
- ~22 assets across 7 chains
```

### WORK (Parallel Agents — up to 5)

**Agent 1: Sui + Aptos handlers**
- `handlers/sui.py` — Sui devnet faucet API + Sui SDK transfers
- `handlers/aptos.py` — Aptos devnet faucet API + Aptos SDK transfers
- Address validation, balance checking, tests for both

**Agent 2: NEAR + XRP handlers**
- `handlers/near.py` — NEAR helper API + near-api-py transfers
- `handlers/xrp.py` — XRP testnet faucet API + xrpl-py transfers
- Address validation, balance checking, tests for both

**Agent 3: Stellar + Tron + TON handlers**
- `handlers/stellar.py` — Stellar friendbot + stellar-sdk transfers
- `handlers/tron.py` — TronGrid API + tronpy transfers
- `handlers/ton.py` — TON testnet faucet + tonsdk transfers
- Address validation, balance checking, tests for all three

**Agent 4: CLI wiring + registry**
- Wire all 7 new handlers into registry and CLI
- Verify all ~22 assets route correctly
- End-to-end integration tests for each handler

### AFTER (Adversarial Review)

```
"Review Phase 4 implementation — 7 new handlers. Check:
1. Does each handler implement ALL BaseHandler abstract methods?
2. Do external faucet calls have proper error handling and rate limit awareness?
3. Are all ~22 assets registered and routed to correct handlers?
4. TUSDC/HTETH naming collisions resolved for Stellar? (Must not conflict with EVM IDs)
5. Does each handler follow established patterns from evm.py?
6. Token transfers on each chain — do they check for native coin balance first?
7. Test coverage for each handler (address validation, native transfer, token transfer)?
8. Are there any hardcoded API URLs that should be in chains.yaml?
Flag every deviation."
```

**Exit criteria**: At least one handler per chain works against its testnet/devnet.

---

## Phase 5 — UTXO Family

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (UTXO section)
- handlers/base.py (patterns)
- config/chains.yaml (UTXO entries — TCANTON should NOT be here)

Entry criteria: Phase 4 complete.
Key decisions:
- UTXO chains need tx construction: input selection, output creation, signing, broadcast
- Consider BlockCypher API for BTC/LTC/DOGE to abstract UTXO management
- 6 assets (TBTC4, TBCH, TBTG, TLTC, TDOGE, TDASH) — TCANTON excluded
- HD derivation from shared mnemonic, per-chain BIP-44 coin types
```

### WORK (Parallel Agents)

**Agent 1: UTXO handler core**
- Implement `handlers/utxo.py` with `UtxoHandler(BaseHandler)`
- UTXO selection algorithm (simple: oldest-first or largest-first)
- Transaction construction, signing, broadcast
- Support for BlockCypher API as alternative backend
- Address validation (base58check + bech32 for BTC)
- HD derivation with per-chain coin types

**Agent 2: Per-chain configuration + tests**
- Configure all 6 UTXO chains in registry
- Handle chain-specific quirks (BCH address format, DOGE dust limits, etc.)
- Integration tests with mocked block explorer APIs
- Balance checking via block explorer APIs

### AFTER (Adversarial Review)

```
"Review Phase 5 UTXO implementation. Check:
1. Is TCANTON absent? (It's not UTXO)
2. Does UTXO selection handle edge cases (dust, insufficient funds)?
3. Is transaction signing correct for each chain's format?
4. Does BTC support both legacy and segwit addresses?
5. Are block explorer API calls abstracted (not hardcoded to one provider)?
6. Does HD derivation use correct coin types (BTC=0, LTC=2, DOGE=3, etc.)?
7. Test coverage for tx construction, signing, UTXO selection?
8. Does the handler properly handle change outputs?
Flag every deviation."
```

**Exit criteria**: `faucet drip TBTC4 <address>` constructs a valid transaction (dry-run mode acceptable).

---

## Phase 6 — Remaining Chains

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (Phase 6 + Remaining Standalone section)
- handlers/base.py (patterns)
- Any 2-3 existing handlers for reference patterns
- config/chains.yaml (remaining chain entries)

Entry criteria: Phase 5 complete.
Key decisions:
- Each chain is standalone — its own handler, its own SDK
- TAVAXP gets avalanche.py handler (P-Chain specific)
- TCANTON gets canton.py handler (Daml-based, NOT UTXO)
- ~29 assets across 12+ chains
- Some chains may need to be deferred if SDKs are unusable
```

### WORK (Parallel Agents — up to 5)

**Agent 1: Hedera + Cardano + Algorand**
- `handlers/hedera.py`, `handlers/cardano.py`, `handlers/algorand.py`
- Each with full BaseHandler implementation
- Tests for each

**Agent 2: Substrate family (Polkadot + Polymesh)**
- `handlers/substrate.py` covering TDOT and TPOLYX
- substrate-interface library
- Tests

**Agent 3: EOS + Stacks + Flow**
- `handlers/eos.py`, `handlers/stacks.py`, `handlers/flow.py`
- Tests for each

**Agent 4: VeChain + Tezos + Zcash**
- `handlers/vechain.py`, `handlers/tezos.py`, `handlers/zcash.py`
- Tests for each

**Agent 5: TAVAXP + TCANTON + ICP + Bittensor**
- `handlers/avalanche.py` (P-Chain only — C-Chain is in evm.py)
- `handlers/canton.py` (Daml-based, research needed)
- `handlers/icp.py`, `handlers/bittensor.py`
- Tests for each

### AFTER (Adversarial Review)

```
"Review Phase 6 implementation — 12+ new handlers. Check:
1. Does EVERY handler implement ALL BaseHandler abstract methods?
2. Is TAVAXP in avalanche.py, NOT evm.py?
3. Is TCANTON in canton.py, NOT utxo.py?
4. Are all ~29 remaining assets registered and routed?
5. Does substrate.py correctly handle both Polkadot and Polymesh?
6. Are there any handlers that silently return success without actually sending?
7. Test coverage for each handler?
8. Are deferred/unimplementable chains clearly marked in the registry?
9. Do GHCN, GHDO, SOL:FORD have verified asset IDs or are they still flagged?
Flag every deviation."
```

**Exit criteria**: All handlers exist. Chains that can't be implemented are documented with reasons.

---

## Phase 7 — Polish

### BEFORE (Session Bootstrap)

```
Read these files:
- docs/plans/FaucetFrameworkPlan.md (Phase 7 section)
- cli.py (current command set)
- core/rate_limiter.py
- core/reporter.py (if exists)

Entry criteria: Phase 6 complete. All handlers exist.
Key decisions:
- Batch command reads CSV: asset,address per line
- Parallel execution bounded by per-chain rate limits
- Rich library for terminal dashboard
- Retry with exponential backoff, max 3 attempts
```

### WORK (Parallel Agents)

**Agent 1: Batch command + retry logic**
- Implement `faucet batch fund wallets.csv`
- CSV parsing (asset,address pairs)
- Parallel execution with asyncio.gather(), bounded concurrency
- Native-before-token ordering enforced automatically
- Retry with exponential backoff in BaseHandler

**Agent 2: Monitoring + reporting**
- Implement `faucet status` dashboard (Rich library, terminal-based)
- Show all faucet wallet balances grouped by family
- Highlight low-balance wallets
- Implement `faucet refill` — shows which wallets are low + fund instructions
- Logging to `~/.testnet-faucet/history.log`

### AFTER (Adversarial Review)

```
"Final review of the complete faucet tool. Check:
1. Does `faucet batch` enforce native-before-token ordering?
2. Does retry logic respect per-source rate limits?
3. Does `faucet status` show balances for ALL registered chains?
4. Is the tool usable end-to-end: init → fund → drip → status?
5. Are there any TODO/FIXME comments left in the code?
6. Is wallets.yaml.example correct and documented?
7. Does README.md cover setup, usage, and adding new chains?
8. Run full test suite — all tests pass?
9. Any security issues (keys in logs, unencrypted wallets, injection)?
Flag every issue."
```

**Exit criteria**: Full test suite passes. `faucet drip`, `faucet batch`, `faucet status`, `faucet list`, `faucet init`, `faucet refill` all work.

---

## Updated Timeline

| Phase | Scope | Assets | Cumulative % | Agents |
|-------|-------|--------|-------------|--------|
| 0 | Corrections + Skeleton + chains.yaml | 0 working | 0% | 3 impl + 1 review |
| 1 | EVM | ~72 | 46% | 3 impl + 1 review |
| 2 | Solana | 12 | 54% | 2 impl + 1 review |
| 3 | Cosmos | 14 | 63% | 2 impl + 1 review |
| 4 | Easy API chains | ~22 | 77% | 4 impl + 1 review |
| 5 | UTXO | 6 | 81% | 2 impl + 1 review |
| 6 | Remaining | ~29 | 100% | 5 impl + 1 review |
| 7 | Polish | - | - | 2 impl + 1 review |

## Files to modify/create

**Phase 0 (corrections)**:
- `docs/plans/FaucetFrameworkPlan.md` — apply C1-C7

**Phase 0 (scaffold)**:
- `pyproject.toml`, `cli.py`, `config/chains.yaml`, `config/wallets.yaml.example`
- `core/__init__.py`, `core/registry.py`, `core/rate_limiter.py`, `core/address_validator.py`, `core/reporter.py`
- `handlers/__init__.py`, `handlers/base.py`
- `tests/` directory

**Phases 1-7**: Handler files as listed in each phase's WORK section.
