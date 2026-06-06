import json
import shlex
import subprocess

from market_intel.cli import handle_daily, handle_init_runtime
from market_intel.core.text_report import render_daily_report_text


QUOTE = {
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


def test_daily_mock_shape():
    payload = handle_daily("ai-energy", use_mock=True, top=3, map_top=2)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "daily"
    assert data["summary"]
    assert data["validation"]["ok"] is True
    assert data["brief"]["top_hotspots"]
    assert data["map"]["layers"]
    assert data["watchlist"]["items"]
    assert data["portfolio_review"]["items"]
    assert data["coverage_context"]["available"] is True
    assert data["coverage_context"]["pool"] == "ai-energy"
    assert data["coverage_context"]["universe"]["available"] is False
    assert "data.coverage_context" in data["agent_contract"]["stable_fields"]
    assert "data.coverage_context.universe.sector_profile" in data["agent_contract"]["stable_fields"]
    assert "data.portfolio_review.repeated_exposures" in data["agent_contract"]["stable_fields"]
    assert "data.risk_register" in data["agent_contract"]["stable_fields"]
    assert "data.risk_register[].affected_symbols" in data["agent_contract"]["stable_fields"]
    assert data["risk_register"]
    concentration = next(item for item in data["risk_register"] if item["risk_id"] == "theme_concentration")
    assert concentration["severity"] == "high"
    assert concentration["affected_count"] >= 2
    assert concentration["affected_symbols"]
    assert concentration["commands"][0] == "market-intel portfolio review --mock --text --pool ai-energy"
    data_quality = next(item for item in data["risk_register"] if item["risk_id"] == "data_quality_warnings")
    assert data_quality["affected_symbols"]
    assert data_quality["commands"][0] == "market-intel daily --mock --json --pool ai-energy"
    assert "data.review_path" in data["agent_contract"]["stable_fields"]
    assert "data.review_path[].runnable" in data["agent_contract"]["stable_fields"]
    assert data["review_path"]
    assert data["review_path"][0]["id"] == "data_quality"
    assert data["review_path"][0]["commands"][0] == "market-intel daily --mock --json --pool ai-energy"
    assert data["review_path"][-1]["id"] == "archive_review"
    assert data["review_path"][-1]["runnable"] is False
    assert data["review_path"][-1]["commands"] == ["market-intel journal save --runtime --json"]
    assert data["review_path"][-1]["unavailable_reason"]
    assert "data.security_risk_profile" in data["agent_contract"]["stable_fields"]
    assert "data.security_risk_profile[].related_risks" in data["agent_contract"]["stable_fields"]
    assert data["security_risk_profile"]
    first_profile = data["security_risk_profile"][0]
    assert first_profile["symbol"] == "300308"
    assert first_profile["related_risks"]
    assert "theme_concentration" in first_profile["risk_ids"]
    assert first_profile["commands"][0] == "market-intel portfolio explain 300308 --mock --text --pool ai-energy"
    assert first_profile["note_prerequisite"]["archive_runnable"] is False
    assert "data.review_tasks" in data["agent_contract"]["stable_fields"]
    assert data["portfolio_review"]["agent_contract"]["stable_fields"]
    assert data["next_questions"]
    assert data["review_tasks"]
    assert data["review_tasks"][0]["commands"]
    assert data["review_tasks"][0]["note_command"].startswith("market-intel journal note --section")
    assert "data.review_tasks[].note_prerequisite" in data["agent_contract"]["stable_fields"]
    assert data["review_tasks"][0]["note_prerequisite"]["requires_journal_entry"] is True
    assert data["review_tasks"][0]["note_prerequisite"]["archive_runnable"] is False
    assert data["review_tasks"][0]["done_when"]
    assert "data.security_review_queue" in data["agent_contract"]["stable_fields"]
    assert "data.security_review_queue[].priority_score" in data["agent_contract"]["stable_fields"]
    assert "data.security_review_queue[].note_command" in data["agent_contract"]["stable_fields"]
    assert "data.security_review_queue[].note_prerequisite" in data["agent_contract"]["stable_fields"]
    assert data["security_review_queue"]
    assert data["security_review_queue"][0]["symbol"] == "300308"
    assert data["security_review_queue"][0]["commands"][0].startswith("market-intel portfolio explain")
    assert data["security_review_queue"][0]["note_command"].startswith("market-intel journal note --section security_review")
    assert data["security_review_queue"][0]["note_prerequisite"]["requires_journal_entry"] is True
    assert data["security_review_queue"][0]["note_prerequisite"]["archive_runnable"] is False
    assert "data.journal_actions" in data["agent_contract"]["stable_fields"]
    assert data["journal_actions"][0]["id"] == "archive_current"
    assert data["journal_actions"][0]["runnable"] is False
    assert data["journal_actions"][1]["command"] == "market-intel journal latest --text"
    assert "data.command_queue" in data["agent_contract"]["stable_fields"]
    assert "data.command_queue[].runnable" in data["agent_contract"]["stable_fields"]
    assert data["command_queue"]
    assert data["command_queue"][0]["command"] == "market-intel daily --mock --json --pool ai-energy"
    assert all("pool explain" not in item["command"] or " --mock" not in item["command"] for item in data["command_queue"])
    archive_item = next(item for item in data["command_queue"] if item["command"] == "market-intel journal save --runtime --json")
    note_item = next(item for item in data["command_queue"] if item["command"].startswith("market-intel journal note --section"))
    assert archive_item["runnable"] is False
    assert archive_item["state_effect"] == "writes_journal"
    assert note_item["runnable"] is False
    assert note_item["state_effect"] == "writes_journal"
    assert note_item["requires_prior_command"] == archive_item["command"]
    assert note_item["run_after_rank"] == archive_item["rank"]
    assert note_item["json_command"].endswith(" --json")


def test_daily_requires_source():
    payload = handle_daily("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "DAILY_SOURCE_REQUIRED"


def test_daily_accepts_file_sources(tmp_path):
    data_dir = tmp_path / "daily inputs"
    data_dir.mkdir()
    quotes_path = data_dir / "quotes.json"
    holdings_path = data_dir / "holdings.json"
    quotes_path.write_text(json.dumps({"quotes": [QUOTE]}, ensure_ascii=False), encoding="utf-8")
    holdings_path.write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_daily(
        "ai-energy",
        use_mock=True,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )

    assert payload["ok"] is True
    assert payload["data"]["mode"] == "file"
    assert payload["data"]["validation"]["summary"]["quote_count"] == 1
    assert payload["data"]["validation"]["summary"]["holding_count"] == 1
    task_commands = [command for task in payload["data"]["review_tasks"] for command in task["commands"]]
    queue_commands = [command for item in payload["data"]["security_review_queue"] for command in item["commands"]]
    risk_commands = [command for item in payload["data"]["risk_register"] for command in item["commands"]]
    path_commands = [command for item in payload["data"]["review_path"] for command in item["commands"]]
    profile_commands = [command for item in payload["data"]["security_risk_profile"] for command in item["commands"]]
    assert any("--quotes-file" in command and "'%s'" % quotes_path in command for command in task_commands)
    assert any("--quotes-file" in command and "'%s'" % quotes_path in command for command in queue_commands)
    assert any("--quotes-file" in command and "'%s'" % quotes_path in command for command in risk_commands)
    assert any("--quotes-file" in command and "'%s'" % quotes_path in command for command in path_commands)
    assert any("--quotes-file" in command and "'%s'" % quotes_path in command for command in profile_commands)
    assert payload["data"]["review_tasks"][0]["note_prerequisite"]["archive_runnable"] is True
    assert "'%s'" % quotes_path in payload["data"]["review_tasks"][0]["note_prerequisite"]["archive_command"]
    assert payload["data"]["security_review_queue"][0]["note_prerequisite"]["archive_runnable"] is True
    assert payload["data"]["journal_actions"][0]["runnable"] is True
    assert "'%s'" % quotes_path in payload["data"]["journal_actions"][0]["command"]
    file_archive = next(item for item in payload["data"]["command_queue"] if "journal save" in item["command"])
    file_note = next(item for item in payload["data"]["command_queue"] if "journal note" in item["command"])
    assert file_archive["runnable"] is True
    assert file_note["runnable"] is True
    assert file_note["requires_prior_command"] == file_archive["command"]


def test_daily_file_validation_failure(tmp_path):
    quotes_path = tmp_path / "quotes.json"
    holdings_path = tmp_path / "holdings.json"
    quotes_path.write_text(json.dumps({"quotes": [{"symbol": "002837"}]}, ensure_ascii=False), encoding="utf-8")
    holdings_path.write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_daily(
        "ai-energy",
        use_mock=False,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )

    assert payload["ok"] is False
    assert payload["command"] == "daily"
    assert payload["data"]["validation"]["ok"] is False
    assert any(error["code"] == "MISSING_REQUIRED_FIELDS" for error in payload["errors"])


def test_daily_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_daily("ai-energy", use_mock=False, use_runtime=True, top=3)

    assert payload["ok"] is True
    assert payload["data"]["mode"] == "runtime"
    assert payload["data"]["validation"]["summary"]["quote_count"] > 0
    assert payload["data"]["review_tasks"][0]["note_prerequisite"]["archive_command"] == "market-intel journal save --runtime --json"
    assert payload["data"]["review_tasks"][0]["note_prerequisite"]["archive_runnable"] is True
    assert payload["data"]["risk_register"]
    assert payload["data"]["risk_register"][0]["commands"][0].endswith("--runtime --text")
    assert payload["data"]["review_path"][-1]["runnable"] is True
    assert payload["data"]["review_path"][-1]["commands"] == ["market-intel journal save --runtime --json"]
    assert payload["data"]["security_risk_profile"][0]["commands"][0].endswith("--runtime --text")
    assert payload["data"]["security_risk_profile"][0]["note_prerequisite"]["archive_runnable"] is True
    runtime_archive = next(item for item in payload["data"]["command_queue"] if item["command"] == "market-intel journal save --runtime --json")
    runtime_note = next(item for item in payload["data"]["command_queue"] if item["command"].startswith("market-intel journal note --section"))
    assert runtime_archive["runnable"] is True
    assert runtime_note["runnable"] is True
    assert runtime_note["run_after_rank"] == runtime_archive["rank"]


def test_daily_text_renderer():
    payload = handle_daily("ai-energy", use_mock=True, top=3)
    text = render_daily_report_text(payload)

    assert "market-intel daily" in text
    assert "数据检查" in text
    assert "链路地图" in text
    assert "持仓复核" in text
    assert "组合暴露" in text
    assert "复盘路径" in text
    assert "先处理数据可信度" in text
    assert "今日复核任务" in text
    assert "标的复核队列" in text
    assert "队列分" in text
    assert "标的风险画像" in text
    assert "登记:" in text
    assert "风险汇总" in text
    assert "主题集中" in text
    assert "核对:" in text
    assert "记录: market-intel journal note --section" in text
    assert "前置:" in text
    assert "留档入口" in text
    assert "命令队列" in text
    assert "需前置 | 写入 | market-intel journal save --runtime --json" in text
    assert "market-intel journal latest --text" in text
    assert "重复链路" in text
    assert "中际旭创" in text
    assert "market-intel portfolio explain 300308 --mock --text" in text
    assert "market-intel portfolio review --mock --text" in text
    assert "下一步问题" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_daily_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "daily",
            "--mock",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel daily" in result.stdout
    assert "观察清单" in result.stdout


def test_daily_command_queue_runnable_commands_parse(cli_cmd):
    payload = handle_daily("ai-energy", use_mock=True, top=3, map_top=2)
    commands = [item["command"] for item in payload["data"]["command_queue"] if item.get("runnable") and "journal note" not in item["command"]]

    for command in commands:
        result = subprocess.run(
            cli_cmd(*shlex.split(command)[1:]),
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, command
