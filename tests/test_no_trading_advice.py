import json

from market_intel.cli import (
    handle_agent_briefing,
    handle_agent_plan,
    handle_agent_run,
    handle_brief,
    handle_daily,
    handle_dashboard,
    handle_holdings_impact,
    handle_hotspots,
    handle_import_holdings,
    handle_import_quotes,
    handle_import_schema,
    handle_init_runtime,
    handle_journal_compare,
    handle_journal_latest,
    handle_journal_list,
    handle_journal_note,
    handle_journal_notes,
    handle_journal_save,
    handle_journal_timeline,
    handle_map,
    handle_status_runtime,
    handle_validate_runtime,
    handle_watchlist,
    handle_pool_explain,
    handle_pool_list,
    handle_portfolio_explain,
    handle_portfolio_review,
    handle_scan,
)


FORBIDDEN_KEYS = {
    "action",
    "recommendation",
    "target_price",
    "position_size",
    "must_buy",
    "must_sell",
}


def test_pool_outputs_do_not_contain_trading_advice_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_save("ai-energy", use_runtime=True)
    payloads = [
        handle_pool_list("ai-energy"),
        handle_pool_explain("ai-energy", "002837"),
        handle_pool_explain("ai-energy", "002281"),
        handle_pool_explain("ai-energy", "002281", use_runtime=True),
        handle_agent_plan("ai-energy", max_quote_age_days=9999),
        handle_agent_briefing("ai-energy", max_quote_age_days=9999),
        handle_agent_run("ai-energy", max_quote_age_days=9999, max_steps=5),
        handle_dashboard("ai-energy", max_quote_age_days=9999, max_steps=5),
        handle_portfolio_review("ai-energy", use_mock=True),
        handle_portfolio_review("ai-energy", use_mock=False, use_runtime=True),
        handle_portfolio_explain("ai-energy", "300308", use_mock=True),
        handle_portfolio_explain("ai-energy", "002837", use_mock=False, use_runtime=True),
        handle_portfolio_explain("ai-energy", "000000", use_mock=True),
        handle_hotspots("ai-energy", use_mock=True),
        handle_holdings_impact("ai-energy", use_mock=True),
        handle_brief("ai-energy", use_mock=True),
        handle_daily("ai-energy", use_mock=True),
        handle_scan("ai-energy", use_mock=True),
        handle_import_schema(),
        handle_import_quotes("examples/quotes.csv.example", dry_run=True),
        handle_import_holdings("examples/holdings.csv.example", dry_run=True),
        handle_journal_list(),
        handle_journal_latest(),
        handle_journal_compare(),
        handle_journal_timeline(),
        handle_journal_note(note_text="记录市场结构、组合暴露和待复核问题。"),
        handle_journal_notes(query="结构"),
        handle_watchlist("ai-energy", use_mock=True),
        handle_map("ai-energy", use_mock=True),
        handle_status_runtime("ai-energy", max_quote_age_days=9999),
        handle_validate_runtime("ai-energy"),
    ]

    for payload in payloads:
        assert_forbidden_keys_absent(payload)
        text = json.dumps(payload, ensure_ascii=False).lower()
        assert "buy" not in text
        assert "sell" not in text
        assert "target_price" not in text
        assert "position_size" not in text


def assert_forbidden_keys_absent(value):
    if isinstance(value, dict):
        assert not (FORBIDDEN_KEYS & set(value))
        for child in value.values():
            assert_forbidden_keys_absent(child)
    elif isinstance(value, list):
        for child in value:
            assert_forbidden_keys_absent(child)
