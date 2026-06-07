from typing import Dict, List, Optional

from .holdings import calculate_holding_impacts
from .models import Holding, Hotspot, PoolItem, Quote
from .scoring import calculate_hotspots
from .symbols import normalize_symbol_text


def build_portfolio_review(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    top: int = 20,
) -> Dict[str, object]:
    quote_by_symbol = {quote.symbol: quote for quote in quotes}
    holding_impact = calculate_holding_impacts(items, holdings)
    hotspots = calculate_hotspots(items, quotes, top=max(1000, len(items)))
    hotspot_context = build_hotspot_context(hotspots)
    rows = [
        build_review_item(holding, impact, quote_by_symbol.get(holding.symbol), hotspot_context)
        for holding, impact in pair_holdings_with_impacts(holdings, holding_impact)
    ]
    rows.sort(key=review_sort_key)
    rows = rows[:top]
    risk_flags = sorted(set(flag for row in rows for flag in row.get("risk_flags", [])))
    return {
        "holding_count": len(holdings),
        "review_count": len(rows),
        "items": rows,
        "summary": build_portfolio_summary(rows, holding_impact, risk_flags),
        "risk_flags": risk_flags,
        "repeated_exposures": holding_impact.get("repeated_exposures", []),
        "repeated_overlap_groups": holding_impact.get("repeated_overlap_groups", []),
        "unmatched_holdings": [
            row
            for row in rows
            if "not_in_pool" in row.get("risk_flags", [])
        ],
        "questions": build_portfolio_questions(rows, holding_impact),
        "guardrails": [
            "这是持仓复盘，不是交易指令。",
            "只展示持仓暴露、行情上下文和风险复核点，不生成交易动作、目标价或仓位建议。",
        ],
        "agent_contract": portfolio_contract(),
    }


def build_portfolio_explain(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    symbol: str,
) -> Dict[str, object]:
    normalized_symbol = normalize_symbol(symbol)
    review = build_portfolio_review(items, quotes, holdings, top=max(1000, len(holdings)))
    target = next((item for item in review.get("items", []) if isinstance(item, dict) and item.get("symbol") == normalized_symbol), None)
    if target is None:
        return {
            "found": False,
            "symbol": normalized_symbol,
            "item": None,
            "summary": "%s 不在当前持仓复盘中。" % normalized_symbol,
            "related": {"same_exposure": [], "same_overlap_group": []},
            "questions": ["确认该代码是否在 holdings.json 中，或先导入最新持仓。"],
            "next_commands": [
                "market-intel portfolio review --runtime --json",
                "market-intel import holdings <holdings.csv> --runtime --json",
            ],
            "agent_contract": portfolio_explain_contract(),
            "errors": [
                {
                    "code": "PORTFOLIO_ITEM_NOT_FOUND",
                    "message": "Symbol is not present in current portfolio review.",
                    "detail": {"symbol": normalized_symbol},
                }
            ],
            "warnings": [],
        }

    related = related_holdings(target, review.get("items", []))
    return {
        "found": True,
        "symbol": normalized_symbol,
        "item": target,
        "summary": build_explain_summary(target, related),
        "related": related,
        "questions": build_explain_questions(target, related),
        "next_commands": [
            "market-intel portfolio review --runtime --text",
            "market-intel pool explain %s --runtime --text" % normalized_symbol,
            "market-intel map --runtime --text",
        ],
        "agent_contract": portfolio_explain_contract(),
        "errors": [],
        "warnings": [],
    }


def pair_holdings_with_impacts(
    holdings: List[Holding],
    holding_impact: Dict[str, object],
) -> List[tuple]:
    impact_by_symbol = {
        str(impact.get("holding_symbol")): impact
        for impact in holding_impact.get("impacts", [])
        if isinstance(impact, dict)
    }
    return [(holding, impact_by_symbol.get(holding.symbol, fallback_impact(holding))) for holding in holdings]


def fallback_impact(holding: Holding) -> Dict[str, object]:
    return {
        "holding_symbol": holding.symbol,
        "holding_name": holding.name,
        "matched_pool_item": False,
        "exposures": [],
        "overlap_groups": [],
        "impact": {"risk_flags": ["not_in_pool"]},
        "explain": "%s 未匹配到当前复盘池。" % holding.symbol,
    }


