import re

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class FlowHandler(BaseHandler):
    """Handler for Flow testnet (TFLOW).

    Flow uses gRPC protocol for transaction submission which requires the
    Flow SDK. Currently returns helpful errors since the SDK is not installed.
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
                error=f"{asset_id} transfer requires Flow SDK (not installed)",
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
        """Return True if *address* is a valid Flow address (16-char hex)."""
        if not address:
            return False
        addr = address.removeprefix("0x")
        return bool(re.match(r'^[0-9a-fA-F]{16}$', addr))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance.

        Flow balance queries require the Flow SDK for gRPC communication,
        so this returns a placeholder message.
        """
        asset_id = self.config.get("blockchain", "Flow")
        return {asset_id: "balance check not yet implemented"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'flow'."""
        return [k for k, v in load_registry().items() if v.get("family") == "flow"]
