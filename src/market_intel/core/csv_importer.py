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
        errors.append(issue("NO_QUOTE_RECORDS", "CSV 中没有可导入的行情记录。", {"path": str(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_json_records(output_path, "quotes", records)
        written = True

    return {
        "kind": "quotes",
        "input": str(csv_path),
        "output": str(output_path) if output_path else None,
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
        errors.append(issue("NO_HOLDING_RECORDS", "CSV 中没有可导入的持仓记录。", {"path": str(csv_path)}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_json_records(output_path, "holdings", records)
        written = True

    return {
        "kind": "holdings",
        "input": str(csv_path),
        "output": str(output_path) if output_path else None,
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


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, object]]]:
    if not path.exists():
        return [], [issue("CSV_FILE_NOT_FOUND", "CSV 文件不存在。", {"path": str(path)})]
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return [], [issue("CSV_HEADER_MISSING", "CSV 缺少表头。", {"path": str(path)})]
            return list(reader), []
    except Exception as exc:
        return [], [issue("CSV_READ_ERROR", str(exc), {"path": str(path)})]


def write_json_records(path: Path, key: str, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({key: records}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


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


def next_commands(kind: str, written: bool, runtime: bool, output_path: Optional[Path]) -> List[str]:
    if not written:
        return []
    if not runtime:
        if kind == "quotes":
            return [
                "market-intel hotspots --quotes-file %s --json" % output_path,
                "market-intel daily --quotes-file %s --holdings-file <holdings.json> --json" % output_path,
            ]
        return [
            "market-intel holdings impact --holdings-file %s --json" % output_path,
            "market-intel daily --quotes-file <quotes.json> --holdings-file %s --json" % output_path,
        ]
    return [
        "market-intel validate runtime --json",
        "market-intel daily --runtime --json",
        "market-intel daily --runtime --text",
    ]


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
