from typing import Dict, List, Optional


def build_agent_plan(
    pool: str,
    runtime_status: Dict[str, object],
    journal_list: Dict[str, object],
    max_quote_age_days: int,
) -> Dict[str, object]:
    readiness = runtime_status.get("readiness", {}) if isinstance(runtime_status.get("readiness"), dict) else {}
    freshness = runtime_status.get("freshness", {}) if isinstance(runtime_status.get("freshness"), dict) else {}
    universe = runtime_status.get("universe", {}) if isinstance(runtime_status.get("universe"), dict) else {}
    validation = runtime_status.get("validation", {}) if isinstance(runtime_status.get("validation"), dict) else {}
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    files = runtime_status.get("files", {}) if isinstance(runtime_status.get("files"), dict) else {}
    entries = journal_list.get("entries", []) if isinstance(journal_list.get("entries"), list) else []
    journal_errors = journal_list.get("errors", []) if isinstance(journal_list.get("errors"), list) else []
    state = agent_state(readiness, entries)
    steps = build_steps(readiness, freshness, universe, entries)

    return {
        "pool": pool,
        "state": state,
        "summary": agent_summary(state, readiness, entries),
        "runtime": {
            "readiness": readiness,
            "freshness": freshness,
            "universe": universe,
            "validation": compact_validation_summary(validation, validation_summary),
            "validation_summary": validation_summary,
            "files": files,
        },
        "journal": {
            "journal_dir": journal_list.get("journal_dir"),
            "entry_count": journal_list.get("total_count", len(entries)),
            "latest_entry": entries[0] if entries else None,
            "can_compare": len(entries) >= 2,
            "compare_pair": compare_pair(entries),
            "errors": journal_errors,
        },
        "execution": execution_summary(steps),
        "steps": steps,
        "agent_contract": agent_contract(max_quote_age_days),
    }


def build_agent_briefing(
    pool: str,
    runtime_status: Dict[str, object],
    scan_payload: Optional[Dict[str, object]],
    daily_payload: Optional[Dict[str, object]],
    journal_timeline: Dict[str, object],
    journal_compare: Optional[Dict[str, object]],
    current_compare: Optional[Dict[str, object]],
    max_quote_age_days: int,
) -> Dict[str, object]:
    readiness = runtime_status.get("readiness", {}) if isinstance(runtime_status.get("readiness"), dict) else {}
    freshness = runtime_status.get("freshness", {}) if isinstance(runtime_status.get("freshness"), dict) else {}
    universe = runtime_status.get("universe", {}) if isinstance(runtime_status.get("universe"), dict) else {}
    validation = runtime_status.get("validation", {}) if isinstance(runtime_status.get("validation"), dict) else {}
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    market_scan = compact_market_scan(scan_payload)
    daily = compact_daily_payload(daily_payload)
    history = compact_history(journal_timeline, journal_compare)
    current_change = compact_current_change(current_compare)
    security_queue = build_security_review_queue(daily, current_change, market_scan)
    focus = build_review_focus(readiness, daily, history, current_change, market_scan)
    checklist = build_review_checklist(readiness, daily, history, focus, current_change, market_scan)
    state = briefing_state(readiness, daily, history)
    next_commands = briefing_next_commands(readiness, daily, history, current_change, market_scan)

    return {
        "pool": pool,
        "state": state,
        "summary": briefing_summary(state, readiness, daily, history, focus, market_scan),
        "runtime": {
            "readiness": readiness,
            "freshness": freshness,
            "universe": universe,
            "validation": compact_validation_summary(validation, validation_summary),
            "validation_summary": validation_summary,
        },
        "market_scan": market_scan,
        "daily": daily,
        "history": history,
        "current_change": current_change,
        "security_review_queue": security_queue,
        "review_focus": focus,
        "review_checklist": checklist,
        "questions": briefing_questions(daily, history, focus, current_change, market_scan),
        "journal_prompt": build_journal_prompt(daily, history, current_change, security_queue),
        "command_queue": build_command_queue(next_commands, focus, checklist),
        "next_commands": next_commands,
        "agent_contract": agent_briefing_contract(max_quote_age_days),
    }


