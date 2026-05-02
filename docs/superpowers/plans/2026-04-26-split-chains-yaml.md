# Split chains.yaml Into Per-Family Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 1661-line monolithic `config/chains.yaml` with a `config/chains/` directory of per-family YAML files, updating all consumers so no runtime or test behaviour changes.

**Architecture:** A new `_get_chains_yaml_dir()` replaces `_get_chains_yaml_path()` as the single seam all consumers use. `load_registry()` globs `config/chains/*.yaml` and merges. `save_chains_yaml()` in `tui/data.py` groups the incoming dict by `family` and writes each group to the matching file. Tests that previously patched `_get_chains_yaml_path` are updated to patch `_get_chains_yaml_dir` with a temp directory.

**Tech Stack:** Python stdlib `pathlib.glob`, `yaml` (already in use), pytest `monkeypatch`

---

### Task 1: Update `core/registry.py` — new seam + updated loader

**Files:**
- Modify: `core/registry.py`
- Modify: `tests/test_registry.py`

---

- [ ] **Step 1: Write failing tests for the new directory-based loader**

Replace the entire contents of `tests/test_registry.py` with:

```python
import yaml
import pytest
from core import registry as reg


ASSET_EVM = {
    "family": "evm",
    "blockchain": "Ethereum",
    "network": "holesky",
    "native_asset": True,
    "drip_amount": "0.05",
    "decimals": 18,
}
ASSET_SOL = {
    "family": "solana",
    "blockchain": "Solana",
    "network": "devnet",
    "native_asset": True,
    "drip_amount": "0.1",
    "decimals": 9,
}


@pytest.fixture(autouse=True)
def reset_registry():
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()
    yield
    reg._REGISTRY = None
    reg._HANDLER_CACHE.clear()


def _make_chains_dir(tmp_path, files: dict[str, dict]) -> None:
    """Create a chains/ directory under tmp_path with one yaml file per entry."""
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    for filename, data in files.items():
        (chains_dir / filename).write_text(yaml.safe_dump(data, sort_keys=False))
    return chains_dir


def test_load_registry_merges_multiple_files(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {
        "evm.yaml": {"HTETH": ASSET_EVM},
        "solana.yaml": {"TSOL": ASSET_SOL},
    })
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    registry = reg.load_registry()
    assert "HTETH" in registry
    assert "TSOL" in registry


def test_load_registry_single_file(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {
        "evm.yaml": {"HTETH": ASSET_EVM},
    })
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    registry = reg.load_registry()
    assert registry["HTETH"]["family"] == "evm"


def test_load_registry_missing_dir_raises(tmp_path, monkeypatch):
    missing = tmp_path / "chains"
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: missing)
    with pytest.raises(FileNotFoundError, match="config/chains"):
        reg.load_registry()


def test_get_asset_config(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {"evm.yaml": {"HTETH": ASSET_EVM}})
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    config = reg.get_asset_config("HTETH")
    assert config["family"] == "evm"
    assert config["network"] == "holesky"


def test_get_asset_config_unknown(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {"evm.yaml": {"HTETH": ASSET_EVM}})
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    with pytest.raises(KeyError, match="UNKNOWN"):
        reg.get_asset_config("UNKNOWN")


def test_get_handler_not_implemented(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {
        "foo.yaml": {
            "TFOO": {
                "family": "unknown_future_chain",
                "blockchain": "FutureChain",
                "network": "testnet",
                "native_asset": True,
                "drip_amount": "1",
                "decimals": 9,
            }
        }
    })
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    with pytest.raises(NotImplementedError):
        reg.get_handler("TFOO")


def test_get_asset_config_missing_fields(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {
        "evm.yaml": {"INCOMPLETE": {"family": "evm"}}
    })
    monkeypatch.setattr(reg, "_get_chains_yaml_dir", lambda: chains_dir)
    with pytest.raises(ValueError, match="missing required fields"):
        reg.get_asset_config("INCOMPLETE")
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
uv run pytest tests/test_registry.py -v
```

