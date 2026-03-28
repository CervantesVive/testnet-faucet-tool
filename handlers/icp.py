import re

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class IcpHandler(BaseHandler):
    """Handler for Internet Computer (TICP).

    ICP uses a complex canister API for transfers which requires dfx CLI
    or ic-py. Currently returns helpful errors since neither is installed.
    """

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*."""
        try:
            rpc_url = self.config.get("rpc_url", "TBD")
            if rpc_url == "TBD":
                return DripResult(
                    success=False,
                    tx_hash=None,
                    explorer_url=None,
                    error=f"{asset_id} rpc_url not configured (TBD)",
                    amount=amount,
                    asset=asset_id,
                )

            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} transfer requires dfx CLI or ic-py (not installed)",
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
        """Return True if *address* is a valid ICP address.

        Accepts two formats:
        - 64-char hex account ID
        - Principal format: groups of lowercase alphanumeric separated by dashes
        """
        if not address:
            return False
        # 64-char hex account ID
        if re.match(r'^[0-9a-fA-F]{64}$', address):
            return True
        # Principal format: groups of lowercase alphanumeric separated by dashes
        if re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(-[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$', address):
            return len(address) >= 5
        return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance.

        ICP balance queries require the canister API, so this returns
        a placeholder message.
        """
        asset_id = self.config.get("blockchain", "Internet Computer")
        return {asset_id: "balance check not yet implemented"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'icp'."""
        return [k for k, v in load_registry().items() if v.get("family") == "icp"]