def compact_daily_payload(payload: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(payload, dict) or not payload.get("ok"):
        return {
            "available": False,
            "trade_date": None,
            "summary": "runtime 暂不可生成日报。",
            "top_hotspots": [],
            "watchlist": {"count": 0, "top_items": []},
            "portfolio_review": {"count": 0, "high_review_count": 0, "top_items": []},
            "risk_flags": [],
            "coverage_context": {"available": False},
            "risk_register": [],
            "review_path": [],
            "validation": empty_validation_summary(),
            "next_questions": [],
            "review_tasks": [],
            "security_review_queue": [],
            "security_risk_profile": [],
            "journal_actions": [],
            "command_queue": [],
            "errors": payload.get("errors", []) if isinstance(payload, dict) else [],
        }

    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
    watchlist = data.get("watchlist", {}) if isinstance(data.get("watchlist"), dict) else {}
    portfolio = data.get("portfolio_review", {}) if isinstance(data.get("portfolio_review"), dict) else {}
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    coverage = data.get("coverage_context", {}) if isinstance(data.get("coverage_context"), dict) else {}
    portfolio_items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    watchlist_items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []

    return {
        "available": True,
        "trade_date": data.get("latest_trade_date"),
        "summary": data.get("summary"),
        "top_hotspots": [
            compact_hotspot(item, rank)
            for rank, item in enumerate(brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else [], start=1)
            if isinstance(item, dict)
        ][:3],
        "watchlist": {
            "count": watchlist.get("count", len(watchlist_items)),
            "top_items": [compact_watchlist_item(item) for item in watchlist_items[:5] if isinstance(item, dict)],
        },
        "portfolio_review": {
            "count": portfolio.get("review_count", len(portfolio_items)),
            "high_review_count": sum(1 for item in portfolio_items if isinstance(item, dict) and item.get("priority") == "high_review"),
            "top_items": [compact_portfolio_item(item) for item in portfolio_items[:5] if isinstance(item, dict)],
            "repeated_exposures": compact_group_counts(portfolio.get("repeated_exposures", [])),
            "repeated_overlap_groups": compact_group_counts(portfolio.get("repeated_overlap_groups", [])),
        },
        "portfolio_exposure": compact_portfolio_exposure(portfolio, portfolio_items),
        "risk_flags": list(data.get("risk_flags", [])) if isinstance(data.get("risk_flags"), list) else [],
        "coverage_context": compact_coverage_context(coverage),
        "risk_register": compact_risk_register(data.get("risk_register", [])),
        "review_path": compact_review_path(data.get("review_path", [])),
        "validation": compact_validation_summary(validation, validation_summary),
        "next_questions": list(data.get("next_questions", [])) if isinstance(data.get("next_questions"), list) else [],
        "review_tasks": compact_daily_review_tasks(data.get("review_tasks", [])),
        "security_review_queue": compact_daily_security_queue(data.get("security_review_queue", [])),
        "security_risk_profile": compact_security_risk_profile(data.get("security_risk_profile", [])),
        "journal_actions": compact_daily_journal_actions(data.get("journal_actions", [])),
        "command_queue": compact_command_queue(data.get("command_queue", [])),
        "errors": [],
    }


def compact_market_scan(payload: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(payload, dict) or not payload.get("ok"):
        return {
            "available": False,
            "summary": "runtime 暂不可生成全市场扫描。",
            "scan_mode": None,
            "sector_groups": [],
            "candidate_securities": [],
            "errors": payload.get("errors", []) if isinstance(payload, dict) else [],
        }
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    groups = data.get("sector_groups", []) if isinstance(data.get("sector_groups"), list) else []
    candidates = data.get("candidate_securities", []) if isinstance(data.get("candidate_securities"), list) else []
    return {
        "available": True,
        "summary": data.get("summary"),
        "scan_mode": data.get("scan_mode"),
        "market_breadth": compact_market_breadth(data.get("market_breadth", {})),
        "quote_count": data.get("quote_count", 0),
        "matched_quote_count": data.get("matched_quote_count", 0),
        "unmatched_quote_count": data.get("unmatched_quote_count", 0),
        "sector_groups": [compact_scan_group(item) for item in groups[:5] if isinstance(item, dict)],
        "candidate_securities": [compact_scan_candidate(item) for item in candidates[:8] if isinstance(item, dict)],
        "candidate_queue": compact_candidate_queue(data.get("candidate_queue", {})),
        "questions": list(data.get("questions", []))[:5] if isinstance(data.get("questions"), list) else [],
        "next_actions": [
            {
                "id": item.get("id"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
            }
            for item in (data.get("next_actions", []) if isinstance(data.get("next_actions"), list) else [])[:5]
            if isinstance(item, dict)
        ],
        "errors": [],
    }


def compact_candidate_queue(value: object) -> Dict[str, object]:
    queue = value if isinstance(value, dict) else {}
    if not queue:
        return {}
    buckets = queue.get("buckets", {}) if isinstance(queue.get("buckets"), dict) else {}
    return {
        "summary": queue.get("summary"),
        "buckets": {
            "review_now": compact_candidate_queue_bucket(buckets.get("review_now", {})),
            "deprioritized": compact_candidate_queue_bucket(buckets.get("deprioritized", {})),
            "data_first": compact_candidate_queue_bucket(buckets.get("data_first", {})),
        },
    }


def compact_candidate_queue_bucket(value: object) -> Dict[str, object]:
    bucket = value if isinstance(value, dict) else {}
    return {
        "label": bucket.get("label"),
        "summary": bucket.get("summary"),
        "count": bucket.get("count", 0),
        "items": [
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "review_score": item.get("review_score"),
                "coverage_state": item.get("coverage_state"),
                "is_holding": bool(item.get("is_holding")),
                "reason": item.get("reason"),
                "next_command": item.get("next_command"),
            }
            for item in (bucket.get("items", []) if isinstance(bucket.get("items"), list) else [])[:4]
            if isinstance(item, dict)
        ],
    }


def compact_market_breadth(value: object) -> Dict[str, object]:
    breadth = value if isinstance(value, dict) else {}
    if not breadth:
        return {}
    return {
        "state": breadth.get("state"),
        "confidence": breadth.get("confidence"),
        "summary": breadth.get("summary"),
        "sample_note": breadth.get("sample_note"),
        "matched_quote_count": breadth.get("matched_quote_count", 0),
        "up_count": breadth.get("up_count", 0),
        "down_count": breadth.get("down_count", 0),
        "up_ratio": breadth.get("up_ratio", 0),
        "active_count": breadth.get("active_count", 0),
        "active_ratio": breadth.get("active_ratio", 0),
        "strong_count": breadth.get("strong_count", 0),
        "stage_high_count": breadth.get("stage_high_count", 0),
        "active_group_count": breadth.get("active_group_count", 0),
        "strong_group_count": breadth.get("strong_group_count", 0),
        "interpretation": breadth.get("interpretation"),
    }


def compact_scan_group(item: Dict[str, object]) -> Dict[str, object]:
    return {
        "rank": item.get("rank"),
        "key": item.get("key"),
        "group_type": item.get("group_type"),
        "layer": item.get("layer"),
        "name": item.get("name"),
        "score": item.get("score"),
        "member_count": item.get("member_count"),
        "active_member_count": item.get("active_member_count"),
        "avg_change_pct": item.get("avg_change_pct"),
        "avg_amount_ratio": item.get("avg_amount_ratio"),
        "leaders": [
            {
                "symbol": leader.get("symbol"),
                "name": leader.get("name"),
                "change_pct": leader.get("change_pct"),
                "coverage_state": leader.get("coverage_state"),
            }
            for leader in (item.get("leaders", []) if isinstance(item.get("leaders"), list) else [])[:3]
            if isinstance(leader, dict)
        ],
        "signals": list(item.get("signals", []))[:6] if isinstance(item.get("signals"), list) else [],
        "risks": list(item.get("risks", []))[:6] if isinstance(item.get("risks"), list) else [],
    }


def compact_scan_candidate(item: Dict[str, object]) -> Dict[str, object]:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    return {
        "rank": item.get("rank"),
        "symbol": item.get("symbol"),
        "name": item.get("name"),
        "is_holding": bool(item.get("is_holding")),
        "review_score": item.get("review_score"),
        "ranking_breakdown": compact_scan_ranking_breakdown(item.get("ranking_breakdown", {})),
        "priority": item.get("priority"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": list(item.get("coverage_state_reasons", []))[:5] if isinstance(item.get("coverage_state_reasons"), list) else [],
        "research_status": compact_research_status(item.get("research_status", {})),
        "change_pct": quote.get("change_pct"),
        "amount_ratio": quote.get("amount_ratio"),
        "intraday_fade_pct": quote.get("intraday_fade_pct"),
        "sector_contexts": [
            {
                "group_type": context.get("group_type"),
                "name": context.get("name"),
                "score": context.get("score"),
                "rank": context.get("rank"),
                "member_count": context.get("member_count", 0),
                "active_member_count": context.get("active_member_count", 0),
            }
            for context in (item.get("sector_contexts", []) if isinstance(item.get("sector_contexts"), list) else [])[:3]
            if isinstance(context, dict)
        ],
        "universe_context": compact_scan_universe_context(item.get("universe_context", {})),
        "risk_flags": list(item.get("risk_flags", []))[:8] if isinstance(item.get("risk_flags"), list) else [],
        "review_focus": compact_scan_review_focus(item.get("review_focus", {})),
        "why_now": item.get("why_now"),
        "checklist": list(item.get("checklist", []))[:5] if isinstance(item.get("checklist"), list) else [],
        "commands": list(item.get("commands", []))[:4] if isinstance(item.get("commands"), list) else [],
        "done_when": item.get("done_when"),
    }


def compact_scan_review_focus(value: object) -> Dict[str, object]:
    focus = value if isinstance(value, dict) else {}
    classification = focus.get("classification", {}) if isinstance(focus.get("classification"), dict) else {}
    coverage = focus.get("coverage", {}) if isinstance(focus.get("coverage"), dict) else {}
    primary_context = classification.get("primary_context", {}) if isinstance(classification.get("primary_context"), dict) else {}
    return {
        "headline": focus.get("headline"),
        "classification": {
            "industry": classification.get("industry"),
            "concepts": list(classification.get("concepts", []))[:4] if isinstance(classification.get("concepts"), list) else [],
            "index_membership": list(classification.get("index_membership", []))[:4] if isinstance(classification.get("index_membership"), list) else [],
            "primary_layer": classification.get("primary_layer"),
            "primary_sub_sector": classification.get("primary_sub_sector"),
            "primary_context": {
                "group_type": primary_context.get("group_type"),
                "name": primary_context.get("name"),
                "score": primary_context.get("score"),
                "rank": primary_context.get("rank"),
            }
            if primary_context
            else {},
        },
        "coverage": {
            "state": coverage.get("state"),
            "reasons": list(coverage.get("reasons", []))[:4] if isinstance(coverage.get("reasons"), list) else [],
            "research_status": coverage.get("research_status"),
            "research_confirmed": bool(coverage.get("research_confirmed")),
            "missing_research_fields": list(coverage.get("missing_research_fields", []))[:4]
            if isinstance(coverage.get("missing_research_fields"), list)
            else [],
        },
        "universe_context": compact_scan_universe_context(focus.get("universe_context", {})),
        "ranking_breakdown": compact_scan_ranking_breakdown(focus.get("ranking_breakdown", {})),
        "signal_drivers": list(focus.get("signal_drivers", []))[:5] if isinstance(focus.get("signal_drivers"), list) else [],
        "risk_flags": list(focus.get("risk_flags", []))[:6] if isinstance(focus.get("risk_flags"), list) else [],
        "first_check": focus.get("first_check"),
        "next_command": focus.get("next_command"),
        "done_when": focus.get("done_when"),
    }


def compact_scan_ranking_breakdown(value: object) -> Dict[str, object]:
    data = value if isinstance(value, dict) else {}
    factors = data.get("factors", data.get("top_factors", []))
    penalties = data.get("penalty_flags", [])
    return {
        "total_score": data.get("total_score"),
        "raw_score": data.get("raw_score"),
        "penalty_score": data.get("penalty_score"),
        "top_factors": compact_ranking_rows(factors),
        "penalty_flags": compact_ranking_rows(penalties),
        "summary": data.get("summary"),
    }


def compact_ranking_rows(value: object) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    return [
        {
            "id": item.get("id"),
            "score": item.get("score"),
            "reason": item.get("reason"),
        }
        for item in sorted(
            (row for row in rows if isinstance(row, dict)),
            key=lambda row: -float(row.get("score") or 0),
        )[:4]
    ]


def compact_scan_universe_context(value: object) -> Dict[str, object]:
    context = value if isinstance(value, dict) else {}
    top_contexts = context.get("top_contexts", []) if isinstance(context.get("top_contexts"), list) else []
    return {
        "available": bool(context.get("available")),
        "dimensions": list(context.get("dimensions", []))[:3] if isinstance(context.get("dimensions"), list) else [],
        "dimension_count": context.get("dimension_count", 0),
        "industry": context.get("industry"),
        "concept_count": context.get("concept_count", 0),
        "index_membership_count": context.get("index_membership_count", 0),
        "context_count": context.get("context_count", 0),
        "top_contexts": [
            {
                "group_type": item.get("group_type"),
                "name": item.get("name"),
                "score": item.get("score"),
                "rank": item.get("rank"),
            }
            for item in top_contexts[:3]
            if isinstance(item, dict)
        ],
        "score_bonus": context.get("score_bonus", 0),
        "explain": context.get("explain"),
    }


def compact_coverage_context(value: object) -> Dict[str, object]:
    coverage = value if isinstance(value, dict) else {}
    if not coverage.get("available"):
        return {"available": False}
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    data_quality_queue = coverage.get("data_quality_queue", []) if isinstance(coverage.get("data_quality_queue"), list) else []
    return {
        "available": True,
        "pool": coverage.get("pool"),
        "scope": coverage.get("scope"),
        "status": coverage.get("status"),
        "summary": coverage.get("summary"),
        "universe": {
            "available": bool(universe.get("available")),
            "record_count": universe.get("record_count", 0),
            "industry_count": universe.get("industry_count", 0),
            "concept_count": universe.get("concept_count", 0),
            "index_membership_count": universe.get("index_membership_count", 0),
            "enrichment_queue": compact_universe_enrichment_queue(universe.get("enrichment_queue", [])),
            "sector_profile": {
                "industry_coverage_ratio": profile.get("industry_coverage_ratio", 0),
                "concept_coverage_ratio": profile.get("concept_coverage_ratio", 0),
                "index_coverage_ratio": profile.get("index_coverage_ratio", 0),
                "top_industries": list(profile.get("top_industries", []))[:5] if isinstance(profile.get("top_industries"), list) else [],
                "missing_field_counts": profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {},
                "coverage_flags": list(profile.get("coverage_flags", [])) if isinstance(profile.get("coverage_flags"), list) else [],
            },
        },
        "gaps": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in (coverage.get("gaps", []) if isinstance(coverage.get("gaps"), list) else [])[:5]
            if isinstance(item, dict)
        ],
        "data_quality_queue": compact_coverage_data_quality_queue(data_quality_queue),
        "next_actions": [
            {
                "id": item.get("id"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
            }
            for item in (coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else [])[:5]
            if isinstance(item, dict)
        ],
    }


def compact_universe_enrichment_queue(value: object) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    compact = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        samples = item.get("samples", []) if isinstance(item.get("samples"), list) else []
        compact.append(
            {
                "rank": item.get("rank"),
                "field": item.get("field"),
                "label": item.get("label"),
                "severity": item.get("severity"),
                "missing_count": item.get("missing_count", 0),
                "missing_ratio": item.get("missing_ratio", 0),
                "reason": item.get("reason"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
                "samples": [
                    {
                        "symbol": sample.get("symbol"),
                        "name": sample.get("name"),
                    }
                    for sample in samples[:3]
                    if isinstance(sample, dict)
                ],
            }
        )
    return compact


def compact_coverage_data_quality_queue(rows: List[object]) -> List[Dict[str, object]]:
    compact = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        samples = item.get("samples", []) if isinstance(item.get("samples"), list) else []
        compact.append(
            {
                "rank": item.get("rank"),
                "flag": item.get("flag"),
                "severity": item.get("severity"),
                "category": item.get("category"),
                "affected_count": item.get("affected_count", 0),
                "suggested_action": item.get("suggested_action"),
                "done_when": item.get("done_when"),
                "review_command": item.get("review_command"),
                "samples": [
                    {
                        "symbol": sample.get("symbol"),
                        "name": sample.get("name"),
                        "raw_row": sample.get("raw_row"),
                        "raw_code": sample.get("raw_code"),
                    }
                    for sample in samples[:3]
                    if isinstance(sample, dict)
                ],
            }
        )
    return compact


def compact_daily_review_tasks(value: object) -> List[Dict[str, object]]:
    tasks = value if isinstance(value, list) else []
    rows = []
    for task in tasks[:6]:
        if not isinstance(task, dict):
            continue
        rows.append(
            {
                "priority": task.get("priority"),
                "id": task.get("id"),
                "title": task.get("title"),
                "evidence": list(task.get("evidence", []))[:3] if isinstance(task.get("evidence"), list) else [],
                "commands": list(task.get("commands", []))[:2] if isinstance(task.get("commands"), list) else [],
                "note_command": task.get("note_command"),
                "note_prerequisite": compact_note_prerequisite(task.get("note_prerequisite", {})),
                "done_when": task.get("done_when"),
            }
        )
    return rows


def compact_daily_security_queue(value: object) -> List[Dict[str, object]]:
    items = value if isinstance(value, list) else []
    rows = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "priority_score": item.get("priority_score"),
                "sources": list(item.get("sources", []))[:4] if isinstance(item.get("sources"), list) else [],
                "reasons": list(item.get("reasons", []))[:4] if isinstance(item.get("reasons"), list) else [],
                "risk_flags": list(item.get("risk_flags", []))[:6] if isinstance(item.get("risk_flags"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "note_command": item.get("note_command"),
                "note_prerequisite": compact_note_prerequisite(item.get("note_prerequisite", {})),
            }
        )
    return rows


def compact_security_risk_profile(value: object, limit: int = 8) -> List[Dict[str, object]]:
    items = value if isinstance(value, list) else []
    rows = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "priority_score": item.get("priority_score"),
                "severity": item.get("severity"),
                "risk_ids": list(item.get("risk_ids", []))[:8] if isinstance(item.get("risk_ids"), list) else [],
                "related_risks": list(item.get("related_risks", []))[:5] if isinstance(item.get("related_risks"), list) else [],
                "evidence": list(item.get("evidence", []))[:4] if isinstance(item.get("evidence"), list) else [],
                "review_questions": list(item.get("review_questions", []))[:4] if isinstance(item.get("review_questions"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "note_command": item.get("note_command"),
                "note_prerequisite": compact_note_prerequisite(item.get("note_prerequisite", {})),
                "done_when": item.get("done_when"),
            }
        )
    return rows


def compact_note_prerequisite(value: object) -> Dict[str, object]:
    prereq = value if isinstance(value, dict) else {}
    if not prereq:
        return {}
    return {
        "requires_journal_entry": bool(prereq.get("requires_journal_entry")),
        "archive_command": prereq.get("archive_command"),
        "archive_runnable": bool(prereq.get("archive_runnable")),
    }


def compact_daily_journal_actions(value: object) -> List[Dict[str, object]]:
    actions = value if isinstance(value, list) else []
    rows = []
    for action in actions[:5]:
        if not isinstance(action, dict):
            continue
        rows.append(
            {
                "id": action.get("id"),
                "title": action.get("title"),
                "command": action.get("command"),
                "runnable": bool(action.get("runnable")),
                "reason": action.get("reason"),
            }
        )
    return rows


def compact_command_queue(value: object, limit: int = 12) -> List[Dict[str, object]]:
    queue = value if isinstance(value, list) else []
    rows = []
    for item in queue[:limit]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": item.get("rank"),
                "command": item.get("command"),
                "json_command": item.get("json_command"),
                "runnable": bool(item.get("runnable", True)),
                "mutates_state": bool(item.get("mutates_state")),
                "state_effect": item.get("state_effect"),
                "purpose": item.get("purpose") or item.get("reason"),
                "read_fields": list(item.get("read_fields", []))[:4] if isinstance(item.get("read_fields"), list) else [],
                "done_when": item.get("done_when"),
                "requires_prior_command": item.get("requires_prior_command"),
                "run_after_rank": item.get("run_after_rank"),
                "unavailable_reason": item.get("unavailable_reason"),
                "related_focus": list(item.get("related_focus", []))[:4] if isinstance(item.get("related_focus"), list) else [],
            }
        )
    return rows


def compact_risk_register(value: object, limit: int = 8) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "rank": item.get("rank"),
                "risk_id": item.get("risk_id"),
                "label": item.get("label"),
                "severity": item.get("severity"),
                "severity_score": item.get("severity_score"),
                "scope": item.get("scope"),
                "affected_count": item.get("affected_count"),
                "affected_symbols": list(item.get("affected_symbols", []))[:5] if isinstance(item.get("affected_symbols"), list) else [],
                "evidence": list(item.get("evidence", []))[:3] if isinstance(item.get("evidence"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "review_question": item.get("review_question"),
                "done_when": item.get("done_when"),
            }
        )
    return result


def compact_review_path(value: object, limit: int = 6) -> List[Dict[str, object]]:
    rows = value if isinstance(value, list) else []
    result = []
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "rank": item.get("rank"),
                "id": item.get("id"),
                "title": item.get("title"),
                "reason": item.get("reason"),
                "risk_ids": list(item.get("risk_ids", []))[:4] if isinstance(item.get("risk_ids"), list) else [],
                "affected_symbols": list(item.get("affected_symbols", []))[:5] if isinstance(item.get("affected_symbols"), list) else [],
                "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
                "runnable": bool(item.get("runnable", True)),
                "unavailable_reason": item.get("unavailable_reason"),
                "done_when": item.get("done_when"),
            }
        )
    return result


