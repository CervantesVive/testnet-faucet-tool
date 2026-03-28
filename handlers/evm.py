import os
import warnings
from decimal import Decimal

from web3 import Web3
from eth_account import Account
from eth_utils import is_address, to_checksum_address

from handlers.base import BaseHandler, DripResult
from core.registry import load_registry

ERC20_ABI = [
    {
        "name": "transfer",
        "type": "function",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]


class EvmHandler(BaseHandler):
    """Handler for EVM-compatible chains (native ETH transfers and ERC-20 tokens)."""

    def _get_account(self) -> Account:
        """Load and return an eth_account Account from env vars.

        Resolution order:
        1. FAUCET_PRIVATE_KEY — raw hex or 0x-prefixed hex private key
        2. FAUCET_MNEMONIC    — BIP-39 mnemonic, derived at m/44'/60'/0'/0/0
        """
        private_key = os.environ.get("FAUCET_PRIVATE_KEY")
        if private_key:
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key
            return Account.from_key(private_key)

        mnemonic = os.environ.get("FAUCET_MNEMONIC")
        if mnemonic:
            Account.enable_unaudited_hdwallet_features()
            return Account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")

        raise RuntimeError(
            "EVM wallet not configured: set FAUCET_PRIVATE_KEY or FAUCET_MNEMONIC"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to *address*.

        Dispatches to _drip_native or _drip_erc20 based on config['native_asset'].
        All exceptions are caught and returned as a failed DripResult.
        """
        try:
            if self.config.get("native_asset"):
                return await self._drip_native(address, asset_id, amount)
            else:
                return await self._drip_erc20(address, asset_id, amount)
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
        """Return True if *address* is a valid EVM address."""
        return is_address(address)

    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current faucet wallet balance(s) keyed by symbol/asset_id.

        For native assets: {asset_id: "<human-readable> ETH"}
        For token assets:  {"ETH": "<native balance>", asset_id: "<token balance>"}
        On any error: {asset_id: "error: <message>"}
        """
        asset_id = self.config.get("blockchain", "UNKNOWN")
        # Use the asset id from context — callers pass asset_id through config
        # The registry key is not stored in config, so we derive a label from it.
        # We use 'blockchain' as a fallback label for the native coin.
        try:
            account = self._get_account()
            w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))

            native_balance_wei = w3.eth.get_balance(account.address)
            native_balance = str(Web3.from_wei(native_balance_wei, "ether"))

            if self.config.get("native_asset"):
                return {asset_id: native_balance}
            else:
                # Token balance
                contract_address = self.config.get("contract_address", "TBD")
                if contract_address == "TBD":
                    return {"ETH": native_balance, asset_id: "error: contract not yet deployed (TBD)"}

                contract = w3.eth.contract(
                    address=to_checksum_address(contract_address), abi=ERC20_ABI
                )
                raw_token_balance = contract.functions.balanceOf(account.address).call()
                decimals = self.config.get("decimals", 18)
                if decimals == 18:
                    token_balance = str(Web3.from_wei(raw_token_balance, "ether"))
                else:
                    token_balance = str(Decimal(raw_token_balance) / Decimal(10 ** decimals))

                return {"ETH": native_balance, asset_id: token_balance}
        except Exception as exc:
            return {asset_id: f"error: {exc}"}

    def supported_assets(self) -> list[str]:
        """Return all registry asset IDs whose family is 'evm'."""
        registry = load_registry()
        return [k for k, v in registry.items() if v.get("family") == "evm"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _drip_native(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send a native ETH (or ETH-equivalent) transfer."""
        w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))
        account = self._get_account()
        nonce = w3.eth.get_transaction_count(account.address)
        chain_id = w3.eth.chain_id

        tx = {
            "to": to_checksum_address(address),
            "value": w3.to_wei(amount, "ether"),
            "gas": 21000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
            "nonce": nonce,
            "chainId": chain_id,
            "type": 2,
        }

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        success = receipt.status == 1
        tx_hash_hex = "0x" + (tx_hash.hex() if isinstance(tx_hash, (bytes, bytearray)) else str(tx_hash))
        explorer = self.config.get("explorer")
        explorer_url = explorer.format(tx_hash=tx_hash_hex) if explorer else None

        return DripResult(
            success=success,
            tx_hash=tx_hash_hex,
            explorer_url=explorer_url,
            error=None if success else "Transaction reverted",
            amount=amount,
            asset=asset_id,
        )

    async def _drip_erc20(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send an ERC-20 token transfer."""
        contract_address = self.config.get("contract_address", "TBD")
        if contract_address == "TBD":
            return DripResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=f"{asset_id} contract address not yet deployed (TBD)",
                amount=amount,
                asset=asset_id,
            )

        w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))
        account = self._get_account()

        # Warn if recipient has no ETH (will be unable to pay gas for future txs)
        recipient_eth = w3.eth.get_balance(to_checksum_address(address))
        if recipient_eth == 0:
            warnings.warn(
                f"Recipient {address} has no ETH for gas fees on {self.config.get('blockchain')}"
            )

        decimals = self.config.get("decimals", 18)
        amount_wei = int(Decimal(amount) * 10 ** decimals)

        contract = w3.eth.contract(
            address=to_checksum_address(contract_address), abi=ERC20_ABI
        )

        nonce = w3.eth.get_transaction_count(account.address)
        chain_id = w3.eth.chain_id
        recipient_checksum = to_checksum_address(address)

        estimated_gas = contract.functions.transfer(
            recipient_checksum, amount_wei
        ).estimate_gas({"from": account.address})

        tx = contract.functions.transfer(recipient_checksum, amount_wei).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "chainId": chain_id,
                "gas": estimated_gas,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
                "type": 2,
            }
        )

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        success = receipt.status == 1
        tx_hash_hex = "0x" + (tx_hash.hex() if isinstance(tx_hash, (bytes, bytearray)) else str(tx_hash))
        explorer = self.config.get("explorer")
        explorer_url = explorer.format(tx_hash=tx_hash_hex) if explorer else None

        return DripResult(
            success=success,
            tx_hash=tx_hash_hex,
            explorer_url=explorer_url,
            error=None if success else "Transaction reverted",
            amount=amount,
            asset=asset_id,
        )
