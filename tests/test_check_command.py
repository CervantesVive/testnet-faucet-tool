"""Integration tests for the `faucet check` and `faucet monitor` CLI commands."""
import pytest
from click.testing import CliRunner
from unittest.mock import patch
from cli import main


def _ok_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "OK",
             "balance": 5.0, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": None}]


def _low_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "LOW",
             "balance": 0.01, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": None}]


def _error_results():
    return [{"asset_id": "TTEST", "blockchain": "TestChain", "status": "ERROR",
             "balance": None, "threshold": 0.1, "refill_source": None,
             "auto_top_attempted": False, "auto_top_succeeded": False, "error": "oops"}]


def test_check_exits_0_when_all_ok():
    """Exit code 0 when all wallets are OK."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 0


def test_check_exits_1_when_any_low():
    """Exit code 1 when any wallet is LOW."""
    with patch("cli.run_check", return_value=_low_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 1


def test_check_exits_1_when_any_error():
    """Exit code 1 when any wallet has ERROR status."""
    with patch("cli.run_check", return_value=_error_results()):
        result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 1


def test_check_output_contains_summary():
    """Output includes summary line with counts."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert "1 OK" in result.output
    assert "0 LOW" in result.output
    assert "0 ERROR" in result.output


def test_check_output_shows_asset_row():
    """Output includes a row with the asset ID."""
    with patch("cli.run_check", return_value=_ok_results()):
        result = CliRunner().invoke(main, ["check"])
    assert "TTEST" in result.output


def test_check_threshold_flag_passed_to_run_check():
    """--threshold flag is forwarded to run_check."""
    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        CliRunner().invoke(main, ["check", "--threshold", "5.0"])
    mock_rc.assert_called_once_with(threshold_override=5.0, family=None)


def test_check_family_flag_passed_to_run_check():
    """--family flag is forwarded to run_check."""
    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        CliRunner().invoke(main, ["check", "--family", "evm"])
    mock_rc.assert_called_once_with(threshold_override=None, family="evm")


def test_check_auto_top_succeeded_shown_in_output():
    """When auto-top succeeded, output reflects it."""
    results = [{"asset_id": "TSOL", "blockchain": "Solana", "status": "LOW",
                "balance": 0.0, "threshold": 2.0, "refill_source": "airdrop",
                "auto_top_attempted": True, "auto_top_succeeded": True, "error": None}]
    with patch("cli.run_check", return_value=results):
        result = CliRunner().invoke(main, ["check"])
    assert "succeeded" in result.output


def test_monitor_invalid_interval_shows_error():
    """Invalid --interval value prints error and exits cleanly."""
    result = CliRunner().invoke(main, ["monitor", "--interval", "bad"])
    assert result.exit_code == 0
    assert "Invalid interval" in result.output


def test_monitor_runs_one_pass_and_stops_on_keyboard_interrupt():
    """Monitor runs one check pass, then stops when sleep is interrupted."""
    ok_results = _ok_results()
    call_count = {"n": 0}

    def fake_sleep(secs):
        call_count["n"] += 1
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=ok_results):
        with patch("cli.time.sleep", side_effect=fake_sleep):
            result = CliRunner().invoke(main, ["monitor", "--interval", "1h"])

    assert call_count["n"] == 1
    assert result.exit_code == 0


def test_monitor_output_contains_pass_started():
    """Monitor output includes pass-started messages."""
    def fake_sleep(_):
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=_ok_results()):
        with patch("cli.time.sleep", side_effect=fake_sleep):
            result = CliRunner().invoke(main, ["monitor", "--interval", "1h"])

    assert "Pass started" in result.output


def test_monitor_threshold_flag_forwarded():
    """--threshold is passed to run_check inside monitor loop."""
    def fake_sleep(_):
        raise KeyboardInterrupt

    with patch("cli.run_check", return_value=_ok_results()) as mock_rc:
        with patch("cli.time.sleep", side_effect=fake_sleep):
            CliRunner().invoke(main, ["monitor", "--interval", "1h", "--threshold", "9.0"])

    mock_rc.assert_called_with(threshold_override=9.0, family=None)
