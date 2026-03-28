import os
import re

import aiohttp

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class SuiHandler(BaseHandler):
    """Handler for Sui chains (native SUI via public faucet; token transfers via object_type)."""

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
        """Return True if *address* is a valid Sui address (0x + 64 hex chars)."""
        return bool(re.match(r'^0x[0-9a-fA-F]{64}$', address))

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "Sui")
        try:
            address = self._get_wallet_address()
            if address is None:
                return {asset_id: "no wallet configured"}

            rpc_url = self.config.get("rpc_url")
            if not rpc_url:
                return {asset_id: "no wallet configured"}

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_getBalance",
                "params": [address, "0x2::sui::SUI"],
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc_url, json=payload) as resp:
                    data = await resp.json()

            result = data.get("result", {})
            total_balance = int(result.get("totalBalance", 0))
            decimals = self.config.get("decimals", 9)
            formatted = f"{total_balance / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'sui'."""
        return [k for k, v in load_registry().items() if v.get("family") == "sui"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_wallet_address(self) -> str | None:
        """Return wallet address from env vars, or None if not configured.

        Resolution order:
        1. FAUCET_MNEMONIC      — BIP-39 mnemonic phrase (not used for Sui faucet)
        2. FAUCET_PRIVATE_KEY   — hex-encoded private key (0x prefix optional)
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            # For Sui, the private key is the wallet address derivation source.
            # We return None here as full key derivation requires the pysui SDK.
            # The faucet drip does not require a wallet address.
            return None

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return None

        return None

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Request SUI from the public devnet faucet via HTTP POST."""
        faucet_url = self.config["faucet_url"]
        payload = {"FixedAmountRequest": {"recipient": address}}

        async with aiohttp.ClientSession() as session:
            async with session.post(faucet_url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()

        # Extract tx digest from response
        # Typical response: {"transferredGasObjects": [...], "error": null}
        # or {"task": "...", "error": null} for async faucets
        tx_hash = None
        if isinstance(data, dict):
            transferred = data.get("transferredGasObjects")
            if transferred and isinstance(transferred, list) and len(transferred) > 0:
                first = transferred[0]
                tx_hash = first.get("transferTxDigest") or first.get("txDigest")
            if tx_hash is None:
                tx_hash = data.get("task") or data.get("digest")

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
        """Send a Sui token (object_type-based) transfer.

        Returns a failed DripResult immediately if object_type is TBD.
        """
        if self.config.get("object_type", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        # Full token transfer implementation would go here once object_type is known.
        raise NotImplementedError(f"Token transfer for {asset_id} not yet implemented")
