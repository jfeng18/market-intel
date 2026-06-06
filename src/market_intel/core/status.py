from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from .fixtures import load_quotes_file
from .models import PoolItem, Quote
from .runtime import runtime_holdings_path, runtime_missing_files, runtime_paths, runtime_quotes_path
from .validation import validate_runtime


def build_runtime_status(
    items: List[PoolItem],
    max_quote_age_days: int = 3,
    today: Optional[date] = None,
) -> Dict[str, object]:
    current_date = today or datetime.now().astimezone().date()
    validation = validate_runtime(items)
    files = runtime_file_status()
    freshness = build_freshness(max_quote_age_days, current_date) if not validation["errors"] else missing_freshness()
    readiness = build_readiness(validation, freshness)
    next_actions = build_next_actions(validation, freshness, readiness)

    return {
        "readiness": readiness,
        "validation": validation,
        "freshness": freshness,
        "files": files,
        "next_actions": next_actions,
        "agent_contract": {
            "success": "ok=true 表示可以继续执行 next_actions 中 priority 最低的 runnable 命令",
            "readiness": "ready 可直接生成日报；degraded 可生成但需复核；blocked 需要先处理 errors",
            "next_actions": "按 priority 升序执行；runnable=false 表示需要用户提供文件或修正数据",
        },
    }


def runtime_file_status() -> Dict[str, object]:
    paths = runtime_paths()
    return {
        "quotes": file_status(Path(paths["quotes"])),
        "holdings": file_status(Path(paths["holdings"])),
    }


def file_status(path: Path) -> Dict[str, object]:
    exists = path.exists()
    stat = path.stat() if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "size": stat.st_size if stat else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat() if stat else None,
    }


def build_freshness(max_quote_age_days: int, today: date) -> Dict[str, object]:
    quotes_path = runtime_quotes_path()
    if not quotes_path.exists():
        return missing_freshness()
    try:
        quotes = load_quotes_file(quotes_path)
    except Exception as exc:
        return {
            "ok": False,
            "max_quote_age_days": max_quote_age_days,
            "trade_dates": [],
            "latest_trade_date": None,
            "quote_age_days": None,
            "is_stale": True,
            "errors": [{"code": "QUOTE_FRESHNESS_READ_ERROR", "message": str(exc), "detail": {"path": str(quotes_path)}}],
            "warnings": [],
        }
    trade_dates = sorted(set(quote.trade_date for quote in quotes if quote.trade_date))
    latest = latest_trade_date(quotes)
    if latest is None:
        return {
            "ok": False,
            "max_quote_age_days": max_quote_age_days,
            "trade_dates": trade_dates,
            "latest_trade_date": None,
            "quote_age_days": None,
            "is_stale": True,
            "errors": [{"code": "QUOTE_TRADE_DATE_MISSING", "message": "行情缺少 trade_date。", "detail": {}}],
            "warnings": [],
        }
    age_days = (today - latest).days
    warnings = []
    if age_days < 0:
        warnings.append(
            {
                "code": "QUOTE_DATE_IN_FUTURE",
                "message": "行情日期晚于当前日期。",
                "detail": {"latest_trade_date": latest.isoformat(), "today": today.isoformat()},
            }
        )
    if age_days > max_quote_age_days:
        warnings.append(
            {
                "code": "QUOTE_DATA_STALE",
                "message": "行情日期过旧。",
                "detail": {
                    "latest_trade_date": latest.isoformat(),
                    "today": today.isoformat(),
                    "quote_age_days": age_days,
                    "max_quote_age_days": max_quote_age_days,
                },
            }
        )
    return {
        "ok": not warnings,
        "max_quote_age_days": max_quote_age_days,
        "trade_dates": trade_dates,
        "latest_trade_date": latest.isoformat(),
        "quote_age_days": age_days,
        "is_stale": age_days > max_quote_age_days,
        "errors": [],
        "warnings": warnings,
    }


