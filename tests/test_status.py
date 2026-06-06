import json
import subprocess
from datetime import date

from market_intel.cli import handle_import_holdings, handle_import_quotes, handle_status_runtime
from market_intel.core.pool_loader import load_pool
from market_intel.core.status import build_runtime_status
from market_intel.core.text_report import render_runtime_status_text


def test_status_runtime_missing_files(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_status_runtime("ai-energy")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "status.runtime"
    assert payload["errors"]
    assert data["readiness"]["state"] == "blocked"
    assert data["readiness"]["can_run_daily"] is False
    assert data["next_actions"][0]["command"] == "market-intel init runtime --json"
    assert data["next_actions"][0]["runnable"] is True


def test_status_runtime_ready_after_csv_import(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_status_runtime("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["errors"] == []
    assert payload["warnings"] == []
    assert data["readiness"]["state"] == "ready"
    assert data["freshness"]["is_stale"] is False
    assert data["next_actions"][0]["id"] == "run_daily_report"


def test_status_runtime_degraded_when_quotes_are_stale(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    (runtime / "quotes.json").write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": "2026-01-01",
                        "last_price": 1,
                        "change_pct": 1,
                        "amount": 1,
                        "amount_ratio": 1,
                        "turnover_rate": 1,
                        "amplitude_pct": 1,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    status = build_runtime_status(load_pool(), max_quote_age_days=3, today=date(2026, 6, 6))

    assert status["readiness"]["state"] == "degraded"
    assert status["readiness"]["can_run_daily"] is True
    assert status["freshness"]["is_stale"] is True
    assert status["freshness"]["warnings"][0]["code"] == "QUOTE_DATA_STALE"
    assert status["next_actions"][0]["id"] == "refresh_quotes"
    assert status["next_actions"][0]["runnable"] is False


def test_status_runtime_blocked_when_freshness_has_errors(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    (runtime / "quotes.json").write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": "",
                        "last_price": 1,
                        "change_pct": 1,
                        "amount": 1,
                        "amount_ratio": 1,
                        "turnover_rate": 1,
                        "amplitude_pct": 1,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    status = build_runtime_status(load_pool(), max_quote_age_days=3, today=date(2026, 6, 6))

    assert status["validation"]["errors"] == []
    assert status["freshness"]["errors"][0]["code"] == "QUOTE_TRADE_DATE_MISSING"
    assert status["readiness"]["state"] == "blocked"
    assert status["readiness"]["can_run_daily"] is False
    assert status["readiness"]["error_count"] == 1
    assert status["next_actions"][0]["id"] == "refresh_quotes"
    assert all(action["id"] != "run_daily_report" or not action["runnable"] for action in status["next_actions"])


def test_status_runtime_text_renderer(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    payload = handle_status_runtime("ai-energy", max_quote_age_days=9999)

    text = render_runtime_status_text(payload)

    assert "market-intel status runtime" in text
    assert "下一步" in text
    assert "daily --runtime" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_status_runtime_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    result = subprocess.run(
        cli_cmd(
            "status",
            "runtime",
            "--max-quote-age-days",
            "9999",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel status runtime" in result.stdout
    assert "状态" in result.stdout
