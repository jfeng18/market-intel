from typing import Dict, List

from .brief import build_daily_brief
from .map_view import build_market_map
from .models import Holding, PoolItem, Quote
from .portfolio import build_portfolio_review
from .validation import validate_cross_coverage, validate_holdings_file, validate_quotes_file
from .watchlist import build_watchlist_report


def build_daily_report(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    top: int = 5,
    map_top: int = 2,
) -> Dict[str, object]:
    brief = build_daily_brief(items, quotes, holdings, top=top)
    market_map = build_market_map(items, quotes, holdings, top=map_top)
    watchlist = build_watchlist_report(items, quotes, holdings, top=max(top, 10))
    portfolio_review = build_portfolio_review(items, quotes, holdings, top=max(top, len(holdings)))
    validation = build_data_check(quotes, holdings)
    risks = sorted(
        set(brief.get("risk_flags", []))
        | set(market_map.get("risk_flags", []))
        | set(watchlist.get("risk_flags", []))
        | set(portfolio_review.get("risk_flags", []))
    )

    risk_register = build_risk_register(brief, watchlist, portfolio_review, validation)
    review_tasks = build_review_tasks(brief, market_map, watchlist, portfolio_review, validation)
    security_review_queue = build_daily_security_queue(watchlist, portfolio_review)

    return {
        "summary": build_report_summary(brief, market_map, watchlist, portfolio_review, validation, risks),
        "trade_dates": quote_trade_dates(quotes),
        "latest_trade_date": latest_trade_date(quotes),
        "validation": validation,
        "brief": brief,
        "map": market_map,
        "watchlist": watchlist,
        "portfolio_review": portfolio_review,
        "risk_flags": risks,
        "risk_register": risk_register,
        "review_path": build_review_path(risk_register, review_tasks, security_review_queue),
        "security_risk_profile": build_security_risk_profile(risk_register, security_review_queue),
        "next_questions": build_next_questions(brief, market_map, portfolio_review, validation),
        "review_tasks": review_tasks,
        "security_review_queue": security_review_queue,
        "agent_contract": daily_contract(),
        "guardrails": [
            "这是复盘报告，不是交易指令。",
            "只聚合行情、链路、持仓暴露和风险复核点，不生成交易动作、目标价或仓位建议。",
        ],
    }


def daily_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.summary",
            "data.latest_trade_date",
            "data.validation",
            "data.validation.warnings",
            "data.brief.top_hotspots",
            "data.map.layers",
            "data.watchlist.items",
            "data.portfolio_review.items",
            "data.portfolio_review.repeated_exposures",
            "data.portfolio_review.repeated_overlap_groups",
            "data.portfolio_review.questions",
            "data.coverage_context",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.universe.enrichment_queue",
            "data.coverage_context.next_actions",
            "data.risk_flags",
            "data.risk_register",
            "data.risk_register[].severity",
            "data.risk_register[].affected_symbols",
            "data.risk_register[].commands",
            "data.risk_register[].done_when",
            "data.review_path",
            "data.review_path[].commands",
            "data.review_path[].runnable",
            "data.review_path[].done_when",
            "data.security_risk_profile",
            "data.security_risk_profile[].risk_ids",
            "data.security_risk_profile[].related_risks",
            "data.security_risk_profile[].commands",
            "data.security_risk_profile[].note_command",
            "data.security_risk_profile[].done_when",
            "data.next_questions",
            "data.review_tasks",
            "data.review_tasks[].commands",
            "data.review_tasks[].note_command",
            "data.review_tasks[].note_prerequisite",
            "data.review_tasks[].done_when",
            "data.security_review_queue",
            "data.security_review_queue[].priority_score",
            "data.security_review_queue[].commands",
            "data.security_review_queue[].note_command",
            "data.security_review_queue[].note_prerequisite",
            "data.journal_actions",
            "data.journal_actions[].command",
            "data.command_queue",
            "data.command_queue[].command",
            "data.command_queue[].runnable",
            "data.command_queue[].state_effect",
            "data.command_queue[].requires_prior_command",
            "data.guardrails",
        ],
        "read_order": [
            "先读 data.validation，确认数据告警。",
            "再读 data.brief.top_hotspots 与 data.map.layers，确认市场结构。",
            "再读 data.watchlist.items 与 data.portfolio_review.items，确认观察项和持仓复核。",
            "最后读 data.portfolio_review.repeated_exposures、data.portfolio_review.repeated_overlap_groups、data.risk_register、data.review_path、data.security_risk_profile、data.review_tasks、data.security_review_queue、data.command_queue 与 data.next_questions。",
        ],
        "boundary": "这是复盘报告，不生成交易指令、目标价或仓位建议。",
        "priority_score": "data.security_review_queue[].priority_score 是队列排序分，用于标的复核优先级，不代表目标价或交易强度。",
    }


