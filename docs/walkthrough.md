# Getting Started with the Testnet Faucet Tool

A step-by-step guide that combines hands-on Custodian practice with blockchain concept learning.

**What you'll accomplish:**
- Understand the two-wallet model: your Custodian accounts (destinations) vs. the faucet signing wallet (source)
- Fund your Custodian testnet accounts across five representative chain families
- Learn the key differences between blockchain families as you go
- Monitor faucet balances and set up automated alerts

**How to use this guide:** Each walkthrough is self-contained — you can do them in order for a full tour, or jump to the chain family you need. Short learning notes are included inline; follow the links for deeper dives into the [Blockchain & Digital Assets Primer](blockchain-primer.md).

---

## Table of Contents

1. [Installation](#1-installation)
2. [The Two-Wallet Model](#2-the-two-wallet-model)
   - [2a. Your Custodian Accounts (Destinations)](#2a-your-Custodian-accounts-destinations)
   - [2b. The Faucet Signing Wallet](#2b-the-faucet-signing-wallet)
   - [2c. The Asset Registry (chains.yaml)](#2c-the-asset-registry-chainsyaml)
   - [2d. Alert Configuration](#2d-alert-configuration)
3. [Orientation: Explore the Tool](#3-orientation-explore-the-tool)
4. [Walkthrough 1 — EVM (Ethereum Holesky: HTETH)](#4-walkthrough-1--evm-ethereum-holesky-hteth)
5. [Walkthrough 2 — Solana (TSOL)](#5-walkthrough-2--solana-tsol)
6. [Walkthrough 3 — Cosmos (TATOM)](#6-walkthrough-3--cosmos-tatom)
7. [Walkthrough 4 — External-Faucet Chains (TXRP)](#7-walkthrough-4--external-faucet-chains-txrp)
8. [Walkthrough 5 — UTXO / Bitcoin (TBTC4)](#8-walkthrough-5--utxo--bitcoin-tbtc4)
9. [Batch Operations](#9-batch-operations)
10. [Monitoring and Alerts](#10-monitoring-and-alerts)
11. [Drip History](#11-drip-history)
12. [Troubleshooting](#12-troubleshooting)
13. [Quick Reference](#13-quick-reference)

---

## 1. Installation

### 1.1 Install dependencies

Navigate to the project directory, then install the Python packages for the chain families you'll use:

```bash
cd /path/to/testnet-faucet-tool
uv sync --extra evm --extra solana --extra cosmos --extra dev
```

> **What is `uv`?** It's a fast Python package manager. `uv sync` reads the project's dependency file and installs exactly the right packages in an isolated environment — nothing conflicts with other Python projects on your machine.

The `--extra` flags select optional dependency groups:

| Group | What it installs | When you need it |
|-------|-----------------|------------------|
| `evm` | web3.py, eth-account | Any EVM chain (Ethereum, Arbitrum, Base, Polygon, etc.) |
| `solana` | solders, solana-py | Solana and SPL tokens |
| `cosmos` | cosmpy | Cosmos Hub, Osmosis, and other Cosmos SDK chains |
| `dev` | pytest, rich | Running tests and the CLI |

### 1.2 Verify the installation

```bash
uv run faucet --help
```

You should see a list of available commands. All commands in this guide use the `uv run faucet` prefix.

---

## 2. The Two-Wallet Model

Before running any commands, understand the most important concept in this guide. Confusion between these two roles is the most common source of errors.

### Two wallets, different jobs

| | Faucet signing wallet | Your Custodian account |
|---|---|---|
| **Role** | Holds the funds; signs and sends transactions | Receives the dripped tokens |
| **Who controls it** | You (set as an env var) | You (via Custodian) |
| **Credential** | `FAUCET_MNEMONIC` or `FAUCET_PRIVATE_KEY` | Managed by Custodian |
| **Holds real money?** | Never — testnet only | Testnet environment only |

Think of it like a vending machine: your Custodian accounts are the people buying drinks; the faucet signing wallet is the machine's own cash drawer. The machine must have coins loaded before it can give change.

> **Learn more:** [What is a wallet? → Primer §4](blockchain-primer.md#4-addresses-and-wallets)

---

### 2a. Your Custodian Accounts (Destinations)

Your Custodian testnet accounts are the destinations for every `faucet drip` command. Before you can fund them, you need their **deposit addresses**.

> **Term: Deposit address** — A blockchain address that Custodian controls on your behalf. When tokens arrive at this address, they appear in your Custodian wallet balance. Each chain family has a different address format. [→ Primer §4](blockchain-primer.md#4-addresses-and-wallets)

**How to find a deposit address in Custodian:**

1. Log in to the Custodian web app and switch to the **testnet environment** (look for a testnet toggle or environment selector — testnet data is completely separate from mainnet).
2. Open the wallet for the chain you want to fund (e.g., your Ethereum wallet).
3. Click **Deposit** or **Receive** — Custodian shows you the deposit address for that wallet.
4. Copy the address.

You will repeat this step at the start of each walkthrough below, for each chain family.

---

### 2b. The Faucet Signing Wallet

This is the wallet the tool uses to sign and send transactions. It is completely separate from your Custodian accounts.

**Step 1: Create a new testnet-only wallet**

You need a 12- or 24-word **seed phrase** (also called a mnemonic). Generate one from any wallet app — MetaMask is the easiest:
1. Install [MetaMask](https://metamask.io/) in your browser.
2. Click **Create a new wallet** and follow the prompts.
3. When MetaMask shows the 12-word phrase, write it down somewhere safe.

This wallet is only for the faucet tool. Never fund it with real assets.

> **Term: Seed phrase / mnemonic** — A human-readable encoding of a private key, standardised as BIP-39. From one seed phrase, the tool derives correct wallet addresses for every supported chain family. This is why a single `FAUCET_MNEMONIC` covers EVM, Cosmos, Bitcoin, and more — each family uses a different derivation path from the same root key. [→ Primer §4](blockchain-primer.md#4-addresses-and-wallets)

> **Security rule:** Never commit this variable to version control. Never reuse a mnemonic from a wallet holding real funds. Testnet coins have no value, but building safe habits now matters.

**Step 2: Set the mnemonic for your terminal session**

```bash
export FAUCET_MNEMONIC="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
```

This stays set for the current terminal session. You'll need to re-run it if you open a new terminal window.

**Step 3: Confirm the tool sees it**

```bash
uv run faucet init evm
```

If the mnemonic is set correctly, you'll see a derived `0x...` address for your faucet wallet on EVM chains. If you see "no wallet configured," re-run the `export` command.

---

### 2c. The Asset Registry (chains.yaml)

`config/chains.yaml` defines all 144 testnet assets the tool supports. You generally do not need to edit it — it comes pre-configured. But understanding its structure helps you interpret command output and troubleshoot issues.

Here is the entry for `HTETH` (Holesky testnet ETH), annotated:

```yaml
HTETH:                                        # Asset ID — used in all CLI commands
  family: evm                                 # Chain family — determines which handler runs
  blockchain: Ethereum                        # Human-readable chain name (display only)
  network: holesky                            # Which testnet
  rpc_url: https://rpc.holesky.ethpandaops.io # Node the tool connects to
  explorer: https://holesky.etherscan.io/tx/{tx_hash}  # Block explorer URL template
  native_asset: true                          # true = coin, false = token
  drip_amount: "0.05"                         # Amount sent per drip
  decimals: 18                                # 10^-18 of 1 ETH = 1 wei
```

> **Term: RPC URL** — The network address of a blockchain node. The tool sends transactions to this endpoint and reads chain state from it. If this URL is down, drips on that chain will fail.

> **Term: Block explorer** — A website for browsing blockchain data: transactions, addresses, balances. After a successful drip, the tool prints an explorer link so you can verify the transaction landed. [→ Primer §1](blockchain-primer.md#1-what-is-a-blockchain)

**What does `TBD` mean?** Many entries have `rpc_url: TBD` or `contract_address: "TBD"`. This means the asset is registered but not yet operational. Attempting to drip a TBD asset returns a clear error immediately — no network call is made.

---

### 2d. Alert Configuration

Alerts notify you when faucet balances run low. Skip this for now and return to it after you've completed the walkthroughs.

> See [Section 10: Monitoring and Alerts](#10-monitoring-and-alerts).

---

## 3. Orientation: Explore the Tool

Before sending any tokens, run these read-only commands. None of these send anything or modify any blockchain.

### 3.1 Browse all supported assets

```bash
uv run faucet list
```

You'll see all 144 assets: ID, family, blockchain, network, and type (coin or token).

**Try filtering by family:**
```bash
uv run faucet list --family evm
uv run faucet list --family cosmos
uv run faucet list --family solana
```

> **Notice** how many EVM chains there are (72). They all use the same handler code because they share the same underlying technology — the Ethereum Virtual Machine. One code path, dozens of networks. [→ Primer §6, EVM Family](blockchain-primer.md#6-chain-families)

### 3.2 Check faucet wallet balances

```bash
uv run faucet status
```

For each native asset, this queries the blockchain and shows the faucet wallet's current balance. Since you haven't funded the wallet yet, most will show zero or "no wallet configured." That's expected — revisit this after each walkthrough.

```bash
uv run faucet status --family evm
```

### 3.3 View the color-coded dashboard

```bash
uv run faucet dashboard
```

Same as `status`, with color coding:
- **FUNDED** (green) — balance is at least 2× the drip amount
- **LOW** (yellow) — balance is below 2× the drip amount
- **ERROR** (red) — could not fetch balance (node down, no wallet configured, etc.)

---

## 4. Walkthrough 1 — EVM (representative: HTETH)

**What you'll learn:**
- Why one address serves all 72 EVM chains
- How to fund a faucet wallet from a public testnet faucet
- How to send a drip and verify it on a block explorer
- How the rate limiter protects the faucet wallet

> **New to EVM?** Read [Primer §6 — EVM Family](blockchain-primer.md#6-chain-families) first. Key concept: Ethereum, Arbitrum, Base, Polygon, Optimism, and dozens more all share the same address format, signing algorithm, and RPC protocol. One piece of handler code covers all of them.

**Covers:** 72 assets — Ethereum (Holesky), Arbitrum (Sepolia), Base (Sepolia), Polygon (Amoy), Optimism (Sepolia), BNB Smart Chain (testnet), Avalanche C-Chain (Fuji), and more.

---

### Step 1: Get your Custodian EVM deposit address

1. In the Custodian web app, switch to the **testnet environment**.
2. Open your **Ethereum testnet wallet**.
3. Click **Deposit** to view the deposit address.
4. Copy the address — it starts with `0x` and is 42 characters long.

> **Why one address for all EVM chains?** Your `0x...` address is the same string on Ethereum Holesky, Arbitrum Sepolia, Base Sepolia, and every other EVM chain. The address format is universal across the EVM family. What changes between chains is only which RPC endpoint the tool connects to.

---

### Step 2: Find your faucet wallet's EVM address

```bash
uv run faucet init evm
```

This derives and displays the EVM address for your faucet signing wallet. All EVM chains share the same address — you'll see it repeated across the table.

**Copy this address.** You'll use it in the next step to fund the faucet wallet from a public faucet.

---

### Step 3: Fund the faucet wallet

The faucet tool sends tokens *from* its wallet. Before it can send to anyone, its wallet needs funds.

1. Go to a free Holesky testnet ETH faucet:
   - [Google Cloud Web3 Holesky Faucet](https://cloud.google.com/application/web3/faucet/ethereum/holesky)
   - [Alchemy Holesky Faucet](https://www.alchemy.com/faucets/ethereum-holesky)
2. Paste the **faucet wallet address** from Step 2 (the `0x...` you copied — not your Custodian address).
3. Request testnet ETH — typically 0.1–1 ETH depending on the faucet.
4. Wait about a minute for the transaction to confirm on-chain.

> **Term: Transaction confirmation** — After you submit a transaction, validators include it in the next block. Once included, it's "confirmed." Most testnets confirm within seconds to a minute. You can watch the transaction appear on a block explorer in real time. [→ Primer §1](blockchain-primer.md#1-what-is-a-blockchain)

**Verify the funding worked:**
```bash
uv run faucet status --family evm
```

You should see a non-zero balance for `HTETH`. If it still shows zero, wait another minute and try again.

---

### Step 4: Validate without sending (dry run)

Before sending your first real drip, use `--dry-run` to validate everything without touching the blockchain:

```bash
uv run faucet drip HTETH 0xYOUR_Custodian_ADDRESS --dry-run
```

Replace `0xYOUR_Custodian_ADDRESS` with the Custodian deposit address from Step 1.

**Expected output:**
```
[DRY RUN] Would send 0.05 HTETH to 0xYOUR_Custodian_ADDRESS
```

A dry run checks:
- The address format is valid for this chain family
- The rate limiter isn't blocking this address

It does **not** check your faucet balance or connect to the blockchain.

---

### Step 5: Send the drip

```bash
uv run faucet drip HTETH 0xYOUR_Custodian_ADDRESS
```

**Expected output:**
```
✓ Sent 0.05 HTETH to 0xYOUR_Custodian_ADDRESS
  TX: 0xabc123...
  Explorer: https://holesky.etherscan.io/tx/0xabc123...
```

> **If the drip fails:** The tool retries automatically — up to 3 times with exponential backoff (waits 1s, then 2s, then 4s). If all three fail, it prints the last error. See [Section 12: Troubleshooting](#12-troubleshooting).

---

### Step 6: Verify the transaction

**On the block explorer:** Click the Explorer link in the output. You'll land on Holesky Etherscan showing the transaction details — sender, recipient, amount, and confirmation status.

**In Custodian:** Open your Ethereum testnet wallet — you should see the 0.05 ETH arrive in your transaction history.

> **Term: Transaction hash (tx hash)** — A unique fingerprint for a single transaction. No two transactions share the same hash. It's how you look up a specific transaction on a block explorer. The faucet tool always prints one after a successful drip. [→ Primer §1](blockchain-primer.md#1-what-is-a-blockchain)

---

### Step 7: See the rate limiter in action

Try sending to the same Custodian address immediately:

```bash
uv run faucet drip HTETH 0xYOUR_Custodian_ADDRESS
```

**Expected output:**
```
Rate limited: HTETH to 0xYOUR_Custodian_ADDRESS — 287 seconds remaining
```

> **Why rate limiting?** The faucet wallet holds a limited supply of testnet ETH. Without limits, one address could drain it in seconds. The 5-minute cooldown is per-asset per-address — so you can drip a different asset or a different address immediately. The cooldown resets after 5 minutes or after you switch to a different destination.

---

### Step 8: Try another EVM chain

The exact same process works for any EVM asset — only the asset ID changes.

First, fund your faucet wallet on Arbitrum Sepolia (from [Arbitrum Sepolia faucet](https://faucet.quicknode.com/arbitrum/sepolia)). Then:

```bash
uv run faucet drip TARBETH 0xYOUR_Custodian_ADDRESS
```

The Custodian address is identical to the Holesky one — same `0x...` string. What changes is the tool connects to Arbitrum's RPC and the explorer link goes to Arbiscan.

---

### Step 9: Token drips (optional)

EVM tokens use colon notation: `HTETH:GOUSD` means the GOUSD token on Holesky Ethereum.

```bash
uv run faucet drip HTETH:GOUSD 0xYOUR_Custodian_ADDRESS
```

> **Most EVM token entries show `contract_address: "TBD"`** in `chains.yaml` — the token contracts haven't been deployed on testnet yet. You'll get an immediate error, which is expected. When a contract is live, the token drip works identically to a native drip — except the recipient needs a small ETH balance to pay the gas fee for the ERC-20 transfer.

> **Learn more:** [Native coins vs tokens → Primer §3](blockchain-primer.md#3-native-coins-vs-tokens)

---

## 5. Walkthrough 2 — Solana (representative: TSOL)

**What you'll learn:**
- How Solana devnet's built-in airdrop API works — no pre-funding needed for native SOL
- What Solana addresses look like and how they differ from EVM
- The difference between native SOL drips and SPL token drips

> **New to Solana?** Read [Primer §6 — Solana Family](blockchain-primer.md#6-chain-families). Key concept: Solana has a completely different architecture from EVM chains — different address format, different transaction model, and its own devnet with a built-in free airdrop endpoint.

**Covers:** 12 assets — native SOL and SPL tokens on Solana devnet.

**Key difference from EVM:** For native SOL, you do **not** need to pre-fund the faucet wallet. Solana devnet has a built-in `requestAirdrop` RPC method that the tool calls directly on your behalf.

---

### Step 1: Get your Custodian Solana deposit address

1. In the Custodian web app, open your **Solana testnet wallet**.
2. Click **Deposit** to view the deposit address.
3. Copy the address — it's a 44-character Base58 string with no `0x` prefix.

> **Term: Base58** — An encoding format used by Solana and Bitcoin. It converts binary data into human-readable text, excluding visually ambiguous characters like `0`, `O`, `l`, and `I`. A Solana address looks like `7v91N7iZ9mNicL8WfG6cgSCKyRXydQjLh6UYBWwm6y1Q`. [→ Primer §4](blockchain-primer.md#4-addresses-and-wallets)

---

### Step 2: Drip native SOL (no pre-funding needed)

```bash
uv run faucet drip TSOL YOUR_Custodian_SOLANA_ADDRESS
```

Replace `YOUR_Custodian_SOLANA_ADDRESS` with the address from Step 1.

**Expected output:**
```
✓ Sent 0.5 TSOL to 7v91N7iZ...
  TX: 5K7bBw...
  Explorer: https://explorer.solana.com/tx/5K7bBw...?cluster=devnet
```

> **What just happened?** The tool called `requestAirdrop` on Solana's devnet RPC (`https://api.devnet.solana.com`). Solana's own devnet infrastructure credited SOL directly to your address — the faucet signing wallet was not involved at all. [→ Primer §5](blockchain-primer.md#5-testnets-and-faucets)

**Rate limit:** SOL airdrops have a 1-minute cooldown. Solana's airdrop API has its own server-side limits too; if you hit them, wait a minute and try again.

---

### Step 3: Verify in Custodian

Open your Solana testnet wallet in Custodian — you should see the 0.5 SOL arrive. Click the transaction to open it on the Solana explorer.

---

### Step 4: SPL token drips (optional, advanced)

SPL tokens (e.g., `TSOL:USDC`) require the faucet wallet to hold and transfer the token — unlike native SOL, the devnet airdrop API doesn't cover tokens.

```bash
uv run faucet drip TSOL:USDC YOUR_Custodian_SOLANA_ADDRESS
```

Most SPL entries have `mint_address: "TBD"` — the contracts haven't been deployed on devnet yet. You'll get an immediate error, which is expected.

> **Term: SPL token** — Solana's equivalent of ERC-20. SPL stands for Solana Program Library. Just as ERC-20 tokens are created by smart contracts on Ethereum, SPL tokens are created by programs on Solana. [→ Primer §3](blockchain-primer.md#3-native-coins-vs-tokens)

---

## 6. Walkthrough 3 — Cosmos (representative: TATOM)

**What you'll learn:**
- How the Cosmos bech32 address prefix system works — the same key produces different-looking addresses on each chain
- How to fund a Cosmos faucet wallet through a Discord faucet channel
- How address validation catches mismatched prefixes before wasting a transaction

> **New to Cosmos?** Read [Primer §6 — Cosmos Family](blockchain-primer.md#6-chain-families). Key concept: Cosmos is an ecosystem of independent blockchains sharing the same SDK. Each chain has a unique address prefix (`cosmos1`, `osmo1`, `sei1`, etc.), but one mnemonic derives valid addresses for all of them.

**Covers:** 14 assets — Cosmos Hub (ATOM), Osmosis (OSMO), Sei, Injective, Celestia, Provenance, and more.

---

### Step 1: Get your Custodian Cosmos Hub deposit address

1. In the Custodian web app, open your **Cosmos Hub testnet wallet**.
2. Click **Deposit** to view the deposit address.
3. Copy the address — it starts with `cosmos1`.

> **Term: Bech32 prefix** — The chain-specific prefix at the start of a Cosmos address. `cosmos1...` is Cosmos Hub; `osmo1...` is Osmosis; `sei1...` is Sei. The same underlying private key produces different-looking addresses depending on which prefix is applied. [→ Primer §6](blockchain-primer.md#6-chain-families)

---

### Step 2: See all your Cosmos faucet wallet addresses

One mnemonic derives a different-looking address for each Cosmos chain. See them all at once:

```bash
uv run faucet init cosmos
```

**Output:** A table with one row per Cosmos chain, showing the bech32 prefix and derived faucet address. Notice how each address looks different (`cosmos1...`, `osmo1...`, `sei1...`) even though they all come from the same mnemonic phrase.

---

### Step 3: Fund the faucet wallet on Cosmos Hub

1. From the `faucet init cosmos` output, copy the `cosmos1...` faucet wallet address.
2. Join the [Cosmos Hub Discord server](https://discord.gg/cosmosnetwork).
3. Go to the `#🚰 | faucet` channel in the Cosmos Hub validators server.
4. Post your `cosmos1...` address to request testnet ATOM.
5. Wait about a minute for the transaction to confirm.

**Verify:**
```bash
uv run faucet status --family cosmos
```

You should see a non-zero balance for `TATOM`.

---

### Step 4: Send the drip

```bash
uv run faucet drip TATOM YOUR_Custodian_COSMOS_ADDRESS
```

Replace `YOUR_Custodian_COSMOS_ADDRESS` with the `cosmos1...` address from Step 1.

**Expected output:**
```
✓ Sent 1 TATOM to cosmos1...
  TX: A1B2C3...
  Explorer: https://explorer.theta-testnet.polypore.xyz/transactions/A1B2C3...
```

---

### Step 5: Verify in Custodian

Open your Cosmos Hub testnet wallet in Custodian — you should see the 1 ATOM arrive.

> **Term: uATOM** — Cosmos stores amounts in micro-units on-chain. 1 ATOM = 1,000,000 uATOM. The `decimals: 6` field in `chains.yaml` tells the tool the conversion factor. You configure `drip_amount: "1"` (in ATOM), and the tool converts it to 1,000,000 uATOM for the transaction.

---

### Step 6: Drip on another Cosmos chain

1. In Custodian, open your **Osmosis testnet wallet** and copy its deposit address (starts with `osmo1`).
2. Fund your faucet wallet on Osmosis — each Cosmos chain is an independent network, so each needs separate funding.
3. Send the drip:

```bash
uv run faucet drip TOSMO YOUR_Custodian_OSMOSIS_ADDRESS
```

> **Address matching is enforced:** If you give a `cosmos1...` address when dripping `TOSMO`, the tool rejects it at validation before attempting any transaction. This protects you from accidentally sending to the wrong network — a mistake that would result in unrecoverable lost funds on mainnet.

---

## 7. Walkthrough 4 — External-Faucet Chains (representative: TXRP)

**What you'll learn:**
- How external-faucet chains work — the tool calls the chain's own faucet API rather than signing a local transaction
- Why no pre-funding is needed for native drips
- Why the rate limit is 24 hours instead of 5 minutes

> **Covers:** XRP (`TXRP`), Stellar (`TXLM`), Sui (`TSUI`), Aptos (`TAPT`).

**Key difference from all other families:** For native coin drips, the tool does **not** sign a transaction from its own wallet. Instead, it sends an HTTP POST request to the chain's own testnet faucet API. You're using the tool as a client that requests tokens from that external service.

This means:
- You do **not** need to pre-fund the faucet wallet
- The rate limit is **24 hours** (the external faucet's own limit window), not 5 minutes
- The `faucet_url` field in `chains.yaml` is the URL the tool POSTs to

> **Learn more:** [What is a faucet? → Primer §5](blockchain-primer.md#5-testnets-and-faucets)

---

### Step 1: Get your Custodian XRP deposit address

1. In the Custodian web app, open your **XRP testnet wallet**.
2. Click **Deposit** to view the deposit address.
3. Copy the address — it starts with `r` and is 25–34 characters long.

> **Term: XRP address format** — XRP Ledger uses its own Base58Check encoding. Addresses always start with `r` and look completely different from EVM (`0x...`) or Cosmos (`cosmos1...`) because XRP Ledger was designed independently with its own priorities (fast settlement, low fees for payments). [→ Primer §6](blockchain-primer.md#6-chain-families)

---

### Step 2: Drip native XRP (no pre-funding needed)

```bash
uv run faucet drip TXRP YOUR_Custodian_XRP_ADDRESS
```

**Expected output:**
```
✓ Sent 100 TXRP to rYOUR_ADDRESS...
  TX: ABC123...
  Explorer: https://testnet.xrpl.org/transactions/ABC123...
```

> **What just happened?** The tool sent a POST request to `https://faucet.altnet.rippletest.net/accounts` — the official XRP Ledger testnet faucet. That service provisioned 100 XRP directly to your address. The faucet signing wallet was not involved.

**Rate limit:** 24 hours — the XRP testnet faucet's own limit per address.

---

### Step 3: Verify in Custodian

Open your XRP testnet wallet in Custodian — you should see 100 XRP arrive.

---

### Step 4: Stellar, Sui, and Aptos

The same pattern works for the other external-faucet chains. Get each address from the corresponding Custodian testnet wallet:

```bash
uv run faucet drip TXLM YOUR_Custodian_STELLAR_ADDRESS   # Stellar addresses start with G
uv run faucet drip TSUI YOUR_Custodian_SUI_ADDRESS        # Sui addresses start with 0x
uv run faucet drip TAPT YOUR_Custodian_APTOS_ADDRESS      # Aptos addresses start with 0x
```

All call their respective devnet faucet APIs. No local transaction signing.

> **Rate limit reminder:** These chains use a 24-hour cooldown instead of 5 minutes because the limit is enforced by the external faucet service — not by the tool.

---

## 8. Walkthrough 5 — UTXO / Bitcoin (representative: TBTC4)

**What you'll learn:**
- The UTXO model — how Bitcoin tracks ownership differently from account-based chains
- Why Bitcoin transactions show inputs and outputs (not just sender and recipient)
- How the faucet handles coin selection and change addresses automatically

> **New to UTXO?** Read [Primer §6 — UTXO Family](blockchain-primer.md#6-chain-families). Key concept: Bitcoin doesn't use account balances. It tracks individual unspent outputs (UTXOs). Spending bitcoin means consuming one or more UTXOs and creating new ones — like handing over a $20 bill and receiving $14 in change.

**Covers:** 6 assets — Bitcoin Testnet4 (`TBTC4`), Bitcoin Cash testnet, Litecoin testnet, Dogecoin testnet, and others.

> **Current status:** Only `TBTC4` has a live RPC endpoint (`blockstream.info`). The remaining 5 UTXO assets have `rpc_url: TBD` and return an immediate error. This walkthrough uses `TBTC4`.

---

### Step 1: Get your Custodian Bitcoin testnet deposit address

1. In the Custodian web app, open your **Bitcoin testnet wallet**.
2. Click **Deposit** to view the deposit address.
3. Copy the address — it starts with `tb1` (native SegWit) or `m`/`n` (legacy).

> **Term: SegWit vs legacy addresses** — Bitcoin has evolved through several address formats. Native SegWit addresses (`tb1...` on testnet, `bc1...` on mainnet) are the modern standard — more efficient and cheaper to spend. Legacy addresses (`m...` or `n...` on testnet) are older but still valid. Custodian typically provides native SegWit by default.

---

### Step 2: Find your faucet wallet's Bitcoin address

```bash
uv run faucet init utxo
```

You'll see a table of all UTXO assets with the faucet wallet's derived address for each. The `coin_type` column shows the BIP-44 coin type — this determines the HD derivation path and thus the address (Bitcoin testnet uses coin type 1, Litecoin uses 2, etc.).

Copy the address in the `TBTC4` row.

---

### Step 3: Fund the faucet wallet

1. Go to the [Bitcoin Testnet4 Faucet (mempool.space)](https://mempool.space/testnet4/faucet).
2. Paste the **faucet wallet address** from Step 2.
3. Request some tBTC (testnet Bitcoin).
4. Wait for the transaction to confirm.

**Verify:**
```bash
uv run faucet status --family utxo
```

---

### Step 4: Send the drip

```bash
uv run faucet drip TBTC4 YOUR_Custodian_BITCOIN_ADDRESS
```

**Expected output:**
```
✓ Sent 0.001 TBTC4 to tb1q...
  TX: a1b2c3d4...
  Explorer: https://blockstream.info/testnet/tx/a1b2c3d4...
```

---

### Step 5: Read a Bitcoin transaction on the block explorer

Click the Explorer link — it opens Blockstream.

> **What you'll see that's different from Etherscan:** Bitcoin transactions show **inputs** (UTXOs being consumed) and **outputs** (UTXOs being created). You'll see at least two outputs: one going to your Custodian address (the drip amount), and one going back to the faucet wallet (the change). This change output is automatic — you can't send a partial UTXO, so you must spend the whole thing and return the remainder to yourself. The faucet tool handles coin selection and change calculation internally.

**In Custodian:** Open your Bitcoin testnet wallet — you should see the 0.001 BTC arrive.

---

## 9. Batch Operations

When you need to fund many wallets at once, use `faucet batch` instead of running `faucet drip` repeatedly.

### CSV format

**Two-column (different asset per row):**
```csv
# Comments and blank lines are ignored
# Use deposit addresses copied from your Custodian testnet wallets
HTETH,0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18   # Custodian Ethereum Holesky wallet
TSOL,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU  # Custodian Solana devnet wallet
TATOM,cosmos1hsk6jryyqjfhp5dhc55tc9jtckygx0eph6dd02  # Custodian Cosmos Hub testnet wallet
```

**Single-column (same asset, multiple addresses):**
```csv
# Multiple Custodian EVM addresses (e.g. different teams or environments)
0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18
0x853d46Dd7745D1643B6dA8bE8110F9e7696gZcK29
0x964e57Ee8856E2754C7c9Cf9a20bF0d8897hAdL30
```

### Run the batch

```bash
# Two-column CSV
uv run faucet batch wallets.csv

# Single-column CSV (specify the asset)
uv run faucet batch addresses.csv --asset HTETH
```

**Output:** A results table with one row per address:
- `OK` — drip succeeded
- `RATE_LIMITED` — this address was dripped recently, skipped
- `ERROR` — invalid address, unknown asset, or configuration issue
- `FAILED` — drip was attempted but the transaction failed
- `SKIP` — handler not yet implemented for this family

After the table: `Processed 5 rows: 4 succeeded, 1 failed/skipped`.

> **Batch vs drip:** `faucet batch` does not retry on failure — if a drip fails, it's marked FAILED and the batch moves on. `faucet drip` retries up to 3 times with exponential backoff. Use `faucet drip` for individual high-priority sends.

---

## 10. Monitoring and Alerts

### Check current balances

```bash
uv run faucet refill
```

Shows each asset's balance versus threshold (default: 2× the drip amount). Assets below threshold are flagged LOW with the exact top-up amount needed.

```bash
uv run faucet refill --family evm --threshold 1.0
```

### One-shot check (for cron jobs and CI)

```bash
uv run faucet check
```

Like `refill`, but exits with **code 1** if any wallet is LOW or ERROR:

```bash
uv run faucet check && echo "All wallets healthy"
```

### Daemon mode

```bash
uv run faucet monitor --interval 1h
```

Runs `check` in a loop. Accepted intervals: `30m`, `1h`, `6h`, `1d`. Press Ctrl-C to stop.

### Setting up alerts

**Step 1:** Copy the template:
```bash
mkdir -p ~/.testnet-faucet
cp config/alerts.yaml.example ~/.testnet-faucet/alerts.yaml
```

**Step 2:** Edit `~/.testnet-faucet/alerts.yaml` to enable the channels you want:

| Channel | When to enable |
|---------|---------------|
| `log` | Always on by default — no action needed |
| `slack` | If your team uses Slack |
| `webhook` | For Discord, PagerDuty, or any webhook-capable service |
| `email` | If you prefer email |

**Slack example:**
```yaml
slack:
  enabled: true
  webhook_url: https://hooks.slack.com/services/YOUR/ACTUAL/WEBHOOK
```

**Discord example:**
```yaml
webhook:
  enabled: true
  url: https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
  method: POST
```

### Cron job (runs every hour)

```bash
crontab -e
```

Add:
```
0 * * * * cd /path/to/project && uv run faucet check >> ~/.testnet-faucet/cron.log 2>&1
```

### Auto-top-up

For assets with `refill_source: airdrop` (currently `TSOL`), `faucet check` automatically attempts a self-refill when it detects a LOW balance. The output shows `auto-top: succeeded` or `auto-top: failed` for these assets.

---

## 11. Drip History

Every drip is logged to `~/.testnet-faucet/history.log` as a JSON lines file (one JSON object per line).

```bash
uv run faucet history           # 20 most recent
uv run faucet history --limit 50
```

Each line looks like:
```json
{"timestamp": "2026-03-28T09:42:11Z", "asset_id": "HTETH", "address": "0x742d35...", "amount": "0.05", "success": true, "tx_hash": "0xabc...", "error": null}
```

Search the raw log:
```bash
grep HTETH ~/.testnet-faucet/history.log
grep '"success": false' ~/.testnet-faucet/history.log
```

---

## 12. Troubleshooting

### "Rate limited: X seconds remaining"

Cooldown periods by chain type:
- **5 minutes** — EVM, Cosmos, UTXO (self-funded faucet wallet)
- **1 minute** — Solana native (devnet airdrop API)
- **24 hours** — External-faucet chains (XRP, Stellar, Sui, Aptos)

Use a different destination address, or wait for the cooldown to expire.

### "invalid address"

Each chain family has its own address format:
- EVM: `0x` + 40 hex chars (42 total)
- Solana: 32–44 Base58 chars (no `0x`)
- Cosmos: chain prefix + `1` + bech32 chars (e.g., `cosmos1...`)
- XRP: starts with `r`, 25–34 chars
- Bitcoin testnet: starts with `tb1`, `m`, or `n`

Giving an EVM address to `faucet drip TSOL` will fail — the formats are incompatible.

### "contract address is TBD" / "rpc_url is TBD"

The asset is registered but not yet operational. This is expected for many entries. To see which assets are currently live:
```bash
grep -v "TBD" config/chains.yaml | grep "rpc_url"
```

### "requires X SDK" / "SDK not installed"

Some families (Hedera, Algorand, Flow, Substrate, ICP) need Python SDKs not installed by default. These are under active development.

### "no wallet configured"

The credential variable for this chain isn't set. Run `faucet init <family>` — it will tell you exactly which variable to export.

### "Drip failed after 3 attempts"

All retries failed. Common causes:
- RPC node is temporarily down — try again later
- Faucet wallet has insufficient balance — run `faucet status` and refill
- Network congestion causing timeouts — wait and retry

### Dry run passes but real drip fails

Dry run doesn't connect to the chain. If the real drip fails:
1. Check `faucet status` — is the balance non-zero?
2. Test the RPC endpoint: `curl <rpc_url>`
3. Verify the mnemonic is set: `faucet init <family>` shows the derived address

---

## 13. Quick Reference

### CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `faucet list` | List all supported assets | `faucet list --family evm` |
| `faucet init <family>` | Derive faucet address, print funding instructions | `faucet init evm` |
| `faucet drip <asset> <address>` | Send testnet tokens (retries 3×) | `faucet drip HTETH 0x...` |
| `faucet drip <asset> <address> --dry-run` | Validate without sending | `faucet drip HTETH 0x... --dry-run` |
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

| Group | Asset IDs | Wallet credential | Address format | Pre-fund faucet wallet? |
|-------|-----------|------------------|---------------|------------------------|
| EVM | `HTETH`, `TARBETH`, `TBASE`, … | `FAUCET_MNEMONIC` | `0x...` (42 chars) | Yes |
| Solana native | `TSOL` | None | Base58 (44 chars) | No — uses devnet airdrop API |
| Solana tokens | `TSOL:USDC`, … | `FAUCET_SOLANA_KEYPAIR` | Base58 (44 chars) | Yes |
| Cosmos | `TATOM`, `TOSMO`, `TSEI`, … | `FAUCET_MNEMONIC` | `<prefix>1...` | Yes |
| External faucet | `TXRP`, `TXLM`, `TSUI`, `TAPT` | None | Chain-specific | No — calls external API |
| UTXO | `TBTC4` | `FAUCET_MNEMONIC` | `tb1...` / `m...` / `n...` | Yes |

### Related Documents

- [Blockchain & Digital Assets Primer](blockchain-primer.md) — foundational concepts and deeper reading
- [README](../README.md) — brief setup and command summary
- [`config/chains.yaml`](../config/chains.yaml) — full asset registry
- [`config/alerts.yaml.example`](../config/alerts.yaml.example) — alert channel template
