import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class StacksHandler(BaseHandler):
    """Handler for Stacks testnet (TSTX).

    Uses the Stacks Node API via aiohttp. Native transfers require
    a Stacks SDK which is not installed, so drip returns an error.
    """

    def _get_faucet_address(self) -> str:
        """Return the faucet address from FAUCET_STACKS_ADDRESS env var."""
        address = os.environ.get("FAUCET_STACKS_ADDRESS", "")
        if not address:
            raise RuntimeError(
                "Stacks wallet not configured: set FAUCET_STACKS_ADDRESS"
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
                error=f"{asset_id} native transfer requires stacks SDK (not installed)",
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
        """Return True if *address* is a valid Stacks testnet address.

        Stacks testnet addresses start with "ST" and are 41-42 characters total.
        """
        if not address:
            return False
        return bool(re.match(r'^ST[0-9A-Z]{39,40}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name."""
        asset_id = self.config.get("blockchain", "Stacks")
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

            balance_hex = data.get("balance", "0x0")
            # Strip 0x prefix if present
            if balance_hex.startswith("0x"):
                balance_hex = balance_hex[2:]
            balance = int(balance_hex, 16)
            decimals = self.config.get("decimals", 6)
            formatted = f"{balance / 10 ** decimals:.6f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'stacks'."""
        return [k for k, v in load_registry().items() if v.get("family") == "stacks"]
