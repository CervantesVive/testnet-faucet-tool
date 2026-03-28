import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class AptosHandler(BaseHandler):
    """Handler for Aptos chains (native APT via public faucet; token transfers via coin_type)."""

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
        """Return True if *address* is a valid Aptos address (0x + 1-64 hex chars)."""
        return bool(re.match(r'^0x[0-9a-fA-F]{1,64}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "Aptos")
        try:
            address = self._get_wallet_address()
            if address is None:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config.get("rpc_url")
            if not rpc_url:
                return {asset_id: "no wallet configured"}

            url = f"{rpc_url.rstrip('/')}/accounts/{address}/resource/0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            coin_value = int(data.get("data", {}).get("coin", {}).get("value", 0))
            decimals = self.config.get("decimals", 8)
            formatted = f"{coin_value / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'aptos'."""
        return [k for k, v in load_registry().items() if v.get("family") == "aptos"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_wallet_address(self) -> str | None:
        """Return wallet address from env vars, or None if not configured.

        Resolution order:
        1. FAUCET_MNEMONIC      — BIP-39 mnemonic phrase (not used for Aptos faucet drip)
        2. FAUCET_PRIVATE_KEY   — hex-encoded private key (0x prefix optional)

        For Aptos, the public faucet does not require a wallet for fund_account.
        Full address derivation from a private key requires the aptos-sdk.
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            # Full key derivation not implemented without aptos-sdk installed
            return None

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return None

        return None

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Request APT from the public devnet faucet via HTTP POST."""
        faucet_url = self.config["faucet_url"]
        decimals = self.config.get("decimals", 8)
        octas = int(float(amount) * (10 ** decimals))

        payload = {"address": address, "amount": octas}

        async with aiohttp.ClientSession() as session:
            async with session.post(faucet_url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()

        # Aptos faucet returns a list of tx hashes
        tx_hash = None
        if isinstance(data, list) and len(data) > 0:
            tx_hash = data[0]
        elif isinstance(data, dict):
            tx_hash = data.get("txn_hash") or data.get("hash")

        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if (explorer and tx_hash) else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send an Aptos token (coin_type-based) transfer.

        Returns a failed DripResult immediately if coin_type is TBD.
        """
        if self.config.get("coin_type", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        # Full token transfer implementation would go here once coin_type is known.
        raise NotImplementedError(f"Token transfer for {asset_id} not yet implemented")