def missing_freshness() -> Dict[str, object]:
    return {
        "ok": False,
        "max_quote_age_days": None,
        "trade_dates": [],
        "latest_trade_date": None,
        "quote_age_days": None,
        "is_stale": True,
        "errors": [],
        "warnings": [],
    }


def latest_trade_date(quotes: List[Quote]) -> Optional[date]:
    dates = []
    for quote in quotes:
        if not quote.trade_date:
            continue
        try:
            dates.append(date.fromisoformat(quote.trade_date[:10]))
        except ValueError:
            continue
    return max(dates) if dates else None


def build_readiness(validation: Dict[str, object], freshness: Dict[str, object]) -> Dict[str, object]:
    error_count = int(validation.get("summary", {}).get("error_count", 0)) if isinstance(validation.get("summary"), dict) else 0
    warning_count = int(validation.get("summary", {}).get("warning_count", 0)) if isinstance(validation.get("summary"), dict) else 0
    freshness_warning_count = len(freshness.get("warnings", [])) if isinstance(freshness.get("warnings"), list) else 0
    if error_count:
        state = "blocked"
    elif warning_count or freshness_warning_count:
        state = "degraded"
    else:
        state = "ready"
    return {
        "state": state,
        "can_run_daily": state != "blocked",
        "error_count": error_count,
        "warning_count": warning_count + freshness_warning_count,
        "reason": readiness_reason(state, error_count, warning_count, freshness_warning_count),
    }


def readiness_reason(state: str, error_count: int, warning_count: int, freshness_warning_count: int) -> str:
    if state == "blocked":
        return "runtime 数据存在错误，先处理 errors。"
    if state == "degraded":
        return "runtime 可生成报告，但有 %s 个数据告警和 %s 个新鲜度告警。" % (warning_count, freshness_warning_count)
    return "runtime 数据可用，可以生成日报。"


def build_next_actions(
    validation: Dict[str, object],
    freshness: Dict[str, object],
    readiness: Dict[str, object],
) -> List[Dict[str, object]]:
    actions = []
    missing = runtime_missing_files()
    if missing:
        actions.append(
            action(
                10,
                "init_runtime",
                "market-intel init runtime --json",
                "runtime 文件缺失，先生成模板或导入 CSV。",
                runnable=True,
            )
        )
        actions.append(
            action(
                20,
                "inspect_import_schema",
                "market-intel import schema --json",
                "查看 CSV 导入字段合同。",
                runnable=True,
            )
        )
        return actions

    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    if errors:
        actions.append(
            action(
                10,
                "fix_runtime_errors",
                "market-intel validate runtime --json",
                "修复 validation.errors 后再生成日报。",
                runnable=False,
            )
        )
        return actions

    if freshness.get("is_stale"):
        actions.append(
            action(
                10,
                "refresh_quotes",
                "market-intel import quotes <quotes.csv> --runtime --json",
                "行情日期过旧或缺失，先刷新 quotes.json。",
                runnable=False,
            )
        )
    if readiness.get("state") == "degraded":
        actions.append(
            action(
                20,
                "review_warnings",
                "market-intel validate runtime --json",
                "复核数据告警，必要时补齐行情或持仓。",
                runnable=True,
            )
        )
    actions.append(
        action(
            30,
            "run_daily_report",
            "market-intel daily --runtime --text",
            "生成日常复盘报告。",
            runnable=bool(readiness.get("can_run_daily")),
        )
    )
    actions.append(
        action(
            40,
            "run_daily_json",
            "market-intel daily --runtime --json",
            "给 agent 读取完整结构化日报。",
            runnable=bool(readiness.get("can_run_daily")),
        )
    )
    return actions


def action(priority: int, action_id: str, command: str, reason: str, runnable: bool) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": action_id,
        "command": command,
        "reason": reason,
        "runnable": runnable,
    }
