"""One-command review: sync + daily + change tracking + journal save."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .agent import command_queue_item
from .journal import (
    compare_daily_payloads,
    list_journal_entries,
    read_journal_by_id,
    save_daily_journal,
)


WINDOW_DAYS = {
    "day": 1,
    "week": 7,
    "month": 30,
}


def build_review_report(
    sync_result: Dict[str, Any],
    daily_payload: Dict[str, Any],
    window: str = "day",
    save_journal: bool = True,
    runtime_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a combined review report from sync + daily + change tracking.

    The change tracking section is placed first in the output to surface
    what's different since the last review.
    """
    warnings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    sync_errors = sync_result.get("errors", []) if isinstance(sync_result.get("errors"), list) else []
    sync_ok = not sync_errors
    daily_ok = daily_payload.get("ok", False)

    if not sync_ok:
        errors.extend(sync_errors)
    if not daily_ok:
        daily_errors = daily_payload.get("errors", [])
        if isinstance(daily_errors, list):
            errors.extend(daily_errors)

    changes = _build_changes(daily_payload, window, warnings)

    journal_entry = None
    profile = runtime_profile if isinstance(runtime_profile, dict) else {}
    journal_status = _journal_status(save_journal, daily_ok, sync_ok, profile)
    if journal_status["can_save"]:
        journal_result = save_daily_journal(daily_payload)
        if journal_result.get("saved"):
            journal_entry = journal_result.get("entry")
            journal_status["saved"] = True
            journal_status["reason"] = "日报已写入 journal。"
        else:
            journal_errors = journal_result.get("errors", [])
            if isinstance(journal_errors, list):
                warnings.extend(journal_errors)
                journal_status["reason"] = "journal 写入失败。"
    elif save_journal and daily_ok and not sync_ok:
        warnings.append(_issue(
            "REVIEW_JOURNAL_SKIPPED_SYNC_FAILED",
            "同步失败，本次复盘未写入 journal，避免用旧行情污染变化追踪。",
            {},
        ))
    elif journal_status["code"] == "sample_runtime":
        warnings.append(_issue(
            "REVIEW_JOURNAL_SKIPPED_SAMPLE_RUNTIME",
            "runtime 仍包含样例数据，本次复盘未写入 journal。",
            {"sample_datasets": journal_status.get("sample_datasets", [])},
        ))

    daily_data = daily_payload.get("data", {}) if isinstance(daily_payload.get("data"), dict) else {}
    next_commands = _next_commands(window, journal_entry, journal_status)

    return {
        "window": window,
        "changes": changes,
        "sync": _compact_sync(sync_result),
        "daily_summary": daily_data.get("summary", ""),
        "risk_flags": daily_data.get("risk_flags", []),
        "brief": daily_data.get("brief"),
        "watchlist": daily_data.get("watchlist"),
        "portfolio_review": daily_data.get("portfolio_review"),
        "validation": daily_data.get("validation"),
        "journal_saved": journal_entry is not None,
        "journal_entry": _compact_journal_entry(journal_entry) if journal_entry else None,
        "journal_status": journal_status,
        "next_commands": next_commands,
        "command_queue": _command_queue(next_commands),
        "agent_contract": _agent_contract(),
        "warnings": warnings,
        "errors": errors,
    }