def validate_daily_files(
    items: List[PoolItem],
    quotes_path,
    holdings_path,
) -> Dict[str, object]:
    quote_errors, quote_warnings, quotes = validate_quotes_file(quotes_path, items)
    holding_errors, holding_warnings, holdings = validate_holdings_file(holdings_path, items)
    warnings = quote_warnings + holding_warnings
    errors = quote_errors + holding_errors
    if not errors:
        warnings.extend(validate_cross_coverage(quotes, holdings))

    return {
        "ok": not errors,
        "quotes": quotes,
        "holdings": holdings,
        "validation": {
            "ok": not errors,
            "summary": {
                "quote_count": len(quotes),
                "holding_count": len(holdings),
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
            "files": {
                "quotes": str(quotes_path),
                "holdings": str(holdings_path),
            },
            "errors": errors,
            "warnings": warnings,
        },
    }


def build_data_check(quotes: List[Quote], holdings: List[Holding]) -> Dict[str, object]:
    warnings = validate_cross_coverage(quotes, holdings)
    return {
        "ok": True,
        "summary": {
            "quote_count": len(quotes),
            "holding_count": len(holdings),
            "error_count": 0,
            "warning_count": len(warnings),
        },
        "warnings": warnings,
    }


def build_report_summary(
    brief: Dict[str, object],
    market_map: Dict[str, object],
    watchlist: Dict[str, object],
    portfolio_review: Dict[str, object],
    validation: Dict[str, object],
    risks: List[str],
) -> str:
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    portfolio_items = portfolio_review.get("items", []) if isinstance(portfolio_review.get("items"), list) else []
    high_review_count = sum(1 for item in portfolio_items if isinstance(item, dict) and item.get("priority") == "high_review")
    return (
        "%s 链路地图覆盖 %s 个层级；观察项 %s 个；持仓复核 %s 个，其中重点复核 %s 个；数据告警 %s 个；风险标签 %s 个。"
        % (
            brief.get("summary") or "暂无简报。",
            market_map.get("layer_count"),
            watchlist.get("count"),
            portfolio_review.get("review_count", 0),
            high_review_count,
            validation_summary.get("warning_count", 0),
            len(risks),
        )
    )


def build_next_questions(
    brief: Dict[str, object],
    market_map: Dict[str, object],
    portfolio_review: Dict[str, object],
    validation: Dict[str, object],
) -> List[str]:
    questions = []
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    if validation_summary.get("warning_count"):
        questions.append("哪些持仓缺行情、哪些行情不在持仓中，需要补数据或降权解读？")
    strongest = market_map.get("strongest_hotspot")
    if isinstance(strongest, dict):
        questions.append(
            "%s / %s 的强度来自多标的共振，还是少数标的拉动？"
            % (strongest.get("layer"), strongest.get("sub_sector"))
        )
    questions.extend(str(question) for question in brief.get("questions", [])[:3])
    questions.extend(str(question) for question in portfolio_review.get("questions", [])[:3])
    deduped = []
    for question in questions:
        if question not in deduped:
            deduped.append(question)
    return deduped[:6]


RISK_DEFINITIONS = {
    "data_quality_warnings": {
        "label": "数据质量告警",
        "severity_score": 75,
        "scope": "data",
        "question": "这些数据缺口会不会改变热点、观察清单或持仓复核结论？",
    },
    "data_quality_errors": {
        "label": "数据质量错误",
        "severity_score": 95,
        "scope": "data",
        "question": "错误修复前，哪些下游结论需要暂缓解读？",
    },
    "theme_concentration": {
        "label": "主题集中",
        "severity_score": 90,
        "scope": "portfolio",
        "question": "多个持仓是否受同一叙事和同一风险驱动？",
    },
    "theme_overlap": {
        "label": "主题重叠",
        "severity_score": 82,
        "scope": "portfolio",
        "question": "重叠主题是否会放大同涨同跌或同向回撤？",
    },
    "multi_chain_exposure": {
        "label": "多链路暴露",
        "severity_score": 80,
        "scope": "portfolio",
        "question": "多链路归属是真实业务弹性，还是复核口径过宽？",
    },
    "holding_missing_quote": {
        "label": "持仓缺行情",
        "severity_score": 86,
        "scope": "data",
        "question": "缺行情持仓是否需要补行情后再进入持仓复核？",
    },
    "not_in_pool": {
        "label": "未匹配池子",
        "severity_score": 84,
        "scope": "data",
        "question": "该持仓是池子缺漏，还是不属于当前复盘主题？",
    },
    "foundation_pool_match": {
        "label": "基础清单覆盖",
        "severity_score": 78,
        "scope": "coverage",
        "question": "该持仓是否只命中全 A 基础清单，尚缺行业/主题逻辑、证据和证伪风险？",
    },
    "draft_pool_match": {
        "label": "草稿池覆盖",
        "severity_score": 76,
        "scope": "coverage",
        "question": "候选或待复核补池行是否已经确认链路、角色和公司逻辑？",
    },
    "chase_high_risk": {
        "label": "追高风险",
        "severity_score": 72,
        "scope": "price_context",
        "question": "涨幅是否来自板块共振，还是少数标的单日拉动？",
    },
    "intraday_fade_risk": {
        "label": "冲高回落风险",
        "severity_score": 70,
        "scope": "price_context",
        "question": "回落是正常波动，还是强度衰减和承接不足？",
    },
    "turnover_expansion_watch": {
        "label": "成交放大待复核",
        "severity_score": 58,
        "scope": "price_context",
        "question": "成交放大是否有链路、资金或消息面的交叉证据？",
    },
    "single_name_or_thin_resonance": {
        "label": "单票或弱共振",
        "severity_score": 56,
        "scope": "market_structure",
        "question": "当前强度是单票驱动，还是已有足够多标的共振？",
    },
    "weak_hotspot_score": {
        "label": "热点强度偏弱",
        "severity_score": 54,
        "scope": "market_structure",
        "question": "热点分偏弱时，是否只应作为观察而非主线判断依据？",
    },
    "weak_price_context": {
        "label": "价格上下文偏弱",
        "severity_score": 52,
        "scope": "price_context",
        "question": "价格表现偏弱是否和所属链路强度背离？",
    },
    "no_hotspot_context": {
        "label": "缺少热点上下文",
        "severity_score": 50,
        "scope": "market_structure",
        "question": "缺少热点上下文的持仓是否需要单独核对公司逻辑？",
    },
}


def build_risk_register(
    brief: Dict[str, object],
    watchlist: Dict[str, object],
    portfolio_review: Dict[str, object],
    validation: Dict[str, object],
    limit: int = 10,
) -> List[Dict[str, object]]:
    entries: Dict[str, Dict[str, object]] = {}
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    portfolio_items = portfolio_review.get("items", []) if isinstance(portfolio_review.get("items"), list) else []
    if validation_summary.get("error_count"):
        upsert_risk_entry(
            entries,
            "data_quality_errors",
            compact_daily_issues(validation.get("errors", [])),
            affected_symbols_from_issues(validation.get("errors", [])),
            ["market-intel validate runtime --json", "market-intel import schema --json"],
        )
    if validation_summary.get("warning_count"):
        upsert_risk_entry(
            entries,
            "data_quality_warnings",
            compact_daily_issues(validation.get("warnings", [])),
            affected_symbols_from_issues(validation.get("warnings", [])),
            ["market-intel daily --runtime --json", "market-intel import schema --json"],
        )

    repeated = portfolio_review.get("repeated_exposures", []) if isinstance(portfolio_review.get("repeated_exposures"), list) else []
    overlap = (
        portfolio_review.get("repeated_overlap_groups", [])
        if isinstance(portfolio_review.get("repeated_overlap_groups"), list)
        else []
    )
    if repeated or overlap:
        upsert_risk_entry(
            entries,
            "theme_concentration",
            compact_group_evidence(repeated, "重复链路") + compact_group_evidence(overlap, "重复主题"),
            affected_symbols_from_concentration(repeated, overlap, portfolio_items),
            ["market-intel portfolio review --runtime --text", "market-intel map --runtime --text"],
        )

    for item in portfolio_items:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        name = item.get("name")
        evidence = portfolio_risk_evidence(item)
        commands = portfolio_security_commands(symbol)
        for flag in item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []:
            upsert_risk_entry(entries, str(flag), [evidence], [symbol_name(symbol, name)], commands)

    watchlist_items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []
    for item in watchlist_items:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        name = item.get("name")
        evidence = watchlist_risk_evidence(item)
        commands = watchlist_security_commands(symbol, bool(item.get("is_holding")))
        for flag in item.get("risks", []) if isinstance(item.get("risks"), list) else []:
            upsert_risk_entry(entries, str(flag), [evidence], [symbol_name(symbol, name)], commands)

    for hotspot in brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []:
        if not isinstance(hotspot, dict):
            continue
        leaders = hotspot.get("leaders", []) if isinstance(hotspot.get("leaders"), list) else []
        affected = [symbol_name(leader.get("symbol"), leader.get("name")) for leader in leaders if isinstance(leader, dict)]
        evidence = "%s/%s | 热点 %s | 活跃 %s/%s" % (
            hotspot.get("layer"),
            hotspot.get("sub_sector"),
            hotspot.get("score"),
            hotspot.get("active_member_count"),
            hotspot.get("member_count"),
        )
        for flag in hotspot.get("risks", []) if isinstance(hotspot.get("risks"), list) else []:
            upsert_risk_entry(
                entries,
                str(flag),
                [evidence],
                affected,
                ["market-intel map --runtime --text", "market-intel brief --runtime --text"],
            )

    rows = list(entries.values())
    for item in rows:
        item["affected_symbols"] = dedupe_texts(item.get("affected_symbols", []))[:8]
        item["evidence"] = dedupe_texts(item.get("evidence", []))[:5]
        item["commands"] = dedupe_texts(item.get("commands", []))[:4]
        item["affected_count"] = len(item["affected_symbols"])
        item["severity"] = severity_label(int_number(item.get("severity_score")))
        item["done_when"] = risk_done_when(item)
    rows.sort(key=lambda row: (-int_number(row.get("severity_score")), -int_number(row.get("affected_count")), str(row.get("risk_id") or "")))
    for rank, item in enumerate(rows[:limit], start=1):
        item["rank"] = rank
    return rows[:limit]


def build_review_path(
    risk_register: List[Dict[str, object]],
    review_tasks: List[Dict[str, object]],
    security_review_queue: List[Dict[str, object]],
    limit: int = 6,
) -> List[Dict[str, object]]:
    steps: List[Dict[str, object]] = []
    data_risk = first_matching_risk(risk_register, {"data"})
    if data_risk:
        steps.append(
            review_path_step(
                "data_quality",
                "先处理数据可信度",
                "数据告警会影响热点、持仓复核和历史留档解读。",
                [data_risk],
                task_commands(review_tasks, "data_quality_review") or data_risk.get("commands", []),
                data_risk.get("done_when") or "已确认数据问题不会误导今日复盘。",
            )
        )

    concentration = first_matching_risk(risk_register, {"portfolio"})
    if concentration:
        steps.append(
            review_path_step(
                "portfolio_risk",
                "再核对组合集中风险",
                "先确认多个持仓是否受同一链路、同一主题或同一价格上下文影响。",
                [concentration],
                task_commands(review_tasks, "portfolio_exposure_review") or concentration.get("commands", []),
                concentration.get("done_when") or "已确认组合集中风险的涉及标的和证据。",
            )
        )

    structure_risk = first_matching_risk(risk_register, {"market_structure", "price_context"})
    if structure_risk:
        steps.append(
            review_path_step(
                "market_structure",
                "确认市场结构强弱",
                "判断当前强度来自多标的共振，还是少数标的单点驱动。",
                [structure_risk],
                task_commands(review_tasks, "market_structure_review") or structure_risk.get("commands", []),
                structure_risk.get("done_when") or "已确认热点强度、活跃数量和主要风险。",
            )
        )

    top_security = first_security_item(security_review_queue)
    if top_security:
        steps.append(
            review_path_security_step(top_security)
        )

    watch_task = first_task(review_tasks, "watchlist_review")
    if watch_task:
        steps.append(
            review_path_step(
                "watchlist_review",
                "扫观察清单",
                watch_task.get("reason") or "把热点领涨、持仓观察和风险标签串起来。",
                [],
                watch_task.get("commands", []),
                watch_task.get("done_when") or "观察清单前几项已核对。",
            )
        )

    steps.append(
        {
            "rank": 0,
            "id": "archive_review",
            "title": "最后保存复盘留档",
            "reason": "把今日风险、标的复核和问题保存成可对比历史。",
            "risk_ids": [],
            "affected_symbols": [],
            "commands": ["market-intel journal save --runtime --json"],
            "runnable": True,
            "done_when": "data.saved 为 true，且 entry.id 已可用于后续 timeline 和 compare。",
        }
    )

    deduped = []
    seen = set()
    for step in steps:
        step_id = str(step.get("id") or "")
        if step_id and step_id not in seen:
            seen.add(step_id)
            deduped.append(step)
    for rank, step in enumerate(deduped[:limit], start=1):
        step["rank"] = rank
    return deduped[:limit]


def review_path_step(
    step_id: str,
    title: str,
    reason: str,
    risks: List[Dict[str, object]],
    commands: object,
    done_when: object,
) -> Dict[str, object]:
    affected = []
    risk_ids = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        risk_ids.append(str(risk.get("risk_id")))
        affected.extend(risk.get("affected_symbols", []) if isinstance(risk.get("affected_symbols"), list) else [])
    return {
        "rank": 0,
        "id": step_id,
        "title": title,
        "reason": reason,
        "risk_ids": dedupe_texts(risk_ids),
        "affected_symbols": dedupe_texts(affected)[:6],
        "commands": dedupe_texts(commands)[:3],
        "runnable": True,
        "done_when": str(done_when or "已完成该步复核。"),
    }


def review_path_security_step(item: Dict[str, object]) -> Dict[str, object]:
    symbol = symbol_name(item.get("symbol"), item.get("name"))
    return {
        "rank": 0,
        "id": "security_review",
        "title": "重点标的复核",
        "reason": "优先展开队列分最高、风险标签最多或持仓相关的标的。",
        "risk_ids": list(item.get("risk_flags", []))[:4] if isinstance(item.get("risk_flags"), list) else [],
        "affected_symbols": [symbol] if symbol else [],
        "commands": list(item.get("commands", []))[:3] if isinstance(item.get("commands"), list) else [],
        "runnable": True,
        "done_when": "已记录该标的的行情、热点上下文、链路暴露、风险标签和还需验证的问题。",
    }


def first_matching_risk(risk_register: List[Dict[str, object]], scopes: set) -> Dict[str, object]:
    for risk in risk_register:
        if isinstance(risk, dict) and risk.get("scope") in scopes:
            return risk
    return {}


def first_task(review_tasks: List[Dict[str, object]], task_id: str) -> Dict[str, object]:
    for task in review_tasks:
        if isinstance(task, dict) and task.get("id") == task_id:
            return task
    return {}


def task_commands(review_tasks: List[Dict[str, object]], task_id: str) -> List[object]:
    task = first_task(review_tasks, task_id)
    return task.get("commands", []) if isinstance(task.get("commands"), list) else []


def first_security_item(security_review_queue: List[Dict[str, object]]) -> Dict[str, object]:
    for item in security_review_queue:
        if isinstance(item, dict):
            return item
    return {}


def build_security_risk_profile(
    risk_register: List[Dict[str, object]],
    security_review_queue: List[Dict[str, object]],
    limit: int = 8,
) -> List[Dict[str, object]]:
    rows = []
    for item in security_review_queue[:limit]:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "")
        if not symbol:
            continue
        risks = risks_for_symbol(risk_register, symbol)
        risk_ids = dedupe_texts(
            list(item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else [])
            + [risk.get("risk_id") for risk in risks if isinstance(risk, dict)]
        )
        evidence = dedupe_texts(
            list(item.get("reasons", []) if isinstance(item.get("reasons"), list) else [])
            + [row for risk in risks if isinstance(risk, dict) for row in risk_evidence_for_symbol(risk, symbol)[:2]]
        )
        review_questions = dedupe_texts(
            list(item.get("review_points", []) if isinstance(item.get("review_points"), list) else [])
            + [risk.get("review_question") for risk in risks if isinstance(risk, dict)]
        )
        highest = max([int_number(risk.get("severity_score")) for risk in risks if isinstance(risk, dict)] + [int_number(item.get("priority_score"))])
        rows.append(
            {
                "rank": item.get("rank"),
                "symbol": symbol,
                "name": item.get("name"),
                "priority_score": item.get("priority_score"),
                "severity": severity_label(highest),
                "risk_ids": risk_ids[:8],
                "related_risks": [
                    {
                        "risk_id": risk.get("risk_id"),
                        "label": risk.get("label"),
                        "severity": risk.get("severity"),
                        "rank": risk.get("rank"),
                    }
                    for risk in risks[:5]
                    if isinstance(risk, dict)
                ],
                "evidence": evidence[:5],
                "review_questions": review_questions[:5],
                "commands": list(item.get("commands", []))[:4] if isinstance(item.get("commands"), list) else [],
                "note_command": item.get("note_command"),
                "done_when": "已核对该标的关联风险、行情上下文、链路暴露和还需验证的问题。",
            }
        )
    rows.sort(key=lambda row: (-int_number(row.get("priority_score")), int_number(row.get("rank"))))
    for rank, row in enumerate(rows[:limit], start=1):
        row["rank"] = rank
    return rows[:limit]


