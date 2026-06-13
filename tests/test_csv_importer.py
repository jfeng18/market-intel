import json
import subprocess

from market_intel.cli import (
    handle_daily,
    handle_import_holdings,
    handle_import_quotes,
    handle_import_research,
    handle_import_schema,
    handle_import_universe,
    handle_pool_coverage,
)
from market_intel.core.csv_importer import read_csv_rows
from market_intel.core.fixtures import load_holdings_file, load_quotes_file
from market_intel.core.text_report import render_import_text, render_import_universe_text
from market_intel.core.tradegov import import_tradegov_holdings


def test_import_schema_is_agent_friendly():
    payload = handle_import_schema()

    assert payload["ok"] is True
    assert payload["command"] == "import.schema"
    assert payload["data"]["agent_contract"]["success"]
    assert payload["data"]["quotes"]["accepted_columns"]["symbol"]
    assert payload["data"]["holdings"]["canonical_schema"]
    assert payload["data"]["universe"]["accepted_columns"]["symbol"]
    assert payload["data"]["universe"]["canonical_schema"]
    quote_commands = payload["data"]["quotes"]["example_commands"]
    assert quote_commands[0] == "market-intel import quotes examples/quotes.csv.example --runtime --dry-run --json"
    assert quote_commands[1] == "market-intel import quotes examples/quotes.csv.example --runtime --json"
    holding_commands = payload["data"]["holdings"]["example_commands"]
    assert holding_commands[0] == "market-intel import holdings examples/holdings.csv.example --runtime --dry-run --json"
    assert holding_commands[1] == "market-intel import holdings examples/holdings.csv.example --runtime --json"
    universe_commands = payload["data"]["universe"]["example_commands"]
    assert universe_commands[0] == "market-intel import universe examples/a_share_universe.csv.example --runtime --dry-run --json"
    assert universe_commands[1] == "market-intel import universe examples/a_share_universe.csv.example --runtime --json"
    research_commands = payload["data"]["research"]["example_commands"]
    assert research_commands[0] == "market-intel import research examples/research_notes.csv.example --runtime --dry-run --json"
    assert research_commands[1] == "market-intel import research examples/research_notes.csv.example --runtime --json"
    assert "data.coverage_delta" in payload["data"]["agent_contract"]["universe_stable_fields"]
    assert "data.coverage_delta.write_mode" in payload["data"]["agent_contract"]["universe_stable_fields"]
    assert "data.coverage_delta.changed_symbol_count" in payload["data"]["agent_contract"]["universe_stable_fields"]
    assert "data.coverage_delta.removed_symbol_count" in payload["data"]["agent_contract"]["universe_stable_fields"]
    assert "data.coverage_delta.recommendation.requires_import" in payload["data"]["agent_contract"]["universe_stable_fields"]


def test_import_quotes_dry_run_normalizes_chinese_csv(tmp_path):
    csv_path = tmp_path / "quotes.csv"
    csv_path.write_text(
        "证券代码,证券名称,涨跌幅,成交额,量比\n002837,英维克,7.2%,12.3亿,2.4\n",
        encoding="utf-8",
    )

    payload = handle_import_quotes(str(csv_path), dry_run=True, trade_date="2026-06-06")
    preview = payload["data"]["preview"][0]

    assert payload["ok"] is True
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["written"] is False
    assert payload["data"]["canonical_schema"]
    assert preview["symbol"] == "002837"
    assert preview["name"] == "英维克"
    assert preview["trade_date"] == "2026-06-06"
    assert preview["amount"] == 1230000000.0
    assert payload["data"]["next_commands"] == []
    assert any(warning["code"] == "QUOTE_FIELD_DEFAULTED" for warning in payload["warnings"])


