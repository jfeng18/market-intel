import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .runtime import runtime_dir_path


JOURNAL_DIRNAME = "journal"
SAFE_ID_RE = re.compile(r"[^0-9A-Za-z_.-]+")
NOTE_MAX_LENGTH = 4000


def journal_dir_path() -> Path:
    return runtime_dir_path() / JOURNAL_DIRNAME


def save_daily_journal(payload: Dict[str, object]) -> Dict[str, object]:
    if payload.get("command") != "daily":
        return {
            "saved": False,
            "errors": [
                {
                    "code": "JOURNAL_PAYLOAD_NOT_DAILY",
                    "message": "journal save requires a daily payload.",
                    "detail": {"command": payload.get("command")},
                }
            ],
            "warnings": [],
        }
    if not payload.get("ok"):
        return {
            "saved": False,
            "errors": [
                {
                    "code": "JOURNAL_DAILY_NOT_OK",
                    "message": "daily payload is not ok.",
                    "detail": {"errors": payload.get("errors", [])},
                }
            ],
            "warnings": [],
        }

    directory = journal_dir_path()
    directory.mkdir(parents=True, exist_ok=True)
    entry = build_journal_entry(payload)
    base_id = str(entry["id"])
    path = directory / ("%s.json" % base_id)
    suffix = 2
    while path.exists():
        entry["id"] = "%s_%s" % (base_id, suffix)
        path = directory / ("%s.json" % entry["id"])
        suffix += 1
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"entry": entry, "payload": payload}, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return {
        "saved": True,
        "entry": {**entry, "path": display_path(path)},
        "journal_dir": display_path(directory),
        "next_commands": [
            "market-intel journal list --json",
            "market-intel journal latest --text",
        ],
        "errors": [],
        "warnings": [],
    }


def build_journal_entry(payload: Dict[str, object]) -> Dict[str, object]:
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    generated_at = payload.get("meta", {}).get("generated_at") if isinstance(payload.get("meta"), dict) else None
    trade_date = infer_trade_date(data)
    generated_part = safe_id(str(generated_at or datetime.now().astimezone().isoformat()))
    entry_id = "%s_%s" % (safe_id(trade_date or "unknown-date"), generated_part)
    summary = str(data.get("summary") or "")
    risk_flags = data.get("risk_flags", []) if isinstance(data.get("risk_flags"), list) else []
    watchlist = data.get("watchlist", {}) if isinstance(data.get("watchlist"), dict) else {}
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    return {
        "id": entry_id,
        "trade_date": trade_date,
        "generated_at": generated_at,
        "summary": summary,
        "risk_flags": risk_flags,
        "watchlist_count": watchlist.get("count"),
        "validation_summary": validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {},
        "mode": data.get("mode"),
        "pool": data.get("pool"),
    }


def list_journal_entries(limit: int = 10) -> Dict[str, object]:
    directory = journal_dir_path()
    entries = []
    errors = []
    if directory.exists():
        for path in sorted(directory.glob("*.json"), reverse=True):
            try:
                record = read_journal_record(path)
                entry = record["entry"]
                entry["path"] = display_path(path)
                entries.append(entry)
            except Exception as exc:
                errors.append(
                    {
                        "code": "JOURNAL_ENTRY_READ_ERROR",
                        "message": str(exc),
                        "detail": {"path": display_path(path)},
                    }
                )
    entries.sort(key=lambda entry: _parse_timestamp(entry.get("generated_at")), reverse=True)
    limited = entries[:limit]
    return {
        "journal_dir": display_path(directory),
        "count": len(limited),
        "total_count": len(entries),
        "entries": limited,
        "errors": errors,
        "warnings": [],
        "next_commands": next_commands_for_entries(limited),
    }


def latest_journal_entry() -> Dict[str, object]:
    listed = list_journal_entries(limit=1)
    if not listed["entries"]:
        return {
            "found": False,
            "journal_dir": listed["journal_dir"],
            "entry": None,
            "payload": None,
            "errors": [],
            "warnings": [],
            "next_commands": ["market-intel daily --runtime --json", "market-intel journal save --runtime --json"],
        }
    return read_journal_by_id(str(listed["entries"][0]["id"]))


def read_journal_by_id(entry_id: str) -> Dict[str, object]:
    path = journal_dir_path() / ("%s.json" % safe_id(entry_id))
    if not path.exists():
        return {
            "found": False,
            "journal_dir": display_path(journal_dir_path()),
            "entry": None,
            "payload": None,
            "errors": [
                {
                    "code": "JOURNAL_ENTRY_NOT_FOUND",
                    "message": "journal entry not found.",
                    "detail": {"id": entry_id, "path": display_path(path)},
                }
            ],
            "warnings": [],
            "next_commands": ["market-intel journal list --json"],
        }
    record = read_journal_record(path)
    entry = record["entry"]
    entry["path"] = display_path(path)
    return {
        "found": True,
        "journal_dir": display_path(journal_dir_path()),
        "entry": entry,
        "payload": record["payload"],
        "notes": record.get("notes", []),
        "errors": [],
        "warnings": [],
        "next_commands": ["market-intel journal list --json"],
    }


def save_journal_note(entry_id: Optional[str], note_text: str, section: Optional[str] = None) -> Dict[str, object]:
    normalized = normalize_note_text(note_text)
    if not normalized:
        return empty_note_result(
            [
                journal_issue(
                    "JOURNAL_NOTE_EMPTY",
                    "Journal note text is required.",
                    {"entry_id": entry_id},
                )
            ]
        )

    target = read_journal_by_id(entry_id) if entry_id else latest_journal_entry()
    if not target.get("found"):
        return empty_note_result(target.get("errors", []) if isinstance(target.get("errors"), list) else [])

    entry = target.get("entry", {}) if isinstance(target.get("entry"), dict) else {}
    path = journal_dir_path() / ("%s.json" % safe_id(str(entry.get("id") or "")))
    record = read_journal_record(path)
    notes = record.get("notes", []) if isinstance(record.get("notes"), list) else []
    note = build_journal_note(normalized, section)
    notes.append(note)
    record["notes"] = notes
    with path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return {
        "saved": True,
        "entry": {**entry, "path": display_path(path)},
        "note": note,
        "note_count": len(notes),
        "journal_dir": display_path(journal_dir_path()),
        "next_commands": [
            "market-intel journal latest --text",
            "market-intel journal show %s --text" % entry.get("id"),
        ],
        "errors": [],
        "warnings": [],
    }


