"""Ensure config/chains.yaml exists before any test runs.

The file is tracked in git but may be missing from the working tree
(e.g. accidentally deleted). Restore it automatically from HEAD so
tests that invoke the CLI via CliRunner don't fail on FileNotFoundError.
"""
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def ensure_chains_yaml():
    chains_yaml = Path(__file__).parent.parent / "config" / "chains.yaml"
    if not chains_yaml.exists():
        result = subprocess.run(
            ["git", "restore", "config/"],
            capture_output=True,
            cwd=chains_yaml.parent.parent,
        )
        if result.returncode != 0 or not chains_yaml.exists():
            pytest.skip("config/chains.yaml missing and could not be restored from git")
