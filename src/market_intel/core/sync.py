"""Fetch A-share daily quotes and write to runtime JSON."""

import json
import time
from math import ceil
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import ssl
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .fixtures import load_holdings_file, load_quotes_file
from .pool_loader import a_share_universe_paths, default_pool_path, read_a_share_universe_items, read_pool_items
from .runtime import (
    display_path,
    mark_runtime_dataset_imported,
    runtime_holdings_path,
    runtime_quotes_path,
    runtime_universe_path,
)
from .symbols import normalize_symbol_input


PROVIDER_AKSHARE = "akshare"
PROVIDER_EASTMONEY = "eastmoney"
PROVIDER_TENCENT = "tencent"
PROVIDER_TENCENT_BATCH = "tencent-batch"
PROVIDER_AUTO = "auto"
SUPPORTED_PROVIDERS = {PROVIDER_AKSHARE, PROVIDER_EASTMONEY, PROVIDER_TENCENT, PROVIDER_TENCENT_BATCH, PROVIDER_AUTO}
PROVIDER_ALIASES = {
    "eastmoney-direct": PROVIDER_EASTMONEY,
    "eastmoney_direct": PROVIDER_EASTMONEY,
    "tencent_batch": PROVIDER_TENCENT_BATCH,
}

TENCENT_BATCH_SIZE = 60
TENCENT_MAX_SYMBOLS = 120
TENCENT_BATCH_MAX_SYMBOLS = 500
TENCENT_BATCH_COVERAGE_DEGRADED_THRESHOLD = 0.8
TENCENT_BATCH_SLEEP_SECONDS = 0.2
TENCENT_MAX_RETRIES = 2
EASTMONEY_SPOT_HOST = "82.push2.eastmoney.com"
EASTMONEY_DIRECT_ENDPOINT = "https://%s/api/qt/clist/get" % EASTMONEY_SPOT_HOST
EASTMONEY_DIRECT_PAGE_SIZE = 500
EASTMONEY_DIRECT_SLEEP_SECONDS = 0.25
EASTMONEY_DIRECT_MAX_RETRIES = 2
EASTMONEY_DIRECT_FIELDS = ["f12", "f14", "f2", "f3", "f6", "f10", "f8", "f7", "f15"]
EASTMONEY_DIRECT_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
PROVIDER_HEALTH_SYMBOL = "000001"