def compact_history(journal_timeline: Dict[str, object], journal_compare: Optional[Dict[str, object]]) -> Dict[str, object]:
    points = journal_timeline.get("points", []) if isinstance(journal_timeline.get("points"), list) else []
    transitions = journal_timeline.get("transitions", []) if isinstance(journal_timeline.get("transitions"), list) else []
    latest_transition = transitions[-1] if transitions and isinstance(transitions[-1], dict) else None
    compare_summary = None
    if isinstance(journal_compare, dict) and journal_compare.get("found"):
        compare_summary = journal_compare.get("summary")
    return {
        "available": bool(journal_timeline.get("found")),
        "can_compare": bool(journal_timeline.get("can_compare")),
        "count": journal_timeline.get("count", 0),
        "total_count": journal_timeline.get("total_count", 0),
        "latest_entry": points[-1] if points and isinstance(points[-1], dict) else None,
        "summary": journal_timeline.get("summary"),
        "latest_transition": latest_transition,
        "compare_summary": compare_summary,
    }


def compact_current_change(current_compare: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(current_compare, dict) or not current_compare.get("found"):
        return {
            "available": False,
            "summary": current_compare.get("summary") if isinstance(current_compare, dict) else "暂无当前对比。",
            "base_entry": None,
            "current_entry": None,
            "risk_flags": {"added_count": 0, "removed_count": 0},
            "watchlist": {"added_count": 0, "removed_count": 0, "changed_count": 0},
            "portfolio_review": {"added_count": 0, "removed_count": 0, "changed_count": 0, "high_review_delta": 0},
            "hotspots": {"added_count": 0, "removed_count": 0, "changed_count": 0, "top": {"base": None, "current": None}},
            "validation": {"warning_delta": 0, "error_delta": 0},
            "next_commands": current_compare.get("next_commands", []) if isinstance(current_compare, dict) else [],
        }
    changes = current_compare.get("changes", {}) if isinstance(current_compare.get("changes"), dict) else {}
    return {
        "available": True,
        "summary": current_compare.get("summary"),
        "base_entry": current_compare.get("base_entry"),
        "current_entry": current_compare.get("current_entry"),
        "risk_flags": compact_text_set(changes.get("risk_flags", {})),
        "watchlist": compact_collection_change(changes.get("watchlist", {})),
        "portfolio_review": compact_portfolio_change(changes.get("portfolio_review", {})),
        "hotspots": compact_hotspot_change(changes.get("hotspots", {})),
        "validation": compact_validation_change(changes.get("validation", {})),
        "next_commands": current_compare.get("next_commands", []) if isinstance(current_compare.get("next_commands"), list) else [],
    }


def compact_text_set(value: object) -> Dict[str, object]:
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


def compact_collection_change(value: object) -> Dict[str, object]:
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


def compact_portfolio_change(value: object) -> Dict[str, object]:
    compact = compact_collection_change(value)
    change = value if isinstance(value, dict) else {}
    priority = change.get("priority_counts", {}) if isinstance(change.get("priority_counts"), dict) else {}
    base_priority = priority.get("base", {}) if isinstance(priority.get("base"), dict) else {}
    current_priority = priority.get("current", {}) if isinstance(priority.get("current"), dict) else {}
    compact["priority_counts"] = {"base": base_priority, "current": current_priority}
    compact["high_review_delta"] = int_value(current_priority.get("high_review")) - int_value(base_priority.get("high_review"))
    return compact


def compact_hotspot_change(value: object) -> Dict[str, object]:
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
        "top": {
            "base": compact_change_hotspot(top.get("base")),
            "current": compact_change_hotspot(top.get("current")),
        },
    }


def compact_validation_change(value: object) -> Dict[str, object]:
    validation = value if isinstance(value, dict) else {}
    base = validation.get("base", {}) if isinstance(validation.get("base"), dict) else {}
    current = validation.get("current", {}) if isinstance(validation.get("current"), dict) else {}
    base_summary = base.get("summary", {}) if isinstance(base.get("summary"), dict) else {}
    current_summary = current.get("summary", {}) if isinstance(current.get("summary"), dict) else {}
    base_warning = int_value(base_summary.get("warning_count"), len(base.get("warning_codes", [])))
    current_warning = int_value(current_summary.get("warning_count"), len(current.get("warning_codes", [])))
    base_error = int_value(base_summary.get("error_count"), len(base.get("error_codes", [])))
    current_error = int_value(current_summary.get("error_count"), len(current.get("error_codes", [])))
    return {
        "warning_delta": current_warning - base_warning,
        "error_delta": current_error - base_error,
        "base_warning_count": base_warning,
        "current_warning_count": current_warning,
        "base_error_count": base_error,
        "current_error_count": current_error,
    }


def compact_change_hotspot(item: object) -> Optional[Dict[str, object]]:
    if not isinstance(item, dict):
        return None
    return {
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "score": item.get("score"),
        "rank": item.get("rank"),
    }


def current_change_has_delta(current_change: Dict[str, object]) -> bool:
    if not current_change.get("available"):
        return False
    risk = current_change.get("risk_flags", {}) if isinstance(current_change.get("risk_flags"), dict) else {}
    watchlist = current_change.get("watchlist", {}) if isinstance(current_change.get("watchlist"), dict) else {}
    portfolio = current_change.get("portfolio_review", {}) if isinstance(current_change.get("portfolio_review"), dict) else {}
    hotspots = current_change.get("hotspots", {}) if isinstance(current_change.get("hotspots"), dict) else {}
    validation = current_change.get("validation", {}) if isinstance(current_change.get("validation"), dict) else {}
    values = [
        risk.get("added_count", 0),
        risk.get("removed_count", 0),
        watchlist.get("added_count", 0),
        watchlist.get("removed_count", 0),
        watchlist.get("changed_count", 0),
        portfolio.get("added_count", 0),
        portfolio.get("removed_count", 0),
        portfolio.get("changed_count", 0),
        hotspots.get("added_count", 0),
        hotspots.get("removed_count", 0),
        hotspots.get("changed_count", 0),
        abs(int_value(validation.get("warning_delta"))),
        abs(int_value(validation.get("error_delta"))),
    ]
    return any(int_value(value) for value in values)


def current_change_summary(current_change: Dict[str, object]) -> str:
    risk = current_change.get("risk_flags", {}) if isinstance(current_change.get("risk_flags"), dict) else {}
    watchlist = current_change.get("watchlist", {}) if isinstance(current_change.get("watchlist"), dict) else {}
    portfolio = current_change.get("portfolio_review", {}) if isinstance(current_change.get("portfolio_review"), dict) else {}
    hotspots = current_change.get("hotspots", {}) if isinstance(current_change.get("hotspots"), dict) else {}
    validation = current_change.get("validation", {}) if isinstance(current_change.get("validation"), dict) else {}
    return "风险 +%s/-%s；观察 +%s/-%s/~%s；持仓复核 +%s/-%s/~%s；热点 +%s/-%s/~%s；告警 %+s；错误 %+s。" % (
        risk.get("added_count", 0),
        risk.get("removed_count", 0),
        watchlist.get("added_count", 0),
        watchlist.get("removed_count", 0),
        watchlist.get("changed_count", 0),
        portfolio.get("added_count", 0),
        portfolio.get("removed_count", 0),
        portfolio.get("changed_count", 0),
        hotspots.get("added_count", 0),
        hotspots.get("removed_count", 0),
        hotspots.get("changed_count", 0),
        validation.get("warning_delta", 0),
        validation.get("error_delta", 0),
    )


