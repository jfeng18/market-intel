"""Add/remove symbols from the runtime A-share universe pool."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pool_loader import runtime_universe_path
from .runtime import display_path
from .symbols import normalize_symbol_text


def pool_add(
    symbol: str,
    name: str = "",
    layer: str = "",
    industry: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Add a symbol to the runtime universe CSV."""
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    normalized = normalize_symbol_text(symbol)
    if not normalized or not normalized.strip().isdigit() or len(normalized) != 6:
        errors.append(_issue(
            "INVALID_SYMBOL",
            "无效的证券代码，需要 6 位数字。",
            {"symbol": symbol},
        ))
        return _build_result("add", normalized or symbol, dry_run, False, warnings, errors)

    path = runtime_universe_path()
    existing = _read_universe(path)
    existing_symbols = {r["symbol"] for r in existing}

    if normalized in existing_symbols:
        warnings.append(_issue(
            "SYMBOL_ALREADY_EXISTS",
            "标的已在 universe 中。",
            {"symbol": normalized},
        ))
        return _build_result("add", normalized, dry_run, False, warnings, errors)

    record = {
        "symbol": normalized,
        "name": name or normalized,
        "industry": industry or layer or "行业待补",
        "concepts": "",
        "index_membership": "",
        "listing_status": "listed",
        "source": "pool:add",
    }

    if not dry_run:
        existing.append(record)
        _write_universe(path, existing)

    return _build_result("add", normalized, dry_run, not dry_run, warnings, errors, record=record)


def pool_remove(
    symbol: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Remove a symbol from the runtime universe CSV."""
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    normalized = normalize_symbol_text(symbol)
    if not normalized:
        errors.append(_issue(
            "INVALID_SYMBOL",
            "无效的证券代码。",
            {"symbol": symbol},
        ))
        return _build_result("remove", symbol, dry_run, False, warnings, errors)

    path = runtime_universe_path()
    existing = _read_universe(path)
    before_count = len(existing)
    removed_record = None

    for record in existing:
        if record["symbol"] == normalized:
            removed_record = record
            break

    if removed_record is None:
        warnings.append(_issue(
            "SYMBOL_NOT_FOUND",
            "标的不在 universe 中。",
            {"symbol": normalized},
        ))
        return _build_result("remove", normalized, dry_run, False, warnings, errors)

    if not dry_run:
        remaining = [r for r in existing if r["symbol"] != normalized]
        _write_universe(path, remaining)

    return _build_result("remove", normalized, dry_run, not dry_run, warnings, errors, record=removed_record)


def _read_universe(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    records = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        for row in reader:
            symbol = ""
            for key in ("symbol", "code", "证券代码", "股票代码", "代码"):
                val = row.get(key, "").strip()
                if val:
                    symbol = normalize_symbol_text(val)
                    break
            if not symbol:
                continue
            records.append({
                "symbol": symbol,
                "name": _first(row, ["name", "company", "证券名称", "名称"]) or symbol,
                "industry": _first(row, ["industry", "行业"]) or "行业待补",
                "concepts": _first(row, ["concepts", "概念"]) or "",
                "index_membership": _first(row, ["index_membership", "指数"]) or "",
                "listing_status": _first(row, ["listing_status", "状态"]) or "listed",
                "source": _first(row, ["source", "来源"]) or "csv",
            })
    return records


def _write_universe(path: Path, records: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["symbol", "name", "industry", "concepts", "index_membership", "listing_status", "source"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({f: record.get(f, "") for f in fields})


def _first(row: Dict[str, str], keys: List[str]) -> str:
    for key in keys:
        val = row.get(key, "").strip()
        if val:
            return val
    return ""


def _build_result(
    action: str,
    symbol: str,
    dry_run: bool,
    written: bool,
    warnings: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    path = runtime_universe_path()
    return {
        "action": action,
        "symbol": symbol,
        "output": display_path(path),
        "dry_run": dry_run,
        "written": written,
        "record": record,
        "next_commands": _next_commands(action, written, dry_run, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def _next_commands(action: str, written: bool, dry_run: bool, has_errors: bool) -> List[str]:
    if has_errors:
        return []
    if dry_run:
        return [
            "market-intel pool %s <symbol>" % action,
            "market-intel pool coverage --runtime --text",
        ]
    if written:
        return [
            "market-intel pool coverage --runtime --text",
            "market-intel scan --runtime --text",
        ]
    return []


def _issue(code: str, message: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail}