def risks_for_symbol(risk_register: List[Dict[str, object]], symbol: str) -> List[Dict[str, object]]:
    rows = []
    for risk in risk_register:
        if not isinstance(risk, dict):
            continue
        affected = risk.get("affected_symbols", []) if isinstance(risk.get("affected_symbols"), list) else []
        if any(symbol_from_display(item) == symbol for item in affected):
            rows.append(risk)
    rows.sort(key=lambda row: (int_number(row.get("rank")), -int_number(row.get("severity_score"))))
    return rows


def risk_evidence_for_symbol(risk: Dict[str, object], symbol: str) -> List[object]:
    evidence = risk.get("evidence", []) if isinstance(risk.get("evidence"), list) else []
    if risk.get("scope") == "data":
        return [row for row in evidence if symbol in str(row)]
    symbol_rows = [row for row in evidence if symbol in str(row)]
    return symbol_rows or evidence


def symbol_from_display(value: object) -> str:
    text = str(value or "").strip()
    return text.split(" ", 1)[0] if text else ""


def upsert_risk_entry(
    entries: Dict[str, Dict[str, object]],
    risk_id: str,
    evidence: List[object],
    affected_symbols: List[object],
    commands: List[object],
) -> None:
    definition = RISK_DEFINITIONS.get(risk_id, {})
    item = entries.setdefault(
        risk_id,
        {
            "risk_id": risk_id,
            "label": definition.get("label", risk_id),
            "scope": definition.get("scope", "review"),
            "severity_score": definition.get("severity_score", 45),
            "severity": "medium",
            "affected_symbols": [],
            "affected_count": 0,
            "evidence": [],
            "commands": [],
            "review_question": definition.get("question", "这条风险是否会影响当天复盘结论？"),
            "done_when": "",
        },
    )
    item["evidence"].extend(str(row) for row in evidence if row)
    item["affected_symbols"].extend(str(row) for row in affected_symbols if row)
    item["commands"].extend(str(command) for command in commands if command)


