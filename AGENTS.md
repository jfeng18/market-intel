# AGENTS.md

## Direction

Build `market-intel` as a local all-A-share review workbench for humans and agents.

- Default scope is `all-a`; theme pools are samples or regression fixtures.
- Keep text short and actionable.
- Keep JSON stable for agent handoff.
- Do not generate buy/sell/hold advice, target prices, or position sizing.

## Key Commands

| Command | Purpose |
|---------|---------|
| `review --text` | One-command daily review (sync + report + change tracking + journal save) |
| `review --html` | Generate self-contained HTML visual report |
| `sync quotes` | Fetch all A-share quotes from akshare (东方财富) |
| `pool add/remove` | Manage runtime universe without editing CSV |
| `dashboard --text` | Full agent workspace |
| `agent run` | Auto-execute read-only command queue |

## Workflow

- Read current code and tests before editing.
- Prefer small, direct changes that improve coverage, holdings review, evidence gaps, journal flow, or agent handoff.
- Runtime data is local. Do not read shell token files or expose personal paths, accounts, tokens, or real holdings.
- `init runtime` writes sample data; real review requires `sync quotes` or importing real runtime files.

## Agent Handoff

- `data.agent_contract.stable_fields`: guaranteed JSON paths.
- `data.agent_contract.read_order`: suggested consumption order.
- `data.agent_contract.boundary`: what the tool does NOT do.
- `data.changes`: delta vs prior journal entry (day/week/month window).
- `data.command_queue`: runnable follow-up commands with `state_effect`.

## Verify

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

## Push

Commit directly to `main` and push after verification.
