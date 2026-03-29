"""BalanceTable — DataTable subclass with color-coded status cells."""
from textual.widgets import DataTable
from rich.text import Text


_STATUS_STYLE = {
    "OK": "bold green",
    "LOW": "bold yellow",
    "ERROR": "bold red",
}


def _fmt_balance(balance: float | None) -> str:
    if balance is None:
        return "N/A"
    # Use up to 4 significant figures; strip trailing zeros for clean display
    return f"{balance:.4g}"


class BalanceTable(DataTable):
    """DataTable showing faucet balances with color-coded status cells.

    Rows are keyed by asset_id. update_from_results() uses update_cell() for
    surgical in-place updates that preserve scroll position.
    """

    COLUMNS = [
        ("asset", "Asset"),
        ("family", "Family"),
        ("blockchain", "Blockchain"),
        ("balance", "Balance"),
        ("status", "Status"),
    ]

    def on_mount(self) -> None:
        for col_key, label in self.COLUMNS:
            self.add_column(label, key=col_key)

    def update_from_results(self, results: list[dict]) -> None:
        """Populate or update the table from a list of check_all result dicts."""
        existing_keys = {str(row.key.value) for row in self.rows.values()}

        for r in results:
            asset_id: str = r["asset_id"]
            family: str = r.get("family", "")
            blockchain: str = r.get("blockchain", "")
            balance_str: str = _fmt_balance(r.get("balance"))
            status: str = r.get("status", "ERROR")

            status_text = Text(status, style=_STATUS_STYLE.get(status, ""))

            if asset_id in existing_keys:
                self.update_cell(asset_id, "family", family)
                self.update_cell(asset_id, "blockchain", blockchain)
                self.update_cell(asset_id, "balance", balance_str)
                self.update_cell(asset_id, "status", status_text)
            else:
                self.add_row(
                    asset_id,
                    family,
                    blockchain,
                    balance_str,
                    status_text,
                    key=asset_id,
                )