def sync_quotes(
    dry_run: bool = False,
    symbols: Optional[List[str]] = None,
    trade_date: Optional[str] = None,
    progress_fn: Optional[Callable[[str], None]] = None,
    provider: str = PROVIDER_AKSHARE,
    pool: str = "all-a",
) -> Dict[str, Any]:
    """Fetch A-share quotes and write to runtime.

    Returns a result dict compatible with the project's envelope pattern.
    """
    _progress = progress_fn or (lambda _msg: None)
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    api_date, quote_date, date_error = _resolve_trade_dates(trade_date)
    provider_name = _normalize_provider_name(provider)
    if date_error:
        errors.append(date_error)
        return _build_result(
            [],
            dry_run,
            False,
            str(trade_date or ""),
            warnings,
            errors,
            provider_name,
            requested_provider=provider_name,
        )

    if provider_name not in SUPPORTED_PROVIDERS:
        errors.append(_issue(
            "SYNC_PROVIDER_UNSUPPORTED",
            "provider 需要 akshare、eastmoney、tencent、tencent-batch 或 auto。",
            {"provider": provider_name, "supported": sorted(SUPPORTED_PROVIDERS)},
        ))
        return _build_result(
            [],
            dry_run,
            False,
            quote_date,
            warnings,
            errors,
            provider_name,
            requested_provider=provider_name,
        )

    # Weekend detection
    try:
        parsed_date = datetime.strptime(api_date, "%Y%m%d").date()
        if parsed_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            _progress("今日非交易日（周末），数据为最近交易日行情。")
    except ValueError:
        pass

    if provider_name == PROVIDER_TENCENT:
        records, fetch_warnings, fetch_errors = _fetch_tencent_quotes(
            symbols,
            quote_date,
            progress_fn=progress_fn,
            pool=pool,
        )
        warnings.extend(fetch_warnings)
        errors.extend(fetch_errors)
        if errors:
            return _build_result(
                [],
                dry_run,
                False,
                quote_date,
                warnings,
                errors,
                PROVIDER_TENCENT,
                requested_provider=provider_name,
            )
        return _finish_sync(records, dry_run, quote_date, warnings, errors, PROVIDER_TENCENT, provider_name)

    if provider_name == PROVIDER_TENCENT_BATCH:
        records, fetch_warnings, fetch_errors, coverage = _fetch_tencent_batch_quotes(
            symbols,
            quote_date,
            progress_fn=progress_fn,
        )
        warnings.extend(fetch_warnings)
        errors.extend(fetch_errors)
        if errors:
            return _build_result(
                [],
                dry_run,
                False,
                quote_date,
                warnings,
                errors,
                PROVIDER_TENCENT_BATCH,
                requested_provider=provider_name,
                coverage=coverage,
            )
        return _finish_sync(
            records,
            dry_run,
            quote_date,
            warnings,
            errors,
            PROVIDER_TENCENT_BATCH,
            provider_name,
            coverage=coverage,
        )

    if provider_name == PROVIDER_EASTMONEY:
        records, fetch_warnings, fetch_errors, coverage = _fetch_eastmoney_quotes(
            quote_date=quote_date,
            symbols=symbols,
            progress_fn=progress_fn,
        )
        warnings.extend(fetch_warnings)
        errors.extend(fetch_errors)
        if errors:
            return _build_result(
                [],
                dry_run,
                False,
                quote_date,
                warnings,
                errors,
                PROVIDER_EASTMONEY,
                requested_provider=provider_name,
                coverage=coverage,
            )
        return _finish_sync(
            records,
            dry_run,
            quote_date,
            warnings,
            errors,
            PROVIDER_EASTMONEY,
            provider_name,
            coverage=coverage,
        )

    records, fetch_warnings, fetch_errors = _fetch_akshare_quotes(
        api_date=api_date,
        quote_date=quote_date,
        symbols=symbols,
        progress_fn=progress_fn,
    )
    warnings.extend(fetch_warnings)
    errors.extend(fetch_errors)

    if not errors:
        return _finish_sync(records, dry_run, quote_date, warnings, errors, PROVIDER_AKSHARE, provider_name)

    if provider_name != PROVIDER_AUTO:
        return _build_result(
            [],
            dry_run,
            False,
            quote_date,
            warnings,
            errors,
            PROVIDER_AKSHARE,
            requested_provider=provider_name,
        )

    failed_codes = [str(error.get("code")) for error in errors if isinstance(error, dict)]
    warnings.append(_issue(
        "SYNC_AKSHARE_FALLBACK_EASTMONEY",
        "akshare 获取失败，尝试 Eastmoney direct 全 A 兜底。",
        {"failed_codes": failed_codes},
    ))
    original_errors = list(errors)
    errors = []
    records, fallback_warnings, fallback_errors, coverage = _fetch_eastmoney_quotes(
        quote_date=quote_date,
        symbols=symbols,
        progress_fn=progress_fn,
    )
    warnings.extend(fallback_warnings)
    errors.extend(fallback_errors)
    if not errors:
        return _finish_sync(
            records,
            dry_run,
            quote_date,
            warnings,
            errors,
            PROVIDER_EASTMONEY,
            provider_name,
            coverage=coverage,
        )

    eastmoney_errors = list(errors)
    if symbols:
        warnings.append(_issue(
            "SYNC_AKSHARE_FALLBACK_TENCENT",
            "akshare 获取失败，尝试 Tencent 选定标的兜底。",
            {"failed_codes": failed_codes},
        ))
        warnings.append(_issue(
            "SYNC_EASTMONEY_FALLBACK_TENCENT",
            "Eastmoney direct 获取失败，尝试 Tencent 选定标的兜底。",
            {"failed_codes": [str(error.get("code")) for error in errors if isinstance(error, dict)]},
        ))
        errors = []
        records, selected_warnings, selected_errors = _fetch_tencent_quotes(
            symbols,
            quote_date,
            progress_fn=progress_fn,
            pool=pool,
        )
        warnings.extend(selected_warnings)
        errors.extend(selected_errors)
        if errors:
            errors = original_errors + eastmoney_errors + errors
            return _build_result(
                [],
                dry_run,
                False,
                quote_date,
                warnings,
                errors,
                PROVIDER_AUTO,
                requested_provider=provider_name,
                coverage=coverage,
            )
        return _finish_sync(records, dry_run, quote_date, warnings, errors, PROVIDER_TENCENT, provider_name)

    warnings.append(_issue(
        "SYNC_EASTMONEY_FALLBACK_TENCENT_BATCH",
        "Eastmoney direct 获取失败，尝试 Tencent universe 批量兜底。",
        {"failed_codes": [str(error.get("code")) for error in errors if isinstance(error, dict)]},
    ))
    errors = []
    records, batch_warnings, batch_errors, batch_coverage = _fetch_tencent_batch_quotes(
        symbols,
        quote_date,
        progress_fn=progress_fn,
    )
    warnings.extend(batch_warnings)
    errors.extend(batch_errors)
    if not errors:
        return _finish_sync(
            records,
            dry_run,
            quote_date,
            warnings,
            errors,
            PROVIDER_TENCENT_BATCH,
            provider_name,
            coverage=batch_coverage,
        )

    warnings.append(_issue(
        "SYNC_TENCENT_BATCH_FALLBACK_SELECTED",
        "Tencent universe 批量兜底失败，尝试 Tencent 选定标的兜底。",
        {"failed_codes": [str(error.get("code")) for error in errors if isinstance(error, dict)]},
    ))
    batch_errors_original = list(errors)
    errors = []
    records, selected_warnings, selected_errors = _fetch_tencent_quotes(
        symbols,
        quote_date,
        progress_fn=progress_fn,
        pool=pool,
    )
    warnings.extend(selected_warnings)
    errors.extend(selected_errors)
    if errors:
        errors = original_errors + eastmoney_errors + batch_errors_original + errors
        return _build_result(
            [],
            dry_run,
            False,
            quote_date,
            warnings,
            errors,
            PROVIDER_AUTO,
            requested_provider=provider_name,
            coverage=batch_coverage,
        )
    return _finish_sync(records, dry_run, quote_date, warnings, errors, PROVIDER_TENCENT, provider_name)


def _normalize_provider_name(provider: object) -> str:
    text = str(provider or PROVIDER_AKSHARE).strip().lower()
    return PROVIDER_ALIASES.get(text, text)


