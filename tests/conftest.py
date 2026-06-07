import sys

import pytest


@pytest.fixture
def cli_cmd():
    def build(*args: str) -> list[str]:
        return [sys.executable, "-m", "market_intel.cli", *args]

    return build


@pytest.fixture(autouse=True)
def isolated_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
