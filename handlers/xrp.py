import os

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import submit_and_wait
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.account import get_balance

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class XrpHandler(BaseHandler):
    """Handler for the XRP Ledger (native XRP and IOU token transfers)."""

    def _get_wallet(self) -> Wallet:
        """Load and return an XRP Wallet from env vars.

        Resolution order:
        1. FAUCET_MNEMONIC      — BIP-39 mnemonic phrase
        2. FAUCET_PRIVATE_KEY   — seed / secret key
        """
        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return Wallet.from_mnemonic(mnemonic)

        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            return Wallet.from_seed(private_key)

        raise RuntimeError(
            "XRP wallet not configured: set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY"
        )

    def _get_client(self) -> JsonRpcClient:
        """Build and return a JsonRpcClient from chain config."""
        return JsonRpcClient(self.config["rpc_url"])

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
        """Return True if *address* is a valid XRP classic address."""
        try:
            return is_valid_classic_address(address)
        except Exception:
            return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by asset_id.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "XRP Ledger")
        try:
            try:
                wallet = self._get_wallet()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            client = self._get_client()
            # get_balance returns drops (int)
            drops = get_balance(wallet.classic_address, client)
            decimals = self.config.get("decimals", 6)
            formatted = f"{drops / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'xrp'."""
        return [k for k, v in load_registry().items() if v.get("family") == "xrp"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native XRP transfer (amounts in drops)."""
        wallet = self._get_wallet()
        client = self._get_client()

        # XRP amounts must be in drops (1 XRP = 1,000,000 drops)
        drops = str(int(float(amount) * 1_000_000))

        payment = Payment(
            account=wallet.classic_address,
            amount=drops,
            destination=address,
        )
        result = submit_and_wait(payment, client, wallet)
        tx_hash = result.result.get("hash") or result.result.get("tx_json", {}).get("hash")

        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if explorer and tx_hash else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send an IOU token transfer via Payment with IssuedCurrencyAmount.

        Returns a failed DripResult immediately if the issuer is TBD.
        """
        if self.config.get("issuer", "TBD") == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        wallet = self._get_wallet()
        client = self._get_client()

        currency_code = self.config["currency_code"]
        issuer = self.config["issuer"]

        payment = Payment(
            account=wallet.classic_address,
            amount=IssuedCurrencyAmount(
                currency=currency_code,
                issuer=issuer,
                value=str(amount),
            ),
            destination=address,
        )
        result = submit_and_wait(payment, client, wallet)
        tx_hash = result.result.get("hash") or result.result.get("tx_json", {}).get("hash")

        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if explorer and tx_hash else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )
