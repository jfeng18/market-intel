import json
import subprocess
from datetime import date

from market_intel.cli import (
    handle_import_holdings,
    handle_import_quotes,
    handle_import_research,
    handle_import_universe,
    handle_init_runtime,
    handle_status_runtime,
)
from market_intel.core.pool_loader import load_pool
from market_intel.core.runtime import write_runtime_manifest
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
    assert data["next_actions"][0]["done_when"]
    assert data["next_actions"][1]["done_when"]
    assert "data.next_actions[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.readiness.can_run_daily" in data["agent_contract"]["stable_fields"]


def test_status_runtime_all_a_degraded_without_universe(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_status_runtime("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["errors"] == []
    assert any(warning["code"] == "A_SHARE_UNIVERSE_MISSING" for warning in payload["warnings"])
    assert data["readiness"]["state"] == "degraded"
    assert data["freshness"]["is_stale"] is False
    assert data["universe"]["state"] == "missing"
    assert data["universe"]["required"] is True
    action = next(item for item in data["next_actions"] if item["id"] == "export_a_share_universe_patch")
    assert action["command"] == "market-intel pool universe --runtime --dry-run --json"
    assert action["runnable"] is True
    assert "dry-run" in action["done_when"]
    import_action = next(item for item in data["next_actions"] if item["id"] == "import_a_share_universe")
    assert import_action["command"] == "market-intel import universe <a_share_universe.csv> --runtime --dry-run --json"
    assert import_action["runnable"] is False
    assert "dry-run" in import_action["done_when"]


def test_status_runtime_ready_after_universe_import(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    handle_import_universe("examples/a_share_universe.csv.example", use_runtime=True)

    payload = handle_status_runtime("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["warnings"] == []
    assert data["readiness"]["state"] == "ready"
    assert data["universe"]["state"] == "ready"
    assert data["universe"]["record_count"] == 16
    assert data["next_actions"][0]["id"] == "run_daily_report"
    assert data["next_actions"][0]["done_when"]


def test_status_runtime_after_init_runtime_is_sample_degraded(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    init_payload = handle_init_runtime(force=False)

    payload = handle_status_runtime("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert init_payload["data"]["profile"]["mode"] == "sample"
    assert any(warning["code"] == "RUNTIME_SAMPLE_DATA" for warning in payload["warnings"])
    assert data["profile"]["mode"] == "sample"
    assert data["profile"]["sample_datasets"] == ["holdings", "quotes", "research", "universe"]
    assert data["files"]["manifest"]["exists"] is True
    assert data["readiness"]["state"] == "degraded"
    assert data["validation"]["summary"]["warning_count"] == 0
    assert data["universe"]["state"] == "ready"
    assert data["next_actions"][0]["id"] == "import_real_quotes"
    assert data["next_actions"][0]["runnable"] is False
    assert data["next_actions"][0]["command"] == "market-intel import quotes <quotes.csv> --runtime --dry-run --json"
    assert "data.profile.mode" in data["agent_contract"]["stable_fields"]
    assert "data.profile.sample_datasets" in data["agent_contract"]["stable_fields"]


def test_status_runtime_imports_clear_sample_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    handle_import_universe("examples/a_share_universe.csv.example", use_runtime=True)
    handle_import_research("examples/research_notes.csv.example", use_runtime=True)

    payload = handle_status_runtime("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["warnings"] == []
    assert data["profile"]["mode"] == "runtime"
    assert data["profile"]["sample_datasets"] == []
    assert data["readiness"]["state"] == "ready"
    assert data["next_actions"][0]["id"] == "run_daily_report"


def test_status_runtime_theme_pool_does_not_require_universe(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_status_runtime("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["warnings"] == []
    assert data["readiness"]["state"] == "ready"
    assert data["universe"]["required"] is False
    assert all(action["id"] != "import_universe" for action in data["next_actions"])


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

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 6), pool="ai-energy")

    assert status["readiness"]["state"] == "degraded"
    assert status["readiness"]["can_run_daily"] is True
    assert status["freshness"]["is_stale"] is True
    assert status["freshness"]["warnings"][0]["code"] == "QUOTE_DATA_STALE"
    assert status["next_actions"][0]["id"] == "refresh_quotes"
    assert status["next_actions"][0]["runnable"] is False
    assert status["next_actions"][0]["done_when"]


def write_status_runtime_fixture(runtime, trade_date):
    runtime.mkdir(exist_ok=True)
    (runtime / "quotes.json").write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": trade_date,
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


def test_status_runtime_freshness_weekday_fresh(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    write_status_runtime_fixture(runtime, "2026-06-08")

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 8), pool="ai-energy")

    assert status["freshness"]["state"] == "fresh"
    assert status["freshness"]["reason_code"] == "within_threshold"
    assert status["freshness"]["calendar_status"]["is_trading_day"] is True
    assert status["freshness"]["degrades_review_confidence"] is False
    assert "data.freshness.state" in status["agent_contract"]["stable_fields"]


def test_status_runtime_weekend_expected_stale_is_not_warning(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    write_status_runtime_fixture(runtime, "2026-06-18")

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=1, today=date(2026, 6, 21), pool="ai-energy")

    assert status["freshness"]["state"] == "market_closed_expected_stale"
    assert status["freshness"]["reason_code"] == "non_trading_day_expected_stale"
    assert status["freshness"]["calendar_status"]["reason_code"] == "dragon_boat_festival"
    assert status["freshness"]["calendar_status"]["previous_expected_trade_date"] == "2026-06-18"
    assert status["freshness"]["warnings"] == []
    assert status["freshness"]["is_stale"] is False
    assert status["readiness"]["state"] == "ready"
    assert status["next_actions"][0]["id"] == "run_daily_report"


def test_status_runtime_trading_day_stale_degrades(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    write_status_runtime_fixture(runtime, "2026-06-18")

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 22), pool="ai-energy")

    assert status["freshness"]["state"] == "stale_on_trading_day"
    assert status["freshness"]["reason_code"] == "trading_day_stale"
    assert status["freshness"]["warnings"][0]["code"] == "QUOTE_DATA_STALE"
    assert status["freshness"]["degrades_review_confidence"] is True
    assert status["readiness"]["state"] == "degraded"


def test_status_runtime_provider_failed_using_cache(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    write_status_runtime_fixture(runtime, "2026-06-08")
    write_runtime_manifest(
        {
            "mode": "runtime",
            "datasets": {"quotes": "runtime", "holdings": "runtime"},
            "quotes": {"provider_failed_using_cache": True},
        }
    )

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 8), pool="ai-energy")

    assert status["freshness"]["state"] == "provider_failed_using_cache"
    assert status["freshness"]["warnings"][0]["code"] == "PROVIDER_FAILED_USING_CACHE"
    assert status["freshness"]["degrades_review_confidence"] is True
    assert status["readiness"]["state"] == "degraded"


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

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 6), pool="ai-energy")

    assert status["validation"]["errors"] == []
    assert status["freshness"]["errors"][0]["code"] == "QUOTE_TRADE_DATE_MISSING"
    assert status["readiness"]["state"] == "blocked"
    assert status["readiness"]["can_run_daily"] is False
    assert status["readiness"]["error_count"] == 1
    assert status["next_actions"][0]["id"] == "refresh_quotes"
    assert all(action["id"] != "run_daily_report" or not action["runnable"] for action in status["next_actions"])


def test_status_runtime_blocked_when_any_quote_trade_date_is_invalid(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    valid_quote = {
        "symbol": "002837",
        "trade_date": "2026-06-06",
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
    invalid_quote = dict(valid_quote, symbol="002281", trade_date="not-a-date")
    (runtime / "quotes.json").write_text(
        json.dumps({"quotes": [valid_quote, invalid_quote]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    status = build_runtime_status(load_pool("ai-energy"), max_quote_age_days=3, today=date(2026, 6, 6), pool="ai-energy")

    assert status["validation"]["errors"] == []
    assert status["freshness"]["latest_trade_date"] == "2026-06-06"
    assert status["freshness"]["errors"][0]["code"] == "QUOTE_TRADE_DATE_INVALID"
    assert status["freshness"]["errors"][0]["detail"]["symbol"] == "002281"
    assert status["readiness"]["state"] == "blocked"
    assert status["readiness"]["can_run_daily"] is False
    assert status["next_actions"][0]["id"] == "refresh_quotes"


def test_status_runtime_text_renderer(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    payload = handle_status_runtime("all-a", max_quote_age_days=9999)

    text = render_runtime_status_text(payload)

    assert "market-intel status runtime" in text
    assert "运行模式" in text
    assert "正式 | 样例数据 无" in text
    assert "全 A 基础清单" in text
    assert "A_SHARE_UNIVERSE_MISSING" in text
    assert "下一步" in text
    assert "pool universe" in text
    assert "完成:" in text
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
