"""Fetch A-share daily quotes from akshare and write to runtime JSON."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .runtime import (
    display_path,
    mark_runtime_dataset_imported,
    runtime_dir_path,
    runtime_quotes_path,
)


def sync_quotes(
    dry_run: bool = False,
    symbols: Optional[List[str]] = None,
    trade_date: Optional[str] = None,
    progress_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Fetch all A-share quotes via akshare and write to runtime.

    Returns a result dict compatible with the project's envelope pattern.
    """
    _progress = progress_fn or (lambda _msg: None)
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    api_date, quote_date, date_error = _resolve_trade_dates(trade_date)
    if date_error:
        errors.append(date_error)
        return _build_result([], dry_run, False, str(trade_date or ""), warnings, errors)

    # Weekend detection
    try:
        parsed_date = datetime.strptime(api_date, "%Y%m%d").date()
        if parsed_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            _progress("今日非交易日（周末），数据为最近交易日行情。")
    except ValueError:
        pass

    spot_df, zt_codes, high_codes, fetch_errors = _fetch_market_data(
        api_date, progress_fn=progress_fn,
    )
    errors.extend(fetch_errors)

    if errors:
        return _build_result([], dry_run, False, quote_date, warnings, errors)

    records = _transform_quotes(spot_df, zt_codes, high_codes, quote_date)

    if symbols:
        normalized = {s.strip().zfill(6) for s in symbols}
        before = len(records)
        records = [r for r in records if r["symbol"] in normalized]
        if len(records) < len(normalized):
            missing = sorted(normalized - {r["symbol"] for r in records})
            if missing:
                warnings.append(_issue(
                    "SYNC_SYMBOLS_NOT_FOUND",
                    "部分指定标的未在行情中找到。",
                    {"missing": missing[:10], "missing_count": len(missing)},
                ))

    if not records:
        errors.append(_issue("SYNC_NO_RECORDS", "未获取到任何行情记录。", {}))
        return _build_result([], dry_run, False, quote_date, warnings, errors)

    written = False
    if not dry_run:
        output_path = runtime_quotes_path()
        _write_quotes(output_path, records)
        mark_runtime_dataset_imported("quotes", "sync:akshare")
        written = True

    return _build_result(records, dry_run, written, quote_date, warnings, errors)


