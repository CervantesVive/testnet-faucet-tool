"""Integration tests for Phase 6 handlers."""

from click.testing import CliRunner
from cli import main
from core import rate_limiter as rl


# ---------------------------------------------------------------------------
# Valid test addresses per asset
# ---------------------------------------------------------------------------

PHASE6_ADDRESSES = {
    "THBAR": "0.0.12345",
    "TADA": "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3jcu5d8ps7zex2k2xt3uqxgjqnnj83ws8lhrn648jjxtwq2ytjqp",
    "TALGO": "VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA",
    "TEOS": "eosio",
    "TDOT": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
    "TSTX": "ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG",
    "TFLOW": "e467b9dd11fa00df",
    "TVET": "0x7567d83b7b8d80addcb281a71d54fc7b3364ffed",
    "TXTZ": "tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb",
    "TZEC": "tmBsTi7vSLp5FwMFUE4grJjTQ7tCzPgYn1A",
    "TICP": "rrkah-fqaaa-aaaaa-aaaaq-cai",
    "TTAO": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
    "TCANTON": "any-canton-address",
    "TAVAXP": "P-fuji1wycm8t4alm0relpjg0mxqjqn0szmkdpjhqvxy5",
}


# ---------------------------------------------------------------------------
# faucet list --family <family>
# ---------------------------------------------------------------------------

class TestListCommand:
    def test_list_hedera(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "hedera"])
        assert result.exit_code == 0
        assert "THBAR" in result.output

    def test_list_cardano(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "cardano"])
        assert result.exit_code == 0
        assert "TADA" in result.output

    def test_list_algorand(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "algorand"])
        assert result.exit_code == 0
        assert "TALGO" in result.output

    def test_list_eos(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "eos"])
        assert result.exit_code == 0
        assert "TEOS" in result.output

    def test_list_substrate(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "substrate"])
        assert result.exit_code == 0
        assert "TDOT" in result.output

    def test_list_stacks(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "stacks"])
        assert result.exit_code == 0
        assert "TSTX" in result.output

    def test_list_flow(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "flow"])
        assert result.exit_code == 0
        assert "TFLOW" in result.output

    def test_list_vechain(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "vechain"])
        assert result.exit_code == 0
        assert "TVET" in result.output

    def test_list_tezos(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "tezos"])
        assert result.exit_code == 0
        assert "TXTZ" in result.output

    def test_list_zcash(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "zcash"])
        assert result.exit_code == 0
        assert "TZEC" in result.output

    def test_list_icp(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "icp"])
        assert result.exit_code == 0
        assert "TICP" in result.output

    def test_list_bittensor(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "bittensor"])
        assert result.exit_code == 0
        assert "TTAO" in result.output

    def test_list_avalanche_p(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "avalanche_p"])
        assert result.exit_code == 0
        assert "TAVAXP" in result.output

    def test_list_canton(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--family", "canton"])
        assert result.exit_code == 0
        assert "TCANTON" in result.output


# ---------------------------------------------------------------------------
# faucet drip --dry-run
# ---------------------------------------------------------------------------

class TestDripDryRun:
    def test_drip_hedera_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "THBAR", "0.0.12345"])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_cardano_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TADA", PHASE6_ADDRESSES["TADA"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_algorand_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TALGO", PHASE6_ADDRESSES["TALGO"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_eos_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TEOS", PHASE6_ADDRESSES["TEOS"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_substrate_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TDOT", PHASE6_ADDRESSES["TDOT"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_stacks_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TSTX", PHASE6_ADDRESSES["TSTX"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_flow_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TFLOW", PHASE6_ADDRESSES["TFLOW"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_vechain_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TVET", PHASE6_ADDRESSES["TVET"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_tezos_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TXTZ", PHASE6_ADDRESSES["TXTZ"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_zcash_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TZEC", PHASE6_ADDRESSES["TZEC"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_icp_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TICP", PHASE6_ADDRESSES["TICP"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_bittensor_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TTAO", PHASE6_ADDRESSES["TTAO"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_canton_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TCANTON", PHASE6_ADDRESSES["TCANTON"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_drip_avalanche_p_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TAVAXP", PHASE6_ADDRESSES["TAVAXP"]])
        assert result.exit_code == 0
        assert "Dry run" in result.output


# ---------------------------------------------------------------------------
# Invalid address tests
# ---------------------------------------------------------------------------

class TestInvalidAddress:
    def test_drip_hedera_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "THBAR", "invalid"])
        assert "Invalid address" in result.output

    def test_drip_cardano_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TADA", "invalid"])
        assert "Invalid address" in result.output

    def test_drip_flow_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TFLOW", "short"])
        assert "Invalid address" in result.output

    def test_drip_icp_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TICP", ""])
        assert result.exit_code != 0 or "Invalid address" in result.output or "Missing" in result.output

    def test_drip_avalanche_p_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TAVAXP", "X-fuji1abc"])
        assert "Invalid address" in result.output

    def test_drip_zcash_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TZEC", "invalid"])
        assert "Invalid address" in result.output

    def test_drip_tezos_invalid(self):
        runner = CliRunner()
        result = runner.invoke(main, ["drip", "--dry-run", "TXTZ", "invalid"])
        assert "Invalid address" in result.output
