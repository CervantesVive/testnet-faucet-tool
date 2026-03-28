import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class VeChainHandler(BaseHandler):
    """Handler for VeChain chains (native VET and VTHO token transfers).

    Uses the VeChain REST API directly via aiohttp since thor-devkit is not
    installed.
    """

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Dispatches to _drip_native or _drip_token based on config['native_asset'].
        """
        try:
            if self.config.get("native_asset"):
                return await self._drip_native(address, asset_id, amount)
            else:
                return await self._drip_token(address, asset_id, amount)
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
        """Return True if *address* looks like a valid VeChain (EVM-style) address.

        VeChain uses the same address format as Ethereum: 0x + 40 hex chars.
        """
        return bool(re.match(r'^0x[0-9a-fA-F]{40}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet VET balance.

        Reads address from FAUCET_VECHAIN_ADDRESS env var.
        If not set: {asset_id: "no wallet configured"}.
        """
        asset_id = self.config.get("blockchain", "VeChain")
        try:
            faucet_address = os.environ.get("FAUCET_VECHAIN_ADDRESS")
            if not faucet_address:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config["rpc_url"].rstrip("/")
            decimals = self.config.get("decimals", 18)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url}/accounts/{faucet_address}"
                ) as resp:
                    data = await resp.json()

            balance_hex = data.get("balance", "0x0")
            formatted = f"{int(balance_hex, 16) / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'vechain'."""
        return [k for k, v in load_registry().items() if v.get("family") == "vechain"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native VET transfer.

        VeChain transactions require clause-based signing via thor-devkit,
        which is not installed.
        """
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
            error=f"{asset_id} native transfer requires thor-devkit (not installed)",
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a VTHO (or other VIP-180) token transfer.

        Token transfers require contract calls via thor-devkit, which is not
        installed.
        """
        return DripResult(
            success=False,
            tx_hash=None,
            explorer_url=None,
            error=f"{asset_id} token transfer requires thor-devkit (not installed)",
            amount=amount,
            asset=asset_id,
        )
