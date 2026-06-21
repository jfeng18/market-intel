from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from .fixtures import load_quotes_file
from .models import PoolItem, Quote
from .pool_loader import DEFAULT_POOL
from .runtime import (
    read_runtime_manifest,
    runtime_holdings_path,
    runtime_missing_files,
    runtime_paths,
    runtime_profile,
    runtime_quotes_path,
)
from .trading_calendar import freshness_state
from .validation import validate_runtime


def build_runtime_status(
    items: List[PoolItem],
    max_quote_age_days: int = 3,
    today: Optional[date] = None,
    pool: str = DEFAULT_POOL,
) -> Dict[str, object]:
    current_date = today or datetime.now().astimezone().date()
    validation = validate_runtime(items)
    files = runtime_file_status()
    freshness = build_freshness(max_quote_age_days, current_date) if not validation["errors"] else missing_freshness()
    universe = build_universe_status(items, pool)
    profile = runtime_profile()
    readiness = build_readiness(validation, freshness, universe, profile)
    next_actions = build_next_actions(validation, freshness, readiness, universe, profile)

    return {
        "readiness": readiness,
        "validation": validation,
        "freshness": freshness,
        "universe": universe,
        "profile": profile,
        "files": files,
        "next_actions": next_actions,
        "agent_contract": {
            "success": "ok=true 表示可以继续执行 next_actions 中 priority 最低的 runnable 命令",
            "readiness": "ready 可直接生成日报；degraded 可生成但需复核；blocked 需要先处理 errors",
            "next_actions": "按 priority 升序执行；runnable=false 表示需要用户提供文件或修正数据",
            "stable_fields": [
                "data.readiness",
                "data.readiness.state",
                "data.readiness.can_run_daily",
                "data.validation.summary",
                "data.freshness",
                "data.freshness.state",
                "data.freshness.reason_code",
                "data.freshness.summary",
                "data.freshness.calendar_status",
                "data.freshness.degrades_review_confidence",
                "data.universe",
                "data.profile",
                "data.profile.mode",
                "data.profile.sample_datasets",
                "data.files",
                "data.next_actions",
                "data.next_actions[].priority",
                "data.next_actions[].id",
                "data.next_actions[].command",
                "data.next_actions[].reason",
                "data.next_actions[].done_when",
                "data.next_actions[].runnable",
            ],
        },
    }


def runtime_file_status() -> Dict[str, object]:
    paths = runtime_paths()
    return {
        "quotes": file_status(Path(paths["quotes"])),
        "holdings": file_status(Path(paths["holdings"])),
        "universe": file_status(Path(paths["universe"])),
        "research": file_status(Path(paths["research"])),
        "manifest": file_status(Path(paths["manifest"])),
    }


def file_status(path: Path) -> Dict[str, object]:
    exists = path.exists()
    stat = path.stat() if exists else None
    return {
        "path": display_path(path),
        "exists": exists,
        "size": stat.st_size if stat else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat() if stat else None,
    }


def display_path(path: Path) -> str:
    if path.is_absolute() and path.parent.name:
        return "%s/%s" % (path.parent.name, path.name)
    return str(path)


