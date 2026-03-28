import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class EosHandler(BaseHandler):
    """Handler for EOS chains (native EOS and token transfers).

    Uses the EOS HTTP API directly via aiohttp since eospy is not installed.
    """

    def _get_account_name(self) -> str:
        """Return the faucet EOS account name from env vars.

        Raises RuntimeError if FAUCET_EOS_ACCOUNT is not set.
        """
        account = os.environ.get("FAUCET_EOS_ACCOUNT")
        if not account:
            raise RuntimeError(
                "EOS wallet not configured: set FAUCET_EOS_ACCOUNT"
            )
        return account

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Dispatches to _drip_native or _drip_token based on config['native_asset'].
        All exceptions are caught and returned as a failed DripResult.
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
        """Return True if *address* looks like a valid EOS account name.

        EOS account names are 1-12 characters, lowercase a-z, digits 1-5, and dots.
        """
        return bool(re.match(r"^[a-z1-5.]{1,12}$", address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet EOS balance.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "EOS")
        try:
            try:
                account_name = self._get_account_name()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config["rpc_url"].rstrip("/")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{rpc_url}/v1/chain/get_account",
                    json={"account_name": account_name},
                ) as resp:
                    data = await resp.json()

            # core_liquid_balance is e.g. "10.0000 EOS"
            balance_str = data.get("core_liquid_balance", "0.0000 EOS")
            # Extract just the numeric part
            balance_value = balance_str.split()[0] if balance_str else "0.0000"
            return {asset_id: balance_value}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'eos'."""
        return [k for k, v in load_registry().items() if v.get("family") == "eos"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(
        self, address: str, asset_id: str, amount: str
    ) -> DripResult:
        """Send a native EOS transfer.

        Returns a failed DripResult because eospy is not installed.
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
            error=f"{asset_id} native transfer requires eospy (not installed)",
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(
        self, address: str, asset_id: str, amount: str
    ) -> DripResult:
        """Send an EOS token transfer.

        Returns a failed DripResult because contract_account is not configured.
        """
        if self.config.get("contract_account", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} token transfer not yet configured",
                amount=amount,
                asset=asset_id,
            )

        # Full token transfer implementation would go here.
        raise NotImplementedError("EOS token transfer not yet implemented")
