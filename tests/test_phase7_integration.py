"""Phase 7 integration tests — batch, refill, dashboard, history, retry via CliRunner."""

from click.testing import CliRunner
from cli import main
from unittest.mock import patch, AsyncMock, MagicMock
from handlers.base import DripResult
import core.rate_limiter as rl
import core.logger as logger_mod


def _isolate(monkeypatch, tmp_path):
    """Isolate rate limiter DB and logger path per test."""
    monkeypatch.setattr(rl, "DB_PATH", tmp_path / "test.db")
    # conftest already patches LOG_PATH, but we need the same tmp_path
    # reference for assertions — grab it from the monkeypatched value
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")


def _make_handler(validate=True, drip_result=None, balance=None, side_effect=None):
    """Create a mock handler with sane defaults."""
    h = MagicMock()
    h.validate_address.return_value = validate
    if side_effect:
        h.drip = AsyncMock(side_effect=side_effect)
    elif drip_result:
        h.drip = AsyncMock(return_value=drip_result)
    else:
        h.drip = AsyncMock(return_value=DripResult(
            success=True, tx_hash="0xdef456", explorer_url=None,
            error=None, amount="0.05", asset="HTETH",
        ))
    if balance is not None:
        h.get_faucet_balance = AsyncMock(return_value=balance)
    else:
        h.get_faucet_balance = AsyncMock(return_value={"native": "10.0"})
    return h


# ---------------------------------------------------------------------------
# 1. Batch command integration
# ---------------------------------------------------------------------------


def test_batch_two_column_csv(tmp_path, monkeypatch):
    """Batch with asset,address CSV -- full round trip."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "wallets.csv"
    csv_file.write_text(
        "HTETH,0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18\n"
        "TSOL,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU\n"
    )

    mock_handler = _make_handler()

    def fake_get_handler(asset_id):
        return mock_handler

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", side_effect=fake_get_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "2" in result.output  # 2 rows processed
    assert mock_handler.drip.call_count == 2


def test_batch_with_malformed_csv(tmp_path, monkeypatch):
    """Batch handles bad asset IDs and invalid addresses gracefully."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "FAKE_ASSET,0x123\n"
        "# comment\n"
        "\n"
        "HTETH,invalid_addr\n"
    )

    mock_handler = _make_handler(validate=False)

    def fake_get_asset_config(asset_id):
        if asset_id == "FAKE_ASSET":
            raise KeyError("Unknown asset: FAKE_ASSET")
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0, result.output
    assert "ERROR" in result.output
    # Comment and empty lines skipped, two error rows
    assert "2" in result.output


def test_batch_single_column_with_asset_flag(tmp_path, monkeypatch):
    """Batch with single-column CSV and --asset flag."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "addrs.csv"
    csv_file.write_text("0xAddress1\n0xAddress2\n")

    mock_handler = _make_handler()

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.1", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(csv_file), "--asset", "HTETH"])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert mock_handler.drip.call_count == 2


def test_batch_single_column_no_asset_flag(tmp_path, monkeypatch):
    """Batch with single-column CSV but missing --asset flag produces error."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "addrs.csv"
    csv_file.write_text("0xAddress1\n")

    runner = CliRunner()
    result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0, result.output
    assert "ERROR" in result.output
    assert "--asset" in result.output


# ---------------------------------------------------------------------------
# 2. Refill command integration
# ---------------------------------------------------------------------------


def test_refill_mixed_statuses(tmp_path, monkeypatch):
    """Refill shows OK, LOW, and ERROR statuses."""
    _isolate(monkeypatch, tmp_path)

    fake_assets = {
        "HTETH": {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True},
        "TSOL": {"family": "solana", "blockchain": "solana", "drip_amount": "1.0", "native_asset": True},
        "TATOM": {"family": "cosmos", "blockchain": "cosmos", "drip_amount": "0.5", "native_asset": True},
    }

    handler_ok = _make_handler(balance={"native": "10.0"})         # well above threshold
    handler_low = _make_handler(balance={"native": "0.5"})         # below 2x drip (2.0)
    handler_err = MagicMock()
    handler_err.get_faucet_balance = AsyncMock(side_effect=RuntimeError("no wallet configured"))

    handler_map = {"HTETH": handler_ok, "TSOL": handler_low, "TATOM": handler_err}

    def fake_get_handler(asset_id):
        return handler_map[asset_id]

    with patch("cli.get_all_assets", return_value=fake_assets), \
         patch("cli.get_handler", side_effect=fake_get_handler):
        runner = CliRunner()
        result = runner.invoke(main, ["refill"])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "LOW" in result.output
    assert "ERROR" in result.output
    assert "Summary" in result.output