Expected: all 7 tests FAIL with `AttributeError: module 'core.registry' has no attribute '_get_chains_yaml_dir'` (or similar).

- [ ] **Step 3: Implement the changes in `core/registry.py`**

Replace the `_get_chains_yaml_path` function and `load_registry` function. Keep everything else identical:

```python
import yaml
from pathlib import Path
from handlers.base import BaseHandler

_REGISTRY: dict[str, dict] | None = None
_HANDLER_CACHE: dict[str, BaseHandler] = {}

FAMILY_HANDLER_MAP: dict[str, str] = {
    "evm": "handlers.evm.EvmHandler",
    "solana": "handlers.solana.SolanaHandler",
    "cosmos": "handlers.cosmos.CosmosHandler",
    "sui": "handlers.sui.SuiHandler",
    "aptos": "handlers.aptos.AptosHandler",
    "near": "handlers.near.NearHandler",
    "xrp": "handlers.xrp.XrpHandler",
    "stellar": "handlers.stellar.StellarHandler",
    "tron": "handlers.tron.TronHandler",
    "ton": "handlers.ton.TonHandler",
    "hedera": "handlers.hedera.HederaHandler",
    "utxo": "handlers.utxo.UtxoHandler",
    "algorand": "handlers.algorand.AlgorandHandler",
    "cardano": "handlers.cardano.CardanoHandler",
    "eos": "handlers.eos.EosHandler",
    "substrate": "handlers.substrate.SubstrateHandler",
    "stacks": "handlers.stacks.StacksHandler",
    "flow": "handlers.flow.FlowHandler",
    "vechain": "handlers.vechain.VeChainHandler",
    "tezos": "handlers.tezos.TezosHandler",
    "zcash": "handlers.zcash.ZcashHandler",
    "icp": "handlers.icp.IcpHandler",
    "bittensor": "handlers.bittensor.BittensorHandler",
    "avalanche_p": "handlers.avalanche.AvalanchePHandler",
    "canton": "handlers.canton.CantonHandler",
}


def _get_chains_yaml_dir() -> Path:
    return Path(__file__).parent.parent / "config" / "chains"


def load_registry() -> dict[str, dict]:
    global _REGISTRY
    if _REGISTRY is None:
        chains_dir = _get_chains_yaml_dir()
        if not chains_dir.exists():
            raise FileNotFoundError(f"config/chains directory not found at {chains_dir}")
        merged: dict[str, dict] = {}
        for yaml_file in sorted(chains_dir.glob("*.yaml")):
            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}
            merged.update(data)
        _REGISTRY = merged
    return _REGISTRY


REQUIRED_FIELDS = {"family", "blockchain", "network", "native_asset", "drip_amount", "decimals"}


def get_asset_config(asset_id: str) -> dict:
    registry = load_registry()
    if asset_id not in registry:
        raise KeyError(f"Unknown asset: {asset_id}")
    config = registry[asset_id]
    missing = REQUIRED_FIELDS - set(config.keys())
    if missing:
        raise ValueError(f"Asset {asset_id} missing required fields: {missing}")
    return config


def get_all_assets() -> dict[str, dict]:
    return load_registry()


def get_handler(asset_id: str) -> BaseHandler:
    if asset_id in _HANDLER_CACHE:
        return _HANDLER_CACHE[asset_id]

    config = get_asset_config(asset_id)
    family = config.get("family")
    if not family:
        raise ValueError(f"Asset {asset_id} has no 'family' field in registry")

    handler_path = FAMILY_HANDLER_MAP.get(family)
    if not handler_path:
        raise NotImplementedError(f"No handler registered for family: {family}")

    module_path, class_name = handler_path.rsplit(".", 1)
    try:
        import importlib
        module = importlib.import_module(module_path)
        handler_class = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise NotImplementedError(f"Handler not yet implemented for family '{family}': {e}")

    handler = handler_class(config)
    _HANDLER_CACHE[asset_id] = handler
    return handler
```

- [ ] **Step 4: Run only the registry tests**

