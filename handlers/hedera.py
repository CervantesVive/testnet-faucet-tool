import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class HederaHandler(BaseHandler):
    """Handler for Hedera chains (HBAR native + HTS tokens).

    Uses the Hedera Mirror Node REST API via aiohttp.
    Native transfers require the Hedera SDK (not installed) — returns
    a helpful error. Token transfers guard on token_id == "TBD".
    """

    def _get_account_id(self) -> str:
        account_id = os.environ.get("FAUCET_HEDERA_ACCOUNT_ID")
        if not account_id:
            raise RuntimeError(
                "Hedera wallet not configured: set FAUCET_HEDERA_ACCOUNT_ID"
            )
        return account_id

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

    async def _drip_native(
        self, address: str, asset_id: str, amount: str
    ) -> DripResult:
        """Send native HBAR transfer.

        Hedera REST API requires signed protobuf transactions which are
        complex without the SDK. Returns a helpful error.
        """
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
            error=f"{asset_id} native transfer requires hedera-sdk-py (not installed)",
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(
        self, address: str, asset_id: str, amount: str
    ) -> DripResult:
        """Send an HTS token transfer.

        Returns a failed DripResult immediately if token_id is TBD.
        """
        if self.config.get("token_id", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} token_id not yet configured (TBD)",
                amount=amount,
                asset=asset_id,
            )
        return DripResult(
            success=False,
            tx_hash=None,
            explorer_url=None,
            error=f"{asset_id} token transfer requires hedera-sdk-py (not installed)",
            amount=amount,
            asset=asset_id,
        )

    def validate_address(self, address: str) -> bool:
        """Return True if *address* looks like a valid Hedera account ID.

        Format: 0.0.NNNNN (shard.realm.account)
        """
        return bool(re.match(r"^0\.0\.\d+$", address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet HBAR balance via Mirror Node API.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "Hedera")
        try:
            try:
                account_id = self._get_account_id()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config.get("rpc_url", "TBD")
            if rpc_url == "TBD":
                return {asset_id: "rpc_url not yet configured (TBD)"}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{rpc_url.rstrip('/')}/api/v1/accounts/{account_id}"
                ) as resp:
                    data = await resp.json()

            balance = data.get("balance", {}).get("balance", 0)
            decimals = self.config.get("decimals", 8)
            formatted = f"{balance / 10**decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'hedera'."""
        return [k for k, v in load_registry().items() if v.get("family") == "hedera"]
