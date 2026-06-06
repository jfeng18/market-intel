import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .fixtures import load_holdings_file, load_quotes_file
from .models import Holding, PoolItem, Quote
from .normalize import find_pool_item
from .runtime import runtime_holdings_path, runtime_missing_files, runtime_quotes_path


QUOTE_REQUIRED_FIELDS = {
    "symbol",
    "trade_date",
    "change_pct",
    "amount",
    "amount_ratio",
    "turnover_rate",
    "amplitude_pct",
    "is_limit_up",
    "is_stage_high",
    "intraday_fade_pct",
}
HOLDING_REQUIRED_FIELDS = {"symbol", "name"}


def validate_runtime(items: List[PoolItem]) -> Dict[str, object]:
    missing = runtime_missing_files()
    errors = [
        issue("MISSING_RUNTIME_FILE", "Runtime file is missing.", {"path": display_path(Path(path))})
        for path in missing
    ]
    warnings: List[Dict[str, object]] = []
    quotes: List[Quote] = []
    holdings: List[Holding] = []

    if not missing:
        quote_errors, quote_warnings, quotes = validate_quotes_file(runtime_quotes_path(), items)
        holding_errors, holding_warnings, holdings = validate_holdings_file(runtime_holdings_path(), items)
        errors.extend(quote_errors)
        errors.extend(holding_errors)
        warnings.extend(quote_warnings)
        warnings.extend(holding_warnings)
        warnings.extend(validate_cross_coverage(quotes, holdings))

    return {
        "ok": not errors,
        "summary": {
            "quote_count": len(quotes),
            "holding_count": len(holdings),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "files": {
            "quotes": display_path(runtime_quotes_path()),
            "holdings": display_path(runtime_holdings_path()),
        },
        "errors": errors,
        "warnings": warnings,
    }


def validate_quotes_file(path: Path, items: List[PoolItem]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Quote]]:
    errors, warnings, raw_values = validate_json_records(path, "quotes", QUOTE_REQUIRED_FIELDS)
    quotes: List[Quote] = []
    if errors:
        return errors, warnings, quotes

    for index, raw in enumerate(raw_values):
        symbol = normalize_symbol(raw.get("symbol"))
        if not symbol:
            errors.append(issue("MISSING_SYMBOL", "Quote symbol is missing.", {"index": index}))
            continue
        if find_pool_item(items, symbol) is None:
            warnings.append(issue("QUOTE_SYMBOL_NOT_IN_POOL", "Quote symbol is not in pool.", {"symbol": symbol}))
        try:
            quotes.append(Quote.from_dict(raw))
        except Exception as exc:
            errors.append(issue("INVALID_QUOTE_RECORD", str(exc), {"index": index, "symbol": symbol}))

    warnings.extend(duplicate_symbol_warnings("DUPLICATE_QUOTE_SYMBOL", [quote.symbol for quote in quotes]))
    return errors, warnings, quotes


def validate_holdings_file(path: Path, items: List[PoolItem]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Holding]]:
    errors, warnings, raw_values = validate_json_records(path, "holdings", HOLDING_REQUIRED_FIELDS)
    holdings: List[Holding] = []
    if errors:
        return errors, warnings, holdings

    for index, raw in enumerate(raw_values):
        symbol = normalize_symbol(raw.get("symbol"))
        if not symbol:
            errors.append(issue("MISSING_SYMBOL", "Holding symbol is missing.", {"index": index}))
            continue
        if find_pool_item(items, symbol) is None:
            warnings.append(issue("HOLDING_SYMBOL_NOT_IN_POOL", "Holding symbol is not in pool.", {"symbol": symbol}))
        try:
            holdings.append(Holding.from_dict(raw))
        except Exception as exc:
            errors.append(issue("INVALID_HOLDING_RECORD", str(exc), {"index": index, "symbol": symbol}))

    warnings.extend(duplicate_symbol_warnings("DUPLICATE_HOLDING_SYMBOL", [holding.symbol for holding in holdings]))
    return errors, warnings, holdings


def validate_json_records(
    path: Path,
    key: str,
    required_fields: Iterable[str],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    errors: List[Dict[str, object]] = []
    warnings: List[Dict[str, object]] = []
    if not path.exists():
        return [issue("MISSING_FILE", "File is missing.", {"path": display_path(path)})], warnings, []

    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return [issue("INVALID_JSON", str(exc), {"path": display_path(path)})], warnings, []

    if isinstance(data, dict):
        records = data.get(key)
    else:
        records = data

    if not isinstance(records, list):
        return [
            issue(
                "INVALID_JSON_SHAPE",
                "Expected a list or an object containing '%s' list." % key,
                {"path": display_path(path)},
            )
        ], warnings, []

    valid_records = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(issue("INVALID_RECORD_SHAPE", "Record must be an object.", {"index": index}))
            continue
        missing = sorted(field for field in required_fields if field not in record)
        if missing:
            errors.append(
                issue(
                    "MISSING_REQUIRED_FIELDS",
                    "Record is missing required fields.",
                    {"index": index, "missing": missing},
                )
            )
            continue
        valid_records.append(record)
    return errors, warnings, valid_records


def validate_cross_coverage(quotes: List[Quote], holdings: List[Holding]) -> List[Dict[str, object]]:
    warnings = []
    quote_symbols = {quote.symbol for quote in quotes}
    holding_symbols = {holding.symbol for holding in holdings}
    for symbol in sorted(holding_symbols - quote_symbols):
        warnings.append(
            issue(
                "HOLDING_WITHOUT_QUOTE",
                "Holding has no quote record, so brief may miss live movement.",
                {"symbol": symbol},
            )
        )
    for symbol in sorted(quote_symbols - holding_symbols):
        warnings.append(
            issue(
                "QUOTE_NOT_IN_HOLDINGS",
                "Quote is not a holding; it can still contribute to hotspots.",
                {"symbol": symbol},
            )
        )
    return warnings


def duplicate_symbol_warnings(code: str, symbols: List[str]) -> List[Dict[str, object]]:
    warnings = []
    seen = set()
    duplicates = set()
    for symbol in symbols:
        if symbol in seen:
            duplicates.add(symbol)
        seen.add(symbol)
    for symbol in sorted(duplicates):
        warnings.append(issue(code, "Duplicate symbol found.", {"symbol": symbol}))
    return warnings


def normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def issue(code: str, message: str, detail: Dict[str, object]) -> Dict[str, object]:
    return {"code": code, "message": message, "detail": detail}


def display_path(path: Path) -> str:
    if path.is_absolute() and path.parent.name:
        return "%s/%s" % (path.parent.name, path.name)
    return str(path)
