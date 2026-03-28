import re

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class BittensorHandler(BaseHandler):
    """Handler for Bittensor (TBD — rpc_url not yet configured)."""

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        try:
            rpc_url = self.config.get("rpc_url", "TBD")
            if rpc_url == "TBD":
                return DripResult(
                    success=False, tx_hash=None, explorer_url=None,
                    error=f"{asset_id} rpc_url not yet configured (TBD)",
                    amount=amount, asset=asset_id,
                )
            # Future: implement actual drip
            return DripResult(
                success=False, tx_hash=None, explorer_url=None,
                error=f"{asset_id} drip not yet implemented",
                amount=amount, asset=asset_id,
            )
        except Exception as exc:
            return DripResult(
                success=False, tx_hash=None, explorer_url=None,
                error=str(exc), amount=amount, asset=asset_id,
            )

    def validate_address(self, address: str) -> bool:
        if not address:
            return False
        return bool(re.match(r'^5[a-km-zA-HJ-NP-Z1-9]{47}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        asset_id = self.config.get("blockchain", "Bittensor")
        rpc_url = self.config.get("rpc_url", "TBD")
        if rpc_url == "TBD":
            return {asset_id: "rpc_url not yet configured (TBD)"}
        return {asset_id: "balance check not yet implemented"}

    def supported_assets(self) -> list[str]:
        return [k for k, v in load_registry().items() if v.get("family") == "bittensor"]
