from click.testing import CliRunner
from unittest.mock import patch
import yaml
from cli import main
from core import registry as reg

MINIMAL_YAML = yaml.dump({
    "HTETH": {"family": "evm", "blockchain": "Ethereum", "network": "holesky",
              "native_asset": True, "drip_amount": "0.05", "decimals": 18},
    "TSOL": {"family": "solana", "blockchain": "Solana", "network": "devnet",
             "native_asset": True, "drip_amount": "0.1", "decimals": 9},
})


def make_chains_yaml(tmp_path):
    p = tmp_path / "chains.yaml"
    p.write_text(MINIMAL_YAML)
    return p


def test_list_command(tmp_path, monkeypatch):
    chains_yaml = make_chains_yaml(tmp_path)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    reg._REGISTRY = None
    runner = CliRunner()
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert "HTETH" in result.output
    assert "TSOL" in result.output


def test_list_command_family_filter(tmp_path, monkeypatch):
    chains_yaml = make_chains_yaml(tmp_path)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    reg._REGISTRY = None
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--family", "evm"])
    assert result.exit_code == 0
    assert "HTETH" in result.output
    assert "TSOL" not in result.output


def test_drip_dry_run_handler_not_implemented(tmp_path, monkeypatch):
    chains_yaml = make_chains_yaml(tmp_path)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "--dry-run", "HTETH", "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18"])
    assert result.exit_code == 0
    # handler not implemented yet, should print skip message
    assert "Skipping" in result.output or "dry run" in result.output


def test_drip_unknown_asset(tmp_path, monkeypatch):
    chains_yaml = make_chains_yaml(tmp_path)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    reg._REGISTRY = None
    runner = CliRunner()
    result = runner.invoke(main, ["drip", "UNKNOWN", "0xabc"])
    assert result.exit_code == 0
    assert "Error" in result.output or "Unknown" in result.output
