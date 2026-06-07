import csv
import json
import subprocess

from market_intel.cli import (
    handle_init_runtime,
    handle_import_universe,
    handle_pool_coverage,
    handle_pool_expansion,
    handle_pool_explain,
    handle_pool_list,
    handle_pool_quality,
    handle_pool_research,
    handle_pool_universe,
)
from market_intel.core.text_report import (
    render_pool_coverage_text,
    render_pool_expansion_text,
    render_pool_explain_text,
    render_pool_quality_text,
    render_pool_research_text,
    render_pool_universe_text,
)


def test_pool_list_returns_json_envelope():
    payload = handle_pool_list("ai-energy")
    pools = {pool["id"]: pool for pool in payload["data"]["available_pools"]}

    assert payload["ok"] is True
    assert payload["command"] == "pool.list"
    assert payload["version"] == "0.1.0"
    assert payload["data"]["count"] > 0
    assert set(pools) >= {"all-a", "ai-energy"}
    assert pools["all-a"]["is_default"] is True
    assert pools["all-a"]["coverage_boundary"] == "seed_until_a_share_universe_imported"
    assert pools["ai-energy"]["next_command"] == "market-intel pool coverage --text --pool ai-energy"
    assert "data.available_pools[].coverage_boundary" in payload["data"]["agent_contract"]["stable_fields"]
    assert "data.available_pools[].next_command" in payload["data"]["agent_contract"]["stable_fields"]
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
    assert "data.expansion_queue" in data["agent_contract"]["stable_fields"]
    assert "data.research_queue" in data["agent_contract"]["stable_fields"]
    assert "data.gaps" in data["agent_contract"]["stable_fields"]
    assert data["next_actions"][0]["id"] == "clean_data_quality_queue"
    assert data["next_actions"][0]["command"].startswith("market-intel pool quality ")
    assert data["next_actions"][1]["id"] == "expand_all_a_sources"
    assert data["next_actions"][1]["command"] == "market-intel import universe examples/a_share_universe.csv.example --runtime --dry-run --json"
    assert data["next_actions"][2]["id"] == "import_all_a_sources"
    assert data["next_actions"][2]["command"] == "market-intel import universe examples/a_share_universe.csv.example --runtime --json"
    assert any(action["id"] == "inspect_coverage" for action in data["next_actions"])
    assert data["holdings_source"] == {"provided": False}
    assert data["expansion_queue"] == []
    assert data["data_quality_queue"]
    assert data["data_quality_queue"][0]["flag"] in {"invalid_symbol", "column_shift_suspected", "missing_role"}
    assert data["data_quality_queue"][0]["severity"] == "high"
    assert data["data_quality_queue"][0]["samples"]
    assert data["data_quality_queue"][0]["done_when"]
    assert data["data_quality_queue"][0]["review_command"].startswith("market-intel pool quality ")
    cleanup_action = next(action for action in data["next_actions"] if action["id"] == "clean_data_quality_queue")
    assert cleanup_action["focus"]["flag"] == data["data_quality_queue"][0]["flag"]
    assert cleanup_action["rank"] == 1
    assert "data.data_quality_queue" in data["agent_contract"]["stable_fields"]
    assert "data.data_quality_queue[].samples" in data["agent_contract"]["stable_fields"]


def test_pool_coverage_mock_holdings_reports_personal_coverage():
    payload = handle_pool_coverage("all-a", use_mock=True)
    coverage = payload["data"]["holdings_coverage"]

    assert payload["ok"] is True
    assert coverage["available"] is True
    assert coverage["holding_count"] == 5
    assert coverage["matched_count"] == 5
    assert coverage["unmatched_count"] == 0
    assert coverage["matched_ratio"] == 1
    assert payload["data"]["expansion_queue"] == []
    assert payload["data"]["holdings_source"]["mode"] == "mock"
    assert payload["meta"]["source"] == "pool:all-a"


