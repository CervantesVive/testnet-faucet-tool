import pytest
from unittest.mock import patch, mock_open
import yaml
from core import registry as reg


MINIMAL_YAML = yaml.dump({
    "HTETH": {"family": "evm", "blockchain": "Ethereum", "network": "holesky", "native_asset": True, "drip_amount": "0.05", "decimals": 18},
    "TSOL": {"family": "solana", "blockchain": "Solana", "network": "devnet", "native_asset": True, "drip_amount": "0.1", "decimals": 9},
})


@pytest.fixture(autouse=True)
def reset_registry():
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()
    yield
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()


def test_load_registry(tmp_path, monkeypatch):
    chains_yaml = tmp_path / "chains.yaml"
    chains_yaml.write_text(MINIMAL_YAML)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    registry = reg.load_registry()
    assert "HTETH" in registry
    assert "TSOL" in registry


def test_get_asset_config(tmp_path, monkeypatch):
    chains_yaml = tmp_path / "chains.yaml"
    chains_yaml.write_text(MINIMAL_YAML)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    config = reg.get_asset_config("HTETH")
    assert config["family"] == "evm"
    assert config["network"] == "holesky"


def test_get_asset_config_unknown(tmp_path, monkeypatch):
    chains_yaml = tmp_path / "chains.yaml"
    chains_yaml.write_text(MINIMAL_YAML)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    with pytest.raises(KeyError, match="UNKNOWN"):
        reg.get_asset_config("UNKNOWN")


def test_get_handler_not_implemented(tmp_path, monkeypatch):
    minimal_with_solana = yaml.dump({
        "TSOL": {
            "family": "solana",
            "blockchain": "Solana",
            "network": "devnet",
            "native_asset": True,
            "drip_amount": "1",
            "decimals": 9,
        }
    })
    chains_yaml = tmp_path / "chains.yaml"
    chains_yaml.write_text(minimal_with_solana)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()
    with pytest.raises(NotImplementedError):
        reg.get_handler("TSOL")  # solana.py not yet implemented


def test_get_asset_config_missing_fields(tmp_path, monkeypatch):
    incomplete_yaml = yaml.dump({"INCOMPLETE": {"family": "evm"}})
    chains_yaml = tmp_path / "chains.yaml"
    chains_yaml.write_text(incomplete_yaml)
    monkeypatch.setattr(reg, "_get_chains_yaml_path", lambda: chains_yaml)
    with pytest.raises(ValueError, match="missing required fields"):
        reg.get_asset_config("INCOMPLETE")
