import json
import subprocess

from market_intel.cli import handle_import_holdings, handle_import_quotes, handle_portfolio_explain, handle_portfolio_review
from market_intel.core.fixtures import load_mock_holdings, load_mock_quotes
from market_intel.core.pool_loader import load_pool
from market_intel.core.portfolio import build_portfolio_explain, build_portfolio_review
from market_intel.core.text_report import render_portfolio_explain_text, render_portfolio_review_text


def test_portfolio_review_mock_shape():
    report = build_portfolio_review(load_pool(), load_mock_quotes(), load_mock_holdings(), top=5)

    assert report["holding_count"] == 5
    assert report["review_count"] == 5
    assert report["items"][0]["priority"] in {"high_review", "medium_review", "normal_review"}
    assert report["items"][0]["review_points"]
    assert report["risk_flags"]
    assert report["agent_contract"]["stable_fields"]


def test_portfolio_review_cli_requires_source():
    payload = handle_portfolio_review("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "PORTFOLIO_REVIEW_SOURCE_REQUIRED"


def test_portfolio_explain_mock_shape():
    report = build_portfolio_explain(load_pool(), load_mock_quotes(), load_mock_holdings(), "300308")

    assert report["found"] is True
    assert report["symbol"] == "300308"
    assert report["item"]["symbol"] == "300308"
    assert report["item"]["review_points"]
    assert report["related"]["same_exposure"] or report["related"]["same_overlap_group"]
    assert report["next_commands"]


def test_portfolio_explain_not_found():
    report = build_portfolio_explain(load_pool(), load_mock_quotes(), load_mock_holdings(), "000000")

    assert report["found"] is False
    assert report["errors"][0]["code"] == "PORTFOLIO_ITEM_NOT_FOUND"
    assert report["next_commands"]


def test_portfolio_explain_cli_requires_source():
    payload = handle_portfolio_explain("ai-energy", "002837", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "PORTFOLIO_EXPLAIN_SOURCE_REQUIRED"


def test_portfolio_review_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_portfolio_review("ai-energy", use_mock=False, use_runtime=True, top=3)

    assert payload["ok"] is True
    assert payload["command"] == "portfolio.review"
    assert payload["data"]["mode"] == "runtime"
    assert payload["data"]["review_count"] == 3
    assert payload["data"]["items"][0]["has_quote"] is True


def test_portfolio_explain_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_portfolio_explain("ai-energy", "002837", use_mock=False, use_runtime=True)

    assert payload["ok"] is True
    assert payload["command"] == "portfolio.explain"
    assert payload["data"]["found"] is True
    assert payload["data"]["item"]["has_quote"] is True
    assert payload["data"]["mode"] == "runtime"


def test_portfolio_explain_accepts_common_a_share_symbol_formats(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    payload = handle_portfolio_explain("ai-energy", "SZ:300308", use_mock=False, use_runtime=True)

    assert payload["ok"] is True
    assert payload["data"]["symbol"] == "300308"
    assert payload["data"]["item"]["symbol"] == "300308"


def test_portfolio_review_detects_missing_quote(tmp_path):
    quotes_path = tmp_path / "quotes.json"
    holdings_path = tmp_path / "holdings.json"
    quotes_path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002837",
                        "trade_date": "2026-06-06",
                        "last_price": 36.8,
                        "change_pct": 7.2,
                        "amount": 12.3,
                        "amount_ratio": 2.7,
                        "turnover_rate": 6,
                        "amplitude_pct": 8.4,
                        "is_limit_up": False,
                        "is_stage_high": True,
                        "intraday_fade_pct": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    holdings_path.write_text(
        json.dumps(
            {
                "holdings": [
                    {"symbol": "002837", "name": "英维克"},
                    {"symbol": "300308", "name": "中际旭创"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = handle_portfolio_review(
        "ai-energy",
        use_mock=False,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )
    missing = [item for item in payload["data"]["items"] if item["symbol"] == "300308"][0]

    assert payload["ok"] is True
    assert missing["has_quote"] is False
    assert "holding_missing_quote" in missing["risk_flags"]
    assert missing["review_points"]


def test_portfolio_review_normalizes_runtime_json_symbol_formats(tmp_path):
    quotes_path = tmp_path / "quotes.json"
    holdings_path = tmp_path / "holdings.json"
    quotes_path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "300308.SZ",
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
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    holdings_path.write_text(
        json.dumps({"holdings": [{"symbol": "SZ:300308", "name": "中际旭创"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    review_payload = handle_portfolio_review(
        "ai-energy",
        use_mock=False,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )
    explain_payload = handle_portfolio_explain(
        "ai-energy",
        "300308",
        use_mock=False,
        quotes_file=str(quotes_path),
        holdings_file=str(holdings_path),
    )

    assert review_payload["ok"] is True
    assert review_payload["data"]["items"][0]["symbol"] == "300308"
    assert review_payload["data"]["items"][0]["has_quote"] is True
    assert explain_payload["ok"] is True
    assert explain_payload["data"]["found"] is True
    assert explain_payload["data"]["item"]["symbol"] == "300308"


def test_portfolio_review_text_renderer():
    payload = handle_portfolio_review("ai-energy", use_mock=True, top=4)
    text = render_portfolio_review_text(payload)

    assert "market-intel portfolio review" in text
    assert "持仓复核" in text
    assert "重复暴露" in text
    assert "重复链路" in text
    assert "光通信" in text
    assert "中际旭创" in text
    assert "待复核问题" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_portfolio_explain_text_renderer():
    payload = handle_portfolio_explain("ai-energy", "300308", use_mock=True)
    text = render_portfolio_explain_text(payload)

    assert "market-intel portfolio explain" in text
    assert "相关持仓" in text
    assert "复核问题" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_portfolio_explain_missing_text_renderer():
    payload = handle_portfolio_explain("ai-energy", "000000", use_mock=True)
    text = render_portfolio_explain_text(payload)

    assert payload["ok"] is False
    assert "market-intel portfolio explain" in text
    assert "下一步" in text


def test_portfolio_review_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "portfolio",
            "review",
            "--mock",
            "--top",
            "3",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel portfolio review" in result.stdout
    assert "持仓复核" in result.stdout


def test_portfolio_explain_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "portfolio",
            "explain",
            "300308",
            "--mock",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel portfolio explain" in result.stdout
    assert "相关持仓" in result.stdout
