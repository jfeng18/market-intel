import sys

import pytest


@pytest.fixture
def cli_cmd():
    def build(*args: str) -> list[str]:
        return [sys.executable, "-m", "market_intel.cli", *args]

    return build
