# Blockchain & Digital Assets Primer

A beginner-friendly guide to the concepts you need to understand the Testnet Faucet Tool.

---

## Table of Contents

1. [What Is a Blockchain?](#1-what-is-a-blockchain)
2. [What Are Digital Assets?](#2-what-are-digital-assets)
3. [Native Coins vs. Tokens](#3-native-coins-vs-tokens)
4. [Addresses and Wallets](#4-addresses-and-wallets)
5. [Testnets and Faucets](#5-testnets-and-faucets)
6. [Chain Families](#6-chain-families)
7. [How This All Maps to the Faucet Tool](#7-how-this-all-maps-to-the-faucet-tool)
8. [Glossary](#8-glossary)
9. [Further Reading & Videos](#9-further-reading--videos)

---

## 1. What Is a Blockchain?

A blockchain is a shared, tamper-resistant ledger. Think of it as a spreadsheet that thousands of computers maintain simultaneously. Once a row (a "block") is added, it can't be edited or deleted.

Every blockchain keeps track of one core thing: **who owns what**. When you send someone cryptocurrency, the blockchain records that transfer as a **transaction** inside a new block. That transaction gets a unique identifier called a **transaction hash** (tx hash) that you can look up on a **block explorer** — a website that lets you browse blockchain data.

**Key takeaway:** Each blockchain is its own independent network with its own rules, its own coin, and its own history of transactions.

### Reading
- [Blockchain Explained (Investopedia)](https://www.investopedia.com/terms/b/blockchain.asp)

### Videos
- [How does a blockchain work? (Simply Explained, 6 min)](https://www.youtube.com/watch?v=SSo_EIwHSd4)
- [Blockchain Demo (Anders Brownworth, 18 min)](https://www.youtube.com/watch?v=_160oMzblY8)

---

## 2. What Are Digital Assets?

A **digital asset** is anything of value that lives on a blockchain. The two most common kinds are:

| Type | What it is | Example |
|------|-----------|---------|
| **Coin** | The blockchain's built-in currency, used to pay transaction fees | ETH on Ethereum, SOL on Solana, BTC on Bitcoin |
| **Token** | A custom asset created by a smart contract *on top of* an existing blockchain | USDC on Ethereum, BUSD on BNB Smart Chain |

In this tool, every asset has an **asset ID** like `HTETH` (Holesky testnet ETH) or `HTETH:GOUSD` (the GOUSD token on Holesky Ethereum). The colon format `CHAIN:TOKEN` tells you the token lives on that chain.

### Reading
- [Coins vs. Tokens (Ledger Academy)](https://www.ledger.com/academy/crypto/what-is-the-difference-between-coins-and-tokens)

### Videos
- [Crypto Coins vs Tokens (Whiteboard Crypto, 8 min)](https://www.youtube.com/watch?v=422HORNUfkU)

---

## 3. Native Coins vs. Tokens

This distinction matters because the faucet tool handles them differently.

**Native coins** (e.g., ETH, SOL, ATOM) are the "fuel" of their blockchain. You need them to do anything — every transaction costs a small fee paid in the native coin. Sending a native coin is a simple value transfer.

**Tokens** (e.g., USDC, DAI) are created by deploying a **smart contract** — a small program that lives on the blockchain and keeps its own ledger of who owns how many of that token. Sending a token means calling a function on that contract, which still costs a fee in the native coin.

In the faucet tool's config, this is represented by two fields:

```yaml
# Native coin — simple transfer
HTETH:
  native_asset: true

# Token — requires a contract address
"HTETH:GOUSD":
  native_asset: false
  contract_address: "0x..."
```

### Reading
- [What Are ERC-20 Tokens? (ethereum.org)](https://ethereum.org/en/developers/docs/standards/tokens/erc-20/)

---

## 4. Addresses and Wallets

A **wallet** is software that manages your private key (a secret number) and derives a **public address** from it. The address is what you share with others so they can send you assets — like an email address for money.

Different blockchains use completely different address formats:

| Family | Example address format |
|--------|----------------------|
| EVM (Ethereum, Polygon, etc.) | `0x742d35Cc6634C0532925a3b844Bc9e7595f2bD28` |
| Solana | `7v91N7iZ9mNicL8WfG6cgSCKyRXydQjLh6UYBWwm6y1Q` |
| Bitcoin (UTXO) | `tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx` |
| Cosmos | `cosmos1hsk6jryyqjfhp5dhc55tc9jtckygx0eph6dd02` |
| XRP | `rN7n3473SaZBCG4dFL83w7p1W9cgZw6maf` |

This is one of the reasons the faucet tool needs different **handlers** for different chain families — each family has its own address validation rules, its own way of constructing and signing transactions, and its own RPC protocol.

### Reading
- [What Is a Crypto Wallet? (Coinbase)](https://www.coinbase.com/learn/crypto-basics/what-is-a-crypto-wallet)

### Videos
- [Crypto Wallets Explained (Whiteboard Crypto, 10 min)](https://www.youtube.com/watch?v=d8IBpfs9bf4)

---

## 5. Testnets and Faucets

### Mainnet vs. Testnet

Every major blockchain runs at least two networks:

- **Mainnet** — the real network where assets have real value.
- **Testnet** — a mirror of mainnet where assets are free and worthless. Developers use it to test their applications without risking real money.

Testnets try to behave identically to mainnet so that code tested on a testnet will work the same way on mainnet. Each testnet has its own name — for example, Ethereum's current testnet is called **Holesky**, and Polygon's is called **Amoy**.

### What Is a Faucet?

A **faucet** is a service that gives away free testnet tokens. Since testnet coins have no value, faucets exist purely as a developer convenience. You provide your testnet wallet address, and the faucet sends you some testnet coins so you can test your application.

**This tool is a faucet.** It holds testnet coins in its own wallet and sends small amounts (a "drip") to addresses you specify.

### Reading
- [What Are Testnets? (Alchemy)](https://www.alchemy.com/overviews/what-are-testnets)

### Videos
- [Testnets Explained (Dapp University, 5 min)](https://www.youtube.com/watch?v=So7TNVhEZMk)

---

## 6. Chain Families

This is the most important concept for understanding the faucet tool's architecture.

### What Is a Chain Family?

A **chain family** is a group of blockchains that share the same underlying technology — the same transaction format, the same address format, and the same way of communicating with nodes (RPC protocol). If you know how to talk to one chain in the family, you can talk to all of them with minor configuration changes.

Think of it like car engines: a Honda Civic and a Honda Accord have different bodies, but the engine works the same way. A mechanic who knows Honda engines can work on both.

### The Families in This Tool

The faucet tool supports **144 assets** across **24 chain families**. Here's a tour of the major ones:

#### EVM Family (72 assets) — The Largest Group

The **Ethereum Virtual Machine (EVM)** is the runtime that powers Ethereum. Dozens of other blockchains adopted the same technology, which means one handler (`EvmHandler`) can serve all of them. This includes Ethereum, Polygon, Arbitrum, Optimism, Base, Avalanche C-Chain, BNB Smart Chain, and many more.

What they share:
- Addresses start with `0x` and are 40 hex characters
- Transactions are signed using the same algorithm (ECDSA with secp256k1)
- Communication happens via the same JSON-RPC protocol
- Smart contracts use the same bytecode format

The only things that change between EVM chains are the **RPC URL** (which node to talk to) and the **chain ID** (a unique number identifying the network).

#### Solana Family (12 assets)

Solana is a high-throughput blockchain with a completely different architecture from EVM chains. It uses a different address format (Base58 public keys), a different transaction model (instructions instead of contract calls), and its own RPC protocol.

#### Cosmos Family (14 assets)

Cosmos is an ecosystem of independent blockchains (called "zones") that can communicate with each other via the IBC protocol. They share the `cosmos`-prefixed address format (Bech32) and similar transaction structures. Includes chains like Cosmos Hub, Osmosis, and others.

#### UTXO Family (6 assets)

**UTXO** stands for "Unspent Transaction Output" — it's the transaction model that Bitcoin invented. Instead of accounts with balances (like Ethereum), UTXO chains track individual "coins" that get spent and created with each transaction. Think of it like physical cash: you hand over a $20 bill and get change back. Bitcoin, Litecoin, and Dogecoin all use this model.

#### Other Families

| Family | Chains | Notable trait |
|--------|--------|--------------|
| **XRP** | XRP Ledger | Purpose-built for payments; 3-5 second settlement |
| **Stellar** | Stellar network | Similar to XRP in philosophy; focuses on cross-border payments |
| **Sui** | Sui network | Move-based language; object-centric model |
| **Aptos** | Aptos network | Also Move-based; parallel transaction execution |
| **Tron** | Tron network | EVM-compatible but uses its own address format (Base58Check) |
| **TON** | The Open Network | Originally built for Telegram; unique "bag of cells" data format |
| **Near** | NEAR Protocol | Human-readable account names (e.g., `alice.near`) |
| **Hedera** | Hedera network | Hashgraph consensus; account IDs like `0.0.12345` |
| **Algorand** | Algorand network | Pure proof-of-stake; 58-char Base32 addresses |
| **Substrate** | Polkadot, Kusama | Framework for building custom blockchains |
| **Stacks** | Stacks (Bitcoin L2) | Smart contracts secured by Bitcoin |
| **Flow** | Flow network | Built for NFTs and games (NBA Top Shot) |
| **Tezos** | Tezos network | Self-amending blockchain; addresses start with `tz1` |
| **VeChain** | VeChain network | Supply chain focus; dual-token model (VET + VTHO) |
| **EOS** | EOS network | Delegated proof-of-stake; human-readable account names |
| **ICP** | Internet Computer | Canister-based smart contracts by DFINITY |
| **Cardano** | Cardano network | Academic peer-reviewed design; eUTXO model |
| **Zcash** | Zcash network | Privacy-focused; supports shielded transactions |
| **Bittensor** | Bittensor network | Decentralized AI/ML network |
| **Canton** | Canton network | Enterprise blockchain by Digital Asset |
| **Avalanche P** | Avalanche P-Chain | Manages validators and subnets (not EVM-compatible) |

### Reading
- [Ethereum Virtual Machine (ethereum.org)](https://ethereum.org/en/developers/docs/evm/)
- [What Is Cosmos? (Cosmos docs)](https://docs.cosmos.network/v0.50/learn/intro/overview)
- [Bitcoin's UTXO Model (River Financial)](https://river.com/learn/bitcoins-utxo-model/)

### Videos
- [EVM Explained (Finematics, 8 min)](https://www.youtube.com/watch?v=GPoze5RmDVU)
- [Cosmos Explained (Finematics, 12 min)](https://www.youtube.com/watch?v=HFynJhOt5Lc)
- [UTXO vs Account Model (Whiteboard Crypto, 10 min)](https://www.youtube.com/watch?v=jbyUVB_mBFQ)

---

## 7. How This All Maps to the Faucet Tool

Now you can connect the dots between blockchain concepts and the tool's codebase.

### The Config File: `config/chains.yaml`

Every asset the faucet can dispense is registered here. Each entry looks like this:

```yaml
HTETH:                           # asset ID
  family: evm                    # Chain family (determines which handler to use)
  blockchain: Ethereum           # Human-readable chain name
  network: holesky               # Which testnet
  rpc_url: https://rpc.holesky.ethpandaops.io  # Node to talk to
  explorer: https://holesky.etherscan.io/tx/{tx_hash}  # Where to view transactions
  native_asset: true             # Coin (true) or token (false)
  drip_amount: "0.05"            # How much to send per request
  decimals: 18                   # Smallest unit (10^-18 of 1 ETH = 1 wei)
```

### The Registry: `core/registry.py`

Maps each `family` name to its handler class. When you request a drip for `HTETH`, the registry:
1. Looks up the asset in `chains.yaml`
2. Reads `family: evm`
3. Finds `EvmHandler` in the family-to-handler map
4. Creates (or reuses) an instance of `EvmHandler` with that asset's config

### The Handlers: `handlers/<family>.py`

Each handler knows how to do four things for its chain family:
1. **`drip()`** — Send testnet tokens to an address
2. **`validate_address()`** — Check if an address is valid for this chain
3. **`get_faucet_balance()`** — Check how many tokens the faucet wallet still has
4. **`supported_assets()`** — List which assets this handler can serve

Because all EVM chains work the same way, one `EvmHandler` serves 72 assets. Meanwhile, Solana needs its own `SolanaHandler`, Cosmos needs `CosmosHandler`, and so on — each implementing those same four methods but using chain-specific libraries and protocols.

### The Flow of a Drip Request

```
User: "Send me 0.05 HTETH to 0xabc..."
  |
  v
CLI parses the command
  |
  v
Registry looks up HTETH -> family: evm -> EvmHandler
  |
  v
EvmHandler.validate_address("0xabc...") -> valid?
  |
  v
EvmHandler.drip("0xabc...", "HTETH", "0.05")
  |        |
  |        v
  |   Connects to rpc_url, builds & signs transaction, broadcasts it
  |
  v
Returns DripResult with tx_hash and explorer URL
  |
  v
CLI prints: "Sent 0.05 HTETH - view at https://holesky.etherscan.io/tx/0x..."
```

---

## 8. Glossary

| Term | Definition |
|------|-----------|
| **Asset** | Any coin or token tracked by the faucet tool |
| **Asset ID** | This tool's identifier for an asset (e.g., `HTETH`, `TSOL`) |
| **Block** | A batch of transactions permanently recorded on the blockchain |
| **Block explorer** | A website for browsing blockchain transactions and addresses |
| **Chain family** | A group of blockchains that share the same technology and can be handled by the same code |
| **Decimals** | How divisible an asset is; ETH has 18 decimals (1 ETH = 10^18 wei) |
| **Drip** | A single disbursement of testnet tokens from the faucet |
| **Faucet** | A service that distributes free testnet tokens to developers |
| **Handler** | A Python class that knows how to interact with a specific chain family |
| **Mainnet** | The production blockchain network where assets have real value |
| **Native asset** | The built-in coin of a blockchain (e.g., ETH for Ethereum) |
| **RPC** | Remote Procedure Call — the protocol used to communicate with blockchain nodes |
| **Smart contract** | A program deployed on a blockchain that can hold and transfer tokens |
| **Testnet** | A test version of a blockchain where assets are free and worthless |
| **Token** | A custom asset created via smart contract on an existing blockchain |
| **Transaction hash** | A unique identifier for a transaction on the blockchain |
| **UTXO** | Unspent Transaction Output — Bitcoin's model for tracking ownership |
| **Wallet** | Software that manages private keys and derives public addresses |

---

## 9. Further Reading & Videos

### Foundational
- **Book:** [Mastering Bitcoin (Andreas Antonopoulos)](https://github.com/bitcoinbook/bitcoinbook) — free, open-source; the definitive technical introduction
- **Book:** [Mastering Ethereum (Andreas Antonopoulos & Gavin Wood)](https://github.com/ethereumbook/ethereumbook) — free, open-source; EVM deep dive
- **Course:** [Blockchain Basics (Coursera, University at Buffalo)](https://www.coursera.org/learn/blockchain-basics) — structured 4-week beginner course

### Videos (General)
- [But how does bitcoin actually work? (3Blue1Brown, 26 min)](https://www.youtube.com/watch?v=bBC-nXj3Ng4) — the best visual explanation of how blockchains work under the hood
- [Smart Contracts Explained (Finematics, 7 min)](https://www.youtube.com/watch?v=pyaIppMhuic)
- [Layer 2 Scaling Explained (Finematics, 15 min)](https://www.youtube.com/watch?v=BgCgauWVTs0)

### Testnet-Specific
- [Ethereum Testnets Overview (ethereum.org)](https://ethereum.org/en/developers/docs/networks/#ethereum-testnets)
- [Solana Devnet & Testnet (Solana docs)](https://docs.solana.com/clusters)
- [Bitcoin Testnet (Bitcoin Wiki)](https://en.bitcoin.it/wiki/Testnet)