def build_review_focus(
    readiness: Dict[str, object],
    daily: Dict[str, object],
    history: Dict[str, object],
    current_change: Dict[str, object],
    market_scan: Dict[str, object],
) -> List[Dict[str, object]]:
    focus = []
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    warning_count = int_value(validation.get("warning_count"))
    error_count = int_value(validation.get("error_count"))
    if readiness.get("state") == "blocked" or error_count:
        focus.append(
            focus_item(
                10,
                "runtime_blocked",
                "数据阻塞",
                "先处理 runtime 错误，否则今日复盘不可用。",
                ["错误 %s 个" % (error_count or readiness.get("error_count", 0))],
                ["market-intel status runtime --json", "market-intel validate runtime --json"],
            )
        )
        return focus

    if warning_count or readiness.get("state") == "degraded":
        focus.append(
            focus_item(
                10,
                "data_warnings",
                "数据告警",
                "日报可生成，但需要先知道哪些字段会影响解读。",
                ["日报告警 %s 个" % warning_count]
                + compact_issue_evidence(validation.get("warnings", []))
                + ["runtime: %s" % readiness.get("reason")],
                ["market-intel validate runtime --json", "market-intel status runtime --text"],
            )
        )

    if market_scan.get("available"):
        groups = market_scan.get("sector_groups", []) if isinstance(market_scan.get("sector_groups"), list) else []
        candidates = market_scan.get("candidate_securities", []) if isinstance(market_scan.get("candidate_securities"), list) else []
        queue_item = first_candidate_queue_item(market_scan)
        if groups or candidates:
            focus.append(
                focus_item(
                    18,
                    "market_scan_review",
                    "全市场扫描",
                    "先看行业/概念/链路强弱，再进入持仓和单票复核。",
                    compact_scan_evidence(groups[:3], candidates[:3]),
                    ["market-intel scan --runtime --text"],
                )
            )
        if queue_item:
            focus.append(
                focus_item(
                    19,
                    "candidate_queue_next",
                    "队列首项",
                    "按候选队列先读最值得推进的标的，而不是只停留在 Top 列表。",
                    [candidate_queue_evidence(queue_item)],
                    [queue_item.get("next_command") or "market-intel pool explain %s --runtime --text" % queue_item.get("symbol")],
                )
            )

    top_hotspots = daily.get("top_hotspots", []) if isinstance(daily.get("top_hotspots"), list) else []
    if top_hotspots:
        top = top_hotspots[0]
        focus.append(
            focus_item(
                20,
                "strongest_hotspot",
                "最强链路",
                "先判断今日强度来自链路共振还是少数标的拉动。",
                ["%s / %s | 热点 %s" % (top.get("layer"), top.get("sub_sector"), top.get("score"))],
                ["market-intel map --runtime --text", "market-intel brief --runtime --text"],
            )
        )

    watchlist = daily.get("watchlist", {}) if isinstance(daily.get("watchlist"), dict) else {}
    watchlist_items = watchlist.get("top_items", []) if isinstance(watchlist.get("top_items"), list) else []
    if watchlist_items:
        focus.append(
            focus_item(
                25,
                "watchlist_review",
                "盘中观察",
                "把热点领涨和持仓观察放在同一张清单里核对。",
                compact_watchlist_evidence(watchlist_items[:3]),
                ["market-intel watchlist --runtime --text"],
            )
        )

    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    high_review_count = int_value(portfolio.get("high_review_count"))
    if high_review_count:
        top_items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
        commands = ["market-intel portfolio review --runtime --text"]
        first_symbol = first_symbol_from_items(top_items)
        if first_symbol:
            commands.append("market-intel portfolio explain %s --runtime --text" % first_symbol)
        focus.append(
            focus_item(
                30,
                "portfolio_review",
                "持仓复核",
                "优先查看风险标签最多、复核分最高的持仓上下文。",
                compact_security_evidence(top_items[:3]),
                commands,
            )
        )

    if current_change.get("available") and current_change_has_delta(current_change):
        focus.append(
            focus_item(
                35,
                "current_change",
                "当前变化",
                "当前 runtime 相比最近留档已经有变化，保存前先看变化集中在哪里。",
                [current_change_summary(current_change)],
                ["market-intel agent briefing --json", "market-intel journal latest --text"],
            )
        )

    transition = history.get("latest_transition", {}) if isinstance(history.get("latest_transition"), dict) else {}
    if transition:
        focus.append(
            focus_item(
                40,
                "history_transition",
                "历史转折",
                "把今天和上一次留档放在一起看，避免只看单日噪音。",
                [transition.get("summary") or history.get("summary")],
                [transition.get("compare_command") or "market-intel journal compare --json", "market-intel journal timeline --text"],
            )
        )
    elif daily.get("available"):
        focus.append(
            focus_item(
                50,
                "archive_daily",
                "日报留档",
                "保存今日日报，后续才能形成稳定的历史对比。",
                ["当前留档 %s 份" % history.get("count", 0)],
                ["market-intel journal save --runtime --json", "market-intel journal timeline --text"],
            )
        )

    return focus


def focus_item(
    priority: int,
    focus_id: str,
    title: str,
    reason: str,
    evidence: List[object],
    commands: List[object],
) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": focus_id,
        "title": title,
        "reason": reason,
        "evidence": [str(item) for item in evidence if item],
        "commands": [str(item) for item in commands if item],
    }


def build_review_checklist(
    readiness: Dict[str, object],
    daily: Dict[str, object],
    history: Dict[str, object],
    focus: List[Dict[str, object]],
    current_change: Dict[str, object],
    market_scan: Dict[str, object],
) -> List[Dict[str, object]]:
    if readiness.get("state") == "blocked" or not daily.get("available"):
        return [
            checklist_item(
                10,
                "runtime_ready_check",
                "确认 runtime 可生成日报",
                "数据阻塞时先处理错误，再进入复盘。",
                ["runtime: %s" % readiness.get("reason")],
                ["market-intel status runtime --json", "market-intel validate runtime --json"],
                "readiness.state 不是 blocked，且 validation.errors 为空。",
            )
        ]

    items: List[Dict[str, object]] = []
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    if int_value(validation.get("warning_count")) or readiness.get("state") == "degraded":
        items.append(
            checklist_item(
                10,
                "data_warning_review",
                "先看数据告警",
                "数据告警会影响热点、持仓和历史转折的解释权重。",
                ["告警 %s 个" % validation.get("warning_count", 0)]
                + compact_issue_evidence(validation.get("warnings", []))
                + ["runtime: %s" % readiness.get("reason")],
                ["market-intel validate runtime --json", "market-intel status runtime --text"],
                "知道哪些行情或持仓字段缺失，并决定是否需要补数据后再解读。",
            )
        )

    if market_scan.get("available"):
        groups = market_scan.get("sector_groups", []) if isinstance(market_scan.get("sector_groups"), list) else []
        candidates = market_scan.get("candidate_securities", []) if isinstance(market_scan.get("candidate_securities"), list) else []
        if groups or candidates:
            items.append(
                checklist_item(
                    18,
                    "market_scan_context_review",
                    "先扫全市场板块",
                    "用 scan 判断今日强弱是否只来自种子链路，还是已有行业/概念/指数层面的扩散。",
                    compact_scan_evidence(groups[:3], candidates[:3]),
                    ["market-intel scan --runtime --text"],
                    "能说清最强板块、候选标的、覆盖状态和仍需补证据的 foundation/draft 项。",
                )
            )

    top_hotspots = daily.get("top_hotspots", []) if isinstance(daily.get("top_hotspots"), list) else []
    if top_hotspots:
        top = top_hotspots[0]
        items.append(
            checklist_item(
                20,
                "hotspot_resonance_review",
                "确认最强链路是不是共振",
                "先判断强度来自多标的链路，还是少数标的单点拉动。",
                [
                    "%s / %s | 热点 %s | 活跃 %s/%s"
                    % (
                        top.get("layer"),
                        top.get("sub_sector"),
                        top.get("score"),
                        top.get("active_member_count"),
                        top.get("member_count"),
                    )
                ],
                ["market-intel map --runtime --text", "market-intel brief --runtime --text"],
                "能说清最强链路、活跃标的数量、领涨标的，以及它和持仓是否有关。",
            )
        )

    watchlist = daily.get("watchlist", {}) if isinstance(daily.get("watchlist"), dict) else {}
    watchlist_items = watchlist.get("top_items", []) if isinstance(watchlist.get("top_items"), list) else []
    if watchlist_items:
        items.append(
            checklist_item(
                30,
                "watchlist_context_review",
                "扫观察清单",
                "把热点领涨、持仓观察和池子解释串起来，避免只看涨幅。",
                compact_watchlist_evidence(watchlist_items[:4]),
                ["market-intel watchlist --runtime --text"],
                "前几项观察标的的链路、是否持仓、热点分和主要风险已核对。",
            )
        )

    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    portfolio_items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
    if portfolio_items:
        first_symbol = first_symbol_from_items(portfolio_items)
        commands = ["market-intel portfolio review --runtime --text"]
        if first_symbol:
            commands.append("market-intel portfolio explain %s --runtime --text" % first_symbol)
        items.append(
            checklist_item(
                40,
                "portfolio_risk_review",
                "逐项看持仓复核",
                "优先处理复核分高、风险标签多、缺行情或缺热点上下文的持仓。",
                compact_security_evidence(portfolio_items[:4]),
                commands,
                "重点复核项的行情、热点上下文、链路暴露、重复主题和复核问题已看过。",
            )
        )

    if current_change.get("available"):
        items.append(
            checklist_item(
                50,
                "current_change_review",
                "对照当前 runtime 与最近留档",
                "当前数据还没保存前，先看它相对最近留档已经发生的变化。",
                [current_change.get("summary")],
                ["market-intel agent briefing --json", "market-intel journal latest --text"],
                "能说清当前 runtime 相比最近留档的风险、观察项、持仓复核和热点变化。",
            )
        )

    transition = history.get("latest_transition", {}) if isinstance(history.get("latest_transition"), dict) else {}
    if transition:
        items.append(
            checklist_item(
                60,
                "history_transition_review",
                "对照最近历史转折",
                "用最近两份留档过滤单日噪音，关注风险、热点和持仓复核是否同向变化。",
                [transition.get("summary")],
                [transition.get("compare_command") or "market-intel journal compare --json", "market-intel journal timeline --text"],
                "能说清本次相对上一份留档新增/减少/变化的风险、观察项、持仓复核和热点。",
            )
        )
    else:
        items.append(
            checklist_item(
                70,
                "archive_for_history",
                "保存日报留档",
                "没有历史就无法判断转折，只能看单日截面。",
                ["当前留档 %s 份" % history.get("count", 0)],
                ["market-intel journal save --runtime --json", "market-intel journal timeline --text"],
                "本次日报已保存，下一次复盘可以形成历史对比。",
            )
        )

    return items


def checklist_item(
    priority: int,
    item_id: str,
    title: str,
    reason: str,
    evidence: List[object],
    commands: List[object],
    done_when: str,
) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": item_id,
        "title": title,
        "reason": reason,
        "evidence": [str(item) for item in evidence if item],
        "commands": [str(command) for command in commands if command],
        "done_when": done_when,
    }


def briefing_state(readiness: Dict[str, object], daily: Dict[str, object], history: Dict[str, object]) -> str:
    readiness_state = str(readiness.get("state") or "blocked")
    if readiness_state == "blocked" or not daily.get("available"):
        return "blocked"
    suffix = "with_history" if history.get("can_compare") else "needs_history"
    if readiness_state == "degraded":
        return "degraded_%s" % suffix
    return "ready_%s" % suffix


def briefing_summary(
    state: str,
    readiness: Dict[str, object],
    daily: Dict[str, object],
    history: Dict[str, object],
    focus: List[Dict[str, object]],
    market_scan: Optional[Dict[str, object]] = None,
) -> str:
    if state == "blocked":
        return "runtime 暂不可生成 briefing：%s" % (readiness.get("reason") or "需要先处理数据。")
    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    history_text = "已有历史对比" if history.get("can_compare") else "历史对比不足"
    scan_text = ""
    if isinstance(market_scan, dict) and market_scan.get("available"):
        groups = market_scan.get("sector_groups", []) if isinstance(market_scan.get("sector_groups"), list) else []
        candidates = market_scan.get("candidate_securities", []) if isinstance(market_scan.get("candidate_securities"), list) else []
        scan_text = "；扫描板块 %s 个，候选 %s 个" % (len(groups), len(candidates))
    return (
        "交易日 %s：风险 %s 个，观察 %s 个，持仓复核 %s 个，其中重点复核 %s 个；数据告警 %s 个%s；%s；复核焦点 %s 个。"
        % (
            daily.get("trade_date") or "未知",
            len(daily.get("risk_flags", []) if isinstance(daily.get("risk_flags"), list) else []),
            daily.get("watchlist", {}).get("count", 0) if isinstance(daily.get("watchlist"), dict) else 0,
            portfolio.get("count", 0),
            portfolio.get("high_review_count", 0),
            validation.get("warning_count", 0),
            scan_text,
            history_text,
            len(focus),
        )
    )


def briefing_questions(
    daily: Dict[str, object],
    history: Dict[str, object],
    focus: List[Dict[str, object]],
    current_change: Dict[str, object],
    market_scan: Optional[Dict[str, object]] = None,
) -> List[str]:
    questions = []
    if isinstance(market_scan, dict):
        questions.extend(str(question) for question in market_scan.get("questions", [])[:3] if question)
    questions.extend(str(question) for question in daily.get("next_questions", [])[:4] if question)
    if current_change.get("available"):
        questions.append("当前 runtime 相比最近留档，变化主要集中在热点、观察项还是持仓复核？")
    if history.get("latest_transition"):
        questions.append("最近一次留档转折里，风险、热点和持仓复核变化是否指向同一条链路？")
    for item in focus[:3]:
        if isinstance(item, dict):
            questions.append("%s：%s" % (item.get("title"), item.get("reason")))
    return dedupe(questions)[:6]


