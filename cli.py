import asyncio
import csv
import click
from core.registry import get_all_assets, get_handler, get_asset_config
from core.reporter import print_drip_result, print_asset_table, console
from core.rate_limiter import check_rate_limit, record_drip
from core.retry import retry_drip


@click.group()
def main():
    """BitGo testnet faucet — fund test wallets across 144 assets."""


@main.command()
@click.option("--family", help="Filter by chain family (e.g. evm, solana)")
def list(family):
    """List all supported assets."""
    assets = get_all_assets()
    if family:
        assets = {k: v for k, v in assets.items() if v.get("family") == family}
    print_asset_table(assets)


@main.command()
@click.argument("asset_ids")
@click.argument("address")
@click.option("--dry-run", is_flag=True, help="Validate but don't send")
def drip(asset_ids, address, dry_run):
    """Send testnet tokens to ADDRESS for one or more ASSET_IDS (comma-separated)."""
    for asset_id in asset_ids.split(","):
        asset_id = asset_id.strip()
        try:
            config = get_asset_config(asset_id)
        except KeyError as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        try:
            handler = get_handler(asset_id)
        except NotImplementedError as e:
            console.print(f"[yellow]Skipping {asset_id}:[/yellow] {e}")
            continue

        if not handler.validate_address(address):
            console.print(f"[red]Invalid address for {asset_id}:[/red] {address}")
            continue

        if dry_run:
            console.print(f"[dim]Dry run:[/dim] would send {config.get('drip_amount')} {asset_id} to {address}")
            continue

        allowed, remaining = check_rate_limit(asset_id, address)
        if not allowed:
            console.print(f"[yellow]Rate limited:[/yellow] {asset_id} → {address} — try again in {remaining:.0f}s")
            continue

        result = asyncio.run(retry_drip(handler, address, asset_id, config.get("drip_amount", "0")))
        print_drip_result(result)
        if result.success:
            record_drip(asset_id, address)


@main.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--asset", "default_asset", default=None, help="Default asset ID for single-column CSV files")
def batch(csv_file, default_asset):
    """Run drip requests from a CSV file.

    CSV format: either 'asset_id,address' (2 columns) or 'address' (1 column, requires --asset flag).
    Lines starting with # and empty lines are skipped.
    """
    from rich.table import Table

    results = []

    with open(csv_file, newline="") as f:
        for line_num, raw_line in enumerate(f, start=1):
            stripped = raw_line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Parse columns
            reader = csv.reader([stripped])
            row = next(reader)

            if len(row) == 2:
                asset_id, address = row[0].strip(), row[1].strip()
            elif len(row) == 1 and default_asset:
                asset_id, address = default_asset, row[0].strip()
            elif len(row) == 1 and not default_asset:
                results.append({
                    "asset": "?",
                    "address": row[0].strip(),
                    "status": "ERROR",
                    "detail": "Single-column CSV requires --asset flag",
                })
                continue
            else:
                results.append({
                    "asset": "?",
                    "address": stripped[:40],
                    "status": "ERROR",
                    "detail": f"Malformed row (line {line_num})",
                })
                continue

            # Get config
            try:
                config = get_asset_config(asset_id)
            except KeyError as e:
                results.append({
                    "asset": asset_id,
                    "address": address,
                    "status": "ERROR",
                    "detail": str(e),
                })
                continue

            # Get handler
            try:
                handler = get_handler(asset_id)
            except NotImplementedError as e:
                results.append({
                    "asset": asset_id,
                    "address": address,
                    "status": "SKIP",
                    "detail": str(e),
                })
                continue

            # Validate address
            if not handler.validate_address(address):
                results.append({
                    "asset": asset_id,
                    "address": address,
                    "status": "ERROR",
                    "detail": "Invalid address",
                })
                continue

            # Rate limit check
            allowed, remaining = check_rate_limit(asset_id, address)
            if not allowed:
                results.append({
                    "asset": asset_id,
                    "address": address,
                    "status": "RATE_LIMITED",
                    "detail": f"Try again in {remaining:.0f}s",
                })
                continue

            # Execute drip
            try:
                result = asyncio.run(handler.drip(address, asset_id, config.get("drip_amount", "0")))
                if result.success:
                    record_drip(asset_id, address)
                    results.append({
                        "asset": asset_id,
                        "address": address,
                        "status": "OK",
                        "detail": result.tx_hash or "",
                    })
                else:
                    results.append({
                        "asset": asset_id,
                        "address": address,
                        "status": "FAILED",
                        "detail": result.error or "Unknown error",
                    })
            except Exception as e:
                results.append({
                    "asset": asset_id,
                    "address": address,
                    "status": "ERROR",
                    "detail": str(e),
                })

    # Print summary table
    if not results:
        console.print("[yellow]No valid rows found in CSV file.[/yellow]")
        return

    table = Table(title="Batch Drip Results")
    table.add_column("Asset")
    table.add_column("Address")
    table.add_column("Status")
    table.add_column("Detail")

    for r in results:
        style = "green" if r["status"] == "OK" else "red" if r["status"] in ("ERROR", "FAILED") else "yellow"
        table.add_row(r["asset"], r["address"], f"[{style}]{r['status']}[/{style}]", r["detail"])

    console.print(table)

    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = len(results) - ok_count
    console.print(f"\nProcessed {len(results)} rows: {ok_count} succeeded, {fail_count} failed/skipped")