def build_hotspot_context(hotspots: List[Hotspot]) -> Dict[str, Dict[str, object]]:
    context: Dict[str, Dict[str, object]] = {}
    for hotspot in hotspots:
        hotspot_dict = hotspot.to_dict()
        for leader in hotspot.leaders:
            symbol = str(leader.get("symbol") or "")
            if not symbol:
                continue
            current = context.get(symbol)
            if current is None or float(hotspot.score) > float(current.get("score") or 0):
                context[symbol] = {
                    "layer": hotspot.layer,
                    "sub_sector": hotspot.sub_sector,
                    "score": hotspot.score,
                    "signals": list(hotspot.signals),
                    "risks": list(hotspot.risks),
                    "leader_rank": leader_rank(symbol, hotspot.leaders),
                    "explain": hotspot_dict.get("explain"),
                }
    return context


def leader_rank(symbol: str, leaders: List[Dict[str, object]]) -> Optional[int]:
    for index, leader in enumerate(leaders, start=1):
        if str(leader.get("symbol") or "") == symbol:
            return index
    return None


def build_review_item(
    holding: Holding,
    impact: Dict[str, object],
    quote: Optional[Quote],
    hotspot_context: Dict[str, Dict[str, object]],
) -> Dict[str, object]:
    exposure_rows = normalize_exposures(impact.get("exposures", []))
    holding_risks = list(impact.get("impact", {}).get("risk_flags", [])) if isinstance(impact.get("impact"), dict) else []
    hotspot = hotspot_context.get(holding.symbol)
    quote_risks = quote_risk_flags(quote)
    context_risks = hotspot.get("risks", []) if isinstance(hotspot, dict) else []
    risk_flags = sorted(set(holding_risks + quote_risks + list(context_risks)))
    if quote is None:
        risk_flags.append("holding_missing_quote")
        risk_flags = sorted(set(risk_flags))
    if hotspot is None and quote is not None:
        risk_flags.append("no_hotspot_context")
        risk_flags = sorted(set(risk_flags))
    coverage_state = impact.get("coverage_state") or ("confirmed" if impact.get("matched_pool_item") else "missing")
    coverage_state_reasons = (
        list(impact.get("coverage_state_reasons", []))
        if isinstance(impact.get("coverage_state_reasons"), list)
        else []
    )
    research = impact.get("research_status", {}) if isinstance(impact.get("research_status"), dict) else {}

    priority_score = calculate_priority_score(risk_flags, quote, hotspot, exposure_rows)
    return {
        "symbol": holding.symbol,
        "name": holding.name or impact.get("holding_name"),
        "quantity": holding.quantity,
        "has_quote": quote is not None,
        "quote": quote.to_dict() if quote else None,
        "matched_pool_item": bool(impact.get("matched_pool_item")),
        "coverage_state": coverage_state,
        "coverage_state_reasons": coverage_state_reasons,
        "research_status": compact_research_status(research),
        "exposure_count": len(exposure_rows),
        "exposures": exposure_rows,
        "overlap_groups": impact.get("overlap_groups", []) if isinstance(impact.get("overlap_groups"), list) else [],
        "hotspot_context": hotspot,
        "risk_flags": risk_flags,
        "priority_score": priority_score,
        "priority": priority_label(priority_score),
        "review_points": review_points(risk_flags, quote, hotspot, exposure_rows, compact_research_status(research)),
        "explain": build_item_explain(holding, quote, hotspot, risk_flags, exposure_rows),
    }


def compact_research_status(value: Dict[str, object]) -> Dict[str, object]:
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


def normalize_exposures(value: object) -> List[Dict[str, object]]:
    exposures = value if isinstance(value, list) else []
    rows = []
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        rows.append(
            {
                "layer": exposure.get("layer"),
                "sub_sector": exposure.get("sub_sector"),
                "role": exposure.get("role"),
            }
        )
    return rows