def test_refill_with_threshold_flag(tmp_path, monkeypatch):
    """Refill respects custom --threshold."""
    _isolate(monkeypatch, tmp_path)

    fake_assets = {
        "HTETH": {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True},
    }
    handler = _make_handler(balance={"native": "5.0"})

    with patch("cli.get_all_assets", return_value=fake_assets), \
         patch("cli.get_handler", return_value=handler):
        runner = CliRunner()
        # threshold=100 means 5.0 balance should be LOW
        result = runner.invoke(main, ["refill", "--threshold", "100"])

    assert result.exit_code == 0, result.output
    assert "LOW" in result.output


# ---------------------------------------------------------------------------
# 3. Dashboard integration
# ---------------------------------------------------------------------------


def test_dashboard_all_statuses(tmp_path, monkeypatch):
    """Dashboard shows funded, low, and error statuses."""
    _isolate(monkeypatch, tmp_path)

    fake_assets = {
        "HTETH": {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True},
        "TSOL": {"family": "solana", "blockchain": "solana", "drip_amount": "1.0", "native_asset": True},
        "TATOM": {"family": "cosmos", "blockchain": "cosmos", "drip_amount": "0.5", "native_asset": True},
    }

    handler_funded = _make_handler(balance={"native": "10.0"})     # above 2*0.05=0.1
    handler_low = _make_handler(balance={"native": "0.5"})         # below 2*1.0=2.0
    handler_err = MagicMock()
    handler_err.get_faucet_balance = AsyncMock(side_effect=RuntimeError("no wallet"))

    handler_map = {"HTETH": handler_funded, "TSOL": handler_low, "TATOM": handler_err}

    def fake_get_handler(asset_id):
        return handler_map[asset_id]

    with patch("cli.get_all_assets", return_value=fake_assets), \
         patch("cli.get_handler", side_effect=fake_get_handler):
        runner = CliRunner()
        result = runner.invoke(main, ["dashboard"])

    assert result.exit_code == 0, result.output
    # Dashboard prints "DASHBOARD <asset> <balance>" for each asset
    assert "DASHBOARD HTETH" in result.output
    assert "DASHBOARD TSOL" in result.output
    assert "DASHBOARD TATOM" in result.output
    # Summary line
    assert "funded" in result.output
    assert "low" in result.output
    assert "error" in result.output


def test_dashboard_family_filter(tmp_path, monkeypatch):
    """Dashboard --family filters to a single family."""
    _isolate(monkeypatch, tmp_path)

    fake_assets = {
        "HTETH": {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True},
        "TSOL": {"family": "solana", "blockchain": "solana", "drip_amount": "1.0", "native_asset": True},
    }

    handler = _make_handler(balance={"native": "10.0"})

    with patch("cli.get_all_assets", return_value=fake_assets), \
         patch("cli.get_handler", return_value=handler):
        runner = CliRunner()
        result = runner.invoke(main, ["dashboard", "--family", "evm"])

    assert result.exit_code == 0, result.output
    assert "DASHBOARD HTETH" in result.output
    assert "TSOL" not in result.output


# ---------------------------------------------------------------------------
# 4. History integration
# ---------------------------------------------------------------------------


def test_history_empty(tmp_path, monkeypatch):
    """History shows message when no drips recorded."""
    _isolate(monkeypatch, tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["history"])

    assert result.exit_code == 0, result.output
    assert "No drip history" in result.output


def test_history_after_drip(tmp_path, monkeypatch):
    """History shows entries after drip operations."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(drip_result=DripResult(
        success=True, tx_hash="0xhistory123", explorer_url=None,
        error=None, amount="0.05", asset="HTETH",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        # First do a drip
        drip_result = runner.invoke(main, ["drip", "HTETH", "0xTestAddr"])
        assert drip_result.exit_code == 0, drip_result.output

        # Then check history
        hist_result = runner.invoke(main, ["history"])

    assert hist_result.exit_code == 0, hist_result.output
    assert "HTETH" in hist_result.output
    assert "0xhistory123" in hist_result.output


# ---------------------------------------------------------------------------
# 5. Retry integration
# ---------------------------------------------------------------------------


def test_drip_retry_transient_failure(tmp_path, monkeypatch):
    """Drip command retries on transient failure and succeeds."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(side_effect=[
        DripResult(success=False, tx_hash=None, explorer_url=None,
                   error="Connection timeout", amount="0.05", asset="HTETH"),
        DripResult(success=True, tx_hash="0xretried", explorer_url=None,
                   error=None, amount="0.05", asset="HTETH"),
    ])

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "HTETH", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    assert mock_handler.drip.call_count == 2
    assert "0xretried" in result.output