def build_journal_prompt(
    daily: Dict[str, object],
    history: Dict[str, object],
    current_change: Dict[str, object],
    security_queue: List[Dict[str, object]],
) -> Dict[str, object]:
    if not daily.get("available"):
        return {
            "available": False,
            "summary": "runtime 暂不可用，先记录阻塞原因和需补数据文件。",
            "sections": [
                journal_prompt_section(
                    "runtime_blocker",
                    "runtime 阻塞",
                    "记录缺失文件、坏 JSON 或缺字段，并说明下一步需要补什么数据。",
                )
            ],
        }
    sections = [
        journal_prompt_section("data_quality", "数据质量", journal_data_quality_prompt(daily)),
        journal_prompt_section("market_structure", "市场结构", journal_market_structure_prompt(daily)),
        journal_prompt_section("portfolio_exposure", "组合暴露", journal_portfolio_exposure_prompt(daily)),
        journal_prompt_section("security_review", "标的复核", journal_security_review_prompt(security_queue)),
        journal_prompt_section("current_change", "当前变化", journal_current_change_prompt(current_change, history)),
    ]
    return {
        "available": True,
        "summary": "按固定五段记录今天复盘，便于后续和 journal 留档对比。",
        "sections": sections,
    }


def journal_prompt_section(section_id: str, title: str, prompt: str) -> Dict[str, object]:
    return {
        "id": section_id,
        "title": title,
        "prompt": prompt,
        "note_command": "market-intel journal note --section %s --text '<填写%s复盘笔记>'" % (section_id, title),
    }


def journal_data_quality_prompt(daily: Dict[str, object]) -> str:
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    if not warnings:
        return "记录数据告警为 0；确认行情和持仓覆盖完整。"
    return "记录告警 %s 个，重点写清 %s。" % (
        validation.get("warning_count", len(warnings)),
        "；".join(compact_issue_evidence(warnings, limit=3)),
    )


def journal_market_structure_prompt(daily: Dict[str, object]) -> str:
    hotspots = daily.get("top_hotspots", []) if isinstance(daily.get("top_hotspots"), list) else []
    if not hotspots:
        return "记录今日没有稳定热点结构，后续只保留数据截面。"
    top = hotspots[0]
    return "记录最强链路 %s / %s，热点 %s，活跃 %s/%s；说明强度来自共振还是少数标的。" % (
        top.get("layer"),
        top.get("sub_sector"),
        top.get("score"),
        top.get("active_member_count"),
        top.get("member_count"),
    )


def journal_portfolio_exposure_prompt(daily: Dict[str, object]) -> str:
    exposure = daily.get("portfolio_exposure", {}) if isinstance(daily.get("portfolio_exposure"), dict) else {}
    if not exposure.get("has_concentration"):
        return "记录组合暂无重复链路或重复主题暴露。"
    groups = exposure.get("repeated_exposures", []) if isinstance(exposure.get("repeated_exposures"), list) else []
    overlap = exposure.get("repeated_overlap_groups", []) if isinstance(exposure.get("repeated_overlap_groups"), list) else []
    names = [str(group.get("group")) for group in groups[:2] if isinstance(group, dict) and group.get("group")]
    names.extend(str(group.get("group")) for group in overlap[:2] if isinstance(group, dict) and group.get("group"))
    return "记录组合集中暴露：%s；说明这些持仓是否受同一叙事和同一风险驱动。" % ("、".join(names) or "有重复暴露")


def journal_security_review_prompt(security_queue: List[Dict[str, object]]) -> str:
    if not security_queue:
        return "记录今日没有高优先级标的复核队列。"
    names = [
        "%s%s" % (item.get("symbol"), " %s" % item.get("name") if item.get("name") else "")
        for item in security_queue[:3]
        if isinstance(item, dict) and item.get("symbol")
    ]
    return "记录优先复核标的：%s；每只写清主要风险标签、所属链路和还需验证的问题。" % ("、".join(names) or "暂无")


def journal_current_change_prompt(current_change: Dict[str, object], history: Dict[str, object]) -> str:
    if current_change.get("available"):
        return "记录当前 runtime 相比最近留档的变化：%s" % (current_change.get("summary") or "暂无摘要。")
    if history.get("can_compare"):
        return "记录最近历史转折，并说明今日是否延续上一份留档的主线。"
    return "记录这是历史样本不足阶段，先保存日报留档，后续再做转折对比。"


def briefing_next_commands(
    readiness: Dict[str, object],
    daily: Dict[str, object],
    history: Dict[str, object],
    current_change: Dict[str, object],
    market_scan: Optional[Dict[str, object]] = None,
) -> List[str]:
    if readiness.get("state") == "blocked" or not daily.get("available"):
        return [
            "market-intel status runtime --json",
            "market-intel validate runtime --json",
            "market-intel import schema --json",
        ]
    commands = [
        "market-intel agent briefing --json",
        "market-intel pool coverage --runtime --text",
        "market-intel scan --runtime --text",
        "market-intel daily --runtime --text",
        "market-intel portfolio review --runtime --text",
        "market-intel watchlist --runtime --text",
    ]
    first_scan_symbol = None
    first_queue_command = None
    if isinstance(market_scan, dict) and market_scan.get("available"):
        queue_item = first_candidate_queue_item(market_scan)
        if queue_item:
            first_scan_symbol = str(queue_item.get("symbol") or "") or None
            first_queue_command = queue_item.get("next_command")
        if not first_scan_symbol:
            candidates = market_scan.get("candidate_securities", []) if isinstance(market_scan.get("candidate_securities"), list) else []
            first_scan_symbol = first_symbol_from_items(candidates)
    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    portfolio_items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
    first_symbol = first_symbol_from_items(portfolio_items)
    if first_symbol:
        commands.append("market-intel portfolio explain %s --runtime --text" % first_symbol)
    if first_queue_command:
        commands.append(str(first_queue_command))
    elif first_scan_symbol:
        commands.append("market-intel pool explain %s --runtime --text" % first_scan_symbol)
    if current_change.get("available"):
        commands.append("market-intel journal latest --text")
    if history.get("can_compare"):
        transition = history.get("latest_transition", {}) if isinstance(history.get("latest_transition"), dict) else {}
        compare_command = transition.get("compare_command")
        if compare_command:
            commands.append(str(compare_command))
        commands.append("market-intel journal timeline --text")
    else:
        commands.append("market-intel journal save --runtime --json")
    return dedupe(commands)


def first_candidate_queue_item(market_scan: Dict[str, object]) -> Optional[Dict[str, object]]:
    queue = market_scan.get("candidate_queue", {}) if isinstance(market_scan.get("candidate_queue"), dict) else {}
    buckets = queue.get("buckets", {}) if isinstance(queue.get("buckets"), dict) else {}
    for key in ["review_now", "data_first", "deprioritized"]:
        bucket = buckets.get(key, {}) if isinstance(buckets.get(key), dict) else {}
        items = bucket.get("items", []) if isinstance(bucket.get("items"), list) else []
        for item in items:
            if isinstance(item, dict) and item.get("symbol"):
                return item
    return None


def candidate_queue_evidence(item: Dict[str, object]) -> str:
    return "%s %s | 分 %s | 覆盖 %s | %s" % (
        item.get("symbol"),
        item.get("name"),
        render_number(item.get("review_score")),
        item.get("coverage_state"),
        item.get("reason") or "候选队列首项",
    )


def agent_briefing_contract(max_quote_age_days: int) -> Dict[str, object]:
    return {
        "success": "ok=true 表示 briefing 生成成功；data.state 决定是否可直接复盘。",
        "state_values": [
            "blocked",
            "degraded_needs_history",
            "degraded_with_history",
            "ready_needs_history",
            "ready_with_history",
        ],
        "stable_fields": [
            "data.state",
            "data.runtime.readiness",
            "data.runtime.validation",
            "data.market_scan",
            "data.market_scan.market_breadth",
            "data.market_scan.sector_groups",
            "data.market_scan.candidate_securities",
            "data.market_scan.candidate_queue",
            "data.market_scan.candidate_securities[].ranking_breakdown",
            "data.market_scan.candidate_securities[].universe_context",
            "data.market_scan.candidate_securities[].why_now",
            "data.market_scan.candidate_securities[].checklist",
            "data.daily.available",
            "data.daily.top_hotspots",
            "data.daily.watchlist",
            "data.daily.portfolio_review",
            "data.daily.portfolio_review.top_items[].coverage_state",
            "data.daily.portfolio_review.top_items[].coverage_state_reasons",
            "data.daily.portfolio_review.top_items[].research_status",
            "data.daily.portfolio_exposure",
            "data.daily.coverage_context",
            "data.daily.coverage_context.universe.sector_profile",
            "data.daily.coverage_context.universe.enrichment_queue",
            "data.daily.coverage_context.data_quality_queue",
            "data.daily.coverage_context.next_actions",
            "data.daily.risk_register",
            "data.daily.risk_register[].severity",
            "data.daily.risk_register[].affected_symbols",
            "data.daily.risk_register[].commands",
            "data.daily.review_path",
            "data.daily.review_path[].commands",
            "data.daily.review_path[].runnable",
            "data.daily.review_path[].done_when",
            "data.daily.validation.warnings",
            "data.daily.validation.errors",
            "data.daily.review_tasks",
            "data.daily.review_tasks[].note_command",
            "data.daily.review_tasks[].note_prerequisite",
            "data.daily.security_review_queue",
            "data.daily.security_review_queue[].note_command",
            "data.daily.security_review_queue[].note_prerequisite",
            "data.daily.security_risk_profile",
            "data.daily.security_risk_profile[].risk_ids",
            "data.daily.security_risk_profile[].commands",
            "data.daily.journal_actions",
            "data.daily.command_queue",
            "data.daily.command_queue[].command",
            "data.daily.command_queue[].runnable",
            "data.daily.command_queue[].state_effect",
            "data.current_change",
            "data.security_review_queue",
            "data.history.can_compare",
            "data.history.latest_entry.latest_note",
            "data.history.latest_transition",
            "data.review_focus",
            "data.review_checklist",
            "data.journal_prompt",
            "data.journal_prompt.sections[].note_command",
            "data.command_queue",
            "data.command_queue[].purpose",
            "data.command_queue[].read_fields",
            "data.command_queue[].done_when",
            "data.command_queue[].state_effect",
            "data.next_commands",
        ],
        "freshness": "max_quote_age_days=%s" % max_quote_age_days,
        "boundary": "这是市场情报 briefing，不生成交易指令、目标价或仓位建议。",
    }


def compact_hotspot(item: Dict[str, object], rank: int) -> Dict[str, object]:
    leaders = item.get("leaders", []) if isinstance(item.get("leaders"), list) else []
    return {
        "rank": rank,
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "score": item.get("score"),
        "active_member_count": item.get("active_member_count"),
        "member_count": item.get("member_count"),
        "leaders": [
            {"symbol": leader.get("symbol"), "name": leader.get("name"), "change_pct": leader.get("change_pct")}
            for leader in leaders[:3]
            if isinstance(leader, dict)
        ],
        "signals": list(item.get("signals", [])) if isinstance(item.get("signals"), list) else [],
        "risks": list(item.get("risks", [])) if isinstance(item.get("risks"), list) else [],
    }


def compact_watchlist_item(item: Dict[str, object]) -> Dict[str, object]:
    symbol = item.get("symbol")
    is_holding = bool(item.get("is_holding"))
    return {
        "symbol": symbol,
        "name": item.get("name"),
        "is_holding": is_holding,
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "focus": item.get("focus") or item.get("reason"),
        "change_pct": item.get("change_pct"),
        "hotspot_score": item.get("hotspot_score"),
        "risks": list(item.get("risks", [])) if isinstance(item.get("risks"), list) else [],
        "commands": watchlist_item_commands(symbol, is_holding),
    }