@main.command()
@click.option("--family", help="Filter by chain family")
def status(family):
    """Show faucet wallet balances."""
    assets = get_all_assets()
    native_assets = {k: v for k, v in assets.items() if v.get("native_asset")}
    if family:
        native_assets = {k: v for k, v in native_assets.items() if v.get("family") == family}

    for asset_id in sorted(native_assets):
        try:
            handler = get_handler(asset_id)
            balances = asyncio.run(handler.get_faucet_balance())
            for token, balance in balances.items():
                console.print(f"{asset_id}: {balance} {token}")
        except NotImplementedError:
            console.print(f"[dim]{asset_id}: handler not yet implemented[/dim]")
        except Exception as e:
            console.print(f"[red]{asset_id}: error — {e}[/red]")


@main.command()
@click.option("--family", help="Filter by chain family")
@click.option("--threshold", type=float, default=None, help="Low-balance threshold (default: 2x drip_amount)")
def refill(family, threshold):
    """Check faucet balances and flag wallets that need refilling."""
    from rich.table import Table

    assets = get_all_assets()
    native_assets = {k: v for k, v in assets.items() if v.get("native_asset")}
    if family:
        native_assets = {k: v for k, v in native_assets.items() if v.get("family") == family}

    table = Table(title="Faucet Refill Status")
    table.add_column("Asset")
    table.add_column("Blockchain")
    table.add_column("Balance")
    table.add_column("Threshold")
    table.add_column("Status")
    table.add_column("Action")

    ok_count = 0
    low_count = 0
    error_count = 0

    for asset_id in sorted(native_assets):
        cfg = native_assets[asset_id]
        blockchain = cfg.get("blockchain", "")
        drip_amount = cfg.get("drip_amount", "0")
        asset_threshold = threshold if threshold is not None else 2.0 * float(drip_amount)

        try:
            handler = get_handler(asset_id)
            balances = asyncio.run(handler.get_faucet_balance())
        except Exception as e:
            error_count += 1
            table.add_row(
                asset_id, blockchain, "N/A", f"{asset_threshold:.4g}",
                "[red]ERROR[/red]", f"[red]{e}[/red]",
            )
            console.print(f"ERROR {asset_id}")
            continue

        # Use the first balance value from the dict
        balance_str = next(iter(balances.values()), "N/A") if balances else "N/A"

        try:
            balance_val = float(balance_str)
        except (ValueError, TypeError):
            error_count += 1
            table.add_row(
                asset_id, blockchain, balance_str, f"{asset_threshold:.4g}",
                "[red]ERROR[/red]", f"[red]{balance_str}[/red]",
            )
            console.print(f"ERROR {asset_id}")
            continue

        if balance_val >= asset_threshold:
            ok_count += 1
            status_label = "[green]OK[/green]"
            action = ""
            console.print(f"OK {asset_id}")
        else:
            low_count += 1
            status_label = "[yellow]LOW[/yellow]"
            action = f"[yellow]Fund with >= {asset_threshold - balance_val:.4g} to reach threshold[/yellow]"
            console.print(f"LOW {asset_id}")

        table.add_row(
            asset_id, blockchain, f"{balance_val:.4g}", f"{asset_threshold:.4g}",
            status_label, action,
        )

    console.print(table)
    console.print(f"\nSummary: {ok_count} OK, {low_count} LOW, {error_count} ERROR")