def build_freshness(max_quote_age_days: int, today: date) -> Dict[str, object]:
    quotes_path = runtime_quotes_path()
    if not quotes_path.exists():
        return missing_freshness()
    provider_failed_cache = provider_failed_using_cache()
    try:
        quotes = load_quotes_file(quotes_path)
    except Exception as exc:
        state = freshness_state(None, today, max_quote_age_days)
        return {
            "ok": False,
            "state": state["state"],
            "reason_code": "read_error",
            "summary": "无法读取行情文件；先修复 quotes.json。",
            "calendar_status": state["calendar_status"],
            "max_quote_age_days": max_quote_age_days,
            "trade_dates": [],
            "latest_trade_date": None,
            "quote_age_days": None,
            "is_stale": True,
            "degrades_review_confidence": True,
            "errors": [{"code": "QUOTE_FRESHNESS_READ_ERROR", "message": str(exc), "detail": {"path": str(quotes_path)}}],
            "warnings": [],
        }
    trade_dates = sorted(set(quote.trade_date for quote in quotes if quote.trade_date))
    date_errors = quote_trade_date_errors(quotes)
    latest = latest_trade_date(quotes)
    if date_errors:
        state = freshness_state(latest, today, max_quote_age_days, provider_failed_cache)
        return {
            "ok": False,
            "state": state["state"],
            "reason_code": state["reason_code"],
            "summary": state["summary"],
            "calendar_status": state["calendar_status"],
            "max_quote_age_days": max_quote_age_days,
            "trade_dates": trade_dates,
            "latest_trade_date": latest.isoformat() if latest else None,
            "quote_age_days": (today - latest).days if latest else None,
            "is_stale": True,
            "degrades_review_confidence": True,
            "errors": date_errors,
            "warnings": [],
        }
    if latest is None:
        state = freshness_state(None, today, max_quote_age_days)
        return {
            "ok": False,
            "state": state["state"],
            "reason_code": state["reason_code"],
            "summary": state["summary"],
            "calendar_status": state["calendar_status"],
            "max_quote_age_days": max_quote_age_days,
            "trade_dates": trade_dates,
            "latest_trade_date": None,
            "quote_age_days": None,
            "is_stale": True,
            "degrades_review_confidence": True,
            "errors": [{"code": "QUOTE_TRADE_DATE_MISSING", "message": "行情缺少 trade_date。", "detail": {}}],
            "warnings": [],
        }
    age_days = (today - latest).days
    state = freshness_state(latest, today, max_quote_age_days, provider_failed_cache)
    warnings = []
    if age_days < 0:
        warnings.append(
            {
                "code": "QUOTE_DATE_IN_FUTURE",
                "message": "行情日期晚于当前日期。",
                "detail": {"latest_trade_date": latest.isoformat(), "today": today.isoformat()},
            }
        )
    if state["state"] in {"stale_on_trading_day", "stale_after_market_close", "provider_failed_using_cache"}:
        warnings.append(
            {
                "code": "PROVIDER_FAILED_USING_CACHE" if state["state"] == "provider_failed_using_cache" else "QUOTE_DATA_STALE",
                "message": "行情 provider 失败后使用缓存。" if state["state"] == "provider_failed_using_cache" else "行情日期过旧。",
                "detail": {
                    "latest_trade_date": latest.isoformat(),
                    "today": today.isoformat(),
                    "quote_age_days": age_days,
                    "max_quote_age_days": max_quote_age_days,
                    "freshness_state": state["state"],
                    "reason_code": state["reason_code"],
                },
            }
        )
    return {
        "ok": not bool(warnings) or state["state"] == "market_closed_expected_stale",
        "state": state["state"],
        "reason_code": state["reason_code"],
        "summary": state["summary"],
        "calendar_status": state["calendar_status"],
        "max_quote_age_days": max_quote_age_days,
        "trade_dates": trade_dates,
        "latest_trade_date": latest.isoformat(),
        "quote_age_days": age_days,
        "is_stale": state["state"] in {"stale_on_trading_day", "stale_after_market_close", "provider_failed_using_cache"},
        "degrades_review_confidence": state["degrades_review_confidence"],
        "errors": [],
        "warnings": warnings,
    }


def provider_failed_using_cache() -> bool:
    manifest = read_runtime_manifest()
    quotes = manifest.get("quotes", {}) if isinstance(manifest.get("quotes"), dict) else {}
    return bool(quotes.get("provider_failed_using_cache"))


def quote_trade_date_errors(quotes: List[Quote]) -> List[Dict[str, object]]:
    errors = []
    for index, quote in enumerate(quotes):
        text = str(quote.trade_date or "").strip()
        if not text:
            errors.append(
                {
                    "code": "QUOTE_TRADE_DATE_MISSING",
                    "message": "行情缺少 trade_date。",
                    "detail": {"index": index, "symbol": quote.symbol},
                }
            )
            continue
        try:
            date.fromisoformat(text[:10])
        except ValueError:
            errors.append(
                {
                    "code": "QUOTE_TRADE_DATE_INVALID",
                    "message": "行情 trade_date 不是 ISO 日期。",
                    "detail": {"index": index, "symbol": quote.symbol, "trade_date": text},
                }
            )
    return errors


