import shlex
from typing import Dict, List


def build_focus_report(daily: Dict[str, object], limit: int = 5, step_limit: int = 5) -> Dict[str, object]:
    validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
    brief = daily.get("brief", {}) if isinstance(daily.get("brief"), dict) else {}
    market_map = daily.get("map", {}) if isinstance(daily.get("map"), dict) else {}
    portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
    risk_register = daily.get("risk_register", []) if isinstance(daily.get("risk_register"), list) else []
    review_path = daily.get("review_path", []) if isinstance(daily.get("review_path"), list) else []
    security_queue = daily.get("security_review_queue", []) if isinstance(daily.get("security_review_queue"), list) else []
    command_queue = daily.get("command_queue", []) if isinstance(daily.get("command_queue"), list) else []
    coverage = daily.get("coverage_context", {}) if isinstance(daily.get("coverage_context"), dict) else {}

    priority_securities = [focus_security(item) for item in security_queue[:limit] if isinstance(item, dict)]
    next_steps = [focus_step(item) for item in review_path[:step_limit] if isinstance(item, dict)]

    return {
        "headline": focus_headline(brief, portfolio, validation, risk_register),
        "trade_date": daily.get("latest_trade_date"),
        "mode": daily.get("mode"),
        "pool": daily.get("pool"),
        "data_status": focus_data_status(daily, validation),
        "coverage_context": focus_coverage_context(coverage),
        "market_focus": focus_market(brief, market_map),
        "portfolio_pressure": focus_portfolio_pressure(portfolio, risk_register),
        "priority_securities": priority_securities,
        "next_steps": next_steps,
        "first_runnable_command": first_runnable_command(command_queue, next_steps),
        "agent_contract": focus_contract(),
        "guardrails": [
            "这是复盘聚焦，不是交易指令。",
            "优先级用于安排核对顺序，不代表买卖方向、目标价或仓位建议。",
        ],
    }


def focus_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.headline",
            "data.data_status",
            "data.coverage_context",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.next_actions",
            "data.market_focus",
            "data.portfolio_pressure",
            "data.priority_securities",
            "data.priority_securities[].symbol",
            "data.priority_securities[].why_now",
            "data.priority_securities[].checklist",
            "data.priority_securities[].commands",
            "data.priority_securities[].note_command",
            "data.priority_securities[].note_prerequisite",
            "data.priority_securities[].journal_ready",
            "data.priority_securities[].done_when",
            "data.next_steps",
            "data.next_steps[].command",
            "data.first_runnable_command",
            "data.guardrails",
        ],
        "read_order": [
            "先读 data.data_status，确认数据是否阻塞。",
            "再读 data.market_focus 和 data.portfolio_pressure，确认今天主要结构。",
            "再读 data.priority_securities，按队列核对重点标的。",
            "最后读 data.next_steps 和 data.first_runnable_command 接下一条命令。",
        ],
        "boundary": "不生成交易动作、目标价或仓位建议。",
    }


def focus_headline(
    brief: Dict[str, object],
    portfolio: Dict[str, object],
    validation: Dict[str, object],
    risk_register: List[object],
) -> str:
    strongest = first_hotspot(brief)
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    portfolio_items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    high_count = sum(1 for item in portfolio_items if isinstance(item, dict) and item.get("priority") == "high_review")
    warning_count = int_number(validation_summary.get("warning_count"))
    risk_count = len(risk_register)
    if strongest:
        chain = "%s / %s" % (strongest.get("layer"), strongest.get("sub_sector"))
        return "%s 是当前最强链路；重点复核 %s 个持仓；数据告警 %s 个；风险登记 %s 项。" % (
            chain,
            high_count,
            warning_count,
            risk_count,
        )
    return "暂无强链路；重点复核 %s 个持仓；数据告警 %s 个；风险登记 %s 项。" % (
        high_count,
        warning_count,
        risk_count,
    )


def focus_data_status(daily: Dict[str, object], validation: Dict[str, object]) -> Dict[str, object]:
    summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    state = "blocked" if errors else "warning" if warnings else "ok"
    return {
        "state": state,
        "quote_count": int_number(summary.get("quote_count")),
        "holding_count": int_number(summary.get("holding_count")),
        "error_count": int_number(summary.get("error_count")),
        "warning_count": int_number(summary.get("warning_count")),
        "top_errors": compact_issues(errors),
        "top_warnings": compact_issues(warnings),
        "command": data_status_command(daily, state),
    }


