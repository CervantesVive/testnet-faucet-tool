import os

from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class StellarHandler(BaseHandler):
    """Handler for the Stellar network (native XLM and custom asset transfers)."""

    def _get_keypair(self) -> Keypair:
        """Load and return a Stellar Keypair from env vars.

        Resolution order:
        1. FAUCET_MNEMONIC      — BIP-39 mnemonic phrase
        2. FAUCET_PRIVATE_KEY   — Stellar secret key (S...)
        """
        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return Keypair.from_mnemonic_phrase(mnemonic)

        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            return Keypair.from_secret(private_key)

        raise RuntimeError(
            "Stellar wallet not configured: set FAUCET_MNEMONIC or FAUCET_PRIVATE_KEY"
        )

    def _get_network_passphrase(self) -> str:
        """Return the Stellar network passphrase from config or derived from network name."""
        if "network_passphrase" in self.config:
            return self.config["network_passphrase"]
        network = self.config.get("network", "testnet").lower()
        if network in ("mainnet", "public"):
            return Network.PUBLIC_NETWORK_PASSPHRASE
        return Network.TESTNET_NETWORK_PASSPHRASE

    def _get_server(self) -> Server:
        """Build and return a Stellar Server from chain config."""
        return Server(horizon_url=self.config["rpc_url"])

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
        """Return True if *address* is a valid Stellar public key."""
        try:
            Keypair.from_public_key(address)
            return True
        except Exception:
            return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet XLM balance.

        On missing wallet: {asset_id: "no wallet configured"}
        On any other error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "Stellar")
        try:
            try:
                keypair = self._get_keypair()
            except RuntimeError:
                return {asset_id: "no wallet configured"}

            server = self._get_server()
            account_data = server.accounts().account_id(keypair.public_key).call()

            # Find the native XLM balance
            for balance in account_data.get("balances", []):
                if balance.get("asset_type") == "native":
                    return {asset_id: balance["balance"]}

            return {asset_id: "0"}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'stellar'."""
        return [k for k, v in load_registry().items() if v.get("family") == "stellar"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native XLM transfer via TransactionBuilder."""
        keypair = self._get_keypair()
        server = self._get_server()

        source_account = server.load_account(keypair.public_key)
        transaction = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=self._get_network_passphrase(),
                base_fee=100,
            )
            .append_payment_op(
                destination=address,
                asset=Asset.native(),
                amount=str(amount),
            )
            .build()
        )
        transaction.sign(keypair)
        response = server.submit_transaction(transaction)

        tx_hash = response.get("hash")
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
        """Send a custom Stellar asset transfer.

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

        keypair = self._get_keypair()
        server = self._get_server()

        asset_code = self.config["asset_code"]
        issuer = self.config["issuer"]

        source_account = server.load_account(keypair.public_key)
        transaction = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=self._get_network_passphrase(),
                base_fee=100,
            )
            .append_payment_op(
                destination=address,
                asset=Asset(asset_code, issuer),
                amount=str(amount),
            )
            .build()
        )
        transaction.sign(keypair)
        response = server.submit_transaction(transaction)

        tx_hash = response.get("hash")
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
