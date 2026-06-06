import json
import subprocess

from market_intel.cli import (
    handle_daily,
    handle_import_holdings,
    handle_import_quotes,
    handle_import_schema,
)
from market_intel.core.fixtures import load_holdings_file, load_quotes_file


def test_import_schema_is_agent_friendly():
    payload = handle_import_schema()

    assert payload["ok"] is True
    assert payload["command"] == "import.schema"
    assert payload["data"]["agent_contract"]["success"]
    assert payload["data"]["quotes"]["accepted_columns"]["symbol"]
    assert payload["data"]["holdings"]["canonical_schema"]


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
    assert preview["trade_date"] == "2026-06-06"
    assert preview["amount"] == 1230000000.0
    assert any(warning["code"] == "QUOTE_FIELD_DEFAULTED" for warning in payload["warnings"])


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


def test_import_schema_cli_smoke():
    result = subprocess.run(
        [".venv/bin/market-intel", "import", "schema", "--json"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["data"]["agent_contract"]


def test_import_quotes_cli_smoke(tmp_path):
    csv_path = tmp_path / "quotes.csv"
    csv_path.write_text("证券代码,涨跌幅\n002837,7.2%\n", encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/market-intel",
            "import",
            "quotes",
            str(csv_path),
            "--dry-run",
            "--trade-date",
            "2026-06-06",
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["data"]["preview"][0]["symbol"] == "002837"