def compact_portfolio_item(item: Dict[str, object]) -> Dict[str, object]:
    symbol = item.get("symbol")
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    return {
        "symbol": symbol,
        "name": item.get("name"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": list(item.get("coverage_state_reasons", [])) if isinstance(item.get("coverage_state_reasons"), list) else [],
        "research_status": compact_research_status(item.get("research_status", {})),
        "risk_flags": list(item.get("risk_flags", [])) if isinstance(item.get("risk_flags"), list) else [],
        "review_points": list(item.get("review_points", []))[:3] if isinstance(item.get("review_points"), list) else [],
        "exposures": compact_exposures(item.get("exposures", [])),
        "overlap_groups": list(item.get("overlap_groups", []))[:5] if isinstance(item.get("overlap_groups"), list) else [],
        "quote": {
            "change_pct": quote.get("change_pct"),
            "amount_ratio": quote.get("amount_ratio"),
            "intraday_fade_pct": quote.get("intraday_fade_pct"),
        }
        if quote
        else None,
        "hotspot": {
            "layer": hotspot.get("layer"),
            "sub_sector": hotspot.get("sub_sector"),
            "score": hotspot.get("score"),
        }
        if hotspot
        else None,
        "commands": portfolio_item_commands(symbol),
    }


def compact_exposures(value: object) -> List[Dict[str, object]]:
    exposures = value if isinstance(value, list) else []
    return [
        {"layer": item.get("layer"), "sub_sector": item.get("sub_sector"), "role": item.get("role")}
        for item in exposures[:5]
        if isinstance(item, dict)
    ]


def compact_research_status(value: object) -> Dict[str, object]:
    data = value if isinstance(value, dict) else {}
    return {
        "available": bool(data.get("available")),
        "status": data.get("status") or "missing",
        "source_file": data.get("source_file"),
        "has_thesis": bool(data.get("has_thesis")),
        "has_evidence": bool(data.get("has_evidence")),
        "has_invalidation": bool(data.get("has_invalidation")),
        "missing_fields": list(data.get("missing_fields", [])) if isinstance(data.get("missing_fields"), list) else [],
        "confirmed": bool(data.get("confirmed")),
    }


def compact_group_counts(value: object) -> List[Dict[str, object]]:
    groups = value if isinstance(value, list) else []
    return [
        {"group": item.get("group"), "holding_count": item.get("holding_count")}
        for item in groups[:5]
        if isinstance(item, dict)
    ]


def compact_portfolio_exposure(portfolio: Dict[str, object], portfolio_items: List[object]) -> Dict[str, object]:
    repeated_exposures = compact_exposure_groups(portfolio.get("repeated_exposures", []), portfolio_items, "exposure")
    repeated_overlap_groups = compact_exposure_groups(portfolio.get("repeated_overlap_groups", []), portfolio_items, "overlap")
    group_count = len(repeated_exposures) + len(repeated_overlap_groups)
    affected_symbols = dedupe(
        [
            str(holding.get("symbol"))
            for group in repeated_exposures + repeated_overlap_groups
            for holding in group.get("holdings", [])
            if isinstance(holding, dict) and holding.get("symbol")
        ]
    )
    return {
        "has_concentration": bool(group_count),
        "summary": portfolio_exposure_summary(repeated_exposures, repeated_overlap_groups, affected_symbols),
        "group_count": group_count,
        "affected_holding_count": len(affected_symbols),
        "repeated_exposures": repeated_exposures,
        "repeated_overlap_groups": repeated_overlap_groups,
        "questions": portfolio_exposure_questions(repeated_exposures, repeated_overlap_groups),
    }


def compact_exposure_groups(value: object, portfolio_items: List[object], group_type: str) -> List[Dict[str, object]]:
    groups = value if isinstance(value, list) else []
    rows = []
    for group in groups[:5]:
        if not isinstance(group, dict) or not group.get("group"):
            continue
        group_name = str(group.get("group"))
        holdings = holdings_for_exposure_group(group_name, portfolio_items, group_type)
        rows.append(
            {
                "group": group_name,
                "holding_count": int_value(group.get("holding_count"), len(holdings)),
                "holdings": holdings[:6],
                "commands": [command for holding in holdings[:3] for command in portfolio_item_commands(holding.get("symbol"))[:1]],
            }
        )
    return rows


def holdings_for_exposure_group(group_name: str, portfolio_items: List[object], group_type: str) -> List[Dict[str, object]]:
    holdings = []
    for item in portfolio_items:
        if not isinstance(item, dict):
            continue
        if group_type == "exposure" and not item_in_exposure_group(item, group_name):
            continue
        if group_type == "overlap" and group_name not in [str(group) for group in item.get("overlap_groups", []) if group]:
            continue
        holdings.append(
            {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "priority": item.get("priority"),
                "priority_score": item.get("priority_score"),
            }
        )
    holdings.sort(key=lambda row: (-int_value(row.get("priority_score")), str(row.get("symbol") or "")))
    return holdings


def item_in_exposure_group(item: Dict[str, object], group_name: str) -> bool:
    exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        if "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")) == group_name:
            return True
    return False


def portfolio_exposure_summary(
    repeated_exposures: List[Dict[str, object]],
    repeated_overlap_groups: List[Dict[str, object]],
    affected_symbols: List[str],
) -> str:
    if not repeated_exposures and not repeated_overlap_groups:
        return "暂无重复链路或重复主题暴露。"
    parts = []
    if repeated_exposures:
        parts.append("重复链路 %s 组" % len(repeated_exposures))
    if repeated_overlap_groups:
        parts.append("重复主题 %s 组" % len(repeated_overlap_groups))
    parts.append("涉及持仓 %s 个" % len(affected_symbols))
    return "，".join(parts) + "。"


def portfolio_exposure_questions(
    repeated_exposures: List[Dict[str, object]],
    repeated_overlap_groups: List[Dict[str, object]],
) -> List[str]:
    questions = []
    for group in repeated_exposures[:2]:
        questions.append("%s 链路里的持仓是否受同一热点和同一风险驱动？" % group.get("group"))
    for group in repeated_overlap_groups[:2]:
        questions.append("%s 主题里的持仓是否本质上是同一叙事暴露？" % group.get("group"))
    return questions


def empty_validation_summary() -> Dict[str, object]:
    return {
        "ok": None,
        "warning_count": 0,
        "error_count": 0,
        "warning_codes": [],
        "error_codes": [],
        "warnings": [],
        "errors": [],
    }


def compact_validation_summary(validation: Dict[str, object], summary: Dict[str, object]) -> Dict[str, object]:
    warnings = compact_issues(validation.get("warnings", []))
    errors = compact_issues(validation.get("errors", []))
    return {
        "ok": validation.get("ok"),
        "warning_count": int_value(summary.get("warning_count"), len(warnings)),
        "error_count": int_value(summary.get("error_count"), len(errors)),
        "warning_codes": [issue_identifier(issue) for issue in warnings],
        "error_codes": [issue_identifier(issue) for issue in errors],
        "warnings": warnings,
        "errors": errors,
    }


def compact_issues(value: object, limit: int = 8) -> List[Dict[str, object]]:
    issues = value if isinstance(value, list) else []
    compact: List[Dict[str, object]] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        detail = item.get("detail", {}) if isinstance(item.get("detail"), dict) else {}
        issue: Dict[str, object] = {
            "code": item.get("code"),
            "message": item.get("message"),
        }
        for key in ("symbol", "path", "field", "index"):
            if detail.get(key) is not None:
                issue[key] = detail.get(key)
        missing = detail.get("missing")
        if isinstance(missing, list):
            issue["missing"] = [str(field) for field in missing]
        elif missing:
            issue["missing"] = [str(missing)]
        compact.append(issue)
        if len(compact) >= limit:
            break
    return compact


def issue_identifier(issue: Dict[str, object]) -> str:
    code = str(issue.get("code") or "UNKNOWN")
    symbol = issue.get("symbol")
    if symbol:
        return "%s:%s" % (code, symbol)
    path = issue.get("path")
    if path:
        return "%s:%s" % (code, path)
    return code


def compact_issue_evidence(value: object, limit: int = 3) -> List[str]:
    issues = value if isinstance(value, list) else []
    evidence = []
    for issue in issues[:limit]:
        if not isinstance(issue, dict):
            continue
        text = issue_identifier(issue)
        missing = issue.get("missing")
        if isinstance(missing, list) and missing:
            text = "%s | 缺字段 %s" % (text, ",".join(str(field) for field in missing[:4]))
        elif issue.get("message"):
            text = "%s | %s" % (text, trim_text(issue.get("message"), 80))
        evidence.append(text)
    return evidence


def compact_security_evidence(items: List[object]) -> List[str]:
    evidence = []
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence.append(
            "%s %s | %s | 复核分 %s"
            % (item.get("symbol"), item.get("name"), item.get("priority"), item.get("priority_score"))
        )
    return evidence


def compact_watchlist_evidence(items: List[object]) -> List[str]:
    evidence = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mark = "持仓" if item.get("is_holding") else "观察"
        evidence.append(
            "%s %s | %s | %s/%s | 涨幅 %s | 热点 %s"
            % (
                item.get("symbol"),
                item.get("name"),
                mark,
                item.get("layer"),
                item.get("sub_sector"),
                render_number(item.get("change_pct")),
                render_number(item.get("hotspot_score")),
            )
        )
    return evidence


def compact_scan_evidence(groups: List[object], candidates: List[object]) -> List[str]:
    evidence = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        evidence.append(
            "%s%s | 扫描分 %s | 活跃 %s/%s"
            % (
                scan_group_type_text(group.get("group_type")),
                group.get("name"),
                render_number(group.get("score")),
                group.get("active_member_count", 0),
                group.get("member_count", 0),
            )
        )
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        evidence.append(
            "%s %s | %s | 覆盖 %s"
            % (
                candidate.get("symbol"),
                candidate.get("name"),
                render_number(candidate.get("review_score")),
                candidate.get("coverage_state"),
            )
        )
    return evidence[:5]


def scan_group_type_text(value: object) -> str:
    labels = {
        "industry": "行业",
        "concept": "概念",
        "index": "指数",
        "chain": "链路",
        "unknown": "分组",
    }
    return labels.get(str(value), str(value or "分组"))


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


def first_symbol_from_items(items: List[object]) -> Optional[str]:
    for item in items:
        if isinstance(item, dict) and item.get("symbol"):
            return str(item.get("symbol"))
    return None


def watchlist_item_commands(symbol: object, is_holding: bool = False) -> List[str]:
    if not symbol:
        return ["market-intel watchlist --runtime --text"]
    if is_holding:
        return [
            "market-intel portfolio explain %s --runtime --text" % symbol,
            "market-intel pool explain %s --runtime --text" % symbol,
        ]
    return [
        "market-intel pool explain %s --runtime --text" % symbol,
        "market-intel watchlist --runtime --text",
    ]


def scan_item_commands(symbol: object) -> List[str]:
    if not symbol:
        return ["market-intel scan --runtime --text"]
    return [
        "market-intel pool explain %s --runtime --text" % symbol,
        "market-intel scan --runtime --text",
    ]


def portfolio_item_commands(symbol: object) -> List[str]:
    if not symbol:
        return ["market-intel portfolio review --runtime --text"]
    return [
        "market-intel portfolio explain %s --runtime --text" % symbol,
        "market-intel pool explain %s --runtime --text" % symbol,
    ]