def focus_coverage_context(coverage: Dict[str, object]) -> Dict[str, object]:
    if not coverage.get("available"):
        return {
            "available": False,
            "summary": "暂无复盘池覆盖上下文。",
            "universe": {"available": False, "sector_profile": {}},
            "gap_count": 0,
            "top_gaps": [],
            "next_actions": [],
        }
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    gaps = coverage.get("gaps", []) if isinstance(coverage.get("gaps"), list) else []
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
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
            "sector_profile": {
                "industry_coverage_ratio": profile.get("industry_coverage_ratio", 0),
                "concept_coverage_ratio": profile.get("concept_coverage_ratio", 0),
                "index_coverage_ratio": profile.get("index_coverage_ratio", 0),
                "top_industries": list(profile.get("top_industries", []))[:5] if isinstance(profile.get("top_industries"), list) else [],
                "missing_field_counts": profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {},
                "missing_field_samples": list(profile.get("missing_field_samples", []))[:5] if isinstance(profile.get("missing_field_samples"), list) else [],
                "coverage_flags": list(profile.get("coverage_flags", [])) if isinstance(profile.get("coverage_flags"), list) else [],
            },
        },
        "gap_count": len(gaps),
        "top_gaps": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in gaps[:5]
            if isinstance(item, dict)
        ],
        "next_actions": [
            {
                "id": item.get("id"),
                "command": item.get("command"),
                "done_when": item.get("done_when"),
            }
            for item in actions[:5]
            if isinstance(item, dict)
        ],
    }


def focus_market(brief: Dict[str, object], market_map: Dict[str, object]) -> Dict[str, object]:
    strongest = first_hotspot(brief)
    layers = market_map.get("layers", []) if isinstance(market_map.get("layers"), list) else []
    layer_rows = []
    for layer in layers[:5]:
        if not isinstance(layer, dict):
            continue
        layer_rows.append(
            {
                "layer": layer.get("layer"),
                "hotspot_count": layer.get("hotspot_count"),
                "holding_count": layer.get("holding_count"),
                "risk_flags": list(layer.get("risk_flags", []))[:5] if isinstance(layer.get("risk_flags"), list) else [],
            }
        )
    return {
        "strongest_chain": focus_hotspot(strongest) if strongest else None,
        "top_chains": [
            focus_hotspot(item)
            for item in brief.get("top_hotspots", [])[:3]
            if isinstance(item, dict)
        ]
        if isinstance(brief.get("top_hotspots"), list)
        else [],
        "layers": layer_rows,
    }


def focus_hotspot(item: Dict[str, object]) -> Dict[str, object]:
    leaders = item.get("leaders", []) if isinstance(item.get("leaders"), list) else []
    return {
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "score": item.get("score"),
        "active_member_count": item.get("active_member_count"),
        "member_count": item.get("member_count"),
        "leaders": [leader_name(row) for row in leaders[:3] if isinstance(row, dict)],
        "signals": list(item.get("signals", []))[:5] if isinstance(item.get("signals"), list) else [],
        "risks": list(item.get("risks", []))[:5] if isinstance(item.get("risks"), list) else [],
    }


def focus_portfolio_pressure(portfolio: Dict[str, object], risk_register: List[object]) -> Dict[str, object]:
    repeated = portfolio.get("repeated_exposures", []) if isinstance(portfolio.get("repeated_exposures"), list) else []
    overlap = (
        portfolio.get("repeated_overlap_groups", [])
        if isinstance(portfolio.get("repeated_overlap_groups"), list)
        else []
    )
    portfolio_items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    high_risks = [
        risk
        for risk in risk_register
        if isinstance(risk, dict) and risk.get("scope") == "portfolio" and risk.get("severity") == "high"
    ]
    return {
        "summary": portfolio.get("summary"),
        "repeated_exposure_count": len(repeated),
        "repeated_overlap_count": len(overlap),
        "repeated_exposures": compact_groups(repeated, portfolio_items, "exposure"),
        "repeated_overlap_groups": compact_groups(overlap, portfolio_items, "overlap"),
        "high_risk_count": len(high_risks),
        "questions": list(portfolio.get("questions", []))[:3] if isinstance(portfolio.get("questions"), list) else [],
    }


def compact_groups(groups: List[object], portfolio_items: List[object], group_type: str) -> List[Dict[str, object]]:
    rows = []
    for group in groups[:3]:
        if not isinstance(group, dict):
            continue
        group_name = str(group.get("group") or "")
        rows.append(
            {
                "group": group_name,
                "holding_count": group.get("holding_count"),
                "symbols": group_symbols(group_name, portfolio_items, group_type),
            }
        )
    return rows


def group_symbols(group_name: str, portfolio_items: List[object], group_type: str) -> List[str]:
    symbols = []
    for item in portfolio_items:
        if not isinstance(item, dict):
            continue
        if group_type == "exposure" and not item_in_exposure_group(item, group_name):
            continue
        if group_type == "overlap" and group_name not in [str(group) for group in item.get("overlap_groups", []) if group]:
            continue
        symbols.append(symbol_name(item.get("symbol"), item.get("name")))
    return symbols