def _fetch_market_data(
    date_str: str,
    progress_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[Any, Set[str], Set[str], List[Dict[str, Any]]]:
    """Call akshare APIs, return (spot_df, zt_codes, high_codes, errors)."""
    _progress = progress_fn or (lambda _msg: None)
    errors: List[Dict[str, Any]] = []

    try:
        import akshare as ak
    except ImportError:
        errors.append(_issue(
            "AKSHARE_NOT_INSTALLED",
            "akshare 未安装。请运行: pip install akshare",
            {},
        ))
        return None, set(), set(), errors

    spot_df = None
    try:
        _progress("正在从东方财富获取全 A 行情...")
        spot_df = ak.stock_zh_a_spot_em()
    except Exception as exc:
        errors.append(_issue(
            "AKSHARE_SPOT_FAILED",
            "获取全 A 行情失败: %s" % exc,
            {"exception": type(exc).__name__},
        ))
        return None, set(), set(), errors

    if spot_df is None or spot_df.empty:
        errors.append(_issue(
            "AKSHARE_SPOT_EMPTY",
            "akshare 返回空行情数据，可能非交易日。",
            {},
        ))
        return None, set(), set(), errors

    _progress("已获取 %d 条行情记录。" % len(spot_df))

    zt_codes: Set[str] = set()
    try:
        _progress("正在获取涨停板数据...")
        zt_df = ak.stock_zt_pool_em(date=date_str)
        if zt_df is not None and not zt_df.empty and "代码" in zt_df.columns:
            zt_codes = set(zt_df["代码"].astype(str))
    except Exception:
        pass

    high_codes: Set[str] = set()
    try:
        _progress("正在获取强势股数据...")
        strong_df = ak.stock_zt_pool_strong_em(date=date_str)
        if strong_df is not None and not strong_df.empty and "代码" in strong_df.columns:
            if "是否新高" in strong_df.columns:
                high_codes = set(strong_df[strong_df["是否新高"] == "是"]["代码"].astype(str))
            else:
                high_codes = set(strong_df["代码"].astype(str))
    except Exception:
        pass

    return spot_df, zt_codes, high_codes, errors


def _transform_quotes(
    spot_df: Any,
    zt_codes: Set[str],
    high_codes: Set[str],
    date_str: str,
) -> List[Dict[str, Any]]:
    """Convert akshare DataFrame rows to our Quote dict format."""
    records: List[Dict[str, Any]] = []

    for _, row in spot_df.iterrows():
        symbol = str(row.get("代码", "")).strip()
        if not symbol or len(symbol) != 6:
            continue

        change_pct = _safe_float(row.get("涨跌幅"), 0.0)
        last_price = _safe_float(row.get("最新价"))
        high = _safe_float(row.get("最高"))
        open_price = _safe_float(row.get("今开"))

        is_limit_up = symbol in zt_codes
        if not is_limit_up:
            limit_pct = _limit_up_threshold(symbol, _is_st(row))
            is_limit_up = change_pct >= limit_pct

        fade_pct = 0.0
        if high is not None and last_price is not None and high > 0:
            if high > last_price:
                fade_pct = round((high - last_price) / high * 100, 2)

        records.append({
            "symbol": symbol,
            "name": str(row.get("名称", "")).strip(),
            "trade_date": date_str,
            "last_price": last_price,
            "change_pct": round(change_pct, 2),
            "amount": _safe_float(row.get("成交额"), 0.0),
            "amount_ratio": _safe_float(row.get("量比"), 1.0),
            "turnover_rate": _safe_float(row.get("换手率"), 0.0),
            "amplitude_pct": _safe_float(row.get("振幅"), 0.0),
            "is_limit_up": is_limit_up,
            "is_stage_high": symbol in high_codes,
            "intraday_fade_pct": fade_pct,
            "source": "sync:akshare",
        })

    return records


def _write_quotes(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"quotes": records}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _build_result(
    records: List[Dict[str, Any]],
    dry_run: bool,
    written: bool,
    date_str: str,
    warnings: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    output_path = runtime_quotes_path()
    limit_up_count = sum(1 for r in records if r.get("is_limit_up"))
    stage_high_count = sum(1 for r in records if r.get("is_stage_high"))

    return {
        "kind": "sync_quotes",
        "source": "akshare",
        "output": display_path(output_path),
        "record_count": len(records),
        "trade_date": date_str,
        "dry_run": dry_run,
        "written": written,
        "summary": {
            "total": len(records),
            "limit_up": limit_up_count,
            "stage_high": stage_high_count,
        },
        "preview": records[:5],
        "next_commands": _next_commands(written, dry_run, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def _next_commands(written: bool, dry_run: bool, has_errors: bool) -> List[str]:
    if has_errors:
        return []
    if dry_run:
        return [
            "market-intel sync quotes",
            "market-intel status runtime --text",
        ]
    if written:
        return [
            "market-intel status runtime --text",
            "market-intel scan --runtime --text",
            "market-intel daily --runtime --text",
            "market-intel dashboard --text",
        ]
    return []


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        result = float(value)
        if result != result or result == float("inf") or result == float("-inf"):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _is_st(row: Any) -> bool:
    name = str(row.get("名称", "")).strip()
    return "ST" in name.upper()


def _limit_up_threshold(symbol: str, is_st: bool) -> float:
    """Return the daily limit-up percentage threshold by board and ST status.

    Main board (000/001/002/003/600/601/603/605): 10% normal, 5% ST
    ChiNext (300) and STAR Market (688): 20% (ST same since 2020 reform)
    BSE (4xxxxx/8xxxxx/920xxx): 30% (ST same)
    """
    prefix = symbol[:3]
    if prefix == "300" or prefix == "688":
        return 19.9
    if symbol.startswith("8") or symbol.startswith("4") or prefix == "920":
        return 29.9
    return 4.9 if is_st else 9.9


def _today_str() -> str:
    return date.today().strftime("%Y%m%d")


def _resolve_trade_dates(value: Optional[str]) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    text = str(value or "").strip()
    if not text:
        today = date.today()
        return today.strftime("%Y%m%d"), today.isoformat(), None
    try:
        if len(text) == 8 and text.isdigit():
            parsed = datetime.strptime(text, "%Y%m%d").date()
        else:
            parsed = date.fromisoformat(text[:10])
    except ValueError:
        return "", "", _issue(
            "SYNC_TRADE_DATE_INVALID",
            "trade_date 需要 YYYYMMDD 或 YYYY-MM-DD。",
            {"trade_date": text},
        )
    return parsed.strftime("%Y%m%d"), parsed.isoformat(), None


def _issue(code: str, message: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail}