def build_security_review_queue(
    daily: Dict[str, object],
    current_change: Dict[str, object],
    market_scan: Optional[Dict[str, object]] = None,
    limit: int = 8,
) -> List[Dict[str, object]]:
    if not daily.get("available"):
        return []
    queue: Dict[str, Dict[str, object]] = {}
    market_scan = market_scan if isinstance(market_scan, dict) else {}
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    for issue in validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []:
        if isinstance(issue, dict) and issue.get("symbol"):
            symbol = issue.get("symbol")
            upsert_security_queue_item(
                queue,
                str(symbol),
                None,
                100,
                "data_quality",
                issue_identifier(issue),
                [],
                [],
                issue_commands(issue),
            )

    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    portfolio_items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
    for item in portfolio_items:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        score = 70 + min(40, int_value(item.get("priority_score")))
        if item.get("priority") == "high_review":
            score += 30
        upsert_security_queue_item(
            queue,
            str(item.get("symbol")),
            item.get("name"),
            score,
            "portfolio_review",
            "%s | 复核分 %s" % (item.get("priority"), render_number(item.get("priority_score"))),
            item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else [],
            item.get("review_points", []) if isinstance(item.get("review_points"), list) else [],
            item.get("commands", []) if isinstance(item.get("commands"), list) else portfolio_item_commands(item.get("symbol")),
            context=portfolio_context(item),
        )

    watchlist = daily.get("watchlist", {}) if isinstance(daily.get("watchlist"), dict) else {}
    watchlist_items = watchlist.get("top_items", []) if isinstance(watchlist.get("top_items"), list) else []
    for item in watchlist_items:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        score = 45 + int_value(item.get("hotspot_score"))
        if item.get("is_holding"):
            score += 25
        upsert_security_queue_item(
            queue,
            str(item.get("symbol")),
            item.get("name"),
            score,
            "watchlist",
            "%s/%s | 涨幅 %s | 热点 %s" % (
                item.get("layer"),
                item.get("sub_sector"),
                render_number(item.get("change_pct")),
                render_number(item.get("hotspot_score")),
            ),
            item.get("risks", []) if isinstance(item.get("risks"), list) else [],
            [item.get("focus")] if item.get("focus") else [],
            item.get("commands", []) if isinstance(item.get("commands"), list) else watchlist_item_commands(item.get("symbol"), bool(item.get("is_holding"))),
            context=watchlist_context(item),
        )

    scan_candidates = market_scan.get("candidate_securities", []) if isinstance(market_scan.get("candidate_securities"), list) else []
    for item in scan_candidates:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        score = 40 + int_value(item.get("review_score"))
        if item.get("is_holding"):
            score += 20
        upsert_security_queue_item(
            queue,
            str(item.get("symbol")),
            item.get("name"),
            score,
            "market_scan",
            "%s | scan %s | 覆盖 %s" % (
                item.get("priority"),
                render_number(item.get("review_score")),
                item.get("coverage_state"),
            ),
            item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else [],
            item.get("checklist", []) if isinstance(item.get("checklist"), list) else [],
            item.get("commands", []) if isinstance(item.get("commands"), list) else scan_item_commands(item.get("symbol")),
            context=scan_context(item),
        )

    add_current_change_symbols(queue, current_change)
    rows = list(queue.values())
    rows.sort(key=lambda row: (-int_value(row.get("priority_score")), str(row.get("symbol") or "")))
    for rank, item in enumerate(rows[:limit], start=1):
        item["rank"] = rank
        item["reasons"] = dedupe(item.get("reasons", []) if isinstance(item.get("reasons"), list) else [])[:5]
        item["risk_flags"] = dedupe(item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else [])[:8]
        item["review_points"] = dedupe(item.get("review_points", []) if isinstance(item.get("review_points"), list) else [])[:5]
        item["commands"] = dedupe(item.get("commands", []) if isinstance(item.get("commands"), list) else [])[:4]
        item["sources"] = dedupe(item.get("sources", []) if isinstance(item.get("sources"), list) else [])[:5]
    return rows[:limit]


def upsert_security_queue_item(
    queue: Dict[str, Dict[str, object]],
    symbol: str,
    name: object,
    score: int,
    source: str,
    reason: str,
    risk_flags: List[object],
    review_points: List[object],
    commands: List[object],
    context: Optional[Dict[str, object]] = None,
) -> None:
    item = queue.setdefault(
        symbol,
        {
            "rank": None,
            "symbol": symbol,
            "name": name,
            "priority_score": 0,
            "sources": [],
            "reasons": [],
            "risk_flags": [],
            "review_points": [],
            "context": {},
            "commands": [],
        },
    )
    if name and not item.get("name"):
        item["name"] = name
    item["priority_score"] = max(int_value(item.get("priority_score")), int_value(score))
    item["sources"].append(source)
    item["reasons"].append(reason)
    item["risk_flags"].extend(str(flag) for flag in risk_flags if flag)
    item["review_points"].extend(str(point) for point in review_points if point)
    item["commands"].extend(str(command) for command in commands if command)
    if context:
        item_context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
        for key, value in context.items():
            if value is not None and item_context.get(key) is None:
                item_context[key] = value
        item["context"] = item_context


def issue_commands(issue: Dict[str, object]) -> List[str]:
    symbol = issue.get("symbol")
    if not symbol:
        return ["market-intel validate runtime --json"]
    if issue.get("code") == "QUOTE_NOT_IN_HOLDINGS":
        return watchlist_item_commands(symbol, False)
    return portfolio_item_commands(symbol)


