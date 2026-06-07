import json

from market_intel.cli import handle_init_runtime, handle_validate_runtime
from market_intel.core.models import Holding, Quote


def test_validate_runtime_after_init(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_validate_runtime("ai-energy")

    assert payload["ok"] is True
    assert payload["command"] == "validate.runtime"
    assert payload["data"]["summary"]["quote_count"] > 0
    assert payload["data"]["summary"]["holding_count"] > 0
    assert payload["errors"] == []
    assert payload["data"]["validation_warnings"] == []


def test_validate_runtime_warns_when_quotes_and_holdings_do_not_match(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    quote = {
        "symbol": "002837",
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
    (runtime / "quotes.json").write_text(
        json.dumps({"quotes": [quote]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "002261", "name": "拓维信息"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_validate_runtime("ai-energy")
    warning_codes = {warning["code"] for warning in payload["data"]["validation_warnings"]}

    assert payload["ok"] is True
    assert "HOLDING_WITHOUT_QUOTE" in warning_codes
    assert "QUOTE_NOT_IN_HOLDINGS" in warning_codes


def test_validate_runtime_missing_files(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_validate_runtime("ai-energy")

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "MISSING_RUNTIME_FILE"


def test_validate_runtime_missing_required_fields(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    (runtime / "quotes.json").write_text(
        json.dumps({"quotes": [{"symbol": "002837"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "002837", "name": "英维克"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_validate_runtime("ai-energy")

    assert payload["ok"] is False
    assert any(error["code"] == "MISSING_REQUIRED_FIELDS" for error in payload["errors"])


def test_validate_runtime_duplicate_symbols_warn(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    quote = {
        "symbol": "002837",
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
    (runtime / "quotes.json").write_text(
        json.dumps({"quotes": [quote, quote]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (runtime / "holdings.json").write_text(
        json.dumps(
            {
                "holdings": [
                    {"symbol": "002837", "name": "英维克"},
                    {"symbol": "002837", "name": "英维克"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = handle_validate_runtime("ai-energy")
    warning_codes = {warning["code"] for warning in payload["data"]["validation_warnings"]}

    assert payload["ok"] is True
    assert "DUPLICATE_QUOTE_SYMBOL" in warning_codes
    assert "DUPLICATE_HOLDING_SYMBOL" in warning_codes


def test_validate_runtime_normalizes_common_a_share_symbol_formats(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime))
    (runtime / "quotes.json").write_text(
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
    (runtime / "holdings.json").write_text(
        json.dumps({"holdings": [{"symbol": "SZ:300308", "name": "中际旭创"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = handle_validate_runtime("ai-energy")
    warning_codes = {warning["code"] for warning in payload["data"]["validation_warnings"]}

    assert payload["ok"] is True
    assert "HOLDING_WITHOUT_QUOTE" not in warning_codes
    assert "QUOTE_NOT_IN_HOLDINGS" not in warning_codes
    assert "QUOTE_SYMBOL_NOT_IN_POOL" not in warning_codes
    assert "HOLDING_SYMBOL_NOT_IN_POOL" not in warning_codes


def test_quote_from_dict_parses_string_booleans():
    quote = Quote.from_dict(
        {
            "symbol": "002837",
            "trade_date": "2026-06-06",
            "last_price": 1,
            "change_pct": 1,
            "amount": 1,
            "amount_ratio": 1,
            "turnover_rate": 1,
            "amplitude_pct": 1,
            "is_limit_up": "false",
            "is_stage_high": "0",
            "intraday_fade_pct": 0,
        }
    )

    assert quote.is_limit_up is False
    assert quote.is_stage_high is False


def test_runtime_models_normalize_common_a_share_symbol_formats():
    quote = Quote.from_dict(
        {
            "symbol": "SZ.300308",
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
    )
    holding = Holding.from_dict({"symbol": "300308.SZ", "name": "中际旭创"})

    assert quote.symbol == "300308"
    assert holding.symbol == "300308"
