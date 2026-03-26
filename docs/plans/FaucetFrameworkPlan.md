# BitGo Testnet Faucet Tool — Framework Design & Implementation Plan

## 1. Problem Statement

Fund test wallets across **144 assets on 70+ blockchains** supported by BitGo. The tool must be:

- **Extensible** — adding a new chain shouldn't require rewriting the core
- **Personal-first** — designed for one engineer, structured to scale to a team
- **Practical** — native coins first (these fund gas), tokens second (these need the native coin already)

---

## 2. Architecture

The tool is a Python CLI with a plugin-per-chain-family design. Think of it like `git` — one entrypoint, many subcommands, each backed by a handler module.

```
bitgo-faucet/
├── cli.py                    # Main entrypoint (Click-based CLI)
├── config/
│   ├── chains.yaml           # Chain registry — RPC URLs, faucet sources, amounts
│   └── wallets.yaml          # Your funded wallet keys (gitignored, encrypted at rest)
├── core/
│   ├── __init__.py
│   ├── registry.py           # Loads chains.yaml, resolves chain family → handler
│   ├── rate_limiter.py       # Local SQLite-based rate limiter
│   ├── address_validator.py  # Dispatch validation by chain family
│   └── reporter.py           # Logs drip results, tracks balances
├── handlers/                 # One module per chain family
│   ├── __init__.py
│   ├── base.py               # Abstract base class for all handlers
│   ├── evm.py                # Covers ~32 chains
│   ├── cosmos.py             # Covers ~8 chains
│   ├── utxo.py               # Covers ~7 chains
│   ├── solana.py             # Solana + SPL tokens
│   ├── near.py               # NEAR + NEP-141 tokens
│   ├── sui.py                # Sui + Sui tokens
│   ├── aptos.py              # Aptos + Aptos tokens
│   ├── xrp.py                # XRP Ledger
│   ├── stellar.py            # Stellar + Stellar tokens
│   ├── tron.py               # Tron + TRC-20 tokens
│   ├── ton.py                # TON
│   ├── hedera.py             # Hedera + HTS tokens
│   ├── substrate.py          # Polkadot, Polymesh
│   ├── cardano.py            # Cardano
│   ├── stacks.py             # Stacks
│   ├── algorand.py           # Algorand
│   ├── eos.py                # EOS + EOS tokens
│   ├── flow.py               # Flow
│   ├── vechain.py            # VeChain
│   ├── tezos.py              # Tezos
│   ├── zcash.py              # Zcash
│   ├── icp.py                # Internet Computer
│   ├── bittensor.py          # Bittensor (Substrate-based, but different enough)
│   └── external_faucet.py    # Fallback: hits a third-party faucet API
├── tests/
│   ├── test_evm.py
│   └── ...
├── pyproject.toml
└── README.md
```

### 2.1 Handler Base Class

Every handler implements the same interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class DripResult:
    success: bool
    tx_hash: str | None
    explorer_url: str | None
    error: str | None
    amount: str
    asset: str

class BaseHandler(ABC):
    """One handler per chain family. Instantiated with chain-specific config."""

    @abstractmethod
    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to the given address."""
        ...

    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """Check if the address is valid for this chain."""
        ...

    @abstractmethod
    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current balance of the faucet wallet for monitoring."""
        ...

    @abstractmethod
    def supported_assets(self) -> list[str]:
        """Return list of BitGo testnet IDs this handler can process."""
        ...
```

### 2.2 Chain Registry (chains.yaml)

The registry maps BitGo testnet IDs to handler config. This is the single source of truth.

```yaml
# Example entries — full registry built incrementally per phase

# --- EVM Family ---
HTETH:
  family: evm
  blockchain: Ethereum
  network: holesky          # or sepolia
  rpc_url: https://rpc.holesky.ethpandaops.io
  explorer: https://holesky.etherscan.io/tx/{tx_hash}
  native_asset: true
  drip_amount: "0.05"
  decimals: 18

TUSDC:
  family: evm
  blockchain: Ethereum
  network: holesky
  rpc_url: https://rpc.holesky.ethpandaops.io
  explorer: https://holesky.etherscan.io/tx/{tx_hash}
  native_asset: false
  contract_address: "0x..."    # testnet USDC contract
  drip_amount: "10"
  decimals: 6