def portfolio_context(item: Dict[str, object]) -> Dict[str, object]:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
    return {
        "is_holding": True,
        "priority": item.get("priority"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": item.get("coverage_state_reasons"),
        "research_status": compact_research_status(item.get("research_status", {})),
        "change_pct": quote.get("change_pct") if quote else None,
        "amount_ratio": quote.get("amount_ratio") if quote else None,
        "intraday_fade_pct": quote.get("intraday_fade_pct") if quote else None,
        "layer": hotspot.get("layer") if hotspot else None,
        "sub_sector": hotspot.get("sub_sector") if hotspot else None,
        "hotspot_score": hotspot.get("score") if hotspot else None,
    }


def watchlist_context(item: Dict[str, object]) -> Dict[str, object]:
    return {
        "is_holding": bool(item.get("is_holding")),
        "focus": item.get("focus"),
        "change_pct": item.get("change_pct"),
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "hotspot_score": item.get("hotspot_score"),
    }


def scan_context(item: Dict[str, object]) -> Dict[str, object]:
    contexts = item.get("sector_contexts", []) if isinstance(item.get("sector_contexts"), list) else []
    primary_context = contexts[0] if contexts and isinstance(contexts[0], dict) else {}
    return {
        "is_holding": bool(item.get("is_holding")),
        "priority": item.get("priority"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": item.get("coverage_state_reasons"),
        "research_status": compact_research_status(item.get("research_status", {})),
        "change_pct": item.get("change_pct"),
        "amount_ratio": item.get("amount_ratio"),
        "intraday_fade_pct": item.get("intraday_fade_pct"),
        "scan_group_type": primary_context.get("group_type"),
        "scan_group": primary_context.get("name"),
        "scan_score": primary_context.get("score"),
    }


def add_current_change_symbols(queue: Dict[str, Dict[str, object]], current_change: Dict[str, object]) -> None:
    if not current_change.get("available"):
        return
    watchlist = current_change.get("watchlist", {}) if isinstance(current_change.get("watchlist"), dict) else {}
    portfolio = current_change.get("portfolio_review", {}) if isinstance(current_change.get("portfolio_review"), dict) else {}
    for symbol in watchlist.get("added_symbols", []) if isinstance(watchlist.get("added_symbols"), list) else []:
        upsert_security_queue_item(
            queue,
            str(symbol),
            None,
            80,
            "current_change",
            "当前观察项新增",
            [],
            ["当前 runtime 相比最近留档新增观察项。"],
            watchlist_item_commands(symbol),
        )
    for symbol in watchlist.get("changed_symbols", []) if isinstance(watchlist.get("changed_symbols"), list) else []:
        upsert_security_queue_item(
            queue,
            str(symbol),
            None,
            70,
            "current_change",
            "当前观察项变化",
            [],
            ["当前 runtime 相比最近留档观察项发生变化。"],
            watchlist_item_commands(symbol),
        )
    for symbol in portfolio.get("changed_symbols", []) if isinstance(portfolio.get("changed_symbols"), list) else []:
        upsert_security_queue_item(
            queue,
            str(symbol),
            None,
            90,
            "current_change",
            "当前持仓复核变化",
            [],
            ["当前 runtime 相比最近留档持仓复核发生变化。"],
            portfolio_item_commands(symbol),
        )


def build_command_queue(
    commands: List[str],
    focus: List[Dict[str, object]],
    checklist: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    focus_index = command_focus_index(focus, checklist)
    return [command_queue_item(command, index + 1, focus_index.get(command, [])) for index, command in enumerate(commands)]


def command_focus_index(focus: List[Dict[str, object]], checklist: List[Dict[str, object]]) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for item in focus + checklist:
        if not isinstance(item, dict):
            continue
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        title = item.get("title")
        for command in commands:
            if command and title:
                values = index.setdefault(str(command), [])
                if str(title) not in values:
                    values.append(str(title))
    return index


def command_queue_item(command: str, rank: int, related_focus: List[str]) -> Dict[str, object]:
    contract = command_execution_contract(command)
    return {
        "rank": rank,
        "command": command,
        "json_command": json_variant(command),
        "mutates_state": contract["state_effect"] != "read_only",
        "state_effect": contract["state_effect"],
        "reason": contract["purpose"],
        "purpose": contract["purpose"],
        "read_fields": contract["read_fields"],
        "input_context": contract["input_context"],
        "output_use": contract["output_use"],
        "done_when": contract["done_when"],
        "related_focus": related_focus[:4],
    }


def json_variant(command: str) -> str:
    if " --json" in command:
        return command
    if "journal note" in command:
        return "%s --json" % command
    if " --text" in command:
        return command.replace(" --text", " --json")
    return "%s --json" % command


def command_mutates_state(command: str) -> bool:
    return command_state_effect(command) != "read_only"


def command_execution_contract(command: str) -> Dict[str, object]:
    read_fields, purpose = command_read_contract(command)
    return {
        "read_fields": read_fields,
        "purpose": purpose,
        "input_context": command_input_context(command),
        "output_use": command_output_use(command),
        "done_when": command_done_when(command),
        "state_effect": command_state_effect(command),
    }


def command_state_effect(command: str) -> str:
    padded = " %s " % command
    if " journal save " in padded or " journal note " in padded:
        return "writes_journal"
    if " import quotes " in padded or " import holdings " in padded or " init runtime" in command:
        return "writes_runtime"
    return "read_only"


def command_input_context(command: str) -> List[str]:
    if "status runtime" in command or "validate runtime" in command:
        return ["runtime_quotes", "runtime_holdings", "pool"]
    if "agent briefing" in command:
        return ["runtime_daily", "journal_timeline", "latest_archive_compare"]
    if "pool coverage" in command:
        return ["pool", "runtime_holdings", "all_a_universe", "research_notes"]
    if "pool quality" in command:
        return ["pool", "data_quality_flag", "pool_csv_rows"]
    if "scan" in command:
        return ["runtime_quotes", "optional_runtime_holdings", "pool", "all_a_universe"]
    if "daily" in command:
        return ["runtime_quotes", "runtime_holdings", "pool"]
    if "portfolio review" in command:
        return ["runtime_holdings", "runtime_quotes", "pool"]
    if "portfolio explain" in command:
        return ["symbol", "runtime_holdings", "runtime_quotes", "pool"]
    if "pool explain" in command:
        return ["symbol", "pool", "optional_runtime_quotes"]
    if "watchlist" in command:
        return ["runtime_quotes", "runtime_holdings", "pool"]
    if "journal latest" in command or "journal timeline" in command or "journal compare" in command:
        return ["journal_entries"]
    if "journal save" in command:
        return ["runtime_daily", "journal_entries"]
    if "journal note" in command:
        return ["journal_entry", "review_note_text"]
    if "import schema" in command:
        return ["csv_source_planning"]
    return ["current_context"]


def command_output_use(command: str) -> str:
    if "status runtime" in command:
        return "判断今天是否能生成日报，以及是否需要先修数据。"
    if "validate runtime" in command:
        return "把错误和告警转成数据质量复核项。"
    if "agent briefing" in command:
        return "作为当天复盘的主工作台和后续命令来源。"
    if "pool coverage" in command:
        return "先确认全 A/复盘池覆盖边界、持仓覆盖状态和证据缺口。"
    if "pool quality" in command:
        return "聚焦一个数据质量标记，读取样本、建议动作和完成标准。"
    if "scan" in command:
        return "读取全市场板块强弱、候选复盘标的、覆盖状态和证据缺口。"
    if "daily" in command:
        return "形成当日完整市场结构、观察项和持仓复核底稿。"
    if "portfolio review" in command:
        return "定位高优先级持仓、重复链路和重复主题。"
    if "portfolio explain" in command:
        return "展开单个持仓的上下文、相关持仓和复核问题。"
    if "pool explain" in command:
        return "确认池内标的角色、链路和运行时上下文。"
    if "watchlist" in command:
        return "确认盘中观察项和持仓观察是否需要进入复核队列。"
    if "journal latest" in command:
        return "读取最近一次留档和用户复盘笔记。"
    if "journal compare" in command:
        return "识别最近两份留档之间的热点、持仓和风险变化。"
    if "journal timeline" in command:
        return "查看多日留档的连续变化和最近笔记。"
    if "journal save" in command:
        return "保存当前日报，供后续 timeline 和 compare 使用。"
    if "journal note" in command:
        return "把复核结论追加到最近日报留档。"
    if "import schema" in command:
        return "指导用户准备行情和持仓 CSV 字段。"
    return "继续推进复盘流程。"


def command_done_when(command: str) -> str:
    if "status runtime" in command:
        return "已确认 data.readiness.state，并记录 blocked/degraded/ready 的原因。"
    if "validate runtime" in command:
        return "errors 已清空，或每个 warning/error 都有对应处理说明。"
    if "agent briefing" in command:
        return "已读取 review_focus、review_checklist、current_change 和 command_queue。"
    if "pool coverage" in command:
        return "已记录 coverage status、universe sector_profile、holdings_coverage、gaps 和 next_actions。"
    if "pool quality" in command:
        return "已记录该 flag 的 affected_count、samples、suggested_action 和 done_when。"
    if "scan" in command:
        return "已记录 sector_groups、candidate_securities、coverage_state 和 next_actions。"
    if "daily" in command:
        return "已记录 summary、validation、portfolio_review 和 next_questions。"
    if "portfolio review" in command:
        return "已记录高优先级持仓、重复链路/主题和待复核问题。"
    if "portfolio explain" in command:
        return "已记录该持仓的 risk_flags、related 和 questions。"
    if "pool explain" in command:
        return "已确认该标的角色、链路、runtime 上下文和待验证问题。"
    if "watchlist" in command:
        return "已记录观察项中的持仓标记、风险标签和后续单票命令。"
    if "journal latest" in command:
        return "已读取最近留档、最新用户笔记和 next_commands。"
    if "journal compare" in command:
        return "已记录新增、减少和变化项，并提炼出需要复核的变化。"
    if "journal timeline" in command:
        return "已读取多日 points、transitions 和最近笔记。"
    if "journal save" in command:
        return "data.saved 为 true，且 entry.id 已可用于后续时间线和对比。"
    if "journal note" in command:
        return "data.saved 为 true，且 note.id 已写入对应日报。"
    if "import schema" in command:
        return "已确认行情 CSV 与持仓 CSV 的必填字段。"
    return "已读取 ok、errors、warnings 和 data。"


def command_read_contract(command: str) -> tuple:
    if "status runtime" in command:
        return (
            ["data.readiness", "data.validation.summary", "data.freshness"],
            "确认 runtime 是否阻塞、降级或行情过旧。",
        )
    if "validate runtime" in command:
        return (
            ["data.validation_warnings", "errors", "warnings"],
            "定位具体数据问题。",
        )
    if "agent briefing" in command:
        return (
            ["data.review_focus", "data.review_checklist", "data.current_change", "data.command_queue"],
            "读取 agent 可接力的复盘入口。",
        )
    if "pool coverage" in command:
        return (
            ["data.status", "data.universe.sector_profile", "data.holdings_coverage", "data.gaps", "data.next_actions"],
            "确认覆盖边界、持仓覆盖和证据缺口，再进入市场扫描。",
        )
    if "pool quality" in command:
        return (
            ["data.flag", "data.affected_count", "data.samples", "data.suggested_action", "data.done_when"],
            "读取单个数据质量标记的清理样本和完成标准。",
        )
    if "scan" in command:
        return (
            ["data.sector_groups", "data.candidate_securities", "data.coverage_context"],
            "读取全市场板块扫描和候选复盘标的。",
        )
    if "daily" in command:
        return (
            ["data.summary", "data.brief.top_hotspots", "data.portfolio_review", "data.validation"],
            "查看完整日报结构。",
        )
    if "portfolio review" in command:
        return (
            ["data.items", "data.repeated_exposures", "data.repeated_overlap_groups", "data.questions"],
            "复核持仓上下文和风险标签。",
        )
    if "portfolio explain" in command:
        return (
            ["data.item", "data.related", "data.questions", "data.next_commands"],
            "深入单个持仓的行情、热点和链路暴露。",
        )
    if "pool explain" in command:
        return (
            ["data.facts", "data.exposures", "data.runtime_context", "data.questions"],
            "确认单个标的在池子里的角色和上下文。",
        )
    if "watchlist" in command:
        return (
            ["data.items", "data.risk_flags", "data.questions"],
            "查看观察项、热点领涨和持仓观察。",
        )
    if "journal latest" in command:
        return (
            ["data.entry", "data.payload.data.summary", "data.next_commands"],
            "读取最近日报留档。",
        )
    if "journal compare" in command:
        return (
            ["data.changes.risk_flags", "data.changes.watchlist", "data.changes.portfolio_review", "data.changes.hotspots"],
            "查看最近两份留档的变化。",
        )
    if "journal timeline" in command:
        return (
            ["data.points", "data.transitions", "data.next_commands"],
            "查看多日留档时间线。",
        )
    if "journal save" in command:
        return (
            ["data.saved", "data.entry", "data.next_commands"],
            "保存当前日报以形成历史对比。",
        )
    if "journal note" in command:
        return (
            ["data.saved", "data.entry.id", "data.note"],
            "确认复盘笔记已写入日报留档。",
        )
    if "import schema" in command:
        return (
            ["data.quotes", "data.holdings", "data.next_commands"],
            "查看 CSV 导入字段要求。",
        )
    return (["ok", "data", "errors", "warnings"], "继续执行下一步。")


def int_value(value: object, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def render_number(value: object) -> str:
    if value is None:
        return "无"
    return str(value)


def trim_text(value: object, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def dedupe(values: List[object]) -> List[str]:
    result = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def agent_state(readiness: Dict[str, object], entries: List[object]) -> str:
    readiness_state = str(readiness.get("state") or "blocked")
    if readiness_state == "blocked":
        return "blocked"
    if readiness_state == "degraded":
        return "degraded"
    if len(entries) >= 2:
        return "ready_with_compare"
    if len(entries) == 1:
        return "ready_needs_second_archive"
    return "ready_needs_archive"


def agent_summary(state: str, readiness: Dict[str, object], entries: List[object]) -> str:
    if state == "blocked":
        return "runtime 暂不可生成日报，先处理数据文件或校验错误。"
    if state == "degraded":
        return "runtime 可生成日报，但需要复核数据告警。"
    if state == "ready_with_compare":
        return "runtime 可生成日报，且已有至少两份留档可做历史对比。"
    if state == "ready_needs_second_archive":
        return "runtime 可生成日报；已有一份留档，再保存一份即可对比。"
    return "runtime 可生成日报；尚无日报留档，建议先保存一份。"


def build_steps(
    readiness: Dict[str, object],
    freshness: Dict[str, object],
    universe: Dict[str, object],
    entries: List[object],
) -> List[Dict[str, object]]:
    readiness_state = str(readiness.get("state") or "blocked")
    can_run_daily = bool(readiness.get("can_run_daily"))
    steps: List[Dict[str, object]] = []

    if readiness_state == "blocked":
        return [
            step(10, "inspect_runtime_status", "market-intel status runtime --json", True, "确认 runtime 阻塞原因。"),
            step(20, "init_runtime", "market-intel init runtime --json", True, "缺少 runtime 文件时生成模板。"),
            step(30, "inspect_import_schema", "market-intel import schema --json", True, "查看 CSV 导入字段合同。"),
            step(40, "load_quotes", "market-intel import quotes <quotes.csv> --runtime --json", False, "导入当日行情。"),
            step(50, "load_holdings", "market-intel import holdings <holdings.csv> --runtime --json", False, "导入当前持仓。"),
            step(60, "load_universe", "market-intel import universe <a_share_universe.csv> --runtime --json", False, "导入 A 股基础清单。"),
        ]

    if freshness.get("is_stale"):
        steps.append(step(10, "refresh_quotes", "market-intel import quotes <quotes.csv> --runtime --json", False, "行情日期过旧或缺失。"))
    if readiness_state == "degraded":
        steps.append(step(20, "review_runtime_warnings", "market-intel validate runtime --json", True, "复核数据告警。"))
    if universe.get("required") and universe.get("state") in {"missing", "empty", "degraded"}:
        steps.append(
            step(
                15,
                "import_universe",
                "market-intel import universe examples/a_share_universe.csv.example --runtime --json",
                True,
                "补齐 all-a 的 A 股基础清单，减少种子覆盖偏差。",
            )
        )

    if can_run_daily:
        archive_reason = archive_step_reason(len(entries))
        steps.extend(
            [
                step(30, "run_agent_briefing", "market-intel agent briefing --text", True, "生成日常复盘工作台。"),
                step(40, "run_agent_briefing_json", "market-intel agent briefing --json", True, "给 agent 读取复盘焦点和下一步命令。"),
                step(45, "run_market_scan", "market-intel scan --runtime --text", True, "先看全市场板块强弱和候选复盘标的。"),
                step(50, "run_market_scan_json", "market-intel scan --runtime --json", True, "给 agent 读取 sector_groups 和 candidate_securities。"),
                step(60, "run_daily_json", "market-intel daily --runtime --json", True, "生成完整结构化日报。"),
                step(70, "run_daily_text", "market-intel daily --runtime --text", True, "生成完整可读复盘。"),
                step(80, "save_daily_archive", "market-intel journal save --runtime --json", True, archive_reason),
                step(90, "list_journal", "market-intel journal list --json", True, "查看留档历史。"),
            ]
        )
        if len(entries) >= 2:
            steps.append(step(100, "compare_latest_journals", "market-intel journal compare --json", True, "对比最近两份日报留档。"))

    return sorted(steps, key=lambda item: int(item.get("priority", 999)))


def archive_step_reason(entry_count: int) -> str:
    if entry_count >= 2:
        return "保存本次日报，形成新的对比基准。"
    if entry_count == 1:
        return "保存本次日报，之后即可对比最近两份留档。"
    return "保存第一份完整日报留档。"


def step(priority: int, step_id: str, command: str, runnable: bool, reason: str) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": step_id,
        "command": command,
        "runnable": runnable,
        "reason": reason,
    }


def execution_summary(steps: List[Dict[str, object]]) -> Dict[str, object]:
    runnable_steps = [item for item in steps if item.get("runnable")]
    manual_steps = [item for item in steps if not item.get("runnable")]
    next_step = runnable_steps[0] if runnable_steps else None
    return {
        "next_runnable_step": next_step,
        "next_runnable_command": next_step.get("command") if isinstance(next_step, dict) else None,
        "runnable_step_count": len(runnable_steps),
        "manual_step_count": len(manual_steps),
    }


def compare_pair(entries: List[object]) -> Optional[Dict[str, object]]:
    if len(entries) < 2:
        return None
    current = entries[0] if isinstance(entries[0], dict) else {}
    base = entries[1] if isinstance(entries[1], dict) else {}
    return {
        "base_id": base.get("id"),
        "current_id": current.get("id"),
        "command": "market-intel journal compare --base %s --current %s --json" % (base.get("id"), current.get("id")),
    }


def agent_contract(max_quote_age_days: int) -> Dict[str, object]:
    return {
        "success": "ok=true 表示计划生成成功；data.state 决定下一步。",
        "state_values": ["blocked", "degraded", "ready_needs_archive", "ready_needs_second_archive", "ready_with_compare"],
        "stable_fields": [
            "data.state",
            "data.runtime.readiness",
            "data.runtime.universe",
            "data.runtime.validation",
            "data.journal.entry_count",
            "data.journal.can_compare",
            "data.execution.next_runnable_command",
            "data.steps",
        ],
        "step_order": "按 priority 升序执行；runnable=false 表示需要人工提供文件或修正数据。",
        "freshness": "max_quote_age_days=%s" % max_quote_age_days,
        "boundary": "这是市场情报工作流计划，不生成交易指令、目标价或仓位建议。",
    }