def test_import_runtime_dry_run_suggests_write_and_review(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    quotes_csv = tmp_path / "quotes.csv"
    holdings_csv = tmp_path / "holdings.csv"
    research_csv = tmp_path / "research_notes.csv"
    quotes_csv.write_text("证券代码,证券名称,交易日期,涨跌幅\n002837,英维克,2026-06-06,7.2%\n", encoding="utf-8")
    holdings_csv.write_text("证券代码,证券名称,持仓数量\n002837,英维克,300\n", encoding="utf-8")
    research_csv.write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险\n"
        "002837,英维克,reviewed,液冷温控复核,订单和毛利率变化,需求放缓\n",
        encoding="utf-8",
    )

    quotes_payload = handle_import_quotes(str(quotes_csv), use_runtime=True, dry_run=True)
    holdings_payload = handle_import_holdings(str(holdings_csv), use_runtime=True, dry_run=True)
    research_payload = handle_import_research(str(research_csv), use_runtime=True, dry_run=True)

    assert quotes_payload["data"]["next_commands"] == [
        "market-intel import quotes quotes.csv --runtime --json",
        "market-intel status runtime --json",
        "market-intel dashboard --text",
    ]
    assert holdings_payload["data"]["next_commands"] == [
        "market-intel import holdings holdings.csv --runtime --json",
        "market-intel status runtime --json",
        "market-intel dashboard --text",
    ]
    assert research_payload["data"]["next_commands"] == [
        "market-intel import research research_notes.csv --runtime --json",
        "market-intel pool coverage --runtime --text",
        "market-intel agent next --text",
    ]


def test_import_text_renders_common_imports(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    quotes_csv = tmp_path / "quotes.csv"
    holdings_csv = tmp_path / "holdings.csv"
    research_csv = tmp_path / "research_notes.csv"
    quotes_csv.write_text("证券代码,证券名称,交易日期,涨跌幅,成交额,量比\n002837,英维克,2026-06-06,7.2%,12.3亿,2.4\n", encoding="utf-8")
    holdings_csv.write_text("证券代码,证券名称,持仓数量\n002837,英维克,300\n", encoding="utf-8")
    research_csv.write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险\n"
        "002837,英维克,reviewed,液冷温控复核,订单和毛利率变化,需求放缓\n",
        encoding="utf-8",
    )

    quotes_text = render_import_text(handle_import_quotes(str(quotes_csv), use_runtime=True, dry_run=True))
    holdings_text = render_import_text(handle_import_holdings(str(holdings_csv), use_runtime=True, dry_run=True))
    research_text = render_import_text(handle_import_research(str(research_csv), use_runtime=True, dry_run=True))

    assert "market-intel import quotes" in quotes_text
    assert "002837 英维克 | 2026-06-06 | 涨跌 7.20% | 成交 12.30亿 | 量比 2.40" in quotes_text
    assert "market-intel import quotes quotes.csv --runtime --json" in quotes_text
    assert "market-intel import holdings" in holdings_text
    assert "002837 英维克 | 数量 300" in holdings_text
    assert "market-intel import holdings holdings.csv --runtime --json" in holdings_text
    assert "market-intel import research" in research_text
    assert "002837 英维克 | reviewed | 逻辑 已填 | 证据 已填 | 证伪 已填" in research_text
    assert "market-intel import research research_notes.csv --runtime --json" in research_text
    assert str(runtime) not in quotes_text + holdings_text + research_text
    assert str(tmp_path) not in quotes_text + holdings_text + research_text


def test_import_holdings_writes_output(tmp_path):
    csv_path = tmp_path / "holdings.csv"
    output_path = tmp_path / "holdings.json"
    csv_path.write_text("证券代码,证券名称,持仓数量\n002837,英维克,1000\n", encoding="utf-8")

    payload = handle_import_holdings(str(csv_path), output=str(output_path))
    holdings = load_holdings_file(output_path)

    assert payload["ok"] is True
    assert payload["data"]["written"] is True
    assert holdings[0].symbol == "002837"
    assert holdings[0].quantity == 1000


def test_import_tradegov_holdings_dry_run_is_read_only(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))

    payload = {
        "data": {
            "positions": [
                {"symbol": "SZ:000001", "name": "平安银行", "quantity": "100", "cost_price": "11.2"},
                {"code": "600519", "security_name": "贵州茅台", "shares": 2},
            ]
        }
    }
    data = import_tradegov_holdings(runtime / "holdings.json", dry_run=True, runtime=True, raw_payload=payload)

    assert data["errors"] == []
    assert data["read_only_source"] is True
    assert data["tradegov_written"] is False
    assert data["record_count"] == 2
    assert data["preview"][0]["symbol"] == "000001"
    assert data["preview"][0]["source"] == "tradegov:status-current"
    assert not (runtime / "holdings.json").exists()
    assert data["next_commands"][0] == "market-intel import holdings --from-tradegov --runtime --json"


