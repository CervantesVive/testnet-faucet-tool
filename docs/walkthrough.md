# Getting Started with the BitGo Testnet Faucet Tool

A step-by-step guide for first-time users.

**Prerequisite:** This guide assumes you have read the [Blockchain & Digital Assets Primer](blockchain-primer.md). Terms like *testnet*, *faucet*, *chain family*, *native coin*, and *token* are used without re-explanation. When in doubt, refer to the [Glossary](blockchain-primer.md#8-glossary).

**What you will accomplish by the end:**
- Configure the tool with a test wallet
- Fund a test address on five representative chain families
- Monitor faucet balances and set up automated alerts

---

## Table of Contents

1. [Installation](#1-installation)
2. [Configuration Deep-Dive](#2-configuration-deep-dive)
   - [2a. Environment Variables (Wallet Credentials)](#2a-environment-variables-wallet-credentials)
   - [2b. The Asset Registry (chains.yaml)](#2b-the-asset-registry-chainsyaml)
   - [2c. Alert Configuration](#2c-alert-configuration)
3. [Orientation: Read-Only Commands](#3-orientation-read-only-commands)
4. [Walkthrough 1 — EVM (representative: HTETH)](#4-walkthrough-1--evm-representative-hteth)
5. [Walkthrough 2 — Solana (representative: TSOL)](#5-walkthrough-2--solana-representative-tsol)
6. [Walkthrough 3 — Cosmos (representative: TATOM)](#6-walkthrough-3--cosmos-representative-tatom)
7. [Walkthrough 4 — External-Faucet Chains (representative: TXRP)](#7-walkthrough-4--external-faucet-chains-representative-txrp)
8. [Walkthrough 5 — UTXO / Bitcoin (representative: TBTC4)](#8-walkthrough-5--utxo--bitcoin-representative-tbtc4)
9. [Batch Operations](#9-batch-operations)
10. [Monitoring and Alerts](#10-monitoring-and-alerts)
11. [Drip History](#11-drip-history)
12. [Troubleshooting](#12-troubleshooting)
13. [Quick Reference](#13-quick-reference)

---

## 1. Installation

### 1.1 Create the Python virtual environment

```bash
cd /path/to/testnet-faucet-tool
python3 -m venv .venv
```

### 1.2 Install the tool and its dependencies

```bash
.venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[evm,solana,cosmos,dev]"
```

The part in `[...]` is the list of **optional dependency groups** to install. Each group adds the Python libraries needed for a specific chain family:

| Group | What it installs | When you need it |
|-------|-----------------|------------------|
| `evm` | web3.py, eth-account | Any EVM chain (Ethereum, Arbitrum, Base, Polygon, etc.) |
| `solana` | solders, solana-py | Solana and SPL tokens |
| `cosmos` | cosmpy | Cosmos Hub, Osmosis, and other Cosmos SDK chains |
| `dev` | pytest, rich | Running tests and the CLI |

To use all three chain families at once (as shown above), include all three. If you only need EVM support, `.[evm,dev]` is enough.

> **Note:** Some chain families (Sui, Aptos, XRP, Stellar, Tron, etc.) do not have installable Python SDKs listed here. The tool handles them differently — see [Walkthrough 4](#7-walkthrough-4--external-faucet-chains-representative-txrp) and the [Troubleshooting](#12-troubleshooting) section.

### 1.3 Verify the installation

```bash
.venv/bin/faucet --help
```

You should see a list of available commands. If you get `command not found`, make sure you're using `.venv/bin/faucet` with the full path.

> **Tip:** For convenience, you can activate the virtual environment first so `faucet` works without the path prefix:
> ```bash
> source .venv/bin/activate
> faucet --help
> ```
> The rest of this guide assumes the venv is activated or you're using `.venv/bin/faucet`.

---

## 2. Configuration Deep-Dive

The tool needs two things to function:
1. **Credentials** — how to sign transactions (your faucet wallet's key material)
2. **Asset registry** — what chains and tokens exist, and how to reach them

### 2a. Environment Variables (Wallet Credentials)

The faucet signs transactions using a wallet you control. You provide the credentials via environment variables, not by editing any files. This keeps secrets out of your repository.

#### Primary credentials

Most chain families share one of these two variables:

| Variable | What it is | Who uses it |
|----------|-----------|-------------|
| `FAUCET_MNEMONIC` | A 12- or 24-word BIP-39 seed phrase | EVM, Cosmos, UTXO (Bitcoin family), XRP |
| `FAUCET_PRIVATE_KEY` | A raw hex private key (`0x...`) | EVM, Cosmos, UTXO (Bitcoin family) |

You only need one. `FAUCET_MNEMONIC` is more convenient because a single seed phrase derives correct addresses for every supported chain family — each family uses a different derivation path internally. `FAUCET_PRIVATE_KEY` is more explicit if you already have a specific key.

> **Security warning:** These credentials give full control over your faucet wallet. Rules:
> - Use a wallet that holds **testnet coins only** — no real money.
> - Never commit this variable to version control.
> - Never reuse a mnemonic from a wallet holding real funds.
> - See `config/wallets.yaml.example` for an age/sops encryption workflow if you want to store key material safely on disk.

#### Chain-specific credentials

Some chains cannot derive a wallet from the shared mnemonic and require their own variable:

| Variable | Chain | What it is |
|----------|-------|-----------|
| `FAUCET_SOLANA_KEYPAIR` | Solana | Base58-encoded 64-byte keypair (preferred for Solana over mnemonic) |
| `FAUCET_HEDERA_ACCOUNT_ID` | Hedera | Account ID like `0.0.12345` |
| `FAUCET_EOS_ACCOUNT` | EOS | Account name like `myfaucet123` |
| `FAUCET_ALGORAND_ADDRESS` | Algorand | Algorand wallet address |
| `FAUCET_STACKS_ADDRESS` | Stacks | Address like `ST1PQHQ...` |
| `FAUCET_TEZOS_ADDRESS` | Tezos | Address like `tz1...` |
| `FAUCET_VECHAIN_ADDRESS` | VeChain | Address like `0x...` |
| `FAUCET_ICP_PRINCIPAL` | ICP | Principal ID like `xxxxx-xxxxx-...-cai` |

You only need to set these if you are actively using that chain family.

#### Path overrides

The tool stores its state in `~/.testnet-faucet/`. You can override individual paths:

| Variable | Default path | Purpose |
|----------|-------------|---------|
| `FAUCET_DB_PATH` | `~/.testnet-faucet/rate_limits.db` | Rate limit database |
| `FAUCET_LOG_PATH` | `~/.testnet-faucet/history.log` | Drip history log |
| `FAUCET_ALERTS_CONFIG` | `~/.testnet-faucet/alerts.yaml` | Alert channel config |

You will rarely need to change these. They are most useful in testing and CI environments.

#### Setting variables for a session

```bash
export FAUCET_MNEMONIC="abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
```

Replace the example phrase above with your own testnet mnemonic. The phrase above is a well-known test mnemonic — **never use it for anything real**.

---

### 2b. The Asset Registry (chains.yaml)

`config/chains.yaml` is the single source of truth for all 144 testnet assets the tool supports. You generally **do not need to edit this file** to use the tool — it comes pre-configured. But understanding it helps you interpret command output and troubleshoot issues.

#### Anatomy of an entry

Here is the entry for HTETH (Holesky testnet Ether), annotated:

```yaml
HTETH:                                        # BitGo asset ID — used in all CLI commands
  family: evm                                 # Chain family — determines which handler code runs
  blockchain: Ethereum                        # Human-readable chain name (display only)
  network: holesky                            # Testnet name (e.g. holesky, sepolia, devnet)
  rpc_url: https://rpc.holesky.ethpandaops.io # Node endpoint the tool talks to
  explorer: https://holesky.etherscan.io/tx/{tx_hash}  # Block explorer URL template
  native_asset: true                          # true = coin, false = token (see below)
  drip_amount: "0.05"                         # How much to send per drip request
  decimals: 18                                # Smallest unit precision (18 = 10^-18 of 1 ETH)
```

**When would you edit this file?**
- You want to change the `drip_amount` to send more or less per request.
- The `rpc_url` for a chain goes down and you want to point it to a different node.
- A new testnet is announced and you want to add it.
- You want to update `explorer` after a block explorer changes its URL.

#### Fields that vary by family

Not all entries look like HTETH. Here is what changes across the families you will encounter:

**EVM token** — adds `contract_address`:
```yaml
"HTETH:GOUSD":          # Token IDs use "CHAIN:TOKEN" format and must be quoted
  family: evm
  blockchain: Ethereum
  network: holesky
  rpc_url: https://rpc.holesky.ethpandaops.io
  explorer: https://holesky.etherscan.io/tx/{tx_hash}
  native_asset: false   # false = this is a token
  contract_address: "TBD"  # ERC-20 contract address (TBD = not yet deployed)
  drip_amount: "10"
  decimals: 18
```

**Cosmos native coin** — adds `denom` and `bech32_prefix`:
```yaml
TATOM:
  family: cosmos
  blockchain: Cosmos Hub
  network: theta-testnet-001
  rpc_url: https://rpc.sentry-01.theta-testnet.polypore.xyz
  explorer: https://explorer.theta-testnet.polypore.xyz/transactions/{tx_hash}
  native_asset: true
  drip_amount: "1"
  decimals: 6
  denom: uatom            # On-chain denomination (uatom = micro-ATOM, 1 ATOM = 1,000,000 uatom)
  bech32_prefix: cosmos   # Address prefix — all Cosmos Hub addresses start with "cosmos1..."
```

**External-faucet chain** — adds `faucet_url`:
```yaml
TXRP:
  family: xrp
  blockchain: XRP Ledger
  network: testnet
  rpc_url: https://s.altnet.rippletest.net:51234
  faucet_url: https://faucet.altnet.rippletest.net/accounts  # The tool calls this URL for you
  explorer: https://testnet.xrpl.org/transactions/{tx_hash}
  native_asset: true
  drip_amount: "100"
  decimals: 6
```

**Solana native** — adds `refill_source` and `funding_method`:
```yaml
TSOL:
  family: solana
  blockchain: Solana
  network: devnet
  refill_source: airdrop         # How this faucet wallet is itself refilled
  rpc_url: https://api.devnet.solana.com
  explorer: https://explorer.solana.com/tx/{tx_hash}?cluster=devnet
  native_asset: true
  drip_amount: "0.5"
  decimals: 9
  funding_method: request_airdrop  # Use Solana's native airdrop RPC call
```

**UTXO (Bitcoin family)** — adds `coin_type`:
```yaml
TBTC4:
  family: utxo
  blockchain: Bitcoin
  network: testnet4
  rpc_url: https://blockstream.info/testnet/api  # Blockstream REST API
  explorer: https://blockstream.info/testnet/tx/{tx_hash}
  native_asset: true
  drip_amount: "0.001"
  decimals: 8
  coin_type: 1    # BIP-44 coin type — determines HD derivation path (1 = Bitcoin testnet)
```

#### What does `TBD` mean?

Many entries have `rpc_url: TBD` or `contract_address: "TBD"`. This means the chain or token is registered in the config but the tool cannot yet interact with it — the endpoint or contract hasn't been set up. Attempting a drip on a TBD asset will return a clear error message immediately without attempting any network call.

---

### 2c. Alert Configuration

Alerts notify you when faucet balances run low. You don't need this to get started — set it up once you are comfortable with basic drip operations.

**Step 1:** Copy the template to the config location:
```bash
mkdir -p ~/.testnet-faucet
cp config/alerts.yaml.example ~/.testnet-faucet/alerts.yaml
```

**Step 2:** Edit `~/.testnet-faucet/alerts.yaml`. The file has four channels:

| Channel | What it does | When to enable |
|---------|-------------|---------------|
| `log` | Writes alerts to `~/.testnet-faucet/alerts.log` (rotates daily, keeps 30 days) | Always on by default — no action needed |
| `slack` | Posts to a Slack channel via incoming webhook | If your team uses Slack |
| `webhook` | HTTP POST to any URL (works for Discord, PagerDuty, custom endpoints) | For any webhook-capable service |
| `email` | Sends via SMTP | If you prefer email notifications |

To enable Slack alerts, edit the file:
```yaml
slack:
  enabled: true
  webhook_url: https://hooks.slack.com/services/YOUR/ACTUAL/WEBHOOK
```

---

## 3. Orientation: Read-Only Commands

Before sending any tokens, run these commands to understand what the tool knows about and what state it's in. None of these make network calls that cost anything.

### Browse supported assets

```bash
faucet list
```

Prints a table of all 144 assets: their ID, family, blockchain, network, and whether they're a native coin or token.

```bash
faucet list --family evm
```

Filters to one family. Try `--family cosmos`, `--family solana`, etc.

### Check faucet wallet balances

```bash
faucet status
```

For each native asset, queries the RPC node and prints the faucet wallet's current balance. This tells you which chains are ready to send and which are empty.

```bash
faucet status --family evm
```

Filters to one family — useful when you only care about EVM chains.

> **First run:** If you haven't set `FAUCET_MNEMONIC` yet, status will print "no wallet configured" for most assets. That's expected.

### Color-coded dashboard

```bash
faucet dashboard
```

Shows the same balance information as `status` but with color-coded status indicators:
- **FUNDED** (green) — balance is healthy (at least 2x the drip amount)
- **LOW** (yellow) — balance is below 2x the drip amount; needs refilling
- **ERROR** (red) — could not fetch balance (RPC down, no wallet configured, etc.)

---

## 4. Walkthrough 1 — EVM (representative: HTETH)

**Covers:** 72 assets — Ethereum (Holesky), Arbitrum (Sepolia), Base (Sepolia), Polygon (Amoy), Optimism (Sepolia), BNB Smart Chain (testnet), Avalanche C-Chain (Fuji), and more.

**Why these are the same:** All EVM chains use identical address formats (`0x...`), the same JSON-RPC protocol, and the same transaction signing algorithm. Once you have done this walkthrough for HTETH, you can drip any EVM asset by simply changing the asset ID.

### Step 1: Generate your faucet wallet address

Set your mnemonic (use a test-only mnemonic — never a real one):

```bash
export FAUCET_MNEMONIC="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
```

Then ask the tool to derive and display the EVM faucet address:

```bash
faucet init evm
```

**Output:** A table listing all EVM chains and the single `0x...` address that serves all of them (all EVM chains share the same derivation path). Copy this address — you will use it in the next step.

**Why one address for all EVM chains?** All EVM chains use the same key format and derivation path. Your `0x...` address on Ethereum Holesky is the same string as on Arbitrum Sepolia or Polygon Amoy — they are different networks, but the address format is identical. What changes is which RPC endpoint the tool talks to.

### Step 2: Fund the faucet wallet on Holesky

The faucet tool sends tokens *from* its own wallet. Before it can send to anyone, its wallet needs tokens.

1. Go to a Holesky testnet faucet. Public options include:
   - [Google Cloud Web3 Holesky Faucet](https://cloud.google.com/application/web3/faucet/ethereum/holesky)
   - [Alchemy Holesky Faucet](https://www.alchemy.com/faucets/ethereum-holesky)
2. Paste the `0x...` address from Step 1.
3. Request testnet ETH (typically 0.1–1 ETH depending on the faucet).
4. Wait a minute for the transaction to confirm.

Verify the wallet received funds:

```bash
faucet status --family evm
```

You should see a non-zero balance for `HTETH`.

### Step 3: Get a test destination address

You need a separate address to *receive* the drip — think of it as a developer's test wallet.

If you don't have one, the easiest way is to install [MetaMask](https://metamask.io/) in your browser and create a new wallet. MetaMask shows your address at the top of the popup. Make sure to switch the network to "Holesky testnet" in MetaMask's network selector.

For this walkthrough, we'll use a placeholder — replace `0xYOUR_TEST_ADDRESS` with your actual address in every command below.

### Step 4: Validate without sending (dry run)

```bash
faucet drip HTETH 0xYOUR_TEST_ADDRESS --dry-run
```

A dry run validates the address format and checks the rate limiter but does not send anything. If the address is invalid, you will see an error here rather than a failed transaction.

**Expected output:**
```
[DRY RUN] Would send 0.05 HTETH to 0xYOUR_TEST_ADDRESS
```

### Step 5: Send the drip

```bash
faucet drip HTETH 0xYOUR_TEST_ADDRESS
```

**Expected output (success):**
```
✓ Sent 0.05 HTETH to 0xYOUR_TEST_ADDRESS
  TX: 0xabc123...
  Explorer: https://holesky.etherscan.io/tx/0xabc123...
```

Click the explorer link to see the transaction on Holesky Etherscan.

> **If the drip fails:** The tool retries up to 3 times with exponential backoff (waits 1s, then 2s, then 4s between attempts). If all three attempts fail, it prints the last error. Common causes are covered in the [Troubleshooting](#12-troubleshooting) section.

### Step 6: Verify rate limiting

Try dripping again immediately:

```bash
faucet drip HTETH 0xYOUR_TEST_ADDRESS
```

You will see a message like:
```
Rate limited: HTETH to 0xYOUR_TEST_ADDRESS — 287 seconds remaining
```

The 5-minute (300-second) cooldown is per-asset per-address. It prevents accidentally draining the faucet wallet. The cooldown resets after 5 minutes or after you use a different destination address.

### Step 7: Try another EVM chain

The exact same steps work for any EVM asset. To drip on Arbitrum Sepolia instead:

```bash
faucet drip TARBETH 0xYOUR_TEST_ADDRESS
```

The address format is identical. The only difference is the tool connects to Arbitrum's RPC and the explorer link goes to Arbiscan. First make sure to fund your faucet wallet on Arbitrum via the Arbitrum Sepolia faucet.

### Step 8: Token drips (EVM tokens)

EVM tokens (like USDC, USDT) use the colon notation: `HTETH:GOUSD` means the GOUSD token on Holesky Ethereum.

```bash
faucet drip HTETH:GOUSD 0xYOUR_TEST_ADDRESS
```

> **Important:** Most EVM token entries currently show `contract_address: "TBD"` in `chains.yaml`, meaning the token contracts haven't been deployed on testnet yet. The drip will return an error like `contract address is TBD`. This is expected — the tool is under active development and tokens are added over time.
>
> When a contract address is properly configured, the token drip works the same as a native drip, except: the recipient needs a small amount of HTETH in their wallet to pay for the gas fee of the ERC-20 transfer. If their ETH balance is zero, the tool will warn you.

---

## 5. Walkthrough 2 — Solana (representative: TSOL)

**Covers:** 12 assets — native SOL and SPL tokens on Solana devnet.

**Key difference from EVM:** Dripping native SOL does not require the faucet wallet to have any balance first. Solana devnet has a built-in `requestAirdrop` RPC call that the tool uses directly — the tool is the client, not the sender. SPL tokens (like TSOL:USDC) *do* require a funded faucet wallet and a separate keypair.

### Step 1: Set up Solana credentials

You have two options:

**Option A — Solana keypair (preferred):**
```bash
export FAUCET_SOLANA_KEYPAIR="your-base58-encoded-64-byte-keypair"
```
A Solana keypair is a base58 string. You can generate one with the Solana CLI (`solana-keygen new`) or export one from a wallet.

**Option B — Use the shared mnemonic:**
```bash
export FAUCET_MNEMONIC="your twelve word mnemonic phrase here"
```

### Step 2: Find your Solana faucet address

```bash
faucet init solana
```

**Output:** Your Solana faucet address (a 44-character base58 string like `7v91N7iZ...`) and a suggested airdrop command.

### Step 3: Drip native SOL

```bash
faucet drip TSOL 7v91N7iZ9mNicL8WfG6cgSCKyRXydQjLh6UYBWwm6y1Q
```

Replace the address with your actual Solana test wallet address (use Phantom wallet or `solana-keygen` to generate one).

**Expected output:**
```
✓ Sent 0.5 TSOL to 7v91N7iZ...
  TX: 5K7bBw...
  Explorer: https://explorer.solana.com/tx/5K7bBw...?cluster=devnet
```

**Why no pre-funding?** Behind the scenes, the tool called `https://api.devnet.solana.com` with a `requestAirdrop` RPC call. Solana devnet gives out SOL for free via this API — the tool is just a convenient wrapper. The faucet wallet address is not involved at all for native SOL.

**Rate limit:** SOL airdrops have a 1-minute cooldown (vs 5 minutes for self-funded assets). Solana's airdrop API has its own limits; if you hit them, wait a minute and try again.

### Step 4: SPL token drips

SPL tokens (e.g., `TSOL:USDC`) are a different story. The tool must transfer tokens from its own wallet, so:
1. The faucet keypair must be set.
2. The faucet wallet must hold the SPL token.
3. `mint_address` in `chains.yaml` must not be `"TBD"`.

```bash
faucet drip TSOL:USDC 7v91N7iZ9mNicL8WfG6cgSCKyRXydQjLh6UYBWwm6y1Q
```

Most SPL token entries currently have `mint_address: "TBD"` (tokens not yet deployed on devnet). When that is the case, the drip returns an immediate error — it does not waste a network call.

---

## 6. Walkthrough 3 — Cosmos (representative: TATOM)

**Covers:** 14 assets — Cosmos Hub (ATOM), Osmosis (OSMO), Sei, Injective, Celestia, Provenance, and more.

**Key difference from EVM:** Each Cosmos chain has a different *address prefix* (called bech32 prefix). The same key material (mnemonic) derives completely different-looking addresses for each chain: `cosmos1abc...` for Cosmos Hub, `osmo1abc...` for Osmosis, `sei1abc...` for Sei, and so on. These are all the same underlying key, just displayed with different prefixes.

### Step 1: Set up Cosmos credentials

```bash
export FAUCET_MNEMONIC="your twelve word mnemonic phrase here"
```

### Step 2: See all your Cosmos addresses

```bash
faucet init cosmos
```

**Output:** A table with one row per Cosmos chain, showing:
- The chain name
- The bech32 prefix (e.g., `cosmos`, `osmo`, `sei`)
- Your derived address for that chain

Even though each address looks different, they all come from the same mnemonic.

### Step 3: Fund the Cosmos Hub faucet wallet

Find the `cosmos1...` address from the table. Fund it from the Cosmos Hub testnet faucet. The official Cosmos testnet faucet is found in the Cosmos Discord server (`#🚰 | faucet` channel in the Cosmos Hub validators server).

Verify:
```bash
faucet status --family cosmos
```

### Step 4: Drip TATOM

```bash
faucet drip TATOM cosmos1abcdefghijklmnopqrstuvwxyz123456789abc
```

Replace the address with a Cosmos Hub testnet address of your choice. All Cosmos Hub addresses start with `cosmos1`.

**Expected output:**
```
✓ Sent 1 TATOM to cosmos1...
  TX: A1B2C3...
  Explorer: https://explorer.theta-testnet.polypore.xyz/transactions/A1B2C3...
```

### Step 5: Drip on another Cosmos chain

To drip Osmosis testnet tokens:

```bash
faucet drip TOSMO osmo1abcdefghijklmnopqrstuvwxyz123456789abc
```

The address must start with `osmo1`. If you give an address with the wrong prefix (e.g., giving a `cosmos1...` address when dripping `TOSMO`), the tool will reject it at the address validation step before attempting any transaction.

---

## 7. Walkthrough 4 — External-Faucet Chains (representative: TXRP)

**Covers:** XRP (`TXRP`), Stellar (`TXLM`), Sui (`TSUI`), Aptos (`TAPT`).

**Key difference from all other families:** For native coin drips on these chains, the tool does **not** sign a transaction from its own wallet. Instead, it calls an external faucet API on the chain's testnet. The tool acts as a client that requests tokens from that external service on your behalf.

This means:
- You do not need to pre-fund the faucet wallet for native drips.
- The rate limit is 24 hours (the external faucet's own rate limit window), not 5 minutes.
- The `faucet_url` field in `chains.yaml` tells the tool which external API to call.

### Step 1: Set credentials (needed for token drips, optional for native)

```bash
export FAUCET_MNEMONIC="your twelve word mnemonic phrase here"
```

### Step 2: Get your XRP faucet address

```bash
faucet init xrp
```

**Output:** Your XRP testnet address (starts with `r`).

### Step 3: Drip native XRP

```bash
faucet drip TXRP rN7n3473SaZBCG4dFL83w7p1W9cgZw6maf
```

Replace the address with your XRP testnet destination address. XRP addresses start with `r` and are 25–34 characters.

**What happens behind the scenes:** The tool sends a POST request to `https://faucet.altnet.rippletest.net/accounts` — the official XRP Ledger testnet faucet — which provisions 100 XRP directly to your address. The faucet tool's own wallet is not involved.

**Rate limit:** 24 hours. This reflects the XRP testnet faucet's own limit per address.

### Step 4: Stellar, Sui, and Aptos

The pattern is identical for the other external-faucet chains. They all have a `faucet_url` in `chains.yaml` and follow the same flow:

```bash
faucet drip TXLM GCEZWKCA5VLDNRLN3RPRJMRZOX3Z6G5CHCGZAKF7FA5WSTJIQYZ
faucet drip TSUI 0x1234abcd...   # Sui devnet address (0x-prefixed)
faucet drip TAPT 0x1234abcd...   # Aptos devnet address (0x-prefixed)
```

All of these call their respective devnet faucet APIs. No local transaction signing.

---

## 8. Walkthrough 5 — UTXO / Bitcoin (representative: TBTC4)

**Covers:** 6 assets — Bitcoin Testnet4 (`TBTC4`), Bitcoin Cash testnet, Litecoin testnet, Dogecoin testnet, and others.

**Key difference from account-based chains:** Bitcoin uses the UTXO (Unspent Transaction Output) model. Instead of an account with a balance, the faucet wallet holds individual "coins" from previous transactions. Sending bitcoin means selecting which coins to spend, combining them, and signing each one individually — the tool handles all of this automatically.

> **Current status:** Of the 6 UTXO assets, only `TBTC4` has a live RPC endpoint (`blockstream.info`). The rest have `rpc_url: TBD` and will return an immediate error. This walkthrough uses TBTC4.

### Step 1: Set credentials

```bash
export FAUCET_MNEMONIC="your twelve word mnemonic phrase here"
```

Or use a raw hex private key:
```bash
export FAUCET_PRIVATE_KEY="0xabc123..."
```

### Step 2: Find your Bitcoin testnet4 address

```bash
faucet init utxo
```

**Output:** A table of all UTXO assets with your derived address for each. The `coin_type` column shows the BIP-44 coin type (1 for Bitcoin testnet, 2 for Litecoin testnet, etc.) — this determines the derivation path and thus the address you get.

For TBTC4, your address will start with `tb1` (native SegWit) or `m`/`n` (legacy).

### Step 3: Fund the faucet wallet

Go to a Bitcoin testnet4 faucet:
- [Bitcoin Testnet4 Faucet (mempool.space)](https://mempool.space/testnet4/faucet)

Paste your `tb1...` or `m...` faucet address and request some tBTC.

Verify:
```bash
faucet status --family utxo
```

### Step 4: Drip

```bash
faucet drip TBTC4 tb1qyourdestinationaddress
```

Replace with your actual Bitcoin testnet4 destination address (generated from MetaMask with the Bitcoin testnet4 network, or from Sparrow Wallet in testnet mode).

**Expected output:**
```
✓ Sent 0.001 TBTC4 to tb1q...
  TX: a1b2c3d4...
  Explorer: https://blockstream.info/testnet/tx/a1b2c3d4...
```

The explorer link opens Blockstream, which shows the full transaction including the inputs (UTXOs spent) and outputs (change sent back to the faucet + amount sent to you).

---

## 9. Batch Operations

When you need to fund many wallets at once, use `faucet batch` instead of running `faucet drip` repeatedly.

### CSV format

The tool accepts two CSV formats:

**Two-column (asset + address per row):**
```csv
# Comments and blank lines are ignored
HTETH,0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18
TSOL,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
TATOM,cosmos1hsk6jryyqjfhp5dhc55tc9jtckygx0eph6dd02
```

**Single-column (all addresses get the same asset):**
```csv
0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18
0x853d46Dd7745D1643B6dA8bE8110F9e7696gZcK29
0x964e57Ee8856E2754C7c9Cf9a20bF0d8897hAdL30
```

### Run the batch

```bash
# Two-column CSV
faucet batch wallets.csv

# Single-column CSV (specify the asset)
faucet batch addresses.csv --asset HTETH
```

**Output:** A results table with one row per address showing:
- `OK` — drip succeeded
- `RATE_LIMITED` — this address was dripped recently, skipped
- `ERROR` — invalid address, unknown asset, or configuration issue
- `FAILED` — drip was attempted but the transaction failed
- `SKIP` — handler not yet implemented for this family

After the table, a summary line shows totals: `Processed 5 rows: 4 succeeded, 1 failed/skipped`.

> **Batch vs drip:** `faucet batch` does not retry on failure. If a drip fails, it is marked FAILED and the batch continues. Use `faucet drip` (which retries 3 times) for individual high-priority sends.

---

## 10. Monitoring and Alerts

### Check current balances

```bash
faucet refill
```

Shows each asset's current balance vs threshold (default: 2× the drip amount). Assets below threshold are flagged LOW with the exact amount needed to top them up.

```bash
faucet refill --family evm --threshold 1.0
```

Filters to EVM only and uses a custom threshold of 1.0 (in the asset's native units).

### One-shot check (for cron)

```bash
faucet check
```

Like `faucet refill` but exits with **code 1** if any wallet is LOW or ERROR. This is designed for use in cron jobs and CI pipelines where a non-zero exit code triggers an alert.

```bash
faucet check && echo "All wallets healthy"
```

### Daemon mode

```bash
faucet monitor --interval 1h
```

Runs `check` in a loop, sleeping for the specified interval between passes. Press `Ctrl-C` to stop. Accepted interval formats: `30m`, `1h`, `6h`, `1d`.

```
Monitor started — checking every 1h
[2026-03-28 09:00:00] Pass started
[2026-03-28 09:00:12] Pass complete: 18 OK, 2 LOW, 1 ERROR
[2026-03-28 10:00:00] Pass started
...
```

### Setting up alerts

When `check` or `monitor` detects a LOW or ERROR wallet, it sends an alert to each enabled channel in `~/.testnet-faucet/alerts.yaml`.

**Slack example:**
```yaml
alerts:
  slack:
    enabled: true
    webhook_url: https://hooks.slack.com/services/T000000/B000000/xxxxxxxxxxxx
```

Create the webhook URL in your Slack workspace under Apps → Incoming Webhooks.

**Discord example** (uses the generic webhook channel):
```yaml
alerts:
  webhook:
    enabled: true
    url: https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
    method: POST
```

### Setting up a cron job

To run `faucet check` every hour and log the output:

```bash
# Open crontab editor
crontab -e
```

Add:
```
0 * * * * /path/to/.venv/bin/python -m faucet check >> ~/.testnet-faucet/cron.log 2>&1
```

Replace `/path/to/` with the absolute path to your project's virtual environment.

### Auto-top-up

For assets configured with `refill_source: airdrop` (currently `TSOL`), `faucet check` automatically attempts a self-drip to the faucet's own address when it detects a LOW balance. The `check` output shows `auto-top: succeeded` or `auto-top: failed` for these assets.

---

## 11. Drip History

Every successful or failed drip is logged to `~/.testnet-faucet/history.log` as a JSON lines file (one JSON object per line).

### View recent drips

```bash
faucet history
```

Shows the 20 most recent drips in a table: time, asset, address (truncated), amount, status (OK/FAIL), and transaction hash or error.

```bash
faucet history --limit 50
```

Show the 50 most recent.

### Raw log format

Each line in `~/.testnet-faucet/history.log` looks like:
```json
{"timestamp": "2026-03-28T09:42:11Z", "asset_id": "HTETH", "address": "0x742d35...", "amount": "0.05", "success": true, "tx_hash": "0xabc...", "error": null}
```

You can search the raw log:
```bash
grep HTETH ~/.testnet-faucet/history.log
grep '"success": false' ~/.testnet-faucet/history.log
```

---

## 12. Troubleshooting

### "Rate limited: X seconds remaining"

The address you are dripping to was dripped recently. Wait for the cooldown to expire, or use a different destination address. Cooldown periods:
- **5 minutes** — for chains with a self-funded faucet wallet (EVM, Cosmos, UTXO, most others)
- **1 minute** — for Solana native (uses the airdrop API)
- **24 hours** — for external-faucet chains (XRP, Stellar, Sui, Aptos)

### "invalid address" or address validation fails

The address format does not match the chain family:
- EVM addresses start with `0x` and are 42 characters (`0x` + 40 hex).
- Solana addresses are 32–44 base58 characters (no `0x` prefix).
- Cosmos addresses start with the chain's bech32 prefix (`cosmos1...`, `osmo1...`, etc.).
- XRP addresses start with `r`.
- Bitcoin testnet addresses start with `tb1`, `m`, or `n`.

Giving an EVM address to `faucet drip TSOL` will fail address validation — the formats are incompatible.

### "contract address is TBD" / "rpc_url is TBD"

The asset is registered in `chains.yaml` but the required endpoint or contract hasn't been set up yet. This is expected for many token entries and some native assets. The tool prints a clear error immediately without making any network calls. To check which assets have live configurations:

```bash
grep -v "TBD" config/chains.yaml | grep "rpc_url"
```

### "requires X SDK" / "SDK not installed"

Some chain families (Hedera, Algorand, Flow, Substrate, ICP, etc.) need Python SDKs that are not installed in the default setup. The drip returns a message like `requires hedera-sdk`. These families are under development. Installing the SDK manually may work, but it is not officially supported yet.

### "no wallet configured"

The environment variable for this chain's credentials is not set. Run `faucet init <family>` — it will tell you exactly which variable to set. Then export the variable and try again.

### "Drip failed after 3 attempts"

All three retry attempts failed. The last error message explains why. Common causes:
- The RPC node is temporarily down — try again later.
- The faucet wallet has insufficient balance — run `faucet status` and refill if needed.
- Network congestion causing timeouts — wait and retry.

### Dry run shows everything OK but the real drip fails

Dry run validates address format and rate limits but does not connect to the chain. If the real drip fails, check:
1. Is `faucet status` showing a non-zero balance?
2. Is the RPC URL in `chains.yaml` reachable? Try `curl <rpc_url>`.
3. Is the mnemonic/private key correctly set? Run `faucet init <family>` to verify the derived address.

---

## 13. Quick Reference

### CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `faucet list` | List all supported assets | `faucet list --family evm` |
| `faucet init <family>` | Derive faucet address, print funding instructions | `faucet init evm` |
| `faucet drip <asset> <address>` | Send testnet tokens (retries 3×) | `faucet drip HTETH 0x...` |
| `faucet drip <assets> <address> --dry-run` | Validate without sending | `faucet drip HTETH 0x... --dry-run` |
| `faucet drip <a>,<b> <address>` | Drip multiple assets at once | `faucet drip HTETH,TARBETH 0x...` |
| `faucet batch <csv>` | Bulk drip from CSV file | `faucet batch wallets.csv` |
| `faucet batch <csv> --asset <id>` | Bulk drip single-column CSV | `faucet batch addrs.csv --asset HTETH` |
| `faucet status` | Check faucet wallet balances | `faucet status --family cosmos` |
| `faucet dashboard` | Color-coded balance overview | `faucet dashboard` |
| `faucet refill` | Low-balance report with funding amounts | `faucet refill --threshold 1.0` |
| `faucet check` | One-shot check, exits 1 on LOW/ERROR | `faucet check --family evm` |
| `faucet monitor` | Daemon mode balance checking | `faucet monitor --interval 30m` |
| `faucet history` | View recent drip history | `faucet history --limit 50` |

### Environment Variables

| Variable | Required for | Notes |
|----------|-------------|-------|
| `FAUCET_MNEMONIC` | EVM, Cosmos, UTXO, XRP | 12- or 24-word BIP-39 phrase |
| `FAUCET_PRIVATE_KEY` | EVM, Cosmos, UTXO | Hex key, alternative to mnemonic |
| `FAUCET_SOLANA_KEYPAIR` | Solana SPL tokens | Base58 64-byte keypair |
| `FAUCET_DB_PATH` | Optional | Override rate limit DB location |
| `FAUCET_LOG_PATH` | Optional | Override history log location |
| `FAUCET_ALERTS_CONFIG` | Optional | Override alerts config location |

### Workflow Groups

| Group | Asset IDs | Wallet credential | Address format | Pre-fund needed? |
|-------|-----------|------------------|---------------|-----------------|
| EVM | `HTETH`, `TARBETH`, `TBASE`, … | `FAUCET_MNEMONIC` or `FAUCET_PRIVATE_KEY` | `0x...` (42 chars) | Yes |
| Solana native | `TSOL` | None | Base58 (44 chars) | No (uses airdrop API) |
| Solana tokens | `TSOL:USDC`, … | `FAUCET_SOLANA_KEYPAIR` or `FAUCET_MNEMONIC` | Base58 (44 chars) | Yes |
| Cosmos | `TATOM`, `TOSMO`, `TSEI`, … | `FAUCET_MNEMONIC` or `FAUCET_PRIVATE_KEY` | `<prefix>1...` | Yes |
| External faucet | `TXRP`, `TXLM`, `TSUI`, `TAPT` | None | Chain-specific | No (calls external API) |
| UTXO | `TBTC4` | `FAUCET_MNEMONIC` or `FAUCET_PRIVATE_KEY` | `tb1...` / `m...` / `n...` | Yes |

### Related Documents

- [Blockchain & Digital Assets Primer](blockchain-primer.md) — foundational concepts
- [README](../README.md) — brief setup and command summary
- [`config/chains.yaml`](../config/chains.yaml) — full asset registry
- [`config/alerts.yaml.example`](../config/alerts.yaml.example) — alert channel template