def test_drip_no_retry_on_tbd(tmp_path, monkeypatch):
    """Drip does NOT retry when handler returns TBD error."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(drip_result=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="rpc_url is TBD", amount="0.05", asset="TBTC4",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "utxo", "blockchain": "bitcoin", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "TBTC4", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    # Non-retryable: drip called only once
    assert mock_handler.drip.call_count == 1


def test_drip_no_retry_on_not_installed(tmp_path, monkeypatch):
    """Drip does NOT retry when handler says SDK not installed."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(drip_result=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="requires substrate SDK not installed", amount="1.0", asset="TDOT",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "substrate", "blockchain": "polkadot", "drip_amount": "1.0", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "TDOT", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    assert mock_handler.drip.call_count == 1


def test_drip_exhausts_retries(tmp_path, monkeypatch):
    """Drip exhausts all retries on persistent transient error."""
    _isolate(monkeypatch, tmp_path)

    fail = DripResult(success=False, tx_hash=None, explorer_url=None,
                      error="server error 500", amount="0.05", asset="HTETH")
    mock_handler = _make_handler(side_effect=[fail, fail, fail])

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "HTETH", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    assert mock_handler.drip.call_count == 3  # 3 attempts (default max)
    assert "server error 500" in result.output


# ---------------------------------------------------------------------------
# 6. Batch + history integration
# ---------------------------------------------------------------------------


def test_batch_logs_to_history(tmp_path, monkeypatch):
    """Batch command logs all drip results to history."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "wallets.csv"
    csv_file.write_text("HTETH,0xAddr1\nHTETH,0xAddr2\n")

    mock_handler = _make_handler(drip_result=DripResult(
        success=True, tx_hash="0xbatch_tx", explorer_url=None,
        error=None, amount="0.05", asset="HTETH",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        batch_result = runner.invoke(main, ["batch", str(csv_file)])
        assert batch_result.exit_code == 0, batch_result.output

        # Now check history
        hist_result = runner.invoke(main, ["history"])

    assert hist_result.exit_code == 0, hist_result.output
    assert "HTETH" in hist_result.output
    # Both drips should be logged
    entries = logger_mod.read_history(20)
    assert len(entries) == 2
    assert all(e["tx_hash"] == "0xbatch_tx" for e in entries)


# ---------------------------------------------------------------------------
# 7. Batch + retry integration
# ---------------------------------------------------------------------------


def test_batch_does_not_use_retry(tmp_path, monkeypatch):
    """Batch command calls handler.drip directly (no retry_drip)."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "wallets.csv"
    csv_file.write_text("HTETH,0xAddr1\n")

    fail_result = DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="Connection timeout", amount="0.05", asset="HTETH",
    )
    mock_handler = _make_handler(drip_result=fail_result)

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0, result.output
    # Batch calls drip once per row, no retry
    assert mock_handler.drip.call_count == 1
    assert "FAILED" in result.output


# ---------------------------------------------------------------------------
# 8. Drip + history end-to-end
# ---------------------------------------------------------------------------


