import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


EMPTY_VALUES = {"", "-", "--", "nan", "none", "null", "无"}
SYMBOL_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")

QUOTE_ALIASES = {
    "symbol": ["symbol", "code", "ticker", "stock_code", "证券代码", "股票代码", "代码", "标的代码"],
    "name": ["name", "证券名称", "股票名称", "名称", "标的名称"],
    "trade_date": ["trade_date", "date", "日期", "交易日期", "行情日期"],
    "last_price": ["last_price", "price", "close", "最新价", "现价", "收盘价", "最新价格"],
    "change_pct": ["change_pct", "pct_chg", "pct_change", "涨跌幅", "涨幅", "今日涨幅"],
    "amount": ["amount", "turnover_value", "成交额", "成交金额", "成交额元"],
    "amount_ratio": ["amount_ratio", "volume_ratio", "量比", "成交放大", "成交放大倍数"],
    "turnover_rate": ["turnover_rate", "turnover", "换手率", "换手"],
    "amplitude_pct": ["amplitude_pct", "amplitude", "振幅"],
    "is_limit_up": ["is_limit_up", "limit_up", "涨停", "是否涨停"],
    "is_stage_high": ["is_stage_high", "stage_high", "阶段新高", "是否阶段新高"],
    "intraday_fade_pct": ["intraday_fade_pct", "fade_pct", "回落", "回落幅度", "冲高回落", "日内回落"],
    "source": ["source", "来源", "数据源"],
}

HOLDING_ALIASES = {
    "symbol": ["symbol", "code", "ticker", "stock_code", "证券代码", "股票代码", "代码", "标的代码"],
    "name": ["name", "证券名称", "股票名称", "名称", "持仓名称"],
    "quantity": ["quantity", "qty", "shares", "持仓数量", "持股数量", "数量", "可用数量"],
    "source": ["source", "来源", "数据源"],
}

UNIVERSE_ALIASES = {
    "symbol": ["symbol", "code", "ticker", "stock_code", "证券代码", "股票代码", "代码", "标的代码"],
    "name": ["name", "company", "证券名称", "股票名称", "名称", "公司名称"],
    "industry": ["industry", "行业", "申万行业", "中信行业", "所属行业"],
    "concepts": ["concepts", "concept", "概念", "主题", "概念板块", "题材"],
    "index_membership": ["index_membership", "indices", "index", "指数", "指数成分", "成分指数"],
    "listing_status": ["listing_status", "status", "上市状态", "状态"],
    "source": ["source", "来源", "数据源"],
}

RESEARCH_ALIASES = {
    "symbol": ["symbol", "code", "ticker", "stock_code", "证券代码", "股票代码", "代码", "标的代码"],
    "name": ["name", "company", "证券名称", "股票名称", "名称", "公司名称"],
    "status": ["status", "review_status", "研究状态", "状态"],
    "thesis": ["thesis", "logic", "核心逻辑", "研究结论", "逻辑"],
    "evidence": ["evidence", "key_evidence", "关键证据", "证据"],
    "invalidation": ["invalidation", "risk", "bear_case", "证伪风险", "风险"],
    "updated_at": ["updated_at", "date", "日期", "更新日期"],
    "source": ["source", "来源", "数据源"],
}