def severity_label(score: int) -> str:
    if score >= 85:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def risk_done_when(item: Dict[str, object]) -> str:
    affected = item.get("affected_count", 0)
    if item.get("scope") == "data":
        return "已确认每个数据告警是否需要补数据，且知道哪些结论需要降权解读。"
    if item.get("scope") == "coverage":
        return "已确认基础/草稿覆盖标的的行业归属、主题逻辑、关键证据和证伪风险。"
    if item.get("scope") == "portfolio":
        return "已核对涉及标的、重复链路或重复主题，并记录是否受同一风险驱动。"
    if item.get("scope") == "price_context":
        return "已核对涨跌幅、成交放大、回落和所属链路强度，涉及标的 %s 个。" % affected
    if item.get("scope") == "market_structure":
        return "已确认该风险来自单票、弱共振还是整体链路强度不足。"
    return "已记录证据、涉及标的和后续复核命令。"


def affected_symbols_from_issues(value: object) -> List[str]:
    rows = []
    for issue in value if isinstance(value, list) else []:
        if not isinstance(issue, dict):
            continue
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        symbol = issue.get("symbol") or detail.get("symbol")
        if symbol:
            rows.append(str(symbol))
    return rows


def affected_symbols_from_groups(groups: List[object]) -> List[str]:
    symbols = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
        for holding in holdings:
            if isinstance(holding, dict):
                symbols.append(symbol_name(holding.get("symbol"), holding.get("name")))
    return symbols