def test_drip_logs_success_to_history(tmp_path, monkeypatch):
    """Successful drip is logged and visible in history."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(drip_result=DripResult(
        success=True, tx_hash="0xe2e_hash", explorer_url=None,
        error=None, amount="0.1", asset="TSOL",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "solana", "blockchain": "solana", "drip_amount": "0.1", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        runner.invoke(main, ["drip", "TSOL", "SomeAddress"])

    entries = logger_mod.read_history(20)
    assert len(entries) == 1
    assert entries[0]["asset_id"] == "TSOL"
    assert entries[0]["tx_hash"] == "0xe2e_hash"
    assert entries[0]["success"] is True


def test_drip_logs_failure_to_history(tmp_path, monkeypatch):
    """Failed drip is logged with error info."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(drip_result=DripResult(
        success=False, tx_hash=None, explorer_url=None,
        error="insufficient funds", amount="0.1", asset="TSOL",
    ))

    def fake_get_asset_config(asset_id):
        return {"family": "solana", "blockchain": "solana", "drip_amount": "0.1", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        runner.invoke(main, ["drip", "TSOL", "SomeAddress"])

    entries = logger_mod.read_history(20)
    assert len(entries) == 1
    assert entries[0]["success"] is False
    assert entries[0]["error"] == "insufficient funds"


# ---------------------------------------------------------------------------
# 9. History limit
# ---------------------------------------------------------------------------


def test_history_respects_limit(tmp_path, monkeypatch):
    """History --limit flag restricts output entries."""
    _isolate(monkeypatch, tmp_path)

    # Write 5 entries directly
    import json
    log_file = tmp_path / "history.log"
    for i in range(5):
        entry = {
            "timestamp": f"2026-01-0{i+1}T00:00:00+00:00",
            "asset_id": "HTETH",
            "address": f"0xAddr{i}",
            "amount": "0.05",
            "success": True,
            "tx_hash": f"0xtx{i}",
            "error": None,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    runner = CliRunner()
    result = runner.invoke(main, ["history", "--limit", "2"])
    assert result.exit_code == 0, result.output
    # Should only show 2 entries
    entries = logger_mod.read_history(2)
    assert len(entries) == 2


# ---------------------------------------------------------------------------
# 10. Multi-asset drip
# ---------------------------------------------------------------------------


def test_drip_comma_separated_assets(tmp_path, monkeypatch):
    """Drip with comma-separated asset IDs processes each."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler()

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config), \
         patch("core.retry.asyncio.sleep", new_callable=AsyncMock):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "HTETH,GTETH", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    assert mock_handler.drip.call_count == 2


# ---------------------------------------------------------------------------
# 11. Refill family filter
# ---------------------------------------------------------------------------


def test_refill_family_filter(tmp_path, monkeypatch):
    """Refill --family filters to the specified family only."""
    _isolate(monkeypatch, tmp_path)

    fake_assets = {
        "HTETH": {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True},
        "TSOL": {"family": "solana", "blockchain": "solana", "drip_amount": "1.0", "native_asset": True},
    }

    handler = _make_handler(balance={"native": "10.0"})

    with patch("cli.get_all_assets", return_value=fake_assets), \
         patch("cli.get_handler", return_value=handler):
        runner = CliRunner()
        result = runner.invoke(main, ["refill", "--family", "evm"])

    assert result.exit_code == 0, result.output
    assert "OK HTETH" in result.output
    assert "TSOL" not in result.output


# ---------------------------------------------------------------------------
# 12. Batch with mixed success/failure
# ---------------------------------------------------------------------------


def test_batch_mixed_results(tmp_path, monkeypatch):
    """Batch with one success and one failure shows correct summary."""
    _isolate(monkeypatch, tmp_path)

    csv_file = tmp_path / "mixed.csv"
    csv_file.write_text("HTETH,0xGoodAddr\nHTETH,0xBadAddr\n")

    call_count = 0

    async def fake_drip(address, asset_id, amount):
        nonlocal call_count
        call_count += 1
        if "Good" in address:
            return DripResult(success=True, tx_hash="0xgood", explorer_url=None,
                              error=None, amount="0.05", asset="HTETH")
        return DripResult(success=False, tx_hash=None, explorer_url=None,
                          error="insufficient funds", amount="0.05", asset="HTETH")

    mock_handler = MagicMock()
    mock_handler.validate_address.return_value = True
    mock_handler.drip = fake_drip

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["batch", str(csv_file)])

    assert result.exit_code == 0, result.output
    assert "1 succeeded" in result.output
    assert "1 failed" in result.output


# ---------------------------------------------------------------------------
# 13. Dry run
# ---------------------------------------------------------------------------


def test_drip_dry_run(tmp_path, monkeypatch):
    """Drip --dry-run validates without sending."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler()

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "HTETH", "0xTestAddr"])

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output or "would send" in result.output
    mock_handler.drip.assert_not_called()


# ---------------------------------------------------------------------------
# 14. Invalid address in drip
# ---------------------------------------------------------------------------


def test_drip_invalid_address(tmp_path, monkeypatch):
    """Drip with invalid address shows error."""
    _isolate(monkeypatch, tmp_path)

    mock_handler = _make_handler(validate=False)

    def fake_get_asset_config(asset_id):
        return {"family": "evm", "blockchain": "ethereum", "drip_amount": "0.05", "native_asset": True}

    with patch("cli.get_handler", return_value=mock_handler), \
         patch("cli.get_asset_config", side_effect=fake_get_asset_config):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "HTETH", "bad_address"])

    assert result.exit_code == 0, result.output
    assert "Invalid address" in result.output
    mock_handler.drip.assert_not_called()
