import re

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class SubstrateHandler(BaseHandler):
    """Handler for Substrate-based chains (Polkadot, Polymesh).

    Requires substrate-interface SDK for websocket RPC communication.
    Currently returns helpful errors since the SDK is not installed.
    """

    # SS58 addresses: start with 5 (generic/Polkadot/Westend) or 2 (Polymesh),
    # followed by 46-47 base58 characters (no 0, O, I, l).
    _ADDRESS_RE = re.compile(r"^[25][a-km-zA-HJ-NP-Z1-9]{46,47}$")

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Currently stubbed — substrate-interface SDK is required for websocket
        RPC extrinsic submission.
        """
        try:
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} transfer requires substrate-interface SDK (not installed)",
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
        """Return True if *address* is a valid SS58 address for Polkadot or Polymesh."""
        if not address:
            return False
        return bool(self._ADDRESS_RE.match(address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance.

        Balance queries require substrate-interface SDK for websocket RPC,
        so this always returns a helpful message.
        """
        asset_id = self.config.get("blockchain", "Polkadot")
        return {asset_id: "balance check requires substrate SDK"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'substrate'."""
        return [k for k, v in load_registry().items() if v.get("family") == "substrate"]