```bash
uv run pytest tests/test_registry.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/registry.py tests/test_registry.py
git commit -m "refactor: replace _get_chains_yaml_path with _get_chains_yaml_dir, load from directory"
```

---

### Task 2: Split `config/chains.yaml` into per-family files

**Files:**
- Create: `config/chains/<family>.yaml` (25 files, one per family)
- (The split script is a one-shot tool, not committed to the repo)

---

- [ ] **Step 1: Run the splitting script**

Execute this in the project root (copy-paste the whole block):

```bash
uv run python - <<'EOF'
import yaml
from pathlib import Path
from collections import defaultdict

src = Path("config/chains.yaml")
dst_dir = Path("config/chains")
dst_dir.mkdir(exist_ok=True)

with open(src) as f:
    all_assets = yaml.safe_load(f)

by_family: dict[str, dict] = defaultdict(dict)
for asset_id, config in all_assets.items():
    family = config.get("family", "unknown")
    by_family[family][asset_id] = config

for family, assets in sorted(by_family.items()):
    out_path = dst_dir / f"{family}.yaml"
    with open(out_path, "w") as f:
        yaml.safe_dump(assets, f, sort_keys=False)
    print(f"  {out_path}  ({len(assets)} assets)")

print(f"\nTotal families: {len(by_family)}")
print(f"Total assets:   {sum(len(v) for v in by_family.values())}")
EOF
```

Expected output (25 families, 144 assets total):
```
  config/chains/algorand.yaml  (1 assets)
  config/chains/aptos.yaml  (3 assets)
  config/chains/avalanche_p.yaml  (1 assets)
  config/chains/bittensor.yaml  (1 assets)
  config/chains/canton.yaml  (1 assets)
  config/chains/cardano.yaml  (1 assets)
  config/chains/cosmos.yaml  (14 assets)
  config/chains/eos.yaml  (5 assets)
  config/chains/evm.yaml  (72 assets)
  config/chains/flow.yaml  (1 assets)
  config/chains/hedera.yaml  (2 assets)
  config/chains/icp.yaml  (1 assets)
  config/chains/near.yaml  (2 assets)
  config/chains/solana.yaml  (12 assets)
  config/chains/stacks.yaml  (1 assets)
  config/chains/stellar.yaml  (4 assets)
  config/chains/substrate.yaml  (2 assets)
  config/chains/sui.yaml  (3 assets)
  config/chains/tezos.yaml  (1 assets)
  config/chains/ton.yaml  (1 assets)
  config/chains/tron.yaml  (4 assets)
  config/chains/utxo.yaml  (6 assets)
  config/chains/vechain.yaml  (2 assets)
  config/chains/xrp.yaml  (2 assets)
  config/chains/zcash.yaml  (1 assets)

Total families: 25
Total assets:   144
```

- [ ] **Step 2: Verify the registry loads from the new directory**

```bash
uv run python -c "
from core import registry as reg
reg._REGISTRY = None
assets = reg.load_registry()
print(f'Loaded {len(assets)} assets from config/chains/')
assert len(assets) == 144, f'Expected 144, got {len(assets)}'
print('OK')
"
```

Expected: prints `Loaded 144 assets from config/chains/` then `OK`.

- [ ] **Step 3: Run the full test suite (chains.yaml still present — both paths co-exist)**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: same pass count as before this PR (531 tests pass).
Note: `config/chains.yaml` still exists at this point; the new directory is live but the old file is not yet removed.

- [ ] **Step 4: Commit the new per-family files**

```bash
git add config/chains/
git commit -m "chore: split config/chains.yaml into per-family files under config/chains/"
```

---

### Task 3: Update `tests/conftest.py` — restore directory instead of single file

**Files:**
- Modify: `tests/conftest.py`

---

- [ ] **Step 1: Confirm current conftest behaviour**

```bash
uv run pytest tests/test_registry.py -v --co -q
```

Expected: 7 tests collected (no skip).

- [ ] **Step 2: Update `tests/conftest.py`**

Replace the entire file with:

