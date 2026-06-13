# Developer Context

This document is for agents or developers changing `market-intel`.

## Product shape

`market-intel` is a local post-market review workbench for A-shares. It is intentionally boring and agent-friendly:

- stable JSON over clever prose;
- explicit data readiness over guessed conclusions;
- evidence gaps over recommendations;
- local runtime files over cloud upload.

The default product scope is `all-a`. Theme pools are examples, fixtures, or regression aids, not the product boundary.

## Repository map

```text
src/market_intel/cli.py              # CLI parser and command routing
src/market_intel/core/models.py      # data models
src/market_intel/core/csv_importer.py# CSV import and schema contracts
src/market_intel/core/sync.py        # quote sync via akshare/Eastmoney
src/market_intel/core/scoring.py     # scan/hotspot scoring
src/market_intel/core/agent.py       # agent plan/briefing/run/next, command safety
src/market_intel/core/html_report.py # self-contained HTML report
src/market_intel/core/text_report.py # CLI text report
src/market_intel/core/journal.py     # daily archive and notes
src/market_intel/core/server.py      # local browser workbench
examples/                            # public sample data
runtime/                             # local user data, not for commit
docs/                                # product, data model, workflow docs
tests/                               # regression tests
```

## Core invariants

1. Do not output trading instructions.
   - Forbidden fields/phrases include `buy`, `sell`, `hold`, `target_price`, `position_size`, `must_buy`, `must_sell` as recommendations.
   - It is fine to describe data, gaps, queues, and verification questions.

2. Readiness gates conclusions.
   - If quotes or holdings are missing, daily/review output must say blocked/degraded.
   - Do not fabricate market breadth, hotspots, or portfolio conclusions from incomplete runtime.

3. Side effects must be explicit.
   - Register new commands in `agent.py:command_state_effect()`.
   - Unknown commands must remain `unknown` and must not be auto-executed by agent flows or server `/api/run`.
   - Prefer dry-run for imports and pool changes before writes.

4. JSON is a public contract.
   - Preserve the envelope: `ok`, `command`, `version`, `data`, `warnings`, `errors`, `meta`.
   - Add fields without removing stable paths where possible.
   - Add or update tests when stable paths change.

5. Personal data stays local.
   - `runtime/` can contain holdings and should not be committed.
   - Docs, examples, tests, screenshots, and reports must not include real private accounts, tokens, or personal holdings unless explicitly intended as local-only files outside git.

## Command safety classes

Expected `state_effect` values:

- `read_only`: safe for automated agent execution.
- `writes_runtime`: writes runtime data.
- `writes_journal`: writes journal/archive notes.
- `writes_runtime_journal`: writes both runtime and journal.
- `unknown`: not safe for automated execution.

New write commands must be blocked by read-only agent execution until explicitly classified.

## Development workflow

Before editing:

```bash
git status --short --branch
PYTHONPATH=src python3 -m market_intel.cli --help
PYTHONPATH=src python3 -m market_intel.cli agent briefing --json
```

After editing:

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

If the change touches server behavior, also inspect or extend:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_server.py
```

## Data import notes

CSV import supports UTF-8 with BOM, GBK, and GB18030. Column aliases are discoverable with:

```bash
market-intel import schema --json
```

Required real-review imports:

```bash
market-intel import quotes quotes.csv --runtime --dry-run --json
market-intel import holdings holdings.csv --runtime --dry-run --json
market-intel import universe a_share_universe.csv --runtime --dry-run --json
```

Write only after dry-run returns no errors.

## Agent integration notes

Primary agent entry points:

```bash
market-intel agent plan --json
market-intel agent briefing --json
market-intel agent next --json
market-intel agent run --json
```

Agents should consume:

- `data.state` / `data.runtime.readiness.state` first;
- `data.agent_contract.stable_fields` for stable paths;
- `data.command_queue[]` or `data.review_handoff.command_chain[]` for next read-only commands;
- `state_effect` before any command execution;
- `data.daily.risk_register`, `data.daily.portfolio_review`, and `data.daily.coverage_context` only when runtime is not blocked.

## Privacy scan expectation

`make privacy-scan` must pass before handoff. If a fixture intentionally resembles sensitive data, document why it is synthetic and adjust the scan allowlist conservatively.
