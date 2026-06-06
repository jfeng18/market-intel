import json
import subprocess

from market_intel.cli import handle_init_runtime, handle_pool_coverage, handle_pool_explain, handle_pool_list
from market_intel.core.text_report import render_pool_coverage_text, render_pool_explain_text


def test_pool_list_returns_json_envelope():
    payload = handle_pool_list("ai-energy")

    assert payload["ok"] is True
    assert payload["command"] == "pool.list"
    assert payload["version"] == "0.1.0"
    assert payload["data"]["count"] > 0
    assert {pool["id"] for pool in payload["data"]["available_pools"]} >= {"all-a", "ai-energy"}
    assert payload["errors"] == []
    assert payload["meta"]["schema_version"] == "0.1"


def test_all_a_pool_list_uses_seed_universe():
    payload = handle_pool_list("all-a")

    assert payload["ok"] is True
    assert payload["data"]["pool"] == "all-a"
    assert payload["data"]["items"][0]["raw"]["pool_scope"] == "all_a_seed"


def test_pool_coverage_all_a_reports_seed_boundaries():
    payload = handle_pool_coverage("all-a")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "pool.coverage"
    assert data["pool"] == "all-a"
    assert data["scope"] == "all_a_seed"
    assert data["status"] == "seed"
    assert data["counts"]["cn_a"] > 0
    assert data["market_distribution"]
    assert data["layer_distribution"]
    assert data["cn_a_board_distribution"]
    assert data["holdings_coverage"]["available"] is False
    assert any(gap["id"] == "all_a_seed_only" for gap in data["gaps"])
    assert "data.holdings_coverage" in data["agent_contract"]["stable_fields"]
    assert "data.gaps" in data["agent_contract"]["stable_fields"]
    assert data["next_actions"][0]["command"] == "market-intel pool coverage --text"
    assert data["holdings_source"] == {"provided": False}


def test_pool_coverage_mock_holdings_reports_personal_coverage():
    payload = handle_pool_coverage("all-a", use_mock=True)
    coverage = payload["data"]["holdings_coverage"]

    assert payload["ok"] is True
    assert coverage["available"] is True
    assert coverage["holding_count"] == 5
    assert coverage["matched_count"] == 5
    assert coverage["unmatched_count"] == 0
    assert coverage["matched_ratio"] == 1
    assert payload["data"]["holdings_source"]["mode"] == "mock"
    assert payload["meta"]["source"] == "pool:all-a"


def test_pool_coverage_file_holdings_reports_unmatched_gap(tmp_path):
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps(
            {
                "holdings": [
                    {"symbol": "000001", "name": "平安银行", "quantity": 100},
                    {"symbol": "002281", "name": "光迅科技", "quantity": 100},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = handle_pool_coverage("all-a", holdings_file=str(holdings_file))
    data = payload["data"]
    coverage = data["holdings_coverage"]

    assert payload["ok"] is True
    assert coverage["holding_count"] == 2
    assert coverage["matched_count"] == 1
    assert coverage["unmatched_count"] == 1
    assert coverage["unmatched"][0]["symbol"] == "000001"
    assert any(gap["id"] == "holding_coverage_gap" for gap in data["gaps"])
    assert data["holdings_source"]["source"] == "holdings_file"
    assert str(holdings_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_coverage_theme_pool_stays_explicit():
    payload = handle_pool_coverage("ai-energy")
    data = payload["data"]

    assert data["pool"] == "ai-energy"
    assert data["scope"] == "theme"
    assert all(gap["id"] != "all_a_seed_only" for gap in data["gaps"])
    assert data["next_actions"][0]["command"] == "market-intel pool coverage --text --pool ai-energy"


def test_pool_coverage_text_renderer():
    text = render_pool_coverage_text(handle_pool_coverage("all-a"))

    assert "market-intel pool coverage" in text
    assert "持仓覆盖" in text
    assert "覆盖缺口" in text
    assert "all_a_seed_only" in text
    assert "交易动作" not in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_explain_acceptance_sample_shape():
    payload = handle_pool_explain("ai-energy", "002837")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "pool.explain"
    assert data["facts"]["symbol"] == "002837"
    assert data["facts"]["name"] == "英维克"
    assert data["facts"]["primary_layer"] == "电力"
    assert data["facts"]["primary_sub_sector"] == "液冷"
    assert "facts" in data
    assert "signals" in data
    assert "risks" in data
    assert "questions" in data
    assert "data_quality_flags" in data
    assert "exposures" in data


def test_pool_explain_not_found_returns_error_envelope():
    payload = handle_pool_explain("ai-energy", "NOPE")

    assert payload["ok"] is False
    assert payload["data"] == {}
    assert payload["errors"][0]["code"] == "POOL_ITEM_NOT_FOUND"


def test_pool_explain_text_renderer():
    payload = handle_pool_explain("ai-energy", "002281")
    text = render_pool_explain_text(payload)

    assert "market-intel pool explain" in text
    assert "光迅科技" in text
    assert "链路暴露" in text
    assert "CPO / 硅光" in text
    assert "交易动作" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_explain_runtime_context(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_pool_explain("ai-energy", "002281", use_runtime=True)
    context = payload["data"]["runtime_context"]

    assert payload["ok"] is True
    assert context["quote"]["symbol"] == "002281"
    assert context["holding"]["symbol"] == "002281"


def test_pool_explain_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "pool",
            "explain",
            "002837",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel pool explain" in result.stdout
    assert "英维克" in result.stdout
    assert "主链路" in result.stdout


def test_pool_coverage_cli_smoke(cli_cmd):
    text_result = subprocess.run(
        cli_cmd("pool", "coverage", "--mock", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("pool", "coverage", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel pool coverage" in text_result.stdout
    assert "持仓覆盖" in text_result.stdout
    assert "覆盖率 100.0%" in text_result.stdout
    assert "覆盖缺口" in text_result.stdout
    assert json.loads(json_result.stdout)["command"] == "pool.coverage"
