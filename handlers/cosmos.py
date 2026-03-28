import os

from bech32 import bech32_decode
from cosmpy.aerial.client import LedgerClient
from cosmpy.aerial.config import NetworkConfig
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.crypto.keypairs import PrivateKey

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class CosmosHandler(BaseHandler):
    """Handler for Cosmos SDK chains (native coin and IBC token transfers)."""

    def _get_wallet(self) -> LocalWallet:
        """Load and return a LocalWallet from env vars.

        Resolution order:
        1. FAUCET_MNEMONIC      — BIP-39 mnemonic phrase
        2. FAUCET_PRIVATE_KEY   — hex-encoded private key (0x prefix optional)
        """
        prefix = self.config["bech32_prefix"]

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return LocalWallet.from_mnemonic(mnemonic, prefix=prefix)

        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            key_hex = private_key.removeprefix("0x")
            return LocalWallet(PrivateKey(bytes.fromhex(key_hex)), prefix=prefix)

        raise RuntimeError(
            "Cosmos wallet not configured: set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY"
        )

    def _get_client(self) -> LedgerClient:
        """Build and return a LedgerClient from chain config."""
        rpc_url = self.config["rpc_url"]
        if not (rpc_url.startswith("rest+") or rpc_url.startswith("grpc+")):
            rpc_url = "rest+" + rpc_url

        cfg = NetworkConfig(
            chain_id=self.config["network"],
            url=rpc_url,
            fee_minimum_gas_price=0.025,
            fee_denomination=self.config["denom"],
            staking_denomination=self.config["denom"],
        )
        return LedgerClient(cfg)

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
        """Return True if *address* is a valid bech32 address with the expected prefix."""
        try:
            hrp, data = bech32_decode(address)
            return hrp == self.config["bech32_prefix"] and data is not None
        except Exception:
            return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance keyed by blockchain name.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "cosmos")
        try:
            try:
                wallet = self._get_wallet()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            client = self._get_client()
            balance_int = client.query_bank_balance(str(wallet.address()), self.config["denom"])
            decimals = self.config.get("decimals", 6)
            formatted = f"{balance_int / 10 ** decimals:.{decimals}f}"
            return {asset_id: formatted}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'cosmos'."""
        return [k for k, v in load_registry().items() if v.get("family") == "cosmos"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native coin transfer via LedgerClient.send_tokens."""
        wallet = self._get_wallet()
        client = self._get_client()

        decimals = self.config.get("decimals", 6)
        int_amount = int(float(amount) * (10 ** decimals))

        submitted = client.send_tokens(address, int_amount, self.config["denom"], wallet)
        submitted.wait_to_complete()

        tx_hash = submitted.tx_hash
        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if explorer else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )

    async def _drip_token(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send an IBC/non-native token transfer via LedgerClient.send_tokens.

        Returns a failed DripResult immediately if the token denom is TBD.
        """
        if self.config.get("denom", "TBD") == "TBD":
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

        decimals = self.config.get("decimals", 6)
        int_amount = int(float(amount) * (10 ** decimals))

        submitted = client.send_tokens(address, int_amount, self.config["denom"], wallet)
        submitted.wait_to_complete()

        tx_hash = submitted.tx_hash
        explorer = self.config.get("explorer", "")
        explorer_url = explorer.format(tx_hash=tx_hash) if explorer else None

        return DripResult(
            success=True,
            tx_hash=tx_hash,
            explorer_url=explorer_url,
            error=None,
            amount=amount,
            asset=asset_id,
        )