def affected_symbols_from_concentration(repeated: List[object], overlap: List[object], portfolio_items: List[object]) -> List[str]:
    symbols = affected_symbols_from_groups(repeated + overlap)
    if symbols:
        return symbols
    repeated_names = {
        str(group.get("group"))
        for group in repeated
        if isinstance(group, dict) and group.get("group")
    }
    overlap_names = {
        str(group.get("group"))
        for group in overlap
        if isinstance(group, dict) and group.get("group")
    }
    for item in portfolio_items:
        if not isinstance(item, dict):
            continue
        matched = False
        exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
        for exposure in exposures:
            if not isinstance(exposure, dict):
                continue
            if "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")) in repeated_names:
                matched = True
                break
        item_overlap = item.get("overlap_groups", []) if isinstance(item.get("overlap_groups"), list) else []
        if any(str(group) in overlap_names for group in item_overlap):
            matched = True
        if matched:
            symbols.append(symbol_name(item.get("symbol"), item.get("name")))
    return symbols


def portfolio_risk_evidence(item: Dict[str, object]) -> str:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    parts = [
        "%s | 复核分 %s" % (symbol_name(item.get("symbol"), item.get("name")), item.get("priority_score")),
    ]
    if quote:
        parts.append("涨幅 %s%%" % quote.get("change_pct"))
        parts.append("回落 %s%%" % quote.get("intraday_fade_pct"))
    if hotspot:
        parts.append("%s/%s | 热点 %s" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score")))
    return " | ".join(parts)


def watchlist_risk_evidence(item: Dict[str, object]) -> str:
    holding = "持仓" if item.get("is_holding") else "观察"
    return "%s | %s | %s/%s | 涨幅 %s%% | 热点 %s" % (
        symbol_name(item.get("symbol"), item.get("name")),
        holding,
        item.get("layer"),
        item.get("sub_sector"),
        item.get("change_pct"),
        item.get("hotspot_score"),
    )


def symbol_name(symbol: object, name: object) -> str:
    if symbol and name:
        return "%s %s" % (symbol, name)
    if symbol:
        return str(symbol)
    return str(name or "")


def build_review_tasks(
    brief: Dict[str, object],
    market_map: Dict[str, object],
    watchlist: Dict[str, object],
    portfolio_review: Dict[str, object],
    validation: Dict[str, object],
) -> List[Dict[str, object]]:
    tasks: List[Dict[str, object]] = []
    validation_summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    if validation_summary.get("warning_count") or validation_summary.get("error_count"):
        tasks.append(
            review_task(
                10,
                "data_quality_review",
                "先确认数据质量",
                "数据缺口会影响热点、持仓复核和历史留档解读。",
                compact_daily_issues(validation.get("errors", [])) + compact_daily_issues(validation.get("warnings", [])),
                ["market-intel validate runtime --json", "market-intel status runtime --text"],
                "知道哪些行情或持仓字段缺失，并决定是否需要补数据后再解读。",
            )
        )

    top_hotspots = brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []
    if top_hotspots:
        top = top_hotspots[0]
        tasks.append(
            review_task(
                20,
                "market_structure_review",
                "确认最强链路的共振强度",
                "先判断今天强度来自多标的链路，还是少数标的单点拉动。",
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
                "能说清最强链路、活跃数量、领涨标的，以及它和持仓是否有关。",
            )
        )

    repeated = portfolio_review.get("repeated_exposures", []) if isinstance(portfolio_review.get("repeated_exposures"), list) else []
    overlap = (
        portfolio_review.get("repeated_overlap_groups", [])
        if isinstance(portfolio_review.get("repeated_overlap_groups"), list)
        else []
    )
    if repeated or overlap:
        tasks.append(
            review_task(
                30,
                "portfolio_exposure_review",
                "核对组合是否扎堆",
                "重复链路或重复主题会让多个持仓受同一叙事和同一风险驱动。",
                compact_group_evidence(repeated, "重复链路") + compact_group_evidence(overlap, "重复主题"),
                ["market-intel portfolio review --runtime --text", "market-intel map --runtime --text"],
                "已确认重复链路/主题涉及哪些持仓，以及这些持仓是否受同一风险驱动。",
            )
        )

    portfolio_items = portfolio_review.get("items", []) if isinstance(portfolio_review.get("items"), list) else []
    high_items = [item for item in portfolio_items if isinstance(item, dict) and item.get("priority") == "high_review"]
    if high_items:
        first_symbol = high_items[0].get("symbol")
        commands = ["market-intel portfolio review --runtime --text"]
        if first_symbol:
            commands.append("market-intel portfolio explain %s --runtime --text" % first_symbol)
        tasks.append(
            review_task(
                40,
                "portfolio_priority_review",
                "逐项看重点持仓",
                "优先看复核分高、风险标签多、缺行情或缺热点上下文的持仓。",
                compact_portfolio_evidence(high_items[:4]),
                commands,
                "重点持仓的行情、热点上下文、链路暴露、风险标签和复核问题已看过。",
            )
        )

    watchlist_items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []
    if watchlist_items:
        tasks.append(
            review_task(
                50,
                "watchlist_review",
                "扫观察清单",
                "把热点领涨、持仓观察和风险标签串起来，避免只看涨幅。",
                compact_watchlist_evidence(watchlist_items[:4]),
                ["market-intel watchlist --runtime --text"],
                "前几项观察标的的链路、是否持仓、热点分和主要风险已核对。",
            )
        )

    return tasks[:6]


def build_daily_security_queue(
    watchlist: Dict[str, object],
    portfolio_review: Dict[str, object],
    limit: int = 8,
) -> List[Dict[str, object]]:
    queue: Dict[str, Dict[str, object]] = {}
    portfolio_items = portfolio_review.get("items", []) if isinstance(portfolio_review.get("items"), list) else []
    for item in portfolio_items:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        score = 60 + int_number(item.get("priority_score"))
        if item.get("priority") == "high_review":
            score += 30
        upsert_daily_security_item(
            queue,
            str(item.get("symbol")),
            item.get("name"),
            score,
            "portfolio_review",
            "%s | 复核分 %s" % (item.get("priority"), item.get("priority_score")),
            item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else [],
            item.get("review_points", []) if isinstance(item.get("review_points"), list) else [],
            portfolio_security_commands(item.get("symbol")),
            portfolio_security_context(item),
        )

    watchlist_items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []
    for item in watchlist_items:
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        score = 45 + int_number(item.get("hotspot_score"))
        if item.get("is_holding"):
            score += 25
        upsert_daily_security_item(
            queue,
            str(item.get("symbol")),
            item.get("name"),
            score,
            "watchlist",
            "%s/%s | 涨幅 %s | 热点 %s"
            % (item.get("layer"), item.get("sub_sector"), item.get("change_pct"), item.get("hotspot_score")),
            item.get("risks", []) if isinstance(item.get("risks"), list) else [],
            [item.get("focus")] if item.get("focus") else [],
            watchlist_security_commands(item.get("symbol"), bool(item.get("is_holding"))),
            watchlist_security_context(item),
        )

    rows = list(queue.values())
    rows.sort(key=lambda row: (-int_number(row.get("priority_score")), str(row.get("symbol") or "")))
    for rank, item in enumerate(rows[:limit], start=1):
        item["rank"] = rank
        item["sources"] = dedupe_texts(item.get("sources", []))[:4]
        item["reasons"] = dedupe_texts(item.get("reasons", []))[:4]
        item["risk_flags"] = dedupe_texts(item.get("risk_flags", []))[:6]
        item["review_points"] = dedupe_texts(item.get("review_points", []))[:4]
        item["commands"] = dedupe_texts(item.get("commands", []))[:4]
        item["note_command"] = security_note_command(item)
    return rows[:limit]


def upsert_daily_security_item(
    queue: Dict[str, Dict[str, object]],
    symbol: str,
    name: object,
    score: int,
    source: str,
    reason: str,
    risk_flags: List[object],
    review_points: List[object],
    commands: List[object],
    context: Dict[str, object],
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
    item["priority_score"] = max(int_number(item.get("priority_score")), int_number(score))
    item["sources"].append(source)
    item["reasons"].append(reason)
    item["risk_flags"].extend(str(flag) for flag in risk_flags if flag)
    item["review_points"].extend(str(point) for point in review_points if point)
    item["commands"].extend(str(command) for command in commands if command)
    item_context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
    for key, value in context.items():
        if value is not None and item_context.get(key) is None:
            item_context[key] = value
    item["context"] = item_context


def portfolio_security_commands(symbol: object) -> List[str]:
    if not symbol:
        return ["market-intel portfolio review --runtime --text"]
    return [
        "market-intel portfolio explain %s --runtime --text" % symbol,
        "market-intel pool explain %s --runtime --text" % symbol,
    ]


def watchlist_security_commands(symbol: object, is_holding: bool) -> List[str]:
    if not symbol:
        return ["market-intel watchlist --runtime --text"]
    if is_holding:
        return portfolio_security_commands(symbol)
    return [
        "market-intel pool explain %s --runtime --text" % symbol,
        "market-intel watchlist --runtime --text",
    ]


def portfolio_security_context(item: Dict[str, object]) -> Dict[str, object]:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    return {
        "is_holding": True,
        "priority": item.get("priority"),
        "coverage_state": item.get("coverage_state"),
        "coverage_state_reasons": item.get("coverage_state_reasons"),
        "research_status": item.get("research_status") if isinstance(item.get("research_status"), dict) else {},
        "change_pct": quote.get("change_pct") if quote else None,
        "amount_ratio": quote.get("amount_ratio") if quote else None,
        "intraday_fade_pct": quote.get("intraday_fade_pct") if quote else None,
        "layer": hotspot.get("layer") if hotspot else None,
        "sub_sector": hotspot.get("sub_sector") if hotspot else None,
        "hotspot_score": hotspot.get("score") if hotspot else None,
    }


def watchlist_security_context(item: Dict[str, object]) -> Dict[str, object]:
    return {
        "is_holding": bool(item.get("is_holding")),
        "focus": item.get("focus"),
        "change_pct": item.get("change_pct"),
        "layer": item.get("layer"),
        "sub_sector": item.get("sub_sector"),
        "hotspot_score": item.get("hotspot_score"),
    }


def review_task(
    priority: int,
    task_id: str,
    title: str,
    reason: str,
    evidence: List[object],
    commands: List[object],
    done_when: str,
) -> Dict[str, object]:
    return {
        "priority": priority,
        "id": task_id,
        "title": title,
        "reason": reason,
        "evidence": [str(item) for item in evidence if item],
        "commands": [str(command) for command in commands if command],
        "note_command": review_task_note_command(task_id, title),
        "done_when": done_when,
    }


def review_task_note_command(task_id: str, title: str) -> str:
    return "market-intel journal note --section %s --text '<填写%s复盘笔记>'" % (task_id, title)


def security_note_command(item: Dict[str, object]) -> str:
    symbol = item.get("symbol") or "unknown"
    name = item.get("name") or ""
    display = "%s %s" % (symbol, name) if name else str(symbol)
    return "market-intel journal note --section security_review --text '<填写%s复核笔记>'" % display


def compact_daily_issues(value: object) -> List[str]:
    issues = value if isinstance(value, list) else []
    rows = []
    for issue in issues[:4]:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code") or "UNKNOWN")
        detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
        symbol = issue.get("symbol") or detail.get("symbol")
        path = issue.get("path") or detail.get("path")
        if symbol:
            rows.append("%s:%s" % (code, symbol))
        elif path:
            rows.append("%s:%s" % (code, path))
        else:
            rows.append(code)
    return rows


def compact_group_evidence(groups: object, prefix: str) -> List[str]:
    rows = groups if isinstance(groups, list) else []
    return [
        "%s %s(%s)" % (prefix, row.get("group"), row.get("holding_count"))
        for row in rows[:3]
        if isinstance(row, dict)
    ]


def compact_portfolio_evidence(items: List[object]) -> List[str]:
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            "%s %s | 复核分 %s | %s"
            % (
                item.get("symbol"),
                item.get("name"),
                item.get("priority_score"),
                ",".join(str(flag) for flag in item.get("risk_flags", [])[:3])
                if isinstance(item.get("risk_flags"), list)
                else "无风险标签",
            )
        )
    return rows


def compact_watchlist_evidence(items: List[object]) -> List[str]:
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        holding = "持仓" if item.get("is_holding") else "观察"
        rows.append(
            "%s %s | %s | %s/%s | 热点 %s"
            % (
                item.get("symbol"),
                item.get("name"),
                holding,
                item.get("layer"),
                item.get("sub_sector"),
                item.get("hotspot_score"),
            )
        )
    return rows


def int_number(value: object, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def dedupe_texts(values: object) -> List[str]:
    rows = values if isinstance(values, list) else []
    result = []
    for value in rows:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def quote_trade_dates(quotes: List[Quote]) -> List[str]:
    return sorted(set(quote.trade_date for quote in quotes if quote.trade_date))


def latest_trade_date(quotes: List[Quote]) -> object:
    dates = quote_trade_dates(quotes)
    return dates[-1] if dates else None
