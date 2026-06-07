import json
import subprocess

from market_intel.cli import handle_scan
from market_intel.core.models import Quote
from market_intel.core.scan import build_market_breadth
from market_intel.core.text_report import render_scan_text


def test_scan_mock_defaults_to_all_a_seed():
    payload = handle_scan("all-a", use_mock=True, top=3, candidate_top=4)
    data = payload["data"]
    text = render_scan_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "scan"
    assert payload["warnings"] == []
    assert data["pool"] == "all-a"
    assert data["scan_mode"] == "pool_chain_seed"
    assert data["market_breadth"]["state"] == "broad_strength"
    assert data["market_breadth"]["confidence"] == "reference"
    assert "种子池" in data["market_breadth"]["sample_note"]
    assert data["market_breadth"]["up_count"] == 9
    assert data["market_breadth"]["active_group_count"] == 3
    assert data["sector_groups"]
    assert data["candidate_securities"]
    assert data["candidate_securities"][0]["why_now"]
    assert data["candidate_securities"][0]["checklist"]
    assert data["candidate_securities"][0]["ranking_breakdown"]["total_score"] == data["candidate_securities"][0]["review_score"]
    assert data["candidate_securities"][0]["ranking_breakdown"]["factors"]
    assert data["candidate_securities"][0]["review_focus"]["ranking_breakdown"]["summary"]
    assert data["candidate_queue"]["summary"]
    assert data["candidate_queue"]["buckets"]["review_now"]["count"] >= 1
    assert data["candidate_queue"]["buckets"]["data_first"]["count"] >= 1
    assert data["candidate_queue"]["buckets"]["review_now"]["items"][0]["next_command"].startswith("market-intel pool explain")
    assert data["candidate_securities"][0]["review_focus"]["headline"]
    assert data["candidate_securities"][0]["review_focus"]["classification"]["primary_context"]
    assert data["candidate_securities"][0]["review_focus"]["coverage"]["state"] == data["candidate_securities"][0]["coverage_state"]
    assert data["candidate_securities"][0]["review_focus"]["next_command"] == data["candidate_securities"][0]["commands"][0]
    assert data["candidate_securities"][0]["commands"][0].startswith("market-intel pool explain")
    assert data["coverage_context"]["available"] is True
    assert data["coverage_context"]["pool"] == "all-a"
    assert data["coverage_context"]["top_data_quality_queue"]
    patch_action = next(action for action in data["next_actions"] if action["id"] == "export_a_share_universe_patch")
    assert patch_action["command"] == "market-intel pool universe --mock --dry-run --json"
    assert "补丁草稿" in patch_action["done_when"]
    assert "data.sector_groups" in data["agent_contract"]["stable_fields"]
    assert "data.market_breadth" in data["agent_contract"]["stable_fields"]
    assert "data.market_breadth.confidence" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_securities[].ranking_breakdown" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_queue" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_securities[].review_focus" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_securities[].review_focus.ranking_breakdown" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_securities[].review_focus.classification" in data["agent_contract"]["stable_fields"]
    assert "data.candidate_securities[].why_now" in data["agent_contract"]["stable_fields"]
    assert "market-intel scan" in text
    assert "市场宽度" in text
    assert "普遍走强" in text
    assert "置信 参考" in text
    assert "候选队列" in text
    assert "排序:" in text
    assert "板块扫描" in text
    assert "候选复盘" in text
    assert "复核焦点" in text
    assert "market-intel pool universe --mock --dry-run --json" in text
    assert "已导入行业" not in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_scan_uses_a_share_universe_groups(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50;沪深300,listed\n",
        encoding="utf-8",
    )
    quotes_file = tmp_path / "quotes.json"
    quotes_file.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "000001",
                        "trade_date": "2026-06-06",
                        "last_price": 12.3,
                        "change_pct": 4.2,
                        "amount": 1000000000,
                        "amount_ratio": 1.8,
                        "turnover_rate": 2.1,
                        "amplitude_pct": 5.0,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 0.8,
                        "source": "test",
                    },
                    {
                        "symbol": "600519",
                        "trade_date": "2026-06-06",
                        "last_price": 1600,
                        "change_pct": 2.1,
                        "amount": 2000000000,
                        "amount_ratio": 1.3,
                        "turnover_rate": 1.2,
                        "amplitude_pct": 3.0,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 0.4,
                        "source": "test",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_scan("all-a", use_mock=False, quotes_file=str(quotes_file), top=5, candidate_top=3)
    data = payload["data"]
    text = render_scan_text(payload)

    assert payload["ok"] is True
    assert data["scan_mode"] == "all_a_universe"
    assert data["matched_quote_count"] == 2
    assert data["market_breadth"]["state"] == "thin_strength"
    assert data["market_breadth"]["confidence"] == "reference"
    assert data["market_breadth"]["up_count"] == 2
    assert data["market_breadth"]["active_count"] == 1
    assert any(group["group_type"] == "industry" and group["name"] == "银行" for group in data["sector_groups"])
    assert any(group["group_type"] == "index" and group["name"] == "沪深300" for group in data["sector_groups"])
    first = data["candidate_securities"][0]
    assert first["symbol"] == "000001"
    assert first["ranking_breakdown"]["penalty_score"] >= 0
    assert any(factor["id"] == "universe_context" for factor in first["ranking_breakdown"]["factors"])
    assert data["candidate_queue"]["buckets"]["data_first"]["count"] >= 1
    assert first["coverage_state"] == "foundation"
    assert "foundation_pool_match" in first["risk_flags"]
    assert first["universe_context"]["available"] is True
    assert first["universe_context"]["dimension_count"] == 3
    assert first["universe_context"]["context_count"] == 5
    assert first["universe_context"]["score_bonus"] > 0
    assert first["review_focus"]["universe_context"]["score_bonus"] == first["universe_context"]["score_bonus"]
    assert first["research_status"]["status"] == "missing"
    assert first["review_focus"]["classification"]["industry"] == "银行"
    assert "股份行" in first["review_focus"]["classification"]["concepts"]
    assert "沪深300" in first["review_focus"]["classification"]["index_membership"]
    assert first["review_focus"]["coverage"]["missing_research_fields"] == ["thesis", "evidence", "invalidation"]
    assert first["review_focus"]["next_command"] == first["commands"][0]
    assert first["commands"][1] == "market-intel pool research --runtime --dry-run --json"
    assert "data.candidate_securities[].universe_context" in data["agent_contract"]["stable_fields"]
    assert "全 A 归属" in first["why_now"]
    assert "全 A:" in text
    assert "全 A 基础清单" in text
    assert "行业银行" in text
    assert str(universe_file) not in json.dumps(payload, ensure_ascii=False)
    assert str(quotes_file) not in json.dumps(payload, ensure_ascii=False)


def test_scan_keeps_universe_context_for_non_leader_members(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,标的一,电子,半导体;国产替代,沪深300,listed\n"
        "000002,标的二,电子,半导体;国产替代,沪深300,listed\n"
        "000003,标的三,电子,半导体;国产替代,沪深300,listed\n"
        "000004,标的四,电子,半导体;国产替代,沪深300,listed\n"
        "000005,标的五,电子,半导体;国产替代,沪深300,listed\n"
        "000006,标的六,电子,半导体;国产替代,沪深300,listed\n",
        encoding="utf-8",
    )
    quotes = []
    for index, symbol in enumerate(["000001", "000002", "000003", "000004", "000005", "000006"], start=1):
        quotes.append(
            {
                "symbol": symbol,
                "trade_date": "2026-06-06",
                "last_price": 10 + index,
                "change_pct": 7 - index * 0.5,
                "amount": 100000000 * index,
                "amount_ratio": 1.8,
                "turnover_rate": 2.0,
                "amplitude_pct": 4.0,
                "is_limit_up": False,
                "is_stage_high": symbol == "000006",
                "intraday_fade_pct": 0.3,
                "source": "test",
            }
        )
    quotes_file = tmp_path / "quotes.json"
    quotes_file.write_text(json.dumps({"quotes": quotes}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_scan("all-a", use_mock=False, quotes_file=str(quotes_file), top=5, candidate_top=6)
    data = payload["data"]
    by_symbol = {item["symbol"]: item for item in data["candidate_securities"]}
    sixth = by_symbol["000006"]

    assert payload["ok"] is True
    assert sixth["universe_context"]["industry"] == "电子"
    assert sixth["universe_context"]["context_count"] == 4
    assert sixth["sector_contexts"][0]["member_count"] == 6
    assert "全 A 归属" in sixth["why_now"]


def test_scan_all_a_keeps_quote_only_candidates_without_universe(tmp_path):
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

    payload = handle_scan("all-a", use_mock=False, quotes_file=str(quotes_file), top=5, candidate_top=5)
    data = payload["data"]
    by_symbol = {item["symbol"]: item for item in data["candidate_securities"]}
    quote_only = by_symbol["600000"]
    text = render_scan_text(payload)

    assert payload["ok"] is True
    assert data["matched_quote_count"] == 2
    assert data["unmatched_quote_count"] == 0
    assert quote_only["name"] == "浦发银行"
    assert quote_only["coverage_state"] == "quote_only"
    assert quote_only["coverage_state_reasons"] == ["quote_not_in_universe"]
    assert "quote_only_candidate" in quote_only["risk_flags"]
    assert quote_only["commands"] == ["market-intel pool universe --quotes-file <quotes.json> --dry-run --json"]
    assert quote_only["review_focus"]["coverage"]["state"] == "quote_only"
    assert quote_only["review_focus"]["next_command"] == quote_only["commands"][0]
    assert data["sources"]["quotes"]["source"] == "quotes_file"
    assert data["candidate_queue"]["buckets"]["data_first"]["items"][0]["symbol"] == "600000"
    assert data["candidate_queue"]["buckets"]["data_first"]["items"][0]["next_command"] == quote_only["commands"][0]
    assert "浦发银行" in text
    assert "行情待覆盖" in text
    assert "market-intel pool universe --quotes-file <quotes.json> --dry-run --json" in text
    assert str(quotes_file) not in json.dumps(payload, ensure_ascii=False)
    assert str(quotes_file) not in text


def test_scan_breadth_classifies_weak_market(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行,沪深300,listed\n"
        "600519,贵州茅台,食品饮料,白酒,沪深300,listed\n",
        encoding="utf-8",
    )
    quotes_file = tmp_path / "quotes.json"
    quotes_file.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "000001",
                        "trade_date": "2026-06-06",
                        "last_price": 12.3,
                        "change_pct": -2.2,
                        "amount": 100000000,
                        "amount_ratio": 0.8,
                        "turnover_rate": 1.0,
                        "amplitude_pct": 2.0,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 1.8,
                        "source": "test",
                    },
                    {
                        "symbol": "600519",
                        "trade_date": "2026-06-06",
                        "last_price": 1600,
                        "change_pct": -1.1,
                        "amount": 200000000,
                        "amount_ratio": 0.9,
                        "turnover_rate": 0.7,
                        "amplitude_pct": 1.8,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 1.0,
                        "source": "test",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_scan("all-a", use_mock=False, quotes_file=str(quotes_file), top=5, candidate_top=3)
    breadth = payload["data"]["market_breadth"]
    text = render_scan_text(payload)

    assert payload["ok"] is True
    assert breadth["state"] == "weak_market"
    assert breadth["confidence"] == "reference"
    assert breadth["up_count"] == 0
    assert breadth["active_count"] == 0
    assert "弱势整理" in breadth["summary"]
    assert "弱势整理" in text


def test_market_breadth_confidence_high_for_large_all_a_sample():
    quotes = [
        Quote(
            symbol="%06d" % index,
            trade_date="2026-06-06",
            last_price=10.0,
            change_pct=1.2,
            amount=100000000,
            amount_ratio=1.1,
            turnover_rate=1.0,
            amplitude_pct=2.0,
            is_limit_up=False,
            is_stage_high=False,
            intraday_fade_pct=0.2,
            source="test",
        )
        for index in range(1, 201)
    ]

    breadth = build_market_breadth(
        quotes,
        [(None, quote) for quote in quotes],
        [],
        "all_a_universe",
    )

    assert breadth["confidence"] == "high"
    assert "主判断" in breadth["sample_note"]


def test_scan_requires_quote_source_has_text_guidance():
    payload = handle_scan("all-a", use_mock=False)
    text = render_scan_text(payload)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "SCAN_QUOTE_SOURCE_REQUIRED"
    assert payload["data"]["next_actions"][0]["command"] == "market-intel import quotes <quotes.csv> --runtime --json"
    assert "数据未就绪" in text
    assert "market-intel import quotes" in text


def test_scan_runtime_requires_quotes_not_holdings(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    quotes_file = runtime_dir / "quotes.json"
    quotes_file.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": "2026-06-06",
                        "last_price": 38.42,
                        "change_pct": 7.2,
                        "amount": 1850000000,
                        "amount_ratio": 2.8,
                        "turnover_rate": 8.6,
                        "amplitude_pct": 9.8,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 1.1,
                        "source": "test",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))

    payload = handle_scan("all-a", use_mock=False, use_runtime=True)

    assert payload["ok"] is True
    assert payload["data"]["mode"] == "runtime"
    assert payload["data"]["sources"]["quotes"]["source"] == "runtime_quotes"
    assert payload["data"]["sources"]["holdings"]["provided"] is False


def test_scan_cli_smoke(cli_cmd):
    text_result = subprocess.run(
        cli_cmd("scan", "--mock", "--top", "3", "--candidate-top", "4", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("scan", "--mock", "--top", "3", "--candidate-top", "4", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel scan" in text_result.stdout
    assert "候选复盘" in text_result.stdout
    assert json.loads(json_result.stdout)["command"] == "scan"
