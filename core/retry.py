import asyncio

from handlers.base import DripResult

# Errors that should NOT be retried
NON_RETRYABLE_PATTERNS = [
    "TBD",
    "not installed",
    "no wallet configured",
    "invalid address",
    "not yet implemented",
    "not supported",
    "requires",
]


async def retry_drip(
    handler,
    address: str,
    asset_id: str,
    amount: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> DripResult:
    """Retry drip with exponential backoff for transient errors only."""
    last_result = None
    for attempt in range(max_attempts):
        result = await handler.drip(address, asset_id, amount)
        if result.success:
            return result
        # Check if error is non-retryable
        if result.error and _is_non_retryable(result.error):
            return result
        last_result = result
        if attempt < max_attempts - 1:
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
    return last_result


def _is_non_retryable(error: str) -> bool:
    """Check if an error message indicates a non-retryable failure."""
    error_lower = error.lower()
    return any(pattern.lower() in error_lower for pattern in NON_RETRYABLE_PATTERNS)
