# Requirements

`market-intel` is a local all-A-share post-market review workbench for humans and agents.

## Goal

Help Livermore and the user answer post-close review questions:

- What happened across all A-shares today?
- Which sectors, concepts, and candidates were active or weakening?
- Did current holdings outperform, lag, or move only with the market?
- Which holdings or candidates lack coverage, research evidence, or fresh data?
- What read-only follow-up commands should an agent run next?

## What this does not do

- No brokerage, order routing, or trading execution.
- No real-time quote terminal or news feed.
- No buy/sell/hold recommendations.
- No target prices, stop prices, or position sizing.
- No replacement for `tradegov`, `researchgov`, `companygov`, `marketregime`, `decision-cockpit`, or `tradelab`.

## Position in Livermore workflow

`market-intel` is the post-close market-structure layer:

| Tool | Role |
|------|------|
| `tradegov` | canonical trading facts, positions, trades, snapshots |
| `researchgov` | external reports, blogger posts, news, claims |
| `companygov` | company/security dossiers and evidence gaps |
| `marketregime` | market regime and environment classification |
| `decision-cockpit` | intraday checklist-only decision support |
| `tradelab` | counterfactual trade experiments |
| `market-intel` | all-A post-close market scan, hotspot structure, portfolio relative review, evidence gaps, agent handoff queue |

## Required runtime inputs

Minimum runtime data for real review:

- `runtime/quotes.json`: current all-A or selected quote universe.
- `runtime/holdings.json`: current holdings exported/imported from broker or another trusted source.
- `runtime/a_share_universe.csv`: all-A base universe for coverage context.

Optional but recommended:

- `runtime/research_notes.csv`: reviewed thesis/evidence/invalidation rows.
- `runtime/journal/`: saved daily review history for change tracking.

## Core commands

Read-only first:

```bash
market-intel status runtime --json
market-intel validate runtime --json
market-intel import schema --json
market-intel agent plan --json
market-intel agent briefing --json
market-intel agent next --json
```

Runtime setup and import:

```bash
market-intel init runtime --json
market-intel import quotes quotes.csv --runtime --dry-run --json
market-intel import quotes quotes.csv --runtime --json
market-intel import holdings holdings.csv --runtime --dry-run --json
market-intel import holdings holdings.csv --runtime --json
market-intel import universe a_share_universe.csv --runtime --dry-run --json
market-intel import universe a_share_universe.csv --runtime --json
```

Post-close review:

```bash
market-intel review --no-sync --no-save --json
market-intel review --text
market-intel review --html --output review.html
market-intel serve
```

## Side-effect policy

- Prefer read-only commands before any write.
- `review --text` writes runtime quotes via sync and writes journal by default.
- `review --no-sync --no-save --json` is the safe agent default when runtime already exists.
- `sync quotes` writes runtime quote data.
- `journal save` and `journal note` write journal files.
- `serve` wraps review behavior; refresh can write sync/journal. Use only when a human wants browser workflow.

## JSON contract

All JSON commands must use the envelope:

```json
{
  "ok": true,
  "command": "agent.briefing",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "generated_at": "2026-06-13T17:00:00+08:00",
    "schema_version": "0.1"
  }
}
```

Failure contract:

- `ok=false` for command failure.
- `errors[]` uses `{code,message,detail}`.
- Do not put Python tracebacks in `data`.
- Readiness may be blocked even when `ok=true`; consumers must check `data.state` or `data.readiness.state`.

Stable agent fields are documented in `docs/data-model.md` and emitted in `data.agent_contract.stable_fields`.

## Minimum test requirements

Before handoff or workflow changes:

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

For server or browser workflow changes, include `tests/test_server.py` coverage or equivalent smoke verification.

## Acceptance criteria

A change is acceptable when:

- JSON envelope remains stable.
- Agent commands include `agent_contract` and safe next steps.
- Runtime errors block review instead of producing misleading conclusions.
- Write commands are marked by `state_effect` and skipped by read-only agent flows.
- No output contains buy/sell/hold advice, target price, or position sizing.
- Public docs do not expose personal paths, accounts, holdings, tokens, or private data.