def quote_risk_flags(quote: Optional[Quote]) -> List[str]:
    if quote is None:
        return []
    risks = []
    if quote.change_pct >= 8:
        risks.append("chase_high_risk")
    if quote.intraday_fade_pct >= 3:
        risks.append("intraday_fade_risk")
    if quote.amount_ratio >= 2.5:
        risks.append("turnover_expansion_watch")
    if quote.change_pct <= -3:
        risks.append("weak_price_context")
    return risks


def calculate_priority_score(
    risk_flags: List[str],
    quote: Optional[Quote],
    hotspot: Optional[Dict[str, object]],
    exposures: List[Dict[str, object]],
) -> float:
    score = 0.0
    weights = {
        "holding_missing_quote": 35,
        "not_in_pool": 35,
        "foundation_pool_match": 18,
        "draft_pool_match": 18,
        "theme_overlap": 20,
        "multi_chain_exposure": 20,
        "theme_concentration": 15,
        "no_hotspot_context": 15,
        "chase_high_risk": 12,
        "intraday_fade_risk": 12,
        "single_name_or_thin_resonance": 10,
        "weak_price_context": 10,
        "turnover_expansion_watch": 6,
    }
    for flag in risk_flags:
        score += weights.get(flag, 4)
    if quote is not None:
        score += min(abs(float(quote.change_pct)) * 1.2, 12)
        score += min(float(quote.intraday_fade_pct) * 1.5, 9)
    if hotspot is not None:
        score += min(float(hotspot.get("score") or 0) / 10, 10)
    if len(exposures) >= 2:
        score += 6
    return round(min(score, 100), 2)


def priority_label(score: float) -> str:
    if score >= 55:
        return "high_review"
    if score >= 30:
        return "medium_review"
    return "normal_review"


