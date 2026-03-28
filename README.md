# BitGo Testnet Faucet Tool

CLI tool for funding test wallets across 144 assets on 70+ blockchains. Plugin-per-chain-family design with a single `faucet` entrypoint.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[evm,solana,cosmos,dev]"
```

## Configuration

Set environment variables for your faucet wallet:

```bash
# Primary wallet (used by EVM, Cosmos, UTXO, and most handlers)
export FAUCET_MNEMONIC="your twelve word mnemonic phrase here"
# Or use a private key directly
export FAUCET_PRIVATE_KEY="0x..."

# Chain-specific (optional)
export FAUCET_SOLANA_KEYPAIR="base58..."
export FAUCET_HEDERA_ACCOUNT_ID="0.0.12345"
export FAUCET_EOS_ACCOUNT="myaccount"
export FAUCET_ALGORAND_ADDRESS="ALGO..."
export FAUCET_STACKS_ADDRESS="ST..."
export FAUCET_TEZOS_ADDRESS="tz1..."
export FAUCET_VECHAIN_ADDRESS="0x..."
export FAUCET_ICP_PRINCIPAL="xxxxx-xxxxx-xxxxx-xxxxx-cai"
```

## Usage

### Fund a wallet

```bash
# Single asset
faucet drip HTETH 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18

# Multiple assets (comma-separated)
faucet drip HTETH,TARBETH 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18

# Dry run (validate without sending)
faucet drip HTETH 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18 --dry-run
```

Drips automatically retry up to 3 times with exponential backoff on transient errors (network timeouts, 5xx). Non-retryable errors (invalid address, missing SDK) fail immediately.

### Bulk fund from CSV

```bash
# Two-column CSV: asset_id,address
faucet batch wallets.csv

# Single-column CSV (addresses only) with --asset flag
faucet batch addresses.csv --asset HTETH
```

CSV format:
```csv
# Comments and empty lines are skipped
HTETH,0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18
TSOL,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
```

### List supported assets

```bash
faucet list
faucet list --family evm
```

### Monitor balances

```bash
# Quick status
faucet status
faucet status --family evm

# Dashboard with color-coded status (funded/low/error)
faucet dashboard
faucet dashboard --family cosmos

# Low-balance alerts with funding instructions
faucet refill
faucet refill --family evm --threshold 1.0
```

### View drip history

```bash
faucet history
faucet history --limit 50
```

History is stored as JSON lines at `~/.bitgo-faucet/history.log`.

### Initialize faucet wallets

```bash
faucet init evm      # Derive addresses, print funding instructions
faucet init solana
faucet init cosmos
```

## Supported Chain Families

| Family | Handler | Chains | Notes |
|--------|---------|--------|-------|
| evm | `handlers/evm.py` | 34 | EVM-compatible chains (Ethereum, Arbitrum, Base, Polygon, etc.) |
| solana | `handlers/solana.py` | 1 | Native airdrop + SPL tokens |
| cosmos | `handlers/cosmos.py` | 8 | Cosmos SDK chains |
| utxo | `handlers/utxo.py` | 6 | Bitcoin, Litecoin, Dogecoin, etc. |
| xrp | `handlers/xrp.py` | 1 | XRP Ledger |
| stellar | `handlers/stellar.py` | 1 | Stellar network |
| sui | `handlers/sui.py` | 1 | Sui devnet faucet |
| aptos | `handlers/aptos.py` | 1 | Aptos devnet faucet |
| near | `handlers/near.py` | 1 | NEAR Protocol |
| tron | `handlers/tron.py` | 1 | Tron network |
| ton | `handlers/ton.py` | 1 | TON network |
| hedera | `handlers/hedera.py` | 1 | Hedera Hashgraph |
| algorand | `handlers/algorand.py` | 1 | Algorand |
| stacks | `handlers/stacks.py` | 1 | Stacks (STX) |
| substrate | `handlers/substrate.py` | 2 | Polkadot, Polymesh |
| eos | `handlers/eos.py` | 1 | EOS |
| flow | `handlers/flow.py` | 1 | Flow |
| vechain | `handlers/vechain.py` | 1 | VeChain |
| tezos | `handlers/tezos.py` | 1 | Tezos |
| avalanche_p | `handlers/avalanche.py` | 1 | Avalanche P-Chain |
| icp | `handlers/icp.py` | 1 | Internet Computer |
| cardano | `handlers/cardano.py` | 1 | Cardano |
| zcash | `handlers/zcash.py` | 1 | Zcash |
| bittensor | `handlers/bittensor.py` | 1 | Bittensor |
| canton | `handlers/canton.py` | 1 | Canton |

## Rate Limiting

A local SQLite rate limiter at `~/.bitgo-faucet/rate_limits.db` prevents accidental wallet drain:

- Self-funded drips: 5 min cooldown per asset+address
- External faucet calls: 24 hr cooldown
- Airdrop APIs (Solana): 1 min cooldown

## Architecture

```
cli.py                    # Click CLI entrypoint
config/chains.yaml        # Asset registry (RPC URLs, amounts, metadata)
core/
  registry.py             # Loads chains.yaml, resolves family -> handler
  rate_limiter.py         # SQLite rate limiter
  reporter.py             # Rich output formatting
  retry.py                # Exponential backoff for drip operations
  logger.py               # JSON lines drip history
handlers/
  base.py                 # BaseHandler ABC (drip, validate_address, get_faucet_balance, supported_assets)
  evm.py, solana.py, ...  # One module per chain family
```

## Testing

```bash
.venv/bin/python -m pytest tests/ -q
```

531 tests covering all handlers, CLI commands, retry logic, and integration scenarios.
