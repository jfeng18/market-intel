# Review

## Checks

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

## 2026-06-13 Livermore workflow integration pass

Prepared `market-intel` as Livermore's post-close all-A market-structure layer;
added concise requirements/developer/workflow docs and README links. Prior gates:
preflight pass, pytest pass, smoke pass, privacy-scan pass, diff-check pass.
Use `PATH=.venv/bin:$PATH <command>` on hosts whose `python3` is below 3.10.

## 2026-06-13 Runtime bootstrap pass

Bootstrapped selected holding/watchlist runtime without claiming full-A breadth:
runtime templates, `.venv` akshare, tradegov holdings import, selected Tencent
quotes, and merged local universe rows. Runtime was degraded but daily-ready;
research notes still needed real `researchgov` or reviewed import.

## 2026-06-13 Tencent provider pass

Added selected-symbol Tencent quote sync for holdings/watchlist fallback. It is
not full-A breadth. TLS uses `certifi` when available; provider dry-run and full
gates passed after the change.

## 2026-06-13 Provider and Livermore roadmap pass

Organized the roadmap into runtime/provider, holdings, evidence, and briefing
stages. Removed temporary Codex prompt files from the working tree.

Implemented:

- `provider health --json`: small-sample provider readiness; no full-market
  fetch; recommendation and reason codes.
- `sync quotes --provider eastmoney`: direct Eastmoney full-A fetch with
  controlled fields, pagination, retry/sleep, coverage, and diagnostics.
- `sync quotes --provider tencent-batch`: universe-based Tencent fallback with
  request limits, retry, coverage_pct, and degraded coverage status.
- `import holdings --from-tradegov`: read-only `tradegov status-current` source;
  writes only market-intel runtime, never tradegov.
- `data.evidence_gaps`: daily/review/agent handoff for researchgov/companygov or
  reviewed research notes.
- `agent briefing --profile livermore --json`: checklist/review-only market
  structure, portfolio mapping, data quality, evidence gaps, and next queue.

Boundaries:

- Tencent selected and Tencent batch coverage are never presented as full-A.
- Livermore profile is checklist/review only, not a trade signal.
- Guardrails use machine-readable `forbidden_outputs`: `trade_signal`,
  `buy_or_sell_advice`, `price_target`, `position_sizing`.

Verification after roadmap pass:

- `pytest`: 403 passed.
- `make smoke`: pass.
- `make privacy-scan`: pass.
- `git diff --check`: pass.
- `knowledge-gc preflight`: 0 errors / 0 warnings.