def review_points(
    risk_flags: List[str],
    quote: Optional[Quote],
    hotspot: Optional[Dict[str, object]],
    exposures: List[Dict[str, object]],
    research: Optional[Dict[str, object]] = None,
) -> List[str]:
    points = []
    research = research if isinstance(research, dict) else {}
    if "holding_missing_quote" in risk_flags:
        points.append("补齐该持仓行情，否则无法判断今日链路上下文。")
    if "not_in_pool" in risk_flags:
        points.append("确认该持仓是否应加入当前复盘池，或单独标记为池外持仓。")
    if "foundation_pool_match" in risk_flags:
        if research.get("available") and not research.get("confirmed"):
            missing = research.get("missing_fields", []) if isinstance(research.get("missing_fields"), list) else []
            suffix = "，缺 %s。" % "、".join(str(field) for field in missing) if missing else "。"
            points.append("该持仓已有研究记录但未达到 reviewed 完整证据%s" % suffix)
        else:
            points.append("该持仓只命中全 A 基础清单，需补行业/主题逻辑、证据和证伪风险。")
    if research.get("confirmed") and "reviewed_research" in research_reason_text(research):
        points.append("研究证据已复核：核心逻辑、关键证据和证伪风险齐全。")
    if "draft_pool_match" in risk_flags:
        points.append("该持仓来自候选或待复核补池行，需确认链路、角色和公司逻辑。")
    if "theme_overlap" in risk_flags or "multi_chain_exposure" in risk_flags:
        points.append("复核多链路或主题重叠是否导致同涨同跌暴露。")
    if "no_hotspot_context" in risk_flags:
        points.append("今日未进入热点上下文，复核是否只是持仓暴露而非当日主线。")
    if quote is not None and quote.intraday_fade_pct >= 3:
        points.append("日内回落较明显，复核强度是否来自早盘脉冲。")
    if quote is not None and quote.change_pct >= 8:
        points.append("涨幅较高，复核追高风险和链路共振强度。")
    if hotspot is not None:
        points.append("对应热点：%s / %s，热点分 %s。" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score")))
    if exposures and not points:
        points.append("链路暴露清晰，继续核对公司逻辑和当日行情来源。")
    return dedupe(points)


def research_reason_text(research: Dict[str, object]) -> str:
    if research.get("confirmed"):
        return "reviewed_research"
    return ""


def build_item_explain(
    holding: Holding,
    quote: Optional[Quote],
    hotspot: Optional[Dict[str, object]],
    risk_flags: List[str],
    exposures: List[Dict[str, object]],
) -> str:
    quote_text = "无行情" if quote is None else "涨幅 %+s%%，成交放大 %s，回落 %s%%" % (
        quote.change_pct,
        quote.amount_ratio,
        quote.intraday_fade_pct,
    )
    hotspot_text = "无热点上下文"
    if hotspot is not None:
        hotspot_text = "%s / %s 热点 %s" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score"))
    return "%s %s：%s；链路 %s 条；%s；风险标签 %s 个。" % (
        holding.symbol,
        holding.name,
        quote_text,
        len(exposures),
        hotspot_text,
        len(risk_flags),
    )


def build_portfolio_summary(
    rows: List[Dict[str, object]],
    holding_impact: Dict[str, object],
    risk_flags: List[str],
) -> str:
    high_count = sum(1 for row in rows if row.get("priority") == "high_review")
    missing_quote_count = sum(1 for row in rows if not row.get("has_quote"))
    unmatched_count = sum(1 for row in rows if "not_in_pool" in row.get("risk_flags", []))
    foundation_count = sum(1 for row in rows if row.get("coverage_state") == "foundation")
    draft_count = sum(1 for row in rows if row.get("coverage_state") == "draft")
    repeated = holding_impact.get("repeated_exposures", []) if isinstance(holding_impact.get("repeated_exposures"), list) else []
    overlap = holding_impact.get("repeated_overlap_groups", []) if isinstance(holding_impact.get("repeated_overlap_groups"), list) else []
    return (
        "持仓 %s 个，需重点复核 %s 个，缺行情 %s 个，池外或未匹配 %s 个，基础/草稿覆盖 %s 个；重复链路 %s 组，重复主题 %s 组，风险标签 %s 个。"
        % (len(rows), high_count, missing_quote_count, unmatched_count, foundation_count + draft_count, len(repeated), len(overlap), len(risk_flags))
    )


def build_portfolio_questions(rows: List[Dict[str, object]], holding_impact: Dict[str, object]) -> List[str]:
    questions = []
    if any(not row.get("has_quote") for row in rows):
        questions.append("哪些持仓缺少行情，需要先补数据再解读？")
    if holding_impact.get("repeated_exposures") or holding_impact.get("repeated_overlap_groups"):
        questions.append("哪些持仓本质上暴露在同一条产业链或同一主题上？")
    high_items = [row for row in rows if row.get("priority") == "high_review"]
    if high_items:
        names = "、".join(str(row.get("name") or row.get("symbol")) for row in high_items[:3])
        questions.append("%s 的高复核优先级来自行情、热点还是主题重叠？" % names)
    if any(row.get("hotspot_context") is None and row.get("has_quote") for row in rows):
        questions.append("哪些持仓有行情但没有热点上下文，是否需要降权解读？")
    foundation = [row for row in rows if row.get("coverage_state") == "foundation"]
    if foundation:
        symbols = "、".join(str(row.get("symbol")) for row in foundation[:4])
        questions.append("%s 只命中全 A 基础清单，是否需要补行业/主题逻辑和证伪风险？" % symbols)
    return dedupe(questions)


def portfolio_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.summary",
            "data.items",
            "data.items[].priority",
            "data.items[].coverage_state",
            "data.items[].coverage_state_reasons",
            "data.items[].research_status",
            "data.items[].risk_flags",
            "data.items[].review_points",
            "data.repeated_exposures",
            "data.questions",
        ],
        "priority_values": ["high_review", "medium_review", "normal_review"],
        "boundary": "这是持仓复盘，不生成交易指令、目标价或仓位建议。",
    }


def portfolio_explain_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 data.found=true",
        "stable_fields": [
            "data.found",
            "data.symbol",
            "data.item.priority",
            "data.item.risk_flags",
            "data.item.review_points",
            "data.related.same_exposure",
            "data.related.same_overlap_group",
            "data.questions",
            "data.next_commands",
        ],
        "boundary": "这是单票持仓复核，不生成交易指令、目标价或仓位建议。",
    }