TARBETH:
  family: evm
  blockchain: Arbitrum
  network: sepolia
  rpc_url: https://sepolia-rollup.arbitrum.io/rpc
  explorer: https://sepolia.arbiscan.io/tx/{tx_hash}
  native_asset: true
  drip_amount: "0.01"
  decimals: 18

# --- Solana ---
TSOL:
  family: solana
  blockchain: Solana
  network: devnet
  rpc_url: https://api.devnet.solana.com
  explorer: https://explorer.solana.com/tx/{tx_hash}?cluster=devnet
  native_asset: true
  drip_amount: "0.1"
  decimals: 9
  funding_method: request_airdrop   # unique to Solana — no wallet needed

# --- Cosmos ---
TATOM:
  family: cosmos
  blockchain: Cosmos Hub
  network: theta-testnet-001
  rpc_url: https://rpc.sentry-01.theta-testnet.polypore.xyz
  explorer: https://explorer.theta-testnet.polypore.xyz/transactions/{tx_hash}
  native_asset: true
  denom: uatom
  drip_amount: "1"
  decimals: 6
```

### 2.3 CLI Interface

```bash
# Fund a single wallet
$ faucet drip TSOL 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU

# Fund multiple assets to the same address
$ faucet drip HTETH,TUSDC 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18

# Batch fund from a file (address per line, or CSV with asset,address pairs)
$ faucet batch fund wallets.csv

# Check faucet wallet balances
$ faucet status

# List all supported assets
$ faucet list
$ faucet list --family evm
$ faucet list --status funded    # only show chains where faucet wallet has balance

# Initialize faucet wallets for a chain family
$ faucet init evm               # generates wallets, prints addresses for manual funding
```

---

## 3. Key Design Decisions

### 3.1 Funding Model by Chain Family

| Family | Funding model | Notes |
|--------|---------------|-------|
| **Solana** | `requestAirdrop` RPC | Free, no wallet needed. Rate-limited by Solana. |
| **EVM** | Self-funded wallet | One wallet per chain. Same mnemonic → deterministic addresses via HD derivation. |
| **Cosmos** | Self-funded wallet | One wallet per chain. Some have public faucet APIs as fallback. |
| **UTXO** | Self-funded wallet | UTXO management required. Consider BlockCypher API for BTC/LTC. |
| **All others** | Self-funded or external faucet API | Chain-specific. Some (Sui, Aptos) have devnet faucet APIs. |

### 3.2 Wallet Management Strategy

Rather than managing 70 separate keypairs, use **HD wallet derivation** where possible:

- **EVM chains:** One BIP-39 mnemonic → derive per-chain wallets via BIP-44 paths. Same private key works across all EVM chains (same address on every chain).
- **Cosmos chains:** One mnemonic → derive per-chain wallets via SLIP-44 coin types.
- **UTXO chains:** One mnemonic → derive per-chain wallets.
- **Non-HD chains** (Solana, NEAR, Sui, etc.): Separate keypairs stored in `wallets.yaml`.

This means you manage **one mnemonic + a handful of chain-specific keys**, not 70 keys.

### 3.3 Token Funding Depends on Native Coin Funding

This is critical: **you can't send ERC-20 tokens without ETH for gas.** The tool should enforce ordering — when you request `TUSDC` (Ethereum USDC), it should check if the recipient has enough `HTETH` for gas and warn if not. The `batch` command should automatically fund native coins before tokens.

### 3.4 Local Rate Limiter

SQLite file at `~/.bitgo-faucet/rate_limits.db`. This is a personal tool, so the rate limiter is mainly a safety net against accidentally draining your faucet wallet with a loop. Simple TTL-based check, same logic as the web faucet but local.

### 3.5 External Faucet Fallback

Some chains have public faucet APIs that don't require a funded wallet:

| Chain | Public faucet API | Notes |
|-------|-------------------|-------|
| Solana Devnet | `requestAirdrop` RPC | Built-in |
| Sui Devnet | `https://faucet.devnet.sui.io/gas` | POST with address |
| Aptos Devnet | `https://faucet.devnet.aptoslabs.com/fund` | POST with address |
| NEAR Testnet | `https://helper.testnet.near.org/account` | Creates + funds accounts |
| XRP Testnet | `https://faucet.altnet.rippletest.net/accounts` | Creates + funds accounts |
| Google Cloud Faucet | Web-only (CAPTCHA-gated) | Not scriptable |

