# AGENTS.md

## Direction

Build `market-intel` as a local all-A-share review workbench for humans and agents.

- Default scope is `all-a`; theme pools are samples or regression fixtures.
- Keep text short and actionable.
- Keep JSON stable for agent handoff.
- Do not generate buy/sell/hold advice, target prices, or position sizing.

## Entry Point Decision Tree

| Goal | Command | Side Effects |
|------|---------|-------------|
| Read-only inspection | `agent briefing --json` | None |
| Automated execution | `agent run` | Read-only; skips writes and unknown |
| Full human review | `review --text` | **Writes: sync + journal** |
| Browser dashboard | `serve` | **Writes: sync + journal per refresh** |

**Warning:** `review` triggers `sync quotes` (network + disk write) and `journal save` (disk write) by default. Use `--no-sync --no-save` for read-only. Serve mode wraps `review` with the same side effects on each refresh. In serve mode, read-only commands get clickable execute buttons; write commands are blocked (403).

## Key Commands

| Command | state_effect |
|---------|-------------|
| `review --text` | writes_runtime_journal |
| `review --no-sync --no-save --text` | read_only |
| `sync quotes` | writes_runtime |
| `sync quotes --dry-run` | read_only |
| `pool add/remove` | writes_runtime |
| `pool add/remove --dry-run` | read_only |
| `init runtime` | writes_runtime |
| `import quotes/holdings/universe/research` | writes_runtime |
| `import * --dry-run` | read_only |
| `import schema` | read_only |
| `journal save/note` | writes_journal |
| `agent briefing/run/plan/next` | read_only |
| `scan/daily/brief/watchlist/map/hotspots/focus/dashboard` | read_only |
| `pool list/coverage/explain/quality` | read_only |
| `status/validate runtime` | read_only |

## Agent Handoff

- `data.agent_contract.stable_fields`: guaranteed JSON paths.
- `data.agent_contract.read_order`: suggested consumption order (review command only).
- `data.agent_contract.boundary`: what the tool does NOT do.
- `data.command_queue[].state_effect`: read_only / writes_runtime / writes_journal / unknown.
- `data.command_queue[].runnable`: false if command has placeholder args.
- `data.changes`: delta vs prior journal entry (day/week/month window).

## Command Safety

`command_state_effect` classifies commands. Unrecognized commands return `unknown` — `agent run` and the serve `/api/run` endpoint both refuse to auto-execute them. New write commands must be registered in `agent.py:command_state_effect()`.

## Data Features

- Holdings CSV supports optional `cost_price` field (aliases: 成本价, 买入均价, 持仓成本). When present, HTML report calculates P&L%.
- CSV import auto-detects encoding: tries utf-8-sig → gbk → gb18030 in order.
- `sync quotes` and `review` print progress messages in text/serve mode; `--json` mode is silent.

## Workflow

- Read current code and tests before editing.
- Prefer small, direct changes.
- Runtime data is local. Do not expose personal paths, accounts, tokens, or real holdings.
- `init runtime` writes sample data; real review requires `sync quotes` and importing real holdings.

## Verify

```bash
PYTHONPATH=src python3 -m pytest -q   # or: make ci
make smoke
make privacy-scan
git diff --check
```