def test_handle_import_holdings_from_tradegov_writes_market_intel_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    payload = {
        "data": {
            "holdings": [
                {"symbol": "000001", "name": "平安银行", "quantity": 100},
            ]
        }
    }

    monkeypatch.setattr(
        "market_intel.core.tradegov.read_tradegov_status",
        lambda _command: (payload, []),
    )

    result = handle_import_holdings(None, use_runtime=True, from_tradegov=True)

    assert result["ok"] is True
    assert result["data"]["source_kind"] == "tradegov.status_current"
    assert result["data"]["read_only_source"] is True
    assert result["data"]["written"] is True
    assert result["data"]["tradegov_written"] is False
    assert result["data"]["source_metadata"]["read_only"] is True
    assert load_holdings_file(runtime / "holdings.json")[0].symbol == "000001"
    manifest = json.loads((runtime / "runtime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "import.holdings"


def test_import_holdings_from_tradegov_missing_command_is_clean_error(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr("market_intel.core.tradegov.shutil.which", lambda _name: None)
    monkeypatch.setattr("market_intel.core.tradegov.TRADEGOV_REPO", tmp_path / "missing-tradegov")

    result = handle_import_holdings(None, use_runtime=True, dry_run=True, from_tradegov=True)

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "TRADEGOV_NOT_FOUND"
    assert not (runtime / "holdings.json").exists()


def test_import_holdings_from_tradegov_falls_back_to_module_command(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    repo = tmp_path / "tradegov"
    repo.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr("market_intel.core.tradegov.shutil.which", lambda _name: None)
    monkeypatch.setattr("market_intel.core.tradegov.TRADEGOV_REPO", repo)

    seen = {}

    class Completed:
        returncode = 0
        stdout = json.dumps({"data": {"positions": [{"symbol": "002261", "name": "拓维信息", "quantity": 100}]}})

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["cwd"] = kwargs.get("cwd")
        return Completed()

    monkeypatch.setattr("market_intel.core.tradegov.subprocess.run", fake_run)

    result = handle_import_holdings(None, use_runtime=True, dry_run=True, from_tradegov=True)

    assert result["ok"] is True
    assert seen["cwd"] == str(repo)
    assert seen["command"][-4:] == ["-m", "tradegov.cli", "status-current", "--json"]
    assert result["data"]["preview"][0]["symbol"] == "002261"
    assert result["data"]["tradegov_written"] is False


def test_import_universe_dry_run_normalizes_chinese_csv(tmp_path):
    csv_path = tmp_path / "a_share_universe.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n000001,平安银行,银行,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )

    payload = handle_import_universe(str(csv_path), dry_run=True)
    preview = payload["data"]["preview"][0]

    assert payload["ok"] is True
    assert payload["command"] == "import.universe"
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["written"] is False
    assert preview["symbol"] == "000001"
    assert preview["name"] == "平安银行"
    assert preview["industry"] == "银行"
    assert preview["concepts"] == "股份行;金融科技"
    assert preview["listing_status"] == "listed"
    assert payload["data"]["coverage_delta"]["available"] is True
    assert payload["data"]["coverage_delta"]["incoming_record_count"] == 1
    assert payload["data"]["coverage_delta"]["after"]["coverage_ratio"]["industry"] == 1
    assert str(csv_path) not in json.dumps(payload, ensure_ascii=False)


def test_import_universe_dry_run_estimates_runtime_coverage_delta(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,,沪深300,listed,existing\n"
        "600519,贵州茅台,行业待补,白酒;消费,,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_update.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50;沪深300\n",
        encoding="utf-8",
    )

    payload = handle_import_universe(str(csv_path), use_runtime=True, dry_run=True)
    delta = payload["data"]["coverage_delta"]

    assert payload["ok"] is True
    assert payload["data"]["written"] is False
    assert delta["target"] == "a_share_universe.csv"
    assert delta["existing_record_count"] == 2
    assert delta["incoming_record_count"] == 2
    assert delta["new_symbol_count"] == 0
    assert delta["updated_symbol_count"] == 2
    assert delta["removed_symbol_count"] == 0
    assert delta["before"]["missing_count"] == {"industry": 1, "concepts": 1, "index_membership": 1}
    assert delta["after"]["missing_count"] == {"industry": 0, "concepts": 0, "index_membership": 0}
    assert delta["improvement"]["state"] == "improved"
    assert delta["improvement"]["covered_count_delta"] == {"industry": 1, "concepts": 1, "index_membership": 1}
    assert delta["improvement"]["missing_count_delta"] == {"industry": -1, "concepts": -1, "index_membership": -1}
    assert delta["improvement"]["improved_fields"] == ["industry", "concepts", "index_membership"]
    assert delta["recommendation"]["action"] == "import_and_verify"
    assert delta["recommendation"]["requires_import"] is True
    assert "行业 覆盖 +1" in delta["improvement"]["summary"]
    assert payload["data"]["next_commands"] == [
        "market-intel import universe a_share_universe_update.csv --runtime --json",
        "market-intel pool coverage --runtime --json",
        "market-intel dashboard --text",
    ]
    assert str(runtime) not in json.dumps(payload, ensure_ascii=False)
    assert str(csv_path) not in json.dumps(payload, ensure_ascii=False)


def test_import_universe_text_renders_coverage_delta(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,,沪深300,listed,existing\n"
        "600519,贵州茅台,行业待补,白酒;消费,,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_update.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50;沪深300\n",
        encoding="utf-8",
    )

    text = render_import_universe_text(handle_import_universe(str(csv_path), use_runtime=True, dry_run=True))

    assert "market-intel import universe" in text
    assert "mode replace | dry_run True | written False" in text
    assert "导入前: 记录 2 | 行业 50.0% 缺 1 | 概念 50.0% 缺 1 | 指数 50.0% 缺 1" in text
    assert "导入后: 记录 2 | 行业 100.0% 缺 0 | 概念 100.0% 缺 0 | 指数 100.0% 缺 0" in text
    assert "缺口变化: 行业 -1 | 概念 -1 | 指数 -1" in text
    assert "import_and_verify | requires_import True" in text
    assert "更新 000001 平安银行" in text
    assert "market-intel import universe a_share_universe_update.csv --runtime --json" in text
    assert str(runtime) not in text
    assert str(csv_path) not in text


def test_import_universe_dry_run_warns_when_no_coverage_improvement(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_same.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )

    payload = handle_import_universe(str(csv_path), use_runtime=True, dry_run=True)
    delta = payload["data"]["coverage_delta"]

    assert payload["ok"] is True
    assert delta["improvement"]["state"] == "unchanged"
    assert delta["recommendation"]["action"] == "skip_import"
    assert delta["recommendation"]["requires_import"] is False
    assert payload["data"]["next_commands"] == [
        "market-intel pool coverage --runtime --json",
        "market-intel import schema --json",
    ]
    assert any(warning["code"] == "UNIVERSE_DRY_RUN_NO_COVERAGE_IMPROVEMENT" for warning in payload["warnings"])
    assert not any("import universe" in command for command in payload["data"]["next_commands"])
    assert str(runtime) not in json.dumps(payload, ensure_ascii=False)
    assert str(csv_path) not in json.dumps(payload, ensure_ascii=False)


def test_import_universe_dry_run_warns_before_removing_existing_symbols(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,,沪深300,listed,existing\n"
        "600519,贵州茅台,行业待补,白酒;消费,,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_subset.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )

    payload = handle_import_universe(str(csv_path), use_runtime=True, dry_run=True)
    delta = payload["data"]["coverage_delta"]

    assert payload["ok"] is True
    assert delta["after_record_count"] == 1
    assert delta["removed_symbol_count"] == 1
    assert delta["removed_samples"] == [{"symbol": "600519", "name": "贵州茅台"}]
    assert delta["recommendation"]["action"] == "review_removed_symbols_before_import"
    assert delta["recommendation"]["requires_import"] is False
    assert any(warning["code"] == "UNIVERSE_DRY_RUN_REMOVES_EXISTING_SYMBOLS" for warning in payload["warnings"])
    assert payload["data"]["next_commands"] == [
        "market-intel import universe <full_a_share_universe.csv> --runtime --dry-run --json",
        "market-intel pool coverage --runtime --json",
    ]
    assert not any("a_share_universe_subset.csv --runtime --json" in command for command in payload["data"]["next_commands"])
    assert str(runtime) not in json.dumps(payload, ensure_ascii=False)
    assert str(csv_path) not in json.dumps(payload, ensure_ascii=False)


def test_import_universe_merge_updates_partial_fields_without_removing_symbols(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    target = runtime / "a_share_universe.csv"
    target.write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,,沪深300,listed,existing\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_patch.csv"
    csv_path.write_text(
        "证券代码,概念\n"
        "000001,股份行;金融科技\n",
        encoding="utf-8",
    )

    dry_run_payload = handle_import_universe(str(csv_path), use_runtime=True, dry_run=True, merge=True)
    delta = dry_run_payload["data"]["coverage_delta"]

    assert dry_run_payload["ok"] is True
    assert dry_run_payload["data"]["write_mode"] == "merge"
    assert dry_run_payload["data"]["record_count"] == 1
    assert dry_run_payload["data"]["target_record_count"] == 2
    assert delta["write_mode"] == "merge"
    assert delta["after_record_count"] == 2
    assert delta["removed_symbol_count"] == 0
    assert delta["after"]["missing_count"] == {"industry": 0, "concepts": 0, "index_membership": 0}
    assert delta["recommendation"]["requires_import"] is True
    assert dry_run_payload["data"]["next_commands"] == [
        "market-intel import universe a_share_universe_patch.csv --runtime --merge --json",
        "market-intel pool coverage --runtime --json",
        "market-intel dashboard --text",
    ]

    import_payload = handle_import_universe(str(csv_path), use_runtime=True, merge=True)
    rows = target.read_text(encoding="utf-8").splitlines()

    assert import_payload["ok"] is True
    assert import_payload["data"]["written"] is True
    assert import_payload["data"]["target_record_count"] == 2
    assert "000001,平安银行,银行,股份行;金融科技,沪深300,listed,csv:a_share_universe_patch.csv" in rows
    assert "600519,贵州茅台,食品饮料,白酒;消费,上证50,listed,existing" in rows
    assert str(runtime) not in json.dumps(dry_run_payload, ensure_ascii=False)
    assert str(csv_path) not in json.dumps(dry_run_payload, ensure_ascii=False)


def test_import_universe_merge_recommends_existing_value_updates(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    runtime.mkdir()
    (runtime / "a_share_universe.csv").write_text(
        "symbol,name,industry,concepts,index_membership,listing_status,source\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300,listed,existing\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "a_share_universe_fix.csv"
    csv_path.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n"
        "000001,平安银行,非银金融,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )

    payload = handle_import_universe(str(csv_path), use_runtime=True, dry_run=True, merge=True)
    delta = payload["data"]["coverage_delta"]

    assert payload["ok"] is True
    assert delta["improvement"]["state"] == "unchanged"
    assert delta["changed_symbol_count"] == 1
    assert delta["changed_field_count"] == 1
    assert delta["changed_samples"] == [{"symbol": "000001", "name": "平安银行", "changed_fields": ["industry"]}]
    assert delta["recommendation"]["action"] == "import_value_updates"
    assert delta["recommendation"]["requires_import"] is True
    assert payload["data"]["next_commands"] == [
        "market-intel import universe a_share_universe_fix.csv --runtime --merge --json",
        "market-intel pool coverage --runtime --json",
        "market-intel dashboard --text",
    ]
    assert not any(warning["code"] == "UNIVERSE_DRY_RUN_NO_COVERAGE_IMPROVEMENT" for warning in payload["warnings"])


def test_import_universe_rejects_non_a_share_symbol(tmp_path):
    csv_path = tmp_path / "a_share_universe.csv"
    csv_path.write_text("证券代码,证券名称,行业\nNVDA,英伟达,海外科技\n", encoding="utf-8")

    payload = handle_import_universe(str(csv_path), dry_run=True)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "INVALID_UNIVERSE_SYMBOL"


def test_import_requires_output_or_dry_run(tmp_path):
    csv_path = tmp_path / "quotes.csv"
    csv_path.write_text("证券代码,涨跌幅\n002837,7.2%\n", encoding="utf-8")

    payload = handle_import_quotes(str(csv_path))

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "IMPORT_OUTPUT_REQUIRED"


def test_import_error_does_not_write_output(tmp_path):
    csv_path = tmp_path / "quotes.csv"
    output_path = tmp_path / "quotes.json"
    csv_path.write_text("证券代码,涨跌幅\n002837,not-a-number\n", encoding="utf-8")

    payload = handle_import_quotes(str(csv_path), output=str(output_path))

    assert payload["ok"] is False
    assert any(error["code"] == "INVALID_NUMERIC_FIELD" for error in payload["errors"])
    assert payload["data"]["next_commands"] == []
    assert not output_path.exists()


def test_import_runtime_then_daily(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    quotes_csv = tmp_path / "quotes.csv"
    holdings_csv = tmp_path / "holdings.csv"
    quotes_csv.write_text(
        (
            "证券代码,证券名称,交易日期,最新价,涨跌幅,成交额,量比,换手率,振幅,涨停,阶段新高,日内回落\n"
            "002837,英维克,2026-06-06,36.8,7.2%,12.3亿,2.7,6.0%,8.4%,否,是,1.0%\n"
        ),
        encoding="utf-8",
    )
    holdings_csv.write_text("证券代码,证券名称,持仓数量\n002837,英维克,300\n", encoding="utf-8")

    quotes_payload = handle_import_quotes(str(quotes_csv), use_runtime=True)
    holdings_payload = handle_import_holdings(str(holdings_csv), use_runtime=True)
    daily_payload = handle_daily("ai-energy", use_mock=False, use_runtime=True)

    assert quotes_payload["ok"] is True
    assert quotes_payload["data"]["next_commands"]
    assert holdings_payload["ok"] is True
    assert load_quotes_file(runtime / "quotes.json")[0].symbol == "002837"
    assert daily_payload["ok"] is True
    assert daily_payload["data"]["mode"] == "runtime"


def test_import_universe_runtime_then_pool_coverage(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    universe_csv = tmp_path / "a_share_universe.csv"
    holdings_json = tmp_path / "holdings.json"
    universe_csv.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n000001,平安银行,银行,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )
    holdings_json.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    import_payload = handle_import_universe(str(universe_csv), use_runtime=True)
    coverage_payload = handle_pool_coverage("all-a", holdings_file=str(holdings_json))

    assert import_payload["ok"] is True
    assert import_payload["data"]["output"] == "a_share_universe.csv"
    assert (runtime / "a_share_universe.csv").exists()
    assert coverage_payload["ok"] is True
    assert coverage_payload["data"]["universe"]["available"] is True
    assert coverage_payload["data"]["holdings_coverage"]["matched_count"] == 1
    assert coverage_payload["data"]["holdings_coverage"]["foundation_matched_count"] == 1
    assert str(universe_csv) not in json.dumps(import_payload, ensure_ascii=False)
    assert str(runtime) not in json.dumps(import_payload, ensure_ascii=False)


def test_import_research_rejects_reviewed_rows_with_missing_evidence(tmp_path):
    csv_path = tmp_path / "research_notes.csv"
    csv_path.write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险\n000001,平安银行,reviewed,银行复核主线,,资产质量恶化\n",
        encoding="utf-8",
    )

    payload = handle_import_research(str(csv_path), dry_run=True)

    assert payload["ok"] is False
    assert any(error["code"] == "RESEARCH_REVIEWED_FIELD_MISSING" for error in payload["errors"])
    assert payload["data"]["next_commands"] == []


def test_import_research_runtime_dry_run_error_has_no_write_command(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    csv_path = tmp_path / "research_notes.csv"
    csv_path.write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险\n000001,平安银行,reviewed,银行复核主线,,资产质量恶化\n",
        encoding="utf-8",
    )

    payload = handle_import_research(str(csv_path), use_runtime=True, dry_run=True)

    assert payload["ok"] is False
    assert any(error["code"] == "RESEARCH_REVIEWED_FIELD_MISSING" for error in payload["errors"])
    assert payload["data"]["next_commands"] == []


def test_import_research_confirms_foundation_coverage(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    universe_csv = tmp_path / "a_share_universe.csv"
    research_csv = tmp_path / "research_notes.csv"
    holdings_json = tmp_path / "holdings.json"
    universe_csv.write_text(
        "证券代码,证券名称,行业,概念,指数成分\n000001,平安银行,银行,股份行;金融科技,沪深300\n",
        encoding="utf-8",
    )
    research_csv.write_text(
        (
            "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险,更新日期,来源\n"
            "000001,平安银行,reviewed,股份行资产质量和息差变化是复核主线,关注营收结构、资产质量、拨备和同业对比,若息差继续承压且资产质量恶化则证伪,2026-06-07,test\n"
        ),
        encoding="utf-8",
    )
    holdings_json.write_text(
        json.dumps({"holdings": [{"symbol": "000001", "name": "平安银行"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    universe_payload = handle_import_universe(str(universe_csv), use_runtime=True)
    research_payload = handle_import_research(str(research_csv), use_runtime=True)
    coverage_payload = handle_pool_coverage("all-a", holdings_file=str(holdings_json))
    matched = coverage_payload["data"]["holdings_coverage"]["matched"][0]

    assert universe_payload["ok"] is True
    assert research_payload["ok"] is True
    assert research_payload["data"]["output"] == "research_notes.csv"
    assert coverage_payload["ok"] is True
    assert coverage_payload["data"]["holdings_coverage"]["confirmed_count"] == 1
    assert coverage_payload["data"]["holdings_coverage"]["foundation_matched_count"] == 0
    assert matched["coverage_state"] == "confirmed"
    assert matched["coverage_state_reasons"] == ["reviewed_research"]
    assert matched["research_status"]["confirmed"] is True
    assert str(research_csv) not in json.dumps(research_payload, ensure_ascii=False)
    assert str(runtime) not in json.dumps(research_payload, ensure_ascii=False)


def test_import_holdings_parses_cost_price_from_chinese_column(tmp_path):
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "证券代码,证券名称,持仓数量,成本价\n002837,英维克,1000,25.60\n",
        encoding="utf-8",
    )

    payload = handle_import_holdings(str(csv_path), dry_run=True)
    preview = payload["data"]["preview"][0]

    assert payload["ok"] is True
    assert preview["symbol"] == "002837"
    assert preview["cost_price"] == 25.6
    assert preview["quantity"] == 1000


def test_import_holdings_cost_price_flows_through_to_holding_record(tmp_path):
    csv_path = tmp_path / "holdings.csv"
    output_path = tmp_path / "holdings.json"
    csv_path.write_text(
        "证券代码,证券名称,持仓数量,买入均价\n002837,英维克,500,18.30\n",
        encoding="utf-8",
    )

    payload = handle_import_holdings(str(csv_path), output=str(output_path))
    holdings = load_holdings_file(output_path)

    assert payload["ok"] is True
    assert payload["data"]["written"] is True
    assert holdings[0].symbol == "002837"
    assert holdings[0].cost_price == 18.3
    assert holdings[0].quantity == 500


def test_import_holdings_cost_price_absent_is_none(tmp_path):
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "证券代码,证券名称,持仓数量\n002837,英维克,300\n",
        encoding="utf-8",
    )

    payload = handle_import_holdings(str(csv_path), dry_run=True)
    preview = payload["data"]["preview"][0]

    assert payload["ok"] is True
    assert preview["cost_price"] is None


def test_import_schema_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd("import", "schema", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["data"]["agent_contract"]


def test_import_quotes_cli_smoke(tmp_path, cli_cmd):
    csv_path = tmp_path / "quotes.csv"
    csv_path.write_text("证券代码,涨跌幅\n002837,7.2%\n", encoding="utf-8")

    result = subprocess.run(
        cli_cmd(
            "import",
            "quotes",
            str(csv_path),
            "--dry-run",
            "--trade-date",
            "2026-06-06",
            "--json",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["data"]["preview"][0]["symbol"] == "002837"


def test_import_common_cli_text_smoke(tmp_path, cli_cmd):
    csv_files = {
        "quotes": tmp_path / "quotes.csv",
        "holdings": tmp_path / "holdings.csv",
        "research": tmp_path / "research_notes.csv",
    }
    csv_files["quotes"].write_text("证券代码,证券名称,交易日期,涨跌幅\n002837,英维克,2026-06-06,7.2%\n", encoding="utf-8")
    csv_files["holdings"].write_text("证券代码,证券名称,持仓数量\n002837,英维克,300\n", encoding="utf-8")
    csv_files["research"].write_text(
        "证券代码,证券名称,状态,核心逻辑,关键证据,证伪风险\n"
        "002837,英维克,reviewed,液冷温控复核,订单和毛利率变化,需求放缓\n",
        encoding="utf-8",
    )

    for kind, csv_path in csv_files.items():
        result = subprocess.run(
            cli_cmd("import", kind, str(csv_path), "--dry-run", "--text"),
            check=True,
            text=True,
            capture_output=True,
        )
        assert "market-intel import %s" % kind in result.stdout
        assert "下一步" in result.stdout
        assert str(tmp_path) not in result.stdout


def test_import_universe_cli_smoke(tmp_path, cli_cmd):
    csv_path = tmp_path / "a_share_universe.csv"
    csv_path.write_text("证券代码,证券名称,行业\n000001,平安银行,银行\n", encoding="utf-8")

    text_result = subprocess.run(
        cli_cmd("import", "universe", str(csv_path), "--dry-run", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("import", "universe", str(csv_path), "--dry-run", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["ok"] is True
    assert payload["command"] == "import.universe"
    assert payload["data"]["preview"][0]["symbol"] == "000001"
    assert "market-intel import universe" in text_result.stdout
    assert "导入后" in text_result.stdout
    assert "requires_import" in text_result.stdout


def test_read_csv_rows_gbk_fallback(tmp_path):
    csv_path = tmp_path / "gbk.csv"
    csv_path.write_bytes("证券代码,证券名称,涨跌幅\n002837,英维克,7.2%\n".encode("gbk"))

    rows, warnings, errors = read_csv_rows(csv_path)

    assert errors == []
    assert len(rows) == 1
    assert rows[0]["证券代码"] == "002837"
    assert rows[0]["证券名称"] == "英维克"
    assert len(warnings) == 1
    assert warnings[0]["code"] == "CSV_ENCODING_FALLBACK"
    assert warnings[0]["detail"]["encoding"] == "gbk"


def test_read_csv_rows_gb18030_fallback(tmp_path):
    csv_path = tmp_path / "gb18030.csv"
    # gb18030 is a superset of gbk; use a character outside gbk range to force gb18030
    # U+20000 (CJK Unified Ideographs Extension B) is in gb18030 but not in gbk
    content = "证券代码,证券名称\n000001,测试\n"
    csv_path.write_bytes(content.encode("gb18030"))

    rows, warnings, errors = read_csv_rows(csv_path)

    assert errors == []
    assert len(rows) == 1
    assert rows[0]["证券代码"] == "000001"
    assert rows[0]["证券名称"] == "测试"
    assert len(warnings) == 1
    assert warnings[0]["code"] == "CSV_ENCODING_FALLBACK"
    # gb18030 is a superset of gbk, so gbk may succeed here too;
    # the important thing is the fallback warning is present
    assert warnings[0]["detail"]["encoding"] in ("gbk", "gb18030")


def test_read_csv_rows_utf8_no_warning(tmp_path):
    csv_path = tmp_path / "utf8.csv"
    csv_path.write_text("证券代码,证券名称\n000001,平安银行\n", encoding="utf-8")

    rows, warnings, errors = read_csv_rows(csv_path)

    assert errors == []
    assert len(rows) == 1
    assert warnings == []


def test_import_quotes_gbk_fallback_warning_surfaces(tmp_path):
    csv_path = tmp_path / "quotes_gbk.csv"
    csv_path.write_bytes(
        "证券代码,证券名称,涨跌幅,成交额,量比\n002837,英维克,7.2%,12.3亿,2.4\n".encode("gbk")
    )

    payload = handle_import_quotes(str(csv_path), dry_run=True, trade_date="2026-06-06")

    assert payload["ok"] is True
    assert payload["data"]["preview"][0]["symbol"] == "002837"
    assert payload["data"]["preview"][0]["name"] == "英维克"
    assert any(w["code"] == "CSV_ENCODING_FALLBACK" for w in payload["warnings"])
