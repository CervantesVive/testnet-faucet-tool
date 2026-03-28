import re

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class AvalanchePHandler(BaseHandler):
    """Handler for Avalanche P-Chain (TAVAXP).

    The P-Chain uses a different protocol from the C-Chain (EVM).
    Transfers require complex export/import operations.
    Currently returns helpful errors since no SDK is installed.
    """

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        try:
            rpc_url = self.config.get("rpc_url", "TBD")
            if rpc_url == "TBD":
                return DripResult(
                    success=False,
                    tx_hash=None,
                    explorer_url=None,
                    error=f"{asset_id} rpc_url not yet configured (TBD)",
                    amount=amount,
                    asset=asset_id,
                )
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} P-Chain transfer requires avalanche SDK (not installed)",
                amount=amount,
                asset=asset_id,
            )
        except Exception as exc:
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=str(exc),
                amount=amount,
                asset=asset_id,
            )

    def validate_address(self, address: str) -> bool:
        if not address:
            return False
        return bool(re.match(r"^P-\w{5,}$", address))

    async def get_faucet_balance(self) -> dict[str, str]:
        asset_id = self.config.get("blockchain", "Avalanche P-Chain")
        return {asset_id: "balance check not yet implemented"}

    def supported_assets(self) -> list[str]:
        return [
            k for k, v in load_registry().items() if v.get("family") == "avalanche_p"
        ]
