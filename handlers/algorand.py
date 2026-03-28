import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class AlgorandHandler(BaseHandler):
    """Handler for Algorand testnet (TALGO).

    Uses the Algorand REST API via aiohttp. Native transfers require
    py-algorand-sdk which is not installed, so drip returns an error.
    """

    def _get_faucet_address(self) -> str:
        """Return the faucet address from FAUCET_ALGORAND_ADDRESS env var."""
        address = os.environ.get("FAUCET_ALGORAND_ADDRESS", "")
        if not address:
            raise RuntimeError(
                "Algorand wallet not configured: set FAUCET_ALGORAND_ADDRESS"
            )
        return address

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

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
                error=f"{asset_id} native transfer requires py-algorand-sdk (not installed)",
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
        """Return True if *address* is a valid Algorand address.

        Algorand addresses are 58-character base32 uppercase strings.
        """
        if not address:
            return False
        return bool(re.match(r'^[A-Z2-7]{58}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name."""
        asset_id = self.config.get("blockchain", "Algorand")
        try:
            try:
                address = self._get_faucet_address()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config["rpc_url"]
            url = f"{rpc_url}/v2/accounts/{address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()

            amount = data.get("amount", 0)
            decimals = self.config.get("decimals", 6)
            formatted = f"{amount / 10 ** decimals:.6f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'algorand'."""
        return [k for k, v in load_registry().items() if v.get("family") == "algorand"]
