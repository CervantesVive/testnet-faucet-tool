from rich.console import Console
from rich.table import Table
from handlers.base import DripResult

console = Console()


def print_drip_result(result: DripResult) -> None:
    if result.success:
        console.print(f"[green]✓[/green] Sent {result.amount} {result.asset}")
        if result.tx_hash:
            console.print(f"  TX: {result.tx_hash}")
        if result.explorer_url:
            console.print(f"  Explorer: {result.explorer_url}")
    else:
        console.print(f"[red]✗[/red] Failed to send {result.asset}: {result.error}")


def print_asset_table(assets: dict[str, dict]) -> None:
    table = Table(title="Supported Assets")
    table.add_column("Asset ID", style="cyan")
    table.add_column("Family", style="magenta")
    table.add_column("Blockchain", style="green")
    table.add_column("Network")
    table.add_column("Native", justify="center")

    for asset_id, config in sorted(assets.items()):
        table.add_row(
            asset_id,
            config.get("family", ""),
            config.get("blockchain", ""),
            config.get("network", ""),
            "✓" if config.get("native_asset") else "",
        )

    console.print(table)