def item_in_exposure_group(item: Dict[str, object], group_name: str) -> bool:
    exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
    for exposure in exposures:
        if isinstance(exposure, dict) and "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")) == group_name:
            return True
    return False


def focus_security(item: Dict[str, object]) -> Dict[str, object]:
    context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
    risk_flags = list(item.get("risk_flags", []))[:5] if isinstance(item.get("risk_flags"), list) else []
    review_points = list(item.get("review_points", []))[:4] if isinstance(item.get("review_points"), list) else []
    reasons = list(item.get("reasons", []))[:3] if isinstance(item.get("reasons"), list) else []
    note_prerequisite = focus_note_prerequisite(item.get("note_prerequisite", {}))
    note_command = item.get("note_command")
    return {
        "rank": item.get("rank"),
        "symbol": item.get("symbol"),
        "name": item.get("name"),
        "priority_score": item.get("priority_score"),
        "is_holding": bool(context.get("is_holding")),
        "chain": chain_name(context.get("layer"), context.get("sub_sector")),
        "change_pct": context.get("change_pct"),
        "hotspot_score": context.get("hotspot_score"),
        "risk_flags": risk_flags,
        "reasons": reasons,
        "why_now": security_why_now(item, context, risk_flags),
        "checklist": security_checklist(review_points, risk_flags),
        "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
        "note_command": note_command,
        "note_prerequisite": note_prerequisite,
        "journal_ready": security_journal_ready(note_command, note_prerequisite),
        "done_when": security_done_when(item, context),
    }


def focus_step(item: Dict[str, object]) -> Dict[str, object]:
    commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
    return {
        "rank": item.get("rank"),
        "id": item.get("id"),
        "title": item.get("title"),
        "reason": item.get("reason"),
        "runnable": bool(item.get("runnable")),
        "command": commands[0] if commands else None,
        "done_when": item.get("done_when"),
    }


def first_runnable_command(command_queue: List[object], next_steps: List[Dict[str, object]]) -> str:
    for step in next_steps:
        command = str(step.get("command") or "")
        if step.get("runnable") and step.get("id") != "data_quality" and " --text" in command:
            return command
    for step in next_steps:
        command = str(step.get("command") or "")
        if step.get("runnable") and command:
            return command
    for item in command_queue:
        if isinstance(item, dict) and item.get("runnable") and item.get("command"):
            return str(item.get("command"))
    return ""


def data_status_command(daily: Dict[str, object], state: str) -> str:
    if state == "ok":
        return ""
    mode = str(daily.get("mode") or "")
    if mode == "runtime":
        return "market-intel validate runtime --json"
    if mode == "mock":
        return "market-intel daily --mock --json"
    sources = daily.get("sources", {}) if isinstance(daily.get("sources"), dict) else {}
    quotes = sources.get("quotes", {}) if isinstance(sources.get("quotes"), dict) else {}
    holdings = sources.get("holdings", {}) if isinstance(sources.get("holdings"), dict) else {}
    quote_source = quotes.get("source")
    holding_source = holdings.get("source")
    if quote_source and holding_source:
        return "market-intel daily --quotes-file %s --holdings-file %s --json" % (
            shlex.quote(str(quote_source)),
            shlex.quote(str(holding_source)),
        )
    return "market-intel import schema --json"


def focus_note_prerequisite(value: object) -> Dict[str, object]:
    prereq = value if isinstance(value, dict) else {}
    if not prereq:
        return {}
    return {
        "requires_journal_entry": bool(prereq.get("requires_journal_entry")),
        "archive_command": prereq.get("archive_command"),
        "archive_runnable": bool(prereq.get("archive_runnable")),
        "archive_reason": prereq.get("archive_reason"),
    }


def security_journal_ready(note_command: object, note_prerequisite: Dict[str, object]) -> str:
    if not note_command:
        return ""
    if not note_prerequisite.get("requires_journal_entry"):
        return "可直接记录复核笔记。"
    archive_command = note_prerequisite.get("archive_command")
    if note_prerequisite.get("archive_runnable") and archive_command:
        return "先执行 %s 保存日报，再记录复核笔记。" % archive_command
    reason = note_prerequisite.get("archive_reason")
    if reason:
        return "需要先有日报留档；当前保存动作不可直接执行：%s" % reason
    return "需要先有日报留档，再记录复核笔记。"