The `external_faucet.py` handler wraps these APIs as a zero-setup option for supported chains. When both methods exist, the tool should prefer the external faucet (free) and fall back to self-funded (reliable).

---

## 4. Phased Implementation Plan

### Phase 0 — Skeleton (Day 1)
- [ ] Project scaffold: `pyproject.toml`, CLI entrypoint, directory structure
- [ ] `BaseHandler` abstract class
- [ ] `chains.yaml` schema and loader (`registry.py`)
- [ ] `wallets.yaml` schema (encrypted with `age` or `sops`)
- [ ] CLI commands: `list`, `status`, `drip` (stubbed)
- [ ] SQLite rate limiter

**Deliverable:** `faucet list` works and prints all 144 assets from the registry.

### Phase 1 — EVM Family (Days 2–3)
Covers **32 chains, 66 assets** — almost half the entire scope.

- [ ] `evm.py` handler: native transfers + ERC-20 transfers
- [ ] Address validation via `eth_utils.is_address()`
- [ ] HD wallet derivation from mnemonic (all EVM chains share one key)
- [ ] Registry entries for all 32 EVM chains with RPC URLs
- [ ] `faucet init evm` — derive + display addresses for each chain
- [ ] `faucet drip HTETH <address>` end-to-end working
- [ ] ERC-20 token transfer (requires contract ABI — standard ERC-20 `transfer()`)

**Dependencies:** `web3.py`, `eth-account`, `eth-utils`

**Known risk:** Sourcing initial funds for 32 chains. Many have public faucets but they're manual/CAPTCHA-gated. This is a one-time bootstrapping pain. Document the faucet URL for each chain in the registry.

### Phase 2 — Solana (Day 3)
Covers **1 chain, 12 assets**.

- [ ] `solana.py` handler: `requestAirdrop` for native SOL
- [ ] SPL token transfers (for TSOL:USDC, TSOL:USDT, etc.)
- [ ] Address validation via `solders` or `solana-py`
- [ ] Registry entries for all 12 Solana assets

**Dependencies:** `solana-py` or `solders`