@main.command()
@click.argument("family")
def init(family):
    """Initialize faucet wallets for FAMILY — derive addresses and print for manual funding."""
    if family == "evm":
        _init_evm()
    elif family == "solana":
        _init_solana()
    elif family == "cosmos":
        _init_cosmos()
    elif family == "sui":
        _init_sui()
    elif family == "aptos":
        _init_aptos()
    elif family == "near":
        _init_near()
    elif family == "xrp":
        _init_xrp()
    elif family == "stellar":
        _init_stellar()
    elif family == "tron":
        _init_tron()
    elif family == "ton":
        _init_ton()
    elif family == "utxo":
        _init_utxo()
    elif family == "hedera":
        _init_hedera()
    elif family == "algorand":
        _init_algorand()
    elif family == "cardano":
        _init_cardano()
    elif family == "eos":
        _init_eos()
    elif family == "substrate":
        _init_substrate()
    elif family == "stacks":
        _init_stacks()
    elif family == "flow":
        _init_flow()
    elif family == "vechain":
        _init_vechain()
    elif family == "tezos":
        _init_tezos()
    elif family == "zcash":
        _init_zcash()
    elif family == "icp":
        _init_icp()
    elif family == "bittensor":
        _init_bittensor()
    elif family == "avalanche_p":
        _init_avalanche_p()
    elif family == "canton":
        _init_canton()
    else:
        console.print(f"[yellow]init for {family} not yet implemented[/yellow]")


def _init_evm():
    """Derive EVM faucet address and print for manual funding."""
    import os
    from eth_account import Account

    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")

    if mnemonic:
        Account.enable_unaudited_hdwallet_features()
        account = Account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")
        console.print("[green]EVM faucet address (BIP-44 m/44'/60'/0'/0/0):[/green]")
        console.print(f"  {account.address}")
    elif private_key:
        account = Account.from_key(private_key)
        console.print("[green]EVM faucet address (from FAUCET_PRIVATE_KEY):[/green]")
        console.print(f"  {account.address}")
    else:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return

    # Show all EVM chains that need to be funded
    assets = get_all_assets()
    evm_native = {k: v for k, v in assets.items() if v.get("family") == "evm" and v.get("native_asset")}

    console.print(f"\n[bold]Fund this address on {len(evm_native)} EVM chains:[/bold]")

    from rich.table import Table
    table = Table()
    table.add_column("Asset")
    table.add_column("Chain")
    table.add_column("Network")
    table.add_column("Drip Amount")

    for asset_id, cfg in sorted(evm_native.items()):
        table.add_row(
            asset_id,
            cfg.get("blockchain", ""),
            cfg.get("network", ""),
            cfg.get("drip_amount", ""),
        )
    console.print(table)


def _init_solana():
    """Derive or load Solana faucet keypair and print for manual funding."""
    import os

    keypair_b58 = os.environ.get("FAUCET_SOLANA_KEYPAIR")
    mnemonic = os.environ.get("FAUCET_MNEMONIC")

    if keypair_b58:
        from solders.keypair import Keypair
        keypair = Keypair.from_base58_string(keypair_b58)
        console.print("[green]Solana faucet address (from FAUCET_SOLANA_KEYPAIR):[/green]")
    elif mnemonic:
        from solders.keypair import Keypair
        keypair = Keypair.from_seed_phrase_and_passphrase(mnemonic, "")
        console.print("[green]Solana faucet address (BIP-39 mnemonic, ed25519):[/green]")
    else:
        console.print("[red]Error:[/red] Set FAUCET_SOLANA_KEYPAIR or FAUCET_MNEMONIC environment variable")
        return

    pubkey = str(keypair.pubkey())
    console.print(f"  {pubkey}")
    console.print()
    console.print("[bold]To fund this wallet on Solana devnet:[/bold]")
    console.print(f"  solana airdrop 2 {pubkey} --url devnet")
    console.print()
    console.print("[dim]Or visit: https://faucet.solana.com and paste the address above[/dim]")