RISK_CHECKS = {
    "chase_high_risk": "涨幅较高，确认强度来自链路共振还是少数标的拉动。",
    "intraday_fade_risk": "日内回落明显，确认是否只是早盘脉冲。",
    "multi_chain_exposure": "多链路归属，确认是真实业务弹性还是口径过宽。",
    "theme_overlap": "主题重叠，确认是否会放大同涨同跌。",
    "theme_concentration": "组合集中，确认多个持仓是否受同一叙事驱动。",
    "turnover_expansion_watch": "成交放大，确认是否有持续性而不是一次性放量。",
    "single_name_or_thin_resonance": "弱共振，确认是否只是单票异动。",
    "weak_hotspot_score": "热点分偏弱，确认是否需要降低当天解读权重。",
    "holding_missing_quote": "持仓缺行情，先补行情再做复核。",
    "no_hotspot_context": "缺少热点上下文，确认它是否仍属于今天主线。",
    "not_in_pool": "池子未匹配，确认是否应加入池子或标为池外持仓。",
    "holding_watch": "这是持仓观察项，确认今天是否需要展开单票复核。",
    "hotspot_leader_watch": "这是热点领涨观察项，确认是否代表链路共振而非单票拉动。",
    "watch": "这是观察项，确认是否需要后续跟踪。",
    "thin_resonance_verify": "共振偏弱，确认是否只是少数标的驱动。",
}


RISK_REASONS = {
    "chase_high_risk": "涨幅较高",
    "intraday_fade_risk": "日内回落明显",
    "multi_chain_exposure": "多链路暴露",
    "theme_overlap": "主题重叠",
    "theme_concentration": "组合集中",
    "turnover_expansion_watch": "成交放大",
    "single_name_or_thin_resonance": "共振偏弱",
    "weak_hotspot_score": "热点分偏弱",
    "holding_missing_quote": "持仓缺行情",
    "no_hotspot_context": "缺少热点上下文",
    "not_in_pool": "池子未匹配",
}


def security_why_now(item: Dict[str, object], context: Dict[str, object], risk_flags: List[object]) -> str:
    parts = []
    holding_text = "持仓" if context.get("is_holding") else "观察标的"
    parts.append("%s进入优先队列，队列分 %s" % (holding_text, item.get("priority_score")))
    chain = chain_name(context.get("layer"), context.get("sub_sector"))
    if chain:
        parts.append("关联 %s" % chain)
    if context.get("change_pct") is not None:
        parts.append("涨幅 %s%%" % context.get("change_pct"))
    if context.get("hotspot_score") is not None:
        parts.append("热点分 %s" % context.get("hotspot_score"))
    risk_text = [risk_reason(flag) for flag in risk_flags[:3]]
    risk_text = [text for text in risk_text if text]
    if risk_text:
        parts.append("主要风险是%s" % "、".join(risk_text))
    return "；".join(parts) + "。"


def security_checklist(review_points: List[object], risk_flags: List[object]) -> List[str]:
    checks = [normalize_check(point) for point in review_points if point]
    checks.extend(RISK_CHECKS.get(str(flag), "") for flag in risk_flags)
    return dedupe_texts([check for check in checks if check])[:4]


def normalize_check(value: object) -> str:
    text = str(value or "")
    if text in RISK_CHECKS:
        return RISK_CHECKS[text]
    if text.isascii() and "_" in text:
        return ""
    return text


def risk_reason(value: object) -> str:
    text = str(value or "")
    if text in RISK_REASONS:
        return RISK_REASONS[text]
    if text.isascii() and "_" in text:
        return ""
    return text


def security_done_when(item: Dict[str, object], context: Dict[str, object]) -> str:
    symbol = symbol_name(item.get("symbol"), item.get("name"))
    if context.get("is_holding"):
        return "已确认 %s 的行情、热点上下文、链路暴露、主要风险，以及它是否放大组合集中。" % symbol
    return "已确认 %s 是否只是观察项、是否属于当天主线，以及后续是否需要加入持仓复核。" % symbol


def dedupe_texts(values: List[str]) -> List[str]:
    rows = []
    for value in values:
        if value not in rows:
            rows.append(value)
    return rows


def compact_issues(issues: List[object]) -> List[Dict[str, object]]:
    rows = []
    for issue in issues[:5]:
        if not isinstance(issue, dict):
            continue
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        rows.append(
            {
                "code": issue.get("code"),
                "symbol": detail.get("symbol") or issue.get("symbol"),
                "path": detail.get("path"),
                "message": issue.get("message"),
            }
        )
    return rows


def first_hotspot(brief: Dict[str, object]) -> Dict[str, object]:
    rows = brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []
    for row in rows:
        if isinstance(row, dict):
            return row
    return {}


def leader_name(value: Dict[str, object]) -> str:
    return "%s %s(%s%%)" % (value.get("symbol"), value.get("name"), value.get("change_pct"))


def chain_name(layer: object, sub_sector: object) -> str:
    if layer and sub_sector:
        return "%s/%s" % (layer, sub_sector)
    return str(layer or sub_sector or "")


def symbol_name(symbol: object, name: object) -> str:
    if symbol and name:
        return "%s %s" % (symbol, name)
    return str(symbol or name or "")


def int_number(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
