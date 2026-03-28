import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from handlers.base import DripResult
from core.retry import retry_drip, _is_non_retryable


# --- Unit tests for _is_non_retryable ---


def test_is_non_retryable_tbd():
    assert _is_non_retryable("rpc_url is TBD") is True


def test_is_non_retryable_sdk_not_installed():
    assert _is_non_retryable("SDK not installed") is True


def test_is_non_retryable_no_wallet():
    assert _is_non_retryable("no wallet configured") is True


def test_is_non_retryable_invalid_address():
    assert _is_non_retryable("invalid address format") is True


def test_is_non_retryable_not_yet_implemented():
    assert _is_non_retryable("feature not yet implemented") is True


def test_is_non_retryable_not_supported():
    assert _is_non_retryable("asset not supported") is True


def test_is_non_retryable_requires():
    assert _is_non_retryable("requires polkadot SDK") is True


def test_is_non_retryable_transient_error():
    assert _is_non_retryable("Connection timeout") is False


def test_is_non_retryable_server_error():
    assert _is_non_retryable("HTTP 503 Service Unavailable") is False


def test_is_non_retryable_case_insensitive():
    assert _is_non_retryable("SDK NOT INSTALLED") is True
    assert _is_non_retryable("No Wallet Configured") is True


# --- Async tests for retry_drip ---


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=True, tx_hash="0xabc", explorer_url=None,
        error=None, amount="0.05", asset="HTETH",
    ))
    result = await retry_drip(handler, "0x123", "HTETH", "0.05")
    assert result.success
    assert result.tx_hash == "0xabc"
    assert handler.drip.call_count == 1


@pytest.mark.asyncio
async def test_retry_transient_then_success():
    handler = MagicMock()
    handler.drip = AsyncMock(side_effect=[
        DripResult(success=False, tx_hash=None, explorer_url=None,
                   error="Connection timeout", amount="0.05", asset="HTETH"),
        DripResult(success=True, tx_hash="0xabc", explorer_url=None,
                   error=None, amount="0.05", asset="HTETH"),
    ])
    with patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await retry_drip(handler, "0x123", "HTETH", "0.05")
    assert result.success
    assert handler.drip.call_count == 2


@pytest.mark.asyncio
async def test_retry_non_retryable_tbd():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="rpc_url is TBD — not yet configured", amount="0.05", asset="TBTC",
    ))
    result = await retry_drip(handler, "addr1", "TBTC", "0.05")
    assert not result.success
    assert handler.drip.call_count == 1


@pytest.mark.asyncio
async def test_retry_non_retryable_sdk_not_installed():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="substrate SDK not installed", amount="1.0", asset="TWND",
    ))
    result = await retry_drip(handler, "addr1", "TWND", "1.0")
    assert not result.success
    assert handler.drip.call_count == 1


@pytest.mark.asyncio
async def test_retry_non_retryable_no_wallet():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="no wallet configured — cryptography not installed",
        amount="1.0", asset="TNEAR",
    ))
    result = await retry_drip(handler, "addr1", "TNEAR", "1.0")
    assert not result.success
    assert handler.drip.call_count == 1


@pytest.mark.asyncio
async def test_retry_max_attempts_exhausted():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="HTTP 503 Service Unavailable", amount="0.05", asset="HTETH",
    ))
    with patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await retry_drip(handler, "0x123", "HTETH", "0.05")
    assert not result.success
    assert result.error == "HTTP 503 Service Unavailable"
    assert handler.drip.call_count == 3


@pytest.mark.asyncio
async def test_retry_exponential_backoff_timing():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="Connection refused", amount="0.05", asset="HTETH",
    ))
    with patch("core.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await retry_drip(handler, "0x123", "HTETH", "0.05")
    assert not result.success
    assert handler.drip.call_count == 3
    # Verify exponential backoff: 1s, 2s (base_delay * 2^attempt)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)


@pytest.mark.asyncio
async def test_retry_custom_max_attempts_and_base_delay():
    handler = MagicMock()
    handler.drip = AsyncMock(return_value=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="timeout", amount="0.05", asset="HTETH",
    ))
    with patch("core.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await retry_drip(
            handler, "0x123", "HTETH", "0.05",
            max_attempts=4, base_delay=0.5,
        )
    assert not result.success
    assert handler.drip.call_count == 4
    # Delays: 0.5, 1.0, 2.0
    assert mock_sleep.call_count == 3
    mock_sleep.assert_any_call(0.5)
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)


@pytest.mark.asyncio
async def test_retry_two_failures_then_success():
    handler = MagicMock()
    handler.drip = AsyncMock(side_effect=[
        DripResult(success=False, tx_hash=None, explorer_url=None,
                   error="HTTP 502 Bad Gateway", amount="0.05", asset="HTETH"),
        DripResult(success=False, tx_hash=None, explorer_url=None,
                   error="Connection reset", amount="0.05", asset="HTETH"),
        DripResult(success=True, tx_hash="0xdef", explorer_url=None,
                   error=None, amount="0.05", asset="HTETH"),
    ])
    with patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await retry_drip(handler, "0x123", "HTETH", "0.05")
    assert result.success
    assert result.tx_hash == "0xdef"
    assert handler.drip.call_count == 3


# --- CLI integration test ---


def test_drip_cli_uses_retry(tmp_path, monkeypatch):
    """Verify the drip CLI command uses retry_drip instead of direct handler.drip."""
    import core.rate_limiter as rl
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")

    mock_result = DripResult(
        success=True, tx_hash="0xabc123", explorer_url=None,
        error=None, amount="0.05", asset="HTETH",
    )

    with patch("cli.retry_drip", return_value=mock_result) as mock_retry, \
         patch("cli.get_handler") as mock_get_handler, \
         patch("cli.get_asset_config", return_value={"drip_amount": "0.05", "family": "evm"}):
        mock_handler = MagicMock()
        mock_handler.validate_address.return_value = True
        mock_get_handler.return_value = mock_handler

        from click.testing import CliRunner
        from cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "HTETH", "0x1234567890abcdef1234567890abcdef12345678"])

        assert result.exit_code == 0
        mock_retry.assert_called_once()
        # Verify retry_drip was called with the handler and correct args
        call_args = mock_retry.call_args
        assert call_args[0][0] is mock_handler
        assert call_args[0][2] == "HTETH"
