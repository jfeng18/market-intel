PYTHON ?= python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
CLI ?= market-intel

export PYTHONPATH := src

.PHONY: check-python install test smoke console-smoke ci

check-python:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 'Python 3.10+ is required for install/ci. Set PYTHON=python3.10 or use a 3.10+ virtualenv.')"

install: check-python
	$(PIP) install --upgrade pip
	$(PIP) install -e . pytest

test:
	$(PYTEST) -q

smoke:
	$(PYTHON) -m market_intel.cli --help >/dev/null
	$(PYTHON) -m market_intel.cli pool explain 002837 --json >/dev/null
	$(PYTHON) -m market_intel.cli daily --mock --text >/dev/null

console-smoke:
	$(CLI) --help >/dev/null

ci: install test smoke console-smoke