def _init_cosmos():
    """Derive Cosmos faucet addresses per chain and print for manual funding."""
    import os
    from cosmpy.aerial.wallet import LocalWallet
    from cosmpy.crypto.keypairs import PrivateKey
    from rich.table import Table

    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")

    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return

    assets = get_all_assets()
    cosmos_native = {
        k: v for k, v in assets.items()
        if v.get("family") == "cosmos" and v.get("native_asset")
    }

    # Derive one address per unique bech32_prefix (same key, different prefix = different address)
    prefix_to_address = {}
    for cfg in cosmos_native.values():
        prefix = cfg.get("bech32_prefix", "cosmos")
        if prefix not in prefix_to_address:
            if mnemonic:
                wallet = LocalWallet.from_mnemonic(mnemonic, prefix=prefix)
            else:
                key = private_key.lstrip("0x") if private_key.startswith("0x") else private_key
                wallet = LocalWallet(PrivateKey(bytes.fromhex(key)), prefix=prefix)
            prefix_to_address[prefix] = str(wallet.address())

    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Cosmos faucet addresses (from {source}):[/green]")
    for prefix, address in sorted(prefix_to_address.items()):
        console.print(f"  {prefix}: {address}")
    console.print()

    table = Table()
    table.add_column("Asset")
    table.add_column("Chain")
    table.add_column("Network")
    table.add_column("Address")
    table.add_column("Drip Amount")

    for asset_id, cfg in sorted(cosmos_native.items()):
        prefix = cfg.get("bech32_prefix", "cosmos")
        table.add_row(
            asset_id,
            cfg.get("blockchain", ""),
            cfg.get("network", ""),
            prefix_to_address[prefix],
            cfg.get("drip_amount", ""),
        )
    console.print(table)


def _init_sui():
    """Print Sui faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Sui faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Sui testnet wallet at: https://faucet.devnet.sui.io/[/dim]")


def _init_aptos():
    """Print Aptos faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Aptos faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Aptos testnet wallet at: https://aptos.dev/en/network/faucet[/dim]")


def _init_near():
    """Print NEAR faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]NEAR faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your NEAR testnet wallet at: https://near-faucet.io/[/dim]")


def _init_xrp():
    """Derive XRP faucet address using xrpl-py if available."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    try:
        from xrpl.wallet import Wallet
        if mnemonic:
            wallet = Wallet.from_mnemonic(mnemonic)
        else:
            wallet = Wallet.from_seed(private_key)
        console.print("[green]XRP faucet address:[/green]")
        console.print(f"  {wallet.classic_address}")
    except Exception:
        source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
        console.print(f"[green]XRP faucet wallet configured (from {source})[/green]")
        console.print("[dim]Fund your XRP testnet wallet at: https://xrpl.org/xrp-testnet-faucet.html[/dim]")


def _init_stellar():
    """Derive Stellar faucet address using stellar-sdk if available."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    try:
        from stellar_sdk import Keypair
        if private_key:
            keypair = Keypair.from_secret(private_key)
        else:
            # Derive from mnemonic using default path
            keypair = Keypair.from_mnemonic_phrase(mnemonic)
        console.print("[green]Stellar faucet address:[/green]")
        console.print(f"  {keypair.public_key}")
    except Exception:
        source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
        console.print(f"[green]Stellar faucet wallet configured (from {source})[/green]")
        console.print("[dim]Fund your Stellar testnet wallet at: https://laboratory.stellar.org/#account-creator[/dim]")


def _init_tron():
    """Print Tron faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Tron faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Tron testnet wallet at: https://nileex.io/join/getJoinPage[/dim]")


