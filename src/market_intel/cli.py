import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core.agent import (
    build_agent_briefing,
    build_agent_plan,
    command_queue_item,
    compact_scan_review_focus,
    portfolio_item_commands,
)
from .core.fixtures import load_holdings_file, load_mock_holdings, load_mock_quotes, load_quotes_file
from .core.brief import build_daily_brief
from .core.csv_importer import import_holdings_csv, import_quotes_csv, import_research_csv, import_schema, import_universe_csv
from .core.coverage import (
    build_data_quality_detail,
    build_pool_coverage,
    export_data_quality_fix_csv,
    export_expansion_queue_csv,
    export_research_queue_csv,
    export_universe_patch_csv,
    matched_coverage_state,
    research_status,
    review_expansion_csv,
)
from .core.daily import build_daily_report, validate_daily_files
from .core.focus import build_focus_report
from .core.holdings import calculate_holding_impacts
from .core.journal import (
    build_journal_timeline,
    compare_latest_journal_to_payload,
    compare_journal_entries,
    latest_journal_entry,
    list_journal_entries,
    list_journal_notes,
    read_journal_by_id,
    save_daily_journal,
    save_journal_note,
)
from .core.json_output import envelope, error
from .core.map_view import build_market_map
from .core.models import Holding, PoolItem
from .core.normalize import explain_pool_item, find_pool_item
from .core.pool_loader import DEFAULT_POOL, default_pool_path, list_pools, load_pool
from .core.portfolio import build_portfolio_explain, build_portfolio_review
from .core.runtime import init_runtime, runtime_missing_files, runtime_paths
from .core.scan import build_market_scan
from .core.scoring import calculate_hotspots
from .core.status import build_runtime_status
from .core.symbols import normalize_symbol_input
from .core.text_report import (
    render_brief_text,
    render_agent_briefing_text,
    render_dashboard_text,
    render_agent_next_text,
    render_agent_plan_text,
    render_agent_run_text,
    render_daily_report_text,
    render_focus_text,
    render_import_text,
    render_import_universe_text,
    render_market_map_text,
    render_pool_coverage_text,
    render_pool_expansion_text,
    render_pool_explain_text,
    render_pool_quality_text,
    render_pool_research_text,
    render_pool_universe_text,
    render_journal_entry_text,
    render_journal_compare_text,
    render_journal_list_text,
    render_journal_notes_text,
    render_journal_timeline_text,
    render_portfolio_explain_text,
    render_portfolio_review_text,
    render_runtime_status_text,
    render_scan_text,
    render_watchlist_text,
)
from .core.validation import validate_runtime
from .core.watchlist import build_watchlist_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-intel")
    subparsers = parser.add_subparsers(dest="resource")

    pool_parser = subparsers.add_parser("pool")
    pool_subparsers = pool_parser.add_subparsers(dest="action")

    list_parser = pool_subparsers.add_parser("list")
    list_parser.add_argument("--pool", default=DEFAULT_POOL)
    list_parser.add_argument("--json", action="store_true", dest="as_json")

    coverage_parser = pool_subparsers.add_parser("coverage")
    coverage_parser.add_argument("--pool", default=DEFAULT_POOL)
    coverage_parser.add_argument("--mock", action="store_true")
    coverage_parser.add_argument("--runtime", action="store_true")
    coverage_parser.add_argument("--holdings-file")
    coverage_parser.add_argument("--json", action="store_true", dest="as_json")
    coverage_parser.add_argument("--text", action="store_true")

    quality_parser = pool_subparsers.add_parser("quality")
    quality_parser.add_argument("flag")
    quality_parser.add_argument("--pool", default=DEFAULT_POOL)
    quality_parser.add_argument("--limit", type=int, default=12)
    quality_parser.add_argument("--output")
    quality_parser.add_argument("--dry-run", action="store_true")
    quality_parser.add_argument("--json", action="store_true", dest="as_json")
    quality_parser.add_argument("--text", action="store_true")

    expansion_parser = pool_subparsers.add_parser("expansion")
    expansion_parser.add_argument("--pool", default=DEFAULT_POOL)
    expansion_parser.add_argument("--mock", action="store_true")
    expansion_parser.add_argument("--runtime", action="store_true")
    expansion_parser.add_argument("--holdings-file")
    expansion_parser.add_argument("--output")
    expansion_parser.add_argument("--review-file")
    expansion_parser.add_argument("--dry-run", action="store_true")
    expansion_parser.add_argument("--json", action="store_true", dest="as_json")
    expansion_parser.add_argument("--text", action="store_true")

    research_parser = pool_subparsers.add_parser("research")
    research_parser.add_argument("--pool", default=DEFAULT_POOL)
    research_parser.add_argument("--mock", action="store_true")
    research_parser.add_argument("--runtime", action="store_true")
    research_parser.add_argument("--holdings-file")
    research_parser.add_argument("--output")
    research_parser.add_argument("--dry-run", action="store_true")
    research_parser.add_argument("--json", action="store_true", dest="as_json")
    research_parser.add_argument("--text", action="store_true")

    universe_parser = pool_subparsers.add_parser("universe")
    universe_parser.add_argument("--pool", default=DEFAULT_POOL)
    universe_parser.add_argument("--mock", action="store_true")
    universe_parser.add_argument("--runtime", action="store_true")
    universe_parser.add_argument("--holdings-file")
    universe_parser.add_argument("--quotes-file")
    universe_parser.add_argument("--output")
    universe_parser.add_argument("--dry-run", action="store_true")
    universe_parser.add_argument("--limit", type=int)
    universe_parser.add_argument("--json", action="store_true", dest="as_json")
    universe_parser.add_argument("--text", action="store_true")

    explain_parser = pool_subparsers.add_parser("explain")
    explain_parser.add_argument("symbol")
    explain_parser.add_argument("--runtime", action="store_true")
    explain_parser.add_argument("--pool", default=DEFAULT_POOL)
    explain_parser.add_argument("--json", action="store_true", dest="as_json")
    explain_parser.add_argument("--text", action="store_true")

    hotspots_parser = subparsers.add_parser("hotspots")
    hotspots_parser.add_argument("--mock", action="store_true")
    hotspots_parser.add_argument("--runtime", action="store_true")
    hotspots_parser.add_argument("--quotes-file")
    hotspots_parser.add_argument("--top", type=int, default=10)
    hotspots_parser.add_argument("--pool", default=DEFAULT_POOL)
    hotspots_parser.add_argument("--json", action="store_true", dest="as_json")

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--mock", action="store_true")
    scan_parser.add_argument("--runtime", action="store_true")
    scan_parser.add_argument("--quotes-file")
    scan_parser.add_argument("--holdings-file")
    scan_parser.add_argument("--top", type=int, default=8)
    scan_parser.add_argument("--candidate-top", type=int, default=12)
    scan_parser.add_argument("--pool", default=DEFAULT_POOL)
    scan_parser.add_argument("--json", action="store_true", dest="as_json")
    scan_parser.add_argument("--text", action="store_true")

    holdings_parser = subparsers.add_parser("holdings")
    holdings_subparsers = holdings_parser.add_subparsers(dest="action")
    impact_parser = holdings_subparsers.add_parser("impact")
    impact_parser.add_argument("--mock", action="store_true")
    impact_parser.add_argument("--runtime", action="store_true")
    impact_parser.add_argument("--holdings-file")
    impact_parser.add_argument("--pool", default=DEFAULT_POOL)
    impact_parser.add_argument("--json", action="store_true", dest="as_json")

    portfolio_parser = subparsers.add_parser("portfolio")
    portfolio_subparsers = portfolio_parser.add_subparsers(dest="action")
    portfolio_review_parser = portfolio_subparsers.add_parser("review")
    portfolio_review_parser.add_argument("--mock", action="store_true")
    portfolio_review_parser.add_argument("--runtime", action="store_true")
    portfolio_review_parser.add_argument("--quotes-file")
    portfolio_review_parser.add_argument("--holdings-file")
    portfolio_review_parser.add_argument("--top", type=int, default=20)
    portfolio_review_parser.add_argument("--pool", default=DEFAULT_POOL)
    portfolio_review_parser.add_argument("--json", action="store_true", dest="as_json")
    portfolio_review_parser.add_argument("--text", action="store_true")
    portfolio_explain_parser = portfolio_subparsers.add_parser("explain")
    portfolio_explain_parser.add_argument("symbol")
    portfolio_explain_parser.add_argument("--mock", action="store_true")
    portfolio_explain_parser.add_argument("--runtime", action="store_true")
    portfolio_explain_parser.add_argument("--quotes-file")
    portfolio_explain_parser.add_argument("--holdings-file")
    portfolio_explain_parser.add_argument("--pool", default=DEFAULT_POOL)
    portfolio_explain_parser.add_argument("--json", action="store_true", dest="as_json")
    portfolio_explain_parser.add_argument("--text", action="store_true")

    brief_parser = subparsers.add_parser("brief")
    brief_parser.add_argument("--mock", action="store_true")
    brief_parser.add_argument("--runtime", action="store_true")
    brief_parser.add_argument("--quotes-file")
    brief_parser.add_argument("--holdings-file")
    brief_parser.add_argument("--top", type=int, default=5)
    brief_parser.add_argument("--pool", default=DEFAULT_POOL)
    brief_parser.add_argument("--json", action="store_true", dest="as_json")
    brief_parser.add_argument("--text", action="store_true")

    watchlist_parser = subparsers.add_parser("watchlist")
    watchlist_parser.add_argument("--mock", action="store_true")
    watchlist_parser.add_argument("--runtime", action="store_true")
    watchlist_parser.add_argument("--quotes-file")
    watchlist_parser.add_argument("--holdings-file")
    watchlist_parser.add_argument("--top", type=int, default=20)
    watchlist_parser.add_argument("--pool", default=DEFAULT_POOL)
    watchlist_parser.add_argument("--json", action="store_true", dest="as_json")
    watchlist_parser.add_argument("--text", action="store_true")

    map_parser = subparsers.add_parser("map")
    map_parser.add_argument("--mock", action="store_true")
    map_parser.add_argument("--runtime", action="store_true")
    map_parser.add_argument("--quotes-file")
    map_parser.add_argument("--holdings-file")
    map_parser.add_argument("--top", type=int, default=3)
    map_parser.add_argument("--pool", default=DEFAULT_POOL)
    map_parser.add_argument("--json", action="store_true", dest="as_json")
    map_parser.add_argument("--text", action="store_true")

    daily_parser = subparsers.add_parser("daily")
    daily_parser.add_argument("--mock", action="store_true")
    daily_parser.add_argument("--runtime", action="store_true")
    daily_parser.add_argument("--quotes-file")
    daily_parser.add_argument("--holdings-file")
    daily_parser.add_argument("--top", type=int, default=5)
    daily_parser.add_argument("--map-top", type=int, default=2)
    daily_parser.add_argument("--pool", default=DEFAULT_POOL)
    daily_parser.add_argument("--json", action="store_true", dest="as_json")
    daily_parser.add_argument("--text", action="store_true")

    dashboard_parser = subparsers.add_parser("dashboard")
    dashboard_parser.add_argument("--pool", default=DEFAULT_POOL)
    dashboard_parser.add_argument("--mock", action="store_true")
    dashboard_parser.add_argument("--top", type=int, default=5)
    dashboard_parser.add_argument("--map-top", type=int, default=2)
    dashboard_parser.add_argument("--max-quote-age-days", type=int, default=3)
    dashboard_parser.add_argument("--max-steps", type=int, default=8)
    dashboard_parser.add_argument("--json", action="store_true", dest="as_json")
    dashboard_parser.add_argument("--text", action="store_true")

    focus_parser = subparsers.add_parser("focus")
    focus_parser.add_argument("--mock", action="store_true")
    focus_parser.add_argument("--runtime", action="store_true")
    focus_parser.add_argument("--quotes-file")
    focus_parser.add_argument("--holdings-file")
    focus_parser.add_argument("--top", type=int, default=5)
    focus_parser.add_argument("--map-top", type=int, default=2)
    focus_parser.add_argument("--pool", default=DEFAULT_POOL)
    focus_parser.add_argument("--json", action="store_true", dest="as_json")
    focus_parser.add_argument("--text", action="store_true")

    import_parser = subparsers.add_parser("import")
    import_subparsers = import_parser.add_subparsers(dest="action")
    import_schema_parser = import_subparsers.add_parser("schema")
    import_schema_parser.add_argument("--json", action="store_true", dest="as_json")

    import_quotes_parser = import_subparsers.add_parser("quotes")
    import_quotes_parser.add_argument("csv_path")
    import_quotes_parser.add_argument("--runtime", action="store_true")
    import_quotes_parser.add_argument("--output")
    import_quotes_parser.add_argument("--dry-run", action="store_true")
    import_quotes_parser.add_argument("--trade-date")
    import_quotes_parser.add_argument("--json", action="store_true", dest="as_json")
    import_quotes_parser.add_argument("--text", action="store_true")

    import_holdings_parser = import_subparsers.add_parser("holdings")
    import_holdings_parser.add_argument("csv_path")
    import_holdings_parser.add_argument("--runtime", action="store_true")
    import_holdings_parser.add_argument("--output")
    import_holdings_parser.add_argument("--dry-run", action="store_true")
    import_holdings_parser.add_argument("--json", action="store_true", dest="as_json")
    import_holdings_parser.add_argument("--text", action="store_true")

    import_universe_parser = import_subparsers.add_parser("universe")
    import_universe_parser.add_argument("csv_path")
    import_universe_parser.add_argument("--runtime", action="store_true")
    import_universe_parser.add_argument("--output")
    import_universe_parser.add_argument("--dry-run", action="store_true")
    import_universe_parser.add_argument("--merge", action="store_true")
    import_universe_parser.add_argument("--json", action="store_true", dest="as_json")
    import_universe_parser.add_argument("--text", action="store_true")

    import_research_parser = import_subparsers.add_parser("research")
    import_research_parser.add_argument("csv_path")
    import_research_parser.add_argument("--runtime", action="store_true")
    import_research_parser.add_argument("--output")
    import_research_parser.add_argument("--dry-run", action="store_true")
    import_research_parser.add_argument("--json", action="store_true", dest="as_json")
    import_research_parser.add_argument("--text", action="store_true")

    init_parser = subparsers.add_parser("init")
    init_subparsers = init_parser.add_subparsers(dest="action")
    runtime_parser = init_subparsers.add_parser("runtime")
    runtime_parser.add_argument("--force", action="store_true")
    runtime_parser.add_argument("--json", action="store_true", dest="as_json")

    validate_parser = subparsers.add_parser("validate")
    validate_subparsers = validate_parser.add_subparsers(dest="action")
    validate_runtime_parser = validate_subparsers.add_parser("runtime")
    validate_runtime_parser.add_argument("--pool", default=DEFAULT_POOL)
    validate_runtime_parser.add_argument("--json", action="store_true", dest="as_json")

    status_parser = subparsers.add_parser("status")
    status_subparsers = status_parser.add_subparsers(dest="action")
    status_runtime_parser = status_subparsers.add_parser("runtime")
    status_runtime_parser.add_argument("--pool", default=DEFAULT_POOL)
    status_runtime_parser.add_argument("--max-quote-age-days", type=int, default=3)
    status_runtime_parser.add_argument("--json", action="store_true", dest="as_json")
    status_runtime_parser.add_argument("--text", action="store_true")

    agent_parser = subparsers.add_parser("agent")
    agent_subparsers = agent_parser.add_subparsers(dest="action")
    agent_plan_parser = agent_subparsers.add_parser("plan")
    agent_plan_parser.add_argument("--pool", default=DEFAULT_POOL)
    agent_plan_parser.add_argument("--max-quote-age-days", type=int, default=3)
    agent_plan_parser.add_argument("--json", action="store_true", dest="as_json")
    agent_plan_parser.add_argument("--text", action="store_true")
    agent_briefing_parser = agent_subparsers.add_parser("briefing")
    agent_briefing_parser.add_argument("--pool", default=DEFAULT_POOL)
    agent_briefing_parser.add_argument("--top", type=int, default=5)
    agent_briefing_parser.add_argument("--map-top", type=int, default=2)
    agent_briefing_parser.add_argument("--max-quote-age-days", type=int, default=3)
    agent_briefing_parser.add_argument("--json", action="store_true", dest="as_json")
    agent_briefing_parser.add_argument("--text", action="store_true")
    agent_run_parser = agent_subparsers.add_parser("run")
    agent_run_parser.add_argument("--pool", default=DEFAULT_POOL)
    agent_run_parser.add_argument("--top", type=int, default=5)
    agent_run_parser.add_argument("--map-top", type=int, default=2)
    agent_run_parser.add_argument("--max-quote-age-days", type=int, default=3)
    agent_run_parser.add_argument("--max-steps", type=int, default=8)
    agent_run_parser.add_argument("--json", action="store_true", dest="as_json")
    agent_run_parser.add_argument("--text", action="store_true")
    agent_next_parser = agent_subparsers.add_parser("next")
    agent_next_parser.add_argument("--pool", default=DEFAULT_POOL)
    agent_next_parser.add_argument("--top", type=int, default=5)
    agent_next_parser.add_argument("--map-top", type=int, default=2)
    agent_next_parser.add_argument("--max-quote-age-days", type=int, default=3)
    agent_next_parser.add_argument("--max-steps", type=int, default=8)
    agent_next_parser.add_argument("--symbol")
    agent_next_parser.add_argument("--mock", action="store_true")
    agent_next_parser.add_argument("--json", action="store_true", dest="as_json")
    agent_next_parser.add_argument("--text", action="store_true")

    journal_parser = subparsers.add_parser("journal")
    journal_subparsers = journal_parser.add_subparsers(dest="action")
    journal_save_parser = journal_subparsers.add_parser("save")
    journal_save_parser.add_argument("--runtime", action="store_true")
    journal_save_parser.add_argument("--quotes-file")
    journal_save_parser.add_argument("--holdings-file")
    journal_save_parser.add_argument("--top", type=int, default=5)
    journal_save_parser.add_argument("--map-top", type=int, default=2)
    journal_save_parser.add_argument("--pool", default=DEFAULT_POOL)
    journal_save_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_list_parser = journal_subparsers.add_parser("list")
    journal_list_parser.add_argument("--limit", type=int, default=10)
    journal_list_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_list_parser.add_argument("--text", action="store_true")
    journal_latest_parser = journal_subparsers.add_parser("latest")
    journal_latest_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_latest_parser.add_argument("--text", action="store_true")
    journal_show_parser = journal_subparsers.add_parser("show")
    journal_show_parser.add_argument("entry_id")
    journal_show_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_show_parser.add_argument("--text", action="store_true")
    journal_compare_parser = journal_subparsers.add_parser("compare")
    journal_compare_parser.add_argument("--base")
    journal_compare_parser.add_argument("--current")
    journal_compare_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_compare_parser.add_argument("--text", action="store_true")
    journal_timeline_parser = journal_subparsers.add_parser("timeline")
    journal_timeline_parser.add_argument("--limit", type=int, default=5)
    journal_timeline_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_timeline_parser.add_argument("--text", action="store_true")
    journal_note_parser = journal_subparsers.add_parser("note")
    journal_note_parser.add_argument("--entry-id")
    journal_note_parser.add_argument("--section")
    journal_note_parser.add_argument("--text")
    journal_note_parser.add_argument("--file")
    journal_note_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_notes_parser = journal_subparsers.add_parser("notes")
    journal_notes_parser.add_argument("--limit", type=int, default=10)
    journal_notes_parser.add_argument("--section")
    journal_notes_parser.add_argument("--query")
    journal_notes_parser.add_argument("--json", action="store_true", dest="as_json")
    journal_notes_parser.add_argument("--text", action="store_true")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.resource == "pool" and args.action == "list":
            result = handle_pool_list(args.pool)
        elif args.resource == "pool" and args.action == "coverage":
            result = handle_pool_coverage(args.pool, args.mock, args.holdings_file, args.runtime)
            if args.text and result["ok"]:
                print(render_pool_coverage_text(result))
                return 0
        elif args.resource == "pool" and args.action == "quality":
            result = handle_pool_quality(args.pool, args.flag, args.limit, args.output, args.dry_run)
            if args.text:
                print(render_pool_quality_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "pool" and args.action == "expansion":
            result = handle_pool_expansion(
                args.pool,
                args.mock,
                args.holdings_file,
                args.runtime,
                args.output,
                args.review_file,
                args.dry_run,
            )
            if args.text:
                print(render_pool_expansion_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "pool" and args.action == "research":
            result = handle_pool_research(
                args.pool,
                args.mock,
                args.holdings_file,
                args.runtime,
                args.output,
                args.dry_run,
            )
            if args.text:
                print(render_pool_research_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "pool" and args.action == "universe":
            result = handle_pool_universe(
                args.pool,
                args.mock,
                args.holdings_file,
                args.runtime,
                args.output,
                args.dry_run,
                args.limit,
                args.quotes_file,
            )
            if args.text:
                print(render_pool_universe_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "pool" and args.action == "explain":
            result = handle_pool_explain(args.pool, args.symbol, args.runtime)
            if args.text and result["ok"]:
                print(render_pool_explain_text(result))
                return 0
        elif args.resource == "hotspots":
            result = handle_hotspots(args.pool, args.mock, args.top, args.quotes_file, args.runtime)
        elif args.resource == "scan":
            result = handle_scan(
                args.pool,
                args.mock,
                args.top,
                args.candidate_top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text:
                print(render_scan_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "holdings" and args.action == "impact":
            result = handle_holdings_impact(args.pool, args.mock, args.holdings_file, args.runtime)
        elif args.resource == "portfolio" and args.action == "review":
            result = handle_portfolio_review(
                args.pool,
                args.mock,
                args.top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_portfolio_review_text(result))
                return 0
        elif args.resource == "portfolio" and args.action == "explain":
            result = handle_portfolio_explain(
                args.pool,
                args.symbol,
                args.mock,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_portfolio_explain_text(result))
                return 0
        elif args.resource == "brief":
            result = handle_brief(
                args.pool,
                args.mock,
                args.top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_brief_text(result))
                return 0
        elif args.resource == "watchlist":
            result = handle_watchlist(
                args.pool,
                args.mock,
                args.top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_watchlist_text(result))
                return 0
        elif args.resource == "map":
            result = handle_map(
                args.pool,
                args.mock,
                args.top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_market_map_text(result))
                return 0
        elif args.resource == "daily":
            result = handle_daily(
                args.pool,
                args.mock,
                args.top,
                args.map_top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text and result["ok"]:
                print(render_daily_report_text(result))
                return 0
        elif args.resource == "dashboard":
            result = handle_dashboard(args.pool, args.top, args.map_top, args.max_quote_age_days, args.max_steps, args.mock)
            if args.text:
                print(render_dashboard_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "focus":
            result = handle_focus(
                args.pool,
                args.mock,
                args.top,
                args.map_top,
                args.quotes_file,
                args.holdings_file,
                args.runtime,
            )
            if args.text:
                print(render_focus_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "import" and args.action == "schema":
            result = handle_import_schema()
        elif args.resource == "import" and args.action == "quotes":
            result = handle_import_quotes(
                args.csv_path,
                args.runtime,
                args.output,
                args.dry_run,
                args.trade_date,
            )
            if args.text:
                print(render_import_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "import" and args.action == "holdings":
            result = handle_import_holdings(
                args.csv_path,
                args.runtime,
                args.output,
                args.dry_run,
            )
            if args.text:
                print(render_import_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "import" and args.action == "universe":
            result = handle_import_universe(
                args.csv_path,
                args.runtime,
                args.output,
                args.dry_run,
                args.merge,
            )
            if args.text:
                print(render_import_universe_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "import" and args.action == "research":
            result = handle_import_research(
                args.csv_path,
                args.runtime,
                args.output,
                args.dry_run,
            )
            if args.text:
                print(render_import_text(result))
                return 0 if result["ok"] else 1
        elif args.resource == "init" and args.action == "runtime":
            result = handle_init_runtime(args.force)
        elif args.resource == "validate" and args.action == "runtime":
            result = handle_validate_runtime(args.pool)
        elif args.resource == "status" and args.action == "runtime":
            result = handle_status_runtime(args.pool, args.max_quote_age_days)
            if args.text and result["ok"]:
                print(render_runtime_status_text(result))
                return 0
        elif args.resource == "agent" and args.action == "plan":
            result = handle_agent_plan(args.pool, args.max_quote_age_days)
            if args.text and result["ok"]:
                print(render_agent_plan_text(result))
                return 0
        elif args.resource == "agent" and args.action == "briefing":
            result = handle_agent_briefing(args.pool, args.top, args.map_top, args.max_quote_age_days)
            if args.text and result["ok"]:
                print(render_agent_briefing_text(result))
                return 0
        elif args.resource == "agent" and args.action == "run":
            result = handle_agent_run(args.pool, args.top, args.map_top, args.max_quote_age_days, args.max_steps)
            if args.text and result["ok"]:
                print(render_agent_run_text(result))
                return 0
        elif args.resource == "agent" and args.action == "next":
            result = handle_agent_next(
                args.pool,
                args.top,
                args.map_top,
                args.max_quote_age_days,
                args.max_steps,
                args.symbol,
                use_mock=args.mock,
            )
            if args.text and result["ok"]:
                print(render_agent_next_text(result))
                return 0
        elif args.resource == "journal" and args.action == "save":
            result = handle_journal_save(
                args.pool,
                args.runtime,
                args.quotes_file,
                args.holdings_file,
                args.top,
                args.map_top,
            )
        elif args.resource == "journal" and args.action == "list":
            result = handle_journal_list(args.limit)
            if args.text and result["ok"]:
                print(render_journal_list_text(result))
                return 0
        elif args.resource == "journal" and args.action == "latest":
            result = handle_journal_latest()
            if args.text and result["ok"]:
                print(render_journal_entry_text(result))
                return 0
        elif args.resource == "journal" and args.action == "show":
            result = handle_journal_show(args.entry_id)
            if args.text and result["ok"]:
                print(render_journal_entry_text(result))
                return 0
        elif args.resource == "journal" and args.action == "compare":
            result = handle_journal_compare(args.base, args.current)
            if args.text and result["ok"]:
                print(render_journal_compare_text(result))
                return 0
        elif args.resource == "journal" and args.action == "timeline":
            result = handle_journal_timeline(args.limit)
            if args.text and result["ok"]:
                print(render_journal_timeline_text(result))
                return 0
        elif args.resource == "journal" and args.action == "note":
            result = handle_journal_note(args.entry_id, args.section, args.text, args.file)
        elif args.resource == "journal" and args.action == "notes":
            result = handle_journal_notes(args.limit, args.section, args.query)
            if args.text and result["ok"]:
                print(render_journal_notes_text(result))
                return 0
        else:
            parser.print_help(sys.stderr)
            return 2
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        result = envelope(
            command="unknown",
            errors=[error("CLI_ERROR", str(exc))],
            source=str(default_pool_path()),
            ok=False,
        )
        print_json(result)
        return 1

    print_json(result)
    return 0 if result["ok"] else 1


def handle_pool_list(pool: str) -> Dict[str, Any]:
    items = load_pool(pool)
    data = {
        "pool": pool,
        "available_pools": list_pools(),
        "count": len(items),
        "items": [item.to_dict() for item in items],
        "agent_contract": pool_list_contract(),
    }
    warnings = pool_warnings(items)
    return envelope(
        command="pool.list",
        data=data,
        warnings=warnings,
        source=str(default_pool_path(pool)),
    )


def pool_list_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.available_pools",
            "data.available_pools[].id",
            "data.available_pools[].scope",
            "data.available_pools[].is_default",
            "data.available_pools[].coverage_boundary",
            "data.available_pools[].next_command",
            "data.available_pools[].done_when",
        ],
        "boundary": "pool list 只列出可用池和入口命令；覆盖边界以 pool coverage 为准。",
    }


def handle_pool_coverage(
    pool: str,
    use_mock: bool = False,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    items = load_pool(pool)
    holdings = None
    holdings_source = None
    if use_runtime:
        paths = runtime_paths()
        holdings_path = Path(paths["holdings"])
        if not holdings_path.exists():
            return pool_coverage_runtime_error(pool)
        holdings_file = paths["holdings"]
    if use_mock or holdings_file:
        holdings, holdings_mode, raw_source = resolve_holdings(use_mock, holdings_file)
        holdings_source = {
            "provided": True,
            "mode": "runtime" if use_runtime else holdings_mode,
            "source": privacy_safe_source(raw_source, "holdings", "runtime" if use_runtime else holdings_mode),
        }

    data = build_pool_coverage(pool, items, holdings=holdings)
    data["holdings_source"] = holdings_source or {"provided": False}
    return envelope(
        command="pool.coverage",
        data=data,
        warnings=pool_warnings(items),
        source="pool:%s" % pool,
    )


def handle_pool_quality(
    pool: str,
    flag: str,
    limit: int = 12,
    output: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    items = load_pool(pool)
    data = build_data_quality_detail(pool, items, flag, limit=limit)
    if data.get("found") and (output or dry_run):
        output_path = Path(output) if output else Path("data/runtime/pool_quality_%s.csv" % flag)
        export_data = export_data_quality_fix_csv(data, output_path, dry_run=dry_run)
        export_data["agent_contract"] = pool_quality_export_contract()
        return envelope(
            command="pool.quality",
            data=export_data,
            warnings=export_data.get("warnings", []),
            source="pool:%s" % pool,
            ok=True,
        )
    return envelope(
        command="pool.quality",
        data=data,
        warnings=[],
        source="pool:%s" % pool,
        ok=bool(data.get("found")),
        errors=[] if data.get("found") else [error("POOL_QUALITY_FLAG_NOT_FOUND", "No pool items match this data quality flag.", {"flag": flag})],
    )


def pool_quality_export_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.flag",
            "data.output",
            "data.record_count",
            "data.written",
            "data.dry_run",
            "data.fields",
            "data.rows",
            "data.next_commands",
        ],
        "boundary": "pool quality 导出只生成数据质量修正草稿，不自动修改主复盘池。",
    }


def handle_pool_expansion(
    pool: str,
    use_mock: bool = False,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
    output: Optional[str] = None,
    review_file: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if review_file:
        if output or dry_run or use_mock or use_runtime or holdings_file:
            return envelope(
                command="pool.expansion",
                data={"pool": pool, "agent_contract": pool_expansion_contract()},
                errors=[
                    error(
                        "POOL_EXPANSION_REVIEW_CONFLICT",
                        "Use --review-file by itself; do not combine it with source or output options.",
                        {"pool": pool},
                    )
                ],
                source="pool:%s" % pool,
                ok=False,
            )
        review_data = review_expansion_csv(Path(review_file))
        review_data["pool"] = pool
        review_data["agent_contract"] = pool_expansion_contract()
        return envelope(
            command="pool.expansion",
            data=review_data,
            warnings=review_data.get("warnings", []),
            errors=review_data.get("blockers", []),
            source="pool:%s" % pool,
            ok=review_data.get("review_state") == "ready",
        )

    coverage_payload = handle_pool_coverage(pool, use_mock, holdings_file, use_runtime)
    if not coverage_payload.get("ok"):
        return coverage_payload
    if not output and not dry_run:
        return envelope(
            command="pool.expansion",
            data={
                "pool": pool,
                "agent_contract": pool_expansion_contract(),
            },
            errors=[
                error(
                    "POOL_EXPANSION_OUTPUT_REQUIRED",
                    "Pool expansion export requires --output or --dry-run.",
                    {"pool": pool},
                )
            ],
            source="pool:%s" % pool,
            ok=False,
        )

    data = coverage_payload.get("data", {}) if isinstance(coverage_payload.get("data"), dict) else {}
    output_path = Path(output) if output else Path("data/runtime/pool_expansion.csv")
    export_data = export_expansion_queue_csv(
        data.get("expansion_queue", []) if isinstance(data.get("expansion_queue"), list) else [],
        output_path,
        dry_run=dry_run,
    )
    export_data["pool"] = pool
    export_data["coverage_summary"] = data.get("holdings_coverage", {})
    export_data["agent_contract"] = pool_expansion_contract()
    return envelope(
        command="pool.expansion",
        data=export_data,
        warnings=export_data.get("warnings", []),
        source="pool:%s" % pool,
    )


def pool_expansion_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.output",
            "data.record_count",
            "data.written",
            "data.dry_run",
            "data.fields",
            "data.rows",
            "data.next_commands",
            "data.review_state",
            "data.blockers",
            "data.ready_rows",
        ],
        "boundary": "pool expansion 只导出或审查候选补池 CSV，不自动修改主复盘池。",
    }


def handle_pool_research(
    pool: str,
    use_mock: bool = False,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    coverage_payload = handle_pool_coverage(pool, use_mock, holdings_file, use_runtime)
    if not coverage_payload.get("ok"):
        return coverage_payload
    if not output and not dry_run:
        return envelope(
            command="pool.research",
            data={
                "pool": pool,
                "agent_contract": pool_research_contract(),
            },
            errors=[
                error(
                    "POOL_RESEARCH_OUTPUT_REQUIRED",
                    "Pool research export requires --output or --dry-run.",
                    {"pool": pool},
                )
            ],
            source="pool:%s" % pool,
            ok=False,
        )

    data = coverage_payload.get("data", {}) if isinstance(coverage_payload.get("data"), dict) else {}
    output_path = Path(output) if output else Path("data/runtime/research_notes.todo.csv")
    export_data = export_research_queue_csv(
        data.get("research_queue", []) if isinstance(data.get("research_queue"), list) else [],
        output_path,
        dry_run=dry_run,
    )
    export_data["pool"] = pool
    export_data["coverage_summary"] = data.get("holdings_coverage", {})
    export_data["agent_contract"] = pool_research_contract()
    return envelope(
        command="pool.research",
        data=export_data,
        warnings=export_data.get("warnings", []),
        source="pool:%s" % pool,
    )


def pool_research_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.output",
            "data.record_count",
            "data.written",
            "data.dry_run",
            "data.fields",
            "data.rows",
            "data.next_commands",
        ],
        "boundary": "pool research 只导出 foundation 持仓的研究证据草稿，不自动生成研究结论。",
    }


def handle_pool_universe(
    pool: str,
    use_mock: bool = False,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
    quotes_file: Optional[str] = None,
) -> Dict[str, Any]:
    # Universe patch export only needs the pool/universe view. Runtime universe is
    # loaded by the pool loader, so do not require runtime holdings here.
    coverage_payload = handle_pool_coverage(pool, use_mock, holdings_file, False)
    if not coverage_payload.get("ok"):
        return coverage_payload
    if not output and not dry_run:
        return envelope(
            command="pool.universe",
            data={
                "pool": pool,
                "agent_contract": pool_universe_contract(),
            },
            errors=[
                error(
                    "POOL_UNIVERSE_OUTPUT_REQUIRED",
                    "Pool universe export requires --output or --dry-run.",
                    {"pool": pool},
                )
            ],
            source="pool:%s" % pool,
            ok=False,
        )

    data = coverage_payload.get("data", {}) if isinstance(coverage_payload.get("data"), dict) else {}
    universe = data.get("universe", {}) if isinstance(data.get("universe"), dict) else {}
    items = load_pool(pool)
    universe_items = [
        item
        for item in items
        if str(item.raw.get("pool_source") or "").startswith("universe:") or item.raw.get("universe_schema")
    ]
    output_path = Path(output) if output else Path("data/runtime/a_share_universe_patch.csv")
    quote_patch = quote_only_universe_patch_rows(pool, items, use_mock, use_runtime, quotes_file)
    export_data = export_universe_patch_csv(
        universe_items,
        output_path,
        dry_run=dry_run,
        limit=limit,
        extra_rows=quote_patch["rows"],
    )
    export_data["pool"] = pool
    export_data["mode"] = "runtime" if use_runtime else "file"
    export_data["coverage_summary"] = universe.get("sector_profile", {})
    export_data["quote_only"] = quote_patch
    export_data["agent_contract"] = pool_universe_contract()
    return envelope(
        command="pool.universe",
        data=export_data,
        warnings=export_data.get("warnings", []),
        source="pool:%s" % pool,
    )


def pool_universe_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.mode",
            "data.output",
            "data.record_count",
            "data.written",
            "data.dry_run",
            "data.limit",
            "data.fields",
            "data.rows",
            "data.next_commands",
            "data.quote_only",
            "data.quote_only.record_count",
            "data.quote_only.rows",
        ],
        "boundary": "pool universe 只导出 A 股基础清单补数字段草稿，不自动写入 runtime；写入需 import universe --merge。",
    }


def quote_only_universe_patch_rows(
    pool: str,
    items: List[PoolItem],
    use_mock: bool,
    use_runtime: bool,
    quotes_file: Optional[str],
) -> Dict[str, object]:
    if use_runtime and not quotes_file:
        paths = runtime_paths()
        runtime_quotes = Path(paths["quotes"])
        if runtime_quotes.exists():
            quotes_file = str(runtime_quotes)
    if not (use_mock or quotes_file):
        return {
            "available": False,
            "record_count": 0,
            "source": None,
            "rows": [],
            "summary": "未提供行情源，未生成 quote-only 补丁行。",
        }
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    scan = build_market_scan(items, quotes, holdings=[], top=8, candidate_top=max(len(quotes), 12), pool=pool)
    candidates = scan.get("candidate_securities", []) if isinstance(scan.get("candidate_securities"), list) else []
    rows = [
        quote_only_universe_patch_row(candidate)
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("coverage_state") == "quote_only"
    ]
    return {
        "available": bool(rows),
        "record_count": len(rows),
        "source": privacy_safe_source(quote_source, "quotes", "runtime" if use_runtime else quote_mode),
        "rows": rows,
        "summary": "行情中有 %s 个 A 股标的未进入 all-a 覆盖底座。" % len(rows) if rows else "行情中暂无 quote-only 标的。",
    }


def quote_only_universe_patch_row(candidate: Dict[str, object]) -> Dict[str, object]:
    return {
        "symbol": str(candidate.get("symbol") or ""),
        "name": str(candidate.get("name") or candidate.get("symbol") or ""),
        "industry": "",
        "concepts": "",
        "index_membership": "",
        "listing_status": "listed",
        "source": "scan.quote_only",
        "missing_fields": "industry;concepts;index_membership",
        "fill_hint": "补行业；补概念，多个用分号分隔；补指数成分，多个用分号分隔",
    }


def handle_pool_explain(pool: str, symbol: str, use_runtime: bool = False) -> Dict[str, Any]:
    symbol = normalize_cli_symbol(symbol) or ""
    items = load_pool(pool)
    item = find_pool_item(items, symbol)
    if item is None:
        return envelope(
            command="pool.explain",
            errors=[
                error(
                    "POOL_ITEM_NOT_FOUND",
                    "Pool item not found: %s" % symbol,
                    {"symbol": symbol, "pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    data = explain_pool_item(item)
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("pool.explain", missing)
        data["runtime_context"] = build_runtime_context(item.symbol)
    return envelope(
        command="pool.explain",
        data=data,
        warnings=pool_warnings([item]),
        source=str(default_pool_path(pool)),
    )


def handle_hotspots(
    pool: str,
    use_mock: bool,
    top: int = 10,
    quotes_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("hotspots", missing)
        quotes_file = runtime_paths()["quotes"]

    if not use_mock and not quotes_file:
        return envelope(
            command="hotspots",
            errors=[
                error(
                    "QUOTE_SOURCE_REQUIRED",
                    "Hotspots require --mock or --quotes-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, mode, source = resolve_quotes(use_mock, quotes_file)
    hotspots = calculate_hotspots(items, quotes, top=top)
    data = {
        "pool": pool,
        "mode": "runtime" if use_runtime else mode,
        "quote_count": len(quotes),
        "count": len(hotspots),
        "hotspots": [hotspot.to_dict() for hotspot in hotspots],
    }
    return envelope(
        command="hotspots",
        data=data,
        source=source,
    )


def handle_scan(
    pool: str,
    use_mock: bool,
    top: int = 8,
    candidate_top: int = 12,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = scan_runtime_missing_files()
        if missing:
            return runtime_error("scan", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_path = Path(paths["holdings"])
        if holdings_path.exists():
            holdings_file = paths["holdings"]

    if not use_mock and not quotes_file:
        return envelope(
            command="scan",
            data={
                "pool": pool,
                "agent_contract": build_market_scan([], [], top=top, candidate_top=candidate_top, pool=pool).get("agent_contract"),
                "next_actions": [
                    {
                        "rank": 1,
                        "id": "import_quotes",
                        "command": "market-intel import quotes <quotes.csv> --runtime --json",
                        "done_when": "已导入当日行情后重新运行 scan。",
                    }
                ],
                "guardrails": ["scan 需要行情源；输出不生成买卖指令、目标价或仓位建议。"],
            },
            errors=[
                error(
                    "SCAN_QUOTE_SOURCE_REQUIRED",
                    "Scan requires --mock, --runtime, or --quotes-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )

    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings = []
    holdings_mode = "none"
    holdings_source = None
    if use_mock or holdings_file:
        holdings, holdings_mode, raw_holdings_source = resolve_holdings(use_mock, holdings_file)
        holdings_source = privacy_safe_source(raw_holdings_source, "holdings", "runtime" if use_runtime else holdings_mode)
    data = build_market_scan(items, quotes, holdings=holdings, top=top, candidate_top=candidate_top, pool=pool)
    data["pool"] = pool
    data["mode"] = scan_mode(use_mock, use_runtime, quotes_file)
    localize_scan_commands(data, pool, data["mode"])
    data["coverage_context"] = daily_coverage_context(pool, items, holdings)
    data["sources"] = {
        "quotes": {
            "mode": "runtime" if use_runtime else quote_mode,
            "source": privacy_safe_source(quote_source, "quotes", "runtime" if use_runtime else quote_mode),
        },
        "holdings": {
            "provided": bool(holdings),
            "mode": "runtime" if use_runtime else holdings_mode,
            "source": holdings_source,
        },
    }
    return envelope(
        command="scan",
        data=data,
        warnings=[],
        source="pool:%s" % pool,
    )


def scan_mode(use_mock: bool, use_runtime: bool, quotes_file: Optional[str]) -> str:
    if use_runtime:
        return "runtime"
    if use_mock and not quotes_file:
        return "mock"
    return "file"


def scan_runtime_missing_files() -> List[str]:
    paths = runtime_paths()
    quotes_path = Path(paths["quotes"])
    return [] if quotes_path.exists() else [str(quotes_path)]


def localize_scan_commands(
    data: Dict[str, object],
    pool: str,
    mode: object,
) -> None:
    mode_text = str(mode or "")
    candidates = data.get("candidate_securities", []) if isinstance(data.get("candidate_securities"), list) else []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        item["commands"] = [localize_scan_command(str(command), pool, mode_text) for command in commands if command]
        sync_scan_review_focus_next_command(item, item["commands"])
    actions = data.get("next_actions", []) if isinstance(data.get("next_actions"), list) else []
    for item in actions:
        if isinstance(item, dict) and item.get("command"):
            item["command"] = localize_scan_command(str(item.get("command")), pool, mode_text)
    queue = data.get("candidate_queue", {}) if isinstance(data.get("candidate_queue"), dict) else {}
    buckets = queue.get("buckets", {}) if isinstance(queue.get("buckets"), dict) else {}
    for bucket in buckets.values():
        items = bucket.get("items", []) if isinstance(bucket, dict) and isinstance(bucket.get("items"), list) else []
        for item in items:
            if isinstance(item, dict) and item.get("next_command"):
                item["next_command"] = localize_scan_command(str(item.get("next_command")), pool, mode_text)


def localize_scan_command(command: str, pool: str, mode: str) -> str:
    if "import universe <a_share_universe.csv>" in command or "pool universe --runtime --dry-run --json" in command:
        return with_pool_arg(scan_universe_patch_command(mode), pool)
    if mode == "runtime":
        if "pool explain" in command and " --runtime" not in command:
            return with_pool_arg(command.replace(" --text", " --runtime --text"), pool)
        if "scan " in command and " --runtime" not in command:
            return with_pool_arg(command.replace(" --text", " --runtime --text"), pool)
        if "focus " in command and " --runtime" not in command:
            return with_pool_arg(command.replace(" --text", " --runtime --text"), pool)
        return with_pool_arg(command, pool)
    if mode == "mock":
        if "pool explain" in command:
            return with_pool_arg(command.replace(" --runtime", ""), pool)
        if "scan " in command:
            return with_pool_arg(command.replace(" --runtime", " --mock"), pool)
        if "focus " in command:
            return with_pool_arg(command.replace(" --runtime", " --mock"), pool)
    if mode == "file":
        if "pool explain" in command:
            return with_pool_arg(command.replace(" --runtime", ""), pool)
        if "scan " in command:
            return with_pool_arg("market-intel scan --json", pool)
        if "focus " in command:
            return with_pool_arg("market-intel focus --json", pool)
    return with_pool_arg(command, pool)


def scan_universe_patch_command(mode: str) -> str:
    if mode == "runtime":
        return "market-intel pool universe --runtime --dry-run --json"
    if mode == "mock":
        return "market-intel pool universe --mock --dry-run --json"
    if mode == "file":
        return "market-intel pool universe --quotes-file <quotes.json> --dry-run --json"
    return "market-intel pool universe --dry-run --json"


def sync_scan_review_focus_next_command(item: Dict[str, object], commands: List[str]) -> None:
    focus = item.get("review_focus", {}) if isinstance(item.get("review_focus"), dict) else {}
    if focus and commands:
        focus["next_command"] = commands[0]


def handle_holdings_impact(
    pool: str,
    use_mock: bool,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("holdings.impact", missing)
        holdings_file = runtime_paths()["holdings"]

    if not use_mock and not holdings_file:
        return envelope(
            command="holdings.impact",
            errors=[
                error(
                    "HOLDINGS_SOURCE_REQUIRED",
                    "Holdings impact requires --mock or --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    holdings, mode, source = resolve_holdings(use_mock, holdings_file)
    data = calculate_holding_impacts(items, holdings)
    data["pool"] = pool
    data["mode"] = "runtime" if use_runtime else mode
    return envelope(
        command="holdings.impact",
        data=data,
        source=source,
    )


def handle_portfolio_review(
    pool: str,
    use_mock: bool,
    top: int = 20,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("portfolio.review", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="portfolio.review",
            errors=[
                error(
                    "PORTFOLIO_REVIEW_SOURCE_REQUIRED",
                    "Portfolio review requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings, holdings_mode, holdings_source = resolve_holdings(use_mock, holdings_file)
    data = build_portfolio_review(items, quotes, holdings, top=top)
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    return envelope(
        command="portfolio.review",
        data=data,
        source="%s;%s" % (quote_source, holdings_source),
    )


def handle_portfolio_explain(
    pool: str,
    symbol: str,
    use_mock: bool,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    symbol = normalize_cli_symbol(symbol) or ""
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("portfolio.explain", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="portfolio.explain",
            errors=[
                error(
                    "PORTFOLIO_EXPLAIN_SOURCE_REQUIRED",
                    "Portfolio explain requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool, "symbol": symbol},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings, holdings_mode, holdings_source = resolve_holdings(use_mock, holdings_file)
    data = build_portfolio_explain(items, quotes, holdings, symbol)
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    return envelope(
        command="portfolio.explain",
        data=data,
        warnings=data.get("warnings", []),
        errors=data.get("errors", []),
        source="%s;%s" % (quote_source, holdings_source),
        ok=bool(data.get("found")),
    )


def handle_brief(
    pool: str,
    use_mock: bool,
    top: int = 5,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("brief", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="brief",
            errors=[
                error(
                    "BRIEF_SOURCE_REQUIRED",
                    "Brief requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings, holdings_mode, holdings_source = resolve_holdings(use_mock, holdings_file)
    data = build_daily_brief(items, quotes, holdings, top=top)
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    return envelope(
        command="brief",
        data=data,
        source="%s;%s" % (quote_source, holdings_source),
    )


def handle_watchlist(
    pool: str,
    use_mock: bool,
    top: int = 20,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("watchlist", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="watchlist",
            errors=[
                error(
                    "WATCHLIST_SOURCE_REQUIRED",
                    "Watchlist requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings, holdings_mode, holdings_source = resolve_holdings(use_mock, holdings_file)
    data = build_watchlist_report(items, quotes, holdings, top=top)
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    return envelope(
        command="watchlist",
        data=data,
        source="%s;%s" % (quote_source, holdings_source),
    )


def handle_map(
    pool: str,
    use_mock: bool,
    top: int = 3,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("map", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="map",
            errors=[
                error(
                    "MAP_SOURCE_REQUIRED",
                    "Map requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )
    items = load_pool(pool)
    quotes, quote_mode, quote_source = resolve_quotes(use_mock, quotes_file)
    holdings, holdings_mode, holdings_source = resolve_holdings(use_mock, holdings_file)
    data = build_market_map(items, quotes, holdings, top=top)
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    return envelope(
        command="map",
        data=data,
        source="%s;%s" % (quote_source, holdings_source),
    )


def handle_daily(
    pool: str,
    use_mock: bool,
    top: int = 5,
    map_top: int = 2,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    if use_runtime:
        missing = runtime_missing_files()
        if missing:
            return runtime_error("daily", missing)
        paths = runtime_paths()
        quotes_file = paths["quotes"]
        holdings_file = paths["holdings"]

    if not use_mock and (not quotes_file or not holdings_file):
        return envelope(
            command="daily",
            errors=[
                error(
                    "DAILY_SOURCE_REQUIRED",
                    "Daily report requires --mock or both --quotes-file and --holdings-file.",
                    {"pool": pool},
                )
            ],
            source=str(default_pool_path(pool)),
            ok=False,
        )

    items = load_pool(pool)
    if use_mock and not (quotes_file or holdings_file):
        quotes, quote_mode, quote_source = resolve_quotes(use_mock=True, quotes_file=None)
        holdings, holdings_mode, holdings_source = resolve_holdings(use_mock=True, holdings_file=None)
        validation = None
    else:
        quotes_path = Path(str(quotes_file))
        holdings_path = Path(str(holdings_file))
        validation = validate_daily_files(items, quotes_path, holdings_path)
        quote_mode, quote_source = "runtime" if use_runtime else "file", str(quotes_path)
        holdings_mode, holdings_source = "runtime" if use_runtime else "file", str(holdings_path)
        if not validation["ok"]:
            return envelope(
                command="daily",
                data={
                    "pool": pool,
                    "mode": "runtime" if use_runtime else "file",
                    "validation": validation["validation"],
                    "sources": {
                        "quotes": {"mode": quote_mode, "source": quote_source},
                        "holdings": {"mode": holdings_mode, "source": holdings_source},
                    },
                },
                errors=validation["validation"]["errors"],
                source="%s;%s" % (quote_source, holdings_source),
                ok=False,
            )
        quotes = validation["quotes"]
        holdings = validation["holdings"]

    data = build_daily_report(items, quotes, holdings, top=top, map_top=map_top)
    if validation is not None:
        data["validation"] = validation["validation"]
    data["pool"] = pool
    data["mode"] = brief_mode(use_mock, use_runtime, quotes_file, holdings_file)
    data["coverage_context"] = daily_coverage_context(pool, items, holdings)
    data["sources"] = {
        "quotes": {"mode": quote_mode, "source": quote_source},
        "holdings": {"mode": holdings_mode, "source": holdings_source},
    }
    data["review_tasks"] = localize_daily_review_task_commands(
        data.get("review_tasks", []),
        pool,
        data["mode"],
        quote_source,
        holdings_source,
    )
    data["security_review_queue"] = localize_daily_security_queue_commands(
        data.get("security_review_queue", []),
        pool,
        data["mode"],
        quote_source,
        holdings_source,
    )
    data["journal_actions"] = daily_journal_actions(
        pool,
        data["mode"],
        quote_source,
        holdings_source,
    )
    data["risk_register"] = localize_daily_risk_register_commands(
        data.get("risk_register", []),
        pool,
        data["mode"],
        quote_source,
        holdings_source,
    )
    data["review_path"] = localize_daily_review_path_commands(
        data.get("review_path", []),
        pool,
        data["mode"],
        quote_source,
        holdings_source,
        data.get("journal_actions", []),
    )
    data["security_risk_profile"] = localize_daily_security_profile_commands(
        data.get("security_risk_profile", []),
        pool,
        data["mode"],
        quote_source,
        holdings_source,
    )
    add_daily_note_prerequisites(data)
    data["command_queue"] = build_daily_command_queue(data)
    return envelope(
        command="daily",
        data=data,
        source="%s;%s" % (quote_source, holdings_source),
    )


def daily_coverage_context(pool: str, items: List[PoolItem], holdings: List[Holding]) -> Dict[str, object]:
    coverage = build_pool_coverage(pool, items, holdings=holdings)
    data_quality_queue = list(coverage.get("data_quality_queue", []))[:5] if isinstance(coverage.get("data_quality_queue"), list) else []
    return {
        "available": True,
        "pool": coverage.get("pool"),
        "scope": coverage.get("scope"),
        "status": coverage.get("status"),
        "summary": coverage.get("summary"),
        "universe": coverage.get("universe"),
        "holdings_coverage": coverage.get("holdings_coverage"),
        "gaps": list(coverage.get("gaps", []))[:5] if isinstance(coverage.get("gaps"), list) else [],
        "data_quality_queue": data_quality_queue,
        "top_data_quality_queue": compact_data_quality_queue(data_quality_queue),
        "next_actions": list(coverage.get("next_actions", []))[:5] if isinstance(coverage.get("next_actions"), list) else [],
        "guardrails": list(coverage.get("guardrails", []))[:5] if isinstance(coverage.get("guardrails"), list) else [],
    }


def handle_focus(
    pool: str,
    use_mock: bool,
    top: int = 5,
    map_top: int = 2,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    use_runtime: bool = False,
) -> Dict[str, Any]:
    daily_payload = handle_daily(
        pool,
        use_mock,
        top,
        map_top,
        quotes_file,
        holdings_file,
        use_runtime,
    )
    if not daily_payload.get("ok"):
        daily_data = daily_payload.get("data", {}) if isinstance(daily_payload.get("data"), dict) else {}
        validation = daily_data.get("validation", {}) if isinstance(daily_data.get("validation"), dict) else {}
        daily_errors = daily_payload.get("errors", []) if isinstance(daily_payload.get("errors"), list) else []
        if not validation and daily_errors:
            validation = {
                "summary": {
                    "quote_count": 0,
                    "holding_count": 0,
                    "error_count": len(daily_errors),
                    "warning_count": 0,
                },
                "errors": daily_errors,
                "warnings": [],
            }
        focus_seed = {"validation": validation, "mode": brief_mode(use_mock, use_runtime, quotes_file, holdings_file)}
        focus_status = build_focus_report(focus_seed).get("data_status", {})
        next_command = focus_status.get("command") if isinstance(focus_status, dict) else None
        return envelope(
            command="focus",
            data={
                "pool": pool,
                "mode": brief_mode(use_mock, use_runtime, quotes_file, holdings_file),
                "headline": "数据未就绪，先处理校验错误。",
                "data_status": focus_status,
                "market_focus": {"strongest_chain": None, "top_chains": [], "layers": []},
                "portfolio_pressure": {"summary": None, "repeated_exposure_count": 0, "repeated_overlap_count": 0},
                "priority_securities": [],
                "next_steps": [
                    {
                        "rank": 1,
                        "id": "data_quality",
                        "title": "先处理数据错误",
                        "reason": "focus 需要可用的行情和持仓数据。",
                        "runnable": bool(next_command),
                        "command": next_command,
                        "done_when": "数据校验 errors 清空后再生成 focus。",
                    }
                ],
                "first_runnable_command": "",
                "agent_contract": build_focus_report({}).get("agent_contract"),
                "guardrails": ["这是复盘聚焦，不是交易指令。"],
            },
            errors=daily_errors,
            source=daily_payload.get("meta", {}).get("source") if isinstance(daily_payload.get("meta"), dict) else None,
            ok=False,
        )

    daily_data = daily_payload.get("data", {}) if isinstance(daily_payload.get("data"), dict) else {}
    data = build_focus_report(daily_data, limit=top)
    return envelope(
        command="focus",
        data=data,
        warnings=daily_payload.get("warnings", []) if isinstance(daily_payload.get("warnings"), list) else [],
        source=daily_payload.get("meta", {}).get("source") if isinstance(daily_payload.get("meta"), dict) else None,
    )


def handle_import_schema() -> Dict[str, Any]:
    return envelope(
        command="import.schema",
        data=import_schema(),
        source="market_intel.core.csv_importer",
    )


def handle_import_quotes(
    csv_path: str,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    target = resolve_import_output("quotes", use_runtime, output, dry_run)
    if target.get("error"):
        return import_config_error("import.quotes", target["error"], csv_path)
    data = import_quotes_csv(
        Path(csv_path),
        target["path"],
        dry_run=dry_run,
        default_trade_date=trade_date,
        runtime=use_runtime,
    )
    return import_envelope("import.quotes", data)


def handle_import_holdings(
    csv_path: str,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    target = resolve_import_output("holdings", use_runtime, output, dry_run)
    if target.get("error"):
        return import_config_error("import.holdings", target["error"], csv_path)
    data = import_holdings_csv(
        Path(csv_path),
        target["path"],
        dry_run=dry_run,
        runtime=use_runtime,
    )
    return import_envelope("import.holdings", data)


def handle_import_universe(
    csv_path: str,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
    merge: bool = False,
) -> Dict[str, Any]:
    target = resolve_import_output("universe", use_runtime, output, dry_run)
    if target.get("error"):
        return import_config_error("import.universe", target["error"], csv_path)
    data = import_universe_csv(
        Path(csv_path),
        target["path"],
        dry_run=dry_run,
        runtime=use_runtime,
        merge=merge,
    )
    return import_envelope("import.universe", data)


def handle_import_research(
    csv_path: str,
    use_runtime: bool = False,
    output: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    target = resolve_import_output("research", use_runtime, output, dry_run)
    if target.get("error"):
        return import_config_error("import.research", target["error"], csv_path)
    data = import_research_csv(
        Path(csv_path),
        target["path"],
        dry_run=dry_run,
        runtime=use_runtime,
    )
    return import_envelope("import.research", data)


def resolve_import_output(
    kind: str,
    use_runtime: bool,
    output: Optional[str],
    dry_run: bool,
) -> Dict[str, Any]:
    if use_runtime and output:
        return {
            "error": error(
                "IMPORT_OUTPUT_CONFLICT",
                "Use either --runtime or --output, not both.",
                {"kind": kind},
            )
        }
    if dry_run:
        if use_runtime:
            paths = runtime_paths()
            return {"path": Path(paths[kind])}
        return {"path": Path(output) if output else None}
    if use_runtime:
        paths = runtime_paths()
        return {"path": Path(paths[kind])}
    if output:
        return {"path": Path(output)}
    return {
        "error": error(
            "IMPORT_OUTPUT_REQUIRED",
            "Import requires --runtime, --output, or --dry-run.",
            {"kind": kind},
        )
    }


def import_config_error(command: str, config_error: Dict[str, Any], source: str) -> Dict[str, Any]:
    return envelope(
        command=command,
        data={
            "agent_contract": {
                "success": "ok=true 且 errors=[]",
                "next_step": "Run market-intel import schema --json to inspect accepted CSV columns.",
            }
        },
        errors=[config_error],
        source=source,
        ok=False,
    )


def import_envelope(command: str, data: Dict[str, object]) -> Dict[str, Any]:
    errors = data.get("errors", [])
    warnings = data.get("warnings", [])
    return envelope(
        command=command,
        data=data,
        warnings=warnings if isinstance(warnings, list) else [],
        errors=errors if isinstance(errors, list) else [],
        source=str(data.get("input") or ""),
        ok=not bool(errors),
    )


def status_errors(data: Dict[str, object]) -> List[Dict[str, Any]]:
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    freshness = data.get("freshness", {}) if isinstance(data.get("freshness"), dict) else {}
    errors = []
    if isinstance(validation.get("errors"), list):
        errors.extend(validation["errors"])
    if isinstance(freshness.get("errors"), list):
        errors.extend(freshness["errors"])
    return errors


def status_warnings(data: Dict[str, object]) -> List[Dict[str, Any]]:
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    freshness = data.get("freshness", {}) if isinstance(data.get("freshness"), dict) else {}
    universe = data.get("universe", {}) if isinstance(data.get("universe"), dict) else {}
    warnings = []
    if isinstance(validation.get("warnings"), list):
        warnings.extend(validation["warnings"])
    if isinstance(freshness.get("warnings"), list):
        warnings.extend(freshness["warnings"])
    if isinstance(universe.get("warnings"), list):
        warnings.extend(universe["warnings"])
    return warnings


def handle_init_runtime(force: bool = False) -> Dict[str, Any]:
    data = init_runtime(force=force)
    return envelope(
        command="init.runtime",
        data=data,
        source="examples/quotes.example.json;examples/holdings.example.json;examples/a_share_universe.csv.example",
    )


def handle_validate_runtime(pool: str = DEFAULT_POOL) -> Dict[str, Any]:
    items = load_pool(pool)
    validation = validate_runtime(items)
    return envelope(
        command="validate.runtime",
        data={
            "pool": pool,
            "summary": validation["summary"],
            "files": validation["files"],
            "validation_warnings": validation["warnings"],
        },
        errors=validation["errors"],
        source="%s;%s" % (validation["files"]["quotes"], validation["files"]["holdings"]),
        ok=bool(validation["ok"]),
    )


def handle_status_runtime(pool: str = DEFAULT_POOL, max_quote_age_days: int = 3) -> Dict[str, Any]:
    items = load_pool(pool)
    data = build_runtime_status(items, max_quote_age_days=max_quote_age_days, pool=pool)
    data["pool"] = pool
    return envelope(
        command="status.runtime",
        data=data,
        warnings=status_warnings(data),
        errors=status_errors(data),
        source="%s;%s;%s" % (
            data["files"]["quotes"]["path"],
            data["files"]["holdings"]["path"],
            data["files"]["universe"]["path"],
        ),
        ok=True,
    )


def handle_agent_plan(pool: str = DEFAULT_POOL, max_quote_age_days: int = 3) -> Dict[str, Any]:
    items = load_pool(pool)
    status_data = build_runtime_status(items, max_quote_age_days=max_quote_age_days, pool=pool)
    journal_data = list_journal_entries(limit=2)
    data = build_agent_plan(pool, status_data, journal_data, max_quote_age_days=max_quote_age_days)
    return envelope(
        command="agent.plan",
        data=data,
        warnings=agent_plan_warnings(status_data, journal_data),
        errors=[],
        source="%s;%s" % (data["runtime"]["files"]["quotes"]["path"], data["runtime"]["files"]["holdings"]["path"]),
        ok=True,
    )


def handle_agent_briefing(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_quote_age_days: int = 3,
) -> Dict[str, Any]:
    items = load_pool(pool)
    status_data = build_runtime_status(items, max_quote_age_days=max_quote_age_days, pool=pool)
    scan_payload = None
    daily_payload = None
    if status_data.get("readiness", {}).get("can_run_daily") if isinstance(status_data.get("readiness"), dict) else False:
        scan_payload = handle_scan(
            pool,
            use_mock=False,
            top=max(top, 8),
            candidate_top=max(top * 2, 12),
            use_runtime=True,
        )
        daily_payload = handle_daily(
            pool,
            use_mock=False,
            top=top,
            map_top=map_top,
            use_runtime=True,
        )
    else:
        daily_payload = envelope(
            command="daily",
            data={"summary": "runtime 暂不可生成日报。"},
            errors=status_errors(status_data),
            source=str(default_pool_path(pool)),
            ok=False,
        )

    timeline_data = build_journal_timeline(limit=5)
    compare_data = compare_journal_entries() if timeline_data.get("can_compare") else None
    current_compare_data = compare_latest_journal_to_payload(daily_payload) if daily_payload.get("ok") else None
    data = build_agent_briefing(
        pool,
        status_data,
        scan_payload,
        daily_payload,
        timeline_data,
        compare_data,
        current_compare_data,
        max_quote_age_days=max_quote_age_days,
    )
    warnings = status_warnings(status_data)
    warnings.extend(timeline_data.get("warnings", []) if isinstance(timeline_data.get("warnings"), list) else [])
    if isinstance(compare_data, dict):
        warnings.extend(compare_data.get("warnings", []) if isinstance(compare_data.get("warnings"), list) else [])
    if isinstance(current_compare_data, dict):
        warnings.extend(current_compare_data.get("warnings", []) if isinstance(current_compare_data.get("warnings"), list) else [])
    if isinstance(scan_payload, dict):
        warnings.extend(scan_payload.get("warnings", []) if isinstance(scan_payload.get("warnings"), list) else [])
    warnings.extend(daily_payload.get("warnings", []) if isinstance(daily_payload.get("warnings"), list) else [])
    return envelope(
        command="agent.briefing",
        data=data,
        warnings=warnings,
        errors=[],
        source="%s;%s" % (status_data["files"]["quotes"]["path"], status_data["files"]["holdings"]["path"]),
        ok=True,
    )


def handle_agent_run(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_quote_age_days: int = 3,
    max_steps: int = 8,
) -> Dict[str, Any]:
    briefing_payload = handle_agent_briefing(pool, top=top, map_top=map_top, max_quote_age_days=max_quote_age_days)
    briefing_data = briefing_payload.get("data", {}) if isinstance(briefing_payload.get("data"), dict) else {}
    queue = build_agent_run_queue(briefing_data)
    source_briefing = compact_agent_run_source(briefing_payload, queue)
    results: List[Dict[str, object]] = []
    skipped: List[Dict[str, object]] = []
    read_limit = max(0, int(max_steps or 0))

    for item in queue:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or item.get("command") or "")
        if not command:
            continue
        if "agent briefing" in command:
            continue
        if not item.get("runnable", True):
            skipped.append(agent_run_skip(item, "命令当前不可直接运行。"))
            continue
        if item.get("mutates_state") or item.get("state_effect") != "read_only":
            skipped.append(agent_run_skip(item, "写入类命令保留给人工确认后运行。"))
            continue
        if command_has_placeholder(command):
            skipped.append(agent_run_skip(item, "命令包含占位符，需要先补充文件或参数。"))
            continue
        if len(results) >= read_limit:
            skipped.append(agent_run_skip(item, "达到本次 agent run 的只读步骤上限。"))
            continue
        result = run_agent_read_command(command, pool, top, map_top, max_quote_age_days)
        results.append(compact_agent_run_result(item, result))

    manual_followups = build_agent_run_manual_followups(skipped)
    review_digest = build_agent_run_review_digest(briefing_data, results, skipped, manual_followups, source_briefing)

    data = {
        "pool": pool,
        "state": agent_run_state(briefing_data, results, skipped),
        "summary": agent_run_summary(briefing_data, results, skipped),
        "source_briefing": source_briefing,
        "review_digest": review_digest,
        "run_limits": {
            "max_steps": read_limit,
            "read_only_only": True,
            "writes_are_skipped": True,
        },
        "queue": compact_agent_run_queue(queue),
        "results": results,
        "skipped": skipped,
        "manual_followups": manual_followups,
        "agent_contract": agent_run_contract(),
    }
    return envelope(
        command="agent.run",
        data=data,
        warnings=briefing_payload.get("warnings", []) if isinstance(briefing_payload.get("warnings"), list) else [],
        errors=[],
        source=briefing_payload.get("meta", {}).get("source") if isinstance(briefing_payload.get("meta"), dict) else None,
        ok=True,
    )


def handle_agent_next(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_quote_age_days: int = 3,
    max_steps: int = 8,
    symbol: Optional[str] = None,
    use_mock: bool = False,
) -> Dict[str, Any]:
    symbol = normalize_cli_symbol(symbol)
    if use_mock:
        return handle_mock_agent_next(pool=pool, top=top, map_top=map_top, max_steps=max_steps, symbol=symbol)
    run_payload = handle_agent_run(pool, top=top, map_top=map_top, max_quote_age_days=max_quote_age_days, max_steps=max_steps)
    run_data = run_payload.get("data", {}) if isinstance(run_payload.get("data"), dict) else {}
    digest = run_data.get("review_digest", {}) if isinstance(run_data.get("review_digest"), dict) else {}
    handoff = digest.get("review_handoff", {}) if isinstance(digest.get("review_handoff"), dict) else {}
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    cards = digest.get("security_cards", {}) if isinstance(digest.get("security_cards"), dict) else {}
    coverage_context = digest.get("coverage_context", {}) if isinstance(digest.get("coverage_context"), dict) else {}
    market_scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    focus_chain = agent_next_focus_chain(pool, digest, handoff)
    if symbol:
        cards = filter_agent_next_cards_for_symbol(cards, symbol)
        cards = ensure_agent_next_symbol_card(pool, symbol, digest, cards)
        cards = ensure_agent_next_pool_symbol_card(pool, symbol, cards)
        handoff = filter_agent_next_handoff_for_symbol(handoff, symbol, agent_next_primary_card_command(cards))
        focus_chain = agent_next_symbol_focus_chain(pool, symbol, handoff, cards, focus_chain)
        if not cards.get("cards"):
            focus_chain = []
            action_summary = agent_next_action_summary(focus_chain, handoff, completion)
            return envelope(
                command="agent.next",
                data={
                    "pool": pool,
                    "state": "symbol_not_found",
                    "summary": "未找到 %s 的单票复核卡片。" % symbol,
                    "symbol": symbol,
                    "source_agent_run_state": run_data.get("state"),
                    "run_limits": run_data.get("run_limits", {}),
                    "action_summary": action_summary,
                    "coverage_context": coverage_context,
                    "market_scan": market_scan,
                    "focus_chain": focus_chain,
                    "review_handoff": handoff,
                    "review_completion": completion,
                    "security_cards": cards,
                    "agent_contract": agent_next_contract(),
                },
                errors=[error("AGENT_NEXT_SYMBOL_NOT_FOUND", "No security card found for symbol.", {"symbol": symbol})],
                source=run_payload.get("meta", {}).get("source") if isinstance(run_payload.get("meta"), dict) else None,
                ok=False,
            )
    action_summary = agent_next_action_summary(focus_chain, handoff, completion)
    data = {
        "pool": pool,
        "symbol": symbol,
        "state": handoff.get("handoff_state") or run_data.get("state"),
        "summary": handoff.get("summary") or run_data.get("summary"),
        "source_agent_run_state": run_data.get("state"),
        "run_limits": run_data.get("run_limits", {}),
        "action_summary": action_summary,
        "coverage_context": coverage_context,
        "market_scan": market_scan,
        "focus_chain": focus_chain,
        "review_handoff": handoff,
        "review_completion": completion,
        "security_cards": cards,
        "agent_contract": agent_next_contract(),
    }
    return envelope(
        command="agent.next",
        data=data,
        warnings=run_payload.get("warnings", []) if isinstance(run_payload.get("warnings"), list) else [],
        errors=run_payload.get("errors", []) if isinstance(run_payload.get("errors"), list) else [],
        source=run_payload.get("meta", {}).get("source") if isinstance(run_payload.get("meta"), dict) else None,
        ok=bool(run_payload.get("ok")),
    )


def handle_mock_agent_next(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_steps: int = 8,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    dashboard_payload = handle_mock_dashboard(pool=pool, top=top, map_top=map_top, max_steps=max_steps)
    dashboard = dashboard_payload.get("data", {}) if isinstance(dashboard_payload.get("data"), dict) else {}
    handoff = dashboard.get("handoff", {}) if isinstance(dashboard.get("handoff"), dict) else {}
    handoff = mock_agent_next_handoff(handoff)
    completion = mock_agent_next_completion(handoff)
    cards = mock_agent_next_security_cards(dashboard)
    focus_chain = mock_agent_next_focus_chain(dashboard)
    if symbol:
        cards = filter_agent_next_cards_for_symbol(cards, symbol)
        focus_chain = mock_agent_next_symbol_focus_chain(symbol, cards, focus_chain)
        if not cards.get("cards"):
            focus_chain = []
            action_summary = agent_next_action_summary(focus_chain, handoff, completion)
            return envelope(
                command="agent.next",
                data={
                    "pool": pool,
                    "state": "symbol_not_found",
                    "summary": "mock 示例里未找到 %s 的单票复核卡片。" % symbol,
                    "symbol": symbol,
                    "source_agent_run_state": dashboard.get("state"),
                    "run_limits": dashboard.get("run_limits", {}),
                    "action_summary": action_summary,
                    "coverage_context": dashboard.get("coverage_context", {}),
                    "market_scan": mock_agent_next_market_scan(dashboard.get("market_pulse", {})),
                    "focus_chain": [],
                    "review_handoff": handoff,
                    "review_completion": completion,
                    "security_cards": cards,
                    "agent_contract": agent_next_contract(),
                },
                errors=[error("AGENT_NEXT_SYMBOL_NOT_FOUND", "No mock security card found for symbol.", {"symbol": symbol})],
                source="mock",
                ok=False,
            )
    action_summary = agent_next_action_summary(focus_chain, handoff, completion)
    data = {
        "pool": pool,
        "symbol": symbol,
        "state": handoff.get("handoff_state") or dashboard.get("state"),
        "summary": handoff.get("summary") or dashboard.get("summary"),
        "source_agent_run_state": dashboard.get("state"),
        "run_limits": dashboard.get("run_limits", {}),
        "action_summary": action_summary,
        "coverage_context": dashboard.get("coverage_context", {}),
        "market_scan": mock_agent_next_market_scan(dashboard.get("market_pulse", {})),
        "focus_chain": focus_chain,
        "review_handoff": handoff,
        "review_completion": completion,
        "security_cards": cards,
        "agent_contract": agent_next_contract(),
    }
    return envelope(
        command="agent.next",
        data=data,
        warnings=dashboard_payload.get("warnings", []) if isinstance(dashboard_payload.get("warnings"), list) else [],
        errors=[],
        source="mock",
        ok=bool(dashboard_payload.get("ok")),
    )


def agent_next_action_summary(
    focus_chain: List[Dict[str, object]],
    handoff: Dict[str, object],
    completion: Dict[str, object],
) -> Dict[str, object]:
    compact_handoff = dashboard_handoff({"review_handoff": handoff, "review_completion": completion})
    today_focus = agent_next_today_focus(focus_chain, compact_handoff)
    return dashboard_action_summary(today_focus, compact_handoff)


def agent_next_today_focus(focus_chain: List[Dict[str, object]], handoff: Dict[str, object]) -> Dict[str, object]:
    item = first_dashboard_focus_item(focus_chain, prefer_read=True)
    if not item:
        item = first_dashboard_focus_item(handoff.get("next_read", []), prefer_read=False)
    if not item:
        item = first_dashboard_focus_item(handoff.get("manual_items", []), prefer_read=False)
    if not item:
        return {
            "available": False,
            "summary": "暂无下一步。",
            "source": "",
            "title": "",
            "reason": "",
            "json_command": "",
            "done_when": "",
            "runnable": False,
            "requires_manual": False,
            "related_symbols": [],
            "focus_chain": focus_chain,
        }
    command = str(item.get("json_command") or "")
    source = str(item.get("item_type") or item.get("source") or item.get("check_id") or "review_next")
    requires_manual = bool(item.get("requires_manual")) or str(item.get("step_type") or "") == "manual"
    runnable = bool(command) and not requires_manual and digest_command_is_read_only(command)
    title = str(item.get("title") or source)
    reason = str(item.get("reason") or "按 agent next 接力队列继续。")
    done_when = str(item.get("done_when") or "已完成该步骤并确认下一条命令。")
    return {
        "available": True,
        "summary": "下一步：%s。" % title,
        "source": source,
        "title": title,
        "reason": reason,
        "json_command": command,
        "done_when": done_when,
        "runnable": runnable,
        "requires_manual": requires_manual,
        "related_symbols": dedupe_queue_texts(
            item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        )[:5],
        "focus_chain": focus_chain,
    }


def mock_agent_next_market_scan(value: object) -> Dict[str, object]:
    market = value if isinstance(value, dict) else {}
    rows = dict(market)
    candidates = market.get("candidates", []) if isinstance(market.get("candidates"), list) else []
    rows["top_candidates"] = candidates
    return rows


def mock_agent_next_handoff(value: object) -> Dict[str, object]:
    handoff = dict(value) if isinstance(value, dict) else {}
    next_read = handoff.get("next_read", []) if isinstance(handoff.get("next_read"), list) else []
    manual_items = handoff.get("manual_items", []) if isinstance(handoff.get("manual_items"), list) else []
    if "command_chain" not in handoff:
        handoff["command_chain"] = review_handoff_command_chain(next_read, manual_items)
    return handoff


def mock_agent_next_completion(handoff: Dict[str, object]) -> Dict[str, object]:
    base = handoff.get("completion", {}) if isinstance(handoff.get("completion"), dict) else {}
    next_read = handoff.get("next_read", []) if isinstance(handoff.get("next_read"), list) else []
    read_count = safe_int(base.get("pending_count"), len(next_read)) or len(next_read)
    checks = [
        review_completion_check(
            "mock_runtime_setup",
            "准备正式 runtime",
            "pending" if read_count else "done",
            "mock 只能验证交接包结构；正式复盘前需要确认导入字段和数据文件。",
            "market-intel import schema --json",
            "已确认 quotes、holdings、a_share_universe 和 research_notes 的导入字段。",
        ),
        review_completion_check(
            "mock_to_runtime",
            "切换正式复盘",
            "manual_required",
            "mock 不读取个人 runtime，也不写 journal。",
            "market-intel init runtime --json",
            "已初始化 runtime，导入真实数据后重新运行 market-intel dashboard --text。",
        ),
        review_completion_check(
            "mock_handoff",
            "交接链",
            "done" if handoff.get("command_chain") else "pending",
            "已生成 mock 待读命令链，可用于检查 agent next 合同。",
            first_digest_read_command(
                [item.get("json_command") for item in next_read if isinstance(item, dict)],
                "market-intel agent next --mock --json",
            ),
            "已确认 command_chain、security_cards 和 market_scan 字段可读。",
        ),
    ]
    blocking = sum(1 for item in checks if item.get("status") == "blocked")
    manual = sum(1 for item in checks if item.get("status") == "manual_required")
    pending = sum(1 for item in checks if item.get("status") == "pending")
    state = str(base.get("completion_state") or "demo")
    return {
        "available": True,
        "completion_state": state,
        "summary": review_completion_summary(checks, state),
        "ready_for_journal_note": False,
        "blocking_count": blocking,
        "manual_required_count": manual,
        "pending_count": pending,
        "checks": checks,
        "write_policy": "mock 只演示复盘收尾门槛，不自动写入 journal。",
    }


def mock_agent_next_focus_chain(dashboard: Dict[str, object]) -> List[Dict[str, object]]:
    focus = dashboard.get("today_focus", {}) if isinstance(dashboard.get("today_focus"), dict) else {}
    chain = focus.get("focus_chain", []) if isinstance(focus.get("focus_chain"), list) else []
    return [dict(item) for item in chain if isinstance(item, dict)]


def mock_agent_next_symbol_focus_chain(
    symbol: str,
    cards: Dict[str, object],
    fallback: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen = set()
    for card in cards.get("cards", []) if isinstance(cards.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        for command in [card.get("next_json_command")] + list(card.get("commands", []) if isinstance(card.get("commands"), list) else []):
            command_text = str(command or "")
            if not command_text or command_text in seen:
                continue
            seen.add(command_text)
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "source": "security_card",
                    "title": "%s %s" % (card.get("symbol"), card.get("name") or ""),
                    "json_command": command_text,
                    "done_when": "已确认 mock 单票卡片结构；正式复盘需切换 runtime。",
                    "runnable": digest_command_is_read_only(command_text),
                    "related_symbols": [symbol],
                }
            )
            if len(rows) >= 3:
                return rows
    for item in fallback:
        if not isinstance(item, dict):
            continue
        symbols = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        command = str(item.get("json_command") or "")
        if symbols and symbol not in symbols:
            continue
        if symbol not in command:
            continue
        if command in seen:
            continue
        rows.append(dict(item))
        if len(rows) >= 3:
            return rows
    return rows


def mock_agent_next_security_cards(dashboard: Dict[str, object]) -> Dict[str, object]:
    holdings = dashboard.get("portfolio_pulse", {}).get("top_holdings", []) if isinstance(dashboard.get("portfolio_pulse"), dict) else []
    cards = []
    for item in holdings:
        if isinstance(item, dict) and item.get("symbol"):
            cards.append(mock_agent_next_security_card(item, len(cards) + 1))
    return {
        "available": bool(cards),
        "summary": "mock 单票复核卡片 %s 张，用于演示 agent next 合同。" % len(cards),
        "cards": cards[:6],
        "write_policy": "mock 只演示单票复核结构，不读取个人 runtime，不生成交易指令。",
    }


def mock_agent_next_security_card(item: Dict[str, object], rank: int) -> Dict[str, object]:
    symbol = str(item.get("symbol") or "")
    command = str(item.get("primary_json_command") or "")
    hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
    hotspot = dict(hotspot) if hotspot else {}
    if hotspot and hotspot.get("score") is None and item.get("review_score") is not None:
        hotspot["score"] = item.get("review_score")
    return {
        "rank": rank,
        "symbol": symbol,
        "name": item.get("name"),
        "priority": item.get("priority"),
        "review_score": item.get("review_score"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": [],
        "research_status": {"available": False, "confirmed": False, "status": "mock"},
        "research_workflow": [],
        "change_priority": item.get("change_priority"),
        "has_quote": bool(item.get("has_quote")),
        "in_hotspot": bool(item.get("hotspot")),
        "hotspot": hotspot,
        "quote": None,
        "risk_flags": list(item.get("risk_flags", []))[:6] if isinstance(item.get("risk_flags"), list) else [],
        "exposure_groups": [],
        "overlap_groups": list(item.get("overlap_groups", []))[:4] if isinstance(item.get("overlap_groups"), list) else [],
        "change": {},
        "supporting_evidence": dedupe_queue_texts([item.get("primary_question"), "mock 示例，正式复盘需导入 runtime。"])[:4],
        "open_gaps": ["mock 示例不能替代真实持仓和行情。"],
        "questions": [item.get("primary_question") or "读取该持仓的行情、热点、风险和组合暴露。"],
        "next_json_command": command,
        "commands": [command] if command else [],
        "watch_items": [],
        "journal_note": {
            "available": False,
            "write_policy": "mock 不生成 journal note；正式复盘请先导入 runtime。",
        },
    }


def normalize_cli_symbol(symbol: Optional[str]) -> Optional[str]:
    return normalize_symbol_input(symbol)


def ensure_agent_next_symbol_card(
    pool: str,
    symbol: str,
    digest: Dict[str, object],
    cards: Dict[str, object],
) -> Dict[str, object]:
    existing = cards.get("cards", []) if isinstance(cards.get("cards"), list) else []
    if existing:
        return cards
    holding = agent_next_symbol_holding(pool, digest, symbol)
    if not holding:
        return cards
    journal_draft = digest.get("journal_draft", {}) if isinstance(digest.get("journal_draft"), dict) else {}
    archive_prerequisite = (
        journal_draft.get("archive_prerequisite", {})
        if isinstance(journal_draft.get("archive_prerequisite"), dict)
        else journal_draft_archive_prerequisite([])
    )
    workbench_by_symbol = {
        str(item.get("symbol")): item
        for item in digest.get("security_workbench", [])
        if isinstance(item, dict) and item.get("symbol")
    } if isinstance(digest.get("security_workbench"), list) else {}
    evidence_by_symbol = security_cards_group_by_symbol(digest.get("evidence_checklist", {}), "related_symbols")
    hypothesis_by_symbol = security_cards_group_by_symbol(digest.get("hypothesis_board", {}), "related_symbols")
    watch_by_symbol = security_cards_group_by_symbol(digest.get("followup_watch", {}), "symbols")
    handoff_commands = security_cards_handoff_commands(digest.get("review_handoff", {}))
    card = security_card_item(
        1,
        holding,
        workbench_by_symbol.get(symbol, {}),
        evidence_by_symbol.get(symbol, []),
        hypothesis_by_symbol.get(symbol, []),
        watch_by_symbol.get(symbol, []),
        handoff_commands.get(symbol, []),
        archive_prerequisite,
    )
    result = dict(cards)
    result["available"] = True
    result["summary"] = "聚焦 %s 的单票复核卡。" % symbol
    result["cards"] = [card]
    return result


def ensure_agent_next_pool_symbol_card(
    pool: str,
    symbol: str,
    cards: Dict[str, object],
) -> Dict[str, object]:
    existing = cards.get("cards", []) if isinstance(cards.get("cards"), list) else []
    if existing:
        return cards
    pool_item = agent_next_pool_symbol_item(pool, symbol)
    if not pool_item:
        return cards
    result = dict(cards)
    result["available"] = True
    result["summary"] = "聚焦 %s 的池内标的复核卡。" % symbol
    result["cards"] = [pool_symbol_security_card(pool_item)]
    return result


def agent_next_pool_symbol_item(pool: str, symbol: str) -> Dict[str, object]:
    source_item = find_pool_item(load_pool(pool), symbol)
    explain_payload = handle_pool_explain(pool, symbol, use_runtime=True)
    if not explain_payload.get("ok"):
        return {}
    data = explain_payload.get("data", {}) if isinstance(explain_payload.get("data"), dict) else {}
    item = data.get("item", {}) if isinstance(data.get("item"), dict) else {}
    facts = data.get("facts", {}) if isinstance(data.get("facts"), dict) else {}
    if not item or str(facts.get("symbol") or item.get("symbol") or "") != symbol:
        return {}
    if source_item:
        coverage = matched_coverage_state(source_item)
        data["coverage_state"] = coverage.get("state")
        data["coverage_state_reasons"] = coverage.get("reasons", [])
        data["research_status"] = research_status(source_item)
    return data


def pool_symbol_security_card(data: Dict[str, object]) -> Dict[str, object]:
    facts = data.get("facts", {}) if isinstance(data.get("facts"), dict) else {}
    item = data.get("item", {}) if isinstance(data.get("item"), dict) else {}
    symbol = str(facts.get("symbol") or item.get("symbol") or "")
    exposures = data.get("exposures", []) if isinstance(data.get("exposures"), list) else []
    runtime_context = data.get("runtime_context", {}) if isinstance(data.get("runtime_context"), dict) else {}
    quote = runtime_context.get("quote") if isinstance(runtime_context.get("quote"), dict) else None
    holding = runtime_context.get("holding") if isinstance(runtime_context.get("holding"), dict) else None
    chain = "%s/%s" % (facts.get("primary_layer"), facts.get("primary_sub_sector"))
    coverage_state = str(data.get("coverage_state") or ("pool_context" if holding else "pool_only"))
    coverage_state_reasons = (
        list(data.get("coverage_state_reasons", []))
        if isinstance(data.get("coverage_state_reasons"), list)
        else ["pool_item_match"]
    )
    if "pool_item_match" not in coverage_state_reasons:
        coverage_state_reasons.insert(0, "pool_item_match")
    if not holding and "not_in_runtime_holdings" not in coverage_state_reasons:
        coverage_state_reasons.append("not_in_runtime_holdings")
    research = compact_digest_research_status(data.get("research_status", {}))
    research_workflow = foundation_research_workflow(symbol, coverage_state)
    supporting = dedupe_queue_texts(
        [
            data.get("explain"),
            "池内标的：%s，主链路 %s。" % (facts.get("name") or item.get("name") or symbol, chain),
            "runtime 有行情。" if quote else None,
            "runtime 有持仓。" if holding else "runtime 未持仓。",
            "研究证据 reviewed。" if research.get("confirmed") else None,
        ]
    )[:6]
    gaps = dedupe_queue_texts(
        list(data.get("questions", []) if isinstance(data.get("questions"), list) else [])
        + (["该标的不在当前 runtime 持仓中，先按池内标的核对，不进入持仓暴露结论。"] if not holding else [])
        + (["runtime 缺少该标的行情。"] if not quote else [])
        + (["全 A 基础清单只说明存在，仍需补 research notes 的核心逻辑、关键证据和证伪风险。"] if coverage_state == "foundation" and not research.get("confirmed") else [])
    )[:6]
    question = (
        "先确认该池内标的的链路、角色、可交易状态和 runtime 行情/持仓上下文。"
        if not holding
        else "先确认该标的的链路、角色、行情和持仓上下文。"
    )
    command = "market-intel pool explain %s --runtime --json" % symbol
    return {
        "rank": 1,
        "symbol": symbol,
        "name": facts.get("name") or item.get("name"),
        "priority": facts.get("priority"),
        "review_score": None,
        "coverage_state": coverage_state,
        "coverage_state_reasons": [str(reason) for reason in coverage_state_reasons[:6] if reason],
        "research_status": research,
        "research_workflow": research_workflow,
        "change_priority": 0,
        "has_quote": bool(quote),
        "in_hotspot": False,
        "hotspot": None,
        "quote": quote,
        "risk_flags": list(data.get("risks", []))[:6] if isinstance(data.get("risks"), list) else [],
        "exposure_groups": [
            {
                "group_type": "chain",
                "group": "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")),
                "role": exposure.get("role"),
            }
            for exposure in exposures[:4]
            if isinstance(exposure, dict)
        ],
        "overlap_groups": [],
        "change": {},
        "supporting_evidence": supporting,
        "open_gaps": gaps,
        "questions": [question],
        "next_json_command": command,
        "commands": [command],
        "watch_items": [],
        "journal_note": {
            "available": False,
            "write_policy": "池内标的 fallback 只给读取入口；是否记录研究笔记需人工确认。",
        },
    }


def agent_next_symbol_holding(pool: str, digest: Dict[str, object], symbol: str) -> Dict[str, object]:
    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    rows = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    for item in rows:
        if isinstance(item, dict) and str(item.get("symbol") or "") == symbol:
            return item
    explain_payload = handle_portfolio_explain(pool, symbol, use_mock=False, use_runtime=True)
    if not explain_payload.get("ok"):
        return {}
    data = explain_payload.get("data", {}) if isinstance(explain_payload.get("data"), dict) else {}
    item = data.get("item", {}) if isinstance(data.get("item"), dict) else {}
    if not item or str(item.get("symbol") or "") != symbol:
        return {}
    return holding_dashboard_row(agent_next_portfolio_item_for_dashboard(item), {})


def agent_next_portfolio_item_for_dashboard(item: Dict[str, object]) -> Dict[str, object]:
    row = dict(item)
    if "hotspot" not in row and isinstance(row.get("hotspot_context"), dict):
        row["hotspot"] = row.get("hotspot_context")
    if "commands" not in row:
        row["commands"] = portfolio_item_commands(row.get("symbol"))
    return row


def agent_next_focus_chain(pool: str, digest: Dict[str, object], handoff: Dict[str, object]) -> List[Dict[str, object]]:
    coverage = dashboard_coverage_context(digest)
    actions = dashboard_action_lane(digest, coverage)
    plan = dashboard_review_plan(pool, digest)
    compact_handoff = dashboard_handoff({"review_handoff": handoff, "review_completion": digest.get("review_completion", {})})
    today_focus = dashboard_today_focus(actions, plan, compact_handoff)
    chain = today_focus.get("focus_chain", []) if isinstance(today_focus.get("focus_chain"), list) else []
    return [dict(item) for item in chain if isinstance(item, dict)]


def agent_next_symbol_focus_chain(
    pool: str,
    symbol: str,
    handoff: Dict[str, object],
    cards: Dict[str, object],
    fallback: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen = set()
    for source in [handoff.get("command_chain", []), handoff.get("next_read", [])]:
        for item in source if isinstance(source, list) else []:
            add_agent_next_symbol_focus_item(rows, seen, item, pool, symbol, allow_global=False)
            if len(rows) >= 3:
                return rows
    for card in cards.get("cards", []) if isinstance(cards.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        add_agent_next_symbol_focus_item(
            rows,
            seen,
            {
                "source": "security_card",
                "title": "%s %s" % (card.get("symbol"), card.get("name") or ""),
                "json_command": card.get("next_json_command"),
                "done_when": "已确认该标的行情、板块、覆盖状态、证据缺口和下一步留档项。",
                "related_symbols": [card.get("symbol")],
            },
            pool,
            symbol,
            allow_global=False,
        )
        if len(rows) >= 3:
            return rows
        for command in card.get("commands", []) if isinstance(card.get("commands"), list) else []:
            add_agent_next_symbol_focus_item(
                rows,
                seen,
                {
                    "source": "security_card",
                    "title": "%s %s" % (card.get("symbol"), card.get("name") or ""),
                    "json_command": command,
                    "done_when": "已确认该标的行情、板块、覆盖状态、证据缺口和下一步留档项。",
                    "related_symbols": [card.get("symbol")],
                },
                pool,
                symbol,
                allow_global=False,
            )
            if len(rows) >= 3:
                return rows
    for item in fallback:
        symbols = item.get("related_symbols", []) if isinstance(item, dict) and isinstance(item.get("related_symbols"), list) else []
        if symbols and symbol not in symbols:
            continue
        add_agent_next_symbol_focus_item(rows, seen, item, pool, symbol, allow_global=False)
        if len(rows) >= 3:
            return rows
    return rows


def add_agent_next_symbol_focus_item(
    rows: List[Dict[str, object]],
    seen: set,
    item: object,
    pool: str,
    symbol: str,
    allow_global: bool = False,
) -> None:
    if not isinstance(item, dict):
        return
    command = with_pool_arg(str(item.get("json_command") or ""), pool)
    if not command or not digest_command_is_read_only(command):
        return
    related = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
    if related and symbol not in related:
        return
    if symbol not in command and not allow_global:
        return
    key = command
    if key in seen:
        return
    seen.add(key)
    related_symbols = related or ([symbol] if symbol in command else [])
    rows.append(
        {
            "rank": len(rows) + 1,
            "source": str(item.get("source") or item.get("item_type") or "symbol_focus"),
            "title": str(item.get("title") or symbol),
            "json_command": command,
            "done_when": str(item.get("done_when") or "已完成该标的复核。"),
            "runnable": True,
            "related_symbols": dedupe_queue_texts(related_symbols)[:5],
        }
    )


def handle_dashboard(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_quote_age_days: int = 3,
    max_steps: int = 8,
    use_mock: bool = False,
) -> Dict[str, Any]:
    if use_mock:
        return handle_mock_dashboard(pool=pool, top=top, map_top=map_top, max_steps=max_steps)

    run_payload = handle_agent_run(pool, top=top, map_top=map_top, max_quote_age_days=max_quote_age_days, max_steps=max_steps)
    run_data = run_payload.get("data", {}) if isinstance(run_payload.get("data"), dict) else {}
    digest = run_data.get("review_digest", {}) if isinstance(run_data.get("review_digest"), dict) else {}
    data = build_dashboard_data(pool, run_data, digest, max_steps=max_steps)
    return envelope(
        command="dashboard",
        data=data,
        warnings=run_payload.get("warnings", []) if isinstance(run_payload.get("warnings"), list) else [],
        errors=run_payload.get("errors", []) if isinstance(run_payload.get("errors"), list) else [],
        source=run_payload.get("meta", {}).get("source") if isinstance(run_payload.get("meta"), dict) else None,
        ok=bool(run_payload.get("ok")),
    )


def handle_mock_dashboard(
    pool: str = DEFAULT_POOL,
    top: int = 5,
    map_top: int = 2,
    max_steps: int = 8,
) -> Dict[str, Any]:
    scan_payload = handle_scan(pool, use_mock=True, top=max(top, 8), candidate_top=max(top * 2, 12))
    daily_payload = handle_daily(pool, use_mock=True, top=top, map_top=map_top)
    warnings = []
    for payload in (scan_payload, daily_payload):
        if isinstance(payload.get("warnings"), list):
            warnings.extend(payload.get("warnings", []))
    errors = []
    for payload in (scan_payload, daily_payload):
        if isinstance(payload.get("errors"), list):
            errors.extend(payload.get("errors", []))
    data = build_mock_dashboard_data(pool, scan_payload, daily_payload, max_steps=max_steps)
    return envelope(
        command="dashboard",
        data=data,
        warnings=warnings,
        errors=errors,
        source="mock",
        ok=bool(scan_payload.get("ok") and daily_payload.get("ok")),
    )


def build_mock_dashboard_data(
    pool: str,
    scan_payload: Dict[str, object],
    daily_payload: Dict[str, object],
    max_steps: int,
) -> Dict[str, object]:
    scan = scan_payload.get("data", {}) if isinstance(scan_payload.get("data"), dict) else {}
    daily = daily_payload.get("data", {}) if isinstance(daily_payload.get("data"), dict) else {}
    portfolio_review = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    coverage = mock_dashboard_coverage_context(daily)
    market = mock_dashboard_market_pulse(pool, scan)
    portfolio = mock_dashboard_portfolio_pulse(pool, portfolio_review)
    evidence = mock_dashboard_evidence_gaps(market, portfolio)
    plan = mock_dashboard_review_plan(pool, coverage, market, portfolio, evidence)
    actions = mock_dashboard_action_lane(plan)
    handoff = mock_dashboard_handoff(pool, plan)
    tiles = mock_dashboard_tiles(market, portfolio, evidence, plan)
    today_focus = dashboard_today_focus(actions, plan, handoff)
    action_summary = dashboard_action_summary(today_focus, handoff)
    return {
        "pool": pool,
        "state": "demo_ready" if scan_payload.get("ok") and daily_payload.get("ok") else "demo_blocked",
        "summary": mock_dashboard_summary(market, portfolio, plan),
        "source_agent_run_state": "mock_demo",
        "run_limits": {
            "max_steps": max_steps,
            "read_only_only": True,
            "writes_are_skipped": True,
            "mode": "mock",
        },
        "action_summary": action_summary,
        "today_focus": today_focus,
        "positioning": dashboard_positioning(pool, mode="mock"),
        "coverage_context": coverage,
        "tiles": tiles,
        "market_pulse": market,
        "portfolio_pulse": portfolio,
        "evidence_gaps": evidence,
        "action_lane": actions,
        "handoff": handoff,
        "review_plan": plan,
        "guardrails": [
            "mock dashboard 只演示报告结构，不读取个人 runtime 持仓或行情。",
            "dashboard 只整理复盘优先级和证据缺口，不生成买卖指令、目标价或仓位建议。",
            "正式复盘应先导入 runtime 行情、持仓和全 A 基础清单，再运行 market-intel dashboard --text。",
        ],
        "agent_contract": dashboard_contract(),
    }


def mock_dashboard_coverage_context(daily: Dict[str, object]) -> Dict[str, object]:
    coverage = daily.get("coverage_context", {}) if isinstance(daily.get("coverage_context"), dict) else {}
    compact = compact_dashboard_coverage_context(coverage)
    if compact.get("available"):
        compact["summary"] = "%s mock 示例；正式复盘需导入 runtime 后复验。" % (compact.get("summary") or "覆盖底座")
    return compact


def mock_dashboard_summary(
    market: Dict[str, object],
    portfolio: Dict[str, object],
    plan: Dict[str, object],
) -> str:
    candidates = market.get("candidates", []) if isinstance(market.get("candidates"), list) else []
    holdings = portfolio.get("top_holdings", []) if isinstance(portfolio.get("top_holdings"), list) else []
    steps = plan.get("items", []) if isinstance(plan.get("items"), list) else []
    return "mock 示例：全市场候选 %s 个，持仓重点 %s 个；复盘步骤 %s 个，用于试跑 dashboard 合同。" % (
        len(candidates),
        len(holdings),
        len(steps),
    )


def mock_dashboard_market_pulse(pool: str, scan: Dict[str, object]) -> Dict[str, object]:
    groups = scan.get("sector_groups", []) if isinstance(scan.get("sector_groups"), list) else []
    candidates = scan.get("candidate_securities", []) if isinstance(scan.get("candidate_securities"), list) else []
    return {
        "available": bool(scan),
        "summary": scan.get("summary") or "mock 全市场扫描示例。",
        "scan_mode": scan.get("scan_mode") or scan.get("mode") or "mock",
        "market_breadth": compact_dashboard_market_breadth(scan.get("market_breadth", {})),
        "quote_count": scan.get("quote_count", 0),
        "matched_quote_count": scan.get("matched_quote_count", 0),
        "top_groups": [mock_dashboard_group(item) for item in groups[:4] if isinstance(item, dict)],
        "seed_chains": [],
        "candidates": [mock_dashboard_candidate(pool, item) for item in candidates[:5] if isinstance(item, dict)],
        "candidate_queue": compact_dashboard_candidate_queue(scan.get("candidate_queue", {})),
        "questions": list(scan.get("questions", []))[:4] if isinstance(scan.get("questions"), list) else [],
        "write_policy": "mock 只读市场扫描，不读取 runtime，不生成交易指令。",
    }


def mock_dashboard_group(item: Dict[str, object]) -> Dict[str, object]:
    return {
        "rank": item.get("rank"),
        "group_type": item.get("group_type"),
        "name": item.get("name"),
        "score": item.get("score"),
        "active_member_count": item.get("active_member_count", 0),
        "member_count": item.get("member_count", 0),
    }


def mock_dashboard_candidate(pool: str, item: Dict[str, object]) -> Dict[str, object]:
    commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
    symbol = item.get("symbol")
    fallback = (
        with_pool_arg("market-intel pool explain %s --json" % symbol, pool)
        if symbol
        else with_pool_arg("market-intel scan --mock --json", pool)
    )
    json_command = mock_dashboard_json_command(commands, fallback)
    review_focus = compact_scan_review_focus_with_next(item.get("review_focus", {}), json_command)
    return {
        "rank": item.get("rank"),
        "symbol": symbol,
        "name": item.get("name"),
        "review_score": item.get("review_score"),
        "ranking_breakdown": compact_dashboard_ranking_breakdown(item.get("ranking_breakdown", {})),
        "coverage_state": item.get("coverage_state"),
        "universe_context": compact_dashboard_universe_context(item.get("universe_context", {})),
        "review_focus": review_focus,
        "why_now": item.get("why_now"),
        "json_command": json_command,
    }


def mock_dashboard_portfolio_pulse(pool: str, portfolio_review: Dict[str, object]) -> Dict[str, object]:
    holdings = portfolio_review.get("items", []) if isinstance(portfolio_review.get("items"), list) else []
    repeated = portfolio_review.get("repeated_exposures", []) if isinstance(portfolio_review.get("repeated_exposures"), list) else []
    overlap = portfolio_review.get("repeated_overlap_groups", []) if isinstance(portfolio_review.get("repeated_overlap_groups"), list) else []
    top_holdings = []
    for item in holdings[:5]:
        if isinstance(item, dict):
            top_holdings.append(mock_dashboard_holding(pool, item, len(top_holdings) + 1))
    pressure_groups = [mock_dashboard_pressure_group(pool, "chain", item) for item in repeated[:2] if isinstance(item, dict)]
    pressure_groups.extend(mock_dashboard_pressure_group(pool, "theme", item) for item in overlap[:2] if isinstance(item, dict))
    high_count = sum(1 for item in holdings if isinstance(item, dict) and item.get("priority") == "high_review")
    buckets = {
        "high_review": high_count,
        "missing_quote": sum(1 for item in holdings if isinstance(item, dict) and not item.get("has_quote")),
        "without_hotspot": sum(
            1
            for item in holdings
            if isinstance(item, dict) and not isinstance(item.get("hotspot_context"), dict)
        ),
        "with_overlap": sum(
            1
            for item in holdings
            if isinstance(item, dict) and item.get("overlap_groups")
        ),
    }
    return {
        "available": bool(portfolio_review),
        "summary": portfolio_review.get("summary") or "mock 持仓复盘示例。",
        "holding_count": portfolio_review.get("holding_count", len(holdings)),
        "high_review_count": high_count,
        "changed_holding_count": 0,
        "buckets": buckets,
        "top_holdings": top_holdings,
        "pressure_groups": pressure_groups[:3],
        "questions": list(portfolio_review.get("questions", []))[:4] if isinstance(portfolio_review.get("questions"), list) else [],
        "write_policy": "mock 只读持仓复盘，不读取个人 runtime，不自动修改持仓或写入 journal。",
    }


def mock_dashboard_holding(pool: str, item: Dict[str, object], rank: int) -> Dict[str, object]:
    symbol = item.get("symbol")
    command = (
        with_pool_arg("market-intel portfolio explain %s --mock --json" % symbol, pool)
        if symbol
        else with_pool_arg("market-intel portfolio review --mock --json", pool)
    )
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    hotspot_chain = "%s/%s" % (hotspot.get("layer"), hotspot.get("sub_sector")) if hotspot.get("layer") or hotspot.get("sub_sector") else ""
    return {
        "rank": rank,
        "symbol": symbol,
        "name": item.get("name"),
        "priority": item.get("priority"),
        "review_score": item.get("priority_score"),
        "coverage_state": item.get("coverage_state"),
        "change_priority": 0,
        "primary_question": mock_holding_primary_question(item),
        "primary_json_command": command,
        "risk_flags": list(item.get("risk_flags", []))[:5] if isinstance(item.get("risk_flags"), list) else [],
        "has_quote": bool(item.get("has_quote")),
        "hotspot": {"chain": hotspot_chain} if hotspot_chain else {},
        "overlap_groups": list(item.get("overlap_groups", []))[:4] if isinstance(item.get("overlap_groups"), list) else [],
    }


def mock_holding_primary_question(item: Dict[str, object]) -> str:
    points = item.get("review_points", []) if isinstance(item.get("review_points"), list) else []
    if points:
        return str(points[0])
    return "读取该持仓的行情、热点、风险和组合暴露。"


def mock_dashboard_pressure_group(pool: str, group_type: str, item: Dict[str, object]) -> Dict[str, object]:
    group = str(item.get("group") or "")
    return {
        "group_type": group_type,
        "group": group,
        "holding_count": item.get("holding_count", 0),
        "priority_question": "%s 是否来自同一驱动，需要核对组合集中度。" % group if group else "核对组合集中度。",
        "primary_json_command": with_pool_arg("market-intel portfolio review --mock --json", pool),
    }


def mock_dashboard_evidence_gaps(
    market: Dict[str, object],
    portfolio: Dict[str, object],
) -> Dict[str, object]:
    rows: List[Dict[str, object]] = []
    for item in portfolio.get("top_holdings", []) if isinstance(portfolio.get("top_holdings"), list) else []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("coverage_state") or "")
        missing = []
        if not item.get("has_quote"):
            missing.append("行情源")
        if status != "confirmed":
            missing.append("核心逻辑、关键证据和证伪风险")
        if not missing:
            continue
        rows.append(
            mock_dashboard_gap_item(
                len(rows) + 1,
                "holding_review",
                "%s %s" % (item.get("symbol"), item.get("name") or ""),
                status or "missing",
                [item.get("symbol")],
                missing,
                item.get("primary_json_command"),
            )
        )
    for item in market.get("candidates", []) if isinstance(market.get("candidates"), list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("coverage_state") == "confirmed":
            continue
        rows.append(
            mock_dashboard_gap_item(
                len(rows) + 1,
                "market_scan",
                "%s %s" % (item.get("symbol"), item.get("name") or ""),
                item.get("coverage_state") or "draft",
                [item.get("symbol")],
                ["行业/主题链路、公司角色、研究证据"],
                item.get("json_command"),
            )
        )
        if len(rows) >= 6:
            break
    summary = "mock 证据缺口 %s 项，重点看 coverage_state 不是 confirmed 的标的。" % len(rows)
    return {
        "available": bool(rows),
        "summary": summary,
        "data_repair": {"available": False},
        "items": rows[:6],
        "write_policy": "mock 只整理证据充分性；不生成交易指令或自动写入 journal。",
    }


def mock_dashboard_gap_item(
    rank: int,
    item_type: str,
    title: str,
    status: object,
    symbols: List[object],
    missing: List[object],
    command: object,
) -> Dict[str, object]:
    return {
        "rank": rank,
        "item_type": item_type,
        "title": title,
        "coverage_status": "pending" if status != "confirmed" else "covered",
        "coverage_label": str(status or "pending"),
        "related_symbols": dedupe_queue_texts(symbols),
        "missing_evidence": dedupe_queue_texts(missing),
        "json_command": str(command or ""),
        "done_when": "已补齐或记录缺失原因，正式复盘时用 runtime 复验。",
    }


def mock_dashboard_review_plan(
    pool: str,
    coverage: Dict[str, object],
    market: Dict[str, object],
    portfolio: Dict[str, object],
    evidence: Dict[str, object],
) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    add_mock_dashboard_runtime_setup(items)
    add_dashboard_plan_coverage(items, coverage, pool, "mock")
    candidates = market.get("candidates", []) if isinstance(market.get("candidates"), list) else []
    groups = market.get("top_groups", []) if isinstance(market.get("top_groups"), list) else []
    if market.get("available"):
        items.append(
            dashboard_plan_item(
                "market_scan",
                "先读全市场强弱",
                market.get("summary") or "确认全市场板块和候选复盘标的。",
                with_pool_arg("market-intel scan --mock --json", pool),
                "read",
                "已记录 mock 最强板块、候选标的和覆盖状态。",
                related_symbols=[item.get("symbol") for item in candidates[:5] if isinstance(item, dict)],
                evidence=dashboard_market_plan_evidence(groups, candidates),
            )
        )
    add_dashboard_plan_candidate_queue(items, market, pool, "mock")
    for holding in portfolio.get("top_holdings", [])[:2] if isinstance(portfolio.get("top_holdings"), list) else []:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        command = holding.get("primary_json_command") or "market-intel portfolio explain %s --mock --json" % holding.get("symbol")
        items.append(
            dashboard_plan_item(
                "holding_review",
                "%s %s" % (holding.get("symbol"), holding.get("name") or ""),
                holding.get("primary_question") or "读取该持仓的行情、热点、风险和组合暴露。",
                command,
                "read",
                "已确认 mock 单票复核字段和证据缺口。",
                related_symbols=[holding.get("symbol")],
                evidence=attention_holding_evidence(holding),
            )
        )
    seen = {str(item.get("json_command") or "") for item in items if isinstance(item, dict)}
    for gap in evidence.get("items", []) if isinstance(evidence.get("items"), list) else []:
        if not isinstance(gap, dict):
            continue
        command = str(gap.get("json_command") or "")
        if not command or command in seen:
            continue
        items.append(
            dashboard_plan_item(
                str(gap.get("item_type") or "evidence"),
                gap.get("title") or "证据缺口",
                "补齐 mock 缺口对应的正式证据来源。",
                command,
                "read",
                gap.get("done_when") or "已补齐或记录缺失原因。",
                related_symbols=gap.get("related_symbols", []) if isinstance(gap.get("related_symbols"), list) else [],
                evidence=gap.get("missing_evidence", []) if isinstance(gap.get("missing_evidence"), list) else [],
            )
        )
        seen.add(command)
        if len(items) >= 6:
            break
    items.append(
        dashboard_plan_item(
            "journal_record",
            "切换正式复盘",
            "mock 不写 journal；导入 runtime 后再保存日报和复盘笔记。",
            with_pool_arg("market-intel dashboard --text", pool),
            "manual",
            "已用 runtime 数据重新生成 dashboard，并由人工确认后留档。",
            requires_manual=True,
        )
    )
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    return {
        "available": bool(items),
        "summary": dashboard_review_plan_summary(items),
        "items": items[:10],
        "write_policy": "mock review_plan 只安排试跑顺序；正式写入和研究结论仍需人工确认。",
    }


def add_mock_dashboard_runtime_setup(items: List[Dict[str, object]]) -> None:
    items.append(
        dashboard_plan_item(
            "runtime_setup",
            "准备正式 runtime 数据",
            "mock 只验证工作台结构；正式复盘先确认行情、持仓、全 A 基础清单和研究证据 CSV 字段。",
            "market-intel import schema --json",
            "read",
            "已确认可导入字段，并准备 quotes、holdings、a_share_universe 和 research_notes 文件。",
            evidence=[
                "需要 quotes/holdings 才能生成个人复盘。",
                "需要 a_share_universe 才能减少全 A 种子覆盖偏差。",
                "需要 research_notes 才能把 foundation 升级为 confirmed。",
            ],
        )
    )


def mock_dashboard_action_lane(plan: Dict[str, object]) -> Dict[str, object]:
    rows = []
    for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": len(rows) + 1,
                "item_type": item.get("item_type"),
                "title": item.get("title"),
                "reason": item.get("reason"),
                "json_command": item.get("json_command"),
                "runnable": bool(item.get("runnable")),
                "requires_manual": bool(item.get("requires_manual")),
                "already_read": False,
                "related_symbols": list(item.get("related_symbols", []))[:5] if isinstance(item.get("related_symbols"), list) else [],
                "done_when": item.get("done_when"),
            }
        )
    return {
        "available": bool(rows),
        "summary": "mock 行动队列 %s 项，其中只读 %s 项。" % (
            len(rows),
            sum(1 for item in rows if item.get("runnable")),
        ),
        "items": rows[:6],
        "write_policy": "mock 队列只演示接力顺序；写入类命令需切换 runtime 后人工确认。",
    }


def mock_dashboard_handoff(pool: str, plan: Dict[str, object]) -> Dict[str, object]:
    items = plan.get("items", []) if isinstance(plan.get("items"), list) else []
    next_read = []
    for item in items:
        if not isinstance(item, dict) or not item.get("runnable") or not item.get("json_command"):
            continue
        next_read.append(
            {
                "rank": len(next_read) + 1,
                "source": item.get("item_type"),
                "title": item.get("title"),
                "reason": item.get("reason"),
                "json_command": item.get("json_command"),
                "done_when": item.get("done_when"),
            }
        )
        if len(next_read) >= 4:
            break
    manual_items = [
        {
            "rank": 1,
            "source": "mock_to_runtime",
            "title": "初始化 runtime 并导入数据",
            "reason": "mock 示例不能代表真实持仓或全市场结论。",
            "json_command": "market-intel init runtime --json",
            "done_when": "已初始化 runtime，并导入行情、持仓和全 A 基础清单文件。",
        }
    ]
    completion = {
        "completion_state": "demo",
        "ready_for_journal_note": False,
        "blocking_count": 0,
        "manual_required_count": 1,
        "pending_count": len(next_read),
    }
    return {
        "available": bool(next_read),
        "summary": "mock 示例已生成；正式使用请导入 runtime 后运行 %s。" % with_pool_arg("market-intel dashboard --text", pool),
        "handoff_state": "demo",
        "resume_prompt": "接手复盘：先运行 %s 理解结构，再切换 runtime。" % with_pool_arg("market-intel dashboard --mock --text", pool),
        "next_read": next_read,
        "manual_items": manual_items,
        "record_templates": [],
        "completion": completion,
        "completion_checklist": dashboard_completion_checklist(completion, next_read, manual_items),
        "journal_gate": dashboard_journal_gate(completion, next_read, manual_items, []),
    }


def mock_dashboard_tiles(
    market: Dict[str, object],
    portfolio: Dict[str, object],
    evidence: Dict[str, object],
    plan: Dict[str, object],
) -> List[Dict[str, object]]:
    groups = market.get("top_groups", []) if isinstance(market.get("top_groups"), list) else []
    candidates = market.get("candidates", []) if isinstance(market.get("candidates"), list) else []
    gaps = evidence.get("items", []) if isinstance(evidence.get("items"), list) else []
    steps = plan.get("items", []) if isinstance(plan.get("items"), list) else []
    return [
        dashboard_tile("market", "全市场", len(groups), market.get("summary")),
        dashboard_tile("candidates", "候选标的", len(candidates), "mock scan 的候选复盘标的。"),
        dashboard_tile("holdings", "持仓重点", portfolio.get("high_review_count", 0), portfolio.get("summary")),
        dashboard_tile("pressure", "组合压力", len(portfolio.get("pressure_groups", []) if isinstance(portfolio.get("pressure_groups"), list) else []), "mock 重复链路/主题暴露。"),
        dashboard_tile("evidence", "证据缺口", len(gaps), evidence.get("summary")),
        dashboard_tile("handoff", "复盘步骤", len(steps), plan.get("summary")),
    ]


def mock_dashboard_json_command(commands: List[object], fallback: str) -> str:
    for command in commands:
        text = str(command or "")
        if not text:
            continue
        return digest_json_variant(text)
    return fallback


def build_dashboard_data(
    pool: str,
    run_data: Dict[str, object],
    digest: Dict[str, object],
    max_steps: int,
) -> Dict[str, object]:
    coverage = dashboard_coverage_context(digest)
    market = dashboard_market_pulse(digest)
    portfolio = dashboard_portfolio_pulse(digest)
    evidence = dashboard_evidence_gaps(digest)
    actions = dashboard_action_lane(digest, coverage)
    handoff = dashboard_handoff(digest)
    plan = dashboard_review_plan(pool, digest)
    today_focus = dashboard_today_focus(actions, plan, handoff)
    action_summary = dashboard_action_summary(today_focus, handoff)
    return {
        "pool": pool,
        "state": dashboard_state(run_data, digest),
        "summary": dashboard_summary(run_data, digest),
        "source_agent_run_state": run_data.get("state"),
        "run_limits": run_data.get("run_limits", {"max_steps": max_steps, "read_only_only": True, "writes_are_skipped": True}),
        "action_summary": action_summary,
        "today_focus": today_focus,
        "positioning": dashboard_positioning(pool, mode="runtime"),
        "coverage_context": coverage,
        "tiles": dashboard_tiles(digest),
        "market_pulse": market,
        "portfolio_pulse": portfolio,
        "evidence_gaps": evidence,
        "action_lane": actions,
        "handoff": handoff,
        "review_plan": plan,
        "guardrails": [
            "dashboard 只整理复盘优先级和证据缺口，不生成买卖指令、目标价或仓位建议。",
            "全 A 结论受行情源、A 股基础清单和研究证据覆盖度影响。",
            "写入 journal 或导入 runtime 的命令需要人工确认后执行。",
        ],
        "agent_contract": dashboard_contract(),
    }


def dashboard_positioning(pool: str, mode: str) -> Dict[str, object]:
    return {
        "headline": "面向全 A 的个人复盘操作系统，不是行情 App、交易入口或买卖建议引擎。",
        "pool": pool,
        "mode": mode,
        "scope": "默认按全 A 复盘闭环组织信息；主题池只是覆盖样例或局部视角。",
        "differentiators": [
            {
                "id": "coverage_boundary",
                "label": "先确认覆盖边界",
                "agent_path": "data.coverage_context",
                "done_when": "已确认 A 股基础清单、行业/概念/指数字段完整度、数据质量队列和覆盖缺口。",
            },
            {
                "id": "holding_first",
                "label": "持仓优先映射",
                "agent_path": "data.portfolio_pulse",
                "done_when": "已确认持仓是否进入热点、是否缺行情/上下文、是否存在重复链路或主题暴露。",
            },
            {
                "id": "evidence_loop",
                "label": "证据闭环",
                "agent_path": "data.evidence_gaps",
                "done_when": "已把未覆盖、foundation、draft 和数据修复项转成可复核命令和完成标准。",
            },
            {
                "id": "agent_handoff",
                "label": "agent 可接力",
                "agent_path": "data.review_plan",
                "done_when": "已生成只读 JSON 命令、人工确认项、journal 前置和 done_when。",
            },
        ],
        "not_competing_on": [
            "实时盘口、交易通道和账户管理。",
            "资讯流、社区分发和大 V 内容消费。",
            "黑盒诊股、目标价、仓位建议和自动下单。",
        ],
        "selection_rule": "新功能必须增强全 A 覆盖、持仓复核、证据留痕或 agent 接力；否则只作为外部输入，不进入核心工作台。",
        "write_policy": "positioning 只说明产品边界和复盘取舍，不生成交易指令。",
    }


def dashboard_coverage_context(digest: Dict[str, object]) -> Dict[str, object]:
    coverage = digest.get("coverage_context", {}) if isinstance(digest.get("coverage_context"), dict) else {}
    return compact_dashboard_coverage_context(coverage)


def compact_dashboard_coverage_context(coverage: Dict[str, object]) -> Dict[str, object]:
    if not coverage.get("available"):
        return {"available": False, "summary": coverage.get("summary") or "暂无复盘池覆盖上下文。"}
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    raw_gaps = coverage.get("gaps") if isinstance(coverage.get("gaps"), list) else None
    gaps = raw_gaps if raw_gaps is not None else coverage.get("top_gaps", [])
    raw_quality_queue = coverage.get("data_quality_queue") if isinstance(coverage.get("data_quality_queue"), list) else coverage.get("top_data_quality_queue")
    data_quality_queue = raw_quality_queue if isinstance(raw_quality_queue, list) else []
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
    return {
        "available": True,
        "pool": coverage.get("pool"),
        "scope": coverage.get("scope"),
        "status": coverage.get("status"),
        "summary": coverage.get("summary"),
        "universe": {
            "available": bool(universe.get("available")),
            "record_count": universe.get("record_count", 0),
            "industry_count": universe.get("industry_count", 0),
            "concept_count": universe.get("concept_count", 0),
            "index_membership_count": universe.get("index_membership_count", 0),
            "enrichment_queue": compact_universe_enrichment_queue(universe.get("enrichment_queue", [])),
            "sector_profile": {
                "industry_coverage_ratio": profile.get("industry_coverage_ratio", 0),
                "concept_coverage_ratio": profile.get("concept_coverage_ratio", 0),
                "index_coverage_ratio": profile.get("index_coverage_ratio", 0),
                "top_industries": list(profile.get("top_industries", []))[:5] if isinstance(profile.get("top_industries"), list) else [],
                "top_concepts": list(profile.get("top_concepts", []))[:5] if isinstance(profile.get("top_concepts"), list) else [],
                "top_indexes": list(profile.get("top_indexes", []))[:5] if isinstance(profile.get("top_indexes"), list) else [],
                "missing_field_counts": profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {},
                "missing_field_samples": list(profile.get("missing_field_samples", []))[:5] if isinstance(profile.get("missing_field_samples"), list) else [],
                "coverage_flags": list(profile.get("coverage_flags", [])) if isinstance(profile.get("coverage_flags"), list) else [],
            },
        },
        "holdings_coverage": compact_dashboard_holdings_coverage(coverage.get("holdings_coverage", {})),
        "gap_count": len(gaps) if isinstance(gaps, list) else 0,
        "top_gaps": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in gaps[:5]
            if isinstance(item, dict)
        ] if isinstance(gaps, list) else [],
        "top_data_quality_queue": compact_data_quality_queue(data_quality_queue),
        "next_actions": [
            {
                "rank": item.get("rank"),
                "id": item.get("id"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
            }
            for item in actions[:5]
            if isinstance(item, dict)
        ],
        "write_policy": "只说明复盘池和全 A 基础清单覆盖边界，不生成交易指令。",
    }


def compact_universe_enrichment_queue(value: object) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    compact = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        samples = item.get("samples", []) if isinstance(item.get("samples"), list) else []
        compact.append(
            {
                "rank": item.get("rank"),
                "field": item.get("field"),
                "label": item.get("label"),
                "severity": item.get("severity"),
                "missing_count": item.get("missing_count", 0),
                "missing_ratio": item.get("missing_ratio", 0),
                "reason": item.get("reason"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
                "samples": [
                    {
                        "symbol": sample.get("symbol"),
                        "name": sample.get("name"),
                    }
                    for sample in samples[:3]
                    if isinstance(sample, dict)
                ],
            }
        )
    return compact


def compact_dashboard_holdings_coverage(value: object) -> Dict[str, object]:
    coverage = value if isinstance(value, dict) else {}
    if not coverage.get("available"):
        return {
            "available": False,
            "reason": coverage.get("reason"),
            "summary": coverage.get("summary") or coverage.get("reason") or "未提供持仓。",
            "holding_count": 0,
            "matched_count": 0,
            "unmatched_count": 0,
            "matched_ratio": 0,
            "needs_review_count": 0,
            "coverage_flags": [],
            "top_review_queue": [],
            "top_unmatched": [],
        }
    review_queue = coverage.get("review_queue", []) if isinstance(coverage.get("review_queue"), list) else []
    unmatched = coverage.get("unmatched", []) if isinstance(coverage.get("unmatched"), list) else []
    return {
        "available": True,
        "summary": coverage.get("summary"),
        "holding_count": coverage.get("holding_count", 0),
        "matched_count": coverage.get("matched_count", 0),
        "unmatched_count": coverage.get("unmatched_count", 0),
        "confirmed_count": coverage.get("confirmed_count", 0),
        "draft_matched_count": coverage.get("draft_matched_count", 0),
        "foundation_matched_count": coverage.get("foundation_matched_count", 0),
        "needs_review_count": coverage.get("needs_review_count", 0),
        "matched_ratio": coverage.get("matched_ratio", 0),
        "coverage_flags": list(coverage.get("coverage_flags", []))[:5] if isinstance(coverage.get("coverage_flags"), list) else [],
        "top_review_queue": [
            {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "coverage_state": item.get("coverage_state"),
                "reasons": list(item.get("reasons", []))[:3] if isinstance(item.get("reasons"), list) else [],
                "json_command": digest_json_variant(item.get("command")),
                "done_when": item.get("done_when"),
            }
            for item in review_queue[:3]
            if isinstance(item, dict)
        ],
        "top_unmatched": [
            {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "reason": item.get("reason"),
                "suggested_action": item.get("suggested_action"),
            }
            for item in unmatched[:3]
            if isinstance(item, dict)
        ],
    }


def compact_data_quality_queue(rows: List[object]) -> List[Dict[str, object]]:
    compact = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        samples = item.get("samples", []) if isinstance(item.get("samples"), list) else []
        compact.append(
            {
                "rank": item.get("rank"),
                "flag": item.get("flag"),
                "severity": item.get("severity"),
                "category": item.get("category"),
                "affected_count": item.get("affected_count", 0),
                "suggested_action": item.get("suggested_action"),
                "done_when": item.get("done_when"),
                "review_command": item.get("review_command"),
                "samples": [
                    {
                        "symbol": sample.get("symbol"),
                        "name": sample.get("name"),
                        "raw_row": sample.get("raw_row"),
                        "raw_code": sample.get("raw_code"),
                    }
                    for sample in samples[:3]
                    if isinstance(sample, dict)
                ],
            }
        )
    return compact


def dashboard_state(run_data: Dict[str, object], digest: Dict[str, object]) -> str:
    if not digest.get("available"):
        return "blocked" if str(run_data.get("state") or "").startswith("blocked") else "degraded"
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    if safe_int(completion.get("blocking_count")):
        return "blocked_review"
    if safe_int(completion.get("manual_required_count")) or safe_int(completion.get("pending_count")):
        return "needs_review"
    return "ready_for_note"


def dashboard_summary(run_data: Dict[str, object], digest: Dict[str, object]) -> str:
    if not digest.get("available"):
        return str(run_data.get("summary") or "runtime 暂不可生成复盘工作台。")
    market = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    portfolio = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    return "全市场候选 %s 个，持仓重点 %s 个；复盘状态 %s，待读 %s 个，需人工 %s 个。" % (
        len(market.get("top_candidates", []) if isinstance(market.get("top_candidates"), list) else []),
        portfolio.get("high_review_count", 0),
        completion.get("completion_state") or "unknown",
        completion.get("pending_count", 0),
        completion.get("manual_required_count", 0),
    )


def dashboard_tiles(digest: Dict[str, object]) -> List[Dict[str, object]]:
    scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    portfolio = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    evidence = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    return [
        dashboard_tile("market", "全市场", len(scan.get("top_groups", []) if isinstance(scan.get("top_groups"), list) else []), scan.get("summary")),
        dashboard_tile("candidates", "候选标的", len(scan.get("top_candidates", []) if isinstance(scan.get("top_candidates"), list) else []), "来自 scan 的候选复盘标的。"),
        dashboard_tile("holdings", "持仓重点", portfolio.get("high_review_count", 0), portfolio.get("summary")),
        dashboard_tile("pressure", "组合压力", pressure.get("group_count", 0), pressure.get("summary")),
        dashboard_tile("evidence", "证据缺口", dashboard_pending_evidence_count(evidence), evidence.get("summary")),
        dashboard_tile("handoff", "待读/人工", "%s/%s" % (completion.get("pending_count", 0), completion.get("manual_required_count", 0)), completion.get("summary")),
    ]


def dashboard_tile(tile_id: str, label_text: str, value: object, detail: object) -> Dict[str, object]:
    return {
        "id": tile_id,
        "label": label_text,
        "value": value,
        "detail": detail,
    }


def dashboard_market_pulse(digest: Dict[str, object]) -> Dict[str, object]:
    scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    structure = digest.get("market_structure", {}) if isinstance(digest.get("market_structure"), dict) else {}
    return {
        "available": bool(scan.get("available") or structure),
        "summary": scan.get("summary") or structure.get("summary") or "暂无全市场扫描。",
        "scan_mode": scan.get("scan_mode"),
        "market_breadth": compact_dashboard_market_breadth(scan.get("market_breadth", {})),
        "quote_count": scan.get("quote_count", 0),
        "matched_quote_count": scan.get("matched_quote_count", 0),
        "top_groups": list(scan.get("top_groups", []))[:4] if isinstance(scan.get("top_groups"), list) else [],
        "seed_chains": list(structure.get("top_chains", []))[:3] if isinstance(structure.get("top_chains"), list) else [],
        "candidates": dashboard_scan_candidates(scan),
        "candidate_queue": compact_dashboard_candidate_queue(scan.get("candidate_queue", {})),
        "questions": list(scan.get("questions", []))[:4] if isinstance(scan.get("questions"), list) else [],
        "write_policy": scan.get("write_policy") or "只读市场扫描，不生成交易指令。",
    }


def dashboard_scan_candidates(scan: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for item in scan.get("top_candidates", []) if isinstance(scan.get("top_candidates"), list) else []:
        if not isinstance(item, dict):
            continue
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        json_command = digest_json_variant(commands[0]) if commands else "market-intel pool explain %s --runtime --json" % item.get("symbol")
        review_focus = compact_scan_review_focus_with_next(item.get("review_focus", {}), json_command)
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "review_score": item.get("review_score"),
                "ranking_breakdown": compact_dashboard_ranking_breakdown(item.get("ranking_breakdown", {})),
                "coverage_state": item.get("coverage_state"),
                "universe_context": compact_dashboard_universe_context(item.get("universe_context", {})),
                "review_focus": review_focus,
                "why_now": item.get("why_now"),
                "json_command": json_command,
            }
        )
    return rows[:5]


def compact_dashboard_market_breadth(value: object) -> Dict[str, object]:
    breadth = value if isinstance(value, dict) else {}
    if not breadth:
        return {}
    return {
        "state": breadth.get("state"),
        "confidence": breadth.get("confidence"),
        "summary": breadth.get("summary"),
        "sample_note": breadth.get("sample_note"),
        "matched_quote_count": breadth.get("matched_quote_count", 0),
        "up_count": breadth.get("up_count", 0),
        "down_count": breadth.get("down_count", 0),
        "active_count": breadth.get("active_count", 0),
        "strong_count": breadth.get("strong_count", 0),
        "stage_high_count": breadth.get("stage_high_count", 0),
        "active_group_count": breadth.get("active_group_count", 0),
        "strong_group_count": breadth.get("strong_group_count", 0),
        "interpretation": breadth.get("interpretation"),
    }


def compact_dashboard_universe_context(value: object) -> Dict[str, object]:
    context = value if isinstance(value, dict) else {}
    top_contexts = context.get("top_contexts", []) if isinstance(context.get("top_contexts"), list) else []
    return {
        "available": bool(context.get("available")),
        "dimensions": list(context.get("dimensions", []))[:3] if isinstance(context.get("dimensions"), list) else [],
        "dimension_count": context.get("dimension_count", 0),
        "industry": context.get("industry"),
        "concept_count": context.get("concept_count", 0),
        "index_membership_count": context.get("index_membership_count", 0),
        "context_count": context.get("context_count", 0),
        "top_contexts": [
            {
                "group_type": item.get("group_type"),
                "name": item.get("name"),
                "score": item.get("score"),
                "rank": item.get("rank"),
            }
            for item in top_contexts[:3]
            if isinstance(item, dict)
        ],
        "score_bonus": context.get("score_bonus", 0),
        "explain": context.get("explain"),
    }


def compact_scan_review_focus_with_next(value: object, next_command: object) -> Dict[str, object]:
    focus = compact_scan_review_focus(value)
    if next_command:
        focus["next_command"] = next_command
    return focus


def compact_dashboard_ranking_breakdown(value: object) -> Dict[str, object]:
    data = value if isinstance(value, dict) else {}
    factors = data.get("factors", data.get("top_factors", []))
    penalties = data.get("penalty_flags", [])
    return {
        "total_score": data.get("total_score"),
        "raw_score": data.get("raw_score"),
        "penalty_score": data.get("penalty_score"),
        "top_factors": compact_dashboard_ranking_rows(factors),
        "penalty_flags": compact_dashboard_ranking_rows(penalties),
        "summary": data.get("summary"),
    }


def compact_dashboard_ranking_rows(value: object) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    return [
        {
            "id": item.get("id"),
            "score": item.get("score"),
            "reason": item.get("reason"),
        }
        for item in sorted(
            (row for row in rows if isinstance(row, dict)),
            key=lambda row: -float(row.get("score") or 0),
        )[:4]
    ]


def compact_dashboard_candidate_queue(value: object) -> Dict[str, object]:
    queue = value if isinstance(value, dict) else {}
    if not queue:
        return {}
    buckets = queue.get("buckets", {}) if isinstance(queue.get("buckets"), dict) else {}
    return {
        "summary": queue.get("summary"),
        "buckets": {
            "review_now": compact_dashboard_candidate_queue_bucket(buckets.get("review_now", {})),
            "deprioritized": compact_dashboard_candidate_queue_bucket(buckets.get("deprioritized", {})),
            "data_first": compact_dashboard_candidate_queue_bucket(buckets.get("data_first", {})),
        },
    }


def compact_dashboard_candidate_queue_bucket(value: object) -> Dict[str, object]:
    bucket = value if isinstance(value, dict) else {}
    return {
        "label": bucket.get("label"),
        "summary": bucket.get("summary"),
        "count": bucket.get("count", 0),
        "items": [
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "review_score": item.get("review_score"),
                "coverage_state": item.get("coverage_state"),
                "is_holding": bool(item.get("is_holding")),
                "reason": item.get("reason"),
                "next_command": item.get("next_command"),
            }
            for item in (bucket.get("items", []) if isinstance(bucket.get("items"), list) else [])[:4]
            if isinstance(item, dict)
        ],
    }


def dashboard_portfolio_pulse(digest: Dict[str, object]) -> Dict[str, object]:
    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    return {
        "available": bool(dashboard.get("available")),
        "summary": dashboard.get("summary") or "暂无持仓复盘。",
        "holding_count": dashboard.get("holding_count", 0),
        "high_review_count": dashboard.get("high_review_count", 0),
        "changed_holding_count": dashboard.get("changed_holding_count", 0),
        "buckets": dashboard.get("buckets", {}) if isinstance(dashboard.get("buckets"), dict) else {},
        "top_holdings": dashboard_portfolio_holdings(dashboard),
        "pressure_groups": list(pressure.get("groups", []))[:3] if isinstance(pressure.get("groups"), list) else [],
        "questions": list(dashboard.get("questions", []))[:4] if isinstance(dashboard.get("questions"), list) else [],
        "write_policy": dashboard.get("write_policy") or "只读持仓复盘，不自动修改持仓或写入 journal。",
    }


def dashboard_portfolio_holdings(dashboard: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for item in dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": len(rows) + 1,
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "priority": item.get("priority"),
                "review_score": item.get("review_score"),
                "coverage_state": item.get("coverage_state"),
                "change_priority": item.get("change_priority"),
                "primary_question": item.get("primary_question"),
                "primary_json_command": item.get("primary_json_command"),
                "risk_flags": list(item.get("risk_flags", []))[:5] if isinstance(item.get("risk_flags"), list) else [],
            }
        )
    return rows[:5]


def dashboard_evidence_gaps(digest: Dict[str, object]) -> Dict[str, object]:
    evidence = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    items = evidence.get("items", []) if isinstance(evidence.get("items"), list) else []
    gaps = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("coverage_status") == "covered":
            continue
        gaps.append(
            {
                "rank": len(gaps) + 1,
                "item_type": item.get("item_type"),
                "title": item.get("title"),
                "coverage_status": item.get("coverage_status"),
                "coverage_label": item.get("coverage_label"),
                "related_symbols": list(item.get("related_symbols", []))[:5] if isinstance(item.get("related_symbols"), list) else [],
                "missing_evidence": list(item.get("missing_evidence", []))[:4] if isinstance(item.get("missing_evidence"), list) else [],
                "json_command": item.get("json_command"),
                "done_when": item.get("done_when"),
            }
        )
    return {
        "available": bool(gaps or repair.get("available")),
        "summary": evidence.get("summary") or repair.get("summary") or "暂无证据缺口。",
        "data_repair": repair if isinstance(repair, dict) and repair.get("available") else {"available": False},
        "items": gaps[:6],
        "write_policy": "只整理证据充分性；不生成交易指令或自动写入 journal。",
    }


def dashboard_pending_evidence_count(evidence: Dict[str, object]) -> int:
    return sum(
        1
        for item in evidence.get("items", []) if isinstance(evidence.get("items"), list)
        if isinstance(item, dict) and item.get("coverage_status") != "covered"
    )


def dashboard_action_lane(digest: Dict[str, object], coverage: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    attention = digest.get("attention_queue", {}) if isinstance(digest.get("attention_queue"), dict) else {}
    items = attention.get("items", []) if isinstance(attention.get("items"), list) else []
    rows = []
    rows.extend(dashboard_coverage_action_items(coverage or {}))
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": len(rows) + 1,
                "item_type": item.get("item_type"),
                "title": item.get("title"),
                "reason": item.get("reason"),
                "json_command": item.get("json_command"),
                "runnable": bool(item.get("runnable")),
                "requires_manual": bool(item.get("requires_manual")),
                "already_read": bool(item.get("already_read")),
                "related_symbols": list(item.get("related_symbols", []))[:5] if isinstance(item.get("related_symbols"), list) else [],
                "done_when": item.get("done_when"),
            }
        )
    return {
        "available": bool(rows),
        "summary": attention.get("summary") or "暂无关注队列。",
        "items": rows[:6],
        "write_policy": attention.get("write_policy") or "队列只整理关注顺序；写入类命令需人工确认。",
    }


def dashboard_coverage_action_items(coverage: Dict[str, object]) -> List[Dict[str, object]]:
    if not coverage.get("available"):
        return []
    gaps = coverage.get("top_gaps", []) if isinstance(coverage.get("top_gaps"), list) else []
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
    if not gaps and not actions:
        return []
    command = dashboard_coverage_plan_command(str(coverage.get("pool") or DEFAULT_POOL), "runtime", actions)
    done_when = dashboard_coverage_plan_done_when(actions)
    return [
        {
            "rank": 1,
            "item_type": "coverage_review",
            "title": "先确认覆盖底座",
            "reason": coverage.get("summary") or "确认复盘池、A 股基础清单、字段完整度和覆盖缺口。",
            "json_command": command,
            "runnable": digest_command_is_read_only(command),
            "requires_manual": False,
            "already_read": False,
            "related_symbols": [],
            "done_when": done_when,
        }
    ]


def dashboard_handoff(digest: Dict[str, object]) -> Dict[str, object]:
    handoff = digest.get("review_handoff", {}) if isinstance(digest.get("review_handoff"), dict) else {}
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    next_read = list(handoff.get("next_read", []))[:4] if isinstance(handoff.get("next_read"), list) else []
    manual_items = compact_dashboard_manual_items(handoff.get("manual_items", []), next_read)
    record_templates = list(handoff.get("record_templates", []))[:3] if isinstance(handoff.get("record_templates"), list) else []
    completion_summary = {
        "completion_state": completion.get("completion_state"),
        "ready_for_journal_note": bool(completion.get("ready_for_journal_note")),
        "blocking_count": completion.get("blocking_count", 0),
        "manual_required_count": completion.get("manual_required_count", 0),
        "pending_count": completion.get("pending_count", 0),
    }
    completion_checklist = dashboard_completion_checklist(completion, next_read, manual_items)
    return {
        "available": bool(handoff.get("available")),
        "summary": handoff.get("summary") or completion.get("summary") or "暂无交接信息。",
        "handoff_state": handoff.get("handoff_state"),
        "resume_prompt": handoff.get("resume_prompt"),
        "next_read": next_read,
        "manual_items": manual_items,
        "record_templates": record_templates,
        "completion": completion_summary,
        "completion_checklist": completion_checklist,
        "journal_gate": dashboard_journal_gate(completion_summary, next_read, manual_items, record_templates),
    }


def dashboard_completion_checklist(
    completion: Dict[str, object],
    next_read: Optional[List[Dict[str, object]]] = None,
    manual_items: Optional[List[Dict[str, object]]] = None,
) -> List[Dict[str, object]]:
    checks = completion.get("checks", []) if isinstance(completion.get("checks"), list) else []
    ranked = [
        item
        for _, item in sorted(
            [(index, item) for index, item in enumerate(checks) if isinstance(item, dict)],
            key=lambda row: (
                dashboard_completion_status_rank(str(row[1].get("status") or "")),
                row[0],
            ),
        )
    ]
    rows = []
    for index, item in enumerate(ranked[:3], start=1):
        rows.append(
            dashboard_completion_checklist_item(
                index,
                item.get("check_id"),
                item.get("title"),
                item.get("status"),
                item.get("reason"),
                item.get("json_command"),
                item.get("done_when"),
            )
        )
    if rows:
        return rows
    for item in next_read or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            dashboard_completion_checklist_item(
                len(rows) + 1,
                item.get("source"),
                item.get("title"),
                "pending",
                item.get("reason"),
                item.get("json_command"),
                item.get("done_when"),
            )
        )
        if len(rows) >= 3:
            return rows
    for item in manual_items or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            dashboard_completion_checklist_item(
                len(rows) + 1,
                item.get("source"),
                item.get("title"),
                "manual_required",
                item.get("reason"),
                item.get("json_command"),
                item.get("done_when"),
            )
        )
        if len(rows) >= 3:
            return rows
    return rows


def dashboard_completion_checklist_item(
    rank: int,
    check_id: object,
    title: object,
    status: object,
    reason: object,
    command: object,
    done_when: object,
) -> Dict[str, object]:
    command_text = str(command or "")
    status_text = str(status or "")
    return {
        "rank": rank,
        "check_id": check_id,
        "title": title,
        "status": status_text,
        "reason": reason,
        "json_command": command_text,
        "done_when": done_when,
        "runnable": bool(command_text)
        and status_text in {"blocked", "pending"}
        and digest_command_is_read_only(command_text),
    }


def dashboard_completion_status_rank(status: str) -> int:
    return {
        "blocked": 0,
        "pending": 1,
        "manual_required": 2,
        "done": 3,
    }.get(status, 4)


def dashboard_journal_gate(
    completion: Dict[str, object],
    next_read: List[Dict[str, object]],
    manual_items: List[Dict[str, object]],
    record_templates: List[Dict[str, object]],
) -> Dict[str, object]:
    pending_count = safe_int(completion.get("pending_count"))
    blocking_count = safe_int(completion.get("blocking_count"))
    manual_count = safe_int(completion.get("manual_required_count"))
    review_read_complete = bool(completion.get("ready_for_journal_note")) and not pending_count and not blocking_count
    ready = review_read_complete and not manual_count
    first_read = next((item for item in next_read if isinstance(item, dict) and item.get("json_command")), {})
    first_manual = next((item for item in manual_items if isinstance(item, dict) and item.get("json_command")), {})
    first_record = next((item for item in record_templates if isinstance(item, dict) and item.get("prefilled_note_command")), {})
    blockers: List[str] = []
    if blocking_count:
        blockers.append("还有 %s 个阻塞项，先处理数据或证据错误。" % blocking_count)
    if pending_count:
        blockers.append("还有 %s 个待读项，先运行下一条只读命令。" % pending_count)
    if manual_count:
        blockers.append("还有 %s 个人工确认项，留档前需要确认。" % manual_count)
    if ready:
        state = "ready"
        next_step = "可人工确认后保存日报并写入 journal note。"
        command = str(first_record.get("run_after") or first_manual.get("json_command") or "market-intel journal save --runtime --json")
    elif blocking_count:
        state = "blocked"
        next_step = blockers[0]
        command = str(first_read.get("json_command") or first_manual.get("json_command") or "")
    elif pending_count:
        state = "needs_read"
        next_step = blockers[0]
        command = str(first_read.get("json_command") or "")
    else:
        state = "needs_manual"
        next_step = blockers[-1] if blockers else "人工确认后保存日报并写入 journal note。"
        command = str(first_manual.get("json_command") or first_record.get("run_after") or "market-intel journal save --runtime --json")
    return {
        "state": state,
        "ready_for_journal_note": ready,
        "next_step": next_step,
        "json_command": command,
        "blockers": blockers[:4],
        "record_template_count": len(record_templates),
    }


def compact_dashboard_manual_items(value: object, next_read: List[Dict[str, object]]) -> List[Dict[str, object]]:
    next_read_commands = {
        digest_json_variant(str(item.get("json_command") or ""))
        for item in next_read
        if isinstance(item, dict) and item.get("json_command")
    }
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        if command and digest_json_variant(command) in next_read_commands:
            continue
        rows.append(item)
        if len(rows) >= 4:
            break
    return rows


def dashboard_today_focus(
    action_lane: Dict[str, object],
    plan: Dict[str, object],
    handoff: Dict[str, object],
) -> Dict[str, object]:
    focus_chain = dashboard_focus_chain(action_lane, plan, handoff)
    item = first_dashboard_focus_item(plan.get("items", []), prefer_read=True)
    if not item:
        item = first_dashboard_focus_item(action_lane.get("items", []), prefer_read=True)
    if not item:
        item = first_dashboard_focus_item(handoff.get("next_read", []), prefer_read=False)
    if not item:
        item = first_dashboard_focus_item(handoff.get("manual_items", []), prefer_read=False)
    if not item:
        return {
            "available": False,
            "summary": "暂无今日焦点。",
            "source": "",
            "title": "",
            "reason": "",
            "json_command": "",
            "done_when": "",
            "runnable": False,
            "requires_manual": False,
            "related_symbols": [],
            "focus_chain": focus_chain,
        }

    command = str(item.get("json_command") or "")
    source = str(item.get("item_type") or item.get("source") or "review_plan")
    requires_manual = bool(item.get("requires_manual")) or str(item.get("step_type") or "") == "manual"
    runnable = bool(command) and not requires_manual and digest_command_is_read_only(command)
    title = str(item.get("title") or source)
    reason = str(item.get("reason") or "按复盘队列优先级先处理。")
    done_when = str(item.get("done_when") or "已完成该焦点项并记录下一步。")
    return {
        "available": True,
        "summary": "今日先做：%s；完成后进入复盘计划下一项。" % title,
        "source": source,
        "title": title,
        "reason": reason,
        "json_command": command,
        "done_when": done_when,
        "runnable": runnable,
        "requires_manual": requires_manual,
        "related_symbols": dedupe_queue_texts(
            item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        )[:5],
        "focus_chain": focus_chain,
    }


def dashboard_action_summary(today_focus: Dict[str, object], handoff: Dict[str, object]) -> Dict[str, object]:
    gate = handoff.get("journal_gate", {}) if isinstance(handoff.get("journal_gate"), dict) else {}
    chain = today_focus.get("focus_chain", []) if isinstance(today_focus.get("focus_chain"), list) else []
    record_templates = handoff.get("record_templates", []) if isinstance(handoff.get("record_templates"), list) else []
    checklist = handoff.get("completion_checklist", []) if isinstance(handoff.get("completion_checklist"), list) else []
    first_record = dashboard_action_record_template(today_focus, record_templates)
    title = str(today_focus.get("title") or "暂无焦点")
    command = str(today_focus.get("json_command") or gate.get("json_command") or "")
    journal_state = str(gate.get("state") or "unknown")
    next_step = str(gate.get("next_step") or "")
    command_queue = dashboard_action_command_queue(today_focus, checklist, chain)
    return {
        "available": bool(today_focus.get("available") or command),
        "headline": "先看：%s" % title if title else "暂无今日焦点。",
        "why": str(today_focus.get("reason") or next_step or "按复盘队列继续。"),
        "next_command": command,
        "done_when": str(today_focus.get("done_when") or ""),
        "journal_state": journal_state,
        "journal_ready": bool(gate.get("ready_for_journal_note")),
        "journal_next_step": next_step,
        "command_queue": command_queue,
        "completion_checklist": [
            {
                "rank": item.get("rank"),
                "check_id": item.get("check_id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "reason": item.get("reason"),
                "json_command": item.get("json_command"),
                "done_when": item.get("done_when"),
                "runnable": bool(item.get("runnable")),
            }
            for item in checklist[:3]
            if isinstance(item, dict)
        ],
        "record_template": {
            "available": bool(first_record),
            "runnable": bool(first_record) and bool(gate.get("ready_for_journal_note")),
            "blocked_reason": "" if gate.get("ready_for_journal_note") else next_step,
            "prerequisite_command": "" if gate.get("ready_for_journal_note") else str(gate.get("json_command") or command),
            "prerequisite_done_when": "" if gate.get("ready_for_journal_note") else str(today_focus.get("done_when") or next_step),
            "section": first_record.get("section"),
            "title": first_record.get("title"),
            "prefilled_note_command": first_record.get("prefilled_note_command"),
            "run_after": first_record.get("run_after"),
        },
        "blockers": list(gate.get("blockers", []))[:3] if isinstance(gate.get("blockers"), list) else [],
        "next_chain": [
            {
                "rank": item.get("rank"),
                "title": item.get("title"),
                "json_command": item.get("json_command"),
                "done_when": item.get("done_when"),
            }
            for item in chain[:3]
            if isinstance(item, dict)
        ],
        "source": str(today_focus.get("source") or ""),
    }


def dashboard_action_command_queue(
    today_focus: Dict[str, object],
    checklist: List[object],
    chain: List[object],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen = set()

    def add_item(
        source: object,
        title: object,
        status: object,
        command: object,
        done_when: object,
        runnable: object,
    ) -> None:
        command_text = str(command or "")
        if not command_text or command_text in seen:
            return
        seen.add(command_text)
        rows.append(
            {
                "rank": len(rows) + 1,
                "source": str(source or ""),
                "title": str(title or source or "继续复盘"),
                "status": str(status or ""),
                "step_type": "read" if runnable else "manual",
                "json_command": command_text,
                "runnable": bool(runnable),
                "done_when": str(done_when or ""),
            }
        )

    add_item(
        today_focus.get("source"),
        today_focus.get("title"),
        "focus",
        today_focus.get("json_command"),
        today_focus.get("done_when"),
        today_focus.get("runnable"),
    )
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if not item.get("runnable"):
            continue
        add_item(
            item.get("check_id"),
            item.get("title"),
            item.get("status"),
            item.get("json_command"),
            item.get("done_when"),
            item.get("runnable"),
        )
        if len(rows) >= 5:
            return rows
    for item in chain:
        if not isinstance(item, dict):
            continue
        add_item(
            item.get("source"),
            item.get("title"),
            "next",
            item.get("json_command"),
            item.get("done_when"),
            item.get("runnable"),
        )
        if len(rows) >= 5:
            return rows
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if item.get("runnable"):
            continue
        add_item(
            item.get("check_id"),
            item.get("title"),
            item.get("status"),
            item.get("json_command"),
            item.get("done_when"),
            item.get("runnable"),
        )
        if len(rows) >= 5:
            return rows
    return rows


def dashboard_action_record_template(today_focus: Dict[str, object], record_templates: List[object]) -> Dict[str, object]:
    records = [item for item in record_templates if isinstance(item, dict) and item.get("prefilled_note_command")]
    if not records:
        return {}
    preferred = dashboard_record_sections_for_source(str(today_focus.get("source") or ""))
    if preferred:
        for section in preferred:
            match = next((item for item in records if str(item.get("section") or "") == section), None)
            if match:
                return match
    return records[0]


def dashboard_record_sections_for_source(source: str) -> List[str]:
    if source in {"market_scan", "market_structure"}:
        return ["market_structure"]
    if source in {"candidate_queue", "holding_review", "security_review"}:
        return ["security_review"]
    if source in {"portfolio_pressure", "portfolio_exposure"}:
        return ["portfolio_exposure"]
    if source in {"coverage_review", "runtime_setup", "data_quality"}:
        return ["data_quality"]
    if source in {"current_change", "current_vs_latest"}:
        return ["current_change"]
    return []


def dashboard_focus_chain(
    action_lane: Dict[str, object],
    plan: Dict[str, object],
    handoff: Dict[str, object],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen = set()
    for collection in [plan.get("items", []), action_lane.get("items", []), handoff.get("next_read", [])]:
        for item in collection if isinstance(collection, list) else []:
            if not isinstance(item, dict):
                continue
            row = dashboard_focus_chain_item(item)
            if not row:
                continue
            key = row.get("json_command") or "%s:%s" % (row.get("source"), row.get("title"))
            if key in seen:
                continue
            seen.add(key)
            row["rank"] = len(rows) + 1
            rows.append(row)
            if len(rows) >= 3:
                return rows
    return rows


def dashboard_focus_chain_item(item: Dict[str, object]) -> Dict[str, object]:
    command = str(item.get("json_command") or "")
    requires_manual = bool(item.get("requires_manual")) or str(item.get("step_type") or "") == "manual"
    if not command or requires_manual or not digest_command_is_read_only(command):
        return {}
    source = str(item.get("item_type") or item.get("source") or "review_plan")
    return {
        "rank": 0,
        "source": source,
        "title": str(item.get("title") or source),
        "json_command": command,
        "done_when": str(item.get("done_when") or ""),
        "runnable": True,
        "related_symbols": dedupe_queue_texts(
            item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        )[:5],
    }


def first_dashboard_focus_item(value: object, prefer_read: bool) -> Dict[str, object]:
    items = value if isinstance(value, list) else []
    fallback = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        if not fallback and (command or item.get("title")):
            fallback = item
        requires_manual = bool(item.get("requires_manual")) or str(item.get("step_type") or "") == "manual"
        if prefer_read and (requires_manual or not command or not digest_command_is_read_only(command)):
            continue
        if command or item.get("title"):
            return item
    return fallback


def dashboard_review_plan(pool: str, digest: Dict[str, object]) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    coverage = dashboard_coverage_context(digest)
    leading_coverage = dashboard_coverage_needs_frontload(coverage)
    if leading_coverage:
        add_dashboard_plan_coverage(items, coverage, pool, "runtime")
    add_dashboard_plan_market(items, digest)
    add_dashboard_plan_candidate_queue(items, dashboard_market_pulse(digest), pool, "runtime")
    add_dashboard_plan_portfolio(items, digest)
    if not leading_coverage:
        add_dashboard_plan_coverage(items, coverage, pool, "runtime")
    add_dashboard_plan_evidence(items, digest)
    add_dashboard_plan_attention(items, digest)
    add_dashboard_plan_handoff(items, digest)
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    return {
        "available": bool(items),
        "summary": dashboard_review_plan_summary(items),
        "items": items[:10],
        "write_policy": "review_plan 只安排复盘顺序；写入、导入和研究结论仍需人工确认。",
    }


FRONTLOAD_COVERAGE_GAPS = {
    "all_a_seed_only",
    "a_share_industry_missing",
    "a_share_theme_sources_missing",
    "cn_a_coverage_thin",
    "holding_coverage_gap",
}


def dashboard_coverage_needs_frontload(coverage: Dict[str, object]) -> bool:
    if not coverage.get("available"):
        return False
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    if universe and not universe.get("available"):
        return True
    gaps = coverage.get("top_gaps", []) if isinstance(coverage.get("top_gaps"), list) else []
    gap_ids = {str(item.get("id") or "") for item in gaps if isinstance(item, dict)}
    return bool(gap_ids & FRONTLOAD_COVERAGE_GAPS)


def add_dashboard_plan_coverage(
    items: List[Dict[str, object]],
    coverage: Dict[str, object],
    pool: str,
    mode: str,
) -> None:
    if not coverage.get("available"):
        return
    gaps = coverage.get("top_gaps", []) if isinstance(coverage.get("top_gaps"), list) else []
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
    if not gaps and not actions:
        return
    command = dashboard_coverage_plan_command(pool, mode, actions)
    done_when = dashboard_coverage_plan_done_when(actions)
    items.append(
        dashboard_plan_item(
            "coverage_review",
            "先确认覆盖底座",
            coverage.get("summary") or "确认复盘池、A 股基础清单、字段完整度和覆盖缺口。",
            command,
            "read",
            done_when,
            evidence=dashboard_coverage_plan_evidence(coverage),
        )
    )


def dashboard_coverage_plan_done_when(actions: List[object]) -> str:
    for action in actions:
        if isinstance(action, dict) and action.get("done_when"):
            return str(action.get("done_when"))
    return "已确认 all-a 覆盖边界、A 股基础清单字段完整度、覆盖缺口和下一步补数动作。"


def dashboard_coverage_plan_command(pool: str, mode: str, actions: List[object]) -> str:
    for action in actions:
        if not isinstance(action, dict):
            continue
        command = str(action.get("command") or "")
        if "pool quality" not in command:
            continue
        return with_pool_arg(digest_json_variant(command), pool)
    for action in actions:
        if not isinstance(action, dict):
            continue
        command = str(action.get("command") or "")
        if "pool coverage" not in command:
            continue
        command = digest_json_variant(command)
        if mode == "mock":
            command = command.replace(" --runtime", "").replace(" --text", " --json")
            if " --mock" not in command:
                command = command.replace("pool coverage", "pool coverage --mock")
        elif " --runtime" not in command:
            command = command.replace("pool coverage", "pool coverage --runtime")
        return with_pool_arg(command, pool)
    if mode == "mock":
        return with_pool_arg("market-intel pool coverage --mock --json", pool)
    return with_pool_arg("market-intel pool coverage --runtime --json", pool)


def dashboard_coverage_plan_evidence(coverage: Dict[str, object]) -> List[object]:
    rows = []
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    quality_queue = coverage.get("top_data_quality_queue", []) if isinstance(coverage.get("top_data_quality_queue"), list) else []
    if universe:
        rows.append(
            "全 A %s | 记录 %s | 行业/概念/指数 %.0f%%/%.0f%%/%.0f%%"
            % (
                "已接入" if universe.get("available") else "未接入",
                universe.get("record_count", 0),
                float(profile.get("industry_coverage_ratio") or 0) * 100,
                float(profile.get("concept_coverage_ratio") or 0) * 100,
                float(profile.get("index_coverage_ratio") or 0) * 100,
            )
        )
    if quality_queue and isinstance(quality_queue[0], dict):
        rows.append(
            "数据质量 #%s %s | %s | 影响 %s"
            % (
                quality_queue[0].get("rank"),
                quality_queue[0].get("flag"),
                quality_queue[0].get("severity"),
                quality_queue[0].get("affected_count", 0),
            )
        )
    for gap in coverage.get("top_gaps", []) if isinstance(coverage.get("top_gaps"), list) else []:
        if isinstance(gap, dict):
            rows.append("%s | %s" % (gap.get("severity"), gap.get("id")))
    for action in coverage.get("next_actions", [])[:2] if isinstance(coverage.get("next_actions"), list) else []:
        if isinstance(action, dict):
            rows.append("下一步 %s" % action.get("id"))
    return rows[:5]


def add_dashboard_plan_market(items: List[Dict[str, object]], digest: Dict[str, object]) -> None:
    scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    if not scan.get("available"):
        return
    groups = scan.get("top_groups", []) if isinstance(scan.get("top_groups"), list) else []
    candidates = scan.get("top_candidates", []) if isinstance(scan.get("top_candidates"), list) else []
    if groups or candidates:
        items.append(
            dashboard_plan_item(
                "market_scan",
                "先读全市场强弱",
                scan.get("summary") or "确认全市场板块和候选复盘标的。",
                "market-intel scan --runtime --json",
                "read",
                "已记录最强板块、候选标的和覆盖状态。",
                related_symbols=[item.get("symbol") for item in candidates[:5] if isinstance(item, dict)],
                evidence=dashboard_market_plan_evidence(groups, candidates),
            )
        )


def add_dashboard_plan_candidate_queue(
    items: List[Dict[str, object]],
    market: Dict[str, object],
    pool: str,
    mode: str,
) -> None:
    queue_item = dashboard_candidate_queue_next_item(market)
    if not queue_item:
        return
    command = dashboard_candidate_queue_command(queue_item, pool, mode)
    items.append(
        dashboard_plan_item(
            "candidate_queue",
            "%s %s" % (queue_item.get("symbol"), queue_item.get("name") or ""),
            queue_item.get("reason") or "读取候选队列首项。",
            command,
            "read",
            "已确认该候选的板块共振、排序因子、覆盖状态和下一步核对项。",
            related_symbols=[queue_item.get("symbol")],
            evidence=[
                "队列 %s | 分 %s | 覆盖 %s"
                % (queue_item.get("lane") or "-", queue_item.get("review_score"), queue_item.get("coverage_state"))
            ],
        )
    )


def dashboard_candidate_queue_next_item(market: Dict[str, object]) -> Dict[str, object]:
    queue = market.get("candidate_queue", {}) if isinstance(market.get("candidate_queue"), dict) else {}
    buckets = queue.get("buckets", {}) if isinstance(queue.get("buckets"), dict) else {}
    for key in ["review_now", "data_first", "deprioritized"]:
        bucket = buckets.get(key, {}) if isinstance(buckets.get(key), dict) else {}
        items = bucket.get("items", []) if isinstance(bucket.get("items"), list) else []
        for item in items:
            if isinstance(item, dict) and item.get("symbol"):
                return item
    return {}


def dashboard_candidate_queue_command(item: Dict[str, object], pool: str, mode: str) -> str:
    command = str(item.get("next_command") or "")
    if not command and item.get("symbol"):
        command = "market-intel pool explain %s --text" % item.get("symbol")
    if not command:
        return with_pool_arg("market-intel scan --json", pool)
    command = digest_json_variant(command)
    if mode == "runtime" and " --runtime" not in command and "pool explain" in command:
        command = command.replace(" --json", " --runtime --json")
    if mode == "mock":
        command = command.replace(" --runtime", "")
    return with_pool_arg(command, pool)


def dashboard_market_plan_evidence(groups: object, candidates: object) -> List[object]:
    rows = []
    for group in groups[:3] if isinstance(groups, list) else []:
        if isinstance(group, dict):
            rows.append("%s%s | 分 %s" % (dashboard_group_type_label(group.get("group_type")), group.get("name"), group.get("score")))
    for item in candidates[:3] if isinstance(candidates, list) else []:
        if isinstance(item, dict):
            rows.append("%s %s | 覆盖 %s" % (item.get("symbol"), item.get("name"), item.get("coverage_state")))
    return rows[:5]


def dashboard_group_type_label(value: object) -> str:
    labels = {
        "industry": "行业",
        "concept": "概念",
        "index": "指数",
        "chain": "链路",
        "unknown": "分组",
    }
    return labels.get(str(value), str(value or "分组"))


def add_dashboard_plan_portfolio(items: List[Dict[str, object]], digest: Dict[str, object]) -> None:
    portfolio = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = portfolio.get("top_holdings", []) if isinstance(portfolio.get("top_holdings"), list) else []
    for holding in holdings[:2]:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        items.append(
            dashboard_plan_item(
                "holding_review",
                "%s %s" % (holding.get("symbol"), holding.get("name") or ""),
                holding.get("primary_question") or "读取该持仓的行情、热点、风险和组合暴露。",
                holding.get("primary_json_command") or holding.get("primary_command"),
                "read",
                "已确认该持仓的行情、热点、风险、覆盖状态和还需补的证据。",
                related_symbols=[holding.get("symbol")],
                evidence=attention_holding_evidence(holding),
            )
        )


def add_dashboard_plan_evidence(items: List[Dict[str, object]], digest: Dict[str, object]) -> None:
    evidence = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    for item in evidence.get("items", []) if isinstance(evidence.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("coverage_status") == "covered":
            continue
        if item.get("item_type") == "holding_review":
            continue
        items.append(
            dashboard_plan_item(
                str(item.get("item_type") or "evidence"),
                item.get("title") or "证据缺口",
                item.get("question") or "补齐该项复盘证据。",
                item.get("json_command"),
                "read" if digest_command_is_read_only(str(item.get("json_command") or "")) else "manual",
                item.get("done_when") or "已补齐证据或记录无法补齐的原因。",
                related_symbols=item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else [],
                evidence=item.get("missing_evidence", []) if isinstance(item.get("missing_evidence"), list) else [],
            )
        )
        if len(items) >= 7:
            return


def add_dashboard_plan_attention(items: List[Dict[str, object]], digest: Dict[str, object]) -> None:
    attention = digest.get("attention_queue", {}) if isinstance(digest.get("attention_queue"), dict) else {}
    seen = {str(item.get("json_command") or "") for item in items if isinstance(item, dict)}
    for item in attention.get("items", []) if isinstance(attention.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        if not command or command in seen:
            continue
        items.append(
            dashboard_plan_item(
                str(item.get("item_type") or "attention"),
                item.get("title") or "关注项",
                item.get("reason") or "按关注队列继续复盘。",
                command,
                "manual" if item.get("requires_manual") else "read",
                item.get("done_when") or "已完成该关注项。",
                related_symbols=item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else [],
                evidence=item.get("evidence", []) if isinstance(item.get("evidence"), list) else [],
                already_read=bool(item.get("already_read")),
                requires_manual=bool(item.get("requires_manual")),
            )
        )
        seen.add(command)
        if len(items) >= 8:
            return


def add_dashboard_plan_handoff(items: List[Dict[str, object]], digest: Dict[str, object]) -> None:
    handoff = digest.get("review_handoff", {}) if isinstance(digest.get("review_handoff"), dict) else {}
    seen = {str(item.get("json_command") or "") for item in items if isinstance(item, dict)}
    for item in handoff.get("manual_items", []) if isinstance(handoff.get("manual_items"), list) else []:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        if command and command in seen:
            continue
        if command and digest_json_variant(command) in seen:
            continue
        items.append(
            dashboard_plan_item(
                str(item.get("source") or "manual"),
                item.get("title") or "人工确认",
                item.get("reason") or "人工确认后再执行。",
                command,
                "manual",
                item.get("done_when") or "人工确认完成。",
                requires_manual=True,
            )
        )
        if command:
            seen.add(command)
        if len(items) >= 9:
            break
    records = handoff.get("record_templates", []) if isinstance(handoff.get("record_templates"), list) else []
    if records:
        record = records[0] if isinstance(records[0], dict) else {}
        items.append(
            dashboard_plan_item(
                "journal_record",
                "最后留档",
                "人工确认复盘结论后保存日报并记录笔记。",
                record.get("prefilled_note_command") or "market-intel journal save --runtime --json",
                "manual",
                "日报和复盘笔记已写入 journal。",
                requires_manual=True,
            )
        )


def dashboard_plan_item(
    item_type: str,
    title: object,
    reason: object,
    command: object,
    step_type: str,
    done_when: object,
    related_symbols: Optional[List[object]] = None,
    evidence: Optional[List[object]] = None,
    already_read: bool = False,
    requires_manual: bool = False,
) -> Dict[str, object]:
    command_text = str(command or "")
    json_command = digest_json_variant(command_text) if command_text and step_type == "read" else command_text
    return {
        "item_type": item_type,
        "step_type": step_type,
        "title": str(title or item_type),
        "reason": str(reason or ""),
        "json_command": json_command,
        "runnable": bool(json_command) and step_type == "read" and digest_command_is_read_only(json_command),
        "requires_manual": bool(requires_manual or step_type == "manual"),
        "already_read": already_read,
        "related_symbols": dedupe_queue_texts(related_symbols or [])[:6],
        "evidence": dedupe_queue_texts(evidence or [])[:5],
        "done_when": str(done_when or ""),
    }


def dashboard_review_plan_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return "暂无可执行复盘计划。"
    read_count = sum(1 for item in items if item.get("step_type") == "read")
    manual_count = sum(1 for item in items if item.get("requires_manual"))
    unread_count = sum(1 for item in items if item.get("step_type") == "read" and not item.get("already_read"))
    return "复盘步骤 %s 个：只读 %s 个，其中待读 %s 个；人工确认 %s 个。" % (
        len(items),
        read_count,
        unread_count,
        manual_count,
    )


def dashboard_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 表示 dashboard 已生成；data.state 表示复盘是否仍需读证据或人工确认。",
        "stable_fields": [
            "data.state",
            "data.summary",
            "data.tiles",
            "data.action_summary",
            "data.action_summary.headline",
            "data.action_summary.next_command",
            "data.action_summary.journal_state",
            "data.action_summary.command_queue",
            "data.action_summary.command_queue[].json_command",
            "data.action_summary.command_queue[].done_when",
            "data.action_summary.command_queue[].runnable",
            "data.action_summary.completion_checklist",
            "data.action_summary.completion_checklist[].status",
            "data.action_summary.completion_checklist[].json_command",
            "data.action_summary.completion_checklist[].done_when",
            "data.action_summary.record_template",
            "data.action_summary.record_template.runnable",
            "data.action_summary.record_template.prerequisite_command",
            "data.action_summary.record_template.prerequisite_done_when",
            "data.action_summary.record_template.prefilled_note_command",
            "data.action_summary.next_chain",
            "data.action_summary.next_chain[].json_command",
            "data.today_focus",
            "data.today_focus.title",
            "data.today_focus.reason",
            "data.today_focus.json_command",
            "data.today_focus.done_when",
            "data.today_focus.runnable",
            "data.today_focus.focus_chain",
            "data.today_focus.focus_chain[].source",
            "data.today_focus.focus_chain[].json_command",
            "data.today_focus.focus_chain[].done_when",
            "data.positioning",
            "data.positioning.differentiators",
            "data.positioning.differentiators[].agent_path",
            "data.positioning.differentiators[].done_when",
            "data.positioning.selection_rule",
            "data.coverage_context",
            "data.coverage_context.universe",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.universe.sector_profile.top_industries",
            "data.coverage_context.universe.sector_profile.top_concepts",
            "data.coverage_context.universe.sector_profile.top_indexes",
            "data.coverage_context.universe.enrichment_queue",
            "data.coverage_context.holdings_coverage",
            "data.coverage_context.holdings_coverage.summary",
            "data.coverage_context.holdings_coverage.top_review_queue",
            "data.coverage_context.holdings_coverage.top_unmatched",
            "data.coverage_context.top_gaps",
            "data.coverage_context.top_data_quality_queue",
            "data.coverage_context.next_actions",
            "data.coverage_context.next_actions[].rank",
            "data.market_pulse",
            "data.market_pulse.market_breadth",
            "data.market_pulse.top_groups",
            "data.market_pulse.candidates",
            "data.market_pulse.candidate_queue",
            "data.market_pulse.candidates[].ranking_breakdown",
            "data.market_pulse.candidates[].universe_context",
            "data.portfolio_pulse",
            "data.portfolio_pulse.top_holdings",
            "data.portfolio_pulse.top_holdings[].primary_question",
            "data.portfolio_pulse.top_holdings[].risk_flags",
            "data.portfolio_pulse.top_holdings[].primary_json_command",
            "data.portfolio_pulse.pressure_groups",
            "data.portfolio_pulse.pressure_groups[].group_type",
            "data.portfolio_pulse.pressure_groups[].group",
            "data.portfolio_pulse.pressure_groups[].holding_count",
            "data.evidence_gaps",
            "data.evidence_gaps.items",
            "data.evidence_gaps.items[].missing_evidence",
            "data.evidence_gaps.items[].done_when",
            "data.evidence_gaps.items[].json_command",
            "data.action_lane",
            "data.action_lane.items",
            "data.review_plan",
            "data.review_plan.items",
            "data.review_plan.items[].json_command",
            "data.review_plan.items[].done_when",
            "data.handoff",
            "data.handoff.journal_gate",
            "data.handoff.journal_gate.state",
            "data.handoff.completion_checklist",
            "data.handoff.completion_checklist[].status",
            "data.handoff.completion_checklist[].json_command",
            "data.handoff.completion_checklist[].done_when",
            "data.handoff.journal_gate.json_command",
            "data.handoff.journal_gate.blockers",
            "data.handoff.next_read",
            "data.guardrails",
        ],
        "boundary": "dashboard 是只读复盘工作台；不自动写 journal，不生成交易指令。",
    }


def filter_agent_next_cards_for_symbol(cards: Dict[str, object], symbol: str) -> Dict[str, object]:
    wanted = str(symbol)
    rows = [
        item
        for item in cards.get("cards", [])
        if isinstance(item, dict) and str(item.get("symbol") or "") == wanted
    ] if isinstance(cards.get("cards"), list) else []
    return {
        "available": bool(rows),
        "summary": "单票复核卡片 %s 张，聚焦 %s。" % (len(rows), wanted) if rows else "未找到 %s 的单票复核卡片。" % wanted,
        "cards": rows,
        "write_policy": cards.get("write_policy") or "只整理单票复核上下文，不生成交易指令。",
    }


def agent_next_primary_card_command(cards: Dict[str, object]) -> str:
    rows = cards.get("cards", []) if isinstance(cards.get("cards"), list) else []
    first = rows[0] if rows and isinstance(rows[0], dict) else {}
    return str(first.get("next_json_command") or "")


def filter_agent_next_handoff_for_symbol(
    handoff: Dict[str, object],
    symbol: str,
    fallback_command: str = "",
) -> Dict[str, object]:
    wanted = str(symbol)
    command_signature = "portfolio.explain:%s" % wanted
    next_read = filter_handoff_symbol_commands(handoff.get("next_read", []), command_signature)
    chain = filter_handoff_symbol_commands(
        handoff.get("command_chain", []),
        command_signature,
        include_sources={"foundation_research"},
    )
    if not next_read:
        default_command = fallback_command or "market-intel portfolio explain %s --runtime --json" % wanted
        next_read = [
            review_handoff_command_item(
                1,
                "security_card",
                "单票复核",
                "聚焦该标的的行情、热点、风险、暴露和待补证据。",
                default_command,
                "已读取该标的单票复核。",
            )
        ]
    if not chain:
        chain = review_handoff_command_chain(next_read, [])
    watch_items = filter_handoff_watch_items_for_symbol(handoff.get("watch_items", []), wanted)
    rows = dict(handoff)
    rows["next_read"] = next_read
    rows["command_chain"] = chain
    rows["watch_items"] = watch_items
    rows["summary"] = "聚焦 %s：待读 %s 项，下次观察 %s 项。" % (wanted, len(next_read), len(watch_items))
    rows["resume_prompt"] = ensure_sentence(
        "接手复盘：聚焦 %s；先运行 %s" % (
            wanted,
            next_read[0].get("json_command") if next_read else "market-intel portfolio explain %s --runtime --json" % wanted,
        )
    )
    rows["handoff_state"] = "continue_reading" if next_read else handoff.get("handoff_state") or "needs_manual"
    return rows


def filter_handoff_watch_items_for_symbol(value: object, symbol: str) -> List[Dict[str, object]]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        symbols = item.get("symbols", []) if isinstance(item.get("symbols"), list) else []
        if symbol in [str(raw) for raw in symbols]:
            row = dict(item)
            row["rank"] = len(rows) + 1
            rows.append(row)
    return rows


def filter_handoff_symbol_commands(
    value: object,
    command_signature: str,
    include_sources: Optional[set] = None,
) -> List[Dict[str, object]]:
    rows = []
    included = include_sources or set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        if attention_command_signature(command) == command_signature or item.get("source") in included:
            row = dict(item)
            row["rank"] = len(rows) + 1
            rows.append(row)
    return rows


def build_agent_run_queue(briefing_data: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen: Dict[str, Dict[str, object]] = {}

    def add_queue(value: object, source: str) -> None:
        items = value if isinstance(value, list) else []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            command = str(raw.get("json_command") or raw.get("command") or "")
            if not command:
                continue
            key = command
            if key in seen:
                existing = seen[key]
                existing_sources = existing.get("queue_sources", []) if isinstance(existing.get("queue_sources"), list) else []
                existing_sources.append(source)
                existing["queue_sources"] = dedupe_queue_texts(existing_sources)
                related = existing.get("related_focus", []) if isinstance(existing.get("related_focus"), list) else []
                new_related = raw.get("related_focus", []) if isinstance(raw.get("related_focus"), list) else []
                existing["related_focus"] = dedupe_queue_texts(list(related) + [str(item) for item in new_related if item])[:4]
                return
            item = dict(raw)
            item["queue_sources"] = [source]
            item["run_rank"] = len(rows) + 1
            rows.append(item)
            seen[key] = item

    add_queue(briefing_data.get("command_queue", []), "briefing.command_queue")
    daily = briefing_data.get("daily", {}) if isinstance(briefing_data.get("daily"), dict) else {}
    add_queue(daily.get("command_queue", []), "daily.command_queue")
    return rows


def compact_agent_run_source(briefing_payload: Dict[str, object], queue: List[Dict[str, object]]) -> Dict[str, object]:
    command = next(
        (
            str(item.get("json_command") or item.get("command"))
            for item in queue
            if isinstance(item, dict) and "agent briefing" in str(item.get("json_command") or item.get("command") or "")
        ),
        "market-intel agent briefing --json",
    )
    return {
        "command": command,
        "ok": bool(briefing_payload.get("ok")),
        "payload_command": briefing_payload.get("command"),
        "summary": command_payload_summary(briefing_payload),
        "observations": command_payload_observations(briefing_payload)[:6],
    }


def compact_agent_run_queue(queue: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for item in queue[:20]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "run_rank": item.get("run_rank"),
                "command": item.get("command"),
                "json_command": item.get("json_command"),
                "runnable": bool(item.get("runnable", True)),
                "state_effect": item.get("state_effect"),
                "queue_sources": list(item.get("queue_sources", [])) if isinstance(item.get("queue_sources"), list) else [],
                "purpose": item.get("purpose") or item.get("reason"),
                "done_when": item.get("done_when"),
            }
        )
    return rows


def run_agent_read_command(
    command: str,
    default_pool: str,
    default_top: int,
    default_map_top: int,
    max_quote_age_days: int,
) -> Dict[str, Any]:
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return envelope(command="agent.command", errors=[error("COMMAND_PARSE_ERROR", str(exc), {"command": command})], ok=False)
    if tokens and tokens[0] == "market-intel":
        tokens = tokens[1:]
    if not tokens:
        return envelope(command="agent.command", errors=[error("COMMAND_EMPTY", "Command is empty.")], ok=False)
    pool = option_value(tokens, "--pool", default_pool)
    top = option_int(tokens, "--top", default_top)
    map_top = option_int(tokens, "--map-top", default_map_top)
    use_runtime = flag_present(tokens, "--runtime")
    use_mock = flag_present(tokens, "--mock")
    quotes_file = option_value(tokens, "--quotes-file")
    holdings_file = option_value(tokens, "--holdings-file")
    candidate_top = option_int(tokens, "--candidate-top", max(default_top * 2, 12))
    resource = tokens[0]
    sub = tokens[1] if len(tokens) > 1 else None

    if resource == "status" and sub == "runtime":
        return handle_status_runtime(pool, max_quote_age_days=max_quote_age_days)
    if resource == "validate" and sub == "runtime":
        return handle_validate_runtime(pool)
    if resource == "import" and sub == "schema":
        return handle_import_schema()
    if resource == "daily":
        return handle_daily(pool, use_mock=use_mock, top=top, map_top=map_top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "scan":
        return handle_scan(pool, use_mock=use_mock, top=max(top, 8), candidate_top=candidate_top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "brief":
        return handle_brief(pool, use_mock=use_mock, top=top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "watchlist":
        return handle_watchlist(pool, use_mock=use_mock, top=top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "map":
        return handle_map(pool, use_mock=use_mock, top=top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "hotspots":
        return handle_hotspots(pool, use_mock=use_mock, top=top, quotes_file=quotes_file, use_runtime=use_runtime)
    if resource == "holdings" and sub == "impact":
        return handle_holdings_impact(pool, use_mock=use_mock, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "portfolio" and sub == "review":
        return handle_portfolio_review(pool, use_mock=use_mock, top=top, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "portfolio" and sub == "explain":
        symbol = first_positional(tokens[2:])
        if not symbol:
            return envelope(command="portfolio.explain", errors=[error("COMMAND_SYMBOL_REQUIRED", "portfolio explain requires a symbol.")], ok=False)
        return handle_portfolio_explain(pool, symbol, use_mock=use_mock, quotes_file=quotes_file, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "pool" and sub == "coverage":
        return handle_pool_coverage(pool, use_mock=use_mock, holdings_file=holdings_file, use_runtime=use_runtime)
    if resource == "pool" and sub == "quality":
        flag = first_positional(tokens[2:])
        if not flag:
            return envelope(command="pool.quality", errors=[error("COMMAND_FLAG_REQUIRED", "pool quality requires a data quality flag.")], ok=False)
        return handle_pool_quality(
            pool,
            flag,
            limit=option_int(tokens, "--limit", 12),
            output=option_value(tokens, "--output"),
            dry_run=flag_present(tokens, "--dry-run"),
        )
    if resource == "pool" and sub == "explain":
        symbol = first_positional(tokens[2:])
        if not symbol:
            return envelope(command="pool.explain", errors=[error("COMMAND_SYMBOL_REQUIRED", "pool explain requires a symbol.")], ok=False)
        return handle_pool_explain(pool, symbol, use_runtime=use_runtime)
    if resource == "journal" and sub == "latest":
        return handle_journal_latest()
    if resource == "journal" and sub == "compare":
        return handle_journal_compare(option_value(tokens, "--base"), option_value(tokens, "--current"))
    if resource == "journal" and sub == "timeline":
        return handle_journal_timeline(option_int(tokens, "--limit", 5))
    return envelope(
        command="agent.command",
        errors=[error("COMMAND_UNSUPPORTED", "agent run does not know how to run this command.", {"command": command})],
        ok=False,
    )


def compact_agent_run_result(item: Dict[str, object], payload: Dict[str, object]) -> Dict[str, object]:
    return {
        "run_rank": item.get("run_rank"),
        "command": item.get("command"),
        "json_command": item.get("json_command"),
        "payload_command": payload.get("command"),
        "ok": bool(payload.get("ok")),
        "state_effect": item.get("state_effect"),
        "queue_sources": list(item.get("queue_sources", [])) if isinstance(item.get("queue_sources"), list) else [],
        "related_focus": list(item.get("related_focus", []))[:4] if isinstance(item.get("related_focus"), list) else [],
        "read_fields": list(item.get("read_fields", []))[:5] if isinstance(item.get("read_fields"), list) else [],
        "summary": command_payload_summary(payload),
        "observations": command_payload_observations(payload)[:8],
        "warnings": compact_payload_issues(payload.get("warnings", [])),
        "errors": compact_payload_issues(payload.get("errors", [])),
        "done_when": item.get("done_when"),
    }


def first_result_payload(results: List[Dict[str, object]], payload_command: str) -> Dict[str, object]:
    for result in results:
        if isinstance(result, dict) and result.get("payload_command") == payload_command:
            return result
    return {}


def agent_run_skip(item: Dict[str, object], reason: str) -> Dict[str, object]:
    return {
        "run_rank": item.get("run_rank"),
        "command": item.get("command"),
        "json_command": item.get("json_command"),
        "runnable": bool(item.get("runnable", True)),
        "state_effect": item.get("state_effect"),
        "queue_sources": list(item.get("queue_sources", [])) if isinstance(item.get("queue_sources"), list) else [],
        "reason": reason,
        "purpose": item.get("purpose") or item.get("reason"),
        "requires_prior_command": item.get("requires_prior_command"),
        "done_when": item.get("done_when"),
    }


def build_agent_run_manual_followups(skipped: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for item in skipped:
        if not isinstance(item, dict):
            continue
        state_effect = str(item.get("state_effect") or "")
        if state_effect == "read_only":
            continue
        rows.append(
            {
                "command": item.get("command"),
                "json_command": item.get("json_command"),
                "state_effect": state_effect,
                "reason": item.get("reason"),
                "requires_prior_command": item.get("requires_prior_command"),
                "done_when": item.get("done_when"),
            }
        )
    return rows[:8]


def build_agent_run_review_digest(
    briefing_data: Dict[str, object],
    results: List[Dict[str, object]],
    skipped: List[Dict[str, object]],
    manual_followups: List[Dict[str, object]],
    source_briefing: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    daily = briefing_data.get("daily", {}) if isinstance(briefing_data.get("daily"), dict) else {}
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    change_tracking = agent_run_digest_change_tracking(briefing_data)
    holding_dashboard = agent_run_digest_holding_dashboard(daily, change_tracking)
    portfolio_pressure = agent_run_digest_portfolio_pressure(daily, holding_dashboard)
    digest: Dict[str, object] = {
        "available": bool(daily.get("available")),
        "headline": agent_run_digest_headline(briefing_data),
        "run_status": {
            "read_count": len(results),
            "read_ok_count": sum(1 for item in results if isinstance(item, dict) and item.get("ok")),
            "skipped_count": len(skipped),
            "manual_followup_count": len(manual_followups),
        },
        "data_quality": agent_run_digest_data_quality(validation, results),
        "coverage_context": agent_run_digest_coverage_context(daily),
        "market_scan": agent_run_digest_market_scan(briefing_data, results),
        "market_structure": agent_run_digest_market_structure(daily),
        "portfolio_pressure": portfolio_pressure,
        "holding_dashboard": holding_dashboard,
        "securities_to_review": agent_run_digest_securities(daily),
        "risk_watch": agent_run_digest_risks(daily),
        "change_tracking": change_tracking,
        "security_workbench": agent_run_digest_security_workbench(daily, change_tracking, portfolio_pressure),
        "next_steps": agent_run_digest_next_steps(daily, results, manual_followups, change_tracking),
    }
    if not daily.get("available"):
        digest["headline"] = "runtime 暂不可生成复盘摘要，先处理数据阻塞。"
    digest["data_repair_plan"] = agent_run_digest_data_repair_plan(digest)
    if isinstance(digest.get("data_quality"), dict):
        digest["data_quality"]["repair_plan"] = digest["data_repair_plan"]  # type: ignore[index]
    digest["evidence_checklist"] = agent_run_digest_evidence_checklist(digest, results, manual_followups)
    digest["hypothesis_board"] = agent_run_digest_hypothesis_board(digest, manual_followups)
    digest["journal_draft"] = agent_run_digest_journal_draft(digest, manual_followups)
    digest["attention_queue"] = agent_run_digest_attention_queue(digest, manual_followups, results, source_briefing or {})
    digest["followup_watch"] = agent_run_digest_followup_watch(digest, manual_followups)
    digest["review_completion"] = agent_run_digest_review_completion(digest, manual_followups)
    digest["review_handoff"] = agent_run_digest_review_handoff(digest, manual_followups)
    digest["security_cards"] = agent_run_digest_security_cards(digest, manual_followups)
    return digest


def agent_run_digest_coverage_context(daily: Dict[str, object]) -> Dict[str, object]:
    coverage = daily.get("coverage_context", {}) if isinstance(daily.get("coverage_context"), dict) else {}
    if not coverage.get("available"):
        return {"available": False, "summary": "暂无复盘池覆盖上下文。"}
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    gaps = coverage.get("gaps", []) if isinstance(coverage.get("gaps"), list) else []
    data_quality_queue = coverage.get("data_quality_queue", []) if isinstance(coverage.get("data_quality_queue"), list) else []
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
    return {
        "available": True,
        "pool": coverage.get("pool"),
        "scope": coverage.get("scope"),
        "status": coverage.get("status"),
        "summary": coverage.get("summary"),
        "universe": {
            "available": bool(universe.get("available")),
            "record_count": universe.get("record_count", 0),
            "industry_count": universe.get("industry_count", 0),
            "concept_count": universe.get("concept_count", 0),
            "index_membership_count": universe.get("index_membership_count", 0),
            "enrichment_queue": compact_universe_enrichment_queue(universe.get("enrichment_queue", [])),
            "sector_profile": {
                "industry_coverage_ratio": profile.get("industry_coverage_ratio", 0),
                "concept_coverage_ratio": profile.get("concept_coverage_ratio", 0),
                "index_coverage_ratio": profile.get("index_coverage_ratio", 0),
                "top_industries": list(profile.get("top_industries", []))[:5] if isinstance(profile.get("top_industries"), list) else [],
                "top_concepts": list(profile.get("top_concepts", []))[:5] if isinstance(profile.get("top_concepts"), list) else [],
                "top_indexes": list(profile.get("top_indexes", []))[:5] if isinstance(profile.get("top_indexes"), list) else [],
                "missing_field_counts": profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {},
                "missing_field_samples": list(profile.get("missing_field_samples", []))[:5] if isinstance(profile.get("missing_field_samples"), list) else [],
                "coverage_flags": list(profile.get("coverage_flags", [])) if isinstance(profile.get("coverage_flags"), list) else [],
            },
        },
        "gap_count": len(gaps),
        "top_gaps": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in gaps[:5]
            if isinstance(item, dict)
        ],
        "top_data_quality_queue": compact_data_quality_queue(data_quality_queue),
        "next_actions": [
            {
                "rank": item.get("rank"),
                "id": item.get("id"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
            }
            for item in actions[:5]
            if isinstance(item, dict)
        ],
    }


def agent_run_digest_market_scan(briefing_data: Dict[str, object], results: List[Dict[str, object]]) -> Dict[str, object]:
    scan = briefing_data.get("market_scan", {}) if isinstance(briefing_data.get("market_scan"), dict) else {}
    result = first_result_payload(results, "scan")
    result_observations = result.get("observations", []) if isinstance(result.get("observations"), list) else []
    if not scan.get("available"):
        return {
            "available": False,
            "summary": scan.get("summary") or "暂无全市场扫描。",
            "read": bool(result),
            "observations": result_observations[:4],
        }
    groups = scan.get("sector_groups", []) if isinstance(scan.get("sector_groups"), list) else []
    candidates = scan.get("candidate_securities", []) if isinstance(scan.get("candidate_securities"), list) else []
    return {
        "available": True,
        "summary": scan.get("summary"),
        "scan_mode": scan.get("scan_mode"),
        "market_breadth": scan.get("market_breadth", {}),
        "quote_count": scan.get("quote_count", 0),
        "matched_quote_count": scan.get("matched_quote_count", 0),
        "candidate_queue": compact_dashboard_candidate_queue(scan.get("candidate_queue", {})),
        "top_groups": [
            {
                "rank": item.get("rank"),
                "group_type": item.get("group_type"),
                "name": item.get("name"),
                "score": item.get("score"),
                "active_member_count": item.get("active_member_count"),
                "member_count": item.get("member_count"),
                "leaders": list(item.get("leaders", []))[:3] if isinstance(item.get("leaders"), list) else [],
            }
            for item in groups[:5]
            if isinstance(item, dict)
        ],
        "top_candidates": [
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "review_score": item.get("review_score"),
                "ranking_breakdown": compact_dashboard_ranking_breakdown(item.get("ranking_breakdown", {})),
                "coverage_state": item.get("coverage_state"),
                "universe_context": item.get("universe_context", {}),
                "review_focus": compact_scan_review_focus_with_next(
                    item.get("review_focus", {}),
                    (item.get("commands", []) if isinstance(item.get("commands"), list) else [None])[0],
                ),
                "why_now": item.get("why_now"),
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
            }
            for item in candidates[:6]
            if isinstance(item, dict)
        ],
        "questions": list(scan.get("questions", []))[:5] if isinstance(scan.get("questions"), list) else [],
        "read": bool(result),
        "observations": result_observations[:4],
        "write_policy": "只读全市场扫描，不生成交易指令。",
    }


def agent_run_digest_headline(briefing_data: Dict[str, object]) -> str:
    daily = briefing_data.get("daily", {}) if isinstance(briefing_data.get("daily"), dict) else {}
    if not daily.get("available"):
        return "runtime 暂不可生成复盘摘要。"
    top = first_dict(daily.get("top_hotspots", []))
    exposure = daily.get("portfolio_exposure", {}) if isinstance(daily.get("portfolio_exposure"), dict) else {}
    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    parts = ["交易日 %s" % (daily.get("trade_date") or "未知")]
    if top:
        parts.append("最强链路 %s/%s，热点 %s" % (top.get("layer"), top.get("sub_sector"), top.get("score")))
    if exposure.get("has_concentration"):
        parts.append(str(exposure.get("summary") or "组合存在集中暴露。").rstrip("。"))
    if portfolio:
        parts.append("重点复核 %s 个" % portfolio.get("high_review_count", 0))
    return "；".join(part for part in parts if part) + "。"


def agent_run_digest_data_quality(validation: Dict[str, object], results: List[Dict[str, object]]) -> Dict[str, object]:
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    if not errors:
        errors = [issue for item in results if isinstance(item, dict) for issue in item.get("errors", []) if isinstance(item.get("errors"), list)]
    error_count = validation.get("error_count")
    warning_count = validation.get("warning_count")
    if errors and not error_count:
        error_count = len(errors)
    if warnings and not warning_count:
        warning_count = len(warnings)
    if error_count is None:
        error_count = len(errors)
    if warning_count is None:
        warning_count = len(warnings)
    return {
        "ok": validation.get("ok"),
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": compact_digest_issues(warnings),
        "errors": compact_digest_issues(errors),
        "summary": "错误 %s 个，告警 %s 个。" % (error_count, warning_count),
    }


def agent_run_digest_data_repair_plan(digest: Dict[str, object]) -> Dict[str, object]:
    data_quality = digest.get("data_quality", {}) if isinstance(digest.get("data_quality"), dict) else {}
    issues = []
    seen = set()
    for severity, values in (
        ("error", data_quality.get("errors", []) if isinstance(data_quality.get("errors"), list) else []),
        ("warning", data_quality.get("warnings", []) if isinstance(data_quality.get("warnings"), list) else []),
    ):
        for issue_item in values:
            if not isinstance(issue_item, dict):
                continue
            key = data_repair_issue_key(issue_item, severity)
            if key in seen:
                continue
            seen.add(key)
            issues.append(data_repair_item(issue_item, severity))
    issues.sort(key=lambda item: (0 if item.get("severity") == "error" else 1, str(item.get("symbol") or ""), str(item.get("code") or "")))
    grouped = group_data_repair_items(issues)
    return {
        "available": bool(issues),
        "summary": data_repair_summary(issues),
        "items": issues[:12],
        "groups": grouped,
        "commands": data_repair_commands(issues),
        "write_policy": "仅提示修复步骤，不自动修改 runtime 文件。",
    }


def data_repair_issue_key(issue_item: Dict[str, object], severity: str) -> tuple:
    return (
        severity,
        str(issue_item.get("code") or ""),
        str(issue_item.get("symbol") or ""),
        str(issue_item.get("path") or ""),
        str(issue_item.get("index") or ""),
    )


def data_repair_item(issue_item: Dict[str, object], severity: str) -> Dict[str, object]:
    code = str(issue_item.get("code") or "UNKNOWN")
    symbol = issue_item.get("symbol")
    missing = issue_item.get("missing", []) if isinstance(issue_item.get("missing"), list) else []
    repair_type = data_repair_type(code)
    return {
        "severity": severity,
        "code": code,
        "symbol": symbol,
        "path": issue_item.get("path"),
        "index": issue_item.get("index"),
        "missing": missing,
        "repair_type": repair_type,
        "title": data_repair_title(code, symbol, missing),
        "why_it_matters": data_repair_why(code),
        "repair_hint": data_repair_hint(code, symbol, missing),
        "commands": data_repair_item_commands(code, symbol),
        "agent_can_fix": False,
    }


def data_repair_type(code: str) -> str:
    if code in {"HOLDING_WITHOUT_QUOTE", "MISSING_FILE", "MISSING_RUNTIME_FILE"}:
        return "missing_quote_data"
    if code in {"QUOTE_NOT_IN_HOLDINGS"}:
        return "quote_not_in_holdings"
    if code in {"MISSING_REQUIRED_FIELDS", "MISSING_SYMBOL"}:
        return "missing_fields"
    if code in {"DUPLICATE_QUOTE_SYMBOL", "DUPLICATE_HOLDING_SYMBOL"}:
        return "duplicate_symbol"
    if code in {"INVALID_JSON", "INVALID_JSON_SHAPE", "INVALID_RECORD_SHAPE"}:
        return "invalid_runtime_file"
    if code in {"QUOTE_SYMBOL_NOT_IN_POOL", "HOLDING_SYMBOL_NOT_IN_POOL"}:
        return "pool_mismatch"
    return "runtime_validation"


def data_repair_title(code: str, symbol: object, missing: List[object]) -> str:
    if code == "HOLDING_WITHOUT_QUOTE":
        return "%s 持仓缺行情" % symbol
    if code == "QUOTE_NOT_IN_HOLDINGS":
        return "%s 行情不在持仓里" % symbol
    if code == "MISSING_REQUIRED_FIELDS":
        return "第 %s 条记录缺字段 %s" % (symbol or "未知", "、".join(str(field) for field in missing[:5]) or "未知")
    if code in {"MISSING_RUNTIME_FILE", "MISSING_FILE"}:
        return "runtime 文件缺失"
    if code.startswith("DUPLICATE_"):
        return "%s 重复记录" % (symbol or "symbol")
    if code.startswith("INVALID_"):
        return "runtime 文件结构异常"
    return "%s%s" % (symbol or "", " %s" % code if code else "数据问题")


def data_repair_why(code: str) -> str:
    messages = {
        "HOLDING_WITHOUT_QUOTE": "持仓缺行情会导致涨跌、热点上下文和持仓复核分失真。",
        "QUOTE_NOT_IN_HOLDINGS": "池内行情不在持仓里，可能仍会影响热点，但不能当作持仓表现解读。",
        "MISSING_REQUIRED_FIELDS": "缺必填字段会阻塞或削弱日报计算。",
        "MISSING_RUNTIME_FILE": "缺 runtime 文件时无法生成日报。",
        "MISSING_FILE": "缺 runtime 文件时无法生成日报。",
        "DUPLICATE_QUOTE_SYMBOL": "重复行情会让同一 symbol 的解释不稳定。",
        "DUPLICATE_HOLDING_SYMBOL": "重复持仓会让组合暴露重复计数。",
        "INVALID_JSON": "JSON 不能解析时无法读取 runtime 数据。",
        "INVALID_JSON_SHAPE": "JSON 结构不符合合同，无法读取记录列表。",
        "INVALID_RECORD_SHAPE": "记录不是对象，无法提取字段。",
        "QUOTE_SYMBOL_NOT_IN_POOL": "行情 symbol 不在池子里，缺少链路解释上下文。",
        "HOLDING_SYMBOL_NOT_IN_POOL": "持仓 symbol 不在池子里，缺少链路解释上下文。",
    }
    return messages.get(code, "该数据问题会影响日报和复核解释。")


def data_repair_hint(code: str, symbol: object, missing: List[object]) -> str:
    if code == "HOLDING_WITHOUT_QUOTE":
        return "补充 %s 的当日行情，或确认该持仓当天无需纳入行情复核。" % symbol
    if code == "QUOTE_NOT_IN_HOLDINGS":
        return "确认 %s 是否只是观察项；如果已经持有，则补入 holdings。" % symbol
    if code == "MISSING_REQUIRED_FIELDS":
        return "补齐字段：%s。" % ("、".join(str(field) for field in missing[:8]) or "必填字段")
    if code in {"MISSING_RUNTIME_FILE", "MISSING_FILE"}:
        return "先运行 init/import，或把 runtime quotes/holdings 文件放到指定路径。"
    if code.startswith("DUPLICATE_"):
        return "保留一条最新、可信的 symbol 记录。"
    if code.startswith("INVALID_"):
        return "修正 JSON 格式，或重新用 CSV 导入生成 runtime 文件。"
    if code in {"QUOTE_SYMBOL_NOT_IN_POOL", "HOLDING_SYMBOL_NOT_IN_POOL"}:
        return "确认 symbol 是否写错，或把该标的补入池子定义。"
    return "运行 validate runtime 查看详细定位。"


def data_repair_item_commands(code: str, symbol: object) -> List[str]:
    commands = ["market-intel validate runtime --json"]
    if code in {"HOLDING_WITHOUT_QUOTE", "MISSING_RUNTIME_FILE", "MISSING_FILE", "INVALID_JSON", "INVALID_JSON_SHAPE"}:
        commands.append("market-intel import quotes <quotes.csv> --runtime --json")
    if code in {"QUOTE_NOT_IN_HOLDINGS", "MISSING_RUNTIME_FILE", "MISSING_FILE", "INVALID_JSON", "INVALID_JSON_SHAPE"}:
        commands.append("market-intel import holdings <holdings.csv> --runtime --json")
    if symbol and code == "QUOTE_NOT_IN_HOLDINGS":
        commands.append("market-intel pool explain %s --runtime --text" % symbol)
    if symbol and code == "HOLDING_WITHOUT_QUOTE":
        commands.append("market-intel portfolio explain %s --runtime --text" % symbol)
    return commands[:4]


def group_data_repair_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    groups: Dict[str, Dict[str, object]] = {}
    for item in items:
        key = str(item.get("repair_type") or "runtime_validation")
        group = groups.setdefault(
            key,
            {
                "repair_type": key,
                "count": 0,
                "symbols": [],
                "codes": [],
                "commands": [],
            },
        )
        group["count"] = safe_int(group.get("count")) + 1
        if item.get("symbol"):
            group["symbols"].append(str(item.get("symbol")))
        if item.get("code"):
            group["codes"].append(str(item.get("code")))
        group["commands"].extend(str(command) for command in item.get("commands", []) if command) if isinstance(item.get("commands"), list) else None
    rows = []
    for group in groups.values():
        group["symbols"] = dedupe_queue_texts(group.get("symbols", []))[:8]
        group["codes"] = dedupe_queue_texts(group.get("codes", []))[:5]
        group["commands"] = dedupe_queue_texts(group.get("commands", []))[:5]
        rows.append(group)
    rows.sort(key=lambda item: (-safe_int(item.get("count")), str(item.get("repair_type") or "")))
    return rows


def data_repair_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return "暂无需要修复的数据问题。"
    error_count = sum(1 for item in items if item.get("severity") == "error")
    warning_count = sum(1 for item in items if item.get("severity") == "warning")
    symbols = dedupe_queue_texts([item.get("symbol") for item in items if item.get("symbol")])
    return "需处理错误 %s 个、告警 %s 个；涉及 symbol %s 个。" % (error_count, warning_count, len(symbols))


def data_repair_commands(items: List[Dict[str, object]]) -> List[str]:
    commands = ["market-intel validate runtime --json"] if items else []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("commands"), list):
            continue
        commands.extend(str(command) for command in item.get("commands", []) if command)
    return dedupe_queue_texts(commands)[:8]


def agent_run_digest_market_structure(daily: Dict[str, object]) -> Dict[str, object]:
    rows = []
    for item in daily.get("top_hotspots", []) if isinstance(daily.get("top_hotspots"), list) else []:
        if not isinstance(item, dict):
            continue
        leaders = [
            {
                "symbol": leader.get("symbol"),
                "name": leader.get("name"),
                "change_pct": leader.get("change_pct"),
            }
            for leader in item.get("leaders", [])[:3]
            if isinstance(leader, dict)
        ] if isinstance(item.get("leaders"), list) else []
        rows.append(
            {
                "rank": item.get("rank"),
                "chain": "%s/%s" % (item.get("layer"), item.get("sub_sector")),
                "score": item.get("score"),
                "active_member_count": item.get("active_member_count"),
                "member_count": item.get("member_count"),
                "leaders": leaders,
                "signals": list(item.get("signals", []))[:5] if isinstance(item.get("signals"), list) else [],
                "risks": list(item.get("risks", []))[:5] if isinstance(item.get("risks"), list) else [],
            }
        )
    top = rows[0] if rows else {}
    return {
        "summary": "%s | 热点 %s | 活跃 %s/%s" % (
            top.get("chain", "暂无稳定链路"),
            top.get("score", 0),
            top.get("active_member_count", 0),
            top.get("member_count", 0),
        )
        if top
        else "暂无稳定链路。",
        "top_chains": rows[:5],
    }


def agent_run_digest_portfolio_pressure(daily: Dict[str, object], holding_dashboard: Dict[str, object]) -> Dict[str, object]:
    exposure = daily.get("portfolio_exposure", {}) if isinstance(daily.get("portfolio_exposure"), dict) else {}
    holding_index = holding_dashboard_index(holding_dashboard)
    groups = []
    for source, group_type in (
        (exposure.get("repeated_exposures", []), "chain"),
        (exposure.get("repeated_overlap_groups", []), "theme"),
    ):
        for group in source if isinstance(source, list) else []:
            if not isinstance(group, dict):
                continue
            holdings = compact_digest_holdings(group.get("holdings", []))
            changed_members = portfolio_pressure_changed_members(holdings, holding_index)
            commands = list(group.get("commands", []))[:3] if isinstance(group.get("commands"), list) else []
            primary_command = "market-intel portfolio review --runtime --json"
            groups.append(
                {
                    "group_type": group_type,
                    "group": group.get("group"),
                    "holding_count": group.get("holding_count"),
                    "holdings": holdings,
                    "changed_member_count": len(changed_members),
                    "changed_members": changed_members,
                    "priority_question": portfolio_pressure_group_question(group_type, group.get("group"), changed_members),
                    "primary_command": primary_command,
                    "primary_json_command": digest_json_variant(primary_command),
                    "commands": commands,
                }
            )
    groups.sort(key=lambda item: (-safe_int(item.get("changed_member_count")), -safe_int(item.get("holding_count")), str(item.get("group") or "")))
    return {
        "has_concentration": bool(exposure.get("has_concentration")),
        "summary": portfolio_pressure_summary(exposure, groups),
        "group_count": exposure.get("group_count", len(groups)),
        "affected_holding_count": exposure.get("affected_holding_count", 0),
        "changed_group_count": sum(1 for group in groups if safe_int(group.get("changed_member_count")) > 0),
        "groups": groups[:5],
        "questions": list(exposure.get("questions", []))[:5] if isinstance(exposure.get("questions"), list) else [],
    }


def holding_dashboard_index(value: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    rows = value.get("top_holdings", []) if isinstance(value.get("top_holdings"), list) else []
    return {
        str(item.get("symbol")): item
        for item in rows
        if isinstance(item, dict) and item.get("symbol")
    }


def portfolio_pressure_changed_members(
    holdings: List[Dict[str, object]],
    holding_index: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    rows = []
    for holding in holdings:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        source = holding_index.get(str(holding.get("symbol")), {})
        change = source.get("change", {}) if isinstance(source.get("change"), dict) else {}
        if not change.get("available"):
            continue
        rows.append(
            {
                "symbol": holding.get("symbol"),
                "name": holding.get("name"),
                "change_priority": source.get("change_priority"),
                "review_score": source.get("review_score"),
                "reasons": list(change.get("reasons", []))[:5] if isinstance(change.get("reasons"), list) else [],
            }
        )
    rows.sort(key=lambda item: (-safe_int(item.get("change_priority")), -safe_float(item.get("review_score")), str(item.get("symbol") or "")))
    return rows[:6]


def portfolio_pressure_group_question(group_type: object, group_name: object, changed_members: List[Dict[str, object]]) -> str:
    label_text = {"chain": "链路", "theme": "主题"}.get(str(group_type), str(group_type or "暴露"))
    if changed_members:
        symbols = "、".join(str(item.get("symbol")) for item in changed_members[:4] if item.get("symbol"))
        return "%s %s 中 %s 发生变化，先确认是否来自同一驱动。" % (label_text, group_name, symbols)
    return "%s %s 涉及多只持仓，确认是否受同一叙事和同一风险驱动。" % (label_text, group_name)


def portfolio_pressure_summary(exposure: Dict[str, object], groups: List[Dict[str, object]]) -> str:
    base = str(exposure.get("summary") or "暂无组合集中暴露。")
    changed = sum(1 for group in groups if safe_int(group.get("changed_member_count")) > 0)
    if changed:
        return "%s；其中 %s 组存在变化成员。" % (base.rstrip("。"), changed)
    return base


def agent_run_digest_holding_dashboard(daily: Dict[str, object], change_tracking: Dict[str, object]) -> Dict[str, object]:
    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
    rows = [holding_dashboard_row(item, change_tracking) for item in items if isinstance(item, dict)]
    rows = [row for row in rows if row.get("symbol")]
    rows.sort(key=lambda row: (-safe_int(row.get("change_priority")), -safe_float(row.get("review_score")), str(row.get("symbol") or "")))
    buckets = holding_dashboard_buckets(rows)
    changed_holdings = [
        row
        for row in rows
        if isinstance(row.get("change"), dict) and row.get("change", {}).get("available")
    ]
    return {
        "available": bool(rows),
        "summary": holding_dashboard_summary(rows, portfolio, buckets),
        "holding_count": portfolio.get("count", len(rows)),
        "high_review_count": portfolio.get("high_review_count", buckets.get("high_review", 0)),
        "changed_holding_count": len(changed_holdings),
        "changed_holdings": compact_changed_holdings(changed_holdings),
        "buckets": buckets,
        "top_holdings": rows[:6],
        "questions": holding_dashboard_questions(rows),
        "write_policy": "只读持仓复盘，不自动修改持仓或写入 journal。",
    }


def holding_dashboard_row(item: Dict[str, object], change_tracking: Dict[str, object]) -> Dict[str, object]:
    symbol = str(item.get("symbol") or "")
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
    exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
    overlap_groups = item.get("overlap_groups", []) if isinstance(item.get("overlap_groups"), list) else []
    risk_flags = list(item.get("risk_flags", [])) if isinstance(item.get("risk_flags"), list) else []
    review_points = list(item.get("review_points", [])) if isinstance(item.get("review_points"), list) else []
    commands = list(item.get("commands", [])) if isinstance(item.get("commands"), list) else []
    coverage_state = str(item.get("coverage_state") or "confirmed")
    coverage_state_reasons = (
        list(item.get("coverage_state_reasons", []))
        if isinstance(item.get("coverage_state_reasons"), list)
        else []
    )
    research = compact_digest_research_status(item.get("research_status", {}))
    primary_command = first_digest_read_command(commands, "market-intel portfolio explain %s --runtime --json" % symbol) if symbol else "market-intel portfolio review --runtime --json"
    change = security_change_context(symbol, change_tracking) if symbol else {"available": False, "reasons": []}
    return {
        "symbol": symbol,
        "name": item.get("name"),
        "priority": item.get("priority"),
        "review_score": item.get("priority_score"),
        "coverage_state": coverage_state,
        "coverage_state_reasons": [str(reason) for reason in coverage_state_reasons[:6] if reason],
        "research_status": research,
        "has_quote": bool(quote),
        "in_hotspot": bool(hotspot),
        "quote": {
            "change_pct": quote.get("change_pct"),
            "amount_ratio": quote.get("amount_ratio"),
            "intraday_fade_pct": quote.get("intraday_fade_pct"),
        }
        if quote
        else None,
        "hotspot": {
            "chain": "%s/%s" % (hotspot.get("layer"), hotspot.get("sub_sector")),
            "score": hotspot.get("score"),
        }
        if hotspot
        else None,
        "exposure_count": len(exposures),
        "exposures": [
            {
                "chain": "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")),
                "role": exposure.get("role"),
            }
            for exposure in exposures[:4]
            if isinstance(exposure, dict)
        ],
        "overlap_groups": [str(group) for group in overlap_groups[:4] if group],
        "risk_flags": [str(flag) for flag in risk_flags[:8] if flag],
        "review_points": [str(point) for point in review_points[:4] if point],
        "change": change,
        "change_priority": holding_change_priority(change),
        "primary_question": holding_dashboard_primary_question(
            review_points,
            risk_flags,
            quote,
            hotspot,
            change,
            coverage_state,
            research,
        ),
        "primary_command": primary_command,
        "primary_json_command": digest_json_variant(primary_command),
        "commands": [str(command) for command in commands[:4] if command],
    }


def compact_changed_holdings(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    result = []
    for row in rows[:6]:
        change = row.get("change", {}) if isinstance(row.get("change"), dict) else {}
        result.append(
            {
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "change_priority": row.get("change_priority"),
                "reasons": list(change.get("reasons", []))[:5] if isinstance(change.get("reasons"), list) else [],
                "source": change.get("source"),
                "base_trade_date": change.get("base_trade_date"),
                "current_trade_date": change.get("current_trade_date"),
            }
        )
    return result


def holding_change_priority(change: Dict[str, object]) -> int:
    if not change.get("available"):
        return 0
    reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
    score = 10
    for reason in reasons:
        text = str(reason)
        if "持仓复核变化" in text:
            score += 8
        elif "观察项" in text:
            score += 6
        elif "新增风险" in text:
            score += 5
        elif "数据告警变化" in text:
            score += 4
        else:
            score += 2
    return score


def holding_dashboard_buckets(rows: List[Dict[str, object]]) -> Dict[str, int]:
    return {
        "total": len(rows),
        "high_review": sum(1 for row in rows if row.get("priority") == "high_review"),
        "medium_review": sum(1 for row in rows if row.get("priority") == "medium_review"),
        "normal_review": sum(1 for row in rows if row.get("priority") == "normal_review"),
        "foundation_coverage": sum(1 for row in rows if row.get("coverage_state") == "foundation"),
        "draft_coverage": sum(1 for row in rows if row.get("coverage_state") == "draft"),
        "missing_quote": sum(1 for row in rows if not row.get("has_quote")),
        "without_hotspot": sum(1 for row in rows if row.get("has_quote") and not row.get("in_hotspot")),
        "with_overlap": sum(1 for row in rows if row.get("overlap_groups")),
    }


def holding_dashboard_summary(
    rows: List[Dict[str, object]],
    portfolio: Dict[str, object],
    buckets: Dict[str, int],
) -> str:
    if not rows:
        return "暂无持仓复盘数据。"
    changed_count = sum(1 for row in rows if isinstance(row.get("change"), dict) and row.get("change", {}).get("available"))
    return (
        "持仓 %s 个，重点复核 %s 个；变化持仓 %s 个，缺行情 %s 个，缺热点上下文 %s 个，主题重叠 %s 个，基础/草稿覆盖 %s 个。"
        % (
            portfolio.get("count", buckets.get("total", 0)),
            portfolio.get("high_review_count", buckets.get("high_review", 0)),
            changed_count,
            buckets.get("missing_quote", 0),
            buckets.get("without_hotspot", 0),
            buckets.get("with_overlap", 0),
            buckets.get("foundation_coverage", 0) + buckets.get("draft_coverage", 0),
        )
    )


def holding_dashboard_primary_question(
    review_points: List[object],
    risk_flags: List[object],
    quote: Dict[str, object],
    hotspot: Dict[str, object],
    change: Dict[str, object],
    coverage_state: object = "",
    research_status: Optional[Dict[str, object]] = None,
) -> str:
    change_reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
    if change_reasons:
        return "先核对变化：%s。" % "、".join(str(reason) for reason in change_reasons[:3])
    research = research_status if isinstance(research_status, dict) else {}
    coverage_text = str(coverage_state or "")
    if coverage_text == "foundation":
        if research.get("available"):
            missing = research.get("missing_fields", []) if isinstance(research.get("missing_fields"), list) else []
            if missing:
                return "先把 research notes 补成 reviewed：缺 %s。" % "、".join(str(field) for field in missing[:3])
        return "先补齐全 A 基础清单命中的行业/主题逻辑、关键证据和证伪风险。"
    if coverage_text == "draft":
        return "先确认候选补池行的链路、角色、公司逻辑和证伪风险。"
    if review_points:
        return str(review_points[0])
    if not quote:
        return "先补齐该持仓行情，再判断今日上下文。"
    if not hotspot:
        return "确认它是否只是持仓波动，而非当日主线。"
    if risk_flags:
        return "复核主要风险标签：%s。" % "、".join(str(flag) for flag in risk_flags[:3])
    return "核对行情、链路和热点上下文是否一致。"


def holding_dashboard_questions(rows: List[Dict[str, object]]) -> List[str]:
    questions = []
    missing_quote = [row for row in rows if not row.get("has_quote")]
    if missing_quote:
        questions.append("先补齐缺行情持仓：%s。" % "、".join(str(row.get("symbol")) for row in missing_quote[:4]))
    no_hotspot = [row for row in rows if row.get("has_quote") and not row.get("in_hotspot")]
    if no_hotspot:
        questions.append("有行情但缺热点上下文的持仓是否只是个股波动：%s。" % "、".join(str(row.get("symbol")) for row in no_hotspot[:4]))
    overlap = [row for row in rows if row.get("overlap_groups")]
    if overlap:
        questions.append("主题重叠持仓是否受同一叙事驱动：%s。" % "、".join(str(row.get("symbol")) for row in overlap[:4]))
    high = [row for row in rows if row.get("priority") == "high_review"]
    if high:
        questions.append("重点复核持仓的高分来自行情、热点还是组合暴露：%s。" % "、".join(str(row.get("symbol")) for row in high[:4]))
    changed = [row for row in rows if isinstance(row.get("change"), dict) and row.get("change", {}).get("available")]
    if changed:
        questions.insert(0, "先看相对留档发生变化的持仓：%s。" % "、".join(str(row.get("symbol")) for row in changed[:4]))
    foundation = [row for row in rows if row.get("coverage_state") == "foundation"]
    if foundation:
        questions.append("基础清单覆盖持仓需要补研究证据：%s。" % "、".join(str(row.get("symbol")) for row in foundation[:4]))
    partial_research = [
        row
        for row in rows
        if isinstance(row.get("research_status"), dict)
        and row.get("research_status", {}).get("available")
        and not row.get("research_status", {}).get("confirmed")
    ]
    if partial_research:
        questions.append("已有 research notes 但证据未完整：%s。" % "、".join(str(row.get("symbol")) for row in partial_research[:4]))
    return dedupe_queue_texts(questions)[:5]


def compact_digest_research_status(value: object) -> Dict[str, object]:
    data = value if isinstance(value, dict) else {}
    return {
        "available": bool(data.get("available")),
        "status": data.get("status") or "missing",
        "source_file": data.get("source_file"),
        "has_thesis": bool(data.get("has_thesis")),
        "has_evidence": bool(data.get("has_evidence")),
        "has_invalidation": bool(data.get("has_invalidation")),
        "missing_fields": list(data.get("missing_fields", [])) if isinstance(data.get("missing_fields"), list) else [],
        "confirmed": bool(data.get("confirmed")),
    }


def agent_run_digest_securities(daily: Dict[str, object]) -> List[Dict[str, object]]:
    profiles = daily.get("security_risk_profile", []) if isinstance(daily.get("security_risk_profile"), list) else []
    rows = []
    for item in profiles[:6]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "severity": item.get("severity"),
                "priority_score": item.get("priority_score"),
                "risk_ids": list(item.get("risk_ids", []))[:8] if isinstance(item.get("risk_ids"), list) else [],
                "risk_labels": [
                    risk.get("label")
                    for risk in item.get("related_risks", [])[:5]
                    if isinstance(risk, dict) and risk.get("label")
                ]
                if isinstance(item.get("related_risks"), list)
                else [],
                "evidence": list(item.get("evidence", []))[:4] if isinstance(item.get("evidence"), list) else [],
                "questions": list(item.get("review_questions", []))[:4] if isinstance(item.get("review_questions"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "note_command": item.get("note_command"),
                "note_prerequisite": item.get("note_prerequisite") if isinstance(item.get("note_prerequisite"), dict) else {},
            }
        )
    return rows


def agent_run_digest_risks(daily: Dict[str, object]) -> List[Dict[str, object]]:
    risks = daily.get("risk_register", []) if isinstance(daily.get("risk_register"), list) else []
    rows = []
    for item in risks[:6]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": item.get("rank"),
                "risk_id": item.get("risk_id"),
                "label": item.get("label"),
                "severity": item.get("severity"),
                "affected_count": item.get("affected_count"),
                "affected_symbols": list(item.get("affected_symbols", []))[:6] if isinstance(item.get("affected_symbols"), list) else [],
                "evidence": list(item.get("evidence", []))[:3] if isinstance(item.get("evidence"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "review_question": item.get("review_question"),
            }
        )
    return rows


def agent_run_digest_security_workbench(
    daily: Dict[str, object],
    change_tracking: Dict[str, object],
    pressure: Dict[str, object],
) -> List[Dict[str, object]]:
    securities = agent_run_digest_securities(daily)
    rows = []
    for item in securities[:6]:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        symbol = str(item.get("symbol"))
        change = security_change_context(symbol, change_tracking)
        exposure_groups = security_exposure_groups(symbol, pressure)
        commands = list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else []
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": symbol,
                "name": item.get("name"),
                "severity": item.get("severity"),
                "priority_score": item.get("priority_score"),
                "review_reason": security_workbench_reason(item, change, exposure_groups),
                "change": change,
                "exposure_groups": exposure_groups,
                "risk_labels": list(item.get("risk_labels", []))[:6] if isinstance(item.get("risk_labels"), list) else [],
                "evidence": list(item.get("evidence", []))[:4] if isinstance(item.get("evidence"), list) else [],
                "questions": list(item.get("questions", []))[:4] if isinstance(item.get("questions"), list) else [],
                "commands": commands,
                "primary_command": commands[0] if commands else None,
                "note_command": item.get("note_command"),
                "note_prerequisite": item.get("note_prerequisite") if isinstance(item.get("note_prerequisite"), dict) else {},
            }
        )
    return rows


def agent_run_digest_evidence_checklist(
    digest: Dict[str, object],
    results: List[Dict[str, object]],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    result_index = attention_result_index(results)
    archive_prerequisite = journal_draft_archive_prerequisite(manual_followups)

    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    if repair.get("available"):
        commands = repair.get("commands", []) if isinstance(repair.get("commands"), list) else []
        items.append(
            evidence_checklist_item(
                items,
                "data_quality",
                "数据质量证据",
                "先确认 runtime 数据是否足够支撑今日复盘。",
                attention_repair_symbols(repair),
                attention_repair_evidence(repair),
                evidence_data_quality_gaps(repair),
                first_digest_read_command(commands, "market-intel validate runtime --json"),
                "数据错误/告警已处理或已明确哪些结论暂不能使用。",
                result_index,
                archive_prerequisite,
            )
        )

    change = attention_active_change(digest.get("change_tracking", {}))
    if change.get("has_delta"):
        commands = change.get("commands", []) if isinstance(change.get("commands"), list) else []
        items.append(
            evidence_checklist_item(
                items,
                str(change.get("change_type") or "current_change"),
                "变化证据",
                change.get("summary") or "相对留档已有变化，需要确认变化来源。",
                attention_change_symbols(change),
                attention_change_evidence(change),
                evidence_change_gaps(change),
                first_digest_read_command(commands, "market-intel agent briefing --json"),
                "已说明变化来自热点、观察项、持仓复核还是数据质量。",
                result_index,
                archive_prerequisite,
            )
        )

    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    for holding in holdings[:3]:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        items.append(
            evidence_checklist_item(
                items,
                "holding_review",
                "%s %s" % (holding.get("symbol"), holding.get("name") or ""),
                holding.get("primary_question") or dashboard.get("summary") or "复核该持仓的行情、热点和风险上下文。",
                [holding.get("symbol")],
                evidence_holding_rows(holding),
                evidence_holding_gaps(holding),
                holding.get("primary_json_command") or holding.get("primary_command"),
                "已核对该持仓的行情、热点、风险标签、组合暴露和变化原因。",
                result_index,
                archive_prerequisite,
            )
        )

    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
    for group in groups[:2]:
        if not isinstance(group, dict):
            continue
        items.append(
            evidence_checklist_item(
                items,
                "portfolio_pressure",
                "组合压力：%s" % (group.get("group") or "重复暴露"),
                group.get("priority_question") or "确认该组持仓是否受同一叙事和同一风险驱动。",
                evidence_group_symbols(group),
                evidence_pressure_rows(group),
                evidence_pressure_gaps(group),
                group.get("primary_json_command") or group.get("primary_command"),
                "已确认该重复暴露是否仍是同一链路/主题驱动。",
                result_index,
                archive_prerequisite,
            )
        )

    market = digest.get("market_structure", {}) if isinstance(digest.get("market_structure"), dict) else {}
    chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
    if chains:
        top = chains[0] if isinstance(chains[0], dict) else {}
        leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
        items.append(
            evidence_checklist_item(
                items,
                "market_structure",
                "市场结构证据",
                "确认最强链路是否有足够活跃成员和持仓关联。",
                [leader.get("symbol") for leader in leaders if isinstance(leader, dict) and leader.get("symbol")],
                evidence_market_rows(top),
                evidence_market_gaps(top),
                "market-intel map --runtime --json",
                "已确认最强链路、活跃成员、领涨标的和组合关联。",
                result_index,
                archive_prerequisite,
            )
        )

    rows = items[:8]
    return {
        "available": bool(rows),
        "summary": evidence_checklist_summary(rows),
        "items": rows,
        "write_policy": "只整理证据充分性；不生成交易指令或自动写入 journal。",
    }


def evidence_checklist_item(
    items: List[Dict[str, object]],
    item_type: str,
    title: object,
    question: object,
    symbols: List[object],
    evidence: List[object],
    missing_evidence: List[object],
    command: object,
    done_when: object,
    result_index: Dict[str, Dict[str, object]],
    archive_prerequisite: Dict[str, object],
) -> Dict[str, object]:
    command_text = str(command or "")
    json_command = digest_json_variant(command_text) if command_text else ""
    linked_result = attention_linked_result(command_text, json_command, result_index)
    clean_symbols = dedupe_queue_texts(symbols)[:6]
    clean_evidence = dedupe_queue_texts(evidence)[:6]
    clean_missing = dedupe_queue_texts(missing_evidence)[:5]
    status = evidence_coverage_status(clean_evidence, clean_missing, bool(linked_result))
    section = evidence_note_section(item_type)
    draft = evidence_note_draft(title, question, clean_symbols, clean_evidence, clean_missing)
    return {
        "rank": len(items) + 1,
        "item_type": item_type,
        "title": str(title or item_type),
        "related_symbols": clean_symbols,
        "question": str(question or ""),
        "evidence": clean_evidence,
        "missing_evidence": clean_missing,
        "coverage_status": status,
        "coverage_label": evidence_coverage_label(status),
        "json_command": json_command,
        "already_read": bool(linked_result),
        "linked_result": linked_result,
        "done_when": str(done_when or ""),
        "journal_note": {
            "available": bool(draft),
            "section": section,
            "draft_text": draft,
            "prefilled_note_command": prefilled_journal_note_command(section, draft) if draft else "",
            "run_after": archive_prerequisite.get("archive_command"),
            "archive_prerequisite": archive_prerequisite,
            "write_policy": "仅生成记录模板，不自动写入 journal。",
        },
    }


def evidence_coverage_status(evidence: List[str], missing: List[str], already_read: bool) -> str:
    if missing and any("数据" in item or "行情" in item for item in missing):
        return "blocked_by_data"
    if missing:
        return "needs_more_context"
    if already_read and evidence:
        return "covered"
    return "needs_read"


def evidence_coverage_label(status: str) -> str:
    labels = {
        "covered": "证据已覆盖",
        "needs_read": "待读取",
        "needs_more_context": "需补证据",
        "blocked_by_data": "数据阻塞",
    }
    return labels.get(status, status)


def evidence_note_section(item_type: str) -> str:
    if item_type == "data_quality":
        return "data_quality"
    if item_type in {"current_vs_latest", "history_transition", "current_change"}:
        return "current_change"
    if item_type == "portfolio_pressure":
        return "portfolio_exposure"
    if item_type == "market_structure":
        return "market_structure"
    return "security_review"


def evidence_note_draft(
    title: object,
    question: object,
    symbols: List[str],
    evidence: List[str],
    missing: List[str],
) -> str:
    symbol_text = "、".join(symbols[:5]) or "暂无"
    evidence_text = "；".join(evidence[:3]) or "暂无"
    missing_text = "；".join(missing[:3]) or "暂无"
    return ensure_sentence(
        "证据复核：%s；标的 %s；问题：%s；已有证据 %s；待补证据 %s"
        % (title, symbol_text, strip_sentence_end(question), evidence_text, missing_text)
    )


def evidence_data_quality_gaps(repair: Dict[str, object]) -> List[object]:
    groups = repair.get("groups", []) if isinstance(repair.get("groups"), list) else []
    if not groups:
        return []
    return [
        "%s 仍需人工处理 %s 项" % (repair_type_label(group.get("repair_type")), group.get("count", 0))
        for group in groups[:4]
        if isinstance(group, dict)
    ]


def evidence_change_gaps(change: Dict[str, object]) -> List[object]:
    gaps = []
    validation = change.get("validation", {}) if isinstance(change.get("validation"), dict) else {}
    if safe_int(validation.get("warning_delta")):
        gaps.append("数据告警有变化，先排除数据口径影响。")
    symbols = attention_change_symbols(change)
    if symbols:
        gaps.append("变化标的需要逐只确认：%s。" % "、".join(str(symbol) for symbol in symbols[:4]))
    return gaps


def evidence_holding_rows(holding: Dict[str, object]) -> List[object]:
    rows = attention_holding_evidence(holding)
    coverage_state = str(holding.get("coverage_state") or "")
    if coverage_state and coverage_state != "confirmed":
        rows.append("覆盖状态 %s" % coverage_state)
    research = holding.get("research_status", {}) if isinstance(holding.get("research_status"), dict) else {}
    if research.get("confirmed"):
        rows.append("研究证据 reviewed，核心逻辑/关键证据/证伪风险齐全")
    elif research.get("available"):
        rows.append("研究记录 %s，证据待补" % (research.get("status") or "draft"))
    quote = holding.get("quote", {}) if isinstance(holding.get("quote"), dict) else {}
    if quote:
        rows.append(
            "涨跌 %s，量比 %s，回落 %s"
            % (quote.get("change_pct"), quote.get("amount_ratio"), quote.get("intraday_fade_pct"))
        )
    hotspot = holding.get("hotspot", {}) if isinstance(holding.get("hotspot"), dict) else {}
    if hotspot:
        rows.append("热点 %s，分 %s" % (hotspot.get("chain"), hotspot.get("score")))
    change = holding.get("change", {}) if isinstance(holding.get("change"), dict) else {}
    reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
    if reasons:
        rows.append("变化 %s" % "、".join(str(reason) for reason in reasons[:3]))
    return rows


def evidence_holding_gaps(holding: Dict[str, object]) -> List[object]:
    gaps = []
    coverage_state = str(holding.get("coverage_state") or "")
    research = holding.get("research_status", {}) if isinstance(holding.get("research_status"), dict) else {}
    if coverage_state == "foundation":
        if research.get("available") and not research.get("confirmed"):
            missing = research.get("missing_fields", []) if isinstance(research.get("missing_fields"), list) else []
            if missing:
                gaps.append("research notes 已存在但未完整，缺 %s。" % "、".join(str(field) for field in missing[:3]))
            else:
                gaps.append("research notes 已存在但状态不是 reviewed。")
        else:
            gaps.append("只命中全 A 基础清单，需补行业/主题逻辑、关键证据和证伪风险。")
    elif coverage_state == "draft":
        gaps.append("来自候选或待复核补池行，需确认链路、角色、公司逻辑和证伪风险。")
    if not holding.get("has_quote"):
        gaps.append("缺少当日行情，先补齐或确认不纳入今日复盘。")
    if holding.get("has_quote") and not holding.get("in_hotspot"):
        gaps.append("缺少热点链路上下文，需要确认是否只是持仓自身波动。")
    if not holding.get("exposures") and not holding.get("overlap_groups"):
        gaps.append("缺少组合或主题暴露证据，需要读取单票解释。")
    change = holding.get("change", {}) if isinstance(holding.get("change"), dict) else {}
    reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
    if any("数据告警" in str(reason) for reason in reasons):
        gaps.append("变化包含数据告警，需要先确认数据口径。")
    return gaps


def evidence_group_symbols(group: Dict[str, object]) -> List[object]:
    holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
    return [holding.get("symbol") for holding in holdings if isinstance(holding, dict) and holding.get("symbol")]


def evidence_pressure_rows(group: Dict[str, object]) -> List[object]:
    label_text = {"chain": "链路", "theme": "主题"}.get(str(group.get("group_type")), str(group.get("group_type") or "暴露"))
    rows = ["%s %s 涉及 %s 个持仓" % (label_text, group.get("group"), group.get("holding_count"))]
    changed = group.get("changed_members", []) if isinstance(group.get("changed_members"), list) else []
    if changed:
        rows.append(
            "变化成员 %s"
            % "、".join(str(member.get("symbol")) for member in changed[:4] if isinstance(member, dict) and member.get("symbol"))
        )
    holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
    if holdings:
        rows.append(
            "成员 %s"
            % "、".join(str(holding.get("symbol")) for holding in holdings[:5] if isinstance(holding, dict) and holding.get("symbol"))
        )
    return rows


def evidence_pressure_gaps(group: Dict[str, object]) -> List[object]:
    changed = group.get("changed_members", []) if isinstance(group.get("changed_members"), list) else []
    if changed:
        return ["需要确认变化成员是否来自同一驱动。"]
    return ["缺少变化成员，只能说明静态集中暴露，仍需确认共同驱动。"]


def evidence_market_rows(top: Dict[str, object]) -> List[object]:
    rows = [
        "链路 %s，热点 %s，活跃 %s/%s"
        % (top.get("chain"), top.get("score"), top.get("active_member_count"), top.get("member_count"))
    ]
    leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
    if leaders:
        rows.append(
            "领涨 %s"
            % "、".join(str(leader.get("symbol")) for leader in leaders[:3] if isinstance(leader, dict) and leader.get("symbol"))
        )
    signals = top.get("signals", []) if isinstance(top.get("signals"), list) else []
    if signals:
        rows.append("信号 %s" % "、".join(str(signal) for signal in signals[:3]))
    risks = top.get("risks", []) if isinstance(top.get("risks"), list) else []
    if risks:
        rows.append("风险 %s" % "、".join(str(risk) for risk in risks[:3]))
    return rows


def evidence_market_gaps(top: Dict[str, object]) -> List[object]:
    gaps = []
    active = safe_int(top.get("active_member_count"))
    members = safe_int(top.get("member_count"))
    if members and active < members:
        gaps.append("活跃成员未覆盖全链路，需要确认强度是否集中在少数标的。")
    leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
    if not leaders:
        gaps.append("缺少领涨标的，需要读取市场地图确认链路强度。")
    return gaps


def evidence_checklist_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return "暂无证据清单。"
    pending = sum(1 for item in items if item.get("coverage_status") != "covered")
    read = sum(1 for item in items if item.get("already_read"))
    symbols = dedupe_queue_texts([symbol for item in items for symbol in item.get("related_symbols", []) if isinstance(item, dict)])
    return "证据项 %s 个，待补证据 %s 个，已读取 %s 个；涉及标的 %s 个。" % (len(items), pending, read, len(symbols))


def agent_run_digest_hypothesis_board(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    archive_prerequisite = journal_draft_archive_prerequisite(manual_followups)
    evidence = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    evidence_items = evidence.get("items", []) if isinstance(evidence.get("items"), list) else []
    evidence_by_type = hypothesis_evidence_by_type(evidence_items)

    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    if repair.get("available"):
        commands = repair.get("commands", []) if isinstance(repair.get("commands"), list) else []
        items.append(
            hypothesis_board_item(
                items,
                "data_quality",
                "数据缺口可能影响今日复盘口径",
                "数据告警/错误如果不处理，热点、持仓复核和历史变化都可能被误读。",
                attention_repair_symbols(repair),
                evidence_items_for_types(evidence_by_type, {"data_quality"}),
                "先确认数据缺口是否消除，或明确哪些结论需要降权解读。",
                "数据错误/告警清零，或已记录仍受影响的 symbol 和字段。",
                first_digest_read_command(commands, "market-intel validate runtime --json"),
                archive_prerequisite,
            )
        )

    change = attention_active_change(digest.get("change_tracking", {}))
    if change.get("has_delta"):
        commands = change.get("commands", []) if isinstance(change.get("commands"), list) else []
        items.append(
            hypothesis_board_item(
                items,
                str(change.get("change_type") or "current_change"),
                "当前变化可能来自结构切换",
                change.get("summary") or "相对留档已有变化，需要确认是热点、持仓复核还是数据口径变化。",
                attention_change_symbols(change),
                evidence_items_for_types(evidence_by_type, {"current_vs_latest", "history_transition", "current_change"}),
                "核对变化是否集中在同一链路/主题，而不是单一标的或数据告警造成。",
                "下一次对比里变化原因消失、转向，或被数据口径解释。",
                first_digest_read_command(commands, "market-intel agent briefing --json"),
                archive_prerequisite,
            )
        )

    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
    if groups:
        group = groups[0] if isinstance(groups[0], dict) else {}
        items.append(
            hypothesis_board_item(
                items,
                "portfolio_pressure",
                "组合可能存在同向暴露",
                group.get("priority_question") or pressure.get("summary") or "组合存在重复链路/主题，需要确认共同驱动。",
                evidence_group_symbols(group),
                evidence_items_for_types(evidence_by_type, {"portfolio_pressure"}),
                "确认同组持仓的上涨/回落、风险标签和热点链路是否来自同一驱动。",
                "同组成员走势和风险标签分化，或共同链路不再是最强结构。",
                group.get("primary_json_command") or "market-intel portfolio review --runtime --json",
                archive_prerequisite,
            )
        )

    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    if holdings:
        holding = holdings[0] if isinstance(holdings[0], dict) else {}
        items.append(
            hypothesis_board_item(
                items,
                "holding_review",
                "%s %s 的复核优先级需要验证" % (holding.get("symbol"), holding.get("name") or ""),
                holding.get("primary_question") or "重点持仓需要确认行情、热点、风险和组合暴露是否一致。",
                [holding.get("symbol")],
                evidence_items_for_symbols(evidence_items, [holding.get("symbol")]),
                "读取单票解释并核对行情、热点、风险标签和组合暴露是否支持当前复核优先级。",
                "单票解释显示缺行情、缺热点、风险标签消失，或复核分回落到常规。",
                holding.get("primary_json_command") or holding.get("primary_command"),
                archive_prerequisite,
            )
        )

    market = digest.get("market_structure", {}) if isinstance(digest.get("market_structure"), dict) else {}
    chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
    if chains:
        top = chains[0] if isinstance(chains[0], dict) else {}
        leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
        items.append(
            hypothesis_board_item(
                items,
                "market_structure",
                "最强链路可能仍是今日主线",
                market.get("summary") or "市场结构需要确认是否由多标的共振支撑。",
                [leader.get("symbol") for leader in leaders if isinstance(leader, dict) and leader.get("symbol")],
                evidence_items_for_types(evidence_by_type, {"market_structure"}),
                "核对最强链路的活跃成员、领涨标的、风险信号和持仓关联是否延续。",
                "活跃成员收缩、领涨标的缺失，或最强链路切换。",
                "market-intel map --runtime --json",
                archive_prerequisite,
            )
        )

    rows = items[:6]
    return {
        "available": bool(rows),
        "summary": hypothesis_board_summary(rows),
        "items": rows,
        "write_policy": "只生成可证伪观察假设，不生成交易指令。",
    }


def hypothesis_board_item(
    items: List[Dict[str, object]],
    item_type: str,
    hypothesis: object,
    why: object,
    symbols: List[object],
    evidence_items: List[Dict[str, object]],
    validation_step: object,
    invalidation_signal: object,
    command: object,
    archive_prerequisite: Dict[str, object],
) -> Dict[str, object]:
    clean_symbols = dedupe_queue_texts(symbols)[:6]
    supporting = hypothesis_supporting_evidence(evidence_items)
    weak_points = hypothesis_weak_points(evidence_items)
    confidence = hypothesis_confidence(supporting, weak_points)
    command_text = str(command or "")
    json_command = digest_json_variant(command_text) if command_text else ""
    section = evidence_note_section(item_type)
    draft = hypothesis_note_draft(hypothesis, clean_symbols, supporting, weak_points, validation_step, invalidation_signal)
    return {
        "rank": len(items) + 1,
        "item_type": item_type,
        "hypothesis": str(hypothesis or item_type),
        "why_it_matters": str(why or ""),
        "related_symbols": clean_symbols,
        "supporting_evidence": supporting,
        "weak_points": weak_points,
        "confidence": confidence,
        "validation_step": str(validation_step or ""),
        "invalidation_signal": str(invalidation_signal or ""),
        "json_command": json_command,
        "done_when": "已记录支持证据、薄弱点、下一步验证和失效信号。",
        "journal_note": {
            "available": bool(draft),
            "section": section,
            "draft_text": draft,
            "prefilled_note_command": prefilled_journal_note_command(section, draft) if draft else "",
            "run_after": archive_prerequisite.get("archive_command"),
            "archive_prerequisite": archive_prerequisite,
            "write_policy": "仅生成记录模板，不自动写入 journal。",
        },
    }


def hypothesis_evidence_by_type(items: List[object]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("item_type") or "")
        if key:
            grouped.setdefault(key, []).append(item)
    return grouped


def evidence_items_for_types(
    grouped: Dict[str, List[Dict[str, object]]],
    types: set,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for item_type in types:
        rows.extend(grouped.get(item_type, []))
    return rows


def evidence_items_for_symbols(items: List[object], symbols: List[object]) -> List[Dict[str, object]]:
    wanted = set(dedupe_queue_texts(symbols))
    if not wanted:
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        related = set(dedupe_queue_texts(item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []))
        if wanted & related:
            rows.append(item)
    return rows


def hypothesis_supporting_evidence(items: List[Dict[str, object]]) -> List[str]:
    rows = []
    for item in items:
        rows.extend(item.get("evidence", []) if isinstance(item.get("evidence"), list) else [])
    return dedupe_queue_texts(rows)[:5]


def hypothesis_weak_points(items: List[Dict[str, object]]) -> List[str]:
    rows = []
    for item in items:
        rows.extend(item.get("missing_evidence", []) if isinstance(item.get("missing_evidence"), list) else [])
        status = item.get("coverage_status")
        if status and status != "covered":
            rows.append(str(item.get("coverage_label") or status))
    return dedupe_queue_texts(rows)[:5]


def hypothesis_confidence(supporting: List[str], weak_points: List[str]) -> str:
    if not supporting:
        return "low"
    if weak_points:
        return "medium"
    return "high"


def hypothesis_note_draft(
    hypothesis: object,
    symbols: List[str],
    supporting: List[str],
    weak_points: List[str],
    validation_step: object,
    invalidation_signal: object,
) -> str:
    return ensure_sentence(
        "观察假设：%s；标的 %s；支持证据 %s；薄弱点 %s；验证：%s；失效信号：%s"
        % (
            hypothesis,
            "、".join(symbols[:5]) or "暂无",
            "；".join(supporting[:3]) or "暂无",
            "；".join(weak_points[:3]) or "暂无",
            strip_sentence_end(validation_step),
            strip_sentence_end(invalidation_signal),
        )
    )


def hypothesis_board_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return "暂无观察假设。"
    weak = sum(1 for item in items if item.get("weak_points"))
    symbols = dedupe_queue_texts([symbol for item in items for symbol in item.get("related_symbols", []) if isinstance(item, dict)])
    return "观察假设 %s 条，其中 %s 条仍有薄弱点；涉及标的 %s 个。" % (len(items), weak, len(symbols))


def agent_run_digest_journal_draft(digest: Dict[str, object], manual_followups: List[Dict[str, object]]) -> Dict[str, object]:
    prerequisite = journal_draft_archive_prerequisite(manual_followups)
    if not digest.get("available"):
        return {
            "available": False,
            "summary": "runtime 暂不可用，先记录数据阻塞和需要补齐的文件。",
            "sections": [
                journal_draft_section(
                    "data_quality",
                    "数据质量",
                    str(digest.get("headline") or "runtime 暂不可生成复盘摘要。"),
                    ["market-intel status runtime --json", "market-intel validate runtime --json"],
                    prerequisite,
                )
            ],
            "combined_text": str(digest.get("headline") or "runtime 暂不可生成复盘摘要。"),
            "archive_prerequisite": prerequisite,
            "write_policy": "仅生成草稿，不自动写入 journal。",
        }
    sections = [
        journal_draft_section(
            "data_quality",
            "数据质量",
            journal_draft_data_quality(digest.get("data_quality", {})),
            ["market-intel validate runtime --json"],
            prerequisite,
        ),
        journal_draft_section(
            "market_structure",
            "市场结构",
            journal_draft_market_structure(digest.get("market_structure", {})),
            ["market-intel daily --runtime --json", "market-intel map --runtime --text"],
            prerequisite,
        ),
        journal_draft_section(
            "portfolio_exposure",
            "组合压力",
            journal_draft_portfolio_pressure(digest.get("portfolio_pressure", {})),
            ["market-intel portfolio review --runtime --text"],
            prerequisite,
        ),
        journal_draft_section(
            "current_change",
            "变化跟踪",
            journal_draft_change_tracking(digest.get("change_tracking", {})),
            ["market-intel journal latest --text", "market-intel journal timeline --text"],
            prerequisite,
        ),
        journal_draft_section(
            "security_review",
            "单票复核",
            journal_draft_security_workbench(digest.get("security_workbench", [])),
            journal_draft_security_commands(digest.get("security_workbench", [])),
            prerequisite,
        ),
    ]
    return {
        "available": True,
        "summary": "按五段生成可编辑复盘草稿；人工确认后再写入 journal。",
        "sections": sections,
        "combined_text": "\n".join("%s：%s" % (section["title"], section["draft_text"]) for section in sections),
        "archive_prerequisite": prerequisite,
        "write_policy": "仅生成草稿，不自动写入 journal。",
    }


def journal_draft_archive_prerequisite(manual_followups: List[Dict[str, object]]) -> Dict[str, object]:
    archive = next(
        (
            item
            for item in manual_followups
            if isinstance(item, dict) and "journal save" in str(item.get("json_command") or item.get("command") or "")
        ),
        None,
    )
    command = archive.get("json_command") or archive.get("command") if isinstance(archive, dict) else "market-intel journal save --runtime --json"
    return {
        "requires_archive": True,
        "archive_command": command,
        "archive_runnable": bool(command),
        "reason": "journal note 会写入最近日报留档；记录草稿前应先保存当前日报。",
    }


def journal_draft_section(
    section_id: str,
    title: str,
    draft_text: str,
    evidence_commands: List[object],
    archive_prerequisite: Dict[str, object],
) -> Dict[str, object]:
    text = str(draft_text or "")
    prefilled = prefilled_journal_note_command(section_id, text)
    return {
        "id": section_id,
        "title": title,
        "draft_text": text,
        "evidence_commands": [str(command) for command in evidence_commands if command][:4],
        "note_command_template": "market-intel journal note --section %s --text '<填写%s复盘笔记>'" % (section_id, title),
        "prefilled_note_command": prefilled,
        "prefilled_note_runnable": bool(text),
        "archive_prerequisite": archive_prerequisite,
        "run_after": archive_prerequisite.get("archive_command"),
    }


def prefilled_journal_note_command(section_id: str, draft_text: str) -> str:
    return "market-intel journal note --section %s --text %s" % (section_id, shlex.quote(draft_text))


def journal_draft_data_quality(value: object) -> str:
    data = value if isinstance(value, dict) else {}
    repair = data.get("repair_plan", {}) if isinstance(data.get("repair_plan"), dict) else {}
    warnings = data.get("warnings", []) if isinstance(data.get("warnings"), list) else []
    errors = data.get("errors", []) if isinstance(data.get("errors"), list) else []
    if errors:
        base = "数据存在错误 %s 个，需要先处理：%s。" % (
            data.get("error_count", len(errors)),
            "、".join(str(item.get("code") or item) for item in errors[:3] if isinstance(item, dict) or item),
        )
        return append_repair_hint(base, repair)
    if warnings:
        base = "数据可用但有告警 %s 个，重点核对：%s。" % (
            data.get("warning_count", len(warnings)),
            "、".join(str(item.get("code") or item) for item in warnings[:3] if isinstance(item, dict) or item),
        )
        return append_repair_hint(base, repair)
    return "数据质量正常：%s" % (data.get("summary") or "错误 0 个，告警 0 个。")


def append_repair_hint(text: str, repair: Dict[str, object]) -> str:
    if not repair.get("available"):
        return text
    groups = repair.get("groups", []) if isinstance(repair.get("groups"), list) else []
    if not groups:
        return text
    first = groups[0] if isinstance(groups[0], dict) else {}
    symbols = first.get("symbols", []) if isinstance(first.get("symbols"), list) else []
    return "%s 修复优先看 %s：%s。" % (
        text.rstrip("。"),
        repair_type_label(first.get("repair_type")),
        "、".join(str(symbol) for symbol in symbols[:5]) or "无 symbol",
    )


def repair_type_label(value: object) -> str:
    labels = {
        "missing_quote_data": "缺行情",
        "quote_not_in_holdings": "行情不在持仓",
        "missing_fields": "缺字段",
        "duplicate_symbol": "重复 symbol",
        "invalid_runtime_file": "runtime 文件异常",
        "pool_mismatch": "池子不匹配",
        "runtime_validation": "runtime 校验",
    }
    return labels.get(str(value), str(value))


def journal_draft_market_structure(value: object) -> str:
    market = value if isinstance(value, dict) else {}
    chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
    if not chains:
        return "今日暂无稳定热点结构。"
    top = chains[0] if isinstance(chains[0], dict) else {}
    leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
    leader_text = "、".join("%s %s" % (leader.get("symbol"), leader.get("name") or "") for leader in leaders[:3] if isinstance(leader, dict))
    return "最强链路为 %s，热点 %s，活跃 %s/%s；领涨/核心观察：%s。" % (
        top.get("chain"),
        top.get("score"),
        top.get("active_member_count"),
        top.get("member_count"),
        leader_text or "暂无",
    )


def journal_draft_portfolio_pressure(value: object) -> str:
    pressure = value if isinstance(value, dict) else {}
    groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
    if not pressure.get("has_concentration"):
        return "组合暂无明显重复链路或重复主题暴露。"
    group_text = "；".join(
        "%s %s 涉及 %s 个持仓" % (
            {"chain": "链路", "theme": "主题"}.get(str(group.get("group_type")), str(group.get("group_type"))),
            group.get("group"),
            group.get("holding_count"),
        )
        for group in groups[:3]
        if isinstance(group, dict)
    )
    return "%s 需要确认这些持仓是否受同一叙事和同一风险驱动。" % (group_text or pressure.get("summary") or "组合存在集中暴露。")


def journal_draft_change_tracking(value: object) -> str:
    tracking = value if isinstance(value, dict) else {}
    transition = tracking.get("history_transition", {}) if isinstance(tracking.get("history_transition"), dict) else {}
    current = tracking.get("current_vs_latest", {}) if isinstance(tracking.get("current_vs_latest"), dict) else {}
    source = transition if transition.get("available") else current
    if not source.get("available"):
        history = tracking.get("history", {}) if isinstance(tracking.get("history"), dict) else {}
        return "历史留档 %s/%s，暂未形成可对比转折。" % (history.get("count", 0), history.get("total_count", 0))
    top = source.get("hotspots", {}).get("top", {}) if isinstance(source.get("hotspots"), dict) else {}
    base = top.get("base", {}) if isinstance(top.get("base"), dict) else {}
    current_top = top.get("current", {}) if isinstance(top.get("current"), dict) else {}
    portfolio = source.get("portfolio_review", {}) if isinstance(source.get("portfolio_review"), dict) else {}
    validation = source.get("validation", {}) if isinstance(source.get("validation"), dict) else {}
    return "%s 最强链路 %s -> %s；持仓复核变化 %s 个；数据告警变化 %+s。" % (
        source.get("summary") or "已有变化对比。",
        base.get("key") or "无",
        current_top.get("key") or "无",
        portfolio.get("changed_count", 0),
        validation.get("warning_delta", 0),
    )


def journal_draft_security_workbench(value: object) -> str:
    rows = value if isinstance(value, list) else []
    if not rows:
        return "今日没有高优先级单票复核。"
    parts = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        groups = item.get("exposure_groups", []) if isinstance(item.get("exposure_groups"), list) else []
        change = item.get("change", {}) if isinstance(item.get("change"), dict) else {}
        change_reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
        parts.append(
            "%s %s：%s%s"
            % (
                item.get("symbol"),
                item.get("name") or "",
                item.get("review_reason") or "需要复核。",
                " 变化：" + "、".join(str(reason) for reason in change_reasons[:3]) if change_reasons else "",
            )
        )
        if groups:
            parts[-1] += " 重复暴露：" + "、".join(str(group.get("group")) for group in groups[:3] if isinstance(group, dict))
    return ensure_sentence("；".join(parts))


def ensure_sentence(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith(("。", "！", "？")):
        return text
    return "%s。" % text


def strip_sentence_end(value: object) -> str:
    return str(value or "").strip().rstrip("。！？；; ")


def journal_draft_security_commands(value: object) -> List[object]:
    rows = value if isinstance(value, list) else []
    commands = []
    for item in rows[:3]:
        if isinstance(item, dict) and item.get("primary_command"):
            commands.append(item.get("primary_command"))
    return commands


def agent_run_digest_attention_queue(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
    results: List[Dict[str, object]],
    source_briefing: Dict[str, object],
) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    result_index = attention_result_index(results)
    context_index = attention_context_index(digest, source_briefing)
    archive_prerequisite = journal_draft_archive_prerequisite(manual_followups)
    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    if repair.get("available"):
        commands = repair.get("commands", []) if isinstance(repair.get("commands"), list) else []
        items.append(
            attention_queue_item(
                items,
                "data_repair",
                "先处理数据问题",
                repair.get("summary"),
                first_digest_read_command(commands, "market-intel validate runtime --json"),
                "read_only",
                "数据错误/告警已定位，知道哪些 symbol 或文件需要人工修正。",
                related_symbols=attention_repair_symbols(repair),
                evidence=attention_repair_evidence(repair),
                result_index=result_index,
                context_index=context_index,
                archive_prerequisite=archive_prerequisite,
            )
        )

    change = attention_active_change(digest.get("change_tracking", {}))
    if change.get("has_delta"):
        commands = change.get("commands", []) if isinstance(change.get("commands"), list) else []
        items.append(
            attention_queue_item(
                items,
                str(change.get("change_type") or "change_tracking"),
                "核对最新变化",
                change.get("summary"),
                first_digest_read_command(commands, "market-intel agent briefing --json"),
                "read_only",
                "已确认变化集中在热点、观察项、持仓复核还是数据质量。",
                related_symbols=attention_change_symbols(change),
                evidence=attention_change_evidence(change),
                result_index=result_index,
                context_index=context_index,
                archive_prerequisite=archive_prerequisite,
            )
        )

    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    for holding in holdings[:2]:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        items.append(
            attention_queue_item(
                items,
                "holding_review",
                "%s %s" % (holding.get("symbol"), holding.get("name") or ""),
                holding.get("primary_question") or dashboard.get("summary"),
                holding.get("primary_json_command") or holding.get("primary_command"),
                "read_only",
                "已读取单票持仓复核，记录行情、热点、暴露和还要验证的问题。",
                related_symbols=[holding.get("symbol")],
                evidence=attention_holding_evidence(holding),
                result_index=result_index,
                context_index=context_index,
                archive_prerequisite=archive_prerequisite,
            )
        )

    risk = first_attention_risk(digest.get("risk_watch", []))
    if risk:
        commands = risk.get("commands", []) if isinstance(risk.get("commands"), list) else []
        items.append(
            attention_queue_item(
                items,
                "risk_review",
                str(risk.get("label") or "风险复核"),
                risk.get("review_question") or "核对该风险是否影响组合和重点持仓。",
                first_digest_read_command(commands, "market-intel daily --runtime --json"),
                "read_only",
                "已确认风险证据、涉及标的和是否需要写入复盘笔记。",
                related_symbols=risk.get("affected_symbols", []) if isinstance(risk.get("affected_symbols"), list) else [],
                evidence=risk.get("evidence", []) if isinstance(risk.get("evidence"), list) else [],
                result_index=result_index,
                context_index=context_index,
                archive_prerequisite=archive_prerequisite,
            )
        )

    for item in manual_followups[:2]:
        if not isinstance(item, dict):
            continue
        items.append(
            attention_queue_item(
                items,
                "manual_followup",
                "人工确认后留档",
                item.get("reason") or "写入类命令需要人工确认。",
                item.get("json_command") or item.get("command"),
                item.get("state_effect") or "manual",
                item.get("done_when") or "人工确认后执行并检查返回结果。",
                requires_manual=True,
                requires_prior_command=item.get("requires_prior_command"),
                result_index=result_index,
                context_index=context_index,
                archive_prerequisite=archive_prerequisite,
            )
        )

    return {
        "available": bool(items),
        "summary": attention_queue_summary(items),
        "items": items[:8],
        "write_policy": "队列只整理关注顺序；agent run 不自动执行写入类命令。",
    }


def attention_queue_item(
    items: List[Dict[str, object]],
    item_type: str,
    title: object,
    reason: object,
    command: object,
    state_effect: object,
    done_when: object,
    related_symbols: Optional[List[object]] = None,
    evidence: Optional[List[object]] = None,
    requires_manual: bool = False,
    requires_prior_command: object = None,
    result_index: Optional[Dict[str, Dict[str, object]]] = None,
    context_index: Optional[Dict[str, Dict[str, object]]] = None,
    archive_prerequisite: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    command_text = str(command or "")
    json_command = digest_json_variant(command_text) if command_text else ""
    linked_result = attention_linked_result(command_text, json_command, result_index or {})
    linked_context = attention_linked_result(command_text, json_command, context_index or {})
    return {
        "rank": len(items) + 1,
        "item_type": item_type,
        "title": str(title or item_type),
        "reason": str(reason or ""),
        "command": command_text,
        "json_command": json_command,
        "state_effect": state_effect,
        "runnable": bool(command_text) and not requires_manual and digest_command_is_read_only(command_text),
        "requires_manual": requires_manual,
        "requires_prior_command": requires_prior_command,
        "already_read": bool(linked_result),
        "linked_result": linked_result,
        "linked_context": linked_context,
        "related_symbols": dedupe_queue_texts(related_symbols or [])[:6],
        "evidence": dedupe_queue_texts(evidence or [])[:5],
        "journal_note": attention_journal_note(
            item_type,
            title,
            reason,
            related_symbols or [],
            evidence or [],
            archive_prerequisite or {},
            requires_manual,
        ),
        "done_when": str(done_when or ""),
    }


def attention_queue_summary(items: List[Dict[str, object]]) -> str:
    runnable = sum(1 for item in items if item.get("runnable"))
    manual = sum(1 for item in items if item.get("requires_manual"))
    read = sum(1 for item in items if item.get("already_read"))
    return "关注项 %s 个，其中已读 %s 个，可只读执行 %s 个，需人工确认 %s 个。" % (len(items), read, runnable, manual)


def attention_journal_note(
    item_type: str,
    title: object,
    reason: object,
    related_symbols: List[object],
    evidence: List[object],
    archive_prerequisite: Dict[str, object],
    requires_manual: bool,
) -> Dict[str, object]:
    section = attention_note_section(item_type)
    if item_type == "manual_followup":
        return {
            "available": False,
            "section": section,
            "reason": "该项本身是人工写入或留档步骤，不再生成二次记录命令。",
            "archive_prerequisite": archive_prerequisite,
            "run_after": archive_prerequisite.get("archive_command"),
        }
    draft = attention_note_draft(item_type, title, reason, related_symbols, evidence)
    return {
        "available": bool(draft),
        "section": section,
        "draft_text": draft,
        "note_command_template": "market-intel journal note --section %s --text '<填写复核结论>'" % section,
        "prefilled_note_command": prefilled_journal_note_command(section, draft) if draft else "",
        "archive_prerequisite": archive_prerequisite,
        "run_after": archive_prerequisite.get("archive_command"),
        "write_policy": "仅生成记录模板，不自动写入 journal。",
        "requires_manual": requires_manual,
    }


def attention_note_section(item_type: str) -> str:
    if item_type == "data_repair":
        return "data_quality"
    if item_type in {"current_vs_latest", "history_transition", "change_tracking"}:
        return "current_change"
    if item_type == "risk_review":
        return "portfolio_exposure"
    if item_type == "holding_review":
        return "security_review"
    return "general"


def attention_note_draft(
    item_type: str,
    title: object,
    reason: object,
    related_symbols: List[object],
    evidence: List[object],
) -> str:
    symbol_text = "、".join(str(symbol) for symbol in related_symbols[:4] if symbol)
    evidence_text = "；".join(str(item) for item in evidence[:3] if item)
    title_text = str(title or "")
    reason_text = strip_sentence_end(reason)
    if item_type == "data_repair":
        return ensure_sentence("数据问题复核：%s；涉及 %s；证据 %s" % (reason_text or title_text, symbol_text or "暂无 symbol", evidence_text or "暂无"))
    if item_type in {"current_vs_latest", "history_transition", "change_tracking"}:
        return ensure_sentence("变化复核：%s；涉及 %s；证据 %s" % (reason_text or title_text, symbol_text or "暂无 symbol", evidence_text or "暂无"))
    if item_type == "risk_review":
        return ensure_sentence("组合风险复核：%s；涉及 %s；证据 %s" % (reason_text or title_text, symbol_text or "暂无 symbol", evidence_text or "暂无"))
    if item_type == "holding_review":
        return ensure_sentence("单票复核：%s；结论待确认：%s；证据 %s" % (title_text, reason_text or "暂无", evidence_text or "暂无"))
    return ensure_sentence("%s：%s" % (title_text or item_type, reason_text))


def attention_result_index(results: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    index: Dict[str, Dict[str, object]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        compact = {
            "run_rank": result.get("run_rank"),
            "payload_command": result.get("payload_command"),
            "ok": bool(result.get("ok")),
            "json_command": result.get("json_command"),
            "summary": result.get("summary"),
            "observations": list(result.get("observations", []))[:4] if isinstance(result.get("observations"), list) else [],
        }
        for key in attention_result_keys(result):
            index.setdefault(key, compact)
    return index


def attention_context_index(digest: Dict[str, object], source_briefing: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    index: Dict[str, Dict[str, object]] = {}
    if source_briefing:
        compact = {
            "source": "source_briefing",
            "payload_command": source_briefing.get("payload_command"),
            "ok": bool(source_briefing.get("ok")),
            "json_command": source_briefing.get("command"),
            "summary": source_briefing.get("summary"),
            "observations": list(source_briefing.get("observations", []))[:4] if isinstance(source_briefing.get("observations"), list) else [],
        }
        index["market-intel agent briefing --json"] = compact
        index["agent.briefing"] = compact

    data_quality = digest.get("data_quality", {}) if isinstance(digest.get("data_quality"), dict) else {}
    if data_quality:
        compact = {
            "source": "review_digest.data_quality",
            "payload_command": "daily.validation",
            "ok": bool(data_quality.get("ok")),
            "json_command": "market-intel validate runtime --json",
            "summary": data_quality.get("summary"),
            "observations": [str(issue.get("code")) for issue in data_quality.get("warnings", [])[:4] if isinstance(issue, dict)]
            if isinstance(data_quality.get("warnings"), list)
            else [],
        }
        index["market-intel validate runtime --json"] = compact
        index["validate.runtime"] = compact

    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    for holding in holdings:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        symbol = str(holding.get("symbol"))
        compact = {
            "source": "review_digest.holding_dashboard",
            "payload_command": "holding_dashboard",
            "ok": True,
            "json_command": holding.get("primary_json_command"),
            "summary": holding.get("primary_question") or dashboard.get("summary"),
            "observations": attention_holding_evidence(holding)[:4],
        }
        command = str(holding.get("primary_json_command") or "")
        if command:
            index[command] = compact
        index["portfolio.explain:%s" % symbol] = compact

    change = attention_active_change(digest.get("change_tracking", {}))
    if change:
        compact = {
            "source": "review_digest.change_tracking",
            "payload_command": change.get("change_type"),
            "ok": bool(change.get("available")),
            "json_command": first_digest_read_command(change.get("commands", []) if isinstance(change.get("commands"), list) else [], "market-intel agent briefing --json"),
            "summary": change.get("summary"),
            "observations": attention_change_evidence(change)[:4],
        }
        command = str(compact.get("json_command") or "")
        if command:
            index[command] = compact
        if change.get("change_type"):
            index[str(change.get("change_type"))] = compact

    return index


def attention_result_keys(result: Dict[str, object]) -> List[str]:
    keys = []
    for command_key in ("json_command", "command"):
        command = str(result.get(command_key) or "")
        if not command:
            continue
        keys.append(command)
        keys.append(digest_json_variant(command))
        keys.append(command.replace(" --json", " --text"))
        parsed = attention_command_signature(command)
        if parsed:
            keys.append(parsed)
    payload = result.get("payload_command")
    if payload:
        keys.append(str(payload))
    return dedupe_queue_texts(keys)


def attention_linked_result(
    command: str,
    json_command: str,
    index: Dict[str, Dict[str, object]],
) -> Optional[Dict[str, object]]:
    candidates = [json_command, command, command.replace(" --json", " --text"), attention_command_signature(command), attention_command_signature(json_command)]
    for key in candidates:
        if key and key in index:
            return index[key]
    return None


def attention_command_signature(command: object) -> str:
    text = str(command or "")
    try:
        tokens = shlex.split(text)
    except ValueError:
        return ""
    if tokens and tokens[0] == "market-intel":
        tokens = tokens[1:]
    if not tokens:
        return ""
    resource = tokens[0]
    sub = tokens[1] if len(tokens) > 1 else ""
    if resource == "portfolio" and sub == "explain":
        symbol = first_positional(tokens[2:]) or ""
        return "portfolio.explain:%s" % symbol
    if resource == "pool" and sub == "explain":
        symbol = first_positional(tokens[2:]) or ""
        return "pool.explain:%s" % symbol
    if resource == "portfolio" and sub == "review":
        return "portfolio.review"
    if resource == "validate" and sub == "runtime":
        return "validate.runtime"
    if resource == "daily":
        return "daily"
    if resource == "watchlist":
        return "watchlist"
    if resource == "map":
        return "map"
    if resource == "journal" and sub:
        return "journal.%s" % sub
    return ".".join(token for token in (resource, sub) if token)


def attention_active_change(value: object) -> Dict[str, object]:
    tracking = value if isinstance(value, dict) else {}
    history = tracking.get("history_transition", {}) if isinstance(tracking.get("history_transition"), dict) else {}
    current = tracking.get("current_vs_latest", {}) if isinstance(tracking.get("current_vs_latest"), dict) else {}
    if history.get("has_delta"):
        return history
    if current.get("has_delta"):
        return current
    return {}


def attention_change_symbols(change: Dict[str, object]) -> List[object]:
    watchlist = change.get("watchlist", {}) if isinstance(change.get("watchlist"), dict) else {}
    portfolio = change.get("portfolio_review", {}) if isinstance(change.get("portfolio_review"), dict) else {}
    values: List[object] = []
    for key in ("added_symbols", "removed_symbols", "changed_symbols"):
        if isinstance(watchlist.get(key), list):
            values.extend(watchlist.get(key, []))
    if isinstance(portfolio.get("changed_symbols"), list):
        values.extend(portfolio.get("changed_symbols", []))
    return dedupe_queue_texts(values)[:6]


def attention_change_evidence(change: Dict[str, object]) -> List[object]:
    risk = change.get("risk_flags", {}) if isinstance(change.get("risk_flags"), dict) else {}
    watchlist = change.get("watchlist", {}) if isinstance(change.get("watchlist"), dict) else {}
    portfolio = change.get("portfolio_review", {}) if isinstance(change.get("portfolio_review"), dict) else {}
    hotspots = change.get("hotspots", {}) if isinstance(change.get("hotspots"), dict) else {}
    validation = change.get("validation", {}) if isinstance(change.get("validation"), dict) else {}
    evidence = [
        "风险 +%s/-%s" % (risk.get("added_count", 0), risk.get("removed_count", 0)),
        "观察 +%s/-%s/~%s" % (watchlist.get("added_count", 0), watchlist.get("removed_count", 0), watchlist.get("changed_count", 0)),
        "持仓复核变化 %s" % portfolio.get("changed_count", 0),
        "热点变化 %s" % hotspots.get("changed_count", 0),
        "告警 %+s，错误 %+s" % (validation.get("warning_delta", 0), validation.get("error_delta", 0)),
    ]
    return evidence


def attention_repair_symbols(repair: Dict[str, object]) -> List[object]:
    items = repair.get("items", []) if isinstance(repair.get("items"), list) else []
    return [item.get("symbol") for item in items if isinstance(item, dict) and item.get("symbol")]


def attention_repair_evidence(repair: Dict[str, object]) -> List[object]:
    groups = repair.get("groups", []) if isinstance(repair.get("groups"), list) else []
    return [
        "%s x%s" % (repair_type_label(group.get("repair_type")), group.get("count", 0))
        for group in groups[:4]
        if isinstance(group, dict)
    ]


def attention_holding_evidence(holding: Dict[str, object]) -> List[object]:
    evidence = [
        "%s | 分 %s" % (holding.get("priority"), holding.get("review_score")),
        "行情 %s" % ("有" if holding.get("has_quote") else "缺"),
        "热点 %s" % (holding.get("hotspot", {}).get("chain") if isinstance(holding.get("hotspot"), dict) else "无"),
    ]
    risks = holding.get("risk_flags", []) if isinstance(holding.get("risk_flags"), list) else []
    if risks:
        evidence.append("风险 %s" % "、".join(str(risk) for risk in risks[:3]))
    overlaps = holding.get("overlap_groups", []) if isinstance(holding.get("overlap_groups"), list) else []
    if overlaps:
        evidence.append("主题 %s" % "、".join(str(group) for group in overlaps[:3]))
    return evidence


def first_attention_risk(value: object) -> Optional[Dict[str, object]]:
    risks = value if isinstance(value, list) else []
    for risk in risks:
        if isinstance(risk, dict):
            return risk
    return None


def agent_run_digest_followup_watch(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    archive_prerequisite = journal_draft_archive_prerequisite(manual_followups)
    items: List[Dict[str, object]] = []
    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    if repair.get("available"):
        items.append(
            followup_watch_item(
                items,
                "data_quality",
                "补齐数据后再复核",
                repair.get("summary"),
                attention_repair_symbols(repair),
                repair.get("commands", []) if isinstance(repair.get("commands"), list) else [],
                "下次先确认数据错误/告警是否减少，再解读持仓和热点。",
                archive_prerequisite,
            )
        )

    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    changed = dashboard.get("changed_holdings", []) if isinstance(dashboard.get("changed_holdings"), list) else []
    if changed:
        changed_symbols = {item.get("symbol") for item in changed if isinstance(item, dict) and item.get("symbol")}
        top_holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
        items.append(
            followup_watch_item(
                items,
                "changed_holdings",
                "跟踪变化持仓",
                "相对留档发生变化的持仓需要下次优先复核。",
                list(changed_symbols),
                [item.get("primary_json_command") for item in top_holdings if isinstance(item, dict) and item.get("symbol") in changed_symbols],
                "下次看这些持仓的变化原因是否延续、收敛或转向。",
                archive_prerequisite,
            )
        )
    else:
        high_holdings = [
            item
            for item in dashboard.get("top_holdings", [])
            if isinstance(item, dict) and item.get("priority") == "high_review"
        ] if isinstance(dashboard.get("top_holdings"), list) else []
        if high_holdings:
            items.append(
                followup_watch_item(
                    items,
                    "priority_holdings",
                    "复查重点持仓",
                    "当前重点复核持仓需要下次继续确认风险标签和热点上下文。",
                    [item.get("symbol") for item in high_holdings if item.get("symbol")],
                    [item.get("primary_json_command") for item in high_holdings if item.get("primary_json_command")],
                    "下次确认这些持仓的复核优先级、风险标签和热点关联是否变化。",
                    archive_prerequisite,
                )
            )

    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    changed_groups = [group for group in pressure.get("groups", []) if isinstance(group, dict) and safe_int(group.get("changed_member_count")) > 0] if isinstance(pressure.get("groups"), list) else []
    if changed_groups:
        group_names = [group.get("group") for group in changed_groups if group.get("group")]
        symbols = []
        for group in changed_groups:
            members = group.get("changed_members", []) if isinstance(group.get("changed_members"), list) else []
            symbols.extend(member.get("symbol") for member in members if isinstance(member, dict) and member.get("symbol"))
        items.append(
            followup_watch_item(
                items,
                "portfolio_pressure",
                "复查同组暴露",
                "变化成员集中在 %s。" % ("、".join(str(name) for name in group_names[:4]) or "重复暴露组"),
                symbols,
                [group.get("primary_json_command") for group in changed_groups if group.get("primary_json_command")],
                "下次确认同组持仓是否仍由同一链路、主题或风险驱动。",
                archive_prerequisite,
            )
        )
    else:
        groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
        if groups:
            group_names = [group.get("group") for group in groups if isinstance(group, dict) and group.get("group")]
            symbols = []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
                symbols.extend(holding.get("symbol") for holding in holdings if isinstance(holding, dict) and holding.get("symbol"))
            items.append(
                followup_watch_item(
                    items,
                    "portfolio_pressure",
                    "复查集中暴露",
                    "组合存在重复链路/主题：%s。" % ("、".join(str(name) for name in group_names[:4]) or "重复暴露"),
                    symbols,
                    ["market-intel portfolio review --runtime --json"],
                    "下次确认这些重复暴露是否仍受同一叙事和同一风险驱动。",
                    archive_prerequisite,
                )
            )

    market = digest.get("market_structure", {}) if isinstance(digest.get("market_structure"), dict) else {}
    chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
    if chains:
        top = chains[0] if isinstance(chains[0], dict) else {}
        leaders = top.get("leaders", []) if isinstance(top.get("leaders"), list) else []
        items.append(
            followup_watch_item(
                items,
                "market_structure",
                "复查最强链路",
                market.get("summary") or "复查最强链路是否延续。",
                [leader.get("symbol") for leader in leaders if isinstance(leader, dict)],
                ["market-intel map --runtime --json", "market-intel brief --runtime --json"],
                "下次确认最强链路、活跃数量和持仓关联是否发生变化。",
                archive_prerequisite,
            )
        )

    return {
        "available": bool(items),
        "summary": followup_watch_summary(items),
        "items": items[:6],
        "write_policy": "只生成下次观察计划，不生成交易指令。",
    }


def followup_watch_item(
    items: List[Dict[str, object]],
    item_type: str,
    title: object,
    reason: object,
    symbols: List[object],
    commands: List[object],
    check_question: object,
    archive_prerequisite: Dict[str, object],
) -> Dict[str, object]:
    clean_symbols = dedupe_queue_texts(symbols)[:8]
    clean_commands = dedupe_queue_texts(commands)[:5]
    command = first_digest_read_command(clean_commands, "market-intel agent run --json")
    note_text = ensure_sentence("%s：%s；观察标的 %s；下次问题：%s" % (
        title,
        strip_sentence_end(reason) or "暂无摘要",
        "、".join(clean_symbols[:6]) or "暂无",
        strip_sentence_end(check_question),
    ))
    section = (
        "current_change"
        if item_type in {"changed_holdings", "market_structure"}
        else "security_review"
        if item_type == "priority_holdings"
        else "portfolio_exposure"
        if item_type == "portfolio_pressure"
        else "data_quality"
    )
    return {
        "rank": len(items) + 1,
        "item_type": item_type,
        "title": str(title or item_type),
        "reason": str(reason or ""),
        "symbols": clean_symbols,
        "check_question": str(check_question or ""),
        "json_command": digest_json_variant(command),
        "commands": clean_commands,
        "journal_note": {
            "available": True,
            "section": section,
            "draft_text": note_text,
            "prefilled_note_command": prefilled_journal_note_command(section, note_text),
            "run_after": archive_prerequisite.get("archive_command"),
            "archive_prerequisite": archive_prerequisite,
            "write_policy": "仅生成记录模板，不自动写入 journal。",
        },
    }


def followup_watch_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return "暂无下次观察计划。"
    symbols = dedupe_queue_texts([symbol for item in items for symbol in item.get("symbols", []) if isinstance(item, dict)])
    return "下次观察项 %s 个，涉及标的 %s 个。" % (len(items), len(symbols))


def agent_run_digest_review_completion(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    checks = [
        review_completion_check_data_quality(digest),
        review_completion_check_evidence(digest),
        review_completion_check_hypothesis(digest),
        review_completion_check_attention(digest),
        review_completion_check_journal(digest, manual_followups),
        review_completion_check_followup(digest),
    ]
    blocking = sum(1 for item in checks if item.get("status") == "blocked")
    manual = sum(1 for item in checks if item.get("status") == "manual_required")
    pending = sum(1 for item in checks if item.get("status") == "pending")
    ready = blocking == 0 and pending == 0
    state = "ready_for_manual_record" if ready and manual else "ready_for_review_note" if ready else "needs_more_review"
    return {
        "available": True,
        "completion_state": state,
        "summary": review_completion_summary(checks, state),
        "ready_for_journal_note": ready,
        "blocking_count": blocking,
        "manual_required_count": manual,
        "pending_count": pending,
        "checks": checks,
        "write_policy": "只整理复盘收尾状态，不自动写入 journal。",
    }


def review_completion_check_data_quality(digest: Dict[str, object]) -> Dict[str, object]:
    data_quality = digest.get("data_quality", {}) if isinstance(digest.get("data_quality"), dict) else {}
    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    errors = safe_int(data_quality.get("error_count"))
    warnings = safe_int(data_quality.get("warning_count"))
    if errors:
        status = "blocked"
        reason = "仍有数据错误 %s 个，复盘结论需要暂缓。" % errors
    elif warnings:
        status = "manual_required"
        reason = "仍有数据告警 %s 个，需要人工确认哪些结论要降权解读。" % warnings
    else:
        status = "done"
        reason = "数据质量已通过当前校验。"
    commands = repair.get("commands", []) if isinstance(repair.get("commands"), list) else []
    return review_completion_check(
        "data_quality",
        "数据质量",
        status,
        reason,
        first_digest_read_command(commands, "market-intel validate runtime --json"),
        "数据错误/告警已处理，或已记录受影响的 symbol 与字段。",
    )


def review_completion_check_evidence(digest: Dict[str, object]) -> Dict[str, object]:
    evidence = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    items = evidence.get("items", []) if isinstance(evidence.get("items"), list) else []
    blocked = [item for item in items if isinstance(item, dict) and item.get("coverage_status") == "blocked_by_data"]
    pending = [item for item in items if isinstance(item, dict) and item.get("coverage_status") in {"needs_read", "needs_more_context"}]
    if blocked:
        status = "blocked"
        reason = "证据清单里有 %s 项受数据阻塞。" % len(blocked)
    elif pending:
        status = "pending"
        reason = "证据清单里有 %s 项还需要读取或补上下文。" % len(pending)
    elif items:
        status = "done"
        reason = "证据清单已有覆盖状态。"
    else:
        status = "pending"
        reason = "暂无证据清单，需要先生成可读证据。"
    first = pending[0] if pending else blocked[0] if blocked else first_dict(items)
    return review_completion_check(
        "evidence",
        "证据充分性",
        status,
        reason,
        first.get("json_command") if isinstance(first, dict) else "market-intel agent run --json",
        "已有证据、待补证据和覆盖状态都已确认。",
    )


def review_completion_check_hypothesis(digest: Dict[str, object]) -> Dict[str, object]:
    board = digest.get("hypothesis_board", {}) if isinstance(digest.get("hypothesis_board"), dict) else {}
    items = board.get("items", []) if isinstance(board.get("items"), list) else []
    weak = [item for item in items if isinstance(item, dict) and item.get("weak_points")]
    if not items:
        status = "pending"
        reason = "暂无观察假设，需要先把证据转成可验证问题。"
    elif weak:
        status = "manual_required"
        reason = "观察假设里有 %s 项仍有薄弱点，需要人工确认是否接受。" % len(weak)
    else:
        status = "done"
        reason = "观察假设都有支持证据、验证步骤和失效信号。"
    first = weak[0] if weak else first_dict(items)
    return review_completion_check(
        "hypothesis",
        "观察假设",
        status,
        reason,
        first.get("json_command") if isinstance(first, dict) else "market-intel agent run --json",
        "已记录假设、支持证据、薄弱点、验证步骤和失效信号。",
    )


def review_completion_check_attention(digest: Dict[str, object]) -> Dict[str, object]:
    attention = digest.get("attention_queue", {}) if isinstance(digest.get("attention_queue"), dict) else {}
    items = attention.get("items", []) if isinstance(attention.get("items"), list) else []
    runnable_unread = [
        item
        for item in items
        if isinstance(item, dict) and item.get("runnable") and not item.get("already_read")
    ]
    manual_items = [
        item
        for item in items
        if isinstance(item, dict) and item.get("requires_manual")
    ]
    if runnable_unread:
        status = "pending"
        reason = "关注队列里还有 %s 个可只读执行但未读取的项目。" % len(runnable_unread)
    elif manual_items:
        status = "manual_required"
        reason = "关注队列里有 %s 个项目需要人工确认。" % len(manual_items)
    elif items:
        status = "done"
        reason = "关注队列已无未读只读项目。"
    else:
        status = "pending"
        reason = "暂无关注队列。"
    first = runnable_unread[0] if runnable_unread else manual_items[0] if manual_items else first_dict(items)
    return review_completion_check(
        "attention_queue",
        "关注队列",
        status,
        reason,
        first.get("json_command") if isinstance(first, dict) else "market-intel agent run --json",
        "只读关注项已读完，人工项已明确保留给用户。",
    )


def review_completion_check_journal(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    draft = digest.get("journal_draft", {}) if isinstance(digest.get("journal_draft"), dict) else {}
    archive = draft.get("archive_prerequisite", {}) if isinstance(draft.get("archive_prerequisite"), dict) else journal_draft_archive_prerequisite(manual_followups)
    sections = draft.get("sections", []) if isinstance(draft.get("sections"), list) else []
    status = "manual_required" if sections else "pending"
    reason = "复盘草稿已生成，保存日报和写入笔记需要人工确认。" if sections else "复盘草稿尚未生成。"
    return review_completion_check(
        "journal_draft",
        "留档草稿",
        status,
        reason,
        archive.get("archive_command") or "market-intel journal save --runtime --json",
        "日报已保存，复盘笔记已按草稿人工确认后记录。",
    )


def review_completion_check_followup(digest: Dict[str, object]) -> Dict[str, object]:
    followup = digest.get("followup_watch", {}) if isinstance(digest.get("followup_watch"), dict) else {}
    items = followup.get("items", []) if isinstance(followup.get("items"), list) else []
    status = "done" if items else "pending"
    reason = "下次观察计划已生成 %s 项。" % len(items) if items else "暂无下次观察计划。"
    first = first_dict(items)
    return review_completion_check(
        "followup_watch",
        "下次观察",
        status,
        reason,
        first.get("json_command") if first else "market-intel agent run --json",
        "下次观察标的、核对问题、只读命令和记录模板已确认。",
    )


def review_completion_check(
    check_id: str,
    title: str,
    status: str,
    reason: object,
    command: object,
    done_when: object,
) -> Dict[str, object]:
    command_text = str(command or "")
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "reason": str(reason or ""),
        "json_command": digest_json_variant(command_text) if command_text else "",
        "done_when": str(done_when or ""),
    }


def review_completion_summary(checks: List[Dict[str, object]], state: str) -> str:
    blocked = sum(1 for item in checks if item.get("status") == "blocked")
    manual = sum(1 for item in checks if item.get("status") == "manual_required")
    pending = sum(1 for item in checks if item.get("status") == "pending")
    done = sum(1 for item in checks if item.get("status") == "done")
    return "复盘收尾状态 %s；完成 %s 项，待读 %s 项，需人工 %s 项，阻塞 %s 项。" % (state, done, pending, manual, blocked)


def agent_run_digest_review_handoff(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    next_read = review_handoff_next_read(digest, completion)
    manual_items = review_handoff_manual_items(digest, manual_followups)
    record_templates = review_handoff_record_templates(digest)
    watch_items = review_handoff_watch_items(digest)
    state = review_handoff_state(completion, next_read, manual_items)
    return {
        "available": True,
        "handoff_state": state,
        "summary": review_handoff_summary(state, next_read, manual_items, record_templates, watch_items),
        "resume_prompt": review_handoff_resume_prompt(digest, completion, next_read, manual_items),
        "command_chain": review_handoff_command_chain(next_read, manual_items),
        "next_read": next_read,
        "manual_items": manual_items,
        "record_templates": record_templates,
        "watch_items": watch_items,
        "write_policy": "只生成交接信息，不自动执行命令或写入 journal。",
    }


def review_handoff_next_read(
    digest: Dict[str, object],
    completion: Dict[str, object],
) -> List[Dict[str, object]]:
    rows = []
    seen_commands = set()
    checks = completion.get("checks", []) if isinstance(completion.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict) or check.get("status") not in {"blocked", "pending"}:
            continue
        command = str(check.get("json_command") or "")
        command_key = digest_json_variant(command)
        if not command_key or command_key in seen_commands:
            continue
        seen_commands.add(command_key)
        rows.append(
            review_handoff_command_item(
                len(rows) + 1,
                check.get("check_id"),
                check.get("title"),
                check.get("reason"),
                command,
                check.get("done_when"),
            )
        )
    if rows:
        add_candidate_queue_next_read(digest, rows, seen_commands)
        return rows[:5]

    add_candidate_queue_next_read(digest, rows, seen_commands)

    attention = digest.get("attention_queue", {}) if isinstance(digest.get("attention_queue"), dict) else {}
    items = attention.get("items", []) if isinstance(attention.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict) or not item.get("runnable") or item.get("already_read"):
            continue
        command = str(item.get("json_command") or item.get("command") or "")
        command_key = digest_json_variant(command)
        if not command_key or command_key in seen_commands:
            continue
        seen_commands.add(command_key)
        rows.append(
            review_handoff_command_item(
                len(rows) + 1,
                item.get("item_type"),
                item.get("title"),
                item.get("reason"),
                command,
                item.get("done_when"),
            )
        )
    return rows[:5]


def add_candidate_queue_next_read(
    digest: Dict[str, object],
    rows: List[Dict[str, object]],
    seen_commands: set,
) -> None:
    market_scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    item = dashboard_candidate_queue_next_item(market_scan)
    if not item:
        return
    command = str(item.get("next_command") or "")
    if not command and item.get("symbol"):
        command = "market-intel pool explain %s --runtime --json" % item.get("symbol")
    command_key = digest_json_variant(command)
    if not command_key or command_key in seen_commands:
        return
    seen_commands.add(command_key)
    rows.append(
        review_handoff_command_item(
            len(rows) + 1,
            "candidate_queue",
            "%s %s" % (item.get("symbol"), item.get("name") or ""),
            item.get("reason") or "读取候选队列首项。",
            command,
            "已确认该候选的板块共振、排序因子、覆盖状态和下一步核对项。",
        )
    )


def review_handoff_command_item(
    rank: int,
    source: object,
    title: object,
    reason: object,
    command: object,
    done_when: object,
) -> Dict[str, object]:
    command_text = digest_json_variant(command)
    return {
        "rank": rank,
        "source": str(source or ""),
        "title": str(title or source or "继续读取"),
        "reason": str(reason or ""),
        "json_command": command_text,
        "runnable": bool(command_text) and digest_command_is_read_only(command_text),
        "done_when": str(done_when or ""),
    }


def review_handoff_command_chain(
    next_read: List[Dict[str, object]],
    manual_items: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    rows = []
    seen = set()

    def add_command(item: Dict[str, object], command: object, step_type: str, title: object, done_when: object) -> None:
        command_text = digest_json_variant(command)
        if not command_text or command_text in seen:
            return
        seen.add(command_text)
        requires_raw = item.get("requires_manual")
        requires_manual = bool(requires_raw) if requires_raw is not None else step_type == "manual"
        rows.append(
            {
                "rank": len(rows) + 1,
                "step_type": step_type,
                "source": item.get("source"),
                "title": title,
                "json_command": command_text,
                "runnable": step_type == "read" and not requires_manual and digest_command_is_read_only(command_text),
                "requires_manual": requires_manual,
                "done_when": done_when,
            }
        )

    for source_items, step_type in ((next_read, "read"), (manual_items, "manual")):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            workflow = item.get("workflow_steps", []) if isinstance(item.get("workflow_steps"), list) else []
            if workflow:
                for step in workflow:
                    if not isinstance(step, dict):
                        continue
                    workflow_type = str(step.get("step_type") or step_type)
                    if workflow_type not in {"read", "manual"}:
                        workflow_type = step_type
                    workflow_item = dict(item)
                    if "requires_manual" in step:
                        workflow_item["requires_manual"] = step.get("requires_manual")
                    elif workflow_type == "read":
                        workflow_item["requires_manual"] = False
                    add_command(
                        workflow_item,
                        step.get("json_command"),
                        workflow_type,
                        step.get("title") or item.get("title"),
                        step.get("done_when") or item.get("done_when"),
                    )
                continue
            add_command(item, item.get("json_command"), step_type, item.get("title"), item.get("done_when"))
    return rows[:12]


def review_handoff_manual_items(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    rows = []
    seen = set()
    for item in foundation_research_manual_items(digest):
        command = str(item.get("json_command") or "")
        key = digest_json_variant(command) or str(item.get("source") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)

    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    checks = completion.get("checks", []) if isinstance(completion.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict) or check.get("status") != "manual_required":
            continue
        command = str(check.get("json_command") or "")
        key = digest_json_variant(command) or str(check.get("check_id") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "rank": len(rows) + 1,
                "source": check.get("check_id"),
                "title": check.get("title"),
                "reason": check.get("reason"),
                "json_command": command,
                "requires_manual": True,
                "done_when": check.get("done_when"),
            }
        )

    for item in manual_followups:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or item.get("command") or "")
        key = digest_json_variant(command) or str(item.get("state_effect") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "rank": len(rows) + 1,
                "source": item.get("state_effect") or "manual_followup",
                "title": "人工后续",
                "reason": item.get("reason"),
                "json_command": command,
                "requires_manual": True,
                "done_when": item.get("done_when"),
            }
        )
    return rows[:6]


def foundation_research_manual_items(digest: Dict[str, object]) -> List[Dict[str, object]]:
    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    foundation = [
        item
        for item in holdings
        if isinstance(item, dict) and item.get("coverage_state") == "foundation" and item.get("symbol")
    ]
    if not foundation:
        return []
    symbols = "、".join(str(item.get("symbol")) for item in foundation[:4])
    workflow = foundation_research_commands(symbols)
    first_command = next((str(step.get("json_command")) for step in workflow if isinstance(step, dict) and step.get("json_command")), "")
    return [
        {
            "rank": 1,
            "source": "foundation_research",
            "title": "补齐 foundation 研究证据",
            "reason": "foundation 持仓需要补 reviewed research_notes：%s。" % symbols,
            "json_command": first_command,
            "requires_manual": True,
            "done_when": "已补齐核心逻辑、关键证据和证伪风险；dry-run 通过；runtime 导入后 coverage 确认为 confirmed。",
            "workflow_steps": workflow,
        }
    ]


def review_handoff_record_templates(digest: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    seen = set()
    for source_key, item_key in (
        ("journal_draft", "sections"),
        ("attention_queue", "items"),
        ("hypothesis_board", "items"),
        ("followup_watch", "items"),
    ):
        source = digest.get(source_key, {}) if isinstance(digest.get(source_key), dict) else {}
        values = source.get(item_key, []) if isinstance(source.get(item_key), list) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
            command = note.get("prefilled_note_command") or item.get("prefilled_note_command")
            section = note.get("section") or item.get("id")
            if not command:
                continue
            key = str(command)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "source": source_key,
                    "section": section,
                    "title": item.get("title") or item.get("hypothesis") or item.get("id"),
                    "prefilled_note_command": command,
                    "run_after": note.get("run_after") or item.get("run_after"),
                    "requires_manual": True,
                }
            )
            if len(rows) >= 6:
                return rows
    return rows


def review_handoff_watch_items(digest: Dict[str, object]) -> List[Dict[str, object]]:
    followup = digest.get("followup_watch", {}) if isinstance(digest.get("followup_watch"), dict) else {}
    items = followup.get("items", []) if isinstance(followup.get("items"), list) else []
    rows = []
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": len(rows) + 1,
                "item_type": item.get("item_type"),
                "title": item.get("title"),
                "symbols": list(item.get("symbols", []))[:6] if isinstance(item.get("symbols"), list) else [],
                "check_question": item.get("check_question"),
                "json_command": item.get("json_command"),
            }
        )
    return rows


def review_handoff_state(
    completion: Dict[str, object],
    next_read: List[Dict[str, object]],
    manual_items: List[Dict[str, object]],
) -> str:
    if safe_int(completion.get("blocking_count")):
        return "blocked"
    if next_read:
        return "continue_reading"
    if manual_items:
        return "needs_manual"
    return "ready_to_close"


def review_handoff_summary(
    state: str,
    next_read: List[Dict[str, object]],
    manual_items: List[Dict[str, object]],
    record_templates: List[Dict[str, object]],
    watch_items: List[Dict[str, object]],
) -> str:
    return "交接状态 %s；待读 %s 项，需人工 %s 项，记录模板 %s 个，下次观察 %s 项。" % (
        state,
        len(next_read),
        len(manual_items),
        len(record_templates),
        len(watch_items),
    )


def review_handoff_resume_prompt(
    digest: Dict[str, object],
    completion: Dict[str, object],
    next_read: List[Dict[str, object]],
    manual_items: List[Dict[str, object]],
) -> str:
    headline = strip_sentence_end(digest.get("headline"))
    completion_summary = strip_sentence_end(completion.get("summary"))
    next_command = next_read[0].get("json_command") if next_read else ""
    if next_command:
        return ensure_sentence("接手复盘：%s；%s；先运行 %s" % (headline or "暂无摘要", completion_summary or "暂无收尾状态", next_command))
    if manual_items:
        return ensure_sentence("接手复盘：%s；%s；下一步人工确认 %s" % (headline or "暂无摘要", completion_summary or "暂无收尾状态", manual_items[0].get("title") or "留档"))
    return ensure_sentence("接手复盘：%s；%s；本轮只读复盘已可收尾" % (headline or "暂无摘要", completion_summary or "暂无收尾状态"))


def agent_run_digest_security_cards(
    digest: Dict[str, object],
    manual_followups: List[Dict[str, object]],
) -> Dict[str, object]:
    archive_prerequisite = journal_draft_archive_prerequisite(manual_followups)
    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    holdings = dashboard.get("top_holdings", []) if isinstance(dashboard.get("top_holdings"), list) else []
    workbench_by_symbol = {
        str(item.get("symbol")): item
        for item in digest.get("security_workbench", [])
        if isinstance(item, dict) and item.get("symbol")
    } if isinstance(digest.get("security_workbench"), list) else {}
    evidence_by_symbol = security_cards_group_by_symbol(digest.get("evidence_checklist", {}), "related_symbols")
    hypothesis_by_symbol = security_cards_group_by_symbol(digest.get("hypothesis_board", {}), "related_symbols")
    watch_by_symbol = security_cards_group_by_symbol(digest.get("followup_watch", {}), "symbols")
    handoff_commands = security_cards_handoff_commands(digest.get("review_handoff", {}))

    cards = []
    for holding in holdings[:6]:
        if not isinstance(holding, dict) or not holding.get("symbol"):
            continue
        symbol = str(holding.get("symbol"))
        workbench = workbench_by_symbol.get(symbol, {})
        evidence_items = evidence_by_symbol.get(symbol, [])
        hypothesis_items = hypothesis_by_symbol.get(symbol, [])
        watch_items = watch_by_symbol.get(symbol, [])
        cards.append(
            security_card_item(
                len(cards) + 1,
                holding,
                workbench,
                evidence_items,
                hypothesis_items,
                watch_items,
                handoff_commands.get(symbol, []),
                archive_prerequisite,
            )
        )
    return {
        "available": bool(cards),
        "summary": security_cards_summary(cards),
        "cards": cards,
        "write_policy": "只整理单票复核上下文，不生成交易指令。",
    }


def security_card_item(
    rank: int,
    holding: Dict[str, object],
    workbench: Dict[str, object],
    evidence_items: List[Dict[str, object]],
    hypothesis_items: List[Dict[str, object]],
    watch_items: List[Dict[str, object]],
    handoff_commands: List[str],
    archive_prerequisite: Dict[str, object],
) -> Dict[str, object]:
    symbol = str(holding.get("symbol") or "")
    coverage_state = str(holding.get("coverage_state") or "confirmed")
    coverage_state_reasons = (
        list(holding.get("coverage_state_reasons", []))
        if isinstance(holding.get("coverage_state_reasons"), list)
        else []
    )
    research = compact_digest_research_status(holding.get("research_status", {}))
    research_workflow = foundation_research_workflow(symbol, coverage_state)
    supporting = dedupe_queue_texts(
        list(holding.get("review_points", []) if isinstance(holding.get("review_points"), list) else [])
        + list(workbench.get("evidence", []) if isinstance(workbench.get("evidence"), list) else [])
        + [row for item in evidence_items for row in item.get("evidence", []) if isinstance(item, dict) and isinstance(item.get("evidence"), list)]
        + [row for item in hypothesis_items for row in item.get("supporting_evidence", []) if isinstance(item, dict) and isinstance(item.get("supporting_evidence"), list)]
        + (["研究证据 reviewed"] if research.get("confirmed") else [])
    )[:6]
    gaps = dedupe_queue_texts(
        [row for item in evidence_items for row in item.get("missing_evidence", []) if isinstance(item, dict) and isinstance(item.get("missing_evidence"), list)]
        + [row for item in hypothesis_items for row in item.get("weak_points", []) if isinstance(item, dict) and isinstance(item.get("weak_points"), list)]
        + evidence_holding_gaps(holding)
    )[:6]
    questions = dedupe_queue_texts(
        [holding.get("primary_question")]
        + list(workbench.get("questions", []) if isinstance(workbench.get("questions"), list) else [])
        + [item.get("check_question") for item in watch_items if isinstance(item, dict)]
    )[:5]
    primary_commands = [
        holding.get("primary_json_command") or holding.get("primary_command"),
        "market-intel pool explain %s --runtime --json" % symbol if symbol else None,
    ]
    commands = dedupe_queue_texts(
        primary_commands
        + handoff_commands
        + [step.get("json_command") for step in research_workflow if isinstance(step, dict)]
        + list(workbench.get("commands", []) if isinstance(workbench.get("commands"), list) else [])
        + [item.get("json_command") for item in evidence_items if isinstance(item, dict)]
        + [item.get("json_command") for item in hypothesis_items if isinstance(item, dict)]
        + [item.get("json_command") for item in watch_items if isinstance(item, dict)]
    )[:6]
    next_command = first_digest_read_command(commands, "market-intel portfolio explain %s --runtime --json" % symbol)
    note_text = ensure_sentence(
        "单票卡片：%s %s；优先级 %s；问题：%s；待补：%s"
        % (
            symbol,
            holding.get("name") or "",
            holding.get("priority") or "unknown",
            strip_sentence_end(first_text(questions)) or "暂无",
            "；".join(gaps[:3]) or "暂无",
        )
    )
    return {
        "rank": rank,
        "symbol": symbol,
        "name": holding.get("name"),
        "priority": holding.get("priority"),
        "review_score": holding.get("review_score"),
        "coverage_state": coverage_state,
        "coverage_state_reasons": [str(reason) for reason in coverage_state_reasons[:6] if reason],
        "research_status": research,
        "research_workflow": research_workflow,
        "change_priority": holding.get("change_priority"),
        "has_quote": bool(holding.get("has_quote")),
        "in_hotspot": bool(holding.get("in_hotspot")),
        "hotspot": holding.get("hotspot"),
        "quote": holding.get("quote"),
        "risk_flags": list(holding.get("risk_flags", []))[:6] if isinstance(holding.get("risk_flags"), list) else [],
        "exposure_groups": list(workbench.get("exposure_groups", []))[:4] if isinstance(workbench.get("exposure_groups"), list) else [],
        "overlap_groups": list(holding.get("overlap_groups", []))[:4] if isinstance(holding.get("overlap_groups"), list) else [],
        "change": holding.get("change") if isinstance(holding.get("change"), dict) else {},
        "supporting_evidence": supporting,
        "open_gaps": gaps,
        "questions": questions,
        "next_json_command": digest_json_variant(next_command),
        "commands": [digest_json_variant(command) for command in commands if command][:6],
        "watch_items": [
            {
                "title": item.get("title"),
                "check_question": item.get("check_question"),
                "json_command": item.get("json_command"),
            }
            for item in watch_items[:3]
            if isinstance(item, dict)
        ],
        "journal_note": {
            "available": True,
            "section": "security_review",
            "draft_text": note_text,
            "prefilled_note_command": prefilled_journal_note_command("security_review", note_text),
            "run_after": archive_prerequisite.get("archive_command"),
            "archive_prerequisite": archive_prerequisite,
            "write_policy": "仅生成记录模板，不自动写入 journal。",
        },
    }


def foundation_research_workflow(symbol: str, coverage_state: str) -> List[Dict[str, object]]:
    if coverage_state != "foundation":
        return []
    return foundation_research_commands(symbol)


def foundation_research_commands(symbol_text: str) -> List[Dict[str, object]]:
    return [
        {
            "rank": 1,
            "step_type": "manual",
            "title": "导出 research notes 待办",
            "json_command": "market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --json",
            "requires_manual": True,
            "reason": "foundation 持仓需要补 reviewed research_notes：%s。" % symbol_text,
            "done_when": "已生成可编辑的 research_notes.todo.csv。",
        },
        {
            "rank": 2,
            "step_type": "manual",
            "title": "补齐三项证据",
            "json_command": "",
            "requires_manual": True,
            "reason": "人工补齐核心逻辑、关键证据、证伪风险，并设置 status=reviewed。",
            "done_when": "已为 %s 补齐核心逻辑、关键证据、证伪风险，并设置 status=reviewed。" % symbol_text,
        },
        {
            "rank": 3,
            "step_type": "read",
            "title": "校验研究证据",
            "json_command": "market-intel import research data/runtime/research_notes.todo.csv --dry-run --json",
            "requires_manual": False,
            "reason": "导入前先校验 research_notes.todo.csv，不写 runtime。",
            "done_when": "dry-run 返回 ok=true 且 errors=[]。",
        },
        {
            "rank": 4,
            "step_type": "manual",
            "title": "导入研究证据",
            "json_command": "market-intel import research data/runtime/research_notes.todo.csv --runtime --json",
            "requires_manual": True,
            "reason": "dry-run 通过后导入 runtime research_notes。",
            "done_when": "已导入 reviewed research_notes。",
        },
        {
            "rank": 5,
            "step_type": "read",
            "title": "复跑 coverage 验证",
            "json_command": "market-intel pool coverage --runtime --json",
            "requires_manual": False,
            "reason": "确认 foundation 缺口已关闭。",
            "done_when": "foundation_matched_count 降为 0，相关标的 coverage_state=confirmed。",
        },
    ]


def security_cards_group_by_symbol(value: object, symbol_key: str) -> Dict[str, List[Dict[str, object]]]:
    data = value if isinstance(value, dict) else {}
    items = data.get("items") or data.get("cards") or []
    if not isinstance(items, list):
        return {}
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        symbols = item.get(symbol_key, []) if isinstance(item.get(symbol_key), list) else []
        for symbol in dedupe_queue_texts(symbols):
            grouped.setdefault(symbol, []).append(item)
    return grouped


def security_cards_handoff_commands(value: object) -> Dict[str, List[str]]:
    handoff = value if isinstance(value, dict) else {}
    rows = handoff.get("next_read", []) if isinstance(handoff.get("next_read"), list) else []
    grouped: Dict[str, List[str]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        command = str(item.get("json_command") or "")
        parsed = attention_command_signature(command)
        if parsed.startswith("portfolio.explain:"):
            symbol = parsed.split(":", 1)[1]
            grouped.setdefault(symbol, []).append(command)
    return grouped


def first_text(values: List[object]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def security_cards_summary(cards: List[Dict[str, object]]) -> str:
    if not cards:
        return "暂无单票复核卡片。"
    high = sum(1 for item in cards if item.get("priority") == "high_review")
    gaps = sum(1 for item in cards if item.get("open_gaps"))
    changed = sum(1 for item in cards if safe_int(item.get("change_priority")) > 0)
    return "单票复核卡片 %s 张，重点 %s 张，有待补证据 %s 张，变化持仓 %s 张。" % (len(cards), high, gaps, changed)


def security_workbench_reason(
    item: Dict[str, object],
    change: Dict[str, object],
    exposure_groups: List[Dict[str, object]],
) -> str:
    parts = ["优先分 %s" % item.get("priority_score")]
    risk_labels = item.get("risk_labels", []) if isinstance(item.get("risk_labels"), list) else []
    if risk_labels:
        parts.append("风险 %s" % "、".join(str(label) for label in risk_labels[:3]))
    change_reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
    if change_reasons:
        parts.append("变化 %s" % "、".join(str(reason) for reason in change_reasons[:3]))
    if exposure_groups:
        parts.append("重复暴露 %s 组" % len(exposure_groups))
    return "；".join(parts) + "。"


def security_change_context(symbol: str, change_tracking: Dict[str, object]) -> Dict[str, object]:
    history_transition = change_tracking.get("history_transition", {}) if isinstance(change_tracking.get("history_transition"), dict) else {}
    current_vs_latest = change_tracking.get("current_vs_latest", {}) if isinstance(change_tracking.get("current_vs_latest"), dict) else {}
    source = history_transition if history_transition.get("has_delta") else current_vs_latest
    if not isinstance(source, dict) or not source.get("available"):
        return {"available": False, "source": None, "reasons": []}
    reasons = security_change_reasons(symbol, source)
    return {
        "available": bool(reasons),
        "source": source.get("change_type"),
        "base_trade_date": source.get("base_trade_date"),
        "current_trade_date": source.get("current_trade_date"),
        "reasons": reasons,
        "top_chain_shift": source.get("hotspots", {}).get("top") if isinstance(source.get("hotspots"), dict) else {},
    }


def security_change_reasons(symbol: str, change: Dict[str, object]) -> List[str]:
    reasons = []
    watchlist = change.get("watchlist", {}) if isinstance(change.get("watchlist"), dict) else {}
    portfolio = change.get("portfolio_review", {}) if isinstance(change.get("portfolio_review"), dict) else {}
    risk = change.get("risk_flags", {}) if isinstance(change.get("risk_flags"), dict) else {}
    validation = change.get("validation", {}) if isinstance(change.get("validation"), dict) else {}
    if symbol in set(str(item) for item in watchlist.get("added_symbols", []) if item):
        reasons.append("观察项新增")
    if symbol in set(str(item) for item in watchlist.get("removed_symbols", []) if item):
        reasons.append("观察项移出")
    if symbol in set(str(item) for item in watchlist.get("changed_symbols", []) if item):
        reasons.append("观察项变化")
    if symbol in set(str(item) for item in portfolio.get("changed_symbols", []) if item):
        reasons.append("持仓复核变化")
    if validation.get("warning_delta"):
        reasons.append("数据告警变化 %+s" % validation.get("warning_delta"))
    added_risks = risk.get("added", []) if isinstance(risk.get("added"), list) else []
    if added_risks:
        reasons.append("新增风险 %s" % "、".join(risk_label_for_digest(value) for value in added_risks[:2]))
    return dedupe_queue_texts(reasons)[:6]


def risk_label_for_digest(value: object) -> str:
    labels = {
        "holding_missing_quote": "持仓缺行情",
        "no_hotspot_context": "缺热点上下文",
        "single_name_or_thin_resonance": "单票或弱共振",
        "theme_concentration": "主题集中",
        "theme_overlap": "主题重叠",
        "multi_chain_exposure": "多链路暴露",
        "chase_high_risk": "追高风险",
        "turnover_expansion_watch": "成交放大待复核",
        "data_quality_warnings": "数据质量告警",
    }
    return labels.get(str(value), str(value))


def security_exposure_groups(symbol: str, pressure: Dict[str, object]) -> List[Dict[str, object]]:
    groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
    rows = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
        if symbol not in {str(holding.get("symbol")) for holding in holdings if isinstance(holding, dict) and holding.get("symbol")}:
            continue
        rows.append(
            {
                "group_type": group.get("group_type"),
                "group": group.get("group"),
                "holding_count": group.get("holding_count"),
                "peer_symbols": [
                    str(holding.get("symbol"))
                    for holding in holdings
                    if isinstance(holding, dict) and holding.get("symbol") and str(holding.get("symbol")) != symbol
                ][:5],
                "commands": list(group.get("commands", []))[:3] if isinstance(group.get("commands"), list) else [],
            }
        )
    return rows[:5]


def agent_run_digest_change_tracking(briefing_data: Dict[str, object]) -> Dict[str, object]:
    current_change = briefing_data.get("current_change", {}) if isinstance(briefing_data.get("current_change"), dict) else {}
    history = briefing_data.get("history", {}) if isinstance(briefing_data.get("history"), dict) else {}
    latest_transition = history.get("latest_transition", {}) if isinstance(history.get("latest_transition"), dict) else {}
    return {
        "current_vs_latest": compact_digest_change("current_vs_latest", current_change),
        "history_transition": compact_digest_change("history_transition", latest_transition),
        "history": {
            "available": bool(history.get("available")),
            "can_compare": bool(history.get("can_compare")),
            "count": history.get("count", 0),
            "total_count": history.get("total_count", 0),
            "summary": history.get("summary"),
            "latest_note": compact_digest_latest_note(history),
        },
    }


def compact_digest_change(change_type: str, value: object) -> Dict[str, object]:
    change = value if isinstance(value, dict) else {}
    available = bool(change.get("available")) if change_type == "current_vs_latest" else bool(change)
    risk = change.get("risk_flags", {}) if isinstance(change.get("risk_flags"), dict) else {}
    watchlist = change.get("watchlist", {}) if isinstance(change.get("watchlist"), dict) else {}
    portfolio = change.get("portfolio_review", {}) if isinstance(change.get("portfolio_review"), dict) else {}
    hotspots = change.get("hotspots", {}) if isinstance(change.get("hotspots"), dict) else {}
    validation = change.get("validation", {}) if isinstance(change.get("validation"), dict) else {}
    return {
        "available": available,
        "change_type": change_type,
        "summary": change.get("summary") or "暂无变化对比。",
        "base_entry_id": change.get("base_entry_id") or entry_id_from_change(change.get("base_entry")),
        "current_entry_id": change.get("current_entry_id") or entry_id_from_change(change.get("current_entry")),
        "base_trade_date": change.get("base_trade_date") or entry_trade_date_from_change(change.get("base_entry")),
        "current_trade_date": change.get("current_trade_date") or entry_trade_date_from_change(change.get("current_entry")),
        "risk_flags": {
            "added_count": risk.get("added_count", 0),
            "removed_count": risk.get("removed_count", 0),
            "added": list(risk.get("added", []))[:6] if isinstance(risk.get("added"), list) else [],
            "removed": list(risk.get("removed", []))[:6] if isinstance(risk.get("removed"), list) else [],
        },
        "watchlist": {
            "added_count": watchlist.get("added_count", 0),
            "removed_count": watchlist.get("removed_count", 0),
            "changed_count": watchlist.get("changed_count", 0),
            "added_symbols": list(watchlist.get("added_symbols", []))[:6] if isinstance(watchlist.get("added_symbols"), list) else [],
            "removed_symbols": list(watchlist.get("removed_symbols", []))[:6] if isinstance(watchlist.get("removed_symbols"), list) else [],
            "changed_symbols": list(watchlist.get("changed_symbols", []))[:6] if isinstance(watchlist.get("changed_symbols"), list) else [],
        },
        "portfolio_review": {
            "added_count": portfolio.get("added_count", 0),
            "removed_count": portfolio.get("removed_count", 0),
            "changed_count": portfolio.get("changed_count", 0),
            "changed_symbols": list(portfolio.get("changed_symbols", []))[:6] if isinstance(portfolio.get("changed_symbols"), list) else [],
            "high_review_delta": portfolio.get("high_review_delta", 0),
        },
        "hotspots": {
            "added_count": hotspots.get("added_count", 0),
            "removed_count": hotspots.get("removed_count", 0),
            "changed_count": hotspots.get("changed_count", 0),
            "added_keys": list(hotspots.get("added_keys", []))[:5] if isinstance(hotspots.get("added_keys"), list) else [],
            "removed_keys": list(hotspots.get("removed_keys", []))[:5] if isinstance(hotspots.get("removed_keys"), list) else [],
            "changed_keys": list(hotspots.get("changed_keys", []))[:5] if isinstance(hotspots.get("changed_keys"), list) else [],
            "top": compact_digest_top_change(hotspots.get("top")),
        },
        "validation": {
            "warning_delta": validation.get("warning_delta", 0),
            "error_delta": validation.get("error_delta", 0),
            "base_warning_count": validation.get("base_warning_count", 0),
            "current_warning_count": validation.get("current_warning_count", 0),
            "base_error_count": validation.get("base_error_count", 0),
            "current_error_count": validation.get("current_error_count", 0),
        },
        "has_delta": digest_change_has_delta(risk, watchlist, portfolio, hotspots, validation),
        "commands": compact_digest_change_commands(change),
    }


def digest_change_has_delta(
    risk: Dict[str, object],
    watchlist: Dict[str, object],
    portfolio: Dict[str, object],
    hotspots: Dict[str, object],
    validation: Dict[str, object],
) -> bool:
    values = [
        risk.get("added_count", 0),
        risk.get("removed_count", 0),
        watchlist.get("added_count", 0),
        watchlist.get("removed_count", 0),
        watchlist.get("changed_count", 0),
        portfolio.get("added_count", 0),
        portfolio.get("removed_count", 0),
        portfolio.get("changed_count", 0),
        portfolio.get("high_review_delta", 0),
        hotspots.get("added_count", 0),
        hotspots.get("removed_count", 0),
        hotspots.get("changed_count", 0),
        validation.get("warning_delta", 0),
        validation.get("error_delta", 0),
    ]
    return any(safe_int(value) != 0 for value in values)


def compact_digest_top_change(value: object) -> Dict[str, object]:
    top = value if isinstance(value, dict) else {}
    return {
        "base": compact_digest_top_hotspot(top.get("base")),
        "current": compact_digest_top_hotspot(top.get("current")),
    }


def compact_digest_top_hotspot(value: object) -> Optional[Dict[str, object]]:
    item = value if isinstance(value, dict) else {}
    if not item:
        return None
    return {
        "key": item.get("key") or "%s/%s" % (item.get("layer"), item.get("sub_sector")),
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "score": item.get("score"),
        "rank": item.get("rank"),
    }


def compact_digest_change_commands(change: Dict[str, object]) -> List[str]:
    commands = []
    if change.get("compare_command"):
        commands.append(str(change.get("compare_command")))
    commands.extend(str(command) for command in change.get("next_commands", [])[:3] if command) if isinstance(change.get("next_commands"), list) else None
    return commands[:4]


def compact_digest_latest_note(history: Dict[str, object]) -> Optional[Dict[str, object]]:
    latest = history.get("latest_entry", {}) if isinstance(history.get("latest_entry"), dict) else {}
    note = latest.get("latest_note", {}) if isinstance(latest.get("latest_note"), dict) else {}
    if not note:
        return None
    return {
        "section": note.get("section"),
        "text": note.get("text"),
        "created_at": note.get("created_at"),
    }


def entry_id_from_change(value: object) -> Optional[object]:
    entry = value if isinstance(value, dict) else {}
    return entry.get("id") or entry.get("entry_id")


def entry_trade_date_from_change(value: object) -> Optional[object]:
    entry = value if isinstance(value, dict) else {}
    return entry.get("trade_date")


def agent_run_digest_next_steps(
    daily: Dict[str, object],
    results: List[Dict[str, object]],
    manual_followups: List[Dict[str, object]],
    change_tracking: Optional[Dict[str, object]] = None,
) -> List[Dict[str, object]]:
    steps: List[Dict[str, object]] = []
    first_error = next((item for item in results if isinstance(item, dict) and not item.get("ok")), None)
    if first_error:
        steps.append(
            {
                "rank": len(steps) + 1,
                "step_type": "data_quality",
                "title": "处理数据问题",
                "command": first_error.get("json_command") or first_error.get("command"),
                "reason": first_error.get("summary"),
                "state_effect": "read_only",
            }
        )
    tracking = change_tracking if isinstance(change_tracking, dict) else {}
    history_transition = tracking.get("history_transition", {}) if isinstance(tracking.get("history_transition"), dict) else {}
    current_vs_latest = tracking.get("current_vs_latest", {}) if isinstance(tracking.get("current_vs_latest"), dict) else {}
    if history_transition.get("has_delta"):
        commands = history_transition.get("commands", []) if isinstance(history_transition.get("commands"), list) else []
        command = first_digest_read_command(commands, "market-intel journal compare --json")
        steps.append(
            {
                "rank": len(steps) + 1,
                "step_type": "history_transition",
                "title": "核对最近留档转折",
                "command": command,
                "reason": history_transition.get("summary"),
                "state_effect": "read_only",
            }
        )
    elif current_vs_latest.get("has_delta"):
        commands = current_vs_latest.get("commands", []) if isinstance(current_vs_latest.get("commands"), list) else []
        command = first_digest_read_command(commands, "market-intel agent briefing --json")
        steps.append(
            {
                "rank": len(steps) + 1,
                "step_type": "current_change",
                "title": "核对当前变化",
                "command": command,
                "reason": current_vs_latest.get("summary"),
                "state_effect": "read_only",
            }
        )
    for item in agent_run_digest_securities(daily)[:2]:
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            steps.append(
                {
                    "rank": len(steps) + 1,
                    "step_type": "security_review",
                    "title": "%s %s" % (item.get("symbol"), item.get("name") or ""),
                    "command": commands[0],
                    "reason": "优先分 %s，风险 %s 个。" % (
                        item.get("priority_score"),
                        len(item.get("risk_ids", []) if isinstance(item.get("risk_ids"), list) else []),
                    ),
                    "state_effect": "read_only",
                }
            )
    for item in manual_followups[:3]:
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "rank": len(steps) + 1,
                "step_type": "manual_followup",
                "title": "人工确认后运行",
                "command": item.get("json_command") or item.get("command"),
                "reason": item.get("reason"),
                "state_effect": item.get("state_effect"),
                "requires_prior_command": item.get("requires_prior_command"),
            }
        )
    return steps[:6]


def first_dict(value: object) -> Dict[str, object]:
    rows = value if isinstance(value, list) else []
    for item in rows:
        if isinstance(item, dict):
            return item
    return {}


def compact_digest_holdings(value: object) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    return [
        {
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "priority": item.get("priority"),
            "priority_score": item.get("priority_score"),
        }
        for item in rows[:6]
        if isinstance(item, dict)
    ]


def compact_digest_issues(value: object, limit: int = 6) -> List[Dict[str, object]]:
    issues = value if isinstance(value, list) else []
    rows = []
    for issue in issues[:limit]:
        if isinstance(issue, str):
            rows.append({"code": issue})
            continue
        if not isinstance(issue, dict):
            continue
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        row: Dict[str, object] = {"code": issue.get("code"), "message": issue.get("message")}
        for key in ("symbol", "path", "field", "index"):
            if issue.get(key) is not None:
                row[key] = issue.get(key)
            elif detail.get(key) is not None:
                row[key] = detail.get(key)
        rows.append(row)
    return rows


def first_digest_read_command(commands: List[object], default: str) -> str:
    for command in commands:
        text = str(command or "")
        if text and digest_command_is_read_only(text):
            return text
    return default


def digest_command_is_read_only(command: str) -> bool:
    padded = " %s " % command
    if " journal save " in padded or " journal note " in padded:
        return False
    if " import research " in padded and " --dry-run " in padded:
        return True
    if " import quotes " in padded or " import holdings " in padded or " import research " in padded or " init runtime " in padded:
        return False
    if " pool research " in padded and " --output " in padded:
        return False
    return True


def digest_json_variant(command: object) -> str:
    text = str(command or "")
    if " --json" in text:
        return text
    if " --text" in text:
        return text.replace(" --text", " --json")
    return "%s --json" % text if text else ""


def safe_int(value: object, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def agent_run_state(briefing_data: Dict[str, object], results: List[Dict[str, object]], skipped: List[Dict[str, object]]) -> str:
    briefing_state_value = str(briefing_data.get("state") or "")
    if briefing_state_value == "blocked":
        return "blocked_review"
    if any(isinstance(item, dict) and not item.get("ok") for item in results):
        return "ran_with_errors"
    if skipped:
        return "ran_with_skips"
    return "ran"


def agent_run_summary(briefing_data: Dict[str, object], results: List[Dict[str, object]], skipped: List[Dict[str, object]]) -> str:
    read_count = len(results)
    ok_count = sum(1 for item in results if isinstance(item, dict) and item.get("ok"))
    skipped_writes = sum(1 for item in skipped if isinstance(item, dict) and item.get("state_effect") != "read_only")
    state = briefing_data.get("state") or "unknown"
    return "briefing 状态 %s；已运行只读步骤 %s 个，成功 %s 个；跳过命令 %s 个，其中写入或需人工确认 %s 个。" % (
        state,
        read_count,
        ok_count,
        len(skipped),
        skipped_writes,
    )


def agent_run_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 表示 agent run 结果包已生成；单条命令是否成功看 data.results[].ok。",
        "stable_fields": [
            "data.state",
            "data.summary",
            "data.source_briefing",
            "data.review_digest",
            "data.review_digest.coverage_context",
            "data.review_digest.coverage_context.universe.sector_profile",
            "data.review_digest.coverage_context.universe.sector_profile.top_industries",
            "data.review_digest.coverage_context.universe.sector_profile.top_concepts",
            "data.review_digest.coverage_context.universe.sector_profile.top_indexes",
            "data.review_digest.coverage_context.universe.enrichment_queue",
            "data.review_digest.coverage_context.top_data_quality_queue",
            "data.review_digest.coverage_context.next_actions",
            "data.review_digest.coverage_context.next_actions[].rank",
            "data.review_digest.market_scan",
            "data.review_digest.market_scan.market_breadth",
            "data.review_digest.market_scan.top_groups",
            "data.review_digest.market_scan.top_candidates",
            "data.review_digest.market_scan.candidate_queue",
            "data.review_digest.market_scan.top_candidates[].ranking_breakdown",
            "data.review_digest.market_scan.top_candidates[].universe_context",
            "data.review_digest.data_repair_plan",
            "data.review_digest.data_repair_plan.items",
            "data.review_digest.data_repair_plan.groups",
            "data.review_digest.market_structure",
            "data.review_digest.portfolio_pressure",
            "data.review_digest.portfolio_pressure.changed_group_count",
            "data.review_digest.portfolio_pressure.groups[].changed_members",
            "data.review_digest.portfolio_pressure.groups[].priority_question",
            "data.review_digest.portfolio_pressure.groups[].primary_json_command",
            "data.review_digest.holding_dashboard",
            "data.review_digest.holding_dashboard.buckets",
            "data.review_digest.holding_dashboard.changed_holdings",
            "data.review_digest.holding_dashboard.top_holdings",
            "data.review_digest.holding_dashboard.top_holdings[].coverage_state",
            "data.review_digest.holding_dashboard.top_holdings[].coverage_state_reasons",
            "data.review_digest.holding_dashboard.top_holdings[].research_status",
            "data.review_digest.holding_dashboard.top_holdings[].change",
            "data.review_digest.holding_dashboard.top_holdings[].change_priority",
            "data.review_digest.holding_dashboard.top_holdings[].primary_question",
            "data.review_digest.holding_dashboard.top_holdings[].primary_command",
            "data.review_digest.holding_dashboard.top_holdings[].primary_json_command",
            "data.review_digest.securities_to_review",
            "data.review_digest.risk_watch",
            "data.review_digest.change_tracking",
            "data.review_digest.change_tracking.current_vs_latest",
            "data.review_digest.change_tracking.history_transition",
            "data.review_digest.security_workbench",
            "data.review_digest.security_workbench[].change",
            "data.review_digest.security_workbench[].exposure_groups",
            "data.review_digest.security_workbench[].primary_command",
            "data.review_digest.security_cards",
            "data.review_digest.security_cards.cards",
            "data.review_digest.security_cards.cards[].symbol",
            "data.review_digest.security_cards.cards[].priority",
            "data.review_digest.security_cards.cards[].coverage_state",
            "data.review_digest.security_cards.cards[].coverage_state_reasons",
            "data.review_digest.security_cards.cards[].research_status",
            "data.review_digest.security_cards.cards[].research_workflow",
            "data.review_digest.security_cards.cards[].research_workflow[].json_command",
            "data.review_digest.security_cards.cards[].open_gaps",
            "data.review_digest.security_cards.cards[].next_json_command",
            "data.review_digest.security_cards.cards[].journal_note.prefilled_note_command",
            "data.review_digest.evidence_checklist",
            "data.review_digest.evidence_checklist.items",
            "data.review_digest.evidence_checklist.items[].coverage_status",
            "data.review_digest.evidence_checklist.items[].missing_evidence",
            "data.review_digest.evidence_checklist.items[].json_command",
            "data.review_digest.evidence_checklist.items[].journal_note.prefilled_note_command",
            "data.review_digest.hypothesis_board",
            "data.review_digest.hypothesis_board.items",
            "data.review_digest.hypothesis_board.items[].hypothesis",
            "data.review_digest.hypothesis_board.items[].supporting_evidence",
            "data.review_digest.hypothesis_board.items[].weak_points",
            "data.review_digest.hypothesis_board.items[].validation_step",
            "data.review_digest.hypothesis_board.items[].invalidation_signal",
            "data.review_digest.hypothesis_board.items[].json_command",
            "data.review_digest.hypothesis_board.items[].journal_note.prefilled_note_command",
            "data.review_digest.journal_draft",
            "data.review_digest.journal_draft.archive_prerequisite",
            "data.review_digest.journal_draft.sections",
            "data.review_digest.journal_draft.sections[].draft_text",
            "data.review_digest.journal_draft.sections[].note_command_template",
            "data.review_digest.journal_draft.sections[].prefilled_note_command",
            "data.review_digest.journal_draft.sections[].run_after",
            "data.review_digest.attention_queue",
            "data.review_digest.attention_queue.items",
            "data.review_digest.attention_queue.items[].json_command",
            "data.review_digest.attention_queue.items[].runnable",
            "data.review_digest.attention_queue.items[].requires_manual",
            "data.review_digest.attention_queue.items[].already_read",
            "data.review_digest.attention_queue.items[].linked_result",
            "data.review_digest.attention_queue.items[].linked_result.run_rank",
            "data.review_digest.attention_queue.items[].linked_result.summary",
            "data.review_digest.attention_queue.items[].linked_context",
            "data.review_digest.attention_queue.items[].linked_context.source",
            "data.review_digest.attention_queue.items[].linked_context.summary",
            "data.review_digest.attention_queue.items[].journal_note",
            "data.review_digest.attention_queue.items[].journal_note.section",
            "data.review_digest.attention_queue.items[].journal_note.prefilled_note_command",
            "data.review_digest.attention_queue.items[].journal_note.run_after",
            "data.review_digest.followup_watch",
            "data.review_digest.followup_watch.items",
            "data.review_digest.followup_watch.items[].symbols",
            "data.review_digest.followup_watch.items[].check_question",
            "data.review_digest.followup_watch.items[].json_command",
            "data.review_digest.followup_watch.items[].journal_note.prefilled_note_command",
            "data.review_digest.review_completion",
            "data.review_digest.review_completion.completion_state",
            "data.review_digest.review_completion.ready_for_journal_note",
            "data.review_digest.review_completion.checks",
            "data.review_digest.review_completion.checks[].status",
            "data.review_digest.review_completion.checks[].json_command",
            "data.review_digest.review_handoff",
            "data.review_digest.review_handoff.handoff_state",
            "data.review_digest.review_handoff.resume_prompt",
            "data.review_digest.review_handoff.command_chain",
            "data.review_digest.review_handoff.command_chain[].json_command",
            "data.review_digest.review_handoff.next_read",
            "data.review_digest.review_handoff.next_read[].json_command",
            "data.review_digest.review_handoff.manual_items",
            "data.review_digest.review_handoff.manual_items[].workflow_steps",
            "data.review_digest.review_handoff.manual_items[].workflow_steps[].json_command",
            "data.review_digest.review_handoff.record_templates",
            "data.review_digest.review_handoff.watch_items",
            "data.review_digest.next_steps",
            "data.queue",
            "data.queue[].json_command",
            "data.queue[].state_effect",
            "data.results",
            "data.results[].json_command",
            "data.results[].ok",
            "data.results[].summary",
            "data.results[].observations",
            "data.skipped",
            "data.skipped[].reason",
            "data.manual_followups",
            "data.manual_followups[].json_command",
        ],
        "boundary": "agent run 只自动运行只读命令；保存日报和记录复盘笔记保留给人工确认。",
    }


def agent_next_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 表示已生成下一步交接包；是否还有待读命令看 data.review_handoff.command_chain。",
        "stable_fields": [
            "data.state",
            "data.summary",
            "data.symbol",
            "data.source_agent_run_state",
            "data.coverage_context",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.universe.sector_profile.top_industries",
            "data.coverage_context.universe.sector_profile.top_concepts",
            "data.coverage_context.universe.sector_profile.top_indexes",
            "data.coverage_context.universe.enrichment_queue",
            "data.coverage_context.top_data_quality_queue",
            "data.coverage_context.next_actions",
            "data.market_scan",
            "data.market_scan.market_breadth",
            "data.market_scan.top_groups",
            "data.market_scan.top_candidates",
            "data.market_scan.candidate_queue",
            "data.market_scan.top_candidates[].ranking_breakdown",
            "data.market_scan.top_candidates[].universe_context",
            "data.action_summary",
            "data.action_summary.headline",
            "data.action_summary.next_command",
            "data.action_summary.command_queue",
            "data.action_summary.command_queue[].json_command",
            "data.action_summary.command_queue[].done_when",
            "data.action_summary.command_queue[].runnable",
            "data.action_summary.completion_checklist",
            "data.action_summary.completion_checklist[].status",
            "data.action_summary.completion_checklist[].json_command",
            "data.action_summary.completion_checklist[].done_when",
            "data.action_summary.record_template",
            "data.action_summary.record_template.runnable",
            "data.action_summary.record_template.prerequisite_command",
            "data.action_summary.record_template.prerequisite_done_when",
            "data.action_summary.record_template.prefilled_note_command",
            "data.focus_chain",
            "data.focus_chain[].source",
            "data.focus_chain[].json_command",
            "data.focus_chain[].done_when",
            "data.review_handoff",
            "data.review_handoff.handoff_state",
            "data.review_handoff.resume_prompt",
            "data.review_handoff.command_chain",
            "data.review_handoff.command_chain[].step_type",
            "data.review_handoff.command_chain[].json_command",
            "data.review_handoff.command_chain[].runnable",
            "data.review_handoff.command_chain[].requires_manual",
            "data.review_handoff.manual_items",
            "data.review_handoff.manual_items[].workflow_steps",
            "data.review_handoff.manual_items[].workflow_steps[].json_command",
            "data.review_completion",
            "data.review_completion.completion_state",
            "data.security_cards",
            "data.security_cards.cards",
            "data.security_cards.cards[].symbol",
            "data.security_cards.cards[].coverage_state",
            "data.security_cards.cards[].coverage_state_reasons",
            "data.security_cards.cards[].research_status",
            "data.security_cards.cards[].research_workflow",
            "data.security_cards.cards[].research_workflow[].json_command",
            "data.security_cards.cards[].next_json_command",
            "data.security_cards.cards[].open_gaps",
        ],
        "boundary": "agent next 只整理下一步上下文，不自动执行命令或写入 journal。",
    }


def command_payload_summary(payload: Dict[str, object]) -> str:
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    summary = data.get("summary")
    if isinstance(summary, str) and summary:
        return summary
    readiness = data.get("readiness", {}) if isinstance(data.get("readiness"), dict) else {}
    if readiness:
        return "%s | %s" % (readiness.get("state"), readiness.get("reason"))
    validation_summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    if validation_summary:
        return "行情 %s 条，持仓 %s 条，告警 %s 个。" % (
            validation_summary.get("quote_count", 0),
            validation_summary.get("holding_count", 0),
            validation_summary.get("warning_count", 0),
        )
    if data.get("explain"):
        return str(data.get("explain"))
    if data.get("found") is False:
        return "未找到可用数据。"
    if payload.get("errors"):
        return "命令返回错误。"
    return "命令已返回结构化结果。"


def command_payload_observations(payload: Dict[str, object]) -> List[str]:
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    command = str(payload.get("command") or "")
    observations: List[str] = []
    if command == "agent.briefing":
        observations.extend(compact_focus_lines(data.get("review_focus", []), "焦点"))
        observations.extend(compact_focus_lines(data.get("review_checklist", []), "清单"))
        queue = data.get("command_queue", []) if isinstance(data.get("command_queue"), list) else []
        observations.append("命令队列 %s 条。" % len(queue))
    elif command == "status.runtime":
        readiness = data.get("readiness", {}) if isinstance(data.get("readiness"), dict) else {}
        observations.append("runtime: %s | %s" % (readiness.get("state"), readiness.get("reason")))
        observations.extend(compact_payload_issues(payload.get("errors", []), limit=3))
        observations.extend(compact_payload_issues(payload.get("warnings", []), limit=3))
    elif command == "validate.runtime":
        summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
        observations.append("行情 %s 条，持仓 %s 条，告警 %s 个。" % (summary.get("quote_count", 0), summary.get("holding_count", 0), summary.get("warning_count", 0)))
        observations.extend(compact_payload_issues(data.get("validation_warnings", []), limit=5))
        observations.extend(compact_payload_issues(payload.get("errors", []), limit=5))
    elif command == "daily":
        brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
        observations.extend(compact_hotspot_lines(brief.get("top_hotspots", [])))
        observations.extend(compact_risk_lines(data.get("risk_register", [])))
        observations.extend(compact_security_profile_lines(data.get("security_risk_profile", [])))
    elif command == "scan":
        observations.extend(compact_scan_group_lines(data.get("sector_groups", [])))
        observations.extend(compact_scan_candidate_lines(data.get("candidate_securities", [])))
    elif command == "portfolio.review":
        observations.extend(compact_security_lines(data.get("items", []), "持仓"))
        observations.extend(compact_group_lines(data.get("repeated_exposures", []), "重复链路"))
        observations.extend(compact_group_lines(data.get("repeated_overlap_groups", []), "重复主题"))
    elif command == "portfolio.explain":
        item = data.get("item", {}) if isinstance(data.get("item"), dict) else {}
        observations.extend(compact_security_lines([item], "标的"))
        related = data.get("related", {}) if isinstance(data.get("related"), dict) else {}
        observations.append("相关同链路 %s 个，同主题 %s 个。" % (
            len(related.get("same_exposure", []) if isinstance(related.get("same_exposure"), list) else []),
            len(related.get("same_overlap_group", []) if isinstance(related.get("same_overlap_group"), list) else []),
        ))
        observations.extend(str(question) for question in data.get("questions", [])[:3] if question)
    elif command == "pool.coverage":
        counts = data.get("counts", {}) if isinstance(data.get("counts"), dict) else {}
        universe = data.get("universe", {}) if isinstance(data.get("universe"), dict) else {}
        profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
        holdings = data.get("holdings_coverage", {}) if isinstance(data.get("holdings_coverage"), dict) else {}
        observations.append(
            "覆盖: %s | %s | A股 %s/%s。"
            % (
                data.get("status"),
                data.get("scope"),
                counts.get("cn_a", 0),
                counts.get("tradable", 0),
            )
        )
        observations.append(
            "全A基础清单: %s | 记录 %s | 行业 %.0f%% / 概念 %.0f%% / 指数 %.0f%%。"
            % (
                "已接入" if universe.get("available") else "未接入",
                universe.get("record_count", 0),
                float(profile.get("industry_coverage_ratio") or 0) * 100,
                float(profile.get("concept_coverage_ratio") or 0) * 100,
                float(profile.get("index_coverage_ratio") or 0) * 100,
            )
        )
        if holdings.get("provided"):
            observations.append(
                "持仓覆盖: confirmed %s / foundation %s / missing %s。"
                % (
                    holdings.get("confirmed_count", 0),
                    holdings.get("foundation_matched_count", 0),
                    holdings.get("unmatched_count", 0),
                )
            )
        gaps = data.get("gaps", []) if isinstance(data.get("gaps"), list) else []
        observations.extend(
            "%s | %s" % (item.get("severity"), item.get("id"))
            for item in gaps[:3]
            if isinstance(item, dict)
        )
        queue = data.get("data_quality_queue", []) if isinstance(data.get("data_quality_queue"), list) else []
        if queue and isinstance(queue[0], dict):
            observations.append(
                "数据质量优先清理: %s | %s | 影响 %s。"
                % (queue[0].get("flag"), queue[0].get("severity"), queue[0].get("affected_count", 0))
            )
    elif command == "pool.quality":
        observations.append(
            "质量标记 %s | %s | 影响 %s。"
            % (data.get("flag"), data.get("severity"), data.get("affected_count", 0))
        )
        observations.append(str(data.get("suggested_action") or "查看样本并修正。"))
        samples = data.get("samples", []) if isinstance(data.get("samples"), list) else []
        observations.extend(
            "样本 row %s: %s %s"
            % (sample.get("raw_row"), sample.get("symbol") or sample.get("raw_code") or "未上市", sample.get("name"))
            for sample in samples[:3]
            if isinstance(sample, dict)
        )
    elif command == "pool.explain":
        facts = data.get("facts", {}) if isinstance(data.get("facts"), dict) else {}
        observations.append("%s %s | %s/%s | 暴露 %s 条。" % (
            facts.get("symbol"),
            facts.get("name"),
            facts.get("primary_layer"),
            facts.get("primary_sub_sector"),
            facts.get("exposure_count", 0),
        ))
        observations.extend(str(question) for question in data.get("questions", [])[:3] if question)
    elif command == "watchlist":
        observations.extend(compact_security_lines(data.get("items", []), "观察"))
    elif command == "map":
        observations.extend(compact_hotspot_lines(data.get("hotspots", []) or data.get("items", [])))
    elif command == "brief":
        observations.extend(compact_hotspot_lines(data.get("top_hotspots", [])))
    elif command.startswith("journal."):
        if data.get("summary"):
            observations.append(str(data.get("summary")))
        observations.extend(str(command_text) for command_text in data.get("next_commands", [])[:3] if command_text)
    elif command == "import.schema":
        observations.append("已读取 CSV 字段合同。")
    observations.extend(compact_payload_issues(payload.get("errors", []), limit=3))
    return dedupe_queue_texts([text for text in observations if text])[:8]


def compact_focus_lines(value: object, label_text: str) -> List[str]:
    rows = value if isinstance(value, list) else []
    return [
        "%s: %s | %s" % (label_text, item.get("title"), item.get("reason"))
        for item in rows[:3]
        if isinstance(item, dict)
    ]


def compact_hotspot_lines(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        result.append("%s/%s | 热点 %s | 活跃 %s/%s" % (
            item.get("layer"),
            item.get("sub_sector"),
            item.get("score"),
            item.get("active_member_count"),
            item.get("member_count"),
        ))
    return result


def compact_scan_group_lines(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        result.append(
            "扫描板块: %s%s | 分 %s | 活跃 %s/%s"
            % (
                item.get("group_type"),
                item.get("name"),
                item.get("score"),
                item.get("active_member_count"),
                item.get("member_count"),
            )
        )
    return result


def compact_scan_candidate_lines(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:4]:
        if not isinstance(item, dict):
            continue
        result.append(
            "扫描候选: %s %s | 分 %s | 覆盖 %s"
            % (
                item.get("symbol"),
                item.get("name"),
                item.get("review_score"),
                item.get("coverage_state"),
            )
        )
    return result


def compact_risk_lines(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    return [
        "风险: %s | %s | 涉及 %s 个" % (item.get("label"), item.get("severity"), item.get("affected_count"))
        for item in rows[:3]
        if isinstance(item, dict)
    ]


def compact_security_profile_lines(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    return [
        "画像: %s %s | %s | 风险 %s" % (
            item.get("symbol"),
            item.get("name"),
            item.get("severity"),
            len(item.get("risk_ids", []) if isinstance(item.get("risk_ids"), list) else []),
        )
        for item in rows[:3]
        if isinstance(item, dict)
    ]


def compact_security_lines(value: object, prefix: str) -> List[str]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:4]:
        if not isinstance(item, dict):
            continue
        flags = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        result.append("%s: %s %s | %s | 复核分 %s | 风险标签 %s" % (
            prefix,
            item.get("symbol"),
            item.get("name"),
            item.get("priority") or item.get("focus") or item.get("layer"),
            item.get("priority_score") or item.get("hotspot_score"),
            len(flags),
        ))
    return result


def compact_group_lines(value: object, prefix: str) -> List[str]:
    rows = value if isinstance(value, list) else []
    return [
        "%s: %s | 持仓 %s" % (prefix, item.get("group"), item.get("holding_count"))
        for item in rows[:3]
        if isinstance(item, dict)
    ]


def compact_payload_issues(value: object, limit: int = 5) -> List[str]:
    issues = value if isinstance(value, list) else []
    result = []
    for issue in issues[:limit]:
        if not isinstance(issue, dict):
            continue
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        suffix = detail.get("symbol") or detail.get("path") or detail.get("field") or detail.get("index")
        if suffix is not None:
            result.append("%s:%s" % (issue.get("code"), suffix))
        else:
            result.append(str(issue.get("code") or issue.get("message") or "UNKNOWN"))
    return result


def command_has_placeholder(command: str) -> bool:
    return "<" in command or ">" in command


def flag_present(tokens: List[str], flag: str) -> bool:
    return flag in tokens


def option_value(tokens: List[str], flag: str, default: Optional[str] = None) -> Optional[str]:
    try:
        index = tokens.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(tokens):
        return default
    return tokens[index + 1]


def option_int(tokens: List[str], flag: str, default: int) -> int:
    value = option_value(tokens, flag)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def first_positional(tokens: List[str]) -> Optional[str]:
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in {
            "--pool",
            "--quotes-file",
            "--holdings-file",
            "--top",
            "--map-top",
            "--max-quote-age-days",
            "--limit",
            "--base",
            "--current",
        }:
            skip_next = True
            continue
        if token.startswith("--"):
            continue
        return token
    return None


def agent_plan_warnings(status_data: Dict[str, object], journal_data: Dict[str, object]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    warnings.extend(status_warnings(status_data))
    journal_errors = journal_data.get("errors", []) if isinstance(journal_data.get("errors"), list) else []
    warnings.extend(journal_errors)
    return warnings


def handle_journal_save(
    pool: str,
    use_runtime: bool = False,
    quotes_file: Optional[str] = None,
    holdings_file: Optional[str] = None,
    top: int = 5,
    map_top: int = 2,
) -> Dict[str, Any]:
    daily_payload = handle_daily(
        pool,
        use_mock=False,
        top=top,
        map_top=map_top,
        quotes_file=quotes_file,
        holdings_file=holdings_file,
        use_runtime=use_runtime,
    )
    if not daily_payload["ok"]:
        return envelope(
            command="journal.save",
            data={
                "saved": False,
                "daily": daily_payload,
                "next_commands": ["market-intel status runtime --json", "market-intel validate runtime --json"],
            },
            errors=daily_payload.get("errors", []),
            source=daily_payload.get("meta", {}).get("source") if isinstance(daily_payload.get("meta"), dict) else None,
            ok=False,
        )
    result = save_daily_journal(daily_payload)
    return envelope(
        command="journal.save",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=daily_payload.get("meta", {}).get("source") if isinstance(daily_payload.get("meta"), dict) else None,
        ok=bool(result.get("saved")),
    )


def handle_journal_list(limit: int = 10) -> Dict[str, Any]:
    result = list_journal_entries(limit=limit)
    return envelope(
        command="journal.list",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=not bool(result.get("errors")),
    )


def handle_journal_latest() -> Dict[str, Any]:
    result = latest_journal_entry()
    return envelope(
        command="journal.latest",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=bool(result.get("found")),
    )


def handle_journal_show(entry_id: str) -> Dict[str, Any]:
    result = read_journal_by_id(entry_id)
    return envelope(
        command="journal.show",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=bool(result.get("found")),
    )


def handle_journal_compare(base_id: Optional[str] = None, current_id: Optional[str] = None) -> Dict[str, Any]:
    result = compare_journal_entries(base_id=base_id, current_id=current_id)
    return envelope(
        command="journal.compare",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=bool(result.get("found")),
    )


def handle_journal_timeline(limit: int = 5) -> Dict[str, Any]:
    result = build_journal_timeline(limit=limit)
    return envelope(
        command="journal.timeline",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=not bool(result.get("errors")),
    )


def handle_journal_note(
    entry_id: Optional[str] = None,
    section: Optional[str] = None,
    note_text: Optional[str] = None,
    note_file: Optional[str] = None,
) -> Dict[str, Any]:
    text_result = read_note_text(note_text, note_file)
    if text_result.get("error"):
        return envelope(
            command="journal.note",
            data={
                "saved": False,
                "next_commands": ["market-intel journal latest --text", "market-intel agent briefing --text"],
            },
            errors=[text_result["error"]],
            source=note_file,
            ok=False,
        )
    result = save_journal_note(entry_id, str(text_result.get("text") or ""), section=section)
    return envelope(
        command="journal.note",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=bool(result.get("saved")),
    )


def handle_journal_notes(limit: int = 10, section: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    result = list_journal_notes(limit=limit, section=section, query=query)
    return envelope(
        command="journal.notes",
        data=result,
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        source=result.get("journal_dir"),
        ok=not bool(result.get("errors")),
    )


def read_note_text(note_text: Optional[str], note_file: Optional[str]) -> Dict[str, object]:
    if note_text and note_file:
        return {"error": error("JOURNAL_NOTE_SOURCE_CONFLICT", "Use either --text or --file, not both.")}
    if note_text is not None:
        return {"text": note_text}
    if note_file:
        try:
            if note_file == "-":
                return {"text": sys.stdin.read()}
            return {"text": Path(note_file).read_text(encoding="utf-8")}
        except Exception as exc:
            return {"error": error("JOURNAL_NOTE_READ_ERROR", str(exc), {"path": note_file})}
    return {"error": error("JOURNAL_NOTE_TEXT_REQUIRED", "Use --text or --file to provide note text.")}


def build_runtime_context(symbol: Optional[str]) -> Dict[str, object]:
    if not symbol:
        return {}
    paths = runtime_paths()
    quotes = load_quotes_file(Path(paths["quotes"]))
    holdings = load_holdings_file(Path(paths["holdings"]))
    quote = next((quote for quote in quotes if quote.symbol == symbol), None)
    holding = next((holding for holding in holdings if holding.symbol == symbol), None)
    return {
        "quote": quote.to_dict() if quote else None,
        "holding": holding.to_dict() if holding else None,
        "sources": paths,
    }


def runtime_error(command: str, missing: List[str]) -> Dict[str, Any]:
    return envelope(
        command=command,
        errors=[
            error(
                "RUNTIME_NOT_INITIALIZED",
                "Runtime files are missing. Run: market-intel init runtime",
                {"missing": missing},
            )
        ],
        source=str(default_pool_path()),
        ok=False,
    )


def pool_coverage_runtime_error(pool: str) -> Dict[str, Any]:
    return envelope(
        command="pool.coverage",
        errors=[
            error(
                "RUNTIME_HOLDINGS_NOT_INITIALIZED",
                "Runtime holdings file is missing. Run: market-intel init runtime",
                {"missing": ["holdings.json"]},
            )
        ],
        source="pool:%s" % pool,
        ok=False,
    )


def privacy_safe_source(source: object, kind: str, mode: str) -> str:
    text = str(source or "")
    if mode == "mock":
        return text
    if mode == "runtime":
        return "runtime_%s" % kind
    return "%s_file" % kind


def brief_mode(
    use_mock: bool,
    use_runtime: bool,
    quotes_file: Optional[str],
    holdings_file: Optional[str],
) -> str:
    if use_runtime:
        return "runtime"
    if use_mock and not (quotes_file or holdings_file):
        return "mock"
    return "file"


def localize_daily_review_task_commands(
    tasks: object,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> List[Dict[str, object]]:
    rows = tasks if isinstance(tasks, list) else []
    return [localize_daily_review_task(task, pool, mode, quote_source, holdings_source) for task in rows if isinstance(task, dict)]


def localize_daily_review_task(
    task: Dict[str, object],
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> Dict[str, object]:
    localized = dict(task)
    commands = task.get("commands", []) if isinstance(task.get("commands"), list) else []
    localized["commands"] = [
        localize_daily_command(str(command), pool, mode, quote_source, holdings_source)
        for command in commands
        if command
    ]
    return localized


def localize_daily_security_queue_commands(
    items: object,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> List[Dict[str, object]]:
    rows = items if isinstance(items, list) else []
    return [localize_daily_security_queue_item(item, pool, mode, quote_source, holdings_source) for item in rows if isinstance(item, dict)]


def localize_daily_risk_register_commands(
    items: object,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> List[Dict[str, object]]:
    rows = items if isinstance(items, list) else []
    localized_rows = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        localized = dict(item)
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        localized["commands"] = [
            localize_daily_command(str(command), pool, mode, quote_source, holdings_source)
            for command in commands
            if command
        ]
        localized_rows.append(localized)
    return localized_rows


def localize_daily_review_path_commands(
    items: object,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
    journal_actions: object,
) -> List[Dict[str, object]]:
    rows = items if isinstance(items, list) else []
    actions = journal_actions if isinstance(journal_actions, list) else []
    archive = next((action for action in actions if isinstance(action, dict) and action.get("id") == "archive_current"), None)
    localized_rows = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        localized = dict(item)
        if localized.get("id") == "archive_review" and isinstance(archive, dict):
            localized["commands"] = [str(archive.get("command"))] if archive.get("command") else []
            localized["runnable"] = bool(archive.get("runnable"))
            if not archive.get("runnable"):
                localized["unavailable_reason"] = archive.get("reason")
        else:
            commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
            localized["commands"] = [
                localize_daily_command(str(command), pool, mode, quote_source, holdings_source)
                for command in commands
                if command
            ]
            localized["runnable"] = bool(localized.get("runnable", True))
        localized_rows.append(localized)
    return localized_rows


def localize_daily_security_profile_commands(
    items: object,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> List[Dict[str, object]]:
    rows = items if isinstance(items, list) else []
    localized_rows = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        localized = dict(item)
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        localized["commands"] = [
            localize_daily_command(str(command), pool, mode, quote_source, holdings_source)
            for command in commands
            if command
        ]
        localized_rows.append(localized)
    return localized_rows


def localize_daily_security_queue_item(
    item: Dict[str, object],
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> Dict[str, object]:
    localized = dict(item)
    commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
    localized["commands"] = [
        localize_daily_command(str(command), pool, mode, quote_source, holdings_source)
        for command in commands
        if command
    ]
    return localized


def localize_daily_command(
    command: str,
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> str:
    if mode == "runtime":
        return command
    if "validate runtime" in command:
        if mode == "mock":
            return with_pool_arg("market-intel daily --mock --json", pool)
        if mode == "file":
            return with_pool_arg(
                "market-intel daily --quotes-file %s --holdings-file %s --json"
                % (quote_command_arg(quote_source), quote_command_arg(holdings_source)),
                pool,
            )
    if "status runtime" in command:
        return "market-intel import schema --json"
    if mode == "mock":
        if "pool explain" in command:
            return with_pool_arg(command.replace(" --runtime", ""), pool)
        return with_pool_arg(command.replace(" --runtime", " --mock"), pool)
    if mode == "file":
        if "pool explain" in command:
            return with_pool_arg(command.replace(" --runtime", ""), pool)
        return with_pool_arg(
            command.replace(
                " --runtime",
                " --quotes-file %s --holdings-file %s"
                % (quote_command_arg(quote_source), quote_command_arg(holdings_source)),
            ),
            pool,
        )
    return command


def daily_journal_actions(
    pool: str,
    mode: str,
    quote_source: object,
    holdings_source: object,
) -> List[Dict[str, object]]:
    actions: List[Dict[str, object]] = []
    if mode == "runtime":
        actions.append(
            journal_action(
                "archive_current",
                "保存当前日报",
                "market-intel journal save --runtime --json",
                True,
                "保存今天的完整日报，后续可做 timeline 和 compare。",
            )
        )
    elif mode == "file":
        actions.append(
            journal_action(
                "archive_current",
                "保存当前日报",
                with_pool_arg(
                    "market-intel journal save --quotes-file %s --holdings-file %s --json"
                    % (quote_command_arg(quote_source), quote_command_arg(holdings_source)),
                    pool,
                ),
                True,
                "保存这组文件生成的日报，后续可做 timeline 和 compare。",
            )
        )
    else:
        actions.append(
            journal_action(
                "archive_current",
                "保存当前日报",
                "market-intel journal save --runtime --json",
                False,
                "mock 日报不直接保存；接入 runtime 或文件后再留档。",
            )
        )

    actions.extend(
        [
            journal_action(
                "latest_archive",
                "查看最近留档",
                "market-intel journal latest --text",
                True,
                "回看最近一次日报和复盘笔记。",
            ),
            journal_action(
                "recent_notes",
                "查看最近笔记",
                "market-intel journal notes --text",
                True,
                "集中查看最近的用户复盘笔记。",
            ),
            journal_action(
                "timeline",
                "查看留档时间线",
                "market-intel journal timeline --text",
                True,
                "看多日热点、风险和持仓复核变化。",
            ),
        ]
    )
    return actions


def add_daily_note_prerequisites(data: Dict[str, object]) -> None:
    actions = data.get("journal_actions", []) if isinstance(data.get("journal_actions"), list) else []
    archive = next((action for action in actions if isinstance(action, dict) and action.get("id") == "archive_current"), None)
    if not isinstance(archive, dict):
        return
    prerequisite = {
        "requires_journal_entry": True,
        "summary": "记录复盘笔记前，需要先有一份日报留档。",
        "archive_command": archive.get("command"),
        "archive_runnable": bool(archive.get("runnable")),
        "archive_reason": archive.get("reason"),
    }
    for task in data.get("review_tasks", []) if isinstance(data.get("review_tasks"), list) else []:
        if isinstance(task, dict) and task.get("note_command"):
            task["note_prerequisite"] = dict(prerequisite)
    for item in data.get("security_review_queue", []) if isinstance(data.get("security_review_queue"), list) else []:
        if isinstance(item, dict) and item.get("note_command"):
            item["note_prerequisite"] = dict(prerequisite)
    for item in data.get("security_risk_profile", []) if isinstance(data.get("security_risk_profile"), list) else []:
        if isinstance(item, dict) and item.get("note_command"):
            item["note_prerequisite"] = dict(prerequisite)


def build_daily_command_queue(data: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen: Dict[str, Dict[str, object]] = {}
    actions = data.get("journal_actions", []) if isinstance(data.get("journal_actions"), list) else []
    archive = next((action for action in actions if isinstance(action, dict) and action.get("id") == "archive_current"), None)
    archive_command = str(archive.get("command")) if isinstance(archive, dict) and archive.get("command") else None
    archive_runnable = bool(archive.get("runnable")) if isinstance(archive, dict) else False
    archive_reason = str(archive.get("reason") or "") if isinstance(archive, dict) else ""

    def append_command(
        command: object,
        related: List[str],
        source: str,
        runnable: bool = True,
        unavailable_reason: Optional[str] = None,
        requires_prior_command: Optional[str] = None,
        run_after_rank: Optional[int] = None,
    ) -> Optional[Dict[str, object]]:
        if not command:
            return None
        text = str(command)
        if text in seen:
            existing = seen[text]
            existing["related_focus"] = dedupe_queue_texts(
                list(existing.get("related_focus", [])) + [item for item in related if item]
            )[:4]
            if runnable:
                existing["runnable"] = True
                existing.pop("unavailable_reason", None)
            return existing
        item = command_queue_item(text, len(rows) + 1, [item for item in related if item])
        item["runnable"] = bool(runnable)
        item["source"] = source
        if unavailable_reason and not runnable:
            item["unavailable_reason"] = unavailable_reason
        if requires_prior_command:
            item["requires_prior_command"] = requires_prior_command
        if run_after_rank is not None:
            item["run_after_rank"] = run_after_rank
        rows.append(item)
        seen[text] = item
        return item

    for task in data.get("review_tasks", []) if isinstance(data.get("review_tasks"), list) else []:
        if not isinstance(task, dict):
            continue
        related = [str(task.get("title") or task.get("id") or "复核任务")]
        commands = task.get("commands", []) if isinstance(task.get("commands"), list) else []
        for command in commands[:2]:
            append_command(command, related, "review_tasks")

    for item in data.get("security_review_queue", [])[:5] if isinstance(data.get("security_review_queue"), list) else []:
        if not isinstance(item, dict):
            continue
        related = ["%s %s" % (item.get("symbol"), item.get("name") or "") if item.get("symbol") else "标的复核"]
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        for command in commands[:2]:
            append_command(command, related, "security_review_queue")

    archive_item = None
    if archive_command:
        archive_item = append_command(
            archive_command,
            ["保存当前日报"],
            "journal_archive",
            runnable=archive_runnable,
            unavailable_reason=archive_reason or "需要先接入可保存的数据源。",
        )
    archive_rank = int(archive_item.get("rank")) if isinstance(archive_item, dict) and archive_item.get("rank") is not None else None

    for task in data.get("review_tasks", []) if isinstance(data.get("review_tasks"), list) else []:
        if not isinstance(task, dict) or not task.get("note_command"):
            continue
        append_command(
            task.get("note_command"),
            [str(task.get("title") or task.get("id") or "复核任务")],
            "review_task_note",
            runnable=archive_runnable,
            unavailable_reason=archive_reason or "记录复盘笔记前，需要先有一份日报留档。",
            requires_prior_command=archive_command,
            run_after_rank=archive_rank,
        )

    for item in data.get("security_review_queue", [])[:3] if isinstance(data.get("security_review_queue"), list) else []:
        if not isinstance(item, dict) or not item.get("note_command"):
            continue
        append_command(
            item.get("note_command"),
            ["%s %s" % (item.get("symbol"), item.get("name") or "") if item.get("symbol") else "标的复核"],
            "security_review_note",
            runnable=archive_runnable,
            unavailable_reason=archive_reason or "记录复盘笔记前，需要先有一份日报留档。",
            requires_prior_command=archive_command,
            run_after_rank=archive_rank,
        )

    for action in actions:
        if not isinstance(action, dict) or action.get("id") == "archive_current":
            continue
        append_command(
            action.get("command"),
            [str(action.get("title") or action.get("id") or "留档入口")],
            "journal_lookup",
            runnable=bool(action.get("runnable")),
            unavailable_reason=str(action.get("reason") or ""),
        )

    return rows[:24]


def dedupe_queue_texts(values: List[object]) -> List[str]:
    result = []
    for value in values:
        text = str(value or "")
        if text and text not in result:
            result.append(text)
    return result


def journal_action(action_id: str, title: str, command: str, runnable: bool, reason: str) -> Dict[str, object]:
    return {
        "id": action_id,
        "title": title,
        "command": command,
        "runnable": runnable,
        "reason": reason,
    }


def quote_command_arg(value: object) -> str:
    return shlex.quote(str(value))


def with_pool_arg(command: str, pool: str) -> str:
    if pool == DEFAULT_POOL or " --pool " in command:
        return command
    return "%s --pool %s" % (command, pool)


def resolve_quotes(use_mock: bool, quotes_file: Optional[str]):
    if quotes_file:
        path = Path(quotes_file)
        return load_quotes_file(path), "file", str(path)
    return load_mock_quotes(), "mock", "src/market_intel/fixtures/mock_quotes.json"


def resolve_holdings(use_mock: bool, holdings_file: Optional[str]):
    if holdings_file:
        path = Path(holdings_file)
        return load_holdings_file(path), "file", str(path)
    return load_mock_holdings(), "mock", "src/market_intel/fixtures/mock_holdings.json"


def pool_warnings(items: List[Any]) -> List[Dict[str, Any]]:
    warning_items = []
    for item in items:
        flags = item.to_dict()["data_quality_flags"]
        if flags:
            warning_items.append(
                {
                    "code": "DATA_QUALITY_FLAGS",
                    "message": "Pool item has data quality flags.",
                    "detail": {
                        "symbol": item.symbol,
                        "name": item.name,
                        "flags": flags,
                    },
                }
            )
    return warning_items


def print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
