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
| Automated execution | `agent run` | Read-only; skips writes |
| Full human review | `review --text` | **Writes: sync + journal** |
| Browser dashboard | `serve` | **Writes: sync + journal per refresh** |

**Warning:** `review` triggers `sync quotes` (network + disk write) and `journal save` (disk write) by default. Use `--no-sync --no-save` for read-only.

## Key Commands

| Command | state_effect |
|---------|-------------|
| `review --text` | writes_runtime_journal |
| `review --no-sync --no-save --text` | read_only |
| `sync quotes` | writes_runtime |
| `sync quotes --dry-run` | read_only |
| `pool add/remove` | writes_runtime |
| `agent briefing/run` | read_only |
| `journal save/note` | writes_journal |

## Agent Handoff

- `data.agent_contract.stable_fields`: guaranteed JSON paths.
- `data.agent_contract.read_order`: suggested consumption order.
- `data.agent_contract.boundary`: what the tool does NOT do.
- `data.command_queue[].state_effect`: read_only / writes_runtime / writes_journal.
- `data.command_queue[].runnable`: false if command has placeholder args.
- `data.changes`: delta vs prior journal entry (day/week/month window).

## Command Safety

`command_state_effect` classifies commands. Unrecognized commands return `unknown` — agent run refuses to auto-execute them. New commands must be registered in `agent.py:command_state_effect()`.

## Workflow

- Read current code and tests before editing.
- Prefer small, direct changes.
- Runtime data is local. Do not expose personal paths, accounts, tokens, or real holdings.
- `init runtime` writes sample data; real review requires `sync quotes` or importing real runtime files.

## Verify

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
