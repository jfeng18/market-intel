# Livermore Workflow Integration

This document defines how Livermore should use `market-intel` inside the existing A-share workflow.

## Role

`market-intel` is the post-close market review layer. It answers market-structure questions after the close:

- What were the strongest and weakest areas today?
- Did holdings move with their sectors or against them?
- Which holdings have missing coverage or research evidence?
- What should Livermore inspect next, using read-only commands first?

It does **not** replace existing canonical tools.

## Tool boundaries

| Tool | Use first when... | Writes canonical facts? |
|------|-------------------|-------------------------|
| `tradegov` | trades, positions, snapshots, validation, daily trade reports | yes |
| `researchgov` | news, reports, blogger posts, claims, validation signals | yes |
| `companygov` | company/security dossier, thesis gaps, company evidence | yes |
| `marketregime` | market regime and environment classification | no trading facts |
| `decision-cockpit` | intraday checklist/cool-down/brief | no trading facts |
| `tradelab` | counterfactual trade experiments | no |
| `market-intel` | all-A post-close scan, hotspot structure, portfolio relative review, evidence queue | local runtime/journal only |

## Gate usage

For post-close review requests, Livermore should still run the workspace gate first:

```bash
python3 <workspace>/scripts/cli_workflow_gate.py '<task>' --json
```

If the gate requires `tradegov`, call `tradegov` before final interpretation:

```bash
cd <tradegov-repo> && python3 -m tradegov.cli status-current --json
```

For market-intel repository changes or handoff work, also run:

```bash
cd <knowledge-gc-repo> && python3 -m knowledge_gc.cli preflight <market-intel-repo> --json
```

## Safe post-close read flow

Default read-only sequence:

```bash
cd <market-intel-repo>
PYTHONPATH=src python3 -m market_intel.cli status runtime --json
PYTHONPATH=src python3 -m market_intel.cli validate runtime --json
PYTHONPATH=src python3 -m market_intel.cli agent briefing --json
PYTHONPATH=src python3 -m market_intel.cli agent next --json
PYTHONPATH=src python3 -m market_intel.cli review --no-sync --no-save --json
```

Interpretation rule:

- If `data.readiness.state` or `data.state` is `blocked`, do not use market-intel conclusions except the blocker itself.
- If `degraded`, use output only with explicit caveats about stale/missing data.
- If ready, read `top_hotspots`, `portfolio_review`, `coverage_context`, `risk_register`, and `command_queue`.

## Write-enabled human review flow

Use only when the user wants a real local market-intel archive or browser workbench:

```bash
cd <market-intel-repo>
PYTHONPATH=src python3 -m market_intel.cli sync quotes --json
PYTHONPATH=src python3 -m market_intel.cli review --text
PYTHONPATH=src python3 -m market_intel.cli serve
```

Notes:

- `review --text` syncs quotes and saves journal by default.
- `serve` can trigger sync/journal writes on refresh.
- Do not use write-enabled flow silently when the user only asks for a quick read.

## Runtime bootstrapping

When runtime is missing, inspect schema first:

```bash
market-intel import schema --json
```

Then use dry-run before writes:

```bash
market-intel import quotes quotes.csv --runtime --dry-run --json
market-intel import holdings holdings.csv --runtime --dry-run --json
market-intel import universe a_share_universe.csv --runtime --dry-run --json
```

After dry-run succeeds:

```bash
market-intel import quotes quotes.csv --runtime --json
market-intel import holdings holdings.csv --runtime --json
market-intel import universe a_share_universe.csv --runtime --json
market-intel validate runtime --json
```

Holdings source priority for Livermore interpretation remains:

1. broker / `SESSION-STATE.md` / `tradegov` current snapshot;
2. market-intel imported holdings as local review input;
3. examples/mock data never as real holdings.

## How to route output

Use market-intel output as a routing layer:

- Hotspot/sector changes → compare with `marketregime` and news.
- Holding underperformance/outperformance → inspect `tradegov` position and company dossier.
- Missing research evidence → add or inspect `researchgov` claim/report.
- Missing company coverage → inspect or update `companygov` dossier.
- Counterfactual questions → use `tradelab`, not market-intel.
- Intraday decisions → use `decision-cockpit`, not market-intel.

## Livermore response rules

When reporting market-intel output to the user:

- Say whether runtime was ready, degraded, or blocked.
- Separate market structure from trading action.
- Do not turn hotspot scores into buy/sell advice.
- Explain whether each holding is strong because of its own evidence, sector beta, or index recovery.
- List follow-up evidence checks rather than recommendations.

Suggested wording:

> market-intel shows this as a post-close structure signal, not a trade signal. I will use it to decide what to inspect next, not to issue buy/sell instructions.

## Completion checklist for integration

Before declaring market-intel integrated into Livermore workflow:

```bash
cd <market-intel-repo>
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
cd <knowledge-gc-repo> && python3 -m knowledge_gc.cli preflight <market-intel-repo> --json
```

Then run one real or intentionally mocked post-close flow and record the result in `docs/review.md`.
