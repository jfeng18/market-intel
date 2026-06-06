import json
import subprocess

from market_intel.cli import handle_brief, handle_holdings_impact, handle_hotspots, handle_init_runtime
from market_intel.core.text_report import render_brief_text


def test_hotspots_accepts_quotes_file(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": "2026-06-06",
                        "last_price": 1,
                        "change_pct": 6,
                        "amount": 100,
                        "amount_ratio": 2,
                        "turnover_rate": 3,
                        "amplitude_pct": 4,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 1,
                        "source": "test",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = handle_hotspots("ai-energy", use_mock=False, quotes_file=str(path))

    assert payload["ok"] is True
    assert payload["data"]["mode"] == "file"
    assert payload["data"]["quote_count"] == 1


def test_holdings_impact_accepts_holdings_file(tmp_path):
    path = tmp_path / "holdings.json"
    path.write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_holdings_impact("ai-energy", use_mock=False, holdings_file=str(path))

    assert payload["ok"] is True
    assert payload["data"]["mode"] == "file"
    assert payload["data"]["holding_count"] == 1


def test_brief_mock_shape():
    payload = handle_brief("ai-energy", use_mock=True, top=3)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "brief"
    assert data["summary"]
    assert len(data["top_hotspots"]) == 3
    assert data["holding_impact"]["holding_count"] == 5
    assert data["watchlist"]
    assert data["risk_flags"]
    assert data["questions"]
    assert data["guardrails"]


def test_brief_requires_sources():
    payload = handle_brief("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "BRIEF_SOURCE_REQUIRED"


def test_brief_text_renderer_is_human_readable():
    payload = handle_brief("ai-energy", use_mock=True, top=3)
    text = render_brief_text(payload)

    assert "market-intel brief" in text
    assert "总览" in text
    assert "热点" in text
    assert "持仓暴露" in text
    assert "观察清单" in text
    assert "待验证问题" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_brief_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "brief",
            "--mock",
            "--top",
            "2",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel brief" in result.stdout
    assert "热点" in result.stdout
    assert "持仓暴露" in result.stdout


def test_runtime_init_and_brief(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))

    init_payload = handle_init_runtime(force=False)
    assert init_payload["ok"] is True
    assert init_payload["data"]["files"][0]["status"] == "written"
    assert (runtime / "a_share_universe.csv").exists()
    assert str(runtime) not in str(init_payload)

    kept_payload = handle_init_runtime(force=False)
    assert kept_payload["data"]["files"][0]["status"] == "kept"
    assert str(runtime) not in str(kept_payload)

    brief_payload = handle_brief("ai-energy", use_mock=False, use_runtime=True, top=2)
    assert brief_payload["ok"] is True
    assert brief_payload["data"]["mode"] == "runtime"
    assert len(brief_payload["data"]["top_hotspots"]) == 2


def test_runtime_missing_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "missing-runtime"))

    payload = handle_brief("ai-energy", use_mock=False, use_runtime=True)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "RUNTIME_NOT_INITIALIZED"