def _fetch_akshare_quotes(
    api_date: str,
    quote_date: str,
    symbols: Optional[List[str]],
    progress_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    spot_df, zt_codes, high_codes, fetch_errors = _fetch_market_data(api_date, progress_fn=progress_fn)
    errors.extend(fetch_errors)
    if errors:
        return [], warnings, errors

    records = _transform_quotes(spot_df, zt_codes, high_codes, quote_date)
    if symbols:
        records, filter_warnings = _filter_records_by_symbols(records, symbols)
        warnings.extend(filter_warnings)

    if not records:
        errors.append(_issue("SYNC_NO_RECORDS", "未获取到任何行情记录。", {}))
    return records, warnings, errors


def provider_health(
    symbol: str = PROVIDER_HEALTH_SYMBOL,
) -> Dict[str, Any]:
    normalized = _normalize_symbol_list([symbol])
    sample_symbol = normalized[0] if normalized else PROVIDER_HEALTH_SYMBOL
    providers = [
        _health_akshare(sample_symbol),
        _health_eastmoney_direct(),
        _health_tencent_selected(sample_symbol),
    ]
    ready = [item for item in providers if item.get("ready")]
    degraded = [item for item in providers if item.get("status") == "degraded"]
    recommended = _recommended_provider(providers)
    return {
        "kind": "provider_health",
        "sample_symbol": sample_symbol,
        "full_market_fetch": False,
        "recommended_provider": recommended,
        "status": "ready" if ready else "degraded" if degraded else "blocked",
        "providers": providers,
        "summary": provider_health_summary(providers, recommended),
        "agent_contract": provider_health_contract(),
        "next_commands": provider_health_next_commands(recommended),
    }


def _health_akshare(symbol: str) -> Dict[str, Any]:
    try:
        import akshare as ak
    except ImportError:
        return _provider_health_row(
            PROVIDER_AKSHARE,
            ready=False,
            coverage="full_a",
            reason_code="AKSHARE_NOT_INSTALLED",
            message="akshare 未安装。",
            detail={},
        )
    try:
        data = ak.stock_bid_ask_em(symbol=symbol)
        row_count = len(data) if data is not None else 0
        return _provider_health_row(
            PROVIDER_AKSHARE,
            ready=bool(row_count),
            coverage="full_a",
            reason_code=None if row_count else "AKSHARE_SAMPLE_EMPTY",
            message="akshare sample ok." if row_count else "akshare sample 返回空数据。",
            detail={"sample_symbol": symbol, "sample_rows": row_count, "full_market_fetch": False},
        )
    except Exception as exc:
        issue = _akshare_spot_issue(exc)
        return _provider_health_row(
            PROVIDER_AKSHARE,
            ready=False,
            coverage="full_a",
            reason_code=str(issue.get("code") or "AKSHARE_SAMPLE_FAILED"),
            message=str(issue.get("message") or "akshare sample failed."),
            detail=issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {},
        )


def _health_eastmoney_direct() -> Dict[str, Any]:
    data, issue = _eastmoney_direct_page(1, 1)
    if issue:
        return _provider_health_row(
            PROVIDER_EASTMONEY,
            ready=False,
            coverage="full_a",
            reason_code=str(issue.get("code") or "EASTMONEY_DIRECT_SAMPLE_FAILED"),
            message=str(issue.get("message") or "Eastmoney direct sample failed."),
            detail=issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {},
        )
    body = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
    rows = body.get("diff", []) if isinstance(body.get("diff"), list) else []
    total = _safe_int(body.get("total"), len(rows))
    return _provider_health_row(
        PROVIDER_EASTMONEY,
        ready=bool(rows),
        coverage="full_a",
        reason_code=None if rows else "EASTMONEY_DIRECT_SAMPLE_EMPTY",
        message="Eastmoney direct sample ok." if rows else "Eastmoney direct sample 返回空数据。",
        detail={"sample_rows": len(rows), "reported_total": total, "full_market_fetch": False},
    )


def _health_tencent_selected(symbol: str) -> Dict[str, Any]:
    normalized = _normalize_tencent_symbol(symbol)
    if not normalized:
        return _provider_health_row(
            PROVIDER_TENCENT,
            ready=False,
            coverage="selected_symbols",
            reason_code="TENCENT_SAMPLE_SYMBOL_INVALID",
            message="Tencent sample symbol invalid.",
            detail={"sample_symbol": symbol},
        )
    records, errors = _fetch_tencent_normalized([normalized], date.today().isoformat())
    if errors:
        first = errors[0]
        return _provider_health_row(
            PROVIDER_TENCENT,
            ready=False,
            coverage="selected_symbols",
            reason_code=str(first.get("code") or "TENCENT_SAMPLE_FAILED"),
            message=str(first.get("message") or "Tencent sample failed."),
            detail=first.get("detail", {}) if isinstance(first.get("detail"), dict) else {},
        )
    return _provider_health_row(
        PROVIDER_TENCENT,
        ready=bool(records),
        coverage="selected_symbols",
        reason_code=None if records else "TENCENT_SAMPLE_EMPTY",
        message="Tencent selected sample ok." if records else "Tencent selected sample 返回空数据。",
        detail={"sample_symbol": symbol, "sample_rows": len(records), "full_market_fetch": False},
    )


def _provider_health_row(
    provider: str,
    ready: bool,
    coverage: str,
    reason_code: Optional[str],
    message: str,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": provider,
        "ready": bool(ready),
        "status": "ready" if ready else "blocked",
        "coverage": coverage,
        "full_market_capable": coverage == "full_a",
        "reason_code": reason_code,
        "message": message,
        "detail": detail,
    }


def _recommended_provider(providers: List[Dict[str, Any]]) -> Optional[str]:
    priority = [PROVIDER_EASTMONEY, PROVIDER_AKSHARE, PROVIDER_TENCENT]
    by_provider = {str(item.get("provider")): item for item in providers}
    for provider in priority:
        item = by_provider.get(provider)
        if item and item.get("ready") and item.get("coverage") == "full_a":
            return provider
    tencent = by_provider.get(PROVIDER_TENCENT)
    if tencent and tencent.get("ready"):
        return PROVIDER_TENCENT
    return None


def provider_health_summary(providers: List[Dict[str, Any]], recommended: Optional[str]) -> str:
    ready = [str(item.get("provider")) for item in providers if item.get("ready")]
    if recommended:
        return "recommended=%s; ready=%s." % (recommended, ",".join(ready) or "none")
    return "no provider ready; inspect providers[].reason_code."


def provider_health_next_commands(recommended: Optional[str]) -> List[str]:
    if recommended == PROVIDER_TENCENT:
        return ["market-intel sync quotes --provider tencent --symbols 000001 --dry-run --json"]
    if recommended:
        return ["market-intel sync quotes --provider %s --dry-run --json" % recommended]
    return ["market-intel provider health --json"]


def provider_health_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 表示 health command 生成成功；data.status 和 providers[].ready 表示 provider 就绪度。",
        "stable_fields": [
            "data.status",
            "data.recommended_provider",
            "data.full_market_fetch",
            "data.providers",
            "data.providers[].provider",
            "data.providers[].ready",
            "data.providers[].coverage",
            "data.providers[].reason_code",
            "data.next_commands",
        ],
        "boundary": "provider health 只做小样本探测，不拉取全市场，也不生成交易建议。",
    }


