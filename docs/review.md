# Review

Short review log. Keep details in commits, tests, and command output.

## Checks

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

## Done

- 2026-06-13: prepared the all-A workflow docs and README links.
- 2026-06-13: bootstrapped selected holdings/watchlist runtime without claiming
  full-A breadth.
- 2026-06-13: added selected-symbol Tencent quote fallback.
- 2026-06-13: added provider health, Eastmoney full-A sync, Tencent batch
  fallback, tradegov holdings import, evidence gaps, and Livermore briefing.
- 2026-06-21: added trading-calendar-aware freshness semantics for
  `status runtime`, `daily --runtime`, and `agent briefing`.
- Boundaries: selected coverage is never full-A; Livermore output is review-only;
  guardrails forbid trade signals, advice, targets, and position sizing.

## 2026-06-21 Usage review

Verdict: keep the core architecture. Improve daily usability, degraded-data
semantics, and agent handoff. Scope remains all-A; selected pools are fixtures.

Observed:

- `agent briefing --profile livermore --json`: `ok=true`,
  `state=degraded_with_history`, trade date `2026-06-17`.
- Full-A providers failed in this run; selected-symbol Tencent fallback was
  ready.
- Runtime showed `QUOTE_DATA_STALE` on `2026-06-21`, a non-trading day.
- Knowledge checks had no blocking errors.

Next:

1. P1: Tighten pool quality cleanup.
   Start with `column_shift_suspected`, then `missing_role`, then missing
   concepts/index membership. Dry-run output must show source rows, suggested
   fixes, and whether an overlay can safely apply them.
2. P1: Add compact agent summary.
   Keep full `agent briefing` unchanged. Add a compact mode or command with
   state, trade date, freshness summary, top 3 hotspots, portfolio positioning,
   data quality summary, 3-5 review questions, read-only next commands, and
   guardrails.
3. P2: Improve provider degradation semantics.
   Separate full-A status, selected-symbol status, cache status, and recommended
   mode. Never present selected-symbol data as full-market coverage.
4. P2: Explain `SESSION-STATE` inline in
   `docs/LIVERMORE_WORKFLOW_INTEGRATION.md`.

Acceptance gates for the next Codex pass:

- New or changed JSON fields are covered by contract tests.
- Weekend expected-stale, trading-day stale, and provider-fallback cases have
  separate fixtures.
- Compact summary output stays review-only and includes machine-readable
  guardrails.
- Pool-quality dry-runs are read-only and show source row, proposed fix, and
  overlay/apply safety.
- `PYTHONPATH=src python3 -m pytest -q`, `make smoke`, `make privacy-scan`, and
  `git diff --check` pass before handoff.

Guardrails:

- No advice, target prices, sizing, personal paths, tokens, accounts, or real
  holdings in docs.
