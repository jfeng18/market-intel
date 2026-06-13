PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
CLI ?= market-intel

export PYTHONPATH := src

.PHONY: check-python install test smoke console-smoke privacy-scan ci

check-python:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 'Python 3.10+ is required for install/ci. Set PYTHON=python3.10 or use a 3.10+ virtualenv.')"

install: check-python
	$(PIP) install --upgrade pip
	$(PIP) install -e . pytest

test:
	$(PYTEST) -q

smoke:
	$(PYTHON) -m market_intel.cli --help >/dev/null
	$(PYTHON) -m market_intel.cli pool --help >/dev/null
	$(PYTHON) -m market_intel.cli serve --help >/dev/null
	$(PYTHON) -m market_intel.cli pool explain 002837 --json >/dev/null
	$(PYTHON) -m market_intel.cli pool add 000001 --dry-run --json >/dev/null
	$(PYTHON) -m market_intel.cli pool remove 000001 --dry-run --json >/dev/null
	$(PYTHON) -m market_intel.cli pool quality invalid_symbol --json >/dev/null
	$(PYTHON) -m market_intel.cli provider health --json >/dev/null || true
	$(PYTHON) -m market_intel.cli sync quotes --provider tencent-batch --symbols 000001 --dry-run --json >/dev/null || true
	$(PYTHON) -m market_intel.cli scan --mock --text >/dev/null
	$(PYTHON) -m market_intel.cli daily --mock --text >/dev/null
	$(PYTHON) -m market_intel.cli focus --mock --text >/dev/null || true
	$(PYTHON) -m market_intel.cli dashboard --mock --text >/dev/null
	$(PYTHON) -m market_intel.cli agent briefing --profile livermore --json >/dev/null || true
	$(PYTHON) -m market_intel.cli review --no-sync --no-save --text >/dev/null 2>&1 || true

console-smoke:
	$(CLI) --help >/dev/null

privacy-scan: check-python
	$(PYTHON) scripts/privacy_scan.py

ci: install test smoke console-smoke privacy-scan