def list_journal_notes(limit: int = 10, section: Optional[str] = None, query: Optional[str] = None) -> Dict[str, object]:
    safe_limit = max(1, int_or_none(limit) or 10)
    section_filter = str(section or "").strip()
    query_filter = str(query or "").strip().lower()
    listed = list_journal_entries(limit=1000)
    notes: List[Dict[str, object]] = []
    warnings: List[Dict[str, object]] = []
    warnings.extend(listed.get("errors", []) if isinstance(listed.get("errors"), list) else [])
    entries = listed.get("entries", []) if isinstance(listed.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        record = read_journal_by_id(str(entry.get("id")))
        if not record.get("found"):
            warnings.extend(record.get("errors", []) if isinstance(record.get("errors"), list) else [])
            continue
        for note in record.get("notes", []) if isinstance(record.get("notes"), list) else []:
            if not isinstance(note, dict):
                continue
            if section_filter and str(note.get("section") or "") != section_filter:
                continue
            if query_filter and query_filter not in str(note.get("text") or "").lower():
                continue
            notes.append(
                {
                    "id": note.get("id"),
                    "created_at": note.get("created_at"),
                    "section": note.get("section"),
                    "text": note.get("text"),
                    "entry_id": entry.get("id"),
                    "trade_date": entry.get("trade_date"),
                    "entry_summary": entry.get("summary"),
                    "commands": [
                        "market-intel journal show %s --text" % entry.get("id"),
                        "market-intel journal show %s --json" % entry.get("id"),
                    ],
                }
            )
    notes.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")), reverse=True)
    limited = notes[:safe_limit]
    return {
        "found": bool(notes),
        "journal_dir": display_path(journal_dir_path()),
        "limit": safe_limit,
        "filters": {"section": section_filter or None, "query": query or None},
        "count": len(limited),
        "total_count": len(notes),
        "notes": limited,
        "agent_contract": journal_notes_contract(),
        "next_commands": ["market-intel journal notes --text", "market-intel journal timeline --text"],
        "errors": [],
        "warnings": warnings,
    }


def journal_notes_contract() -> Dict[str, object]:
    return {
        "success": "ok=true；data.found=false 只表示还没有用户复盘笔记",
        "order": "data.notes 按 note.created_at 从新到旧排列",
        "stable_fields": [
            "data.notes[].id",
            "data.notes[].created_at",
            "data.notes[].section",
            "data.notes[].text",
            "data.notes[].entry_id",
            "data.notes[].trade_date",
            "data.filters",
            "data.next_commands",
        ],
    }


def empty_note_result(errors: List[Dict[str, object]]) -> Dict[str, object]:
    return {
        "saved": False,
        "entry": None,
        "note": None,
        "note_count": 0,
        "journal_dir": display_path(journal_dir_path()),
        "next_commands": ["market-intel journal list --json", "market-intel journal latest --text"],
        "errors": errors,
        "warnings": [],
    }


def normalize_note_text(note_text: object) -> str:
    text = str(note_text or "").strip()
    return text[:NOTE_MAX_LENGTH]


def build_journal_note(note_text: str, section: Optional[str] = None) -> Dict[str, object]:
    created_at = datetime.now().astimezone().isoformat()
    note_id = "note_%s" % safe_id(created_at)
    return {
        "id": note_id,
        "created_at": created_at,
        "section": str(section or "general"),
        "text": note_text,
    }


def compare_journal_entries(base_id: Optional[str] = None, current_id: Optional[str] = None) -> Dict[str, object]:
    mode = "explicit_ids" if base_id or current_id else "latest_two"
    requested = {"base_id": base_id, "current_id": current_id}
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []

    if base_id or current_id:
        if not base_id or not current_id:
            errors.append(
                journal_issue(
                    "JOURNAL_COMPARE_IDS_REQUIRED",
                    "Both base and current journal entry ids are required.",
                    requested,
                )
            )
            return empty_compare_result(mode, requested, errors, warnings)
        base_record = read_journal_by_id(base_id)
        current_record = read_journal_by_id(current_id)
    else:
        listed = list_journal_entries(limit=2)
        warnings.extend(listed.get("errors", []) if isinstance(listed.get("errors"), list) else [])
        entries = listed.get("entries", []) if isinstance(listed.get("entries"), list) else []
        if len(entries) < 2:
            errors.append(
                journal_issue(
                    "JOURNAL_COMPARE_REQUIRES_TWO_ENTRIES",
                    "Journal compare requires at least two readable entries.",
                    {"readable_count": len(entries), "journal_dir": listed.get("journal_dir")},
                )
            )
            return empty_compare_result(mode, requested, errors, warnings)
        current_id = str(entries[0].get("id"))
        base_id = str(entries[1].get("id"))
        requested = {"base_id": base_id, "current_id": current_id}
        base_record = read_journal_by_id(base_id)
        current_record = read_journal_by_id(current_id)

    if not base_record.get("found"):
        errors.extend(scoped_errors(base_record.get("errors", []), "base"))
    if not current_record.get("found"):
        errors.extend(scoped_errors(current_record.get("errors", []), "current"))
    if errors:
        return empty_compare_result(mode, requested, errors, warnings)

    base_entry = base_record.get("entry", {}) if isinstance(base_record.get("entry"), dict) else {}
    current_entry = current_record.get("entry", {}) if isinstance(current_record.get("entry"), dict) else {}
    if str(base_entry.get("id")) == str(current_entry.get("id")):
        errors.append(
            journal_issue(
                "JOURNAL_COMPARE_SAME_ENTRY",
                "Base and current journal entry ids must be different.",
                {"id": base_entry.get("id")},
            )
        )
        return empty_compare_result(mode, requested, errors, warnings)

    base_payload = base_record.get("payload", {}) if isinstance(base_record.get("payload"), dict) else {}
    current_payload = current_record.get("payload", {}) if isinstance(current_record.get("payload"), dict) else {}
    changes = compare_daily_payloads(base_payload, current_payload)
    return {
        "found": True,
        "mode": mode,
        "journal_dir": display_path(journal_dir_path()),
        "requested": requested,
        "base_entry": base_entry,
        "current_entry": current_entry,
        "summary": summarize_journal_compare(base_entry, current_entry, changes),
        "changes": changes,
        "agent_contract": journal_compare_contract(),
        "next_commands": compare_next_commands(str(base_entry.get("id")), str(current_entry.get("id"))),
        "errors": errors,
        "warnings": warnings,
    }


def compare_latest_journal_to_payload(current_payload: Dict[str, object]) -> Dict[str, object]:
    latest = latest_journal_entry()
    if not latest.get("found"):
        return empty_current_compare_result(
            errors=[],
            warnings=latest.get("warnings", []) if isinstance(latest.get("warnings"), list) else [],
        )
    if current_payload.get("command") != "daily" or not current_payload.get("ok"):
        return empty_current_compare_result(
            errors=[
                journal_issue(
                    "JOURNAL_CURRENT_PAYLOAD_NOT_DAILY",
                    "Current payload must be an ok daily payload.",
                    {"command": current_payload.get("command"), "ok": current_payload.get("ok")},
                )
            ],
            warnings=[],
        )
    base_entry = latest.get("entry", {}) if isinstance(latest.get("entry"), dict) else {}
    base_payload = latest.get("payload", {}) if isinstance(latest.get("payload"), dict) else {}
    current_entry = build_journal_entry(current_payload)
    current_entry["id"] = "runtime_current"
    changes = compare_daily_payloads(base_payload, current_payload)
    return {
        "found": True,
        "mode": "latest_entry_to_runtime_current",
        "journal_dir": display_path(journal_dir_path()),
        "base_entry": base_entry,
        "current_entry": current_entry,
        "summary": summarize_journal_compare(base_entry, current_entry, changes),
        "changes": changes,
        "agent_contract": journal_current_compare_contract(),
        "next_commands": [
            "market-intel journal save --runtime --json",
            "market-intel journal latest --text",
            "market-intel journal timeline --text",
        ],
        "errors": [],
        "warnings": [],
    }


def empty_current_compare_result(
    errors: List[Dict[str, object]],
    warnings: List[Dict[str, object]],
) -> Dict[str, object]:
    return {
        "found": False,
        "mode": "latest_entry_to_runtime_current",
        "journal_dir": display_path(journal_dir_path()),
        "base_entry": None,
        "current_entry": None,
        "summary": "需要至少一份日报留档和当前 runtime daily 才能对比。",
        "changes": empty_changes(),
        "agent_contract": journal_current_compare_contract(),
        "next_commands": [
            "market-intel journal save --runtime --json",
            "market-intel journal latest --text",
        ],
        "errors": errors,
        "warnings": warnings,
    }


def journal_current_compare_contract() -> Dict[str, object]:
    contract = journal_compare_contract()
    return {
        **contract,
        "default_mode": "对比最近一份日报留档与当前 runtime daily，不要求先保存当前日报。",
        "current_marker": "data.current_entry.id=runtime_current 表示当前 runtime 截面。",
    }


def build_journal_timeline(limit: int = 5) -> Dict[str, object]:
    safe_limit = max(1, int_or_none(limit) or 5)
    listed = list_journal_entries(limit=safe_limit)
    warnings: List[Dict[str, object]] = []
    warnings.extend(listed.get("errors", []) if isinstance(listed.get("errors"), list) else [])
    warnings.extend(listed.get("warnings", []) if isinstance(listed.get("warnings"), list) else [])

    records = []
    entries = listed.get("entries", []) if isinstance(listed.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        record = read_journal_by_id(str(entry.get("id")))
        if record.get("found"):
            records.append(record)
        else:
            warnings.extend(record.get("errors", []) if isinstance(record.get("errors"), list) else [])

    records.sort(key=timeline_record_sort_key)
    points = [build_timeline_point(record) for record in records]
    transitions = []
    for base_record, current_record in zip(records, records[1:]):
        transitions.append(build_timeline_transition(base_record, current_record))

    return {
        "found": bool(points),
        "can_compare": len(points) >= 2,
        "journal_dir": display_path(journal_dir_path()),
        "limit": safe_limit,
        "count": len(points),
        "total_count": listed.get("total_count", len(points)),
        "order": "oldest_to_newest",
        "summary": summarize_journal_timeline(points, transitions, int_value(listed.get("total_count"), len(points))),
        "points": points,
        "transitions": transitions,
        "agent_contract": journal_timeline_contract(),
        "next_commands": timeline_next_commands(points, safe_limit),
        "errors": [],
        "warnings": warnings,
    }


def build_timeline_point(record: Dict[str, object]) -> Dict[str, object]:
    entry = record.get("entry", {}) if isinstance(record.get("entry"), dict) else {}
    payload = record.get("payload", {}) if isinstance(record.get("payload"), dict) else {}
    data = daily_data(payload)
    risk_flags = unique_text_list(data.get("risk_flags", entry.get("risk_flags", [])))
    watchlist_items = index_watchlist_items(data)
    portfolio_items = index_portfolio_items(data)
    portfolio_counts = priority_counts(portfolio_items)
    top_hotspot = first_or_none(sorted(index_hotspots(data).values(), key=lambda item: int_value(item.get("rank"), 9999)))
    validation = validation_digest(data)
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    top_portfolio_items = sorted(portfolio_items.values(), key=lambda item: int_value(item.get("rank"), 9999))[:3]
    entry_id = str(entry.get("id") or "")
    notes = compact_journal_notes(record.get("notes", []))
    return {
        "entry_id": entry_id,
        "trade_date": entry.get("trade_date") or data.get("latest_trade_date"),
        "generated_at": entry.get("generated_at"),
        "summary": entry.get("summary") or data.get("summary"),
        "note_count": len(record.get("notes", [])) if isinstance(record.get("notes"), list) else 0,
        "latest_note": notes[-1] if notes else None,
        "notes": notes,
        "risk_count": len(risk_flags),
        "risk_flags": risk_flags,
        "watchlist_count": len(watchlist_items) if watchlist_items else int_value(entry.get("watchlist_count")),
        "portfolio_review": {
            "count": len(portfolio_items),
            "priority_counts": portfolio_counts,
            "high_review_count": portfolio_counts.get("high_review", 0),
            "medium_review_count": portfolio_counts.get("medium_review", 0),
            "normal_review_count": portfolio_counts.get("normal_review", 0),
            "top_items": [compact_portfolio_item(item) for item in top_portfolio_items],
        },
        "top_hotspot": compact_hotspot(top_hotspot),
        "validation": {
            "ok": validation.get("ok"),
            "warning_count": int_value(validation_summary.get("warning_count"), len(validation.get("warning_codes", []))),
            "error_count": int_value(validation_summary.get("error_count"), len(validation.get("error_codes", []))),
            "warning_codes": validation.get("warning_codes", []),
            "error_codes": validation.get("error_codes", []),
        },
        "commands": [
            "market-intel journal show %s --json" % entry_id,
            "market-intel journal show %s --text" % entry_id,
        ],
    }


def compact_journal_notes(value: object, limit: int = 3) -> List[Dict[str, object]]:
    notes = value if isinstance(value, list) else []
    compact = []
    for note in notes[-limit:]:
        if not isinstance(note, dict):
            continue
        compact.append(
            {
                "id": note.get("id"),
                "created_at": note.get("created_at"),
                "section": note.get("section"),
                "text": str(note.get("text") or "")[:240],
            }
        )
    return compact


def build_timeline_transition(base_record: Dict[str, object], current_record: Dict[str, object]) -> Dict[str, object]:
    base_entry = base_record.get("entry", {}) if isinstance(base_record.get("entry"), dict) else {}
    current_entry = current_record.get("entry", {}) if isinstance(current_record.get("entry"), dict) else {}
    base_payload = base_record.get("payload", {}) if isinstance(base_record.get("payload"), dict) else {}
    current_payload = current_record.get("payload", {}) if isinstance(current_record.get("payload"), dict) else {}
    changes = compare_daily_payloads(base_payload, current_payload)
    base_id = str(base_entry.get("id") or "")
    current_id = str(current_entry.get("id") or "")
    return {
        "base_entry_id": base_id,
        "current_entry_id": current_id,
        "base_trade_date": base_entry.get("trade_date"),
        "current_trade_date": current_entry.get("trade_date"),
        "summary": summarize_timeline_transition(base_entry, current_entry, changes),
        "risk_flags": compact_text_set_transition(changes.get("risk_flags", {})),
        "watchlist": compact_collection_transition(changes.get("watchlist", {})),
        "portfolio_review": compact_portfolio_transition(changes.get("portfolio_review", {})),
        "hotspots": compact_hotspot_transition(changes.get("hotspots", {})),
        "validation": compact_validation_transition(changes.get("validation", {})),
        "compare_command": "market-intel journal compare --base %s --current %s --json" % (base_id, current_id),
    }


def summarize_journal_timeline(points: List[Dict[str, object]], transitions: List[Dict[str, object]], total_count: int) -> str:
    if not points:
        return "还没有日报留档。先保存一份 daily 作为历史基线。"
    if len(points) == 1:
        point = points[0]
        return "已有 1 份日报留档：%s。还需要再保存一份才能观察转折。" % (
            point.get("trade_date") or point.get("entry_id")
        )

    latest = points[-1]
    portfolio = latest.get("portfolio_review", {}) if isinstance(latest.get("portfolio_review"), dict) else {}
    top_text = format_compact_hotspot(latest.get("top_hotspot"))
    summary = "最近 %s/%s 份留档：最新 %s；当前最强链路 %s；风险 %s 个，重点复核 %s 个。" % (
        len(points),
        total_count,
        latest.get("trade_date") or latest.get("entry_id"),
        top_text,
        latest.get("risk_count", 0),
        portfolio.get("high_review_count", 0),
    )
    if transitions:
        latest_transition = transitions[-1]
        risk_flags = latest_transition.get("risk_flags", {}) if isinstance(latest_transition.get("risk_flags"), dict) else {}
        watchlist = latest_transition.get("watchlist", {}) if isinstance(latest_transition.get("watchlist"), dict) else {}
        portfolio_review = (
            latest_transition.get("portfolio_review", {})
            if isinstance(latest_transition.get("portfolio_review"), dict)
            else {}
        )
        hotspots = latest_transition.get("hotspots", {}) if isinstance(latest_transition.get("hotspots"), dict) else {}
        summary += " 最近一次转折：风险 +%s/-%s；观察 +%s/-%s/~%s；持仓复核 +%s/-%s/~%s；热点 +%s/-%s/~%s。" % (
            risk_flags.get("added_count", 0),
            risk_flags.get("removed_count", 0),
            watchlist.get("added_count", 0),
            watchlist.get("removed_count", 0),
            watchlist.get("changed_count", 0),
            portfolio_review.get("added_count", 0),
            portfolio_review.get("removed_count", 0),
            portfolio_review.get("changed_count", 0),
            hotspots.get("added_count", 0),
            hotspots.get("removed_count", 0),
            hotspots.get("changed_count", 0),
        )
    return summary


def summarize_timeline_transition(
    base_entry: Dict[str, object],
    current_entry: Dict[str, object],
    changes: Dict[str, object],
) -> str:
    risk_flags = changes.get("risk_flags", {}) if isinstance(changes.get("risk_flags"), dict) else {}
    watchlist = changes.get("watchlist", {}) if isinstance(changes.get("watchlist"), dict) else {}
    portfolio_review = changes.get("portfolio_review", {}) if isinstance(changes.get("portfolio_review"), dict) else {}
    hotspots = changes.get("hotspots", {}) if isinstance(changes.get("hotspots"), dict) else {}
    return "%s -> %s：风险 +%s/-%s；观察 +%s/-%s/~%s；持仓复核 +%s/-%s/~%s；热点 +%s/-%s/~%s。" % (
        base_entry.get("trade_date") or base_entry.get("id"),
        current_entry.get("trade_date") or current_entry.get("id"),
        len(risk_flags.get("added", [])) if isinstance(risk_flags.get("added"), list) else 0,
        len(risk_flags.get("removed", [])) if isinstance(risk_flags.get("removed"), list) else 0,
        len(watchlist.get("added", [])) if isinstance(watchlist.get("added"), list) else 0,
        len(watchlist.get("removed", [])) if isinstance(watchlist.get("removed"), list) else 0,
        len(watchlist.get("changed", [])) if isinstance(watchlist.get("changed"), list) else 0,
        len(portfolio_review.get("added", [])) if isinstance(portfolio_review.get("added"), list) else 0,
        len(portfolio_review.get("removed", [])) if isinstance(portfolio_review.get("removed"), list) else 0,
        len(portfolio_review.get("changed", [])) if isinstance(portfolio_review.get("changed"), list) else 0,
        len(hotspots.get("added", [])) if isinstance(hotspots.get("added"), list) else 0,
        len(hotspots.get("removed", [])) if isinstance(hotspots.get("removed"), list) else 0,
        len(hotspots.get("changed", [])) if isinstance(hotspots.get("changed"), list) else 0,
    )


def compact_text_set_transition(value: object) -> Dict[str, object]:
    change = value if isinstance(value, dict) else {}
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    return {
        "base_count": int_value(change.get("base_count")),
        "current_count": int_value(change.get("current_count")),
        "added_count": len(added),
        "removed_count": len(removed),
        "added": added,
        "removed": removed,
    }


def compact_collection_transition(value: object) -> Dict[str, object]:
    change = value if isinstance(value, dict) else {}
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    changed = change.get("changed", []) if isinstance(change.get("changed"), list) else []
    return {
        "base_count": int_value(change.get("base_count")),
        "current_count": int_value(change.get("current_count")),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added_symbols": symbols_from_items(added),
        "removed_symbols": symbols_from_items(removed),
        "changed_symbols": symbols_from_changed(changed),
    }


def compact_portfolio_transition(value: object) -> Dict[str, object]:
    compact = compact_collection_transition(value)
    change = value if isinstance(value, dict) else {}
    priority = change.get("priority_counts", {}) if isinstance(change.get("priority_counts"), dict) else {}
    base_priority = priority.get("base", {}) if isinstance(priority.get("base"), dict) else {}
    current_priority = priority.get("current", {}) if isinstance(priority.get("current"), dict) else {}
    base_high = int_value(base_priority.get("high_review"))
    current_high = int_value(current_priority.get("high_review"))
    compact["priority_counts"] = {"base": base_priority, "current": current_priority}
    compact["high_review_delta"] = current_high - base_high
    return compact


def compact_hotspot_transition(value: object) -> Dict[str, object]:
    change = value if isinstance(value, dict) else {}
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    changed = change.get("changed", []) if isinstance(change.get("changed"), list) else []
    top = change.get("top", {}) if isinstance(change.get("top"), dict) else {}
    return {
        "base_count": int_value(change.get("base_count")),
        "current_count": int_value(change.get("current_count")),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added_keys": hotspot_keys_from_items(added),
        "removed_keys": hotspot_keys_from_items(removed),
        "changed_keys": hotspot_keys_from_changed(changed),
        "top": {
            "base": compact_hotspot(top.get("base")),
            "current": compact_hotspot(top.get("current")),
        },
    }


def compact_validation_transition(value: object) -> Dict[str, object]:
    validation = value if isinstance(value, dict) else {}
    base = validation.get("base", {}) if isinstance(validation.get("base"), dict) else {}
    current = validation.get("current", {}) if isinstance(validation.get("current"), dict) else {}
    base_summary = base.get("summary", {}) if isinstance(base.get("summary"), dict) else {}
    current_summary = current.get("summary", {}) if isinstance(current.get("summary"), dict) else {}
    base_warning_count = int_value(base_summary.get("warning_count"), len(base.get("warning_codes", [])))
    current_warning_count = int_value(current_summary.get("warning_count"), len(current.get("warning_codes", [])))
    base_error_count = int_value(base_summary.get("error_count"), len(base.get("error_codes", [])))
    current_error_count = int_value(current_summary.get("error_count"), len(current.get("error_codes", [])))
    return {
        "base_ok": base.get("ok"),
        "current_ok": current.get("ok"),
        "base_warning_count": base_warning_count,
        "current_warning_count": current_warning_count,
        "warning_delta": current_warning_count - base_warning_count,
        "base_error_count": base_error_count,
        "current_error_count": current_error_count,
        "error_delta": current_error_count - base_error_count,
    }


def compact_portfolio_item(item: Dict[str, object]) -> Dict[str, object]:
    risk_flags = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
    return {
        "symbol": item.get("symbol"),
        "name": item.get("name"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "risk_count": len(risk_flags),
        "risk_flags": risk_flags,
        "hotspot_key": item.get("hotspot_key"),
        "change_pct": item.get("change_pct"),
    }


def compact_hotspot(item: object) -> Optional[Dict[str, object]]:
    if not isinstance(item, dict):
        return None
    return {
        "key": item.get("key") or hotspot_key(item),
        "rank": item.get("rank"),
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "score": item.get("score"),
        "active_member_count": item.get("active_member_count"),
        "member_count": item.get("member_count"),
    }


def format_compact_hotspot(value: object) -> str:
    hotspot = value if isinstance(value, dict) else {}
    if not hotspot:
        return "暂无热点"
    return "%s / %s（热点 %s）" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score"))


def symbols_from_items(items: List[object]) -> List[str]:
    symbols = []
    for item in items:
        if isinstance(item, dict) and item.get("symbol"):
            symbols.append(str(item.get("symbol")))
    return symbols


def symbols_from_changed(items: List[object]) -> List[str]:
    symbols = []
    for item in items:
        if isinstance(item, dict) and item.get("symbol"):
            symbols.append(str(item.get("symbol")))
    return symbols


def hotspot_keys_from_items(items: List[object]) -> List[str]:
    keys = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or hotspot_key(item)
        if key:
            keys.append(str(key))
    return keys


def hotspot_keys_from_changed(items: List[object]) -> List[str]:
    keys = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        current = item.get("current", {}) if isinstance(item.get("current"), dict) else {}
        key = key or current.get("key") or hotspot_key(current)
        if key:
            keys.append(str(key))
    return keys


def timeline_next_commands(points: List[Dict[str, object]], limit: int) -> List[str]:
    if not points:
        return [
            "market-intel daily --runtime --json",
            "market-intel journal save --runtime --json",
        ]
    if len(points) == 1:
        return [
            "market-intel journal save --runtime --json",
            "market-intel journal latest --text",
            "market-intel journal timeline --limit %s --json" % limit,
        ]
    base_id = str(points[-2].get("entry_id") or "")
    current_id = str(points[-1].get("entry_id") or "")
    return [
        "market-intel journal compare --base %s --current %s --json" % (base_id, current_id),
        "market-intel journal show %s --text" % current_id,
        "market-intel journal timeline --limit %s --json" % limit,
    ]


def journal_timeline_contract() -> Dict[str, object]:
    return {
        "success": "ok=true；data.found=false 只表示还没有日报留档",
        "order": "data.points 与 data.transitions 均按时间从旧到新排列",
        "stable_fields": [
            "data.found",
            "data.can_compare",
            "data.points[].entry_id",
            "data.points[].trade_date",
            "data.points[].risk_count",
            "data.points[].watchlist_count",
            "data.points[].portfolio_review",
            "data.points[].top_hotspot",
            "data.points[].latest_note",
            "data.transitions[].risk_flags",
            "data.transitions[].watchlist",
            "data.transitions[].portfolio_review",
            "data.transitions[].hotspots",
            "data.transitions[].validation",
            "data.next_commands",
        ],
        "missing_history": "data.count=0 表示需要先运行 journal save；data.count=1 表示还不能形成转折。",
    }


def timeline_record_sort_key(record: Dict[str, object]) -> object:
    entry = record.get("entry", {}) if isinstance(record.get("entry"), dict) else {}
    return _parse_timestamp(entry.get("generated_at"))


def compare_daily_payloads(base_payload: Dict[str, object], current_payload: Dict[str, object]) -> Dict[str, object]:
    base_data = daily_data(base_payload)
    current_data = daily_data(current_payload)
    return {
        "trade_date": {
            "base": base_data.get("latest_trade_date"),
            "current": current_data.get("latest_trade_date"),
        },
        "daily_summary": {
            "base": base_data.get("summary"),
            "current": current_data.get("summary"),
        },
        "risk_flags": compare_text_sets(base_data.get("risk_flags", []), current_data.get("risk_flags", [])),
        "watchlist": compare_watchlists(base_data, current_data),
        "portfolio_review": compare_portfolio_reviews(base_data, current_data),
        "hotspots": compare_hotspots(base_data, current_data),
        "validation": compare_validation(base_data, current_data),
    }


def compare_watchlists(base_data: Dict[str, object], current_data: Dict[str, object]) -> Dict[str, object]:
    base_items = index_watchlist_items(base_data)
    current_items = index_watchlist_items(current_data)
    base_symbols = set(base_items)
    current_symbols = set(current_items)
    added_symbols = sorted(current_symbols - base_symbols)
    removed_symbols = sorted(base_symbols - current_symbols)
    changed = []
    unchanged_symbols = []

    for symbol in sorted(base_symbols & current_symbols):
        item_changes = compare_watchlist_item(base_items[symbol], current_items[symbol])
        if item_changes:
            changed.append(
                {
                    "symbol": symbol,
                    "name": current_items[symbol].get("name") or base_items[symbol].get("name"),
                    "changes": item_changes,
                    "base": base_items[symbol],
                    "current": current_items[symbol],
                }
            )
        else:
            unchanged_symbols.append(symbol)

    return {
        "base_count": len(base_items),
        "current_count": len(current_items),
        "added": [current_items[symbol] for symbol in added_symbols],
        "removed": [base_items[symbol] for symbol in removed_symbols],
        "changed": changed,
        "unchanged_symbols": unchanged_symbols,
    }


def compare_hotspots(base_data: Dict[str, object], current_data: Dict[str, object]) -> Dict[str, object]:
    base_items = index_hotspots(base_data)
    current_items = index_hotspots(current_data)
    base_keys = set(base_items)
    current_keys = set(current_items)
    added_keys = sorted(current_keys - base_keys)
    removed_keys = sorted(base_keys - current_keys)
    changed = []
    unchanged_keys = []

    for key in sorted(base_keys & current_keys):
        item_changes = compare_hotspot_item(base_items[key], current_items[key])
        if item_changes:
            changed.append(
                {
                    "key": key,
                    "changes": item_changes,
                    "base": base_items[key],
                    "current": current_items[key],
                }
            )
        else:
            unchanged_keys.append(key)

    return {
        "base_count": len(base_items),
        "current_count": len(current_items),
        "top": {
            "base": first_or_none(sorted(base_items.values(), key=lambda item: int_value(item.get("rank"), 9999))),
            "current": first_or_none(sorted(current_items.values(), key=lambda item: int_value(item.get("rank"), 9999))),
        },
        "added": [current_items[key] for key in added_keys],
        "removed": [base_items[key] for key in removed_keys],
        "changed": changed,
        "unchanged_keys": unchanged_keys,
    }


def compare_portfolio_reviews(base_data: Dict[str, object], current_data: Dict[str, object]) -> Dict[str, object]:
    base_items = index_portfolio_items(base_data)
    current_items = index_portfolio_items(current_data)
    base_symbols = set(base_items)
    current_symbols = set(current_items)
    added_symbols = sorted(current_symbols - base_symbols)
    removed_symbols = sorted(base_symbols - current_symbols)
    changed = []
    unchanged_symbols = []

    for symbol in sorted(base_symbols & current_symbols):
        item_changes = compare_portfolio_item(base_items[symbol], current_items[symbol])
        if item_changes:
            changed.append(
                {
                    "symbol": symbol,
                    "name": current_items[symbol].get("name") or base_items[symbol].get("name"),
                    "changes": item_changes,
                    "base": base_items[symbol],
                    "current": current_items[symbol],
                }
            )
        else:
            unchanged_symbols.append(symbol)

    return {
        "base_count": len(base_items),
        "current_count": len(current_items),
        "added": [current_items[symbol] for symbol in added_symbols],
        "removed": [base_items[symbol] for symbol in removed_symbols],
        "changed": changed,
        "unchanged_symbols": unchanged_symbols,
        "priority_counts": {
            "base": priority_counts(base_items),
            "current": priority_counts(current_items),
        },
    }


def compare_validation(base_data: Dict[str, object], current_data: Dict[str, object]) -> Dict[str, object]:
    base_validation = validation_digest(base_data)
    current_validation = validation_digest(current_data)
    return {
        "base": base_validation,
        "current": current_validation,
        "summary_delta": compare_summary_values(
            base_validation.get("summary", {}),
            current_validation.get("summary", {}),
        ),
        "warning_codes": compare_text_sets(
            base_validation.get("warning_codes", []),
            current_validation.get("warning_codes", []),
        ),
        "error_codes": compare_text_sets(
            base_validation.get("error_codes", []),
            current_validation.get("error_codes", []),
        ),
    }


def index_portfolio_items(data: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    portfolio = data.get("portfolio_review", {}) if isinstance(data.get("portfolio_review"), dict) else {}
    items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    indexed: Dict[str, Dict[str, object]] = {}
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        normalized = normalize_portfolio_item(item, rank)
        symbol = normalized.get("symbol")
        if symbol:
            indexed[str(symbol)] = normalized
    return indexed


def normalize_portfolio_item(item: Dict[str, object], rank: int) -> Dict[str, object]:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    return {
        "rank": rank,
        "symbol": text_or_none(item.get("symbol")),
        "name": text_or_none(item.get("name")),
        "priority": text_or_none(item.get("priority")),
        "priority_score": numeric_or_none(item.get("priority_score")),
        "has_quote": bool(item.get("has_quote")),
        "matched_pool_item": bool(item.get("matched_pool_item")),
        "change_pct": numeric_or_none(quote.get("change_pct")),
        "amount_ratio": numeric_or_none(quote.get("amount_ratio")),
        "intraday_fade_pct": numeric_or_none(quote.get("intraday_fade_pct")),
        "hotspot_key": hotspot_key(hotspot),
        "hotspot_score": numeric_or_none(hotspot.get("score")),
        "exposure_keys": sorted(exposure_keys(item.get("exposures", []))),
        "overlap_groups": unique_text_list(item.get("overlap_groups", [])),
        "risk_flags": unique_text_list(item.get("risk_flags", [])),
        "review_points": unique_text_list(item.get("review_points", [])),
    }


def compare_portfolio_item(base_item: Dict[str, object], current_item: Dict[str, object]) -> Dict[str, object]:
    changes: Dict[str, object] = {}
    for field in ["rank", "name", "priority", "has_quote", "matched_pool_item", "hotspot_key"]:
        if base_item.get(field) != current_item.get(field):
            changes[field] = {"base": base_item.get(field), "current": current_item.get(field)}
    for field in ["priority_score", "change_pct", "amount_ratio", "intraday_fade_pct", "hotspot_score"]:
        numeric_change = compare_numeric_value(base_item.get(field), current_item.get(field))
        if numeric_change:
            changes[field] = numeric_change
    for field in ["exposure_keys", "overlap_groups", "risk_flags", "review_points"]:
        list_change = compare_text_sets(base_item.get(field, []), current_item.get(field, []))
        if list_change["added"] or list_change["removed"]:
            changes[field] = list_change
    return changes


def priority_counts(items: Dict[str, Dict[str, object]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items.values():
        priority = str(item.get("priority") or "unknown")
        counts[priority] = counts.get(priority, 0) + 1
    return counts


def hotspot_key(value: object) -> Optional[str]:
    hotspot = value if isinstance(value, dict) else {}
    if not hotspot:
        return None
    return "%s/%s" % (hotspot.get("layer") or "", hotspot.get("sub_sector") or "")


def exposure_keys(value: object) -> List[str]:
    exposures = value if isinstance(value, list) else []
    keys = []
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        key = "%s/%s" % (exposure.get("layer") or "", exposure.get("sub_sector") or "")
        if key not in keys:
            keys.append(key)
    return keys


def index_watchlist_items(data: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    watchlist = data.get("watchlist", {}) if isinstance(data.get("watchlist"), dict) else {}
    items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []
    indexed: Dict[str, Dict[str, object]] = {}
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        normalized = normalize_watchlist_item(item, rank)
        symbol = normalized.get("symbol")
        if symbol:
            indexed[str(symbol)] = normalized
    return indexed


def normalize_watchlist_item(item: Dict[str, object], rank: int) -> Dict[str, object]:
    return {
        "rank": rank,
        "symbol": text_or_none(item.get("symbol")),
        "name": text_or_none(item.get("name")),
        "is_holding": bool(item.get("is_holding")),
        "layer": text_or_none(item.get("layer")),
        "sub_sector": text_or_none(item.get("sub_sector")),
        "focus": text_or_none(item.get("focus") or item.get("reason")),
        "change_pct": numeric_or_none(item.get("change_pct")),
        "hotspot_score": numeric_or_none(item.get("hotspot_score")),
        "amount_ratio": numeric_or_none(item.get("amount_ratio")),
        "intraday_fade_pct": numeric_or_none(item.get("intraday_fade_pct")),
        "signals": unique_text_list(item.get("signals", [])),
        "risks": unique_text_list(item.get("risks", [])),
    }


def compare_watchlist_item(base_item: Dict[str, object], current_item: Dict[str, object]) -> Dict[str, object]:
    changes: Dict[str, object] = {}
    for field in ["rank", "name", "is_holding", "layer", "sub_sector", "focus"]:
        if base_item.get(field) != current_item.get(field):
            changes[field] = {"base": base_item.get(field), "current": current_item.get(field)}
    for field in ["change_pct", "hotspot_score", "amount_ratio", "intraday_fade_pct"]:
        numeric_change = compare_numeric_value(base_item.get(field), current_item.get(field))
        if numeric_change:
            changes[field] = numeric_change
    for field in ["signals", "risks"]:
        list_change = compare_text_sets(base_item.get(field, []), current_item.get(field, []))
        if list_change["added"] or list_change["removed"]:
            changes[field] = list_change
    return changes


def index_hotspots(data: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
    hotspots = brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []
    indexed: Dict[str, Dict[str, object]] = {}
    for rank, hotspot in enumerate(hotspots, start=1):
        if not isinstance(hotspot, dict):
            continue
        normalized = normalize_hotspot(hotspot, rank)
        key = normalized.get("key")
        if key:
            indexed[str(key)] = normalized
    return indexed


def normalize_hotspot(hotspot: Dict[str, object], rank: int) -> Dict[str, object]:
    layer = text_or_none(hotspot.get("layer"))
    sub_sector = text_or_none(hotspot.get("sub_sector"))
    leaders = hotspot.get("leaders", []) if isinstance(hotspot.get("leaders"), list) else []
    normalized_leaders = []
    for leader in leaders[:5]:
        if not isinstance(leader, dict):
            continue
        normalized_leaders.append(
            {
                "symbol": text_or_none(leader.get("symbol")),
                "name": text_or_none(leader.get("name")),
                "change_pct": numeric_or_none(leader.get("change_pct")),
            }
        )
    return {
        "key": "%s/%s" % (layer or "", sub_sector or ""),
        "rank": rank,
        "layer": layer,
        "sub_sector": sub_sector,
        "score": numeric_or_none(hotspot.get("score")),
        "active_member_count": int_or_none(hotspot.get("active_member_count")),
        "member_count": int_or_none(hotspot.get("member_count")),
        "leaders": normalized_leaders,
        "leader_keys": [leader.get("symbol") or leader.get("name") for leader in normalized_leaders],
        "signals": unique_text_list(hotspot.get("signals", [])),
        "risks": unique_text_list(hotspot.get("risks", [])),
    }


def compare_hotspot_item(base_item: Dict[str, object], current_item: Dict[str, object]) -> Dict[str, object]:
    changes: Dict[str, object] = {}
    for field in ["rank", "active_member_count", "member_count"]:
        if base_item.get(field) != current_item.get(field):
            changes[field] = {"base": base_item.get(field), "current": current_item.get(field)}
    score_change = compare_numeric_value(base_item.get("score"), current_item.get("score"))
    if score_change:
        changes["score"] = score_change
    leader_change = compare_text_sets(base_item.get("leader_keys", []), current_item.get("leader_keys", []))
    if leader_change["added"] or leader_change["removed"]:
        changes["leaders"] = leader_change
    for field in ["signals", "risks"]:
        list_change = compare_text_sets(base_item.get(field, []), current_item.get(field, []))
        if list_change["added"] or list_change["removed"]:
            changes[field] = list_change
    return changes


def validation_digest(data: Dict[str, object]) -> Dict[str, object]:
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    return {
        "ok": validation.get("ok"),
        "summary": summary,
        "warning_codes": issue_identifiers(validation.get("warnings", [])),
        "error_codes": issue_identifiers(validation.get("errors", [])),
    }


def issue_identifiers(value: object) -> List[str]:
    issues = value if isinstance(value, list) else []
    identifiers = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code") or "")
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        symbol = detail.get("symbol")
        identifiers.append("%s:%s" % (code, symbol) if symbol else code)
    return sorted(set(identifier for identifier in identifiers if identifier))


def compare_summary_values(base_summary: object, current_summary: object) -> Dict[str, object]:
    base = base_summary if isinstance(base_summary, dict) else {}
    current = current_summary if isinstance(current_summary, dict) else {}
    changes: Dict[str, object] = {}
    for key in sorted(set(base) | set(current)):
        if base.get(key) == current.get(key):
            continue
        numeric_change = compare_numeric_value(base.get(key), current.get(key))
        changes[str(key)] = numeric_change or {"base": base.get(key), "current": current.get(key)}
    return changes


def compare_text_sets(base_values: object, current_values: object) -> Dict[str, object]:
    base_set = set(unique_text_list(base_values))
    current_set = set(unique_text_list(current_values))
    return {
        "base_count": len(base_set),
        "current_count": len(current_set),
        "added": sorted(current_set - base_set),
        "removed": sorted(base_set - current_set),
        "unchanged": sorted(base_set & current_set),
    }


def compare_numeric_value(base_value: object, current_value: object) -> Optional[Dict[str, object]]:
    base_number = numeric_or_none(base_value)
    current_number = numeric_or_none(current_value)
    if base_number is None and current_number is None:
        return None
    if base_number is not None and current_number is not None:
        delta = round(current_number - base_number, 4)
        if abs(delta) < 0.0001:
            return None
        return {"base": base_number, "current": current_number, "delta": delta}
    if base_number == current_number:
        return None
    return {"base": base_number, "current": current_number, "delta": None}


def summarize_journal_compare(
    base_entry: Dict[str, object],
    current_entry: Dict[str, object],
    changes: Dict[str, object],
) -> str:
    risk_flags = changes.get("risk_flags", {}) if isinstance(changes.get("risk_flags"), dict) else {}
    watchlist = changes.get("watchlist", {}) if isinstance(changes.get("watchlist"), dict) else {}
    portfolio_review = changes.get("portfolio_review", {}) if isinstance(changes.get("portfolio_review"), dict) else {}
    hotspots = changes.get("hotspots", {}) if isinstance(changes.get("hotspots"), dict) else {}
    top = hotspots.get("top", {}) if isinstance(hotspots.get("top"), dict) else {}
    current_top = top.get("current", {}) if isinstance(top.get("current"), dict) else {}
    summary = (
        "对比 %s 到 %s：风险新增 %s 个、减少 %s 个；观察项新增 %s 个、减少 %s 个、变化 %s 个；"
        "持仓复核新增 %s 个、减少 %s 个、变化 %s 个；热点新增 %s 个、减少 %s 个、变化 %s 个。"
        % (
            base_entry.get("trade_date") or base_entry.get("id"),
            current_entry.get("trade_date") or current_entry.get("id"),
            len(risk_flags.get("added", [])) if isinstance(risk_flags.get("added"), list) else 0,
            len(risk_flags.get("removed", [])) if isinstance(risk_flags.get("removed"), list) else 0,
            len(watchlist.get("added", [])) if isinstance(watchlist.get("added"), list) else 0,
            len(watchlist.get("removed", [])) if isinstance(watchlist.get("removed"), list) else 0,
            len(watchlist.get("changed", [])) if isinstance(watchlist.get("changed"), list) else 0,
            len(portfolio_review.get("added", [])) if isinstance(portfolio_review.get("added"), list) else 0,
            len(portfolio_review.get("removed", [])) if isinstance(portfolio_review.get("removed"), list) else 0,
            len(portfolio_review.get("changed", [])) if isinstance(portfolio_review.get("changed"), list) else 0,
            len(hotspots.get("added", [])) if isinstance(hotspots.get("added"), list) else 0,
            len(hotspots.get("removed", [])) if isinstance(hotspots.get("removed"), list) else 0,
            len(hotspots.get("changed", [])) if isinstance(hotspots.get("changed"), list) else 0,
        )
    )
    if current_top:
        summary += " 当前最强链路是 %s / %s，热点 %s。" % (
            current_top.get("layer"),
            current_top.get("sub_sector"),
            current_top.get("score"),
        )
    return summary


def empty_compare_result(
    mode: str,
    requested: Dict[str, object],
    errors: List[Dict[str, object]],
    warnings: List[Dict[str, object]],
) -> Dict[str, object]:
    return {
        "found": False,
        "mode": mode,
        "journal_dir": display_path(journal_dir_path()),
        "requested": requested,
        "base_entry": None,
        "current_entry": None,
        "summary": "至少需要两份日报留档才能对比。",
        "changes": empty_changes(),
        "agent_contract": journal_compare_contract(),
        "next_commands": [
            "market-intel journal save --runtime --json",
            "market-intel journal list --json",
        ],
        "errors": errors,
        "warnings": warnings,
    }


def _empty_text_set() -> Dict[str, object]:
    return {"base_count": 0, "current_count": 0, "added": [], "removed": [], "unchanged": []}


def empty_changes() -> Dict[str, object]:
    return {
        "trade_date": {"base": None, "current": None},
        "daily_summary": {"base": None, "current": None},
        "risk_flags": _empty_text_set(),
        "watchlist": {
            "base_count": 0,
            "current_count": 0,
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged_symbols": [],
        },
        "portfolio_review": {
            "base_count": 0,
            "current_count": 0,
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged_symbols": [],
            "priority_counts": {"base": {}, "current": {}},
        },
        "hotspots": {
            "base_count": 0,
            "current_count": 0,
            "top": {"base": None, "current": None},
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged_keys": [],
        },
        "validation": {
            "base": {"ok": None, "summary": {}, "warning_codes": [], "error_codes": []},
            "current": {"ok": None, "summary": {}, "warning_codes": [], "error_codes": []},
            "summary_delta": {},
            "warning_codes": _empty_text_set(),
            "error_codes": _empty_text_set(),
        },
    }


def journal_compare_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 data.found=true",
        "default_mode": "未传 id 时对比最近两份日报留档",
        "stable_fields": [
            "data.base_entry",
            "data.current_entry",
            "data.changes.risk_flags",
            "data.changes.watchlist",
            "data.changes.portfolio_review",
            "data.changes.hotspots",
            "data.changes.validation",
            "data.next_commands",
        ],
        "missing_history": "JOURNAL_COMPARE_REQUIRES_TWO_ENTRIES 表示需要再保存日报留档。",
    }


def compare_next_commands(base_id: str, current_id: str) -> List[str]:
    return [
        "market-intel journal compare --base %s --current %s --json" % (base_id, current_id),
        "market-intel journal show %s --text" % current_id,
        "market-intel journal show %s --json" % base_id,
        "market-intel journal list --json",
    ]


def daily_data(payload: Dict[str, object]) -> Dict[str, object]:
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    return data


def scoped_errors(errors: object, side: str) -> List[Dict[str, object]]:
    scoped = []
    for item in errors if isinstance(errors, list) else []:
        if not isinstance(item, dict):
            continue
        detail = item.get("detail", {}) if isinstance(item.get("detail"), dict) else {}
        scoped.append({**item, "detail": {**detail, "side": side}})
    return scoped


def journal_issue(code: str, message: str, detail: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    return {"code": code, "message": message, "detail": detail or {}}


def text_or_none(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def numeric_or_none(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip().replace("%", "")
        if not text:
            return None
        return float(text)
    except ValueError:
        return None


def int_or_none(value: object) -> Optional[int]:
    number = numeric_or_none(value)
    return int(number) if number is not None else None


def int_value(value: object, default: int = 0) -> int:
    number = int_or_none(value)
    return number if number is not None else default


def unique_text_list(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    texts = []
    for item in items:
        if item is None:
            continue
        text = str(item)
        if text and text not in texts:
            texts.append(text)
    return texts


def first_or_none(values: List[Any]) -> Optional[Any]:
    return values[0] if values else None


def read_journal_record(path: Path) -> Dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        record = json.load(handle)
    if not isinstance(record, dict) or not isinstance(record.get("entry"), dict) or not isinstance(record.get("payload"), dict):
        raise ValueError("Invalid journal record shape.")
    return record


def display_path(path: Path) -> str:
    if path.is_absolute() and path.parent.name:
        return "%s/%s" % (path.parent.name, path.name)
    return str(path)


def infer_trade_date(data: Dict[str, object]) -> Optional[str]:
    if data.get("latest_trade_date"):
        return str(data.get("latest_trade_date"))
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    freshness = data.get("freshness", {}) if isinstance(data.get("freshness"), dict) else {}
    if freshness.get("latest_trade_date"):
        return str(freshness.get("latest_trade_date"))
    brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
    hotspots = brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []
    for hotspot in hotspots:
        if not isinstance(hotspot, dict):
            continue
        for leader in hotspot.get("leaders", []) if isinstance(hotspot.get("leaders"), list) else []:
            if isinstance(leader, dict) and leader.get("trade_date"):
                return str(leader.get("trade_date"))
    files = validation.get("files", {}) if isinstance(validation.get("files"), dict) else {}
    quotes_path = files.get("quotes")
    if quotes_path:
        return None
    return None


def next_commands_for_entries(entries: List[Dict[str, object]]) -> List[str]:
    if not entries:
        return ["market-intel daily --runtime --json", "market-intel journal save --runtime --json"]
    return ["market-intel journal latest --text", "market-intel journal show %s --json" % entries[0]["id"]]


def _parse_timestamp(value: object) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return datetime.min


def safe_id(value: str) -> str:
    return SAFE_ID_RE.sub("_", value.replace(":", "").replace("+", "_")).strip("_")[:120]