def missing_freshness() -> Dict[str, object]:
    return {
        "ok": False,
        "state": "missing",
        "reason_code": "missing_quotes",
        "summary": "runtime 缺少 quotes.json；先初始化或导入行情。",
        "calendar_status": None,
        "max_quote_age_days": None,
        "trade_dates": [],
        "latest_trade_date": None,
        "quote_age_days": None,
        "is_stale": True,
        "degrades_review_confidence": True,
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


def build_universe_status(items: List[PoolItem], pool: str) -> Dict[str, object]:
    universe_items = [
        item
        for item in items
        if str(item.raw.get("pool_source") or "").startswith("universe:") or item.raw.get("universe_schema")
    ]
    runtime_path = Path(runtime_paths()["universe"])
    if pool != DEFAULT_POOL:
        return {
            "required": False,
            "state": "not_applicable",
            "record_count": len(universe_items),
            "file": file_status(runtime_path),
            "warnings": [],
        }
    if not runtime_path.exists() and not universe_items:
        return {
            "required": True,
            "state": "missing",
            "record_count": 0,
            "file": file_status(runtime_path),
            "warnings": [
                {
                    "code": "A_SHARE_UNIVERSE_MISSING",
                    "message": "all-a 缺少 A 股基础清单，当前只能按种子覆盖解读。",
                    "detail": {"path": runtime_path.name},
                }
            ],
        }
    if not universe_items:
        return {
            "required": True,
            "state": "empty",
            "record_count": 0,
            "file": file_status(runtime_path),
            "warnings": [
                {
                    "code": "A_SHARE_UNIVERSE_EMPTY",
                    "message": "A 股基础清单文件存在，但未形成可用记录。",
                    "detail": {"path": runtime_path.name},
                }
            ],
        }
    industries = {str(item.raw.get("universe_industry") or "").strip() for item in universe_items}
    industries.discard("")
    warnings = []
    if not industries:
        warnings.append(
            {
                "code": "A_SHARE_UNIVERSE_INDUSTRY_MISSING",
                "message": "A 股基础清单缺少行业字段，行业复盘底座仍不完整。",
                "detail": {"record_count": len(universe_items)},
            }
        )
    return {
        "required": True,
        "state": "ready" if not warnings else "degraded",
        "record_count": len(universe_items),
        "industry_count": len(industries),
        "file": file_status(runtime_path),
        "warnings": warnings,
    }


def build_readiness(
    validation: Dict[str, object],
    freshness: Dict[str, object],
    universe: Dict[str, object],
    profile: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    validation_error_count = (
        int(validation.get("summary", {}).get("error_count", 0)) if isinstance(validation.get("summary"), dict) else 0
    )
    warning_count = int(validation.get("summary", {}).get("warning_count", 0)) if isinstance(validation.get("summary"), dict) else 0
    freshness_error_count = len(freshness.get("errors", [])) if isinstance(freshness.get("errors"), list) else 0
    freshness_warning_count = len(freshness.get("warnings", [])) if isinstance(freshness.get("warnings"), list) else 0
    universe_warning_count = len(universe.get("warnings", [])) if isinstance(universe.get("warnings"), list) else 0
    profile_data = profile if isinstance(profile, dict) else {}
    profile_warning_count = len(profile_data.get("warnings", [])) if isinstance(profile_data.get("warnings"), list) else 0
    error_count = validation_error_count + freshness_error_count
    if error_count:
        state = "blocked"
    elif warning_count or freshness_warning_count or universe_warning_count or profile_warning_count:
        state = "degraded"
    else:
        state = "ready"
    return {
        "state": state,
        "can_run_daily": state != "blocked",
        "error_count": error_count,
        "warning_count": warning_count + freshness_warning_count + universe_warning_count + profile_warning_count,
        "reason": readiness_reason(
            state,
            error_count,
            warning_count,
            freshness_warning_count,
            universe_warning_count,
            profile_warning_count,
        ),
    }


def readiness_reason(
    state: str,
    error_count: int,
    warning_count: int,
    freshness_warning_count: int,
    universe_warning_count: int,
    profile_warning_count: int = 0,
) -> str:
    if state == "blocked":
        return "runtime 数据存在错误，先处理 errors。"
    if state == "degraded":
        return "runtime 可生成报告，但有 %s 个数据告警、%s 个新鲜度告警、%s 个 universe 告警和 %s 个来源告警。" % (
            warning_count,
            freshness_warning_count,
            universe_warning_count,
            profile_warning_count,
        )
    return "runtime 数据可用，可以生成日报。"


def build_next_actions(
    validation: Dict[str, object],
    freshness: Dict[str, object],
    readiness: Dict[str, object],
    universe: Dict[str, object],
    profile: Optional[Dict[str, object]] = None,
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
                "runtime 目录存在，quotes、holdings 和全 A 基础清单模板已生成或已准备导入。",
                runnable=True,
            )
        )
        actions.append(
            action(
                20,
                "inspect_import_schema",
                "market-intel import schema --json",
                "查看 CSV 导入字段合同。",
                "已确认 quotes、holdings、a_share_universe 和 research_notes 可接受字段。",
                runnable=True,
            )
        )
        return actions

    profile_data = profile if isinstance(profile, dict) else {}
    if profile_data.get("mode") == "sample":
        actions.extend(sample_runtime_actions(profile_data))

    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    if errors:
        actions.append(
            action(
                10,
                "fix_runtime_errors",
                "market-intel validate runtime --json",
                "修复 validation.errors 后再生成日报。",
                "validate runtime 返回 errors=[]，再重新运行 status runtime。",
                runnable=False,
            )
        )
        return actions

    if freshness.get("is_stale"):
        stale_reason = str(freshness.get("summary") or "行情日期过旧或缺失，先刷新 quotes.json。")
        actions.append(
            action(
                10,
                "refresh_quotes",
                "market-intel import quotes <quotes.csv> --runtime --json",
                stale_reason,
                "quotes.json 已更新到可接受交易日，freshness.errors 清空且 is_stale=false。",
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
                "已确认 warnings 是否可接受，或导入修正后的 runtime 数据。",
                runnable=True,
            )
        )
    if universe.get("required") and universe.get("state") in {"missing", "empty", "degraded"}:
        actions.append(
            action(
                15,
                "export_a_share_universe_patch",
                "market-intel pool universe --runtime --dry-run --json",
                "先导出 A 股基础清单补丁草稿，减少种子覆盖偏差。",
                "dry-run 已预览可检查的 A 股基础清单补丁；如果为空，先准备真实 <a_share_universe.csv>。",
                runnable=True,
            )
        )
        actions.append(
            action(
                16,
                "import_a_share_universe",
                "market-intel import universe <a_share_universe.csv> --runtime --dry-run --json",
                "用真实 A 股基础清单 dry-run 校验字段和覆盖变化。",
                "真实 A 股基础清单 dry-run 无 errors，确认 warnings 后再去掉 --dry-run 写入 runtime。",
                runnable=False,
            )
        )
    actions.append(
        action(
            30,
            "run_daily_report",
            "market-intel daily --runtime --text",
            "生成日常复盘报告。",
            "已阅读文本日报并确认风险、证据缺口和下一步命令。",
            runnable=bool(readiness.get("can_run_daily")),
        )
    )
    actions.append(
        action(
            40,
            "run_daily_json",
            "market-intel daily --runtime --json",
            "给 agent 读取完整结构化日报。",
            "agent 已读取 JSON 日报，并记录 review_path、risk_register 和 command_queue。",
            runnable=bool(readiness.get("can_run_daily")),
        )
    )
    return sorted(actions, key=lambda item: int(item.get("priority", 999)))


def sample_runtime_actions(profile: Dict[str, object]) -> List[Dict[str, object]]:
    sample_datasets = set(profile.get("sample_datasets", [])) if isinstance(profile.get("sample_datasets"), list) else set()
    rows = []
    if "quotes" in sample_datasets:
        rows.append(
            action(
                11,
                "import_real_quotes",
                "market-intel import quotes <quotes.csv> --runtime --dry-run --json",
                "当前 quotes 来自 init 示例数据；正式复盘前先 dry-run 真实行情。",
                "真实 quotes dry-run 无 errors，确认字段后去掉 --dry-run 写入 runtime。",
                runnable=False,
            )
        )
    if "holdings" in sample_datasets:
        rows.append(
            action(
                12,
                "import_real_holdings",
                "market-intel import holdings <holdings.csv> --runtime --dry-run --json",
                "当前 holdings 来自 init 示例数据；正式复盘前先 dry-run 真实持仓。",
                "真实 holdings dry-run 无 errors，确认字段后去掉 --dry-run 写入 runtime。",
                runnable=False,
            )
        )
    if "universe" in sample_datasets:
        rows.append(
            action(
                13,
                "import_real_universe",
                "market-intel import universe <a_share_universe.csv> --runtime --dry-run --json",
                "当前 A 股基础清单来自示例数据；正式全 A 复盘前先 dry-run 真实清单。",
                "真实 universe dry-run 无 errors，确认覆盖变化后去掉 --dry-run 写入 runtime。",
                runnable=False,
            )
        )
    if "research" in sample_datasets:
        rows.append(
            action(
                14,
                "import_real_research",
                "market-intel import research <research_notes.csv> --runtime --dry-run --json",
                "当前 research notes 来自示例数据；正式复盘前先 dry-run 真实研究证据。",
                "真实 research dry-run 无 errors，确认 reviewed 记录证据齐全后写入 runtime。",
                runnable=False,
            )
        )
    return rows


def action(priority: int, action_id: str, command: str, reason: str, done_when: str, runnable: bool) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": action_id,
        "command": command,
        "reason": reason,
        "done_when": done_when,
        "runnable": runnable,
    }
