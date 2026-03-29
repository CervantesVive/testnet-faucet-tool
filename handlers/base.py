from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DripResult:
    success: bool
    tx_hash: str | None
    explorer_url: str | None
    error: str | None
    amount: str
    asset: str


class BaseHandler(ABC):
    """One handler per chain family. Instantiated with chain-specific config."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def drip(self, address: str, asset_id: str, amount: str) -> DripResult:
        """Send testnet tokens to the given address."""
        ...

    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """Check if the address is valid for this chain."""
        ...

    @abstractmethod
    async def get_faucet_balance(self) -> dict[str, str]:
        """Return current balance of the faucet wallet for monitoring."""
        ...

    @abstractmethod
    def supported_assets(self) -> list[str]:
        """Return list of testnet asset IDs this handler can process."""
        ...

    def get_faucet_address(self) -> str | None:
        """Return the faucet's own address for auto-refill, or None if not configured.

        Override in handlers that support auto-top. The monitor calls this to determine
        the recipient address for self-drip refills.
        """
        return None
