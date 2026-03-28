import os

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from spl.token.instructions import (
    transfer_checked,
    TransferCheckedParams,
    get_associated_token_address,
    create_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry


class SolanaHandler(BaseHandler):
    """Handler for Solana chains (native SOL airdrop and SPL token transfers)."""

    def _get_keypair(self) -> Keypair:
        """Load and return a Solana Keypair from env vars.

        Resolution order:
        1. FAUCET_SOLANA_KEYPAIR — base58-encoded 64-byte keypair
        2. FAUCET_MNEMONIC       — BIP-39 mnemonic phrase
        """
        solana_keypair = os.environ.get("FAUCET_SOLANA_KEYPAIR")
        if solana_keypair:
            return Keypair.from_base58_string(solana_keypair)

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            return Keypair.from_seed_phrase_and_passphrase(mnemonic, "")

        raise RuntimeError(
            "Solana wallet not configured: set FAUCET_SOLANA_KEYPAIR or FAUCET_MNEMONIC"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Dispatches to _drip_native (requestAirdrop) or _drip_spl based on
        config['native_asset']. All exceptions are caught and returned as a
        failed DripResult.
        """
        try:
            if self.config.get("native_asset"):
                return await self._drip_native(address, asset_id, amount)
            else:
                return await self._drip_spl(address, asset_id, amount)
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
        """Return True if *address* is a valid Solana public key."""
        try:
            Pubkey.from_string(address)
            return True
        except (ValueError, Exception):
            return False

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance(s) keyed by symbol/asset_id.

        For native assets: {blockchain: "<balance> SOL"}
        For token assets:  {"SOL": "<native balance>", asset_id: "<token balance>"}
        On any error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "SOL")
        try:
            try:
                keypair = self._get_keypair()
            except RuntimeError:
                if self.config.get("native_asset"):
                    return {asset_id: "no wallet configured"}
                else:
                    return {"SOL": "no wallet configured", asset_id: "no wallet configured"}

            async with AsyncClient(self.config["rpc_url"]) as client:
                # Native SOL balance
                sol_resp = await client.get_balance(keypair.pubkey())
                sol_balance = sol_resp.value / 1_000_000_000

                if self.config.get("native_asset"):
                    return {asset_id: f"{sol_balance:.9f}"}

                # SPL token balance
                mint_address = self.config.get("mint_address", "TBD")
                if mint_address == "TBD":
                    return {"SOL": f"{sol_balance:.9f}", asset_id: "0 (ATA not funded)"}

                mint = Pubkey.from_string(mint_address)
                ata = get_associated_token_address(keypair.pubkey(), mint)

                try:
                    token_resp = await client.get_token_account_balance(ata)
                    token_balance = token_resp.value.ui_amount_string
                except Exception:
                    token_balance = "0 (ATA not funded)"

                return {"SOL": f"{sol_balance:.9f}", asset_id: token_balance}

        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'solana'."""
        registry = load_registry()
        return [k for k, v in registry.items() if v.get("family") == "solana"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Request a SOL airdrop via the RPC requestAirdrop method (no keypair needed)."""
        lamports = int(float(amount) * 1_000_000_000)
        pubkey = Pubkey.from_string(address)

        async with AsyncClient(self.config["rpc_url"]) as client:
            resp = await client.request_airdrop(pubkey, lamports)

        tx_hash = str(resp.value)
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

    async def _drip_spl(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send an SPL token transfer to *address*."""
        mint_address = self.config.get("mint_address", "TBD")
        if mint_address == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        keypair = self._get_keypair()
        mint = Pubkey.from_string(mint_address)
        decimals = self.config.get("decimals", 6)
        int_amount = int(float(amount) * (10 ** decimals))

        recipient_pubkey = Pubkey.from_string(address)
        src_ata = get_associated_token_address(keypair.pubkey(), mint)
        dest_ata = get_associated_token_address(recipient_pubkey, mint)

        async with AsyncClient(self.config["rpc_url"]) as client:
            blockhash_resp = await client.get_latest_blockhash()
            blockhash = blockhash_resp.value.blockhash

            instr = transfer_checked(
                TransferCheckedParams(
                    source=src_ata,
                    mint=mint,
                    dest=dest_ata,
                    owner=keypair.pubkey(),
                    amount=int_amount,
                    decimals=decimals,
                    program_id=TOKEN_PROGRAM_ID,
                )
            )

            txn = Transaction.new_signed_with_payer(
                [instr],
                keypair.pubkey(),
                [keypair],
                blockhash,
            )

            resp = await client.send_transaction(txn)

        tx_hash = str(resp.value)
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
