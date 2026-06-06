import json
import subprocess

from market_intel.cli import handle_init_runtime, handle_map
from market_intel.core.fixtures import load_mock_holdings, load_mock_quotes
from market_intel.core.map_view import build_market_map
from market_intel.core.pool_loader import load_pool
from market_intel.core.text_report import render_market_map_text


def test_market_map_groups_hotspots_and_holdings_by_layer():
    report = build_market_map(load_pool(), load_mock_quotes(), load_mock_holdings(), top=2)

    assert report["layer_count"] >= 5
    assert report["layers"][0]["layer"] == "算力"
    assert report["strongest_hotspot"]
    assert report["risk_flags"]
    assert any(layer["holding_count"] > 0 for layer in report["layers"])
    assert all(len(layer["top_hotspots"]) <= 2 for layer in report["layers"])


def test_map_cli_requires_source():
    payload = handle_map("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "MAP_SOURCE_REQUIRED"


def test_map_accepts_file_sources(tmp_path):
    quotes_path = tmp_path / "quotes.json"
    holdings_path = tmp_path / "holdings.json"
    quotes_path.write_text(
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
    holdings_path.write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_map(
        "ai-energy",
        use_mock=False,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )

    assert payload["ok"] is True
    assert payload["command"] == "map"
    assert payload["data"]["mode"] == "file"
    assert payload["data"]["holding_count"] == 1


def test_map_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_map("ai-energy", use_mock=False, use_runtime=True, top=2)

    assert payload["ok"] is True
    assert payload["command"] == "map"
    assert payload["data"]["mode"] == "runtime"
    assert payload["data"]["layers"]


def test_map_text_renderer():
    payload = handle_map("ai-energy", use_mock=True, top=2)
    text = render_market_map_text(payload)

    assert "market-intel map" in text
    assert "总览" in text
    assert "链路" in text
    assert "风险汇总" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_map_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "map",
            "--mock",
            "--top",
            "2",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel map" in result.stdout
    assert "链路" in result.stdout