```python
"""Ensure config/chains/ directory exists before any test runs.

The per-family YAML files are tracked in git but may be missing from the
working tree (e.g. accidentally deleted). Restore from HEAD automatically.
"""
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def ensure_chains_dir():
    chains_dir = Path(__file__).parent.parent / "config" / "chains"
    if not chains_dir.exists() or not any(chains_dir.glob("*.yaml")):
        result = subprocess.run(
            ["git", "restore", "config/"],
            capture_output=True,
            cwd=chains_dir.parent.parent,
        )
        if result.returncode != 0 or not chains_dir.exists():
            pytest.skip("config/chains/ missing and could not be restored from git")


@pytest.fixture(autouse=True)
def _isolate_history_log(tmp_path, monkeypatch):
    """Redirect drip history log to a temp file so tests don't write to ~/.testnet-faucet/."""
    import core.logger as logger_mod
    monkeypatch.setattr(logger_mod, "LOG_PATH", tmp_path / "history.log")


@pytest.fixture(autouse=True)
def _isolate_alerts_log(tmp_path, monkeypatch):
    """Redirect alerts log to a temp file so tests don't write to ~/.testnet-faucet/."""
    import core.alerting as alerting_mod
    monkeypatch.setattr(alerting_mod, "ALERTS_LOG_PATH", tmp_path / "alerts.log")
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: 531 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "refactor: update conftest restore fixture to handle config/chains/ directory"
```

---

### Task 4: Update `tui/data.py` — load/save from directory

**Files:**
- Modify: `tui/data.py`
- Modify: `tests/test_tui_data.py`

---

- [ ] **Step 1: Write failing tests for the new load/save behaviour**

Open `tests/test_tui_data.py`. Find the section starting at line 89:

```
# ---------------------------------------------------------------------------
# load_chains_yaml / save_chains_yaml
# ---------------------------------------------------------------------------
```

Replace the three tests `test_load_chains_yaml_returns_dict`, `test_save_chains_yaml_roundtrip`, and `test_save_chains_yaml_invalidates_cache` with:

```python
# ---------------------------------------------------------------------------
# load_chains_yaml / save_chains_yaml
# ---------------------------------------------------------------------------

def _make_chains_dir(tmp_path, files: dict[str, dict]):
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    for filename, content in files.items():
        (chains_dir / filename).write_text(yaml.safe_dump(content, sort_keys=False))
    return chains_dir


def test_load_chains_yaml_returns_merged_dict(tmp_path, monkeypatch):
    chains_dir = _make_chains_dir(tmp_path, {
        "evm.yaml": {"HTETH": {"family": "evm"}},
        "solana.yaml": {"TSOL": {"family": "solana"}},
    })
    monkeypatch.setattr("core.registry._get_chains_yaml_dir", lambda: chains_dir)
    result = data.load_chains_yaml()
    assert result == {
        "HTETH": {"family": "evm"},
        "TSOL": {"family": "solana"},
    }


def test_save_chains_yaml_splits_by_family(tmp_path, monkeypatch):
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    monkeypatch.setattr("core.registry._get_chains_yaml_dir", lambda: chains_dir)
    payload = {
        "HTETH": {"family": "evm", "drip_amount": "0.05"},
        "TSOL": {"family": "solana", "drip_amount": "0.1"},
    }
    data.save_chains_yaml(payload)
    assert (chains_dir / "evm.yaml").exists()
    assert (chains_dir / "solana.yaml").exists()
    evm_data = yaml.safe_load((chains_dir / "evm.yaml").read_text())
    assert evm_data == {"HTETH": {"family": "evm", "drip_amount": "0.05"}}


def test_save_chains_yaml_roundtrip(tmp_path, monkeypatch):
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    monkeypatch.setattr("core.registry._get_chains_yaml_dir", lambda: chains_dir)
    payload = {
        "HTETH": {"family": "evm", "drip_amount": "0.05"},
        "TSOL": {"family": "solana", "drip_amount": "0.1"},
    }
    data.save_chains_yaml(payload)
    result = data.load_chains_yaml()
    assert result == payload


def test_save_chains_yaml_invalidates_cache(tmp_path, monkeypatch):
    chains_dir = tmp_path / "chains"
    chains_dir.mkdir()
    monkeypatch.setattr("core.registry._get_chains_yaml_dir", lambda: chains_dir)
    reg._REGISTRY = {"stale": {}}
    reg._HANDLER_CACHE["stale"] = MagicMock()
    data.save_chains_yaml({"fresh": {"family": "evm"}})
    assert reg._REGISTRY is None
    assert reg._HANDLER_CACHE == {}
```