**Note:** SPL token transfers require a funded wallet (can't airdrop tokens). The native SOL airdrop is free. For tokens, you'll need to acquire testnet SPL tokens separately — there's no universal SPL faucet.

### Phase 3 — Cosmos Family (Days 4–5)
Covers **8 chains, 14 assets**.

- [ ] `cosmos.py` handler: native transfers via `cosmpy` or raw REST API
- [ ] Address validation (bech32 with chain-specific prefix)
- [ ] HD derivation from mnemonic with per-chain SLIP-44 coin types
- [ ] Registry entries for all Cosmos chains
- [ ] External faucet integration where available

**Dependencies:** `cosmpy` or `httpx` (many Cosmos chains have REST APIs)

### Phase 4 — "Easy API" Chains (Days 5–6)
Chains with scriptable faucet APIs or simple SDKs.

- [ ] `sui.py` — Sui devnet faucet API + Sui SDK transfers
- [ ] `aptos.py` — Aptos devnet faucet API + Aptos SDK transfers
- [ ] `near.py` — NEAR helper API + near-api-py transfers
- [ ] `xrp.py` — XRP testnet faucet API + xrpl-py transfers
- [ ] `stellar.py` — Stellar friendbot + stellar-sdk transfers
- [ ] `tron.py` — TronGrid API + tronpy transfers
- [ ] `ton.py` — TON testnet faucet + tonsdk transfers

**Dependencies:** `sui-py`, `aptos-sdk`, `near-api-py`, `xrpl-py`, `stellar-sdk`, `tronpy`, `tonsdk`

### Phase 5 — UTXO Family (Days 7–8)
Covers **5 chains, 7 assets**. Hardest family.

- [ ] `utxo.py` handler: UTXO selection, tx construction, signing, broadcast
- [ ] Bitcoin testnet (TBTC4) via BlockCypher or Blockstream API
- [ ] Litecoin testnet (TLTC)
- [ ] Dogecoin testnet (TDOGE)
- [ ] Dash testnet (TDASH)
- [ ] Bitcoin Cash testnet (TBCH)
- [ ] Canton (TCANTON) — research needed, may not be standard UTXO

**Dependencies:** `bitcoinlib` or `bit`, `httpx` for block explorer APIs

**Alternative:** Use BlockCypher's `/txs/new` endpoint which abstracts UTXO management. Trades reliability for simplicity.

### Phase 6 — Remaining Chains (Days 9–11)
Each of these is a standalone handler with its own SDK.

- [ ] `hedera.py` — Hedera SDK (`hedera-sdk-py`) or REST API
- [ ] `cardano.py` — `pycardano` library
- [ ] `algorand.py` — `py-algorand-sdk`
- [ ] `substrate.py` — Polkadot + Polymesh via `substrate-interface`
- [ ] `eos.py` — `eospy` or REST API
- [ ] `stacks.py` — Stacks API (STX testnet faucet exists)
- [ ] `flow.py` — Flow CLI or REST API
- [ ] `vechain.py` — `thor-devkit.py`
- [ ] `tezos.py` — `pytezos`
- [ ] `zcash.py` — Similar to UTXO, zcash-specific tooling
- [ ] `icp.py` — `ic-py` or dfx CLI wrapper
- [ ] `bittensor.py` — `bittensor` Python package

### Phase 7 — Polish (Day 12)
- [ ] `faucet batch` command — CSV input, parallel execution
- [ ] Balance monitoring dashboard (terminal-based, `rich` library)
- [ ] Retry logic with exponential backoff per handler
- [ ] Logging to `~/.bitgo-faucet/history.log`
- [ ] `faucet refill` — shows which faucet wallets are low, prints fund instructions

---

## 5. Estimated Timeline

| Phase | Scope | Assets covered | Cumulative % | Time |
|-------|-------|----------------|-------------|------|
| 0 | Skeleton | 0 | 0% | 1 day |
| 1 | EVM | 66 | 46% | 2 days |
| 2 | Solana | 12 | 54% | 0.5 day |
| 3 | Cosmos | 14 | 64% | 2 days |
| 4 | Easy API chains | 24 | 80% | 2 days |
| 5 | UTXO | 7 | 85% | 2 days |
| 6 | Remaining | 21 | 100% | 3 days |
| 7 | Polish | — | — | 1 day |
| **Total** | | **144** | **100%** | **~13.5 days** |

Phase 1 alone gets you to 46% coverage. Phases 1–4 get you to 80%. The long tail (UTXO + exotic chains) is the remaining 20% but takes 40% of the time.

---

## 6. Full Asset TODO List

Status key: `[ ]` = not started, `[~]` = handler exists but asset not configured, `[x]` = working

### EVM Family (32 chains, 66 assets)

**Native coins:**
- [ ] HTETH — Ethereum (Holesky)
- [ ] TARBETH — Arbitrum Sepolia
- [ ] TAVAXC — Avalanche C-Chain Fuji
- [ ] TAVAXP — Avalanche P-Chain Fuji
- [ ] TBASEETH — Base Sepolia
- [ ] TBERA — Berachain Testnet
- [ ] TBSC — BNB Smart Chain Testnet
- [ ] TCELO — Celo Alfajores
- [ ] TCOREDAO — CoreDAO Testnet
- [ ] TETC — Ethereum Classic Mordor
- [ ] TFLR — Flare Coston2
- [ ] THYPEEVM — Hyperliquid EVM Testnet
- [ ] TIP — Story Testnet
- [ ] TIOTA — IOTA Testnet
- [ ] TJOVAYETH — Jovay Testnet
- [ ] TKAIA — Kaia Kairos
- [ ] TKAVAEVM — Kava EVM Testnet
- [ ] TMANTLE — Mantle Sepolia
- [ ] TMON — Monad Testnet
- [ ] TMORPHETH — Morph Testnet
- [ ] TOAS — Oasys Testnet
- [ ] TOKBXLAYER — OKB X Layer Testnet
- [ ] TOPETH — Optimism Sepolia
- [ ] TRBTC — RSK Testnet
- [ ] TSEIEVM — Sei EVM Testnet
- [ ] TSGB — Songbird Coston
- [ ] TSONEIUM — Soneium Testnet
- [ ] TSONIC — Sonic Testnet
- [ ] TWEMIX — WeMix Testnet
- [ ] TWORLD — WorldChain Testnet
- [ ] TXDC — XDC Apothem
- [ ] TXPL — Plasma Testnet
- [ ] TZETA — ZetaChain Athens
- [ ] TOG — 0G Testnet

**ERC-20 / L2 tokens (require native coin for gas):**
- [ ] HTETH:GOUSD — GoUSD (Ethereum)
- [ ] HTETH:GRTX — GreatX (Ethereum)
- [ ] HTETH:USD1 — USD1 (Ethereum)
- [ ] TBERA:BGT — Bera Governance Token (Ethereum)
- [ ] TBSC:BUSD — BSC-USD (BSC)
- [ ] TBSC:USD1 — USD1 (BSC)
- [ ] TCUSD — CUSD (Celo)
- [ ] TDAI — DAI (Ethereum)
- [ ] TEIGEN — EIGEN (Ethereum)
- [ ] TEUROC — Euro Coin (Ethereum)
- [ ] TFMF — Formosa Financial (Ethereum)
- [ ] TFLR:WFLR — Wrapped Flare (Flare)
- [ ] GHCN — Himalaya Coin (Ethereum)
- [ ] GHDO — Himalaya Dollar (Ethereum)
- [ ] TARBETH:LINK — Chainlink (Arbitrum)
- [ ] TARBETH:XSGD — XSGD (Arbitrum)
- [ ] TAVAXC:LINK — Chainlink (Avalanche)
- [ ] TAVAXC:XSGD — XSGD (Avalanche)
- [ ] TBASEETH:USDC — USDC (Base)
- [ ] TJOVAYETH:USDCE — Bridged USDC (Mantle)
- [ ] TMATIC — Matic (Ethereum)
- [ ] TMORPHETH:USD1 — USD1 (Morph)
- [ ] TMSN — meson.network (Ethereum)
- [ ] TOPETH:WCT — WalletConnect (Optimism)
- [ ] TPOLYGON:LINK — ChainLink (Polygon)
- [ ] TPOLYGON:USDC — USDC (Polygon)
- [ ] TPOLYGON:USDT — USDT (Polygon)
- [ ] TPOLYGON:XSGD — XSGD (Polygon)
- [ ] TRIF — RIF Token (Ethereum)
- [ ] TRLUSD — Ripple USD (Ethereum)
- [ ] TUSDC — USD Coin (Ethereum)
- [ ] TUSDT — Tether (Ethereum)
- [ ] TWDOGE — Wrapped DOGE (Ethereum)
- [ ] TWETH — Wrapped ETH (Ethereum)
- [ ] TWORLD:USDC — USDC (WorldChain)
- [ ] TWORLD:WLD — Worldcoin (WorldChain)
- [ ] TXSGD — StraitsX (Ethereum)
- [ ] TXUSD — StraitsX XUSD (Ethereum)

### Solana Family (1 chain, 12 assets)

- [ ] TSOL — Solana (Devnet) — `requestAirdrop`, no wallet needed
- [ ] TSOL:USDC — USDC (Solana)
- [ ] TSOL:USDT — USD Tether (Solana)
- [ ] TSOL:USD1 — USD1 (Solana)
- [ ] TSOL:WSOL — Wrapped SOL (Solana)
- [ ] TSOL:GMT — GMT (Solana)
- [ ] TSOL:GARI — Gari (Solana)
- [ ] TSOL:ORCA — Orca (Solana)
- [ ] TSOL:RAY — Raydium (Solana)
- [ ] TSOL:SLND — Solend (Solana)
- [ ] TSOL:SRM — Serum (Solana)
- [ ] SOL:FORD — Forward Industries (Solana)

### Cosmos Family (8 chains, 14 assets)

- [ ] TATOM — Cosmos Hub Theta Testnet
- [ ] TOSMO — Osmosis Testnet
- [ ] TSEI — SEI Testnet
- [ ] TTIA — Celestia Mocha Testnet
- [ ] TCOREUM — Coreum Testnet
- [ ] TBLD — Agoric Emerynet
- [ ] TINJECTIVE — Injective Testnet
- [ ] THASH — Provenance Testnet
- [ ] THASH:YLDS — YLDS Token (Provenance)
- [ ] TCRONOS — Cronos POS Testnet
- [ ] TASI — Fetch.ai Dorado Testnet
- [ ] TINITIA — Initia Testnet
- [ ] TBABY — Babylon Testnet
- [ ] TTHORCHAIN:RUNE — Thorchain Stagenet

### Sui Family (1 chain, 3 assets)

- [ ] TSUI — Sui (Devnet) — has faucet API
- [ ] TSUI:DEEP — Deepbook (Sui)
- [ ] TSUI:WAL — Walrus (Sui)

### Aptos Family (1 chain, 3 assets)

- [ ] TAPT — Aptos (Devnet) — has faucet API
- [ ] TAPT:USDT — USD Tether (Aptos)
- [ ] TAPT:USD1 — USD1 (Aptos)

### NEAR Family (1 chain, 2 assets)

- [ ] TNEAR — NEAR Testnet — has helper API
- [ ] TNEAR:USDC — USD Coin (NEAR)

### XRP Family (2 entries, 2 assets)

- [ ] TXRP — XRP Testnet — has faucet API
- [ ] TXRP:RLUSD — Ripple USD (XRP)

### Stellar Family (1 chain, 4 assets)

- [ ] TXLM — Stellar Testnet — has friendbot
- [ ] TUSDC — Stellar USDC
- [ ] HTETH — Stellar ETH
- [ ] TBST — BitGo Shield Token (Stellar)

### Tron Family (1 chain, 4 assets)

- [ ] TTRX — Tron Nile Testnet
- [ ] TTRX:USDC — USD Coin (Tron)
- [ ] TTRX:USDT — Tether USD (Tron)
- [ ] TTRX:USD1 — USD1 (Tron)

### TON (1 chain, 1 asset)

- [ ] TTON — TON Testnet

### Hedera Family (1 chain, 2 assets)

- [ ] THBAR — Hedera Testnet
- [ ] THBAR:USDC — Hedera USDC

### UTXO Family (5 chains, 7 assets)

- [ ] TBTC4 — Bitcoin Testnet4
- [ ] TBCH — Bitcoin Cash Testnet
- [ ] TBTG — Bitcoin Gold Testnet
- [ ] TLTC — Litecoin Testnet
- [ ] TDOGE — Dogecoin Testnet
- [ ] TDASH — Dash Testnet
- [ ] TCANTON — Canton Testnet

### Remaining Standalone Chains (12 assets)

- [ ] TALGO — Algorand Testnet
- [ ] TADA — Cardano Preview/Preprod
- [ ] TEOS — EOS Jungle Testnet
- [ ] TEOS:BOX — Box (EOS)
- [ ] TEOS:CHEX — Chintai (EOS)
- [ ] TEOS:IQ — Everipedia (EOS)
- [ ] TEOS:USDT — Tether (EOS)
- [ ] TDOT — Polkadot Westend
- [ ] TPOLYX — Polymesh Testnet
- [ ] TSTX — Stacks Testnet
- [ ] TFLOW — Flow Testnet
- [ ] TVET — VeChain Testnet
- [ ] TVET:VTHO — VeThor (VeChain)
- [ ] TXTZ — Tezos Ghostnet
- [ ] TZEC — Zcash Testnet
- [ ] TICP — Internet Computer (dfx)
- [ ] TTAO — Bittensor Testnet
- [ ] TTON — TON Testnet

---

## 7. Risks & Open Questions

| Item | Severity | Notes |
|------|----------|-------|
| **Testnet RPC availability** | High | Some chains (0G, Plasma, Jovayeth, Canton) are obscure. Their testnets may be unreliable or undocumented. |
| **Token contract addresses** | Medium | The CSV doesn't include testnet contract addresses for tokens. These need to be researched per-chain. |
| **Holesky vs Sepolia** | Medium | Holesky is failing. Confirm which Ethereum testnet BitGo's `HTETH` actually targets. |
| **UTXO complexity** | Medium | UTXO chains need tx construction logic. Consider managed APIs (BlockCypher) over raw implementation. |
| **Initial wallet funding** | Medium | 32+ EVM chains means 32+ faucet visits to bootstrap. Some are CAPTCHA-gated. This is a one-time pain but plan for an afternoon of manual work. |
| **SPL / ERC-20 token sourcing** | Medium | Many testnet tokens (TSOL:GARI, GHCN, etc.) may not have public faucets. You may need to mint them yourself on testnet. |
| **Canton** | Low | Classified as UTXO in the CSV but Canton (Digital Asset / Daml) is not a traditional UTXO chain. Needs separate research. |
| **SOL:FORD** | Low | No `T` prefix — possibly a data issue in the CSV. Verify this is actually a testnet asset. |

---

## 8. What I'd Build First

If I were you, I'd do **Phase 0 + Phase 1** this week. That gives you:

- A working CLI framework
- 66 assets covered (46% of total) with one handler
- A pattern that every subsequent handler copies

The EVM handler is the highest-leverage work because one module covers 32 chains. Every other handler covers 1–8 chains. Start where the ROI is highest.
