import json
import shlex
import subprocess

from market_intel.cli import (
    handle_agent_briefing,
    handle_agent_next,
    handle_agent_plan,
    handle_agent_run,
    handle_init_runtime,
    handle_dashboard,
    handle_import_holdings,
    handle_import_quotes,
    handle_import_research,
    handle_import_universe,
    handle_journal_note,
    handle_journal_save,
    dashboard_action_summary,
    dashboard_journal_gate,
    run_agent_read_command,
)
from market_intel.core.agent import build_agent_plan
from market_intel.core.text_report import render_agent_briefing_text, render_agent_next_text, render_agent_plan_text, render_agent_run_text, render_dashboard_text


def import_runtime_examples(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)


def dashboard_text_max_non_command_line_length(text):
    lines = []
    for line in text.splitlines():
        if "market-intel " in line:
            continue
        lines.append(len(line))
    return max(lines, default=0)


def import_runtime_with_many_holdings(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    holdings_path = tmp_path / "many_holdings.csv"
    holdings_path.write_text(
        "证券代码,证券名称,持仓数量\n"
        "002261,拓维信息,100\n"
        "002281,光迅科技,100\n"
        "300308,中际旭创,100\n"
        "300604,长川科技,100\n"
        "002837,英维克,100\n"
        "300499,高澜股份,100\n"
        "301018,申菱环境,100\n",
        encoding="utf-8",
    )
    return handle_import_holdings(str(holdings_path), use_runtime=True)


def write_changed_quotes(tmp_path):
    path = tmp_path / "quotes.changed.csv"
    path.write_text(
        "\n".join(
            [
                "证券代码,证券名称,交易日期,最新价,涨跌幅,成交额,量比,换手率,振幅,涨停,阶段新高,日内回落",
                "002837,英维克,2026-06-07,39.10,9.8%,20.1亿,4.1,7.3%,10.2%,是,是,0.5%",
                "300499,高澜股份,2026-06-07,24.50,10.1%,15.0亿,3.8,8.1%,11.0%,是,是,0.4%",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def import_foundation_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    universe_path = tmp_path / "a_share_universe.csv"
    universe_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n",
        encoding="utf-8",
    )
    quotes_path = tmp_path / "quotes.csv"
    quotes_path.write_text(
        "证券代码,证券名称,交易日期,最新价,涨跌幅,成交额,量比,换手率,振幅,涨停,阶段新高,日内回落\n"
        "000001,平安银行,2026-06-07,11.20,1.2%,9.8亿,1.4,0.8%,2.1%,否,否,0.4%\n",
        encoding="utf-8",
    )
    holdings_path = tmp_path / "holdings.csv"
    holdings_path.write_text(
        "证券代码,证券名称,持仓数量\n"
        "000001,平安银行,100\n",
        encoding="utf-8",
    )
    handle_import_universe(str(universe_path), use_runtime=True)
    handle_import_quotes(str(quotes_path), use_runtime=True)
    handle_import_holdings(str(holdings_path), use_runtime=True)


def import_foundation_runtime_without_holding(monkeypatch, tmp_path):
    import_foundation_runtime(monkeypatch, tmp_path)
    holdings_path = tmp_path / "empty_holdings.csv"
    holdings_path.write_text(
        "证券代码,证券名称,持仓数量\n"
        "002837,英维克,100\n",
        encoding="utf-8",
    )
    handle_import_holdings(str(holdings_path), use_runtime=True)


def import_foundation_research(tmp_path):
    research_path = tmp_path / "research_notes.csv"
    research_path.write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险,更新日期,来源\n"
        "000001,平安银行,reviewed,股份行资产质量和息差变化是复核主线,关注营收结构、资产质量、拨备和同业对比,若息差继续承压且资产质量恶化则证伪,2026-06-07,test\n",
        encoding="utf-8",
    )
    handle_import_research(str(research_path), use_runtime=True)


def test_agent_plan_blocked_when_runtime_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_agent_plan("ai-energy")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "agent.plan"
    assert data["state"] == "blocked"
    assert data["runtime"]["readiness"]["can_run_daily"] is False
    assert data["runtime"]["validation"]["errors"]
    assert data["runtime"]["validation"]["errors"][0]["code"] == "MISSING_RUNTIME_FILE"
    assert data["runtime"]["validation"]["errors"][0]["path"]
    assert data["execution"]["next_runnable_command"] == "market-intel status runtime --json"
    assert data["steps"][0]["id"] == "inspect_runtime_status"
    assert "data.runtime.validation" in data["agent_contract"]["stable_fields"]


def test_agent_briefing_blocked_when_runtime_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_agent_briefing("ai-energy")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "agent.briefing"
    assert data["state"] == "blocked"
    assert data["daily"]["available"] is False
    assert data["runtime"]["validation"]["errors"]
    assert data["runtime"]["validation"]["errors"][0]["code"] == "MISSING_RUNTIME_FILE"
    assert data["command_queue"][0]["command"] == "market-intel status runtime --json"
    assert data["command_queue"][2]["command"] == "market-intel import schema --json"
    assert data["command_queue"][2]["mutates_state"] is False
    assert data["command_queue"][2]["state_effect"] == "read_only"
    assert data["command_queue"][2]["purpose"]
    assert data["command_queue"][2]["output_use"]
    assert data["command_queue"][2]["done_when"]
    assert data["review_focus"][0]["id"] == "runtime_blocked"
    assert data["review_checklist"][0]["id"] == "runtime_ready_check"
    assert data["next_commands"][0] == "market-intel status runtime --json"
    assert data["journal_prompt"]["available"] is False
    assert data["journal_prompt"]["sections"][0]["id"] == "runtime_blocker"
    assert data["journal_prompt"]["sections"][0]["note_command"].startswith("market-intel journal note")
    assert "data.runtime.validation" in data["agent_contract"]["stable_fields"]

    text = render_agent_briefing_text(payload)
    assert "runtime 错误" in text
    assert "留档提示" in text
    assert "MISSING_RUNTIME_FILE" in text


def test_agent_run_blocked_runs_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_agent_run("ai-energy", max_steps=5)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "agent.run"
    assert data["state"] == "blocked_review"
    assert data["source_briefing"]["payload_command"] == "agent.briefing"
    assert [item["payload_command"] for item in data["results"]] == [
        "status.runtime",
        "validate.runtime",
        "import.schema",
    ]
    assert data["results"][0]["ok"] is True
    assert data["results"][1]["ok"] is False
    assert data["results"][1]["errors"]
    assert data["review_digest"]["available"] is False
    assert data["review_digest"]["data_quality"]["errors"]
    assert data["review_digest"]["next_steps"][0]["step_type"] == "data_quality"
    assert data["manual_followups"] == []
    assert "data.review_digest.next_steps" in data["agent_contract"]["stable_fields"]
    assert "data.results[].observations" in data["agent_contract"]["stable_fields"]


def test_agent_plan_ready_without_journal(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_plan("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["state"] == "ready_needs_archive"
    assert data["runtime"]["readiness"]["state"] == "ready"
    assert data["journal"]["entry_count"] == 0
    assert data["journal"]["can_compare"] is False
    assert data["execution"]["next_runnable_command"] == "market-intel agent briefing --text"
    assert "data.execution.next_runnable_command" in data["agent_contract"]["stable_fields"]


def test_agent_plan_all_a_prompts_universe_patch(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_plan("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["state"] == "degraded"
    assert data["runtime"]["universe"]["state"] == "missing"
    assert data["execution"]["next_runnable_command"] == "market-intel pool universe --runtime --dry-run --json"
    assert any(step["id"] == "export_a_share_universe_patch" for step in data["steps"])
    assert "data.runtime.universe" in data["agent_contract"]["stable_fields"]


def test_agent_plan_universe_patch_preserves_non_default_pool():
    data = {
        "readiness": {"state": "degraded", "can_run_daily": True},
        "freshness": {"is_stale": False},
        "universe": {"required": True, "state": "missing"},
        "validation": {"summary": {}},
    }

    payload = build_agent_plan("ai-energy", data, {"entries": []}, max_quote_age_days=3)

    assert payload["execution"]["next_runnable_command"] == (
        "market-intel pool universe --runtime --dry-run --json --pool ai-energy"
    )


def test_agent_plan_all_a_ready_after_universe_import(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    handle_import_universe("examples/a_share_universe.csv.example", use_runtime=True)

    payload = handle_agent_plan("all-a", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["runtime"]["universe"]["state"] == "ready"
    assert data["state"] == "ready_needs_archive"
    assert all(step["id"] != "import_universe" for step in data["steps"])


def test_agent_next_focuses_holding_outside_default_cards(monkeypatch, tmp_path):
    imported = import_runtime_with_many_holdings(monkeypatch, tmp_path)

    payload = handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5, symbol="301018")
    data = payload["data"]
    card = data["security_cards"]["cards"][0]
    focus_commands = [item["json_command"] for item in data["focus_chain"]]

    assert imported["data"]["record_count"] == 7
    assert payload["ok"] is True
    assert data["state"] == "continue_reading"
    assert data["symbol"] == "301018"
    assert len(data["security_cards"]["cards"]) == 1
    assert card["symbol"] == "301018"
    assert card["next_json_command"] == "market-intel portfolio explain 301018 --runtime --json"
    assert "market-intel pool explain 301018 --runtime --json" in card["commands"]
    assert focus_commands[:2] == [
        "market-intel portfolio explain 301018 --runtime --json --pool ai-energy",
        "market-intel pool explain 301018 --runtime --json --pool ai-energy",
    ]


def test_agent_next_focuses_pool_symbol_outside_holdings(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5, symbol="002261")
    data = payload["data"]
    card = data["security_cards"]["cards"][0]
    focus_commands = [item["json_command"] for item in data["focus_chain"]]

    assert payload["ok"] is True
    assert data["state"] == "continue_reading"
    assert data["symbol"] == "002261"
    assert len(data["security_cards"]["cards"]) == 1
    assert card["symbol"] == "002261"
    assert card["coverage_state"] == "confirmed"
    assert "not_in_runtime_holdings" in card["coverage_state_reasons"]
    assert card["next_json_command"] == "market-intel pool explain 002261 --runtime --json"
    assert data["review_handoff"]["next_read"][0]["json_command"] == "market-intel pool explain 002261 --runtime --json"
    assert focus_commands == ["market-intel pool explain 002261 --runtime --json --pool ai-energy"]
    assert any("不在当前 runtime 持仓" in gap for gap in card["open_gaps"])


def test_agent_next_surfaces_foundation_symbol_outside_holdings(monkeypatch, tmp_path):
    import_foundation_runtime_without_holding(monkeypatch, tmp_path)

    payload = handle_agent_next("all-a", max_quote_age_days=9999, max_steps=5, symbol="000001")
    data = payload["data"]
    card = data["security_cards"]["cards"][0]
    focus_commands = [item["json_command"] for item in data["focus_chain"]]

    assert payload["ok"] is True
    assert data["state"] == "continue_reading"
    assert card["symbol"] == "000001"
    assert card["coverage_state"] == "foundation"
    assert "a_share_universe_foundation" in card["coverage_state_reasons"]
    assert "not_in_runtime_holdings" in card["coverage_state_reasons"]
    assert card["research_status"]["status"] == "missing"
    assert card["research_workflow"][0]["json_command"].startswith("market-intel pool research")
    assert any(step["json_command"].startswith("market-intel import research") and "--dry-run" in step["json_command"] for step in card["research_workflow"])
    assert card["next_json_command"] == "market-intel pool explain 000001 --runtime --json"
    assert focus_commands == ["market-intel pool explain 000001 --runtime --json"]
    assert any("全 A 基础清单只说明存在" in gap for gap in card["open_gaps"])
    assert any("不在当前 runtime 持仓" in gap for gap in card["open_gaps"])


def test_agent_briefing_ready_without_journal(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_briefing("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["state"] == "ready_needs_history"
    assert data["daily"]["available"] is True
    assert data["daily"]["top_hotspots"]
    assert data["daily"]["watchlist"]["top_items"]
    assert data["daily"]["watchlist"]["top_items"][0]["commands"]
    assert data["daily"]["portfolio_review"]["top_items"]
    assert data["daily"]["coverage_context"]["available"] is True
    assert data["daily"]["coverage_context"]["pool"] == "ai-energy"
    assert data["daily"]["coverage_context"]["universe"]["available"] is False
    assert data["market_scan"]["available"] is True
    assert data["market_scan"]["sector_groups"]
    assert data["market_scan"]["candidate_securities"]
    assert data["market_scan"]["candidate_queue"]["summary"]
    assert data["market_scan"]["candidate_securities"][0]["why_now"]
    assert data["market_scan"]["candidate_securities"][0]["ranking_breakdown"]["total_score"]
    assert data["market_scan"]["candidate_securities"][0]["review_focus"]["headline"]
    assert data["market_scan"]["candidate_securities"][0]["review_focus"]["coverage"]["state"]
    assert "data.daily.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.daily.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.sector_groups" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.candidate_queue" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.candidate_securities[].ranking_breakdown" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.candidate_securities[].why_now" in data["agent_contract"]["stable_fields"]
    assert data["daily"]["portfolio_review"]["top_items"][0]["commands"][0].startswith("market-intel portfolio explain")
    exposure = data["daily"]["portfolio_exposure"]
    assert exposure["has_concentration"] is True
    assert exposure["group_count"] >= 1
    assert exposure["affected_holding_count"] >= 2
    assert exposure["repeated_exposures"] or exposure["repeated_overlap_groups"]
    first_group = (exposure["repeated_exposures"] or exposure["repeated_overlap_groups"])[0]
    assert first_group["holdings"]
    assert first_group["holdings"][0]["symbol"]
    assert exposure["questions"]
    assert data["daily"]["risk_register"]
    first_risk = data["daily"]["risk_register"][0]
    assert first_risk["severity"] in {"high", "medium", "low"}
    assert first_risk["affected_symbols"]
    assert first_risk["commands"]
    assert first_risk["done_when"]
    assert data["daily"]["review_path"]
    assert data["daily"]["review_path"][0]["commands"]
    assert data["daily"]["review_path"][0]["done_when"]
    assert data["daily"]["review_path"][-1]["id"] == "archive_review"
    assert data["daily"]["review_path"][-1]["runnable"] is True
    assert data["daily"]["security_risk_profile"]
    first_profile = data["daily"]["security_risk_profile"][0]
    assert first_profile["symbol"]
    assert first_profile["risk_ids"]
    assert first_profile["related_risks"]
    assert first_profile["commands"]
    assert first_profile["note_prerequisite"]["archive_runnable"] is True
    assert data["daily"]["validation"]["warnings"] == []
    assert data["daily"]["validation"]["warning_codes"] == []
    assert data["daily"]["review_tasks"]
    assert data["daily"]["review_tasks"][0]["commands"]
    assert data["daily"]["review_tasks"][0]["note_command"].startswith("market-intel journal note --section")
    assert data["daily"]["review_tasks"][0]["note_prerequisite"]["requires_journal_entry"] is True
    assert data["daily"]["review_tasks"][0]["note_prerequisite"]["archive_command"] == "market-intel journal save --runtime --json"
    assert data["daily"]["review_tasks"][0]["note_prerequisite"]["archive_runnable"] is True
    assert data["daily"]["security_review_queue"]
    assert data["daily"]["security_review_queue"][0]["commands"]
    assert data["daily"]["security_review_queue"][0]["note_command"].startswith("market-intel journal note --section security_review")
    assert data["daily"]["security_review_queue"][0]["note_prerequisite"]["requires_journal_entry"] is True
    assert data["daily"]["security_review_queue"][0]["note_prerequisite"]["archive_runnable"] is True
    assert data["daily"]["journal_actions"]
    assert data["daily"]["journal_actions"][0]["command"].startswith("market-intel journal save")
    assert data["daily"]["command_queue"]
    daily_archive = next(item for item in data["daily"]["command_queue"] if item["command"] == "market-intel journal save --runtime --json")
    daily_note = next(item for item in data["daily"]["command_queue"] if item["command"].startswith("market-intel journal note --section"))
    assert daily_archive["runnable"] is True
    assert daily_archive["state_effect"] == "writes_journal"
    assert daily_note["runnable"] is True
    assert daily_note["requires_prior_command"] == daily_archive["command"]
    assert daily_note["run_after_rank"] == daily_archive["rank"]
    assert data["security_review_queue"]
    assert data["security_review_queue"][0]["rank"] == 1
    assert data["security_review_queue"][0]["symbol"]
    assert data["security_review_queue"][0]["reasons"]
    assert data["security_review_queue"][0]["commands"]
    assert any("portfolio_review" in item["sources"] for item in data["security_review_queue"])
    assert any("watchlist" in item["sources"] for item in data["security_review_queue"])
    assert data["journal_prompt"]["available"] is True
    assert len(data["journal_prompt"]["sections"]) == 5
    assert {section["id"] for section in data["journal_prompt"]["sections"]} == {
        "data_quality",
        "market_structure",
        "portfolio_exposure",
        "security_review",
        "current_change",
    }
    assert all(section["note_command"].startswith("market-intel journal note --section") for section in data["journal_prompt"]["sections"])
    assert data["history"]["can_compare"] is False
    assert any(item["id"] == "market_scan_review" for item in data["review_focus"])
    assert any(item["id"] == "watchlist_review" for item in data["review_focus"])
    assert any(item["id"] == "archive_daily" for item in data["review_focus"])
    assert any(item["id"] == "market_scan_context_review" for item in data["review_checklist"])
    assert any(item["id"] == "hotspot_resonance_review" for item in data["review_checklist"])
    assert any(item["id"] == "watchlist_context_review" for item in data["review_checklist"])
    assert any(item["id"] == "portfolio_risk_review" for item in data["review_checklist"])
    assert any(item["id"] == "archive_for_history" for item in data["review_checklist"])
    assert all(item["done_when"] for item in data["review_checklist"])
    assert data["command_queue"]
    assert data["command_queue"][0]["command"] == data["next_commands"][0]
    assert data["command_queue"][0]["json_command"].endswith("--json")
    assert data["command_queue"][0]["read_fields"]
    assert data["command_queue"][0]["purpose"]
    assert data["command_queue"][0]["input_context"]
    assert data["command_queue"][0]["output_use"]
    assert data["command_queue"][0]["done_when"]
    assert data["command_queue"][1]["command"] == "market-intel pool coverage --runtime --text"
    assert data["command_queue"][1]["json_command"] == "market-intel pool coverage --runtime --json"
    assert data["command_queue"][1]["state_effect"] == "read_only"
    assert "data.universe.sector_profile" in data["command_queue"][1]["read_fields"]
    scan_command = next(item for item in data["command_queue"] if item["command"] == "market-intel scan --runtime --text")
    assert scan_command["json_command"] == "market-intel scan --runtime --json"
    assert scan_command["state_effect"] == "read_only"
    assert "data.sector_groups" in scan_command["read_fields"]
    archive_command = next(item for item in data["command_queue"] if item["command"] == "market-intel journal save --runtime --json")
    assert archive_command["mutates_state"] is True
    assert archive_command["state_effect"] == "writes_journal"
    assert archive_command["done_when"]
    assert "market-intel pool coverage --runtime --text" in data["next_commands"]
    assert "market-intel scan --runtime --text" in data["next_commands"]
    assert any("portfolio explain" in command for command in data["next_commands"])
    assert any("pool explain" in command for command in data["next_commands"])
    assert "data.review_focus" in data["agent_contract"]["stable_fields"]
    assert "data.review_checklist" in data["agent_contract"]["stable_fields"]
    assert "data.daily.portfolio_exposure" in data["agent_contract"]["stable_fields"]
    assert "data.daily.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.daily.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.daily.risk_register" in data["agent_contract"]["stable_fields"]
    assert "data.daily.risk_register[].affected_symbols" in data["agent_contract"]["stable_fields"]
    assert "data.daily.review_path" in data["agent_contract"]["stable_fields"]
    assert "data.daily.review_path[].runnable" in data["agent_contract"]["stable_fields"]
    assert "data.daily.validation.warnings" in data["agent_contract"]["stable_fields"]
    assert "data.daily.review_tasks" in data["agent_contract"]["stable_fields"]
    assert "data.daily.review_tasks[].note_command" in data["agent_contract"]["stable_fields"]
    assert "data.daily.review_tasks[].note_prerequisite" in data["agent_contract"]["stable_fields"]
    assert "data.daily.security_review_queue" in data["agent_contract"]["stable_fields"]
    assert "data.daily.security_review_queue[].note_command" in data["agent_contract"]["stable_fields"]
    assert "data.daily.security_review_queue[].note_prerequisite" in data["agent_contract"]["stable_fields"]
    assert "data.daily.security_risk_profile" in data["agent_contract"]["stable_fields"]
    assert "data.daily.security_risk_profile[].risk_ids" in data["agent_contract"]["stable_fields"]
    assert "data.daily.journal_actions" in data["agent_contract"]["stable_fields"]
    assert "data.daily.command_queue" in data["agent_contract"]["stable_fields"]
    assert "data.daily.command_queue[].runnable" in data["agent_contract"]["stable_fields"]
    assert "data.journal_prompt" in data["agent_contract"]["stable_fields"]
    assert "data.journal_prompt.sections[].note_command" in data["agent_contract"]["stable_fields"]
    assert "data.command_queue" in data["agent_contract"]["stable_fields"]
    assert "data.command_queue[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.command_queue[].state_effect" in data["agent_contract"]["stable_fields"]
    assert "data.security_review_queue" in data["agent_contract"]["stable_fields"]
    assert "data.history.latest_entry.latest_note" in data["agent_contract"]["stable_fields"]


def test_agent_briefing_surfaces_all_a_sector_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    universe_path = tmp_path / "a_share_universe.csv"
    universe_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n",
        encoding="utf-8",
    )
    quotes_path = tmp_path / "quotes.csv"
    quotes_path.write_text(
        "证券代码,证券名称,交易日期,最新价,涨跌幅,成交额,量比,换手率,振幅,涨停,阶段新高,日内回落\n"
        "000001,平安银行,2026-06-07,11.20,1.2%,9.8亿,1.4,0.8%,2.1%,否,否,0.4%\n",
        encoding="utf-8",
    )
    holdings_path = tmp_path / "holdings.csv"
    holdings_path.write_text(
        "证券代码,证券名称,持仓数量\n"
        "000001,平安银行,100\n",
        encoding="utf-8",
    )
    handle_import_universe(str(universe_path), use_runtime=True)
    handle_import_quotes(str(quotes_path), use_runtime=True)
    handle_import_holdings(str(holdings_path), use_runtime=True)

    payload = handle_agent_briefing("all-a", max_quote_age_days=9999)
    coverage = payload["data"]["daily"]["coverage_context"]
    profile = coverage["universe"]["sector_profile"]

    assert payload["ok"] is True
    assert coverage["pool"] == "all-a"
    assert coverage["universe"]["available"] is True
    assert profile["industry_coverage_ratio"] == 1
    assert profile["concept_coverage_ratio"] == 0
    assert profile["index_coverage_ratio"] == 1
    assert profile["top_industries"] == [{"name": "银行", "count": 1}]
    assert profile["top_concepts"] == []
    assert profile["top_indexes"] == [{"name": "沪深300", "count": 1}]
    assert profile["coverage_flags"] == ["concepts_missing"]
    assert "data.daily.coverage_context.universe.sector_profile.top_concepts" in payload["data"]["agent_contract"]["stable_fields"]
    assert any(action["id"] == "export_a_share_universe_patch" for action in coverage["next_actions"])
    assert any(action["id"] == "merge_a_share_universe_patch" for action in coverage["next_actions"])


def test_agent_run_ready_executes_read_only_and_skips_writes(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_run("ai-energy", max_quote_age_days=9999, max_steps=6)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "agent.run"
    assert data["state"] == "ran_with_skips"
    assert data["run_limits"]["read_only_only"] is True
    assert data["results"]
    assert [item["payload_command"] for item in data["results"][:6]] == [
        "pool.coverage",
        "scan",
        "daily",
        "portfolio.review",
        "watchlist",
        "portfolio.explain",
    ]
    assert all(item["state_effect"] == "read_only" for item in data["results"])
    assert all(item["summary"] for item in data["results"])
    assert any(item["observations"] for item in data["results"])
    digest = data["review_digest"]
    assert digest["available"] is True
    assert digest["headline"]
    assert digest["coverage_context"]["available"] is True
    assert digest["coverage_context"]["pool"] == "ai-energy"
    assert digest["coverage_context"]["universe"]["available"] is False
    assert isinstance(digest["coverage_context"]["top_data_quality_queue"], list)
    assert digest["coverage_context"]["next_actions"][0]["rank"] == 1
    assert digest["market_scan"]["available"] is True
    assert digest["market_scan"]["read"] is True
    assert digest["market_scan"]["top_groups"]
    assert digest["market_scan"]["top_candidates"]
    assert digest["market_scan"]["top_candidates"][0]["review_focus"]["next_command"] == digest["market_scan"]["top_candidates"][0]["commands"][0]
    assert digest["market_scan"]["write_policy"] == "只读全市场扫描，不生成交易指令。"
    assert "data.review_digest.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.coverage_context.universe.enrichment_queue" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.coverage_context.top_data_quality_queue" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.coverage_context.next_actions[].rank" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.market_scan" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.market_scan.top_groups" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.market_scan.top_candidates" in data["agent_contract"]["stable_fields"]
    assert digest["market_structure"]["top_chains"]
    assert digest["portfolio_pressure"]["has_concentration"] is True
    assert digest["portfolio_pressure"]["groups"]
    assert digest["portfolio_pressure"]["changed_group_count"] == 0
    assert digest["portfolio_pressure"]["groups"][0]["changed_member_count"] == 0
    assert digest["portfolio_pressure"]["groups"][0]["changed_members"] == []
    assert digest["portfolio_pressure"]["groups"][0]["primary_json_command"].endswith("--json")
    dashboard = digest["holding_dashboard"]
    assert dashboard["available"] is True
    assert dashboard["holding_count"] == 3
    assert dashboard["high_review_count"] == 2
    assert dashboard["buckets"]["high_review"] == 2
    assert dashboard["buckets"]["with_overlap"] >= 2
    assert dashboard["changed_holding_count"] == 0
    assert dashboard["changed_holdings"] == []
    assert dashboard["top_holdings"][0]["symbol"] == "300308"
    assert dashboard["top_holdings"][0]["change"]["available"] is False
    assert dashboard["top_holdings"][0]["change_priority"] == 0
    assert dashboard["top_holdings"][0]["primary_question"]
    assert dashboard["top_holdings"][0]["primary_json_command"].startswith("market-intel portfolio explain 300308")
    assert dashboard["top_holdings"][0]["primary_json_command"].endswith("--json")
    assert dashboard["write_policy"] == "只读持仓复盘，不自动修改持仓或写入 journal。"
    assert digest["securities_to_review"][0]["symbol"] == "300308"
    assert digest["securities_to_review"][0]["risk_labels"]
    assert digest["security_workbench"]
    first_workbench = digest["security_workbench"][0]
    assert first_workbench["symbol"] == "300308"
    assert first_workbench["primary_command"].startswith("market-intel portfolio explain")
    assert first_workbench["exposure_groups"]
    assert first_workbench["review_reason"]
    assert first_workbench["note_prerequisite"]["requires_journal_entry"] is True
    cards = digest["security_cards"]
    assert cards["available"] is True
    assert cards["cards"]
    cards_by_symbol = {item["symbol"]: item for item in cards["cards"]}
    first_card = cards_by_symbol["300308"]
    assert first_card["priority"] == "high_review"
    assert first_card["next_json_command"].startswith("market-intel portfolio explain 300308")
    assert first_card["supporting_evidence"]
    assert first_card["questions"]
    assert first_card["journal_note"]["section"] == "security_review"
    assert first_card["journal_note"]["prefilled_note_command"].startswith("market-intel journal note --section security_review")
    assert "data.review_digest.security_cards.cards[].next_json_command" in data["agent_contract"]["stable_fields"]
    evidence = digest["evidence_checklist"]
    assert evidence["available"] is True
    assert evidence["items"]
    evidence_types = {item["item_type"] for item in evidence["items"]}
    assert {"holding_review", "portfolio_pressure", "market_structure"} <= evidence_types
    first_evidence = evidence["items"][0]
    assert first_evidence["coverage_status"] in {"covered", "needs_read", "needs_more_context", "blocked_by_data"}
    assert first_evidence["evidence"]
    assert first_evidence["json_command"].endswith("--json")
    assert first_evidence["journal_note"]["prefilled_note_command"].startswith("market-intel journal note --section")
    pressure_evidence = next(item for item in evidence["items"] if item["item_type"] == "portfolio_pressure")
    assert pressure_evidence["missing_evidence"]
    assert pressure_evidence["journal_note"]["section"] == "portfolio_exposure"
    hypothesis = digest["hypothesis_board"]
    assert hypothesis["available"] is True
    assert hypothesis["items"]
    hypothesis_types = {item["item_type"] for item in hypothesis["items"]}
    assert {"portfolio_pressure", "holding_review", "market_structure"} <= hypothesis_types
    pressure_hypothesis = next(item for item in hypothesis["items"] if item["item_type"] == "portfolio_pressure")
    assert pressure_hypothesis["supporting_evidence"]
    assert pressure_hypothesis["weak_points"]
    assert pressure_hypothesis["validation_step"]
    assert pressure_hypothesis["invalidation_signal"]
    assert pressure_hypothesis["json_command"].endswith("--json")
    assert pressure_hypothesis["journal_note"]["section"] == "portfolio_exposure"
    assert pressure_hypothesis["journal_note"]["prefilled_note_command"].startswith("market-intel journal note --section")
    draft = digest["journal_draft"]
    assert draft["available"] is True
    assert len(draft["sections"]) == 5
    assert draft["archive_prerequisite"]["requires_archive"] is True
    assert draft["archive_prerequisite"]["archive_command"] == "market-intel journal save --runtime --json"
    assert {section["id"] for section in draft["sections"]} == {
        "data_quality",
        "market_structure",
        "portfolio_exposure",
        "current_change",
        "security_review",
    }
    assert all(section["draft_text"] for section in draft["sections"])
    assert all(section["archive_prerequisite"]["archive_command"] == draft["archive_prerequisite"]["archive_command"] for section in draft["sections"])
    assert all(section["run_after"] == draft["archive_prerequisite"]["archive_command"] for section in draft["sections"])
    assert all(section["note_command_template"].startswith("market-intel journal note --section") for section in draft["sections"])
    assert all(section["prefilled_note_command"].startswith("market-intel journal note --section") for section in draft["sections"])
    first_prefilled = draft["sections"][0]["prefilled_note_command"]
    parsed = shlex.split(first_prefilled)
    assert parsed[:5] == ["market-intel", "journal", "note", "--section", "data_quality"]
    assert parsed[6] == draft["sections"][0]["draft_text"]
    assert "单票复核" in draft["combined_text"]
    attention = digest["attention_queue"]
    assert attention["available"] is True
    assert attention["items"]
    assert attention["items"][0]["item_type"] == "holding_review"
    assert attention["items"][0]["runnable"] is True
    assert attention["items"][0]["json_command"].startswith("market-intel portfolio explain 300308")
    assert attention["items"][0]["json_command"].endswith("--json")
    assert attention["items"][0]["related_symbols"] == ["300308"]
    assert attention["items"][0]["already_read"] is True
    assert attention["items"][0]["linked_result"]["payload_command"] == "portfolio.explain"
    assert attention["items"][0]["linked_result"]["run_rank"] == 7
    assert attention["items"][0]["journal_note"]["available"] is True
    assert attention["items"][0]["journal_note"]["section"] == "security_review"
    assert attention["items"][0]["journal_note"]["run_after"] == "market-intel journal save --runtime --json"
    assert attention["items"][0]["journal_note"]["prefilled_note_command"].startswith("market-intel journal note --section security_review")
    parsed_note = shlex.split(attention["items"][0]["journal_note"]["prefilled_note_command"])
    assert parsed_note[:5] == ["market-intel", "journal", "note", "--section", "security_review"]
    assert attention["items"][1]["already_read"] is False
    assert attention["items"][1]["linked_result"] is None
    assert attention["items"][1]["linked_context"]["source"] == "review_digest.holding_dashboard"
    manual_attention = [item for item in attention["items"] if item["item_type"] == "manual_followup"]
    assert manual_attention
    assert manual_attention[0]["requires_manual"] is True
    assert manual_attention[0]["runnable"] is False
    assert manual_attention[0]["state_effect"] == "writes_journal"
    assert manual_attention[0]["already_read"] is False
    assert manual_attention[0]["journal_note"]["available"] is False
    assert attention["write_policy"] == "队列只整理关注顺序；agent run 不自动执行写入类命令。"
    followup = digest["followup_watch"]
    assert followup["available"] is True
    assert followup["items"]
    followup_types = {item["item_type"] for item in followup["items"]}
    assert {"priority_holdings", "portfolio_pressure", "market_structure"} <= followup_types
    priority_followup = next(item for item in followup["items"] if item["item_type"] == "priority_holdings")
    assert priority_followup["symbols"]
    assert priority_followup["journal_note"]["section"] == "security_review"
    pressure_followup = next(item for item in followup["items"] if item["item_type"] == "portfolio_pressure")
    assert pressure_followup["journal_note"]["section"] == "portfolio_exposure"
    assert followup["items"][0]["json_command"].endswith("--json")
    assert followup["items"][0]["journal_note"]["prefilled_note_command"].startswith("market-intel journal note --section")
    assert followup["write_policy"] == "只生成下次观察计划，不生成交易指令。"
    completion = digest["review_completion"]
    assert completion["available"] is True
    assert completion["completion_state"] in {"needs_more_review", "ready_for_manual_record", "ready_for_review_note"}
    assert completion["ready_for_journal_note"] is False
    assert completion["pending_count"] >= 1
    assert completion["manual_required_count"] >= 1
    assert completion["blocking_count"] == 0
    completion_by_id = {item["check_id"]: item for item in completion["checks"]}
    assert completion_by_id["evidence"]["status"] == "pending"
    assert completion_by_id["journal_draft"]["status"] == "manual_required"
    assert completion_by_id["followup_watch"]["status"] == "done"
    assert completion_by_id["attention_queue"]["json_command"].endswith("--json")
    assert "data.review_digest.review_completion.completion_state" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.review_completion.checks[].status" in data["agent_contract"]["stable_fields"]
    handoff = digest["review_handoff"]
    assert handoff["available"] is True
    assert handoff["handoff_state"] == "continue_reading"
    assert handoff["resume_prompt"]
    assert handoff["next_read"]
    assert handoff["next_read"][0]["json_command"].endswith("--json")
    assert handoff["next_read"][0]["runnable"] is True
    assert handoff["command_chain"]
    assert handoff["command_chain"][0]["step_type"] == "read"
    assert handoff["command_chain"][0]["json_command"] == handoff["next_read"][0]["json_command"]
    assert handoff["manual_items"]
    assert any(item["requires_manual"] for item in handoff["manual_items"])
    assert handoff["record_templates"]
    assert handoff["record_templates"][0]["prefilled_note_command"].startswith("market-intel journal note --section")
    assert handoff["watch_items"]
    assert "data.review_digest.review_handoff.resume_prompt" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.review_handoff.next_read[].json_command" in data["agent_contract"]["stable_fields"]
    assert digest["risk_watch"]
    assert digest["next_steps"][0]["step_type"] == "security_review"
    assert data["skipped"]
    assert any(item["state_effect"] == "writes_journal" for item in data["skipped"])
    assert data["manual_followups"]
    assert data["manual_followups"][0]["state_effect"] == "writes_journal"
    assert "data.review_digest.holding_dashboard" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.portfolio_pressure.groups[].changed_members" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.holding_dashboard.top_holdings[].change" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.holding_dashboard.top_holdings[].primary_json_command" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.securities_to_review" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.security_workbench" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.security_cards.cards[].open_gaps" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.evidence_checklist.items[].coverage_status" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.evidence_checklist.items[].missing_evidence" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.hypothesis_board.items[].hypothesis" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.hypothesis_board.items[].invalidation_signal" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.journal_draft.sections[].draft_text" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.journal_draft.sections[].prefilled_note_command" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.journal_draft.sections[].run_after" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].requires_manual" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].already_read" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].linked_result.summary" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].linked_context.summary" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.attention_queue.items[].journal_note.prefilled_note_command" in data["agent_contract"]["stable_fields"]
    assert "data.review_digest.followup_watch.items[].check_question" in data["agent_contract"]["stable_fields"]
    assert "data.manual_followups[].json_command" in data["agent_contract"]["stable_fields"]


def test_agent_run_digest_tracks_current_change(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)

    payload = handle_agent_run("ai-energy", max_quote_age_days=9999, max_steps=4)
    digest = payload["data"]["review_digest"]
    change = digest["change_tracking"]["current_vs_latest"]

    assert payload["ok"] is True
    assert change["available"] is True
    assert change["base_entry_id"] == first["data"]["entry"]["id"]
    assert change["current_entry_id"] == "runtime_current"
    assert change["has_delta"] is True
    assert change["portfolio_review"]["changed_count"] >= 1
    assert change["hotspots"]["top"]["current"]["key"] == "电力/液冷"
    pressure = digest["portfolio_pressure"]
    assert pressure["changed_group_count"] >= 1
    changed_groups = [group for group in pressure["groups"] if group["changed_member_count"]]
    assert changed_groups
    assert changed_groups[0]["changed_members"][0]["reasons"]
    assert changed_groups[0]["priority_question"]
    assert changed_groups[0]["primary_json_command"].endswith("--json")
    workbench = digest["security_workbench"]
    by_symbol = {item["symbol"]: item for item in workbench}
    assert "持仓复核变化" in by_symbol["002837"]["change"]["reasons"]
    assert any("数据告警变化" in reason for reason in by_symbol["002281"]["change"]["reasons"])
    assert by_symbol["002281"]["exposure_groups"]
    dashboard = digest["holding_dashboard"]
    assert dashboard["changed_holding_count"] >= 2
    changed_by_symbol = {item["symbol"]: item for item in dashboard["top_holdings"]}
    assert changed_by_symbol["002837"]["change"]["available"] is True
    assert "持仓复核变化" in changed_by_symbol["002837"]["change"]["reasons"]
    assert changed_by_symbol["002837"]["change_priority"] > 0
    assert dashboard["changed_holdings"][0]["reasons"]
    assert "先看相对留档发生变化的持仓" in dashboard["questions"][0]
    cards = digest["security_cards"]
    cards_by_symbol = {item["symbol"]: item for item in cards["cards"]}
    assert cards_by_symbol["002837"]["change"]["available"] is True
    assert cards_by_symbol["002837"]["change_priority"] > 0
    assert cards_by_symbol["002281"]["open_gaps"]
    assert cards_by_symbol["002281"]["next_json_command"].endswith("--json")
    repair = digest["data_repair_plan"]
    assert repair["available"] is True
    assert repair["write_policy"] == "仅提示修复步骤，不自动修改 runtime 文件。"
    repair_by_symbol = {item["symbol"]: item for item in repair["items"] if item.get("symbol")}
    assert repair_by_symbol["002281"]["repair_type"] == "missing_quote_data"
    assert repair_by_symbol["300499"]["repair_type"] == "quote_not_in_holdings"
    assert repair_by_symbol["002281"]["agent_can_fix"] is False
    assert repair["groups"][0]["symbols"]
    assert "market-intel validate runtime --json" in repair["commands"]
    attention = digest["attention_queue"]
    assert attention["items"][0]["item_type"] == "data_repair"
    assert attention["items"][0]["runnable"] is True
    assert "002281" in attention["items"][0]["related_symbols"]
    assert attention["items"][0]["already_read"] is False
    assert attention["items"][0]["linked_result"] is None
    assert attention["items"][0]["linked_context"]["source"] == "review_digest.data_quality"
    assert attention["items"][0]["journal_note"]["section"] == "data_quality"
    assert attention["items"][1]["item_type"] == "current_vs_latest"
    assert attention["items"][1]["runnable"] is True
    assert "002837" in attention["items"][1]["related_symbols"]
    assert attention["items"][1]["linked_context"]["source"] in {"source_briefing", "review_digest.change_tracking"}
    assert attention["items"][1]["journal_note"]["section"] == "current_change"
    evidence = digest["evidence_checklist"]
    evidence_types = {item["item_type"] for item in evidence["items"]}
    assert {"data_quality", "current_vs_latest", "holding_review"} <= evidence_types
    data_evidence = next(item for item in evidence["items"] if item["item_type"] == "data_quality")
    assert data_evidence["coverage_status"] == "blocked_by_data"
    assert "002281" in data_evidence["related_symbols"]
    assert data_evidence["missing_evidence"]
    change_evidence = next(item for item in evidence["items"] if item["item_type"] == "current_vs_latest")
    assert change_evidence["journal_note"]["section"] == "current_change"
    assert change_evidence["done_when"]
    hypothesis = digest["hypothesis_board"]
    hypothesis_types = {item["item_type"] for item in hypothesis["items"]}
    assert {"data_quality", "current_vs_latest"} <= hypothesis_types
    data_hypothesis = next(item for item in hypothesis["items"] if item["item_type"] == "data_quality")
    assert data_hypothesis["weak_points"]
    assert data_hypothesis["confidence"] in {"low", "medium", "high"}
    change_hypothesis = next(item for item in hypothesis["items"] if item["item_type"] == "current_vs_latest")
    assert change_hypothesis["journal_note"]["section"] == "current_change"
    assert change_hypothesis["invalidation_signal"]
    followup = digest["followup_watch"]
    followup_types = {item["item_type"] for item in followup["items"]}
    assert {"data_quality", "changed_holdings", "portfolio_pressure", "market_structure"} <= followup_types
    changed_followup = next(item for item in followup["items"] if item["item_type"] == "changed_holdings")
    assert "002837" in changed_followup["symbols"]
    assert changed_followup["check_question"]
    assert changed_followup["journal_note"]["run_after"] == "market-intel journal save --runtime --json"
    completion = digest["review_completion"]
    completion_by_id = {item["check_id"]: item for item in completion["checks"]}
    assert completion["blocking_count"] >= 1
    assert completion["ready_for_journal_note"] is False
    assert completion_by_id["data_quality"]["status"] == "manual_required"
    assert completion_by_id["evidence"]["status"] == "blocked"
    assert completion_by_id["evidence"]["json_command"].endswith("--json")
    handoff = digest["review_handoff"]
    assert handoff["handoff_state"] == "blocked"
    assert handoff["next_read"]
    assert handoff["next_read"][0]["source"] == "evidence"
    assert handoff["command_chain"][0]["step_type"] == "read"
    assert handoff["manual_items"]
    assert handoff["resume_prompt"]
    text = render_agent_run_text(payload)
    assert "数据修复计划" in text
    assert "单票卡片" in text
    assert "证据清单" in text
    assert "观察假设" in text
    assert "关注队列" in text
    assert "下次观察" in text
    assert "复盘收尾" in text
    assert "复盘交接" in text
    assert "变化成员" in text
    assert "变化:" in text
    assert "持仓缺行情" in text
    assert digest["next_steps"][0]["step_type"] == "current_change"
    assert "data.review_digest.data_repair_plan.items" in payload["data"]["agent_contract"]["stable_fields"]
    assert "data.review_digest.change_tracking.current_vs_latest" in payload["data"]["agent_contract"]["stable_fields"]


def test_agent_run_digest_tracks_history_transition(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_note(
        entry_id=second["data"]["entry"]["id"],
        section="current_change",
        note_text="观察项变化明显，继续核对液冷链路。",
    )

    payload = handle_agent_run("ai-energy", max_quote_age_days=9999, max_steps=5)
    digest = payload["data"]["review_digest"]
    transition = digest["change_tracking"]["history_transition"]

    assert payload["ok"] is True
    assert transition["available"] is True
    assert transition["base_entry_id"] == first["data"]["entry"]["id"]
    assert transition["current_entry_id"] == second["data"]["entry"]["id"]
    assert transition["has_delta"] is True
    assert transition["risk_flags"]["added_count"] >= 1
    assert transition["portfolio_review"]["changed_symbols"]
    assert transition["hotspots"]["top"]["base"]["key"] == "运力/CPO / 硅光"
    assert transition["hotspots"]["top"]["current"]["key"] == "电力/液冷"
    by_symbol = {item["symbol"]: item for item in digest["security_workbench"]}
    assert "持仓复核变化" in by_symbol["002837"]["change"]["reasons"]
    assert digest["change_tracking"]["history"]["latest_note"]["section"] == "current_change"
    assert digest["next_steps"][0]["step_type"] == "history_transition"
    assert "data.review_digest.change_tracking.history_transition" in payload["data"]["agent_contract"]["stable_fields"]


def test_agent_plan_with_compare_pair(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)

    payload = handle_agent_plan("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["state"] in {"degraded", "ready_with_compare"}
    assert data["journal"]["can_compare"] is True
    assert data["journal"]["compare_pair"]["base_id"] == first["data"]["entry"]["id"]
    assert data["journal"]["compare_pair"]["current_id"] == second["data"]["entry"]["id"]
    assert "journal compare" in data["journal"]["compare_pair"]["command"]
    assert any(step["id"] == "compare_latest_journals" for step in data["steps"])


def test_agent_briefing_with_history(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_note(
        entry_id=second["data"]["entry"]["id"],
        section="current_change",
        note_text="观察项变化明显，继续核对液冷链路。",
    )

    payload = handle_agent_briefing("ai-energy", max_quote_age_days=9999)
    data = payload["data"]
    text = render_agent_briefing_text(payload)

    assert payload["ok"] is True
    assert data["state"] in {"ready_with_history", "degraded_with_history"}
    assert data["history"]["can_compare"] is True
    assert data["history"]["latest_transition"]["base_entry_id"] == first["data"]["entry"]["id"]
    assert data["history"]["latest_transition"]["current_entry_id"] == second["data"]["entry"]["id"]
    assert data["history"]["latest_transition"]["portfolio_review"]["changed_count"] >= 1
    assert data["history"]["latest_entry"]["latest_note"]["section"] == "current_change"
    assert data["history"]["compare_summary"]
    assert any(item["id"] == "history_transition" for item in data["review_focus"])
    assert any(item["id"] == "history_transition_review" for item in data["review_checklist"])
    assert any("journal compare" in command for command in data["next_commands"])
    assert "最近笔记" in text
    assert "液冷链路" in text


def test_agent_briefing_compares_runtime_to_latest_archive(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)

    payload = handle_agent_briefing("ai-energy", max_quote_age_days=9999)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["current_change"]["available"] is True
    assert data["current_change"]["base_entry"]["id"] == first["data"]["entry"]["id"]
    assert data["current_change"]["current_entry"]["id"] == "runtime_current"
    assert data["current_change"]["portfolio_review"]["changed_count"] >= 1
    assert data["current_change"]["hotspots"]["top"]["current"]
    warning_codes = {warning["code"] for warning in data["daily"]["validation"]["warnings"]}
    warning_symbols = {warning.get("symbol") for warning in data["daily"]["validation"]["warnings"]}
    assert "HOLDING_WITHOUT_QUOTE" in warning_codes
    assert "QUOTE_NOT_IN_HOLDINGS" in warning_codes
    assert {"002281", "300308", "300499"} <= warning_symbols
    queue_by_symbol = {item["symbol"]: item for item in data["security_review_queue"]}
    assert {"002281", "300308", "300499"} <= set(queue_by_symbol)
    assert "data_quality" in queue_by_symbol["002281"]["sources"]
    assert "portfolio_review" in queue_by_symbol["002281"]["sources"]
    assert "data_quality" in queue_by_symbol["300499"]["sources"]
    assert "watchlist" in queue_by_symbol["300499"]["sources"]
    assert any("HOLDING_WITHOUT_QUOTE:002281" in row for row in queue_by_symbol["002281"]["reasons"])
    assert queue_by_symbol["002281"]["commands"][0].startswith("market-intel portfolio explain")
    assert queue_by_symbol["300499"]["commands"][0].startswith("market-intel pool explain")
    data_warning_focus = next(item for item in data["review_focus"] if item["id"] == "data_warnings")
    assert any("HOLDING_WITHOUT_QUOTE:002281" in row for row in data_warning_focus["evidence"])
    data_warning_check = next(item for item in data["review_checklist"] if item["id"] == "data_warning_review")
    assert any("QUOTE_NOT_IN_HOLDINGS:300499" in row for row in data_warning_check["evidence"])
    assert any(item["id"] == "current_change" for item in data["review_focus"])
    assert any(item["id"] == "current_change_review" for item in data["review_checklist"])
    assert "data.current_change" in data["agent_contract"]["stable_fields"]

    text = render_agent_briefing_text(payload)
    assert "数据告警" in text
    assert "标的复核队列" in text
    assert "300499" in text
    assert "HOLDING_WITHOUT_QUOTE:002281" in text
    assert "QUOTE_NOT_IN_HOLDINGS:300499" in text


def test_agent_plan_text_renderer(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    text = render_agent_plan_text(handle_agent_plan("ai-energy", max_quote_age_days=9999))

    assert "market-intel agent plan" in text
    assert "下一跳" in text
    assert "agent briefing --text" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_briefing_text_renderer(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    text = render_agent_briefing_text(handle_agent_briefing("ai-energy", max_quote_age_days=9999))

    assert "market-intel agent briefing" in text
    assert "复核焦点" in text
    assert "复核清单" in text
    assert "当前变化" in text
    assert "命令队列" in text
    assert "留档提示" in text
    assert "记录命令" in text
    assert "journal note --section" in text
    assert "组合暴露" in text
    assert "全市场扫描" in text
    assert "焦点:" in text
    assert "下一条:" in text
    assert "标的复核队列" in text
    assert "最强链路" in text
    assert "观察清单" in text
    assert "market-intel scan" in text
    assert "portfolio explain" in text
    assert "下一步" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_run_text_renderer(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    text = render_agent_run_text(handle_agent_run("ai-energy", max_quote_age_days=9999, max_steps=3))

    assert "market-intel agent run" in text
    assert "复盘摘要" in text
    assert "全市场扫描" in text
    assert "焦点:" in text
    assert "下一条:" in text
    assert "市场结构" in text
    assert "组合压力" in text
    assert "持仓仪表盘" in text
    assert "primary_json_command" not in text
    assert "标的复核" in text
    assert "单票工作台" in text
    assert "单票卡片" in text
    assert "证据清单" in text
    assert "观察假设" in text
    assert "变化跟踪" in text
    assert "留档草稿" in text
    assert "关注队列" in text
    assert "下次观察" in text
    assert "复盘收尾" in text
    assert "复盘交接" in text
    assert "预填命令" in text
    assert "前置: market-intel journal save --runtime --json" in text
    assert "记录命令" in text
    assert "已运行" in text
    assert "已跳过" in text
    assert "人工后续" in text
    assert "portfolio review" in text
    assert "journal save" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_returns_compact_handoff(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5)
    data = payload["data"]
    text = render_agent_next_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "agent.next"
    assert data["state"] == data["review_handoff"]["handoff_state"]
    assert data["coverage_context"]["available"] is True
    assert data["coverage_context"]["pool"] == "ai-energy"
    assert data["market_scan"]["available"] is True
    assert data["market_scan"]["market_breadth"]["state"]
    assert data["market_scan"]["market_breadth"]["confidence"]
    assert data["market_scan"]["top_groups"]
    assert data["market_scan"]["top_candidates"]
    assert data["market_scan"]["candidate_queue"]["summary"]
    assert data["market_scan"]["top_candidates"][0]["ranking_breakdown"]["total_score"]
    assert data["market_scan"]["top_candidates"][0]["review_focus"]["headline"]
    assert data["market_scan"]["top_candidates"][0]["review_focus"]["next_command"]
    assert data["market_scan"]["top_candidates"][0]["review_focus"]["next_command"] == data["market_scan"]["top_candidates"][0]["commands"][0]
    assert "universe_context" in data["market_scan"]["top_candidates"][0]
    assert data["action_summary"]["next_command"] == data["focus_chain"][0]["json_command"]
    assert data["action_summary"]["command_queue"]
    assert data["action_summary"]["command_queue"][0]["json_command"] == data["action_summary"]["next_command"]
    assert len({item["json_command"] for item in data["action_summary"]["command_queue"]}) == len(data["action_summary"]["command_queue"])
    assert data["action_summary"]["completion_checklist"]
    assert data["action_summary"]["completion_checklist"][0]["json_command"]
    assert data["action_summary"]["record_template"]["available"] is True
    assert [item["source"] for item in data["focus_chain"][:3]] == [
        "coverage_review",
        "market_scan",
        "candidate_queue",
    ]
    assert " --json" in data["focus_chain"][0]["json_command"]
    assert data["review_handoff"]["command_chain"]
    assert data["review_handoff"]["command_chain"][0]["json_command"].endswith("--json")
    assert any(item["source"] == "candidate_queue" for item in data["review_handoff"]["command_chain"])
    assert data["security_cards"]["cards"]
    assert data["review_completion"]["checks"]
    assert "data.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.top_data_quality_queue" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.market_breadth" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.top_groups" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.top_candidates" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.candidate_queue" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.top_candidates[].ranking_breakdown" in data["agent_contract"]["stable_fields"]
    assert "data.market_scan.top_candidates[].universe_context" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.command_queue[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.completion_checklist[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.focus_chain[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.review_handoff.command_chain[].json_command" in data["agent_contract"]["stable_fields"]
    assert "market-intel agent next" in text
    assert "操作摘要" in text
    assert "接力链" in text
    assert "覆盖底座" in text
    assert "全市场扫描" in text
    assert "焦点:" in text
    assert "下一条:" in text
    assert "命令链" in text
    assert "单票卡片" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_mock_returns_demo_handoff_without_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_agent_next(use_mock=True, max_steps=5)
    data = payload["data"]
    text = render_agent_next_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "agent.next"
    assert data["pool"] == "all-a"
    assert data["state"] == "demo"
    assert data["source_agent_run_state"] == "demo_ready"
    assert data["run_limits"]["mode"] == "mock"
    assert data["coverage_context"]["pool"] == "all-a"
    assert data["market_scan"]["top_candidates"]
    assert data["review_handoff"]["handoff_state"] == "demo"
    assert data["review_handoff"]["command_chain"]
    assert data["review_handoff"]["command_chain"][0]["json_command"] == "market-intel import schema --json"
    assert data["action_summary"]["next_command"] == "market-intel import schema --json"
    assert data["action_summary"]["command_queue"][0]["json_command"] == "market-intel import schema --json"
    assert data["action_summary"]["command_queue"][1]["json_command"] == "market-intel pool quality invalid_symbol --json"
    assert data["action_summary"]["completion_checklist"][0]["json_command"] == "market-intel import schema --json"
    assert data["action_summary"]["record_template"]["available"] is False
    assert data["review_completion"]["checks"]
    assert data["review_completion"]["ready_for_journal_note"] is False
    assert data["security_cards"]["cards"]
    assert data["security_cards"]["cards"][0]["next_json_command"].endswith("--mock --json")
    assert "market-intel agent next" in text
    assert "操作摘要" in text
    assert "mock 示例" in text
    assert "单票卡片" in text
    assert "复盘收尾" in text
    assert "复盘收尾: 暂无" not in text
    assert "分 None" not in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_mock_can_focus_symbol(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_agent_next(use_mock=True, symbol="sz300308")
    data = payload["data"]
    focus_commands = [item["json_command"] for item in data["focus_chain"]]

    assert payload["ok"] is True
    assert data["symbol"] == "300308"
    assert len(data["security_cards"]["cards"]) == 1
    assert data["security_cards"]["cards"][0]["symbol"] == "300308"
    assert focus_commands[0].startswith("market-intel portfolio explain 300308 --mock --json")
    assert all("300308" in command for command in focus_commands)


def test_dashboard_journal_gate_requires_manual_items_before_ready():
    gate = dashboard_journal_gate(
        {
            "completion_state": "ready_for_manual_record",
            "ready_for_journal_note": True,
            "blocking_count": 0,
            "manual_required_count": 1,
            "pending_count": 0,
        },
        [],
        [{"json_command": "market-intel journal save --runtime --json"}],
        [],
    )

    assert gate["state"] == "needs_manual"
    assert gate["ready_for_journal_note"] is False
    assert gate["json_command"] == "market-intel journal save --runtime --json"
    assert gate["blockers"] == ["还有 1 个人工确认项，留档前需要确认。"]


def test_dashboard_returns_one_screen_workbench(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    handle_import_universe("examples/a_share_universe.csv.example", use_runtime=True)

    payload = handle_dashboard("all-a", max_quote_age_days=9999, max_steps=5)
    data = payload["data"]
    text = render_dashboard_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "dashboard"
    assert data["pool"] == "all-a"
    assert data["state"] in {"needs_review", "ready_for_note", "blocked_review"}
    assert data["tiles"]
    assert data["coverage_context"]["available"] is True
    assert data["coverage_context"]["universe"]["available"] is True
    assert data["coverage_context"]["universe"]["record_count"] == 16
    assert data["coverage_context"]["universe"]["sector_profile"]["industry_coverage_ratio"] == 1
    holdings_coverage = data["coverage_context"]["holdings_coverage"]
    assert "available" in holdings_coverage
    assert "holding_count" in holdings_coverage
    assert "matched_count" in holdings_coverage
    assert "matched" not in holdings_coverage
    assert "unmatched" not in holdings_coverage
    assert "review_queue" not in holdings_coverage
    assert "top_review_queue" in holdings_coverage
    assert "top_unmatched" in holdings_coverage
    assert data["coverage_context"]["gap_count"] >= 1
    assert data["coverage_context"]["top_gaps"]
    assert data["coverage_context"]["top_data_quality_queue"]
    assert data["coverage_context"]["top_data_quality_queue"][0]["samples"]
    assert data["coverage_context"]["next_actions"][0]["rank"] == 1
    assert data["today_focus"]["available"] is True
    assert data["today_focus"]["source"] == "market_scan"
    assert data["today_focus"]["json_command"] == "market-intel scan --runtime --json"
    assert data["today_focus"]["done_when"]
    assert data["action_summary"]["headline"].startswith("先看：")
    assert data["action_summary"]["next_command"] == data["today_focus"]["json_command"]
    assert data["action_summary"]["journal_state"] == data["handoff"]["journal_gate"]["state"]
    assert data["action_summary"]["next_chain"][0]["json_command"] == data["today_focus"]["focus_chain"][0]["json_command"]
    action_queue = data["action_summary"]["command_queue"]
    assert action_queue
    assert action_queue[0]["json_command"] == data["action_summary"]["next_command"]
    assert action_queue[0]["runnable"] is True
    assert len({item["json_command"] for item in action_queue}) == len(action_queue)
    checklist = data["action_summary"]["completion_checklist"]
    assert checklist == data["handoff"]["completion_checklist"][:3]
    assert checklist
    assert checklist[0]["status"] in {"blocked", "pending", "manual_required", "done"}
    assert checklist[0]["json_command"].endswith("--json")
    assert checklist[0]["done_when"]
    assert data["action_summary"]["record_template"]["available"] is True
    assert data["action_summary"]["record_template"]["section"] == "market_structure"
    assert data["action_summary"]["record_template"]["runnable"] is False
    assert data["action_summary"]["record_template"]["prerequisite_command"] == data["handoff"]["journal_gate"]["json_command"]
    assert data["action_summary"]["record_template"]["prerequisite_done_when"] == data["today_focus"]["done_when"]
    assert data["action_summary"]["record_template"]["prefilled_note_command"].startswith("market-intel journal note --section")
    assert data["action_summary"]["record_template"]["run_after"] == "market-intel journal save --runtime --json"
    assert [item["json_command"] for item in data["today_focus"]["focus_chain"][:3]] == [
        item["json_command"] for item in data["review_plan"]["items"][:3]
    ]
    assert data["today_focus"]["focus_chain"][1]["source"] == "candidate_queue"
    assert data["positioning"]["headline"].startswith("面向全 A")
    assert data["positioning"]["differentiators"][0]["agent_path"] == "data.coverage_context"
    assert "data.today_focus" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.next_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.command_queue[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.command_queue[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.command_queue[].runnable" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.completion_checklist[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.completion_checklist[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.record_template.runnable" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.record_template.prerequisite_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.record_template.prerequisite_done_when" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.record_template.prefilled_note_command" in data["agent_contract"]["stable_fields"]
    assert "data.action_summary.next_chain[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.today_focus.json_command" in data["agent_contract"]["stable_fields"]
    assert "data.today_focus.focus_chain[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.positioning" in data["agent_contract"]["stable_fields"]
    assert "data.positioning.differentiators[].agent_path" in data["agent_contract"]["stable_fields"]
    assert "data.positioning.selection_rule" in data["agent_contract"]["stable_fields"]
    assert data["market_pulse"]["available"] is True
    assert data["market_pulse"]["market_breadth"]["state"]
    assert data["market_pulse"]["market_breadth"]["confidence"]
    assert data["market_pulse"]["top_groups"]
    assert data["market_pulse"]["candidates"]
    assert data["market_pulse"]["candidate_queue"]["summary"]
    assert data["market_pulse"]["candidates"][0]["ranking_breakdown"]["total_score"]
    assert "universe_context" in data["market_pulse"]["candidates"][0]
    assert data["market_pulse"]["candidates"][0]["review_focus"]["headline"]
    assert data["market_pulse"]["candidates"][0]["review_focus"]["next_command"] == data["market_pulse"]["candidates"][0]["json_command"]
    assert data["market_pulse"]["candidates"][0]["json_command"].endswith("--json")
    assert data["portfolio_pulse"]["available"] is True
    assert data["portfolio_pulse"]["top_holdings"]
    assert data["portfolio_pulse"]["top_holdings"][0]["primary_json_command"].endswith("--json")
    assert data["evidence_gaps"]["items"]
    assert data["action_lane"]["items"]
    assert data["review_plan"]["available"] is True
    assert data["review_plan"]["items"]
    assert data["review_plan"]["items"][0]["item_type"] == "market_scan"
    assert any(
        item["item_type"] == "coverage_review" and item["json_command"] == "market-intel pool quality invalid_symbol --json"
        for item in data["review_plan"]["items"]
    )
    assert any(item["item_type"] == "candidate_queue" for item in data["review_plan"]["items"])
    assert data["review_plan"]["items"][0]["done_when"]
    assert data["action_lane"]["items"][0]["item_type"] == "coverage_review"
    assert data["action_lane"]["items"][0]["json_command"] == "market-intel pool quality invalid_symbol --json"
    assert data["handoff"]["next_read"]
    gate = data["handoff"]["journal_gate"]
    assert gate["state"] in {"needs_read", "needs_manual", "blocked", "ready"}
    assert gate["ready_for_journal_note"] is False
    assert gate["json_command"]
    assert gate["blockers"]
    assert data["guardrails"]
    assert "data.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.holdings_coverage.summary" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.holdings_coverage.top_review_queue" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.top_gaps" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.top_data_quality_queue" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.next_actions[].rank" in data["agent_contract"]["stable_fields"]
    assert "data.market_pulse.market_breadth" in data["agent_contract"]["stable_fields"]
    assert "data.market_pulse.candidate_queue" in data["agent_contract"]["stable_fields"]
    assert "data.market_pulse.candidates" in data["agent_contract"]["stable_fields"]
    assert "data.market_pulse.candidates[].universe_context" in data["agent_contract"]["stable_fields"]
    assert "data.market_pulse.candidates[].ranking_breakdown" in data["agent_contract"]["stable_fields"]
    assert "data.portfolio_pulse.top_holdings" in data["agent_contract"]["stable_fields"]
    assert "data.portfolio_pulse.top_holdings[].primary_question" in data["agent_contract"]["stable_fields"]
    assert "data.portfolio_pulse.top_holdings[].risk_flags" in data["agent_contract"]["stable_fields"]
    assert "data.portfolio_pulse.pressure_groups[].group_type" in data["agent_contract"]["stable_fields"]
    assert "data.evidence_gaps.items[].missing_evidence" in data["agent_contract"]["stable_fields"]
    assert "data.evidence_gaps.items[].done_when" in data["agent_contract"]["stable_fields"]
    assert "data.action_lane.items" in data["agent_contract"]["stable_fields"]
    assert "data.review_plan.items[].json_command" in data["agent_contract"]["stable_fields"]
    assert "data.handoff.journal_gate" in data["agent_contract"]["stable_fields"]
    assert "data.handoff.journal_gate.state" in data["agent_contract"]["stable_fields"]
    assert "data.handoff.completion_checklist[].status" in data["agent_contract"]["stable_fields"]
    assert "market-intel dashboard" in text
    assert len(text.splitlines()) <= 80
    assert dashboard_text_max_non_command_line_length(text) <= 110
    assert "操作摘要" in text
    assert "接力命令:" in text
    assert "门槛:" in text
    assert "记录前置:" in text
    assert "前置命令:" in text
    assert "前置完成:" in text
    assert "今日焦点" in text
    assert "为什么:" in text
    assert "接力:" in text
    assert "保留在 JSON data.review_plan.items" in text
    assert "下一条见操作摘要" in text
    assert "定位" in text
    assert "个人复盘操作系统" in text
    assert "覆盖底座" in text
    assert "all-a | %s |" % data["coverage_context"]["status"] in text
    assert "全 A: 已接入 | 记录 16" in text
    assert "持仓覆盖:" in text
    assert "质量:" in text
    assert "全市场" in text
    assert "宽度:" in text
    assert "候选:" in text
    assert "持仓" in text
    assert "先看:" in text
    assert "证据缺口" in text
    assert "复盘计划" in text
    assert "下一步" in text
    assert "留档门槛" in text
    assert "读:" in text
    assert "不生成买卖指令" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()

    first_command = data["review_plan"]["items"][0]["json_command"]
    first_payload = run_agent_read_command(first_command, "all-a", 5, 2, 9999)
    assert first_payload["ok"] is True
    assert first_payload["command"] == "scan"
    assert first_payload["data"]["pool"] == "all-a"
    quality_command = data["coverage_context"]["top_data_quality_queue"][0]["review_command"]
    quality_payload = run_agent_read_command(quality_command, "all-a", 5, 2, 9999)
    assert quality_payload["ok"] is True
    assert quality_payload["command"] == "pool.quality"
    assert quality_payload["data"]["flag"] == data["coverage_context"]["top_data_quality_queue"][0]["flag"]
    assert quality_payload["data"]["samples"]


def test_dashboard_mock_returns_demo_workbench_without_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_dashboard("all-a", use_mock=True, max_steps=5)
    data = payload["data"]
    text = render_dashboard_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "dashboard"
    assert data["state"] == "demo_ready"
    assert data["source_agent_run_state"] == "mock_demo"
    assert data["run_limits"]["mode"] == "mock"
    assert data["positioning"]["mode"] == "mock"
    assert data["positioning"]["differentiators"][1]["agent_path"] == "data.portfolio_pulse"
    assert data["coverage_context"]["available"] is True
    assert data["coverage_context"]["universe"]["available"] is False
    assert data["coverage_context"]["next_actions"][0]["rank"] == 1
    assert "matched" not in data["coverage_context"]["holdings_coverage"]
    assert "top_review_queue" in data["coverage_context"]["holdings_coverage"]
    assert data["today_focus"]["available"] is True
    assert data["today_focus"]["source"] == "runtime_setup"
    assert data["today_focus"]["json_command"] == "market-intel import schema --json"
    assert data["today_focus"]["json_command"] == data["action_lane"]["items"][0]["json_command"]
    assert data["action_summary"]["next_command"] == "market-intel import schema --json"
    assert data["action_summary"]["journal_state"] == data["handoff"]["journal_gate"]["state"]
    assert data["action_summary"]["command_queue"][0]["json_command"] == "market-intel import schema --json"
    assert data["action_summary"]["command_queue"][1]["json_command"] == "market-intel pool quality invalid_symbol --json"
    assert data["action_summary"]["completion_checklist"] == data["handoff"]["completion_checklist"][:3]
    assert data["action_summary"]["completion_checklist"][0]["check_id"] == "runtime_setup"
    assert data["action_summary"]["completion_checklist"][0]["status"] == "pending"
    assert data["action_summary"]["record_template"]["available"] is False
    assert [item["source"] for item in data["today_focus"]["focus_chain"][:3]] == [
        "runtime_setup",
        "coverage_review",
        "market_scan",
    ]
    assert data["market_pulse"]["available"] is True
    assert data["market_pulse"]["candidates"]
    assert data["market_pulse"]["candidates"][0]["review_focus"]["headline"]
    assert data["market_pulse"]["candidates"][0]["review_focus"]["next_command"] == data["market_pulse"]["candidates"][0]["json_command"]
    assert data["market_pulse"]["candidates"][0]["json_command"].endswith("--json")
    assert data["portfolio_pulse"]["available"] is True
    assert data["portfolio_pulse"]["top_holdings"]
    assert data["portfolio_pulse"]["top_holdings"][0]["rank"] == 1
    assert data["portfolio_pulse"]["top_holdings"][0]["primary_json_command"].endswith("--mock --json")
    assert any(item["group_type"] == "theme" for item in data["portfolio_pulse"]["pressure_groups"])
    assert data["evidence_gaps"]["items"]
    assert data["review_plan"]["items"][0]["item_type"] == "runtime_setup"
    assert data["review_plan"]["items"][0]["json_command"] == "market-intel import schema --json"
    assert data["review_plan"]["items"][1]["item_type"] == "coverage_review"
    assert data["review_plan"]["items"][2]["json_command"] == "market-intel scan --mock --json"
    assert data["review_plan"]["items"][3]["item_type"] == "candidate_queue"
    assert data["review_plan"]["items"][3]["json_command"].startswith("market-intel pool explain")
    assert data["action_lane"]["items"]
    assert data["action_lane"]["items"][0]["item_type"] == "runtime_setup"
    assert data["action_lane"]["items"][2]["item_type"] == "market_scan"
    assert data["handoff"]["handoff_state"] == "demo"
    assert data["handoff"]["next_read"]
    assert data["handoff"]["next_read"][2]["source"] == "market_scan"
    assert data["handoff"]["manual_items"][0]["json_command"] == "market-intel init runtime --json"
    assert data["handoff"]["journal_gate"]["state"] == "needs_read"
    assert data["handoff"]["journal_gate"]["ready_for_journal_note"] is False
    assert data["handoff"]["journal_gate"]["json_command"] == "market-intel import schema --json"
    assert any("mock" in item for item in data["guardrails"])
    assert "mock 示例" in text
    assert len(text.splitlines()) <= 80
    assert dashboard_text_max_non_command_line_length(text) <= 110
    assert "操作摘要" in text
    assert "接力命令:" in text
    assert "门槛:" in text
    assert "记录: market-intel journal note --section" not in text
    assert "今日焦点" in text
    assert "接力:" in text
    assert text.count("market-intel import schema --json") == 1
    assert "其余: 5 项保留在 JSON data.review_plan.items。" in text
    assert "读: 4 项，下一条见操作摘要。" in text
    assert "定位" in text
    assert "个人复盘操作系统" in text
    assert "候选:" in text
    assert "先看:" in text
    assert "原因: 300308 中际旭创 | 复核多链路或主题重叠是否导致同涨同跌暴露。 | 风险 追高风险、多链路暴露、主题重叠" in text
    assert "压力: 链路 运力/CPO / 硅光 | 持仓 2；主题 光通信 | 持仓 2" in text
    assert "首项: 300499 高澜股份 | 缺 行业/主题链路、公司角色、研究证据 | 已补齐或记录缺失原因" in text
    assert "命令: market-intel pool explain 300499 --json" in text
    assert "下一步" in text
    assert "留档门槛" in text
    assert "覆盖底座" in text
    assert "all-a | seed |" in text
    assert "全 A: 未接入" in text
    assert "持仓覆盖: 5/5" in text
    assert "market-intel dashboard" in text
    assert "不生成买卖指令" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()

    coverage_command = data["review_plan"]["items"][1]["json_command"]
    coverage_payload = run_agent_read_command(coverage_command, "all-a", 5, 2, 9999)
    assert coverage_payload["ok"] is True
    assert coverage_payload["command"] == "pool.quality"
    assert coverage_payload["data"]["pool"] == "all-a"
    assert coverage_payload["data"]["flag"] == "invalid_symbol"


def test_dashboard_action_summary_selects_record_template_by_focus_source():
    summary = dashboard_action_summary(
        {
            "available": True,
            "source": "candidate_queue",
            "title": "300308 中际旭创",
            "json_command": "market-intel pool explain 300308 --runtime --json",
            "focus_chain": [],
        },
        {
            "journal_gate": {"state": "needs_read", "ready_for_journal_note": False, "next_step": "先读候选。"},
            "record_templates": [
                {
                    "section": "data_quality",
                    "title": "数据质量",
                    "prefilled_note_command": "market-intel journal note --section data_quality --text '数据质量。'",
                    "run_after": "market-intel journal save --runtime --json",
                },
                {
                    "section": "security_review",
                    "title": "单票复核",
                    "prefilled_note_command": "market-intel journal note --section security_review --text '单票复核。'",
                    "run_after": "market-intel journal save --runtime --json",
                },
            ],
        },
    )

    assert summary["record_template"]["section"] == "security_review"
    assert summary["record_template"]["runnable"] is False
    assert summary["record_template"]["blocked_reason"] == "先读候选。"
    assert "security_review" in summary["record_template"]["prefilled_note_command"]


def test_dashboard_blocked_handoff_does_not_duplicate_next_read(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_dashboard("all-a", max_quote_age_days=9999, max_steps=5)
    data = payload["data"]
    next_read_commands = {
        item["json_command"]
        for item in data["handoff"]["next_read"]
        if isinstance(item, dict) and item.get("json_command")
    }
    manual_commands = {
        item["json_command"]
        for item in data["handoff"]["manual_items"]
        if isinstance(item, dict) and item.get("json_command")
    }

    assert payload["ok"] is True
    assert data["state"] == "blocked"
    assert data["handoff"]["completion_checklist"][0]["status"] == "blocked"
    assert data["handoff"]["completion_checklist"][0]["check_id"] == "data_quality"
    assert data["action_summary"]["completion_checklist"][0]["json_command"] == data["handoff"]["completion_checklist"][0]["json_command"]
    assert data["action_summary"]["command_queue"][0]["json_command"] == "market-intel validate runtime --json"
    assert data["action_summary"]["record_template"]["available"] is True
    assert data["action_summary"]["record_template"]["runnable"] is False
    assert data["action_summary"]["record_template"]["blocked_reason"]
    assert data["action_summary"]["record_template"]["prerequisite_command"] == "market-intel validate runtime --json"
    assert data["action_summary"]["record_template"]["prerequisite_done_when"]
    assert "market-intel validate runtime --json" in next_read_commands
    assert "market-intel validate runtime --json" not in manual_commands
    assert data["review_plan"]["items"][0]["json_command"] == "market-intel validate runtime --json"


def test_dashboard_init_runtime_prioritizes_market_over_seed_quality(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_dashboard("all-a", max_quote_age_days=9999, max_steps=5)
    data = payload["data"]
    item_types = [item["item_type"] for item in data["review_plan"]["items"]]
    candidates = {item["symbol"]: item for item in data["market_pulse"]["candidates"]}
    holdings = {item["symbol"]: item for item in data["portfolio_pulse"]["top_holdings"]}
    gate = data["handoff"]["journal_gate"]

    assert payload["ok"] is True
    assert data["state"] in {"needs_review", "ready_for_note", "blocked_review"}
    assert data["today_focus"]["source"] == "market_scan"
    assert data["today_focus"]["json_command"] == "market-intel scan --runtime --json"
    assert item_types[0] == "market_scan"
    assert "coverage_review" in item_types
    assert data["coverage_context"]["top_gaps"][0]["id"] == "data_quality_flags"
    assert {
        symbol: candidates[symbol]["review_focus"]["coverage"]["research_status"]
        for symbol in ["300308", "002281", "002837"]
    } == {"300308": "reviewed", "002281": "reviewed", "002837": "reviewed"}
    assert candidates["300308"]["coverage_state"] == "confirmed"
    assert candidates["002281"]["coverage_state"] == "confirmed"
    assert candidates["002837"]["coverage_state"] == "draft"
    assert holdings["300308"]["primary_question"].startswith("研究证据已复核")
    assert holdings["002281"]["primary_question"].startswith("研究证据已复核")
    assert holdings["002837"]["primary_question"].startswith("先确认候选补池行")
    assert gate["state"] == "needs_read"
    assert gate["ready_for_journal_note"] is False
    assert gate["json_command"].startswith("market-intel portfolio explain")
    assert gate["blockers"][0].startswith("还有")


def test_dashboard_surfaces_universe_enrichment_queue(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,,沪深300,listed\n"
        "600519,贵州茅台,,白酒;消费,,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    payload = handle_dashboard("all-a", max_quote_age_days=9999, max_steps=5)
    data = payload["data"]
    text = render_dashboard_text(payload)

    queue = data["coverage_context"]["universe"]["enrichment_queue"]
    profile = data["coverage_context"]["universe"]["sector_profile"]
    assert queue
    assert queue[0]["field"] == "industry"
    assert queue[0]["samples"][0] == {"symbol": "600519", "name": "贵州茅台"}
    assert queue[0]["command"] == "market-intel import universe <a_share_universe_patch.csv> --runtime --merge --dry-run --json"
    assert profile["top_industries"] == [{"name": "银行", "count": 1}]
    assert profile["top_concepts"][:2] == [{"name": "消费", "count": 1}, {"name": "白酒", "count": 1}]
    assert profile["top_indexes"] == [{"name": "沪深300", "count": 1}]
    assert "data.coverage_context.universe.sector_profile.top_concepts" in data["agent_contract"]["stable_fields"]
    assert "补数: #1 行业 | 缺 1" in text
    assert "分布: 行业 银行(1) | 概念 消费(1)、白酒(1) | 指数 沪深300(1)" in text
    assert str(universe_file) not in text


def test_dashboard_mock_preserves_non_default_pool(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_dashboard("ai-energy", use_mock=True)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["pool"] == "ai-energy"
    assert data["review_plan"]["items"][0]["json_command"] == "market-intel import schema --json"
    assert data["review_plan"]["items"][1]["json_command"].endswith("--pool ai-energy")
    assert data["review_plan"]["items"][2]["json_command"].endswith("--pool ai-energy")
    assert data["portfolio_pulse"]["top_holdings"][0]["primary_json_command"].endswith("--pool ai-energy")
    assert data["action_lane"]["items"][0]["json_command"] == "market-intel import schema --json"
    assert data["action_lane"]["items"][1]["json_command"].endswith("--pool ai-energy")
    assert data["handoff"]["summary"].endswith("--pool ai-energy。")

    coverage_payload = run_agent_read_command(data["review_plan"]["items"][1]["json_command"], "all-a", 5, 2, 9999)
    assert coverage_payload["ok"] is True
    assert coverage_payload["command"] == "pool.quality"
    assert coverage_payload["data"]["pool"] == "ai-energy"
    assert coverage_payload["data"]["flag"] == "invalid_symbol"


def test_agent_next_can_focus_symbol(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5, symbol="300308")
    data = payload["data"]
    text = render_agent_next_text(payload)

    assert payload["ok"] is True
    assert data["symbol"] == "300308"
    assert data["review_handoff"]["handoff_state"] == "continue_reading"
    assert data["review_handoff"]["command_chain"]
    assert data["review_handoff"]["command_chain"][0]["json_command"].startswith("market-intel portfolio explain 300308")
    assert data["focus_chain"][0]["json_command"].startswith("market-intel portfolio explain 300308")
    assert data["focus_chain"][0]["related_symbols"] == ["300308"]
    assert data["focus_chain"][1]["json_command"].startswith("market-intel pool explain 300308")
    assert all(item["json_command"].endswith("--pool ai-energy") for item in data["focus_chain"])
    assert all("300308" in item["json_command"] or "300308" in item.get("related_symbols", []) for item in data["focus_chain"])
    assert len(data["security_cards"]["cards"]) == 1
    assert data["security_cards"]["cards"][0]["symbol"] == "300308"
    assert "data.symbol" in data["agent_contract"]["stable_fields"]
    assert "聚焦标的: 300308" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_normalizes_symbol_input(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payloads = [
        handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5, symbol=value)
        for value in [" 300308 ", "sz300308", "300308.SZ", "SZ:300308", "sz.300308"]
    ]

    for payload in payloads:
        assert payload["ok"] is True
        assert payload["data"]["symbol"] == "300308"
        assert payload["data"]["security_cards"]["cards"][0]["symbol"] == "300308"
        assert payload["data"]["focus_chain"][0]["json_command"].startswith("market-intel portfolio explain 300308")


def test_agent_next_surfaces_foundation_holding_review(monkeypatch, tmp_path):
    import_foundation_runtime(monkeypatch, tmp_path)

    payload = handle_agent_next("all-a", max_quote_age_days=9999, max_steps=5, symbol="000001")
    data = payload["data"]
    text = render_agent_next_text(payload)
    card = data["security_cards"]["cards"][0]

    assert payload["ok"] is True
    assert card["symbol"] == "000001"
    assert data["coverage_context"]["pool"] == "all-a"
    assert data["coverage_context"]["universe"]["available"] is True
    assert data["coverage_context"]["universe"]["sector_profile"]["industry_coverage_ratio"] == 1
    assert card["coverage_state"] == "foundation"
    assert "a_share_universe_foundation" in card["coverage_state_reasons"]
    assert "foundation_pool_match" in card["risk_flags"]
    assert card["research_workflow"][0]["json_command"].startswith("market-intel pool research")
    assert any(step["json_command"].startswith("market-intel import research") and "--dry-run" in step["json_command"] for step in card["research_workflow"])
    assert any(step["json_command"].startswith("market-intel import research") and "--runtime" in step["json_command"] for step in card["research_workflow"])
    assert card["research_workflow"][-1]["json_command"] == "market-intel pool coverage --runtime --json"
    assert any(item["source"] == "foundation_research" for item in data["review_handoff"]["manual_items"])
    manual_research_items = [
        item
        for item in data["review_handoff"]["manual_items"]
        if item["source"] == "foundation_research"
    ]
    assert len(manual_research_items) == 1
    assert manual_research_items[0]["requires_manual"] is True
    workflow_steps = manual_research_items[0]["workflow_steps"]
    assert any(step["json_command"].endswith("--dry-run --json") and step["requires_manual"] is False for step in workflow_steps)
    assert workflow_steps[-1]["json_command"] == "market-intel pool coverage --runtime --json"
    research_steps = [
        item
        for item in data["review_handoff"]["command_chain"]
        if item["source"] == "foundation_research"
    ]
    assert research_steps
    assert any("--dry-run" in item["json_command"] for item in research_steps)
    assert any(item["json_command"] == "market-intel pool coverage --runtime --json" for item in research_steps)
    assert any(item["requires_manual"] is False for item in research_steps)
    assert any(item["requires_manual"] is True for item in research_steps)
    assert any(item["runnable"] is True for item in research_steps)
    assert any(item["runnable"] is False for item in research_steps)
    dry_run_step = next(item for item in research_steps if "--dry-run" in item["json_command"])
    assert dry_run_step["step_type"] == "read"
    assert dry_run_step["runnable"] is True
    import_step = next(item for item in research_steps if item["json_command"].startswith("market-intel import research") and "--runtime" in item["json_command"])
    assert import_step["step_type"] == "manual"
    assert import_step["runnable"] is False
    assert any("全 A 基础清单" in gap for gap in card["open_gaps"])
    assert card["next_json_command"].startswith("market-intel portfolio explain 000001")
    assert "data.security_cards.cards[].coverage_state" in data["agent_contract"]["stable_fields"]
    assert "data.security_cards.cards[].research_workflow" in data["agent_contract"]["stable_fields"]
    assert "data.review_handoff.manual_items[].workflow_steps" in data["agent_contract"]["stable_fields"]
    assert "覆盖: foundation" in text or "覆盖: 基础" in text
    assert "覆盖底座" in text
    assert "字段覆盖: 行业 100.0%" in text
    assert "研究流程" in text
    assert "证伪风险" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_closes_foundation_gap_with_reviewed_research(monkeypatch, tmp_path):
    import_foundation_runtime(monkeypatch, tmp_path)
    import_foundation_research(tmp_path)

    payload = handle_agent_next("all-a", max_quote_age_days=9999, max_steps=5, symbol="000001")
    data = payload["data"]
    text = render_agent_next_text(payload)
    card = data["security_cards"]["cards"][0]

    assert payload["ok"] is True
    assert card["symbol"] == "000001"
    assert card["coverage_state"] == "confirmed"
    assert card["coverage_state_reasons"] == ["reviewed_research"]
    assert card["research_status"]["confirmed"] is True
    assert card["research_workflow"] == []
    assert "foundation_pool_match" not in card["risk_flags"]
    assert not any("全 A 基础清单" in gap for gap in card["open_gaps"])
    assert "data.security_cards.cards[].research_status" in data["agent_contract"]["stable_fields"]
    assert "研究: reviewed" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_agent_next_symbol_not_found(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    payload = handle_agent_next("ai-energy", max_quote_age_days=9999, max_steps=5, symbol="000000")

    assert payload["ok"] is False
    assert payload["data"]["state"] == "symbol_not_found"
    assert payload["data"]["focus_chain"] == []
    assert payload["errors"][0]["code"] == "AGENT_NEXT_SYMBOL_NOT_FOUND"


def test_agent_plan_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    json_result = subprocess.run(
        cli_cmd(
            "agent",
            "plan",
            "--max-quote-age-days",
            "9999",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd(
            "agent",
            "plan",
            "--max-quote-age-days",
            "9999",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(json_result.stdout)["command"] == "agent.plan"
    assert "market-intel agent plan" in text_result.stdout


def test_agent_briefing_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    json_result = subprocess.run(
        cli_cmd(
            "agent",
            "briefing",
            "--max-quote-age-days",
            "9999",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd(
            "agent",
            "briefing",
            "--max-quote-age-days",
            "9999",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(json_result.stdout)["command"] == "agent.briefing"
    assert "market-intel agent briefing" in text_result.stdout


def test_agent_run_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    json_result = subprocess.run(
        cli_cmd(
            "agent",
            "run",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd(
            "agent",
            "run",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(json_result.stdout)["command"] == "agent.run"
    assert "market-intel agent run" in text_result.stdout


def test_agent_next_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    json_result = subprocess.run(
        cli_cmd(
            "agent",
            "next",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd(
            "agent",
            "next",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    symbol_result = subprocess.run(
        cli_cmd(
            "agent",
            "next",
            "--max-quote-age-days",
            "9999",
            "--symbol",
            "300308",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(json_result.stdout)
    assert data["command"] == "agent.next"
    assert data["data"]["review_handoff"]["command_chain"]
    assert "market-intel agent next" in text_result.stdout
    symbol_data = json.loads(symbol_result.stdout)
    assert symbol_data["data"]["symbol"] == "300308"
    assert symbol_data["data"]["security_cards"]["cards"][0]["symbol"] == "300308"

    mock_result = subprocess.run(
        cli_cmd("agent", "next", "--mock", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    mock_data = json.loads(mock_result.stdout)
    assert mock_data["data"]["run_limits"]["mode"] == "mock"
    assert mock_data["data"]["review_handoff"]["command_chain"]


def test_dashboard_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    json_result = subprocess.run(
        cli_cmd(
            "dashboard",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd(
            "dashboard",
            "--max-quote-age-days",
            "9999",
            "--max-steps",
            "3",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(json_result.stdout)
    assert data["command"] == "dashboard"
    assert data["data"]["market_pulse"]["candidates"]
    assert "market-intel dashboard" in text_result.stdout


def test_dashboard_mock_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    json_result = subprocess.run(
        cli_cmd("dashboard", "--mock", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    text_result = subprocess.run(
        cli_cmd("dashboard", "--mock", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(json_result.stdout)
    assert data["command"] == "dashboard"
    assert data["data"]["state"] == "demo_ready"
    assert data["data"]["run_limits"]["mode"] == "mock"
    assert data["data"]["review_plan"]["items"][0]["json_command"] == "market-intel import schema --json"
    assert data["data"]["review_plan"]["items"][1]["json_command"] == "market-intel pool quality invalid_symbol --json"
    assert data["data"]["review_plan"]["items"][2]["json_command"] == "market-intel scan --mock --json"
    assert "mock 示例" in text_result.stdout
    assert "准备正式 runtime 数据" in text_result.stdout