def _finish_sync(
    records: List[Dict[str, Any]],
    dry_run: bool,
    quote_date: str,
    warnings: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    provider: str,
    requested_provider: str,
    coverage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not records:
        errors.append(_issue("SYNC_NO_RECORDS", "未获取到任何行情记录。", {}))
        return _build_result(
            [],
            dry_run,
            False,
            quote_date,
            warnings,
            errors,
            provider,
            requested_provider=requested_provider,
            coverage=coverage,
        )

    written = False
    if not dry_run:
        output_path = runtime_quotes_path()
        _write_quotes(output_path, records)
        mark_runtime_dataset_imported(
            "quotes",
            "sync:%s" % provider,
            {
                "provider": provider,
                "requested_provider": requested_provider,
                "fallback_used": bool(
                    requested_provider == PROVIDER_AUTO
                    and provider in {PROVIDER_EASTMONEY, PROVIDER_TENCENT_BATCH, PROVIDER_TENCENT}
                ),
                "provider_failed_using_cache": False,
            },
        )
        written = True

    return _build_result(
        records,
        dry_run,
        written,
        quote_date,
        warnings,
        errors,
        provider,
        requested_provider=requested_provider,
        coverage=coverage,
    )


def _fetch_tencent_quotes(
    symbols: Optional[List[str]],
    date_str: str,
    progress_fn: Optional[Callable[[str], None]] = None,
    pool: str = "all-a",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch selected symbols from Tencent qt.gtimg.cn.

    Tencent is selected-symbol only here. Full all-A sync should still use a bulk
    provider such as akshare/Eastmoney or another full-market source.
    """
    _progress = progress_fn or (lambda _msg: None)
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    selected_symbols, selected_warnings = _selected_tencent_symbols(symbols, pool)
    warnings.extend(selected_warnings)
    normalized = [_normalize_tencent_symbol(symbol) for symbol in selected_symbols]
    normalized = _dedupe([symbol for symbol in normalized if symbol])
    if not selected_symbols:
        errors.append(_issue(
            "TENCENT_SYMBOLS_REQUIRED",
            "Tencent provider 需要 --symbols，或 runtime holdings / selected universe。",
            {"max_symbols": TENCENT_MAX_SYMBOLS},
        ))
        return [], warnings, errors
    if not normalized:
        errors.append(_issue(
            "TENCENT_SYMBOLS_INVALID",
            "Tencent provider 未识别到有效 A 股代码。",
            {"symbol_count": len(selected_symbols)},
        ))
        return [], warnings, errors
    if len(normalized) > TENCENT_MAX_SYMBOLS:
        errors.append(_issue(
            "TENCENT_SYMBOL_LIMIT_EXCEEDED",
            "Tencent provider 只用于选定标的兜底，拒绝批量拉取过多代码。",
            {"symbol_count": len(normalized), "max_symbols": TENCENT_MAX_SYMBOLS},
        ))
        return [], warnings, errors

    records: List[Dict[str, Any]] = []
    _progress("正在从腾讯财经获取 %d 个标的行情..." % len(normalized))
    for start in range(0, len(normalized), TENCENT_BATCH_SIZE):
        chunk = normalized[start:start + TENCENT_BATCH_SIZE]
        url = "https://qt.gtimg.cn/q=" + quote(",".join(chunk), safe=",")
        try:
            with urlopen(url, timeout=10, context=_ssl_context()) as resp:
                body = resp.read().decode("gbk", errors="ignore")
        except Exception as exc:
            errors.append(_issue(
                "TENCENT_QUOTE_FAILED",
                "获取腾讯财经行情失败: %s" % exc,
                {"exception": type(exc).__name__, "symbols": chunk[:10]},
            ))
            return [], warnings, errors
        records.extend(_parse_tencent_payload(body, date_str))
        if start + TENCENT_BATCH_SIZE < len(normalized):
            time.sleep(TENCENT_BATCH_SLEEP_SECONDS)

    found = {record["symbol"] for record in records}
    requested = {symbol[-6:] for symbol in normalized}
    missing = sorted(requested - found)
    if missing:
        warnings.append(_issue(
            "SYNC_SYMBOLS_NOT_FOUND",
            "部分指定标的未在腾讯财经行情中找到。",
            {"missing": missing[:10], "missing_count": len(missing)},
        ))
    return records, warnings, errors


def _fetch_tencent_batch_quotes(
    symbols: Optional[List[str]],
    date_str: str,
    progress_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    _progress = progress_fn or (lambda _msg: None)
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    universe_symbols, universe_warnings = _tencent_batch_universe_symbols(symbols)
    warnings.extend(universe_warnings)
    normalized = _dedupe([symbol for symbol in (_normalize_tencent_symbol(item) for item in universe_symbols) if symbol])
    universe_count = len(_dedupe(_normalize_symbol_list(universe_symbols)))
    coverage = _provider_coverage(
        PROVIDER_TENCENT_BATCH,
        "universe_based",
        universe_count=universe_count,
        requested=len(normalized),
        success=0,
        failed=0,
    )

    if not universe_symbols:
        errors.append(_issue(
            "TENCENT_BATCH_UNIVERSE_REQUIRED",
            "Tencent batch provider 需要 --symbols 或 runtime/local universe。",
            {"max_symbols": TENCENT_BATCH_MAX_SYMBOLS},
        ))
        return [], warnings, errors, coverage
    if not normalized:
        errors.append(_issue(
            "TENCENT_BATCH_SYMBOLS_INVALID",
            "Tencent batch provider 未识别到有效 A 股代码。",
            {"symbol_count": len(universe_symbols)},
        ))
        return [], warnings, errors, coverage
    if len(normalized) > TENCENT_BATCH_MAX_SYMBOLS:
        errors.append(_issue(
            "TENCENT_BATCH_SYMBOL_LIMIT_EXCEEDED",
            "Tencent batch provider 当前限制批量标的数量，避免不安全请求。",
            {"symbol_count": len(normalized), "max_symbols": TENCENT_BATCH_MAX_SYMBOLS},
        ))
        return [], warnings, errors, coverage

    _progress("正在从腾讯财经按 universe 批量获取 %d 个标的行情..." % len(normalized))
    records, request_errors = _fetch_tencent_normalized(normalized, date_str)
    errors.extend(request_errors)
    requested_codes = {symbol[-6:] for symbol in normalized}
    success_codes = {str(record.get("symbol") or "") for record in records}
    failed_codes = sorted(requested_codes - success_codes)
    coverage = _provider_coverage(
        PROVIDER_TENCENT_BATCH,
        "universe_based",
        universe_count=universe_count,
        requested=len(requested_codes),
        success=len(success_codes),
        failed=len(failed_codes),
        failed_symbols=failed_codes[:20],
    )
    if failed_codes:
        warnings.append(_issue(
            "TENCENT_BATCH_PARTIAL_MISSING",
            "部分 universe 标的未在腾讯财经行情中返回。",
            {"missing": failed_codes[:20], "missing_count": len(failed_codes)},
        ))
    if coverage["status"] == "degraded" and not errors:
        warnings.append(_issue(
            "TENCENT_BATCH_COVERAGE_DEGRADED",
            "Tencent batch universe 覆盖率低于阈值，结果标记为 degraded。",
            {
                "coverage_pct": coverage["coverage_pct"],
                "threshold_pct": round(TENCENT_BATCH_COVERAGE_DEGRADED_THRESHOLD * 100, 2),
            },
        ))
    if not records and not errors:
        errors.append(_issue("TENCENT_BATCH_NO_RECORDS", "Tencent batch 未获取到任何行情记录。", {}))
    return records, warnings, errors, coverage


def _fetch_tencent_normalized(
    normalized_symbols: List[str],
    date_str: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for start in range(0, len(normalized_symbols), TENCENT_BATCH_SIZE):
        chunk = normalized_symbols[start:start + TENCENT_BATCH_SIZE]
        url = "https://qt.gtimg.cn/q=" + quote(",".join(chunk), safe=",")
        body = None
        last_exc: Optional[Exception] = None
        for attempt in range(TENCENT_MAX_RETRIES + 1):
            try:
                with urlopen(url, timeout=10, context=_ssl_context()) as resp:
                    body = resp.read().decode("gbk", errors="ignore")
                break
            except Exception as exc:
                last_exc = exc
                if attempt < TENCENT_MAX_RETRIES:
                    time.sleep(0.2 * (attempt + 1))
        if body is None:
            errors.append(_issue(
                "TENCENT_QUOTE_FAILED",
                "获取腾讯财经行情失败: %s" % last_exc,
                {"exception": type(last_exc).__name__ if last_exc else "Unknown", "symbols": chunk[:10]},
            ))
            return records, errors
        records.extend(_parse_tencent_payload(body, date_str))
        if start + TENCENT_BATCH_SIZE < len(normalized_symbols):
            time.sleep(TENCENT_BATCH_SLEEP_SECONDS)
    return records, errors


def _tencent_batch_universe_symbols(symbols: Optional[List[str]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    if symbols:
        return _dedupe(_normalize_symbol_list(symbols)), []
    warnings: List[Dict[str, Any]] = []
    selected: List[str] = []
    paths = a_share_universe_paths()
    for path in paths:
        try:
            selected.extend(item.symbol for item in read_a_share_universe_items(path) if item.symbol)
        except Exception as exc:
            warnings.append(_issue(
                "TENCENT_BATCH_UNIVERSE_READ_FAILED",
                "读取 universe 失败，已跳过该来源。",
                {"source": display_path(path), "exception": type(exc).__name__},
            ))
    return _dedupe(_normalize_symbol_list(selected)), warnings


def _fetch_eastmoney_quotes(
    quote_date: str,
    symbols: Optional[List[str]] = None,
    progress_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    _progress = progress_fn or (lambda _msg: None)
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    normalized_symbols = set(_normalize_symbol_list(symbols or []))
    _progress("正在从 Eastmoney direct 获取全 A 行情...")
    first, first_issue = _eastmoney_direct_page(1, EASTMONEY_DIRECT_PAGE_SIZE)
    if first_issue:
        errors.append(first_issue)
        return [], warnings, errors, _provider_coverage(PROVIDER_EASTMONEY, "full_a", failed=1)

    data = first.get("data", {}) if isinstance(first.get("data"), dict) else {}
    rows = data.get("diff", []) if isinstance(data.get("diff"), list) else []
    total = _safe_int(data.get("total"), len(rows))
    pages = max(1, ceil(total / EASTMONEY_DIRECT_PAGE_SIZE)) if total else 1
    all_rows = list(rows)
    failed_pages: List[int] = []
    for page in range(2, pages + 1):
        page_data, issue = _eastmoney_direct_page(page, EASTMONEY_DIRECT_PAGE_SIZE)
        if issue:
            failed_pages.append(page)
            warnings.append(issue)
            continue
        page_body = page_data.get("data", {}) if isinstance(page_data.get("data"), dict) else {}
        page_rows = page_body.get("diff", []) if isinstance(page_body.get("diff"), list) else []
        all_rows.extend(page_rows)
        if page < pages:
            time.sleep(EASTMONEY_DIRECT_SLEEP_SECONDS)

    records = [_eastmoney_row_to_quote(row, quote_date) for row in all_rows if isinstance(row, dict)]
    records = [record for record in records if record]
    if normalized_symbols:
        records, filter_warnings = _filter_records_by_symbols(records, list(normalized_symbols))
        warnings.extend(filter_warnings)
    coverage = _provider_coverage(
        PROVIDER_EASTMONEY,
        "full_a",
        universe_count=total,
        requested=len(normalized_symbols) if normalized_symbols else total,
        success=len(records),
        failed=len(failed_pages),
        failed_pages=failed_pages[:20],
        page_count=pages,
        partial_failure=bool(failed_pages),
    )
    if failed_pages:
        warnings.append(_issue(
            "EASTMONEY_DIRECT_PARTIAL_FAILURE",
            "Eastmoney direct 部分页失败，coverage 已标记 degraded。",
            {"failed_pages": failed_pages[:20], "failed_count": len(failed_pages), "page_count": pages},
        ))
    if not records and not errors:
        errors.append(_issue("EASTMONEY_DIRECT_NO_RECORDS", "Eastmoney direct 未获取到任何行情记录。", {}))
    return records, warnings, errors, coverage


def _eastmoney_direct_page(page: int, page_size: int) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    params = {
        "pn": page,
        "pz": page_size,
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": EASTMONEY_DIRECT_FS,
        "fields": ",".join(EASTMONEY_DIRECT_FIELDS),
    }
    url = EASTMONEY_DIRECT_ENDPOINT + "?" + urlencode(params)
    headers = {
        "User-Agent": "Mozilla/5.0 market-intel/0.1",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
        "Accept": "application/json,text/plain,*/*",
    }
    last_exc: Optional[Exception] = None
    for attempt in range(EASTMONEY_DIRECT_MAX_RETRIES + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=12, context=_ssl_context()) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if not isinstance(data, dict):
                return {}, _issue(
                    "EASTMONEY_DIRECT_BAD_JSON",
                    "Eastmoney direct 返回非对象 JSON。",
                    {"page": page},
                )
            return data, None
        except Exception as exc:
            last_exc = exc
            if attempt < EASTMONEY_DIRECT_MAX_RETRIES:
                time.sleep(0.3 * (attempt + 1))
    return {}, _eastmoney_direct_issue(last_exc or Exception("unknown"), page)


def _eastmoney_row_to_quote(row: Dict[str, Any], quote_date: str) -> Optional[Dict[str, Any]]:
    symbol = normalize_symbol_input(str(row.get("f12") or ""))
    if not symbol or len(symbol) != 6:
        return None
    price = _eastmoney_number(row.get("f2"))
    high = _eastmoney_number(row.get("f15"))
    change_pct = _eastmoney_number(row.get("f3"), 0.0) or 0.0
    fade_pct = 0.0
    if high is not None and price is not None and high > price and high > 0:
        fade_pct = round((high - price) / high * 100, 2)
    return {
        "symbol": symbol,
        "name": str(row.get("f14") or "").strip(),
        "trade_date": quote_date,
        "last_price": price,
        "change_pct": round(change_pct, 2),
        "amount": _eastmoney_number(row.get("f6"), 0.0) or 0.0,
        "amount_ratio": _eastmoney_number(row.get("f10"), 1.0) or 1.0,
        "turnover_rate": _eastmoney_number(row.get("f8"), 0.0) or 0.0,
        "amplitude_pct": _eastmoney_number(row.get("f7"), 0.0) or 0.0,
        "is_limit_up": change_pct >= _limit_up_threshold(symbol, _is_st({"名称": row.get("f14")})),
        "is_stage_high": False,
        "intraday_fade_pct": fade_pct,
        "source": "sync:eastmoney",
    }


def _eastmoney_number(value: Any, default: Optional[float] = None) -> Optional[float]:
    text = str(value).strip() if value is not None else ""
    if text in {"", "-", "--", "None", "nan"}:
        return default
    return _safe_float(text, default)


def _eastmoney_direct_issue(exc: Exception, page: int) -> Dict[str, Any]:
    base = _akshare_spot_issue(exc)
    code = str(base.get("code") or "AKSHARE_SPOT_FAILED").replace("AKSHARE", "EASTMONEY_DIRECT", 1)
    detail = base.get("detail", {}) if isinstance(base.get("detail"), dict) else {}
    detail["provider"] = PROVIDER_EASTMONEY
    detail["page"] = page
    return _issue(code, str(base.get("message") or "Eastmoney direct 获取失败。"), detail)


def _selected_tencent_symbols(
    symbols: Optional[List[str]],
    pool: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    if symbols:
        return _dedupe(_normalize_symbol_list(symbols)), []

    warnings: List[Dict[str, Any]] = []
    selected: List[str] = []
    holdings_path = runtime_holdings_path()
    if holdings_path.exists():
        try:
            selected.extend(holding.symbol for holding in load_holdings_file(holdings_path) if holding.symbol)
        except Exception as exc:
            warnings.append(_issue(
                "TENCENT_RUNTIME_HOLDINGS_READ_FAILED",
                "读取 runtime holdings 失败，已跳过 holdings 兜底标的。",
                {"exception": type(exc).__name__},
            ))

    quotes_path = runtime_quotes_path()
    if quotes_path.exists():
        try:
            quote_symbols = [quote.symbol for quote in load_quotes_file(quotes_path) if quote.symbol]
        except Exception as exc:
            quote_symbols = []
            warnings.append(_issue(
                "TENCENT_RUNTIME_QUOTES_READ_FAILED",
                "读取 runtime quotes 失败，已跳过 quotes 兜底标的。",
                {"exception": type(exc).__name__},
            ))
        if len(quote_symbols) <= TENCENT_MAX_SYMBOLS:
            selected.extend(quote_symbols)
        else:
            warnings.append(_issue(
                "TENCENT_RUNTIME_QUOTES_TOO_LARGE",
                "runtime quotes 超过 Tencent 兜底上限，未批量拉取。",
                {"symbol_count": len(quote_symbols), "max_symbols": TENCENT_MAX_SYMBOLS},
            ))

    universe_path = runtime_universe_path()
    if universe_path.exists():
        try:
            universe_symbols = [
                item.symbol
                for item in read_a_share_universe_items(universe_path)
                if item.symbol
            ]
        except Exception as exc:
            universe_symbols = []
            warnings.append(_issue(
                "TENCENT_RUNTIME_UNIVERSE_READ_FAILED",
                "读取 runtime universe 失败，已跳过 universe 兜底标的。",
                {"exception": type(exc).__name__},
            ))
        if len(universe_symbols) <= TENCENT_MAX_SYMBOLS:
            selected.extend(universe_symbols)
        else:
            warnings.append(_issue(
                "TENCENT_RUNTIME_UNIVERSE_TOO_LARGE",
                "runtime universe 超过 Tencent 兜底上限，未批量拉取。",
                {"symbol_count": len(universe_symbols), "max_symbols": TENCENT_MAX_SYMBOLS},
            ))

    if not selected and pool and pool != "all-a":
        try:
            pool_symbols = [
                item.symbol
                for item in read_pool_items(default_pool_path(pool), source="base")
                if item.symbol
            ]
        except Exception as exc:
            pool_symbols = []
            warnings.append(_issue(
                "TENCENT_POOL_READ_FAILED",
                "读取 pool 标的失败，已跳过 pool 兜底标的。",
                {"pool": str(pool), "exception": type(exc).__name__},
            ))
        if len(pool_symbols) <= TENCENT_MAX_SYMBOLS:
            selected.extend(pool_symbols)
            warnings.append(_issue(
                "TENCENT_POOL_SELECTED",
                "未提供 --symbols，Tencent 兜底使用指定 pool 的小样本标的。",
                {"pool": str(pool), "symbol_count": len(pool_symbols)},
            ))
        elif pool_symbols:
            warnings.append(_issue(
                "TENCENT_POOL_TOO_LARGE",
                "pool 标的超过 Tencent 兜底上限，未批量拉取。",
                {"pool": str(pool), "symbol_count": len(pool_symbols), "max_symbols": TENCENT_MAX_SYMBOLS},
            ))

    return _dedupe(_normalize_symbol_list(selected)), warnings


def _normalize_symbol_list(values: Iterable[object]) -> List[str]:
    symbols = []
    for value in values:
        text = str(value or "").strip()
        normalized = normalize_symbol_input(text)
        if normalized and normalized.isdigit() and len(normalized) < 6:
            normalized = normalized.zfill(6)
        if normalized and len(normalized) == 6 and normalized.isdigit():
            symbols.append(normalized)
    return symbols


def _filter_records_by_symbols(
    records: List[Dict[str, Any]],
    symbols: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normalized = set(_normalize_symbol_list(symbols))
    filtered = [record for record in records if str(record.get("symbol") or "") in normalized]
    warnings: List[Dict[str, Any]] = []
    if len(filtered) < len(normalized):
        missing = sorted(normalized - {str(record.get("symbol") or "") for record in filtered})
        if missing:
            warnings.append(_issue(
                "SYNC_SYMBOLS_NOT_FOUND",
                "部分指定标的未在行情中找到。",
                {"missing": missing[:10], "missing_count": len(missing)},
            ))
    return filtered, warnings


def _dedupe(values: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_tencent_symbol(symbol: object) -> Optional[str]:
    text = str(symbol or "").strip().lower()
    if not text:
        return None
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8 and text[2:].isdigit():
        return text
    code = text[-6:]
    if not (len(code) == 6 and code.isdigit()):
        return None
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("8", "4")):
        return "bj" + code
    return "sz" + code


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _parse_tencent_payload(body: str, date_str: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in body.split(";"):
        if "=\"" not in line:
            continue
        prefix, raw = line.split("=\"", 1)
        raw = raw.rstrip('"\n\r ')
        if not raw or "pv_none_match" in raw:
            continue
        fields = raw.split("~")
        if len(fields) < 40:
            continue
        market_symbol = prefix.split("v_")[-1].strip()
        code = market_symbol[-6:]
        if not (len(code) == 6 and code.isdigit()):
            continue
        price = _safe_float(_field(fields, 3))
        high = _safe_float(_field(fields, 33))
        change_pct = _safe_float(_field(fields, 32), 0.0) or 0.0
        fade_pct = 0.0
        if high is not None and price is not None and high > price and high > 0:
            fade_pct = round((high - price) / high * 100, 2)
        records.append({
            "symbol": code,
            "name": _field(fields, 1),
            "trade_date": date_str,
            "last_price": price,
            "change_pct": round(change_pct, 2),
            "amount": (_safe_float(_field(fields, 37), 0.0) or 0.0) * 10000,
            "amount_ratio": 1.0,
            "turnover_rate": 0.0,
            "amplitude_pct": 0.0,
            "is_limit_up": change_pct >= _limit_up_threshold(code, False),
            "is_stage_high": False,
            "intraday_fade_pct": fade_pct,
            "source": "sync:tencent",
        })
    return records


def _field(fields: List[str], index: int) -> str:
    return fields[index].strip() if index < len(fields) else ""


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
        errors.append(_akshare_spot_issue(exc))
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

    for row in spot_df.to_dict("records"):
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
    provider: str = PROVIDER_AKSHARE,
    requested_provider: Optional[str] = None,
    coverage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    output_path = runtime_quotes_path()
    limit_up_count = sum(1 for r in records if r.get("is_limit_up"))
    stage_high_count = sum(1 for r in records if r.get("is_stage_high"))
    coverage_data = coverage if isinstance(coverage, dict) else _provider_coverage(
        provider,
        _provider_default_coverage_kind(provider),
        requested=len(records),
        success=len(records),
        failed=0,
    )

    return {
        "kind": "sync_quotes",
        "source": provider,
        "requested_provider": requested_provider or provider,
        "fallback_used": bool(requested_provider == PROVIDER_AUTO and provider in {PROVIDER_EASTMONEY, PROVIDER_TENCENT_BATCH, PROVIDER_TENCENT}),
        "coverage": coverage_data,
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


def _provider_default_coverage_kind(provider: str) -> str:
    if provider == PROVIDER_TENCENT:
        return "selected_symbols"
    if provider == PROVIDER_TENCENT_BATCH:
        return "universe_based"
    if provider == PROVIDER_EASTMONEY:
        return "full_a"
    if provider == PROVIDER_AKSHARE:
        return "full_a"
    return "unknown"


def _provider_coverage(
    provider: str,
    coverage_kind: str,
    universe_count: int = 0,
    requested: int = 0,
    success: int = 0,
    failed: int = 0,
    **extra: Any,
) -> Dict[str, Any]:
    requested_count = max(0, int(requested or 0))
    success_count = max(0, int(success or 0))
    failed_count = max(0, int(failed or 0))
    pct = round(success_count / requested_count * 100, 2) if requested_count else 0.0
    degraded = bool(extra.get("partial_failure")) or failed_count > 0
    if provider == PROVIDER_TENCENT_BATCH and requested_count:
        degraded = degraded or (success_count / requested_count) < TENCENT_BATCH_COVERAGE_DEGRADED_THRESHOLD
    if provider == PROVIDER_EASTMONEY and requested_count:
        degraded = degraded or success_count < requested_count
    data: Dict[str, Any] = {
        "source": provider,
        "coverage": coverage_kind,
        "universe_count": max(0, int(universe_count or 0)),
        "requested": requested_count,
        "success": success_count,
        "failed": failed_count,
        "coverage_pct": pct,
        "status": "degraded" if degraded else "ok",
    }
    for key, value in extra.items():
        if value is not None:
            data[key] = value
    return data


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
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


def _akshare_spot_issue(exc: Exception) -> Dict[str, Any]:
    exception_name = type(exc).__name__
    text = str(exc)
    lower_text = text.lower()
    detail = {
        "exception": exception_name,
        "host": EASTMONEY_SPOT_HOST,
        "provider": PROVIDER_AKSHARE,
    }

    if _looks_like_eastmoney_dns_failure(exception_name, lower_text):
        detail.update({"reason": "dns_resolution_failed", "retryable": True})
        return _issue(
            "AKSHARE_EASTMONEY_DNS_FAILED",
            "无法解析东方财富行情域名 %s，akshare 全 A 行情未获取。请检查 DNS/网络后重试；如需降级，只能使用 --provider auto 做选定标的兜底。"
            % EASTMONEY_SPOT_HOST,
            detail,
        )
    if _looks_like_tls_failure(exception_name, lower_text):
        detail.update({"reason": "tls_failed", "retryable": True})
        return _issue(
            "AKSHARE_EASTMONEY_TLS_FAILED",
            "访问东方财富行情接口时 TLS 校验失败，akshare 全 A 行情未获取。",
            detail,
        )
    if _looks_like_proxy_failure(exception_name, lower_text):
        detail.update({"reason": "proxy_failed", "retryable": True})
        return _issue(
            "AKSHARE_EASTMONEY_PROXY_FAILED",
            "访问东方财富行情接口时代理连接失败，akshare 全 A 行情未获取。",
            detail,
        )
    if _looks_like_timeout(exception_name, lower_text):
        detail.update({"reason": "timeout", "retryable": True})
        return _issue(
            "AKSHARE_EASTMONEY_TIMEOUT",
            "访问东方财富行情接口超时，akshare 全 A 行情未获取。",
            detail,
        )

    return _issue(
        "AKSHARE_SPOT_FAILED",
        "获取全 A 行情失败: %s" % text,
        {"exception": exception_name},
    )


def _looks_like_eastmoney_dns_failure(exception_name: str, lower_text: str) -> bool:
    names = {"ConnectionError", "NameResolutionError", "NewConnectionError", "MaxRetryError", "gaierror"}
    has_dns_evidence = (
        "failed to resolve" in lower_text
        or "nameresolutionerror" in lower_text
        or "nodename nor servname" in lower_text
        or "name or service not known" in lower_text
        or "temporary failure in name resolution" in lower_text
        or "getaddrinfo failed" in lower_text
    )
    return has_dns_evidence or exception_name in names and "name resolution" in lower_text


def _looks_like_tls_failure(exception_name: str, lower_text: str) -> bool:
    return "ssl" in exception_name.lower() or "ssl" in lower_text or "certificate" in lower_text


def _looks_like_proxy_failure(exception_name: str, lower_text: str) -> bool:
    return "proxy" in exception_name.lower() or "proxy" in lower_text


def _looks_like_timeout(exception_name: str, lower_text: str) -> bool:
    names = {"Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutError"}
    return exception_name in names or "timed out" in lower_text


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