Also add `import yaml` at the top of `test_tui_data.py` if not already there.

- [ ] **Step 2: Run those specific tests to confirm they fail**

```bash
uv run pytest tests/test_tui_data.py -k "chains_yaml" -v
```

Expected: all 4 tests FAIL (the helpers don't exist yet / old implementation is wrong).

- [ ] **Step 3: Update `tui/data.py` — new `load_chains_yaml` and `save_chains_yaml`**

Replace the `load_chains_yaml` and `save_chains_yaml` functions (lines 56–73) with:

```python
def load_chains_yaml() -> dict:
    """Load the asset registry by merging all files in config/chains/."""
    chains_dir = registry._get_chains_yaml_dir()
    merged: dict = {}
    for yaml_file in sorted(chains_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            merged.update(yaml.safe_load(f) or {})
    return merged


def save_chains_yaml(data: dict) -> None:
    """Write data back to config/chains/, splitting by family field.

    NOTE: Comments will be lost — callers should warn users.
    """
    chains_dir = registry._get_chains_yaml_dir()
    by_family: dict[str, dict] = {}
    for asset_id, config in data.items():
        family = config.get("family", "unknown")
        by_family.setdefault(family, {})[asset_id] = config
    for family, assets in by_family.items():
        with open(chains_dir / f"{family}.yaml", "w") as f:
            yaml.safe_dump(assets, f, sort_keys=False)
    registry._REGISTRY = None
    registry._HANDLER_CACHE.clear()
```

- [ ] **Step 4: Run the tui_data tests**

```bash
uv run pytest tests/test_tui_data.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: 531 tests pass.

- [ ] **Step 6: Commit**

```bash
git add tui/data.py tests/test_tui_data.py
git commit -m "refactor: update tui/data.py load/save to use config/chains/ directory"
```

---

### Task 5: Remove the old `config/chains.yaml` file

**Files:**
- Delete: `config/chains.yaml`

---

- [ ] **Step 1: Confirm no remaining references to `_get_chains_yaml_path`**

```bash
grep -rn "_get_chains_yaml_path" /Users/ivo/dev/personal/testnet-faucet-tool/ --include="*.py"
```

Expected: zero matches. If any remain, update them to `_get_chains_yaml_dir` before continuing.

- [ ] **Step 2: Confirm no code reads `config/chains.yaml` directly**

```bash
grep -rn "chains\.yaml" /Users/ivo/dev/personal/testnet-faucet-tool/ --include="*.py" | grep -v "test_" | grep -v "__pycache__"
```

Expected: zero matches (or only comments).

- [ ] **Step 3: Remove `config/chains.yaml` from git tracking**

```bash
git rm config/chains.yaml
```

- [ ] **Step 4: Run the full test suite one final time**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: 531 tests pass with no errors or skips.

- [ ] **Step 5: Check that `faucet status` still works at the CLI level**

```bash
uv run faucet status --family evm 2>&1 | head -5
```

Expected: prints a table of EVM asset statuses (or "no wallet configured" messages) — no `FileNotFoundError`.

- [ ] **Step 6: Update `TODO.md` to mark the refactoring item complete**

In `TODO.md`, change:

```
- [ ] Split `config/chains.yaml` (1662 lines) into one file per chain family
```

to:

```
- [x] Split `config/chains.yaml` (1662 lines) into one file per chain family
```

- [ ] **Step 7: Final commit**

```bash
git add TODO.md
git commit -m "chore: remove config/chains.yaml — fully replaced by config/chains/ directory"
```
