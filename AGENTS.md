# AGENTS.md

## Direction

Build `market-intel` as a local all-A-share review workbench for humans and agents.

- Default scope is `all-a`; theme pools are samples or regression fixtures.
- Keep text short and actionable.
- Keep JSON stable for agent handoff.
- Do not generate buy/sell/hold advice, target prices, or position sizing.

## Workflow

- Read current code and tests before editing.
- Prefer small, direct changes that improve coverage, holdings review, evidence gaps, journal flow, or agent handoff.
- Runtime data is local. Do not read shell token files or expose personal paths, accounts, tokens, or real holdings.
- `init runtime` writes sample data; real review requires importing real runtime files.

## Verify

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

## Push

Commit directly to `main` and push after verification.
