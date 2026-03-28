import asyncio
import click
from core.registry import get_all_assets, get_handler, get_asset_config
from core.reporter import print_drip_result, print_asset_table, console
from core.rate_limiter import check_rate_limit, record_drip


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

        result = asyncio.run(handler.drip(address, asset_id, config.get("drip_amount", "0")))
        print_drip_result(result)
        if result.success:
            record_drip(asset_id, address)


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
@click.argument("family")
def init(family):
    """Initialize faucet wallets for FAMILY — derive addresses and print for manual funding."""
    if family == "evm":
        _init_evm()
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


if __name__ == "__main__":
    main()
