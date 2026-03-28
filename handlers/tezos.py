import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class TezosHandler(BaseHandler):
    """Handler for Tezos chains (TXTZ on ghostnet).

    Uses the Tezos RPC API directly via aiohttp since pytezos is not installed.
    """

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Tezos transactions require complex Micheline encoding and signing,
        so without pytezos we return a failed result.
        """
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
                error=f"{asset_id} native transfer requires pytezos (not installed)",
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
        """Return True if *address* looks like a valid Tezos address.

        Tezos addresses start with tz1, tz2, tz3, or KT1 and are 36
        base58check characters.
        """
        return bool(re.match(r'^(tz[1-3]|KT1)[a-km-zA-HJ-NP-Z1-9]{33}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance in XTZ.

        Reads address from FAUCET_TEZOS_ADDRESS env var.
        If not set: {asset_id: "no wallet configured"}.
        """
        asset_id = self.config.get("blockchain", "Tezos")
        try:
            faucet_address = os.environ.get("FAUCET_TEZOS_ADDRESS")
            if not faucet_address:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config["rpc_url"].rstrip("/")
            decimals = self.config.get("decimals", 6)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url}/chains/main/blocks/head/context/contracts/{faucet_address}/balance"
                ) as resp:
                    balance_str = await resp.text()

            # balance_str is a JSON string like "12345678" (mutez)
            balance_str = balance_str.strip().strip('"')
            formatted = f"{int(balance_str) / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'tezos'."""
        return [k for k, v in load_registry().items() if v.get("family") == "tezos"]