def import_quotes_csv(
    csv_path: Path,
    output_path: Optional[Path],
    dry_run: bool = False,
    default_trade_date: Optional[str] = None,
    runtime: bool = False,
) -> Dict[str, object]:
    rows, read_errors = read_csv_rows(csv_path)
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = list(read_errors)
    records: List[Dict[str, object]] = []
    trade_date = default_trade_date or datetime.now().astimezone().date().isoformat()

    if not errors:
        for index, row in enumerate(rows):
            record, row_warnings, row_errors = parse_quote_row(row, index, csv_path, trade_date)
            warnings.extend(row_warnings)
            errors.extend(row_errors)
            if record:
                records.append(record)
    if not errors and not records:
        errors.append(issue("NO_QUOTE_RECORDS", "CSV 中没有可导入的行情记录。", {"path": command_path(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_json_records(output_path, "quotes", records)
        written = True

    return {
        "kind": "quotes",
        "input": command_path(csv_path),
        "output": command_path(output_path) if output_path else None,
        "record_key": "quotes",
        "record_count": len(records),
        "dry_run": dry_run,
        "written": written,
        "preview": records[:5],
        "canonical_schema": quote_schema(),
        "next_commands": next_commands("quotes", csv_path, written, dry_run, runtime, output_path, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def import_holdings_csv(
    csv_path: Path,
    output_path: Optional[Path],
    dry_run: bool = False,
    runtime: bool = False,
) -> Dict[str, object]:
    rows, read_errors = read_csv_rows(csv_path)
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = list(read_errors)
    records: List[Dict[str, object]] = []

    if not errors:
        for index, row in enumerate(rows):
            record, row_warnings, row_errors = parse_holding_row(row, index, csv_path)
            warnings.extend(row_warnings)
            errors.extend(row_errors)
            if record:
                records.append(record)
    if not errors and not records:
        errors.append(issue("NO_HOLDING_RECORDS", "CSV 中没有可导入的持仓记录。", {"path": command_path(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_json_records(output_path, "holdings", records)
        written = True

    return {
        "kind": "holdings",
        "input": command_path(csv_path),
        "output": command_path(output_path) if output_path else None,
        "record_key": "holdings",
        "record_count": len(records),
        "dry_run": dry_run,
        "written": written,
        "preview": records[:5],
        "canonical_schema": holding_schema(),
        "next_commands": next_commands("holdings", csv_path, written, dry_run, runtime, output_path, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def import_universe_csv(
    csv_path: Path,
    output_path: Optional[Path],
    dry_run: bool = False,
    runtime: bool = False,
    merge: bool = False,
) -> Dict[str, object]:
    rows, read_errors = read_csv_rows(csv_path)
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = list(read_errors)
    records: List[Dict[str, object]] = []

    if not errors:
        for index, row in enumerate(rows):
            record, row_warnings, row_errors = parse_universe_row(row, index, csv_path)
            warnings.extend(row_warnings)
            errors.extend(row_errors)
            if record:
                records.append(record)
    if not errors and not records:
        errors.append(issue("NO_UNIVERSE_RECORDS", "CSV 中没有可导入的 A 股基础清单记录。", {"path": command_path(csv_path)}))

    target_records = universe_target_records(output_path, records, merge) if not errors else []
    coverage_delta = (
        universe_coverage_delta(output_path, records, target_records, merge)
        if not errors
        else empty_universe_coverage_delta(output_path, merge)
    )
    if not errors and dry_run:
        warnings.extend(universe_dry_run_warnings(coverage_delta))
    written = False
    if not errors and not dry_run and output_path is not None:
        write_universe_csv(output_path, target_records)
        written = True

    return {
        "kind": "universe",
        "input": command_path(csv_path),
        "output": command_path(output_path) if output_path else None,
        "record_key": "universe",
        "record_count": len(records),
        "target_record_count": len(target_records),
        "write_mode": "merge" if merge else "replace",
        "dry_run": dry_run,
        "written": written,
        "preview": records[:5],
        "canonical_schema": universe_schema(),
        "coverage_delta": coverage_delta,
        "next_commands": universe_next_commands(csv_path, written, dry_run, runtime, output_path, coverage_delta, merge, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def import_research_csv(
    csv_path: Path,
    output_path: Optional[Path],
    dry_run: bool = False,
    runtime: bool = False,
) -> Dict[str, object]:
    rows, read_errors = read_csv_rows(csv_path)
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = list(read_errors)
    records: List[Dict[str, object]] = []

    if not errors:
        for index, row in enumerate(rows):
            record, row_warnings, row_errors = parse_research_row(row, index, csv_path)
            warnings.extend(row_warnings)
            errors.extend(row_errors)
            if record:
                records.append(record)
    if not errors and not records:
        errors.append(issue("NO_RESEARCH_RECORDS", "CSV 中没有可导入的研究证据记录。", {"path": command_path(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_research_csv(output_path, records)
        written = True

    return {
        "kind": "research",
        "input": command_path(csv_path),
        "output": command_path(output_path) if output_path else None,
        "record_key": "research",
        "record_count": len(records),
        "dry_run": dry_run,
        "written": written,
        "preview": records[:5],
        "canonical_schema": research_schema(),
        "next_commands": next_commands("research", csv_path, written, dry_run, runtime, output_path, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def import_schema() -> Dict[str, object]:
    return {
        "quotes": {
            "record_key": "quotes",
            "accepted_columns": QUOTE_ALIASES,
            "canonical_schema": quote_schema(),
            "defaults": {
                "name": "缺失时使用 symbol",
                "trade_date": "命令执行日期，可用 --trade-date 覆盖",
                "last_price": None,
                "change_pct": 0,
                "amount": 0,
                "amount_ratio": 1,
                "turnover_rate": 0,
                "amplitude_pct": 0,
                "is_limit_up": "change_pct >= 9.5 时默认 true，否则 false",
                "is_stage_high": False,
                "intraday_fade_pct": 0,
                "source": "csv:<filename>",
            },
            "example_commands": [
                "market-intel import quotes examples/quotes.csv.example --runtime --dry-run --json",
                "market-intel import quotes examples/quotes.csv.example --runtime --json",
                "market-intel import quotes quotes.csv --output data/runtime/quotes.json --json",
                "market-intel import quotes quotes.csv --dry-run --json",
            ],
        },
        "holdings": {
            "record_key": "holdings",
            "accepted_columns": HOLDING_ALIASES,
            "canonical_schema": holding_schema(),
            "defaults": {
                "name": "缺失时使用 symbol",
                "quantity": None,
                "source": "csv:<filename>",
            },
            "example_commands": [
                "market-intel import holdings examples/holdings.csv.example --runtime --dry-run --json",
                "market-intel import holdings examples/holdings.csv.example --runtime --json",
                "market-intel import holdings holdings.csv --output data/runtime/holdings.json --json",
                "market-intel import holdings holdings.csv --dry-run --json",
            ],
        },
        "universe": {
            "record_key": "universe",
            "accepted_columns": UNIVERSE_ALIASES,
            "canonical_schema": universe_schema(),
            "defaults": {
                "industry": "行业待补",
                "concepts": "",
                "index_membership": "",
                "listing_status": "listed",
                "source": "csv:<filename>",
            },
            "example_commands": [
                "market-intel import universe examples/a_share_universe.csv.example --runtime --dry-run --json",
                "market-intel import universe examples/a_share_universe.csv.example --runtime --json",
                "market-intel import universe a_share_universe.csv --output data/runtime/a_share_universe.csv --json",
                "market-intel import universe a_share_universe.csv --dry-run --json",
                "market-intel import universe a_share_universe_patch.csv --runtime --merge --dry-run --json",
            ],
        },
        "research": {
            "record_key": "research",
            "accepted_columns": RESEARCH_ALIASES,
            "canonical_schema": research_schema(),
            "defaults": {
                "name": "缺失时使用 symbol",
                "status": "draft",
                "source": "csv:<filename>",
            },
            "example_commands": [
                "market-intel import research examples/research_notes.csv.example --runtime --dry-run --json",
                "market-intel import research examples/research_notes.csv.example --runtime --json",
                "market-intel import research research_notes.csv --output data/runtime/research_notes.csv --json",
                "market-intel import research research_notes.csv --dry-run --json",
            ],
        },
        "agent_contract": {
            "output": "JSON envelope",
            "success": "ok=true 且 errors=[]",
            "warnings": "warnings 为可继续但需要复核的问题",
            "errors": "errors 非空时不会写入输出文件",
            "stable_fields": [
                "data.record_count",
                "data.target_record_count",
                "data.write_mode",
                "data.preview",
                "data.canonical_schema",
                "data.next_commands",
            ],
            "universe_stable_fields": [
                "data.coverage_delta",
                "data.coverage_delta.write_mode",
                "data.coverage_delta.before",
                "data.coverage_delta.after",
                "data.coverage_delta.changed_symbol_count",
                "data.coverage_delta.removed_symbol_count",
                "data.coverage_delta.improvement",
                "data.coverage_delta.improvement.improved_fields",
                "data.coverage_delta.recommendation",
                "data.coverage_delta.recommendation.requires_import",
            ],
            "follow_up": "写入 runtime 后可执行 market-intel validate runtime --json 和 market-intel daily --runtime --json",
        },
    }


def parse_quote_row(
    row: Dict[str, str],
    index: int,
    csv_path: Path,
    default_trade_date: str,
) -> Tuple[Optional[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    symbol = normalize_symbol(get_value(row, QUOTE_ALIASES["symbol"]))
    if not symbol:
        return None, warnings, [issue("MISSING_SYMBOL", "行情记录缺少证券代码。", {"index": index})]
    name = get_value(row, QUOTE_ALIASES["name"])
    if is_empty(name):
        name = symbol
        warnings.append(default_warning("QUOTE_NAME_DEFAULTED", index, symbol, "name", name))

    trade_date = get_value(row, QUOTE_ALIASES["trade_date"])
    if is_empty(trade_date):
        trade_date = default_trade_date
        warnings.append(default_warning("TRADE_DATE_DEFAULTED", index, symbol, "trade_date", trade_date))

    change_pct = numeric_field(row, QUOTE_ALIASES["change_pct"], "change_pct", index, symbol, 0, warnings, errors)
    amount = numeric_field(row, QUOTE_ALIASES["amount"], "amount", index, symbol, 0, warnings, errors)
    amount_ratio = numeric_field(row, QUOTE_ALIASES["amount_ratio"], "amount_ratio", index, symbol, 1, warnings, errors)
    turnover_rate = numeric_field(row, QUOTE_ALIASES["turnover_rate"], "turnover_rate", index, symbol, 0, warnings, errors)
    amplitude_pct = numeric_field(row, QUOTE_ALIASES["amplitude_pct"], "amplitude_pct", index, symbol, 0, warnings, errors)
    intraday_fade_pct = numeric_field(
        row,
        QUOTE_ALIASES["intraday_fade_pct"],
        "intraday_fade_pct",
        index,
        symbol,
        0,
        warnings,
        errors,
    )
    last_price = optional_numeric_field(row, QUOTE_ALIASES["last_price"], "last_price", index, symbol, errors)
    is_limit_up = bool_field(
        row,
        QUOTE_ALIASES["is_limit_up"],
        "is_limit_up",
        index,
        symbol,
        default=change_pct >= 9.5,
        warnings=warnings,
        errors=errors,
    )
    is_stage_high = bool_field(
        row,
        QUOTE_ALIASES["is_stage_high"],
        "is_stage_high",
        index,
        symbol,
        default=False,
        warnings=warnings,
        errors=errors,
    )

    if errors:
        return None, warnings, errors

    return {
        "symbol": symbol,
        "name": str(name),
        "trade_date": str(trade_date),
        "last_price": last_price,
        "change_pct": change_pct,
        "amount": amount,
        "amount_ratio": amount_ratio,
        "turnover_rate": turnover_rate,
        "amplitude_pct": amplitude_pct,
        "is_limit_up": is_limit_up,
        "is_stage_high": is_stage_high,
        "intraday_fade_pct": intraday_fade_pct,
        "source": get_value(row, QUOTE_ALIASES["source"]) or "csv:%s" % csv_path.name,
    }, warnings, errors


def parse_holding_row(
    row: Dict[str, str],
    index: int,
    csv_path: Path,
) -> Tuple[Optional[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    symbol = normalize_symbol(get_value(row, HOLDING_ALIASES["symbol"]))
    if not symbol:
        return None, warnings, [issue("MISSING_SYMBOL", "持仓记录缺少证券代码。", {"index": index})]

    name = get_value(row, HOLDING_ALIASES["name"])
    if is_empty(name):
        name = symbol
        warnings.append(default_warning("HOLDING_NAME_DEFAULTED", index, symbol, "name", name))
    quantity = optional_numeric_field(row, HOLDING_ALIASES["quantity"], "quantity", index, symbol, errors)

    if errors:
        return None, warnings, errors

    return {
        "symbol": symbol,
        "name": str(name),
        "quantity": quantity,
        "source": get_value(row, HOLDING_ALIASES["source"]) or "csv:%s" % csv_path.name,
    }, warnings, errors


def parse_universe_row(
    row: Dict[str, str],
    index: int,
    csv_path: Path,
) -> Tuple[Optional[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    symbol = normalize_symbol(get_value(row, UNIVERSE_ALIASES["symbol"]))
    if not symbol:
        return None, warnings, [issue("MISSING_SYMBOL", "A 股基础清单记录缺少证券代码。", {"index": index})]
    if not re.match(r"^\d{6}$", symbol):
        return None, warnings, [
            issue("INVALID_UNIVERSE_SYMBOL", "A 股基础清单只接受 6 位 A 股代码。", {"index": index, "symbol": symbol})
        ]

    name = get_value(row, UNIVERSE_ALIASES["name"])
    if is_empty(name):
        name = symbol
        warnings.append(default_warning("UNIVERSE_NAME_DEFAULTED", index, symbol, "name", name))
    industry = get_value(row, UNIVERSE_ALIASES["industry"])
    if is_empty(industry):
        industry = "行业待补"
        warnings.append(default_warning("UNIVERSE_FIELD_DEFAULTED", index, symbol, "industry", industry))
    listing_status = get_value(row, UNIVERSE_ALIASES["listing_status"])
    if is_empty(listing_status):
        listing_status = "listed"
        warnings.append(default_warning("UNIVERSE_FIELD_DEFAULTED", index, symbol, "listing_status", listing_status))

    return {
        "symbol": symbol,
        "name": str(name),
        "industry": str(industry),
        "concepts": get_value(row, UNIVERSE_ALIASES["concepts"]) or "",
        "index_membership": get_value(row, UNIVERSE_ALIASES["index_membership"]) or "",
        "listing_status": str(listing_status),
        "source": get_value(row, UNIVERSE_ALIASES["source"]) or "csv:%s" % csv_path.name,
    }, warnings, errors


def parse_research_row(
    row: Dict[str, str],
    index: int,
    csv_path: Path,
) -> Tuple[Optional[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    symbol = normalize_symbol(get_value(row, RESEARCH_ALIASES["symbol"]))
    if not symbol:
        return None, warnings, [issue("MISSING_SYMBOL", "研究证据记录缺少证券代码。", {"index": index})]
    if not re.match(r"^\d{6}$", symbol):
        return None, warnings, [
            issue("INVALID_RESEARCH_SYMBOL", "研究证据当前只接受 6 位 A 股代码。", {"index": index, "symbol": symbol})
        ]

    name = get_value(row, RESEARCH_ALIASES["name"])
    if is_empty(name):
        name = symbol
        warnings.append(default_warning("RESEARCH_NAME_DEFAULTED", index, symbol, "name", name))
    status = normalize_research_status(get_value(row, RESEARCH_ALIASES["status"]))
    thesis = get_value(row, RESEARCH_ALIASES["thesis"]) or ""
    evidence = get_value(row, RESEARCH_ALIASES["evidence"]) or ""
    invalidation = get_value(row, RESEARCH_ALIASES["invalidation"]) or ""
    if status in {"reviewed", "confirmed"}:
        for field, value in (("thesis", thesis), ("evidence", evidence), ("invalidation", invalidation)):
            if is_empty(value):
                errors.append(
                    issue(
                        "RESEARCH_REVIEWED_FIELD_MISSING",
                        "已复核研究证据缺少必填字段。",
                        {"index": index, "symbol": symbol, "field": field},
                    )
                )
    if errors:
        return None, warnings, errors

    return {
        "symbol": symbol,
        "name": str(name),
        "status": status,
        "thesis": str(thesis),
        "evidence": str(evidence),
        "invalidation": str(invalidation),
        "updated_at": get_value(row, RESEARCH_ALIASES["updated_at"]) or "",
        "source": get_value(row, RESEARCH_ALIASES["source"]) or "csv:%s" % csv_path.name,
    }, warnings, errors


def normalize_research_status(value: Optional[str]) -> str:
    text = str(value or "").strip().lower()
    if text in {"reviewed", "confirmed", "已复核", "已确认", "确认"}:
        return "reviewed"
    if text in {"blocked", "invalid", "驳回", "阻塞"}:
        return "blocked"
    return "draft"


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, object]]]:
    if not path.exists():
        return [], [issue("CSV_FILE_NOT_FOUND", "CSV 文件不存在。", {"path": command_path(path)})]
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return [], [issue("CSV_HEADER_MISSING", "CSV 缺少表头。", {"path": command_path(path)})]
            return list(reader), []
    except Exception as exc:
        return [], [issue("CSV_READ_ERROR", str(exc), {"path": command_path(path)})]


def write_json_records(path: Path, key: str, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({key: records}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_universe_csv(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [row["field"] for row in universe_schema()]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def write_research_csv(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [row["field"] for row in research_schema()]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


UNIVERSE_PLACEHOLDERS = {
    "industry": {"行业待补", "待补", "unknown", "未知"},
    "concepts": {"概念待补", "待补", "unknown", "未知"},
    "index_membership": {"指数待补", "指数成分待补", "待补", "unknown", "未知"},
}


def universe_target_records(
    output_path: Optional[Path],
    records: List[Dict[str, object]],
    merge: bool,
) -> List[Dict[str, object]]:
    existing_records = read_existing_universe_records(output_path)
    if not merge:
        return records
    merged_by_symbol = {str(record.get("symbol") or ""): dict(record) for record in existing_records if record.get("symbol")}
    order = [str(record.get("symbol") or "") for record in existing_records if record.get("symbol")]
    for record in records:
        symbol = str(record.get("symbol") or "")
        if not symbol:
            continue
        if symbol not in merged_by_symbol:
            merged_by_symbol[symbol] = dict(record)
            order.append(symbol)
            continue
        merged_by_symbol[symbol] = merge_universe_record(merged_by_symbol[symbol], record)
    return [merged_by_symbol[symbol] for symbol in order]


def merge_universe_record(existing: Dict[str, object], incoming: Dict[str, object]) -> Dict[str, object]:
    merged = dict(existing)
    merged["symbol"] = incoming.get("symbol") or existing.get("symbol")
    changed = False
    for field in ("industry", "concepts", "index_membership"):
        value = incoming.get(field)
        if universe_field_present(value, field):
            changed = changed or merged.get(field) != value
            merged[field] = value
    name = incoming.get("name")
    if universe_merge_name_present(name, incoming.get("symbol"), existing):
        changed = changed or merged.get("name") != name
        merged["name"] = name
    listing_status = incoming.get("listing_status")
    if universe_merge_listing_status_present(listing_status, existing):
        changed = changed or merged.get("listing_status") != listing_status
        merged["listing_status"] = listing_status
    if changed and not is_empty(incoming.get("source")):
        merged["source"] = incoming.get("source")
    return merged


def universe_merge_name_present(value: object, symbol: object, existing: Dict[str, object]) -> bool:
    if is_empty(value):
        return False
    text = str(value).strip()
    symbol_text = str(symbol or "").strip()
    existing_name = str(existing.get("name") or "").strip()
    if symbol_text and text == symbol_text and existing_name and existing_name != text:
        return False
    return True


def universe_merge_listing_status_present(value: object, existing: Dict[str, object]) -> bool:
    if is_empty(value):
        return False
    text = str(value).strip()
    if text == "listed" and not is_empty(existing.get("listing_status")):
        return False
    return not is_empty(value)


def universe_coverage_delta(
    output_path: Optional[Path],
    records: List[Dict[str, object]],
    target_records: List[Dict[str, object]],
    merge: bool,
) -> Dict[str, object]:
    existing_records = read_existing_universe_records(output_path)
    existing_by_symbol = {str(record.get("symbol") or ""): record for record in existing_records if record.get("symbol")}
    incoming_by_symbol = {str(record.get("symbol") or ""): record for record in records if record.get("symbol")}
    target_by_symbol = {str(record.get("symbol") or ""): record for record in target_records if record.get("symbol")}
    existing_symbols = set(existing_by_symbol)
    incoming_symbols = set(incoming_by_symbol)
    target_symbols = set(target_by_symbol)
    removed_symbols = sorted(existing_symbols - target_symbols)
    before = universe_field_coverage_summary(list(existing_by_symbol.values()))
    after = universe_field_coverage_summary(target_records)
    improvement = universe_coverage_improvement(before, after)
    changed_samples = universe_changed_samples(existing_by_symbol, target_by_symbol)
    changed_field_count = sum(len(sample["changed_fields"]) for sample in changed_samples)
    removed_samples = [universe_removed_symbol_sample(existing_by_symbol[symbol]) for symbol in removed_symbols[:5]]
    return {
        "available": bool(records),
        "target": command_path(output_path) if output_path else None,
        "write_mode": "merge" if merge else "replace",
        "existing_record_count": len(existing_by_symbol),
        "incoming_record_count": len(records),
        "after_record_count": len(target_records),
        "new_symbol_count": len(incoming_symbols - existing_symbols),
        "updated_symbol_count": len(incoming_symbols & existing_symbols),
        "changed_symbol_count": len(changed_samples),
        "changed_field_count": changed_field_count,
        "changed_samples": changed_samples[:5],
        "removed_symbol_count": len(removed_symbols),
        "removed_samples": removed_samples,
        "before": before,
        "after": after,
        "improvement": improvement,
        "recommendation": universe_delta_recommendation(improvement, after, len(removed_symbols), len(changed_samples)),
        "done_when": "dry-run 预估显示目标字段缺口减少；正式导入后运行 market-intel pool coverage --runtime --json 复验 universe.enrichment_queue。",
    }


def empty_universe_coverage_delta(output_path: Optional[Path], merge: bool = False) -> Dict[str, object]:
    return {
        "available": False,
        "target": command_path(output_path) if output_path else None,
        "write_mode": "merge" if merge else "replace",
        "existing_record_count": 0,
        "incoming_record_count": 0,
        "after_record_count": 0,
        "new_symbol_count": 0,
        "updated_symbol_count": 0,
        "changed_symbol_count": 0,
        "changed_field_count": 0,
        "changed_samples": [],
        "removed_symbol_count": 0,
        "removed_samples": [],
        "before": universe_field_coverage_summary([]),
        "after": universe_field_coverage_summary([]),
        "improvement": {
            "record_count_delta": 0,
            "covered_count_delta": {"industry": 0, "concepts": 0, "index_membership": 0},
            "missing_count_delta": {"industry": 0, "concepts": 0, "index_membership": 0},
            "improved_fields": [],
            "state": "no_valid_records",
            "summary": "未解析到可用于预估的 A 股基础清单记录。",
        },
        "recommendation": {
            "action": "fix_csv",
            "reason": "没有可用于预估的有效记录。",
            "requires_import": False,
        },
        "done_when": "修复 CSV 错误后重新 dry-run。",
    }


def read_existing_universe_records(output_path: Optional[Path]) -> List[Dict[str, object]]:
    if output_path is None or not output_path.exists():
        return []
    rows, errors = read_csv_rows(output_path)
    if errors:
        return []
    records = []
    for index, row in enumerate(rows):
        record, _, row_errors = parse_universe_row(row, index, output_path)
        if record and not row_errors:
            records.append(record)
    return records


def universe_field_coverage_summary(records: List[Dict[str, object]]) -> Dict[str, object]:
    total = len(records)
    covered = {field: 0 for field in ("industry", "concepts", "index_membership")}
    missing_samples = []
    for record in records:
        missing_fields = []
        for field in covered:
            if universe_field_present(record.get(field), field):
                covered[field] += 1
            else:
                missing_fields.append(field)
        if missing_fields and len(missing_samples) < 5:
            missing_samples.append(
                {
                    "symbol": record.get("symbol"),
                    "name": record.get("name"),
                    "missing_fields": missing_fields,
                }
            )
    missing = {field: total - count for field, count in covered.items()}
    ratios = {field: coverage_ratio(count, total) for field, count in covered.items()}
    return {
        "record_count": total,
        "covered_count": covered,
        "missing_count": missing,
        "coverage_ratio": ratios,
        "missing_samples": missing_samples,
    }


def universe_coverage_improvement(before: Dict[str, object], after: Dict[str, object]) -> Dict[str, object]:
    fields = ("industry", "concepts", "index_membership")
    before_covered = before.get("covered_count", {}) if isinstance(before.get("covered_count"), dict) else {}
    after_covered = after.get("covered_count", {}) if isinstance(after.get("covered_count"), dict) else {}
    before_missing = before.get("missing_count", {}) if isinstance(before.get("missing_count"), dict) else {}
    after_missing = after.get("missing_count", {}) if isinstance(after.get("missing_count"), dict) else {}
    covered_delta = {field: int(after_covered.get(field, 0)) - int(before_covered.get(field, 0)) for field in fields}
    missing_delta = {field: int(after_missing.get(field, 0)) - int(before_missing.get(field, 0)) for field in fields}
    improved_fields = [field for field in fields if covered_delta[field] > 0 or missing_delta[field] < 0]
    state = "improved" if improved_fields else "unchanged"
    return {
        "record_count_delta": int(after.get("record_count", 0)) - int(before.get("record_count", 0)),
        "covered_count_delta": covered_delta,
        "missing_count_delta": missing_delta,
        "improved_fields": improved_fields,
        "state": state,
        "summary": universe_improvement_summary(state, improved_fields, covered_delta, missing_delta),
    }


def universe_removed_symbol_sample(record: Dict[str, object]) -> Dict[str, object]:
    return {
        "symbol": record.get("symbol"),
        "name": record.get("name"),
    }


def universe_changed_samples(
    existing_by_symbol: Dict[str, Dict[str, object]],
    target_by_symbol: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    samples = []
    fields = ("name", "industry", "concepts", "index_membership", "listing_status")
    for symbol in sorted(set(existing_by_symbol) & set(target_by_symbol)):
        existing = existing_by_symbol[symbol]
        target = target_by_symbol[symbol]
        changed_fields = [
            field
            for field in fields
            if normalize_universe_compare_value(existing.get(field)) != normalize_universe_compare_value(target.get(field))
        ]
        if changed_fields:
            samples.append(
                {
                    "symbol": symbol,
                    "name": target.get("name") or existing.get("name"),
                    "changed_fields": changed_fields,
                }
            )
    return samples


def normalize_universe_compare_value(value: object) -> str:
    return str(value or "").strip()


def universe_delta_recommendation(
    improvement: Dict[str, object],
    after: Dict[str, object],
    removed_symbol_count: int,
    changed_symbol_count: int = 0,
) -> Dict[str, object]:
    after_missing = after.get("missing_count", {}) if isinstance(after.get("missing_count"), dict) else {}
    remaining_missing = sum(int(after_missing.get(field, 0)) for field in ("industry", "concepts", "index_membership"))
    if removed_symbol_count:
        return {
            "action": "review_removed_symbols_before_import",
            "reason": "dry-run 会移除已有 A 股基础清单标的 %s 个；请确认 CSV 是完整清单后再正式导入。" % removed_symbol_count,
            "requires_import": False,
        }
    if improvement.get("state") != "improved":
        if changed_symbol_count:
            return {
                "action": "import_value_updates",
                "reason": "dry-run 不减少字段缺口，但会更新 %s 个已有标的的基础字段；建议导入后复验。" % changed_symbol_count,
                "requires_import": True,
            }
        if not remaining_missing:
            return {
                "action": "skip_import",
                "reason": "dry-run 未带来新的字段覆盖改善，当前目标字段也没有缺口；无需正式导入。",
                "requires_import": False,
            }
        return {
            "action": "review_enrichment_queue",
            "reason": "dry-run 未减少行业、概念或指数成分缺口；不建议直接正式导入。",
            "requires_import": False,
        }
    if remaining_missing:
        return {
            "action": "import_then_continue_enrichment",
            "reason": "dry-run 会减少部分字段缺口，但导入后仍有 %s 个字段缺口需继续补数。" % remaining_missing,
            "requires_import": True,
        }
    return {
        "action": "import_and_verify",
        "reason": "dry-run 会关闭当前目标中的行业、概念和指数成分字段缺口。",
        "requires_import": True,
    }


def universe_dry_run_warnings(coverage_delta: Dict[str, object]) -> List[Dict[str, object]]:
    warnings = []
    recommendation = coverage_delta.get("recommendation", {}) if isinstance(coverage_delta.get("recommendation"), dict) else {}
    action = recommendation.get("action")
    if action == "review_removed_symbols_before_import":
        warnings.append(
            issue(
                "UNIVERSE_DRY_RUN_REMOVES_EXISTING_SYMBOLS",
                "dry-run 会移除已有 A 股基础清单标的，不建议直接正式导入。",
                {
                    "recommendation": action,
                    "removed_symbol_count": int(coverage_delta.get("removed_symbol_count") or 0),
                    "removed_samples": coverage_delta.get("removed_samples", []),
                },
            )
        )
    if action in {"review_enrichment_queue", "skip_import"}:
        warnings.append(
            issue(
                "UNIVERSE_DRY_RUN_NO_COVERAGE_IMPROVEMENT",
                "dry-run 未减少 A 股基础清单字段覆盖缺口，不建议直接正式导入。",
                {
                    "recommendation": action,
                },
            )
        )
    if action == "import_then_continue_enrichment":
        after = coverage_delta.get("after", {}) if isinstance(coverage_delta.get("after"), dict) else {}
        missing = after.get("missing_count", {}) if isinstance(after.get("missing_count"), dict) else {}
        warnings.append(
            issue(
                "UNIVERSE_DRY_RUN_PARTIAL_COVERAGE_IMPROVEMENT",
                "dry-run 会减少部分字段覆盖缺口，但导入后仍需继续补数。",
                {
                    "recommendation": action,
                    "remaining_missing_count": sum(int(missing.get(field, 0)) for field in ("industry", "concepts", "index_membership")),
                },
            )
        )
    return warnings


def universe_improvement_summary(
    state: str,
    improved_fields: List[str],
    covered_delta: Dict[str, int],
    missing_delta: Dict[str, int],
) -> str:
    if state != "improved":
        return "本次导入未改善行业、概念或指数成分字段覆盖。"
    parts = []
    labels = {"industry": "行业", "concepts": "概念", "index_membership": "指数成分"}
    for field in improved_fields:
        parts.append("%s 覆盖 +%s，缺口 %+d" % (labels[field], covered_delta[field], missing_delta[field]))
    return "；".join(parts)


def universe_field_present(value: object, field: str) -> bool:
    text = str(value or "").strip()
    if is_empty(text):
        return False
    normalized = text.lower()
    placeholders = {item.lower() for item in UNIVERSE_PLACEHOLDERS.get(field, set())}
    if normalized in placeholders:
        return False
    if field in {"concepts", "index_membership"}:
        return any(part.lower() not in placeholders for part in split_universe_values(text))
    return True


def split_universe_values(value: object) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = []
    for chunk in text.replace("，", ";").replace(",", ";").replace("|", ";").replace("/", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def coverage_ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0


def quote_schema() -> List[Dict[str, object]]:
    return [
        {"field": "symbol", "type": "string", "required": True},
        {"field": "name", "type": "string", "required": False},
        {"field": "trade_date", "type": "string", "required": True},
        {"field": "last_price", "type": "number|null", "required": False},
        {"field": "change_pct", "type": "number", "required": True},
        {"field": "amount", "type": "number", "required": True},
        {"field": "amount_ratio", "type": "number", "required": True},
        {"field": "turnover_rate", "type": "number", "required": True},
        {"field": "amplitude_pct", "type": "number", "required": True},
        {"field": "is_limit_up", "type": "boolean", "required": True},
        {"field": "is_stage_high", "type": "boolean", "required": True},
        {"field": "intraday_fade_pct", "type": "number", "required": True},
        {"field": "source", "type": "string", "required": False},
    ]


def holding_schema() -> List[Dict[str, object]]:
    return [
        {"field": "symbol", "type": "string", "required": True},
        {"field": "name", "type": "string", "required": True},
        {"field": "quantity", "type": "number|null", "required": False},
        {"field": "source", "type": "string", "required": False},
    ]


def universe_schema() -> List[Dict[str, object]]:
    return [
        {"field": "symbol", "type": "string", "required": True},
        {"field": "name", "type": "string", "required": True},
        {"field": "industry", "type": "string", "required": True},
        {"field": "concepts", "type": "string", "required": False},
        {"field": "index_membership", "type": "string", "required": False},
        {"field": "listing_status", "type": "string", "required": False},
        {"field": "source", "type": "string", "required": False},
    ]


def research_schema() -> List[Dict[str, object]]:
    return [
        {"field": "symbol", "type": "string", "required": True},
        {"field": "name", "type": "string", "required": True},
        {"field": "status", "type": "draft|reviewed|blocked", "required": True},
        {"field": "thesis", "type": "string", "required": "status=reviewed"},
        {"field": "evidence", "type": "string", "required": "status=reviewed"},
        {"field": "invalidation", "type": "string", "required": "status=reviewed"},
        {"field": "updated_at", "type": "string", "required": False},
        {"field": "source", "type": "string", "required": False},
    ]


def next_commands(
    kind: str,
    csv_path: Path,
    written: bool,
    dry_run: bool,
    runtime: bool,
    output_path: Optional[Path],
    has_errors: bool = False,
) -> List[str]:
    if has_errors:
        return []
    if dry_run and runtime:
        import_command = "market-intel import %s %s --runtime --json" % (kind, command_path(csv_path))
        if kind == "research":
            return [
                import_command,
                "market-intel pool coverage --runtime --text",
                "market-intel agent next --text",
            ]
        return [
            import_command,
            "market-intel status runtime --json",
            "market-intel dashboard --text",
        ]
    if not written:
        return []
    path_text = command_path(output_path) if output_path else ""
    if not runtime:
        if kind == "quotes":
            return [
                "market-intel hotspots --quotes-file %s --json" % path_text,
                "market-intel daily --quotes-file %s --holdings-file <holdings.json> --json" % path_text,
            ]
        if kind == "universe":
            return [
                "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=%s market-intel pool coverage --text" % path_text,
                "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=%s market-intel pool coverage --runtime --text" % path_text,
            ]
        if kind == "research":
            return [
                "MARKET_INTEL_RESEARCH_NOTES_PATHS=%s market-intel pool coverage --runtime --text" % path_text,
                "MARKET_INTEL_RESEARCH_NOTES_PATHS=%s market-intel agent next --text" % path_text,
            ]
        return [
            "market-intel holdings impact --holdings-file %s --json" % path_text,
            "market-intel daily --quotes-file <quotes.json> --holdings-file %s --json" % path_text,
        ]
    if kind == "research":
        return [
            "market-intel pool coverage --runtime --text",
            "market-intel agent next --text",
            "market-intel journal note --section security_review --text '<填写研究证据确认>'",
        ]
    if kind == "universe":
        return [
            "market-intel pool coverage --text",
            "market-intel pool coverage --runtime --text",
            "market-intel focus --runtime --text",
        ]
    return [
        "market-intel validate runtime --json",
        "market-intel daily --runtime --json",
        "market-intel daily --runtime --text",
    ]


def universe_next_commands(
    csv_path: Path,
    written: bool,
    dry_run: bool,
    runtime: bool,
    output_path: Optional[Path],
    coverage_delta: Dict[str, object],
    merge: bool = False,
    has_errors: bool = False,
) -> List[str]:
    if has_errors:
        return []
    if written:
        return next_commands("universe", csv_path, written, dry_run, runtime, output_path, has_errors)
    if not dry_run:
        return []
    improvement = coverage_delta.get("improvement", {}) if isinstance(coverage_delta.get("improvement"), dict) else {}
    recommendation = coverage_delta.get("recommendation", {}) if isinstance(coverage_delta.get("recommendation"), dict) else {}
    if recommendation.get("action") == "review_removed_symbols_before_import":
        if runtime:
            return [
                "market-intel import universe <full_a_share_universe.csv> --runtime --dry-run --json"
                if not merge
                else "market-intel import universe %s --runtime --merge --dry-run --json" % command_path(csv_path),
                "market-intel pool coverage --runtime --json",
            ]
        if output_path:
            return [
                "market-intel import universe <full_a_share_universe.csv> --output %s --dry-run --json" % command_path(output_path)
                if not merge
                else "market-intel import universe %s --output %s --merge --dry-run --json"
                % (command_path(csv_path), command_path(output_path)),
                "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=%s market-intel pool coverage --text" % command_path(output_path),
            ]
        return [
            "market-intel import universe <full_a_share_universe.csv> --dry-run --json"
            if not merge
            else "market-intel import universe %s --merge --dry-run --json" % command_path(csv_path),
            "market-intel pool coverage --json",
        ]
    if recommendation.get("requires_import") is True:
        import_command = "market-intel import universe %s --json" % command_path(csv_path)
        if merge:
            import_command = "market-intel import universe %s --merge --json" % command_path(csv_path)
        if runtime:
            import_command = "market-intel import universe %s --runtime --json" % command_path(csv_path)
            if merge:
                import_command = "market-intel import universe %s --runtime --merge --json" % command_path(csv_path)
            return [
                import_command,
                "market-intel pool coverage --runtime --json",
                "market-intel dashboard --text",
            ]
        if output_path:
            return [
                "%s --output %s" % (import_command, command_path(output_path)),
                "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=%s market-intel pool coverage --text" % command_path(output_path),
            ]
        return [
            "market-intel import universe %s --runtime --merge --json" % command_path(csv_path)
            if merge
            else "market-intel import universe %s --runtime --json" % command_path(csv_path),
            "market-intel pool coverage --runtime --json",
        ]
    return [
        "market-intel pool coverage --runtime --json" if runtime else "market-intel pool coverage --json",
        "market-intel import schema --json",
    ]


def command_path(path: Optional[Path]) -> str:
    if path is None:
        return ""
    return str(path) if not path.is_absolute() else path.name


def get_value(row: Dict[str, str], aliases: Iterable[str]) -> Optional[str]:
    normalized = {normalize_header(key): value for key, value in row.items() if key is not None}
    for alias in aliases:
        value = normalized.get(normalize_header(alias))
        if not is_empty(value):
            return str(value).strip()
    return None


def numeric_field(
    row: Dict[str, str],
    aliases: Iterable[str],
    field: str,
    index: int,
    symbol: str,
    default: float,
    warnings: List[Dict[str, object]],
    errors: List[Dict[str, object]],
) -> float:
    value = get_value(row, aliases)
    if is_empty(value):
        warnings.append(default_warning("QUOTE_FIELD_DEFAULTED", index, symbol, field, default))
        return default
    parsed = parse_number(value)
    if parsed is None:
        errors.append(invalid_number_error(index, symbol, field, value))
        return default
    return parsed


def optional_numeric_field(
    row: Dict[str, str],
    aliases: Iterable[str],
    field: str,
    index: int,
    symbol: str,
    errors: List[Dict[str, object]],
) -> Optional[float]:
    value = get_value(row, aliases)
    if is_empty(value):
        return None
    parsed = parse_number(value)
    if parsed is None:
        errors.append(invalid_number_error(index, symbol, field, value))
    return parsed


def bool_field(
    row: Dict[str, str],
    aliases: Iterable[str],
    field: str,
    index: int,
    symbol: str,
    default: bool,
    warnings: List[Dict[str, object]],
    errors: List[Dict[str, object]],
) -> bool:
    value = get_value(row, aliases)
    if is_empty(value):
        warnings.append(default_warning("QUOTE_FIELD_DEFAULTED", index, symbol, field, default))
        return default
    parsed = parse_bool(value)
    if parsed is None:
        errors.append(issue("INVALID_BOOL_FIELD", "布尔字段无法解析。", {"index": index, "symbol": symbol, "field": field, "value": value}))
        return default
    return parsed


def parse_number(value: Any) -> Optional[float]:
    if is_empty(value):
        return None
    text = str(value).strip().lower().replace(",", "").replace("，", "").replace("−", "-")
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    text = (
        text.replace("%", "")
        .replace("％", "")
        .replace("元", "")
        .replace("人民币", "")
        .replace("rmb", "")
    )
    if is_empty(text):
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def parse_bool(value: Any) -> Optional[bool]:
    if is_empty(value):
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "是", "涨停", "新高", "√"}:
        return True
    if text in {"0", "false", "no", "n", "否", "未涨停", "不是", "x"}:
        return False
    number = parse_number(text)
    if number is not None:
        return number != 0
    return None


def normalize_symbol(value: Optional[str]) -> Optional[str]:
    if is_empty(value):
        return None
    text = str(value).strip().upper()
    match = SYMBOL_RE.search(text)
    if match:
        return match.group(1)
    return text


def normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    for token in (" ", "_", "-", "%", "％", "(", ")", "（", "）", "/", "\\"):
        text = text.replace(token, "")
    return text


def is_empty(value: object) -> bool:
    return str(value or "").strip().lower() in EMPTY_VALUES


def default_warning(code: str, index: int, symbol: str, field: str, value: object) -> Dict[str, object]:
    return issue(code, "字段缺失，已使用默认值。", {"index": index, "symbol": symbol, "field": field, "default": value})


def invalid_number_error(index: int, symbol: str, field: str, value: object) -> Dict[str, object]:
    return issue("INVALID_NUMERIC_FIELD", "数字字段无法解析。", {"index": index, "symbol": symbol, "field": field, "value": value})


def issue(code: str, message: str, detail: Dict[str, object]) -> Dict[str, object]:
    return {"code": code, "message": message, "detail": detail}