def _init_ton():
    """Print TON faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]TON faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your TON testnet wallet at: https://t.me/testgiver_ton_bot[/dim]")


def _init_utxo():
    """Print UTXO faucet wallet configuration."""
    import os
    from rich.table import Table

    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]UTXO faucet wallet configured (from {source})[/green]")

    assets = get_all_assets()
    utxo_native = {
        k: v for k, v in assets.items()
        if v.get("family") == "utxo" and v.get("native_asset")
    }

    console.print(f"\n[bold]Fund faucet wallet on {len(utxo_native)} UTXO chains:[/bold]")

    table = Table()
    table.add_column("Asset")
    table.add_column("Blockchain")
    table.add_column("Coin Type")
    table.add_column("Drip Amount")

    for asset_id, cfg in sorted(utxo_native.items()):
        table.add_row(
            asset_id,
            cfg.get("blockchain", ""),
            str(cfg.get("coin_type", "")),
            cfg.get("drip_amount", ""),
        )
    console.print(table)


def _init_hedera():
    """Print Hedera faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Hedera faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Hedera testnet wallet at: https://portal.hedera.com/[/dim]")


def _init_algorand():
    """Print Algorand faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Algorand faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Algorand testnet wallet at: https://bank.testnet.algorand.network/[/dim]")


def _init_cardano():
    """Print Cardano faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Cardano faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Cardano testnet wallet at: https://docs.cardano.org/cardano-testnets/tools/faucet/[/dim]")


def _init_eos():
    """Print EOS faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    eos_account = os.environ.get("FAUCET_EOS_ACCOUNT")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]EOS faucet wallet configured (from {source})[/green]")
    if eos_account:
        console.print(f"[green]EOS account: {eos_account}[/green]")
    console.print("[dim]Fund your EOS testnet wallet at: https://jungle4.cryptolions.io/#home[/dim]")


def _init_substrate():
    """Print Substrate faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Substrate faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Substrate testnet wallet at: https://faucet.polkadot.io/westend[/dim]")


def _init_stacks():
    """Print Stacks faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Stacks faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Stacks testnet wallet at: https://explorer.hiro.so/sandbox/faucet?chain=testnet[/dim]")


def _init_flow():
    """Print Flow faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Flow faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Flow testnet wallet at: https://testnet-faucet.onflow.org/[/dim]")


def _init_vechain():
    """Print VeChain faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]VeChain faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your VeChain testnet wallet at: https://faucet.vecha.in/[/dim]")


def _init_tezos():
    """Print Tezos faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Tezos faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Tezos testnet wallet at: https://faucet.ghostnet.teztnets.com/[/dim]")


def _init_zcash():
    """Print Zcash faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Zcash faucet wallet configured (from {source})[/green]")
    console.print("[dim]No public testnet faucet known — manual funding required[/dim]")


def _init_icp():
    """Print ICP faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    icp_principal = os.environ.get("FAUCET_ICP_PRINCIPAL")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]ICP faucet wallet configured (from {source})[/green]")
    if icp_principal:
        console.print(f"[green]ICP principal: {icp_principal}[/green]")
    console.print("[dim]Fund your ICP testnet wallet at: https://faucet.dfinity.org/[/dim]")


def _init_bittensor():
    """Print Bittensor faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Bittensor faucet wallet configured (from {source})[/green]")
    console.print("[dim]No public testnet faucet known — manual funding required[/dim]")


def _init_avalanche_p():
    """Print Avalanche P-Chain faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Avalanche P-Chain faucet wallet configured (from {source})[/green]")
    console.print("[dim]Fund your Avalanche P-Chain testnet wallet at: https://core.app/tools/testnet-faucet/[/dim]")


def _init_canton():
    """Print Canton faucet wallet configuration."""
    import os
    mnemonic = os.environ.get("FAUCET_MNEMONIC")
    private_key = os.environ.get("FAUCET_PRIVATE_KEY")
    if not mnemonic and not private_key:
        console.print("[red]Error:[/red] Set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY environment variable")
        return
    source = "FAUCET_MNEMONIC" if mnemonic else "FAUCET_PRIVATE_KEY"
    console.print(f"[green]Canton faucet wallet configured (from {source})[/green]")
    console.print("[dim]No public testnet faucet known — manual funding required[/dim]")


if __name__ == "__main__":
    main()