def related_holdings(target: Dict[str, object], items: object) -> Dict[str, object]:
    rows = items if isinstance(items, list) else []
    target_symbol = str(target.get("symbol") or "")
    target_exposure_keys = exposure_keys(target.get("exposures", []))
    target_overlap_groups = set(str(group) for group in target.get("overlap_groups", []) if group)
    same_exposure = []
    same_overlap_group = []
    for row in rows:
        if not isinstance(row, dict) or row.get("symbol") == target_symbol:
            continue
        shared_exposures = sorted(target_exposure_keys & exposure_keys(row.get("exposures", [])))
        shared_groups = sorted(target_overlap_groups & set(str(group) for group in row.get("overlap_groups", []) if group))
        if shared_exposures:
            same_exposure.append(related_row(row, shared_exposures))
        if shared_groups:
            same_overlap_group.append(related_row(row, shared_groups))
    same_exposure.sort(key=lambda row: (-float(row.get("priority_score") or 0), str(row.get("symbol") or "")))
    same_overlap_group.sort(key=lambda row: (-float(row.get("priority_score") or 0), str(row.get("symbol") or "")))
    return {
        "same_exposure": same_exposure,
        "same_overlap_group": same_overlap_group,
    }


def related_row(row: Dict[str, object], shared: List[str]) -> Dict[str, object]:
    return {
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "priority": row.get("priority"),
        "priority_score": row.get("priority_score"),
        "shared": shared,
        "risk_flags": row.get("risk_flags", []),
    }


def exposure_keys(value: object) -> set:
    exposures = value if isinstance(value, list) else []
    keys = set()
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        keys.add("%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")))
    return keys


def build_explain_summary(target: Dict[str, object], related: Dict[str, object]) -> str:
    quote = target.get("quote", {}) if isinstance(target.get("quote"), dict) else {}
    quote_text = "无行情" if not quote else "涨幅 %+s%%，成交放大 %s，回落 %s%%" % (
        quote.get("change_pct"),
        quote.get("amount_ratio"),
        quote.get("intraday_fade_pct"),
    )
    return (
        "%s %s：%s；优先级 %s，风险标签 %s 个；同链路相关持仓 %s 个，同主题相关持仓 %s 个。"
        % (
            target.get("symbol"),
            target.get("name"),
            quote_text,
            priority_text(target.get("priority")),
            len(target.get("risk_flags", [])) if isinstance(target.get("risk_flags"), list) else 0,
            len(related.get("same_exposure", [])) if isinstance(related.get("same_exposure"), list) else 0,
            len(related.get("same_overlap_group", [])) if isinstance(related.get("same_overlap_group"), list) else 0,
        )
    )


def build_explain_questions(target: Dict[str, object], related: Dict[str, object]) -> List[str]:
    questions = []
    if not target.get("has_quote"):
        questions.append("这只持仓是否缺少当日行情，需要先补数据？")
    if target.get("hotspot_context") is None and target.get("has_quote"):
        questions.append("它有行情但缺少热点上下文，是否只是个股波动？")
    if related.get("same_exposure"):
        questions.append("同链路持仓是否放大了组合内的同向暴露？")
    if related.get("same_overlap_group"):
        questions.append("同主题持仓是否集中在同一叙事上？")
    review_points = target.get("review_points", []) if isinstance(target.get("review_points"), list) else []
    questions.extend(str(point) for point in review_points[:2])
    return dedupe(questions)


def normalize_symbol(symbol: str) -> str:
    return normalize_symbol_text(symbol)


def priority_text(value: object) -> str:
    labels = {
        "high_review": "重点复核",
        "medium_review": "中等复核",
        "normal_review": "常规复核",
    }
    return labels.get(str(value), str(value))


def review_sort_key(row: Dict[str, object]):
    quote = row.get("quote", {}) if isinstance(row.get("quote"), dict) else {}
    return (
        -float(row.get("priority_score") or 0),
        not bool(row.get("has_quote")),
        -float(quote.get("change_pct") or 0),
        str(row.get("symbol") or ""),
    )


def dedupe(values: List[str]) -> List[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