def test_pool_coverage_reports_a_share_universe(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50;沪深300,listed\n",
        encoding="utf-8",
    )
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "SZ:000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_pool_coverage("all-a", holdings_file=str(holdings_file))
    data = payload["data"]
    coverage = data["holdings_coverage"]

    assert payload["ok"] is True
    assert data["universe"]["available"] is True
    assert data["universe"]["record_count"] == 2
    assert data["universe"]["source_files"] == ["a_share_universe.csv"]
    assert data["universe"]["industry_count"] == 2
    assert data["universe"]["concept_count"] == 4
    assert data["universe"]["index_membership_count"] == 3
    profile = data["universe"]["sector_profile"]
    assert profile["record_count"] == 2
    assert profile["industry_coverage_ratio"] == 1
    assert profile["concept_coverage_ratio"] == 1
    assert profile["index_coverage_ratio"] == 1
    assert profile["top_industries"][0] == {"name": "银行", "count": 1}
    assert profile["missing_field_counts"] == {"industry": 0, "concepts": 0, "index_membership": 0}
    assert profile["missing_field_samples"] == []
    assert coverage["matched_count"] == 1
    assert coverage["matched"][0]["symbol"] == "000001"
    assert coverage["unmatched_count"] == 0
    assert coverage["foundation_matched_count"] == 1
    assert coverage["matched"][0]["coverage_state"] == "foundation"
    assert "a_share_universe_foundation" in coverage["matched"][0]["coverage_state_reasons"]
    assert data["research_queue"][0]["symbol"] == "000001"
    assert data["research_queue"][0]["commands"][0] == "market-intel portfolio explain 000001 --runtime --text"
    assert data["research_queue"][0]["candidate_research_row"]["status"] == "draft"
    assert "foundation_pool_matches" in coverage["coverage_flags"]
    assert any(gap["id"] == "foundation_research_missing" for gap in data["gaps"])
    assert any(action["id"] == "export_research_queue" for action in data["next_actions"])
    assert all(gap["id"] != "all_a_seed_only" for gap in data["gaps"])
    assert "data.universe" in data["agent_contract"]["stable_fields"]
    assert "data.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.universe.sector_profile.top_industries" in data["agent_contract"]["stable_fields"]
    assert str(universe_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_coverage_text_renders_a_share_universe(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    text = render_pool_coverage_text(handle_pool_coverage("all-a"))

    assert "全 A 基础清单" in text
    assert "a_share_universe_v1" in text
    assert "来源文件: a_share_universe.csv" in text
    assert "字段覆盖 | 行业 100.0% | 概念 100.0% | 指数 100.0%" in text
    assert "头部行业: 银行(1)" in text
    assert "000001 平安银行" in text
    assert "研究证据任务" in text


def test_pool_coverage_reports_universe_sector_profile_gaps(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n"
        "600519,贵州茅台,,白酒;消费,,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_pool_coverage("all-a")
    profile = payload["data"]["universe"]["sector_profile"]
    text = render_pool_coverage_text(payload)

    assert payload["ok"] is True
    assert profile["industry_coverage_ratio"] == 0.5
    assert profile["concept_coverage_ratio"] == 0.5
    assert profile["index_coverage_ratio"] == 0.5
    assert profile["missing_field_counts"] == {"industry": 1, "concepts": 1, "index_membership": 1}
    assert profile["coverage_flags"] == ["industry_missing", "concepts_missing", "index_membership_missing"]
    assert profile["missing_field_samples"][0]["symbol"] == "000001"
    assert profile["missing_field_samples"][0]["missing_fields"] == ["concepts"]
    queue = payload["data"]["universe"]["enrichment_queue"]
    assert [item["field"] for item in queue] == ["industry", "concepts", "index_membership"]
    assert queue[0]["label"] == "行业"
    assert queue[0]["severity"] == "high"
    assert queue[0]["missing_count"] == 1
    assert queue[0]["samples"][0]["symbol"] == "600519"
    assert queue[0]["command"] == "market-intel import universe <a_share_universe_patch.csv> --runtime --merge --dry-run --json"
    assert queue[0]["done_when"]
    export_action = next(action for action in payload["data"]["next_actions"] if action["id"] == "export_a_share_universe_patch")
    merge_action = next(action for action in payload["data"]["next_actions"] if action["id"] == "merge_a_share_universe_patch")
    assert export_action["command"] == "market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --json"
    assert merge_action["command"] == "market-intel import universe <a_share_universe_patch.csv> --runtime --merge --dry-run --json"
    assert "data.universe.enrichment_queue" in payload["data"]["agent_contract"]["stable_fields"]
    assert "data.universe.enrichment_queue[].samples" in payload["data"]["agent_contract"]["stable_fields"]
    assert "字段覆盖 | 行业 50.0% | 概念 50.0% | 指数 50.0%" in text
    assert "缺字段 | 行业 1 | 概念 1 | 指数 1" in text
    assert "待补 000001 平安银行 | concepts" in text
    assert "补数队列" in text
    assert "#1 行业 | 缺 1" in text


def test_pool_universe_exports_patch_template(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    output_file = tmp_path / "a_share_universe_patch.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n"
        "600519,贵州茅台,,白酒;消费,,listed\n"
        "000002,万科A,房地产,,沪深300,listed\n"
        "000063,中兴通讯,通信,,沪深300,listed\n"
        "000333,美的集团,家电,,沪深300,listed\n"
        "000651,格力电器,家电,,沪深300,listed\n"
        "002415,海康威视,计算机,,沪深300,listed\n"
        "300750,宁德时代,电力设备,,沪深300,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    dry_run_payload = handle_pool_universe("all-a", dry_run=True)
    limited_payload = handle_pool_universe("all-a", dry_run=True, limit=2)

    assert dry_run_payload["ok"] is True
    assert dry_run_payload["command"] == "pool.universe"
    assert dry_run_payload["data"]["mode"] == "file"
    assert dry_run_payload["data"]["dry_run"] is True
    assert dry_run_payload["data"]["written"] is False
    assert dry_run_payload["data"]["record_count"] == 8
    assert dry_run_payload["data"]["limit"] is None
    assert limited_payload["data"]["record_count"] == 2
    assert limited_payload["data"]["limit"] == 2
    assert dry_run_payload["data"]["fields"] == [
        "symbol",
        "name",
        "industry",
        "concepts",
        "index_membership",
        "listing_status",
        "source",
        "missing_fields",
        "fill_hint",
    ]
    assert dry_run_payload["data"]["rows"] == [
        {
            "symbol": "000001",
            "name": "平安银行",
            "industry": "银行",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "000002",
            "name": "万科A",
            "industry": "房地产",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "000063",
            "name": "中兴通讯",
            "industry": "通信",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "000333",
            "name": "美的集团",
            "industry": "家电",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "000651",
            "name": "格力电器",
            "industry": "家电",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "002415",
            "name": "海康威视",
            "industry": "计算机",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "300750",
            "name": "宁德时代",
            "industry": "电力设备",
            "concepts": "",
            "index_membership": "沪深300",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "concepts",
            "fill_hint": "补概念，多个用分号分隔",
        },
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "",
            "concepts": "白酒;消费",
            "index_membership": "",
            "listing_status": "listed",
            "source": "pool.universe.todo",
            "missing_fields": "industry;index_membership",
            "fill_hint": "补行业；补指数成分，多个用分号分隔",
        },
    ]
    assert dry_run_payload["data"]["next_commands"] == [
        "market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --json"
    ]
    assert any(warning["code"] == "UNIVERSE_PATCH_NEEDS_ENRICHMENT" for warning in dry_run_payload["warnings"])

    write_payload = handle_pool_universe("all-a", output=str(output_file))

    assert write_payload["ok"] is True
    assert write_payload["data"]["written"] is True
    assert write_payload["data"]["next_commands"] == [
        "market-intel import universe a_share_universe_patch.csv --runtime --merge --dry-run --json",
        "market-intel import universe a_share_universe_patch.csv --runtime --merge --json",
        "market-intel pool coverage --runtime --text",
    ]
    with output_file.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == dry_run_payload["data"]["rows"]
    rows[0]["concepts"] = "股份行;金融科技"
    rows[-1]["industry"] = "食品饮料"
    rows[-1]["index_membership"] = "上证50;沪深300"
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=write_payload["data"]["fields"])
        writer.writeheader()
        writer.writerows(rows)
    import_payload = handle_import_universe(str(output_file), use_runtime=True, dry_run=True, merge=True)
    assert import_payload["ok"] is True
    assert import_payload["data"]["coverage_delta"]["write_mode"] == "merge"
    assert str(universe_file) not in json.dumps(write_payload, ensure_ascii=False)


def test_pool_universe_exports_quote_only_candidates_from_quotes(tmp_path):
    quotes_file = tmp_path / "quotes.json"
    quotes_file.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "600000",
                        "name": "浦发银行",
                        "trade_date": "2026-06-06",
                        "last_price": 9.8,
                        "change_pct": 6.8,
                        "amount": 2100000000,
                        "amount_ratio": 2.1,
                        "turnover_rate": 1.8,
                        "amplitude_pct": 5.3,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 0.5,
                        "source": "test",
                    },
                    {
                        "symbol": "300308",
                        "name": "中际旭创",
                        "trade_date": "2026-06-06",
                        "last_price": 168.5,
                        "change_pct": 1.2,
                        "amount": 1200000000,
                        "amount_ratio": 1.1,
                        "turnover_rate": 1.4,
                        "amplitude_pct": 3.2,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 0.3,
                        "source": "test",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = handle_pool_universe("all-a", quotes_file=str(quotes_file), dry_run=True)
    text = render_pool_universe_text(payload)
    row = payload["data"]["rows"][0]

    assert payload["ok"] is True
    assert payload["data"]["record_count"] == 1
    assert payload["data"]["quote_only"]["record_count"] == 1
    assert payload["data"]["quote_only"]["source"] == "quotes_file"
    assert row["symbol"] == "600000"
    assert row["name"] == "浦发银行"
    assert row["source"] == "scan.quote_only"
    assert row["missing_fields"] == "industry;concepts;index_membership"
    assert "quote-only 1" in text
    assert "600000 浦发银行" in text
    assert str(quotes_file) not in json.dumps(payload, ensure_ascii=False)
    assert str(quotes_file) not in text


def test_pool_universe_runtime_does_not_require_runtime_holdings(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,,沪深300,listed,test\n",
        encoding="utf-8",
    )

    payload = handle_pool_universe("all-a", use_runtime=True, dry_run=True)

    assert payload["ok"] is True
    assert payload["command"] == "pool.universe"
    assert payload["data"]["mode"] == "runtime"
    assert payload["data"]["rows"][0]["symbol"] == "000001"
    assert payload["data"]["rows"][0]["concepts"] == ""
    assert str(runtime) not in json.dumps(payload, ensure_ascii=False)


def test_pool_universe_text_renders_patch_guidance(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n"
        "600519,贵州茅台,,白酒;消费,,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    text = render_pool_universe_text(handle_pool_universe("all-a", dry_run=True))

    assert "market-intel pool universe" in text
    assert "行 2" in text
    assert "行业 1 | 概念 1 | 指数 1" in text
    assert "000001 平安银行 | 缺字段: concepts" in text
    assert "600519 贵州茅台 | 缺字段: industry;index_membership" in text
    assert "补概念" in text
    assert "补指数成分" in text
    assert "market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --json" in text
    assert "import universe --merge" in text


def test_pool_research_exports_foundation_research_draft(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n",
        encoding="utf-8",
    )
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    output_file = tmp_path / "research_notes.todo.csv"
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_pool_research("all-a", holdings_file=str(holdings_file), output=str(output_file))

    assert payload["ok"] is True
    assert payload["command"] == "pool.research"
    assert payload["data"]["written"] is True
    assert payload["data"]["record_count"] == 1
    assert payload["data"]["rows"][0]["symbol"] == "000001"
    assert payload["data"]["rows"][0]["status"] == "draft"
    assert payload["data"]["rows"][0]["thesis"] == ""
    assert "market-intel import research research_notes.todo.csv --dry-run --json" in payload["data"]["next_commands"]
    with output_file.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["symbol"] == "000001"
    assert str(output_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_research_text_renders_foundation_draft(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n",
        encoding="utf-8",
    )
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    text = render_pool_research_text(handle_pool_research("all-a", holdings_file=str(holdings_file), dry_run=True))

    assert "market-intel pool research" in text
    assert "000001 平安银行" in text
    assert "核心逻辑、关键证据、证伪风险" in text


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
    assert data["expansion_queue"][0]["symbol"] == "000001"
    assert data["expansion_queue"][0]["candidate_pool_row"]["status"] == "candidate"
    assert data["expansion_queue"][0]["candidate_pool_row"]["code"] == "000001"
    assert data["expansion_queue"][0]["required_fields"] == ["section", "level", "desc"]
    assert any(action["id"] == "review_expansion_queue" for action in data["next_actions"])
    assert data["holdings_source"]["source"] == "holdings_file"
    assert str(holdings_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_expansion_requires_output_or_dry_run(tmp_path):
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_pool_expansion("all-a", holdings_file=str(holdings_file))

    assert payload["ok"] is False
    assert payload["command"] == "pool.expansion"
    assert payload["errors"][0]["code"] == "POOL_EXPANSION_OUTPUT_REQUIRED"


def test_pool_expansion_dry_run_exports_candidate_rows(tmp_path):
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_pool_expansion("all-a", holdings_file=str(holdings_file), dry_run=True)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["record_count"] == 1
    assert data["written"] is False
    assert data["dry_run"] is True
    assert data["rows"][0]["code"] == "000001"
    assert data["rows"][0]["company"] == "平安银行"
    assert "data.rows" in data["agent_contract"]["stable_fields"]
    assert str(holdings_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_expansion_writes_pool_csv(tmp_path):
    holdings_file = tmp_path / "holdings.json"
    output_file = tmp_path / "pool_expansion.csv"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_pool_expansion("all-a", holdings_file=str(holdings_file), output=str(output_file))

    assert payload["ok"] is True
    assert payload["data"]["written"] is True
    assert payload["data"]["record_count"] == 1
    with output_file.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "candidate"
    assert rows[0]["code"] == "000001"
    assert rows[0]["section"] == "待确认 / 持仓补充"
    assert "MARKET_INTEL_POOL_EXTRA_PATHS=" in payload["data"]["next_commands"][0]


def test_pool_expansion_review_blocks_candidate_draft(tmp_path):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,待确认 / 持仓补充,待确认,平安银行,000001,持仓未匹配当前复盘池,source=test\n",
        encoding="utf-8",
    )

    payload = handle_pool_expansion("all-a", review_file=str(expansion_file))
    data = payload["data"]

    assert payload["ok"] is False
    assert data["review_state"] == "blocked"
    assert data["row_count"] == 1
    assert data["blocked_count"] == 1
    assert any(blocker["code"] == "POOL_EXPANSION_STATUS_NOT_READY" for blocker in data["blockers"])
    assert any(blocker["code"] == "POOL_EXPANSION_REQUIRED_FIELDS_PENDING" for blocker in data["blockers"])
    assert str(expansion_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_expansion_review_accepts_reviewed_rows(tmp_path):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "reviewed,P2,银行 / 银行,股份行,平安银行,000001,股份行龙头；用于持仓覆盖补充,source=test\n",
        encoding="utf-8",
    )

    payload = handle_pool_expansion("all-a", review_file=str(expansion_file))
    data = payload["data"]

    assert payload["ok"] is True
    assert data["review_state"] == "ready"
    assert data["ready_count"] == 1
    assert data["ready_rows"][0]["symbol"] == "000001"
    assert data["ready_rows"][0]["normalized"]["primary_layer"] == "其他"
    assert "MARKET_INTEL_POOL_EXTRA_PATHS=" in data["next_commands"][0]
    assert str(expansion_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_expansion_review_keeps_safe_relative_commands(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "data" / "runtime"
    runtime_dir.mkdir(parents=True)
    expansion_file = runtime_dir / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "reviewed,P2,银行 / 银行,股份行,平安银行,000001,股份行龙头；用于持仓覆盖补充,source=test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    payload = handle_pool_expansion("all-a", review_file="data/runtime/pool_expansion.csv")
    commands = payload["data"]["next_commands"]

    assert payload["ok"] is True
    assert "MARKET_INTEL_POOL_EXTRA_PATHS=data/runtime/pool_expansion.csv" in commands[0]
    assert "data/runtime/pool_expansion.csv" in commands[1]


def test_pool_expansion_text_renderer_for_review(tmp_path):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,待确认 / 持仓补充,待确认,平安银行,000001,持仓未匹配当前复盘池,source=test\n",
        encoding="utf-8",
    )

    text = render_pool_expansion_text(handle_pool_expansion("all-a", review_file=str(expansion_file)))

    assert "market-intel pool expansion" in text
    assert "review blocked" in text
    assert "POOL_EXPANSION_STATUS_NOT_READY" in text
    assert "下一步" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_expansion_review_rejects_conflicting_options(tmp_path):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text("status,priority,section,level,company,code,desc,notes\n", encoding="utf-8")

    payload = handle_pool_expansion("all-a", review_file=str(expansion_file), dry_run=True)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "POOL_EXPANSION_REVIEW_CONFLICT"


def test_pool_expansion_overlay_closes_coverage_gap(monkeypatch, tmp_path):
    holdings_file = tmp_path / "holdings.json"
    output_file = tmp_path / "pool_expansion.csv"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    handle_pool_expansion("all-a", holdings_file=str(holdings_file), output=str(output_file))
    monkeypatch.setenv("MARKET_INTEL_POOL_EXTRA_PATHS", str(output_file))

    payload = handle_pool_coverage("all-a", holdings_file=str(holdings_file))
    coverage = payload["data"]["holdings_coverage"]

    assert payload["ok"] is True
    assert coverage["matched_count"] == 1
    assert coverage["unmatched_count"] == 0
    assert coverage["confirmed_count"] == 0
    assert coverage["draft_matched_count"] == 1
    assert coverage["needs_review_count"] == 1
    assert coverage["matched"][0]["coverage_state"] == "draft"
    assert "candidate_status" in coverage["matched"][0]["coverage_state_reasons"]
    assert "extra_pool_overlay" in coverage["matched"][0]["coverage_state_reasons"]
    assert coverage["review_queue"][0]["symbol"] == "000001"
    assert "draft_pool_matches" in coverage["coverage_flags"]
    assert payload["data"]["expansion_queue"] == []
    assert any(gap["id"] == "draft_pool_matches" for gap in payload["data"]["gaps"])
    assert any(action["id"] == "review_draft_pool_matches" for action in payload["data"]["next_actions"])


def test_pool_coverage_text_renders_draft_matches(monkeypatch, tmp_path):
    holdings_file = tmp_path / "holdings.json"
    output_file = tmp_path / "pool_expansion.csv"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    handle_pool_expansion("all-a", holdings_file=str(holdings_file), output=str(output_file))
    monkeypatch.setenv("MARKET_INTEL_POOL_EXTRA_PATHS", str(output_file))

    text = render_pool_coverage_text(handle_pool_coverage("all-a", holdings_file=str(holdings_file)))

    assert "待复核覆盖: 1" in text
    assert "草稿匹配: 1" in text
    assert "draft_pool_matches" in text
    assert "000001 平安银行" in text


def test_pool_coverage_text_renders_expansion_queue(tmp_path):
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps(
            {
                "holdings": [
                    {"symbol": "000001", "name": "平安银行", "quantity": 100},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    text = render_pool_coverage_text(handle_pool_coverage("all-a", holdings_file=str(holdings_file)))

    assert "补池任务" in text
    assert "000001 平安银行" in text
    assert "候选行" in text
    assert "待确认 / 持仓补充" in text


def test_pool_coverage_theme_pool_stays_explicit():
    payload = handle_pool_coverage("ai-energy")
    data = payload["data"]

    assert data["pool"] == "ai-energy"
    assert data["scope"] == "theme"
    assert all(gap["id"] != "all_a_seed_only" for gap in data["gaps"])
    assert data["next_actions"][0]["id"] == "clean_data_quality_queue"
    assert data["next_actions"][0]["command"].endswith("--pool ai-energy")
    assert any(action["id"] == "inspect_coverage" for action in data["next_actions"])


def test_pool_coverage_text_renderer():
    text = render_pool_coverage_text(handle_pool_coverage("all-a"))

    assert "market-intel pool coverage" in text
    assert "持仓覆盖" in text
    assert "覆盖缺口" in text
    assert "数据质量清理队列" in text
    assert "影响" in text
    assert "all_a_seed_only" in text
    assert "交易动作" not in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_quality_focuses_data_quality_flag():
    payload = handle_pool_quality("all-a", "invalid_symbol", limit=3)
    data = payload["data"]
    text = render_pool_quality_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "pool.quality"
    assert payload["warnings"] == []
    assert data["flag"] == "invalid_symbol"
    assert data["found"] is True
    assert data["severity"] == "high"
    assert data["affected_count"] > 0
    assert data["sample_count"] == 3
    assert data["samples"][0]["raw_row"]
    assert data["samples"][0]["source_file"]
    assert data["samples"][0]["raw_company"]
    assert data["samples"][0]["raw_desc"]
    assert data["samples"][0]["fix_hint"]
    assert all("invalid_symbol" in sample["flags"] for sample in data["samples"])
    assert all("missing_role" not in sample["flags"] for sample in data["samples"][:3])
    assert data["suggested_action"]
    assert data["done_when"]
    assert data["next_commands"][0] == "market-intel pool quality invalid_symbol --json"
    assert "data.samples[].raw_row" in data["agent_contract"]["stable_fields"]
    assert "data.samples[].source_file" in data["agent_contract"]["stable_fields"]
    assert "data.samples[].fix_hint" in data["agent_contract"]["stable_fields"]
    assert "market-intel pool quality" in text
    assert "invalid_symbol" in text
    assert "完成标准" in text
    assert "row" in text
    assert "修复提示" in text
    assert "交易动作" not in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_quality_uses_flag_source_rows_for_merged_items():
    payload = handle_pool_quality("all-a", "invalid_symbol", limit=12)
    samples = payload["data"]["samples"]
    tongfu_rows = [sample for sample in samples if sample["symbol"] == "002156"]

    assert tongfu_rows
    assert tongfu_rows[0]["raw_row"] == 238
    assert tongfu_rows[0]["raw_code"] == "通富微电"
    assert "invalid_symbol" in tongfu_rows[0]["flags"]
    assert "missing_role" not in tongfu_rows[0]["flags"]
    assert not any(sample["symbol"] == "002156" and sample["raw_row"] == 33 for sample in samples)


def test_pool_quality_column_shift_suggests_corrected_pool_row():
    payload = handle_pool_quality("all-a", "column_shift_suspected", limit=1)
    data = payload["data"]
    sample = data["samples"][0]
    suggested = sample["suggested_row"]
    text = render_pool_quality_text(payload)

    assert sample["raw_row"] == 238
    assert sample["raw_code"] == "通富微电"
    assert suggested == {
        "status": "pending",
        "priority": "P1",
        "section": "3.3 HBM（史诗级紧缺）",
        "level": "🇨🇳 中国封装",
        "company": "通富微电",
        "code": "002156",
        "desc": "HBM3e 堆叠封装龙头",
        "notes": "fixes_column_shift; source_row=238",
    }
    assert "data.samples[].suggested_row" in data["agent_contract"]["stable_fields"]
    assert "建议: company=通富微电 | code=002156" in text


def test_pool_quality_dry_run_exports_suggested_rows():
    payload = handle_pool_quality("all-a", "column_shift_suspected", limit=2, dry_run=True)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["flag"] == "column_shift_suspected"
    assert data["dry_run"] is True
    assert data["written"] is False
    assert data["record_count"] == 2
    assert data["fields"] == ["status", "priority", "section", "level", "company", "code", "desc", "notes"]
    assert data["rows"][0]["company"] == "通富微电"
    assert data["rows"][0]["code"] == "002156"
    assert data["rows"][0]["notes"] == "fixes_column_shift; source_row=238"
    assert "data.rows" in data["agent_contract"]["stable_fields"]
    assert data["next_commands"][0] == "market-intel pool quality column_shift_suspected --output data/runtime/pool_quality_column_shift_suspected.csv --json"


def test_pool_quality_writes_suggested_rows(tmp_path):
    output_file = tmp_path / "pool_quality_column_shift_suspected.csv"

    payload = handle_pool_quality("all-a", "column_shift_suspected", limit=1, output=str(output_file))
    data = payload["data"]

    assert payload["ok"] is True
    assert data["written"] is True
    assert data["record_count"] == 1
    with output_file.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["company"] == "通富微电"
    assert rows[0]["code"] == "002156"
    assert "pool expansion --review-file pool_quality_column_shift_suspected.csv --json" in data["next_commands"][0]
    assert str(output_file) not in json.dumps(payload, ensure_ascii=False)


def test_pool_quality_export_warns_without_suggested_rows():
    payload = handle_pool_quality("all-a", "missing_role", limit=2, dry_run=True)

    assert payload["ok"] is True
    assert payload["data"]["record_count"] == 0
    assert payload["warnings"][0]["code"] == "DATA_QUALITY_FIX_ROWS_UNAVAILABLE"


def test_pool_quality_unknown_flag_returns_structured_error():
    payload = handle_pool_quality("all-a", "not_a_flag")
    data = payload["data"]

    assert payload["ok"] is False
    assert payload["command"] == "pool.quality"
    assert payload["errors"][0]["code"] == "POOL_QUALITY_FLAG_NOT_FOUND"
    assert data["found"] is False
    assert data["available_flags"]


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


def test_pool_explain_accepts_common_a_share_symbol_formats():
    payload = handle_pool_explain("ai-energy", "300308.SZ")

    assert payload["ok"] is True
    assert payload["data"]["facts"]["symbol"] == "300308"
    assert payload["data"]["facts"]["name"] == "中际旭创"


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


def test_pool_quality_cli_smoke(cli_cmd):
    text_result = subprocess.run(
        cli_cmd("pool", "quality", "invalid_symbol", "--limit", "2", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("pool", "quality", "invalid_symbol", "--limit", "2", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(json_result.stdout)
    assert data["command"] == "pool.quality"
    assert data["data"]["flag"] == "invalid_symbol"
    assert data["data"]["sample_count"] == 2
    assert "market-intel pool quality" in text_result.stdout
    assert "invalid_symbol" in text_result.stdout


def test_pool_quality_export_cli_smoke(cli_cmd):
    text_result = subprocess.run(
        cli_cmd("pool", "quality", "column_shift_suspected", "--limit", "1", "--dry-run", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("pool", "quality", "column_shift_suspected", "--limit", "1", "--dry-run", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["data"]["dry_run"] is True
    assert payload["data"]["rows"][0]["code"] == "002156"
    assert "修正草稿" in text_result.stdout
    assert "002156 通富微电" in text_result.stdout


def test_pool_expansion_cli_smoke(tmp_path, cli_cmd):
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        cli_cmd(
            "pool",
            "expansion",
            "--holdings-file",
            str(holdings_file),
            "--dry-run",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["command"] == "pool.expansion"
    assert payload["data"]["rows"][0]["code"] == "000001"


def test_pool_research_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n",
        encoding="utf-8",
    )
    holdings_file = tmp_path / "holdings.json"
    holdings_file.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    result = subprocess.run(
        cli_cmd(
            "pool",
            "research",
            "--holdings-file",
            str(holdings_file),
            "--dry-run",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["command"] == "pool.research"
    assert payload["data"]["rows"][0]["symbol"] == "000001"
    assert payload["data"]["fields"] == ["symbol", "name", "status", "thesis", "evidence", "invalidation", "updated_at", "source"]


def test_pool_universe_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    text_result = subprocess.run(
        cli_cmd("pool", "universe", "--dry-run", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("pool", "universe", "--dry-run", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    quotes_file = tmp_path / "quotes.json"
    quotes_file.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "600000",
                        "name": "浦发银行",
                        "trade_date": "2026-06-06",
                        "last_price": 9.8,
                        "change_pct": 6.8,
                        "amount": 2100000000,
                        "amount_ratio": 2.1,
                        "turnover_rate": 1.8,
                        "amplitude_pct": 5.3,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 0.5,
                        "source": "test",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quote_result = subprocess.run(
        cli_cmd("pool", "universe", "--quotes-file", str(quotes_file), "--dry-run", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(json_result.stdout)
    quote_payload = json.loads(quote_result.stdout)
    assert payload["command"] == "pool.universe"
    assert payload["data"]["rows"][0]["symbol"] == "000001"
    assert quote_payload["data"]["quote_only"]["record_count"] == 1
    assert any(row["symbol"] == "600000" for row in quote_payload["data"]["rows"])
    assert payload["data"]["fields"] == [
        "symbol",
        "name",
        "industry",
        "concepts",
        "index_membership",
        "listing_status",
        "source",
        "missing_fields",
        "fill_hint",
    ]
    assert "market-intel pool universe" in text_result.stdout
    assert "000001 平安银行" in text_result.stdout
    assert "补概念" in text_result.stdout


def test_pool_expansion_review_cli_smoke(tmp_path, cli_cmd):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,待确认 / 持仓补充,待确认,平安银行,000001,持仓未匹配当前复盘池,source=test\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        cli_cmd(
            "pool",
            "expansion",
            "--review-file",
            str(expansion_file),
            "--json",
        ),
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["command"] == "pool.expansion"
    assert payload["data"]["review_state"] == "blocked"


def test_pool_expansion_review_text_cli_smoke(tmp_path, cli_cmd):
    expansion_file = tmp_path / "pool_expansion.csv"
    expansion_file.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,待确认 / 持仓补充,待确认,平安银行,000001,持仓未匹配当前复盘池,source=test\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        cli_cmd(
            "pool",
            "expansion",
            "--review-file",
            str(expansion_file),
            "--text",
        ),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "market-intel pool expansion" in result.stdout
    assert "review blocked" in result.stdout
    assert "POOL_EXPANSION_STATUS_NOT_READY" in result.stdout
