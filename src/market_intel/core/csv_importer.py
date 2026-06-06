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
        "next_commands": next_commands("quotes", written, runtime, output_path),
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
        "next_commands": next_commands("holdings", written, runtime, output_path),
        "warnings": warnings,
        "errors": errors,
    }


def import_universe_csv(
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
            record, row_warnings, row_errors = parse_universe_row(row, index, csv_path)
            warnings.extend(row_warnings)
            errors.extend(row_errors)
            if record:
                records.append(record)
    if not errors and not records:
        errors.append(issue("NO_UNIVERSE_RECORDS", "CSV 中没有可导入的 A 股基础清单记录。", {"path": command_path(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_universe_csv(output_path, records)
        written = True

    return {
        "kind": "universe",
        "input": command_path(csv_path),
        "output": command_path(output_path) if output_path else None,
        "record_key": "universe",
        "record_count": len(records),
        "dry_run": dry_run,
        "written": written,
        "preview": records[:5],
        "canonical_schema": universe_schema(),
        "next_commands": next_commands("universe", written, runtime, output_path),
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
        "next_commands": next_commands("research", written, runtime, output_path),
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
                "market-intel import universe examples/a_share_universe.csv.example --runtime --json",
                "market-intel import universe a_share_universe.csv --output data/runtime/a_share_universe.csv --json",
                "market-intel import universe a_share_universe.csv --dry-run --json",
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


def quote_schema() -> List[Dict[str, object]]:
    return [
        {"field": "symbol", "type": "string", "required": True},
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


def next_commands(kind: str, written: bool, runtime: bool, output_path: Optional[Path]) -> List[str]:
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