def _build_changes(
    daily_payload: Dict[str, Any],
    window: str,
    warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Find a journal entry within the window and compare with current daily."""
    max_days = WINDOW_DAYS.get(window, 1)
    listed = list_journal_entries(limit=100)
    entries = listed.get("entries", []) if isinstance(listed.get("entries"), list) else []

    if not entries:
        return _empty_changes(window, "还没有历史日报留档，无法对比变化。")

    base_entry = _find_entry_in_window(entries, max_days)
    if base_entry is None:
        return _empty_changes(window, "在 %s 窗口内未找到历史日报留档。" % _window_label(window))

    base_record = read_journal_by_id(str(base_entry.get("id")))
    if not base_record.get("found"):
        warnings.extend(base_record.get("errors", []) if isinstance(base_record.get("errors"), list) else [])
        return _empty_changes(window, "无法读取历史日报留档。")

    base_payload = base_record.get("payload", {}) if isinstance(base_record.get("payload"), dict) else {}
    changes = compare_daily_payloads(base_payload, daily_payload)

    return {
        "available": True,
        "window": window,
        "window_label": _window_label(window),
        "base_trade_date": base_entry.get("trade_date"),
        "base_entry_id": str(base_entry.get("id", "")),
        "summary": _summarize_changes(base_entry, changes, window),
        "risk_flags": changes.get("risk_flags", {}),
        "watchlist": changes.get("watchlist", {}),
        "portfolio_review": changes.get("portfolio_review", {}),
        "hotspots": changes.get("hotspots", {}),
        "validation": changes.get("validation", {}),
    }


def _find_entry_in_window(entries: List[Dict[str, Any]], max_days: int) -> Optional[Dict[str, Any]]:
    """Find the oldest journal entry within the given time window."""
    now = datetime.now().astimezone()
    cutoff = now - timedelta(days=max_days)

    candidates = []
    for entry in entries:
        generated_at = entry.get("generated_at")
        if not generated_at:
            continue
        try:
            entry_time = datetime.fromisoformat(str(generated_at))
            if entry_time >= cutoff:
                candidates.append((entry_time, entry))
        except (ValueError, TypeError):
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _summarize_changes(
    base_entry: Dict[str, Any],
    changes: Dict[str, Any],
    window: str,
) -> str:
    risk = changes.get("risk_flags", {}) if isinstance(changes.get("risk_flags"), dict) else {}
    watchlist = changes.get("watchlist", {}) if isinstance(changes.get("watchlist"), dict) else {}
    portfolio = changes.get("portfolio_review", {}) if isinstance(changes.get("portfolio_review"), dict) else {}
    hotspots = changes.get("hotspots", {}) if isinstance(changes.get("hotspots"), dict) else {}

    added_risks = len(risk.get("added", [])) if isinstance(risk.get("added"), list) else 0
    removed_risks = len(risk.get("removed", [])) if isinstance(risk.get("removed"), list) else 0
    added_watch = len(watchlist.get("added", [])) if isinstance(watchlist.get("added"), list) else 0
    removed_watch = len(watchlist.get("removed", [])) if isinstance(watchlist.get("removed"), list) else 0
    changed_watch = len(watchlist.get("changed", [])) if isinstance(watchlist.get("changed"), list) else 0

    parts = []
    parts.append("对比 %s（%s）" % (base_entry.get("trade_date", "?"), _window_label(window)))

    if added_risks or removed_risks:
        parts.append("风险 +%d/-%d" % (added_risks, removed_risks))
    if added_watch or removed_watch or changed_watch:
        parts.append("观察 +%d/-%d/~%d" % (added_watch, removed_watch, changed_watch))

    added_portfolio = len(portfolio.get("added", [])) if isinstance(portfolio.get("added"), list) else 0
    removed_portfolio = len(portfolio.get("removed", [])) if isinstance(portfolio.get("removed"), list) else 0
    if added_portfolio or removed_portfolio:
        parts.append("持仓 +%d/-%d" % (added_portfolio, removed_portfolio))

    added_hotspots = len(hotspots.get("added", [])) if isinstance(hotspots.get("added"), list) else 0
    removed_hotspots = len(hotspots.get("removed", [])) if isinstance(hotspots.get("removed"), list) else 0
    if added_hotspots or removed_hotspots:
        parts.append("热点 +%d/-%d" % (added_hotspots, removed_hotspots))

    if len(parts) == 1:
        parts.append("无显著变化")

    return "；".join(parts) + "。"


def _compact_sync(sync_result: Dict[str, Any]) -> Dict[str, Any]:
    errors = sync_result.get("errors", []) if isinstance(sync_result.get("errors"), list) else []
    skipped = bool(sync_result.get("skipped"))
    return {
        "ok": not errors,
        "status": "skipped" if skipped else "ok" if not errors else "failed",
        "skipped": skipped,
        "record_count": sync_result.get("record_count", 0),
        "trade_date": sync_result.get("trade_date"),
        "summary": sync_result.get("summary"),
    }


def _compact_journal_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": entry.get("id"),
        "trade_date": entry.get("trade_date"),
        "path": entry.get("path"),
    }


def _journal_status(
    save_journal: bool,
    daily_ok: bool,
    sync_ok: bool,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    sample_datasets = (
        profile.get("sample_datasets", [])
        if isinstance(profile.get("sample_datasets"), list)
        else []
    )
    if not save_journal:
        return {"can_save": False, "saved": False, "code": "disabled", "reason": "用户使用 --no-save 跳过留档。"}
    if not daily_ok:
        return {"can_save": False, "saved": False, "code": "daily_failed", "reason": "daily 执行失败，未写入 journal。"}
    if not sync_ok:
        return {"can_save": False, "saved": False, "code": "sync_failed", "reason": "同步失败，未写入 journal。"}
    if profile.get("mode") == "sample" or sample_datasets:
        return {
            "can_save": False,
            "saved": False,
            "code": "sample_runtime",
            "reason": "runtime 仍包含样例数据，未写入 journal。",
            "sample_datasets": sample_datasets,
        }
    return {"can_save": True, "saved": False, "code": "ready", "reason": "runtime 可写入 journal。"}


def _empty_changes(window: str, reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "window": window,
        "window_label": _window_label(window),
        "base_trade_date": None,
        "base_entry_id": None,
        "summary": reason,
        "risk_flags": {},
        "watchlist": {},
        "portfolio_review": {},
        "hotspots": {},
        "validation": {},
    }


def _window_label(window: str) -> str:
    labels = {"day": "日级", "week": "周级", "month": "月级"}
    return labels.get(window, "日级")


def _next_commands(
    window: str,
    journal_entry: Optional[Dict[str, Any]],
    journal_status: Optional[Dict[str, Any]] = None,
) -> List[str]:
    status = journal_status if isinstance(journal_status, dict) else {}
    if status.get("code") == "sample_runtime":
        return _sample_runtime_commands(status)
    commands = []
    if journal_entry:
        commands.append("market-intel journal show %s --text" % journal_entry.get("id"))
    if window == "day":
        commands.append("market-intel review --window week --no-sync --no-save --text")
    elif window == "week":
        commands.append("market-intel review --window month --no-sync --no-save --text")
    commands.append("market-intel journal timeline --text")
    commands.append("market-intel focus --runtime --text")
    return commands


def _sample_runtime_commands(journal_status: Dict[str, Any]) -> List[str]:
    commands = ["market-intel sync quotes"]
    sample_datasets = (
        journal_status.get("sample_datasets", [])
        if isinstance(journal_status.get("sample_datasets"), list)
        else []
    )
    sample_set = set(str(item) for item in sample_datasets)
    if not sample_set or "holdings" in sample_set:
        commands.append("market-intel import holdings <holdings.csv> --runtime")
    if not sample_set or "universe" in sample_set:
        commands.append("market-intel import universe <a_share_universe.csv> --runtime --dry-run --json")
    if not sample_set or "research" in sample_set:
        commands.append("market-intel import research <research_notes.csv> --runtime --dry-run --json")
    commands.append("market-intel status runtime --text")
    return commands


def _command_queue(commands: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for command in commands:
        item = command_queue_item(command, len(rows) + 1, _command_focus(command))
        item["runnable"] = bool(item.get("runnable", True))
        item["source"] = "review.next_commands"
        rows.append(item)
    return rows


def _command_focus(command: str) -> List[str]:
    if " journal show " in " %s " % command:
        return ["日报留档"]
    if " journal timeline " in " %s " % command:
        return ["历史时间线"]
    if " review " in " %s " % command:
        return ["变化追踪"]
    if " focus " in " %s " % command:
        return ["复盘工作台"]
    return ["复盘后续"]


def _agent_contract() -> Dict[str, Any]:
    return {
        "stable_fields": [
            "data.window",
            "data.changes",
            "data.changes.summary",
            "data.sync",
            "data.daily_summary",
            "data.risk_flags",
            "data.journal_saved",
            "data.journal_status",
            "data.journal_status.code",
            "data.next_commands",
            "data.command_queue",
            "data.command_queue[].command",
            "data.command_queue[].json_command",
            "data.command_queue[].runnable",
            "data.command_queue[].state_effect",
            "data.command_queue[].done_when",
        ],
        "boundary": "不产生交易指令、目标价或仓位建议。",
        "read_order": [
            "data.changes.summary",
            "data.daily_summary",
            "data.risk_flags",
            "data.changes.risk_flags",
            "data.changes.watchlist",
            "data.changes.portfolio_review",
            "data.changes.hotspots",
            "data.brief",
            "data.watchlist",
            "data.portfolio_review",
            "data.command_queue",
        ],
    }


def _issue(code: str, message: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail}
