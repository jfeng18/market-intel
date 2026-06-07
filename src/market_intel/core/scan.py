from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .coverage import matched_coverage_state, research_status, split_universe_values
from .models import Holding, PoolItem, Quote


GroupKey = Tuple[str, str, str]


def build_market_scan(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: Optional[List[Holding]] = None,
    top: int = 8,
    candidate_top: int = 12,
    pool: str = "all-a",
) -> Dict[str, object]:
    holdings = holdings or []
    holding_symbols = {holding.symbol for holding in holdings}
    quote_by_symbol = {quote.symbol: quote for quote in quotes}
    quoted_items = [
        (item, quote_by_symbol[item.symbol])
        for item in items
        if item.tradable and item.symbol and item.symbol in quote_by_symbol
    ]

    groups = build_scan_groups(quoted_items)
    symbol_context = build_symbol_context(quoted_items, groups)
    candidates = build_scan_candidates(quoted_items, holding_symbols, symbol_context, limit=candidate_top, pool=pool)
    candidate_queue = build_candidate_queue(candidates)
    scan_mode = "all_a_universe" if any(has_universe_context(item) for item, _ in quoted_items) else "pool_chain_seed"
    market_breadth = build_market_breadth(quotes, quoted_items, groups, scan_mode)

    return {
        "summary": scan_summary(quotes, quoted_items, groups, candidates, scan_mode, market_breadth),
        "scan_mode": scan_mode,
        "market_breadth": market_breadth,
        "quote_count": len(quotes),
        "matched_quote_count": len(quoted_items),
        "unmatched_quote_count": max(len(quotes) - len(quoted_items), 0),
        "holding_count": len(holdings),
        "trade_dates": sorted({quote.trade_date for quote in quotes if quote.trade_date}),
        "sector_groups": groups[:top],
        "candidate_securities": candidates,
        "candidate_queue": candidate_queue,
        "questions": scan_questions(groups, candidates, scan_mode),
        "next_actions": scan_next_actions(scan_mode, pool),
        "agent_contract": scan_contract(),
        "guardrails": [
            "scan 只生成板块强弱和复盘候选，不生成买卖指令、目标价或仓位建议。",
            "全 A 基础清单只代表覆盖底座；foundation/draft 标的仍需要补齐研究证据。",
            "样本偏薄、缺行情或缺行业/概念字段时，应降权解读扫描结果。",
        ],
    }


def build_scan_groups(quoted_items: List[Tuple[PoolItem, Quote]]) -> List[Dict[str, object]]:
    grouped: Dict[GroupKey, List[Tuple[PoolItem, Quote]]] = defaultdict(list)
    for item, quote in quoted_items:
        seen = set()
        for key in scan_group_keys(item):
            if key in seen:
                continue
            grouped[key].append((item, quote))
            seen.add(key)

    rows = [build_scan_group(key, members) for key, members in grouped.items() if members]
    rows.sort(
        key=lambda row: (
            -float(row.get("score") or 0),
            -int(row.get("active_member_count") or 0),
            -float(row.get("avg_change_pct") or 0),
            str(row.get("group_type") or ""),
            str(row.get("name") or ""),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def scan_group_keys(item: PoolItem) -> List[GroupKey]:
    raw = item.raw if isinstance(item.raw, dict) else {}
    industry = str(raw.get("universe_industry") or "").strip()
    concepts = split_universe_values(raw.get("universe_concepts"))
    indexes = split_universe_values(raw.get("universe_index_membership"))
    keys: List[GroupKey] = []
    if industry:
        keys.append(("industry", industry, "行业"))
    keys.extend(("concept", concept, "概念") for concept in concepts)
    keys.extend(("index", index, "指数") for index in indexes)
    if keys:
        return keys

    for exposure in item.exposures:
        layer = str(exposure.layer or "链路")
        sub_sector = str(exposure.sub_sector or "其他")
        keys.append(("chain", "%s/%s" % (layer, sub_sector), layer))
    return keys or [("unknown", "未分组", "其他")]


def build_scan_group(key: GroupKey, members: List[Tuple[PoolItem, Quote]]) -> Dict[str, object]:
    group_type, name, layer = key
    quotes = [quote for _, quote in members]
    member_count = len(members)
    active_count = sum(1 for quote in quotes if quote.change_pct >= 3 or quote.amount_ratio >= 1.5)
    strong_count = sum(1 for quote in quotes if quote.change_pct >= 5 or quote.is_limit_up)
    stage_high_count = sum(1 for quote in quotes if quote.is_stage_high)
    avg_change = average(quote.change_pct for quote in quotes)
    avg_amount_ratio = average(quote.amount_ratio for quote in quotes)
    avg_fade = average(quote.intraday_fade_pct for quote in quotes)
    active_ratio = active_count / member_count if member_count else 0
    strong_ratio = strong_count / member_count if member_count else 0
    stage_ratio = stage_high_count / member_count if member_count else 0
    score = clamp(avg_change * 7 + avg_amount_ratio * 12 + active_ratio * 30 + strong_ratio * 25 + stage_ratio * 10 - avg_fade * 4)
    if member_count == 1:
        score = min(score, 60)

    leaders = [
        leader_row(item, quote)
        for item, quote in sorted(members, key=lambda pair: pair[1].change_pct, reverse=True)[:5]
    ]
    signals = group_signals(member_count, active_count, strong_count, stage_high_count, avg_amount_ratio, score)
    risks = group_risks(member_count, active_count, avg_fade)

    return {
        "rank": None,
        "key": "%s:%s" % (group_type, name),
        "group_type": group_type,
        "layer": layer,
        "name": name,
        "score": round(score, 2),
        "member_count": member_count,
        "active_member_count": active_count,
        "strong_member_count": strong_count,
        "stage_high_count": stage_high_count,
        "avg_change_pct": round(avg_change, 2),
        "avg_amount_ratio": round(avg_amount_ratio, 2),
        "avg_intraday_fade_pct": round(avg_fade, 2),
        "leaders": leaders,
        "signals": signals,
        "risks": risks,
        "explain": "%s%s 扫描分 %.2f，活跃 %s/%s，领涨 %s。"
        % (group_type_label(group_type), name, score, active_count, member_count, leader_names(leaders)),
    }


def build_market_breadth(
    quotes: List[Quote],
    quoted_items: List[Tuple[PoolItem, Quote]],
    groups: List[Dict[str, object]],
    scan_mode: str,
) -> Dict[str, object]:
    matched_quotes = [quote for _, quote in quoted_items]
    quote_count = len(quotes)
    matched_count = len(matched_quotes)
    up_count = sum(1 for quote in matched_quotes if quote.change_pct > 0)
    down_count = sum(1 for quote in matched_quotes if quote.change_pct < 0)
    flat_count = max(matched_count - up_count - down_count, 0)
    active_count = sum(1 for quote in matched_quotes if quote.change_pct >= 3 or quote.amount_ratio >= 1.5)
    strong_count = sum(1 for quote in matched_quotes if quote.change_pct >= 5 or quote.is_limit_up)
    stage_high_count = sum(1 for quote in matched_quotes if quote.is_stage_high)
    avg_change = average(quote.change_pct for quote in matched_quotes)
    avg_amount_ratio = average(quote.amount_ratio for quote in matched_quotes)
    active_group_count = sum(1 for group in groups if int(group.get("active_member_count") or 0) >= 2)
    strong_group_count = sum(1 for group in groups if float(group.get("score") or 0) >= 70)
    state = market_breadth_state(matched_count, up_count, active_count, active_group_count)
    confidence = market_breadth_confidence(quote_count, matched_count, scan_mode)
    sample_note = market_breadth_sample_note(confidence, quote_count, matched_count, scan_mode)
    summary = market_breadth_summary(
        state,
        matched_count,
        up_count,
        down_count,
        active_count,
        strong_count,
        active_group_count,
        strong_group_count,
    )
    return {
        "state": state,
        "confidence": confidence,
        "summary": summary,
        "sample_note": sample_note,
        "quote_count": quote_count,
        "matched_quote_count": matched_count,
        "matched_ratio": round(matched_count / quote_count, 4) if quote_count else 0,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "up_ratio": round(up_count / matched_count, 4) if matched_count else 0,
        "active_count": active_count,
        "active_ratio": round(active_count / matched_count, 4) if matched_count else 0,
        "strong_count": strong_count,
        "strong_ratio": round(strong_count / matched_count, 4) if matched_count else 0,
        "stage_high_count": stage_high_count,
        "avg_change_pct": round(avg_change, 2),
        "avg_amount_ratio": round(avg_amount_ratio, 2),
        "active_group_count": active_group_count,
        "strong_group_count": strong_group_count,
        "top_group_count": len(groups),
        "interpretation": market_breadth_interpretation(state),
    }


def market_breadth_state(
    matched_count: int,
    up_count: int,
    active_count: int,
    active_group_count: int,
) -> str:
    if matched_count == 0:
        return "no_matched_quotes"
    up_ratio = up_count / matched_count
    active_ratio = active_count / matched_count
    if up_ratio >= 0.6 and active_ratio >= 0.35 and active_group_count >= 3:
        return "broad_strength"
    if active_ratio >= 0.25 and active_group_count >= 2:
        return "structured_strength"
    if active_count > 0:
        return "thin_strength"
    if up_ratio >= 0.5:
        return "mild_rebound"
    return "weak_market"


def market_breadth_confidence(quote_count: int, matched_count: int, scan_mode: str) -> str:
    if matched_count <= 0:
        return "none"
    matched_ratio = matched_count / quote_count if quote_count else 0
    if scan_mode == "all_a_universe" and matched_count >= 200 and matched_ratio >= 0.7:
        return "high"
    if matched_count >= 50 and matched_ratio >= 0.5:
        return "medium"
    return "reference"


def market_breadth_sample_note(confidence: str, quote_count: int, matched_count: int, scan_mode: str) -> str:
    if confidence == "high":
        return "全 A 样本较充分，可作为市场宽度主判断。"
    if confidence == "medium":
        return "样本可参考，但仍需结合覆盖缺口和未匹配行情。"
    if confidence == "none":
        return "暂无匹配行情，不能解读市场宽度。"
    if scan_mode != "all_a_universe":
        return "当前不是完整全 A 样本，宽度只代表复盘池或种子池。"
    return "匹配样本偏少，宽度只作参考。"


def market_breadth_summary(
    state: str,
    matched_count: int,
    up_count: int,
    down_count: int,
    active_count: int,
    strong_count: int,
    active_group_count: int,
    strong_group_count: int,
) -> str:
    return "%s：上涨 %s/%s，下跌 %s，活跃 %s，强势 %s；活跃板块 %s，强板块 %s。" % (
        market_breadth_state_label(state),
        up_count,
        matched_count,
        down_count,
        active_count,
        strong_count,
        active_group_count,
        strong_group_count,
    )


def market_breadth_state_label(value: object) -> str:
    labels = {
        "broad_strength": "普遍走强",
        "structured_strength": "结构性走强",
        "thin_strength": "局部活跃",
        "mild_rebound": "温和修复",
        "weak_market": "弱势整理",
        "no_matched_quotes": "无匹配行情",
    }
    return labels.get(str(value), str(value or "未知"))


def market_breadth_interpretation(state: str) -> str:
    mapping = {
        "broad_strength": "先看板块扩散和持仓是否跟随，避免只追单日涨幅。",
        "structured_strength": "优先复核强板块是否多标的共振，再看候选证据缺口。",
        "thin_strength": "强势集中在少数标的，需确认是否单票驱动。",
        "mild_rebound": "上涨面尚可但活跃度有限，重点看持续性证据。",
        "weak_market": "整体偏弱，候选应降权解读并优先看风险。",
        "no_matched_quotes": "先补行情源和复盘池匹配，再解读市场强弱。",
    }
    return mapping.get(state, "先确认行情覆盖和板块共振质量。")


def leader_row(item: PoolItem, quote: Quote) -> Dict[str, object]:
    state = matched_coverage_state(item)
    return {
        "symbol": item.symbol,
        "name": item.name,
        "change_pct": quote.change_pct,
        "amount_ratio": quote.amount_ratio,
        "is_stage_high": quote.is_stage_high,
        "coverage_state": state["state"],
    }


def group_signals(
    member_count: int,
    active_count: int,
    strong_count: int,
    stage_high_count: int,
    avg_amount_ratio: float,
    score: float,
) -> List[str]:
    signals = []
    if active_count >= 2:
        signals.append("sector_resonance")
    if member_count >= 3 and active_count / member_count >= 0.5:
        signals.append("broad_sector_strength")
    if strong_count:
        signals.append("strong_members")
    if stage_high_count:
        signals.append("stage_high_members")
    if avg_amount_ratio >= 1.5:
        signals.append("turnover_expansion")
    if score >= 70:
        signals.append("high_hotspot_score")
    return signals


def group_risks(member_count: int, active_count: int, avg_fade: float) -> List[str]:
    risks = []
    if member_count == 1 or active_count <= 1:
        risks.append("single_name_or_thin_resonance")
    if avg_fade >= 3:
        risks.append("intraday_fade_risk")
    if not risks:
        risks.append("continuation_needs_confirmation")
    return risks


def build_symbol_context(
    quoted_items: List[Tuple[PoolItem, Quote]],
    groups: List[Dict[str, object]],
) -> Dict[str, List[Dict[str, object]]]:
    group_by_key = {str(group.get("key")): group for group in groups if isinstance(group, dict)}
    by_symbol: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for item, _ in quoted_items:
        if not item.symbol:
            continue
        seen = set()
        for key in scan_group_keys(item):
            group_key = "%s:%s" % (key[0], key[1])
            if group_key in seen:
                continue
            seen.add(group_key)
            group = group_by_key.get(group_key)
            if not group:
                continue
            by_symbol[item.symbol].append(scan_context_row(group))
    for contexts in by_symbol.values():
        contexts.sort(key=lambda row: (-float(row.get("score") or 0), int(row.get("rank") or 9999)))
    return by_symbol


def scan_context_row(group: Dict[str, object]) -> Dict[str, object]:
    return {
        "key": group.get("key"),
        "group_type": group.get("group_type"),
        "layer": group.get("layer"),
        "name": group.get("name"),
        "score": group.get("score"),
        "rank": group.get("rank"),
        "member_count": group.get("member_count", 0),
        "active_member_count": group.get("active_member_count", 0),
        "signals": group.get("signals", []),
        "risks": group.get("risks", []),
    }


def build_scan_candidates(
    quoted_items: List[Tuple[PoolItem, Quote]],
    holding_symbols: set,
    symbol_context: Dict[str, List[Dict[str, object]]],
    limit: int,
    pool: str,
) -> List[Dict[str, object]]:
    rows = []
    for item, quote in quoted_items:
        if not item.symbol:
            continue
        contexts = symbol_context.get(item.symbol, [])
        state = matched_coverage_state(item)
        research = research_status(item)
        risk_flags = candidate_risk_flags(item, quote, contexts, state["state"])
        universe_context = candidate_universe_context(item, contexts)
        ranking_breakdown = candidate_ranking_breakdown(
            item,
            quote,
            contexts,
            item.symbol in holding_symbols,
            risk_flags,
            research,
            universe_context,
        )
        review_score = ranking_breakdown["total_score"]
        checklist = candidate_checklist(quote, contexts, state["state"], research, risk_flags)
        commands = candidate_commands(item.symbol, state["state"], pool)
        done_when = candidate_done_when(state["state"])
        rows.append(
            {
                "rank": None,
                "symbol": item.symbol,
                "name": item.name,
                "is_holding": item.symbol in holding_symbols,
                "industry": item.raw.get("universe_industry"),
                "concepts": split_universe_values(item.raw.get("universe_concepts")),
                "index_membership": split_universe_values(item.raw.get("universe_index_membership")),
                "primary_layer": item.primary_layer,
                "primary_sub_sector": item.primary_sub_sector,
                "quote": quote.to_dict(),
                "sector_contexts": contexts[:4],
                "universe_context": universe_context,
                "coverage_state": state["state"],
                "coverage_state_reasons": state["reasons"],
                "research_status": research,
                "risk_flags": risk_flags,
                "review_score": review_score,
                "ranking_breakdown": ranking_breakdown,
                "priority": priority_label(review_score),
                "why_now": candidate_why_now(
                    item,
                    quote,
                    contexts,
                    state["state"],
                    item.symbol in holding_symbols,
                    universe_context,
                ),
                "review_focus": candidate_review_focus(
                    item,
                    quote,
                    contexts,
                    state,
                    research,
                    risk_flags,
                    checklist,
                    commands,
                    done_when,
                    universe_context,
                    ranking_breakdown,
                ),
                "checklist": checklist,
                "commands": commands,
                "done_when": done_when,
            }
        )
    rows.sort(key=candidate_sort_key)
    for rank, row in enumerate(rows[:limit], start=1):
        row["rank"] = rank
    return rows[:limit]


def candidate_risk_flags(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: str,
) -> List[str]:
    flags = []
    if quote.change_pct >= 8:
        flags.append("chase_high_risk")
    if quote.intraday_fade_pct >= 3:
        flags.append("intraday_fade_risk")
    if quote.amount_ratio >= 2.5:
        flags.append("turnover_expansion_watch")
    if quote.change_pct <= -3:
        flags.append("weak_price_context")
    if coverage_state == "foundation":
        flags.append("foundation_pool_match")
    if coverage_state == "draft":
        flags.append("draft_pool_match")
    for context in contexts[:2]:
        risks = context.get("risks", []) if isinstance(context.get("risks"), list) else []
        flags.extend(str(risk) for risk in risks)
    flags.extend(str(flag) for flag in item.data_quality_flags if flag)
    return sorted(set(flags))


def candidate_ranking_breakdown(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    is_holding: bool,
    risk_flags: List[str],
    research: Dict[str, object],
    universe_context: Dict[str, object],
) -> Dict[str, object]:
    best_context_score = max([float(context.get("score") or 0) for context in contexts] or [0])
    factors = [
        ranking_factor("price_strength", min(max(quote.change_pct, 0) * 2.2, 22), "涨幅 %+s%%" % quote.change_pct),
        ranking_factor("turnover_expansion", min(quote.amount_ratio * 6, 18), "成交放大 %.2f" % quote.amount_ratio),
        ranking_factor("sector_strength", min(best_context_score / 2, 40), "最强上下文 %.0f" % best_context_score),
    ]
    universe_bonus = float(universe_context.get("score_bonus") or 0)
    if universe_bonus:
        factors.append(ranking_factor("universe_context", universe_bonus, "全 A 归属加成"))
    if quote.is_stage_high:
        factors.append(ranking_factor("stage_high", 8, "阶段新高"))
    if is_holding:
        factors.append(ranking_factor("holding_attention", 8, "当前持仓"))
    if "foundation_pool_match" in risk_flags or "draft_pool_match" in risk_flags:
        factors.append(ranking_factor("coverage_gap", 10, "覆盖待补，优先复核"))
    if research.get("available") and not research.get("confirmed"):
        factors.append(ranking_factor("research_unconfirmed", 5, "研究记录未确认"))
    if item.data_quality_flags:
        factors.append(ranking_factor("data_quality_attention", 5, "数据质量需核对"))
    penalty_flags = candidate_ranking_penalties(risk_flags, contexts, quote)
    raw_score = sum(float(factor.get("score") or 0) for factor in factors)
    penalty_score = sum(float(flag.get("score") or 0) for flag in penalty_flags)
    total_score = round(clamp(raw_score - penalty_score), 2)
    return {
        "total_score": total_score,
        "raw_score": round(raw_score, 2),
        "penalty_score": round(penalty_score, 2),
        "factors": [factor for factor in factors if float(factor.get("score") or 0) > 0],
        "penalty_flags": penalty_flags,
        "summary": ranking_breakdown_summary(factors, penalty_flags, total_score),
    }


def candidate_review_score(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    is_holding: bool,
    risk_flags: List[str],
    research: Dict[str, object],
    universe_context: Dict[str, object],
) -> float:
    return candidate_ranking_breakdown(
        item,
        quote,
        contexts,
        is_holding,
        risk_flags,
        research,
        universe_context,
    )["total_score"]


def ranking_factor(factor_id: str, score: float, reason: str) -> Dict[str, object]:
    return {
        "id": factor_id,
        "score": round(max(score, 0), 2),
        "reason": reason,
    }


def candidate_ranking_penalties(
    risk_flags: List[str],
    contexts: List[Dict[str, object]],
    quote: Quote,
) -> List[Dict[str, object]]:
    penalties = []
    if "chase_high_risk" in risk_flags:
        penalties.append(ranking_factor("chase_high_risk", 6, "涨幅较高，避免追高"))
    if "intraday_fade_risk" in risk_flags:
        penalties.append(ranking_factor("intraday_fade_risk", 8, "日内回落削弱持续性"))
    if "weak_price_context" in risk_flags:
        penalties.append(ranking_factor("weak_price_context", 10, "价格上下文偏弱"))
    if "single_name_or_thin_resonance" in risk_flags:
        penalties.append(ranking_factor("thin_resonance", 5, "共振偏薄"))
    if not contexts:
        penalties.append(ranking_factor("missing_context", 8, "缺少板块上下文"))
    if quote.amount_ratio >= 4 and quote.intraday_fade_pct >= 2:
        penalties.append(ranking_factor("hot_money_noise", 4, "放量且回落，需防短线噪音"))
    return penalties


def ranking_breakdown_summary(
    factors: List[Dict[str, object]],
    penalty_flags: List[Dict[str, object]],
    total_score: float,
) -> str:
    top_factors = [
        "%s +%.0f" % (ranking_label(factor.get("id")), float(factor.get("score") or 0))
        for factor in sorted(factors, key=lambda value: -float(value.get("score") or 0))[:3]
        if float(factor.get("score") or 0) > 0
    ]
    penalties = [
        "%s -%.0f" % (ranking_label(flag.get("id")), float(flag.get("score") or 0))
        for flag in penalty_flags[:2]
        if float(flag.get("score") or 0) > 0
    ]
    parts = []
    if top_factors:
        parts.append("主因 %s" % "、".join(top_factors))
    if penalties:
        parts.append("降权 %s" % "、".join(penalties))
    parts.append("总分 %.0f" % total_score)
    return "；".join(parts)


def ranking_label(value: object) -> str:
    labels = {
        "price_strength": "涨幅",
        "turnover_expansion": "放量",
        "sector_strength": "板块",
        "universe_context": "全A",
        "stage_high": "新高",
        "holding_attention": "持仓",
        "coverage_gap": "覆盖缺口",
        "research_unconfirmed": "研究待确认",
        "data_quality_attention": "数据质量",
        "chase_high_risk": "追高",
        "intraday_fade_risk": "回落",
        "weak_price_context": "弱价格",
        "thin_resonance": "弱共振",
        "missing_context": "缺上下文",
        "hot_money_noise": "短线噪音",
    }
    return labels.get(str(value), str(value or "因子"))


def candidate_why_now(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: str,
    is_holding: bool,
    universe_context: Dict[str, object],
) -> str:
    parts = [
        "涨幅 %+s%%，成交放大 %.2f" % (quote.change_pct, quote.amount_ratio),
    ]
    if contexts:
        best = contexts[0]
        parts.append("%s%s 扫描分 %s" % (group_type_label(best.get("group_type")), best.get("name"), best.get("score")))
    else:
        parts.append("%s/%s 有行情但缺少板块上下文" % (item.primary_layer, item.primary_sub_sector))
    if quote.is_stage_high:
        parts.append("阶段新高")
    if is_holding:
        parts.append("当前持仓")
    if universe_context.get("available") and universe_context.get("explain"):
        parts.append(str(universe_context.get("explain")))
    if coverage_state != "confirmed":
        parts.append("覆盖状态 %s 需复核" % coverage_state)
    return "；".join(parts)


def candidate_checklist(
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: str,
    research: Dict[str, object],
    risk_flags: List[str],
) -> List[str]:
    checklist = []
    if contexts:
        checklist.append("核对板块强度是否由多只标的共同贡献，而不是单票异动。")
    else:
        checklist.append("补充行业/概念/指数成分字段，确认该标的所属板块。")
    if quote.amount_ratio >= 1.5:
        checklist.append("核对成交放大是否有新闻、业绩、政策或资金行为支撑。")
    if quote.intraday_fade_pct >= 3:
        checklist.append("复核日内回落是否削弱板块持续性。")
    if quote.change_pct >= 8:
        checklist.append("复核涨幅较高后的风险，不把强势等同于可追。")
    if coverage_state == "foundation":
        missing = research.get("missing_fields", []) if isinstance(research.get("missing_fields"), list) else []
        suffix = "，缺 %s" % "、".join(str(field) for field in missing[:3]) if missing else ""
        checklist.append("补齐 research_notes 的核心逻辑、关键证据和证伪风险%s。" % suffix)
    if coverage_state == "draft":
        checklist.append("确认草稿池行的行业/主题链路、角色、逻辑和证伪风险。")
    if not checklist and risk_flags:
        checklist.append("核对风险标签是否影响复盘优先级。")
    return dedupe(checklist)[:5]


def candidate_review_focus(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: Dict[str, object],
    research: Dict[str, object],
    risk_flags: List[str],
    checklist: List[str],
    commands: List[str],
    done_when: str,
    universe_context: Dict[str, object],
    ranking_breakdown: Dict[str, object],
) -> Dict[str, object]:
    state = str(coverage_state.get("state") or "")
    return {
        "headline": candidate_review_headline(item, quote, contexts, state),
        "classification": candidate_classification(item, contexts),
        "coverage": {
            "state": state,
            "reasons": list(coverage_state.get("reasons", [])) if isinstance(coverage_state.get("reasons"), list) else [],
            "research_status": research.get("status"),
            "research_confirmed": bool(research.get("confirmed")),
            "missing_research_fields": list(research.get("missing_fields", [])) if isinstance(research.get("missing_fields"), list) else [],
        },
        "universe_context": compact_universe_context(universe_context),
        "ranking_breakdown": compact_ranking_breakdown(ranking_breakdown),
        "signal_drivers": candidate_signal_drivers(quote, contexts),
        "risk_flags": risk_flags[:8],
        "first_check": checklist[0] if checklist else "",
        "next_command": commands[0] if commands else "",
        "done_when": done_when,
    }


def compact_ranking_breakdown(value: Dict[str, object]) -> Dict[str, object]:
    return {
        "total_score": value.get("total_score"),
        "raw_score": value.get("raw_score"),
        "penalty_score": value.get("penalty_score"),
        "top_factors": list(value.get("factors", []))[:4] if isinstance(value.get("factors"), list) else [],
        "penalty_flags": list(value.get("penalty_flags", []))[:4] if isinstance(value.get("penalty_flags"), list) else [],
        "summary": value.get("summary"),
    }


def candidate_universe_context(item: PoolItem, contexts: List[Dict[str, object]]) -> Dict[str, object]:
    industry = str(item.raw.get("universe_industry") or "").strip()
    concepts = split_universe_values(item.raw.get("universe_concepts"))
    indexes = split_universe_values(item.raw.get("universe_index_membership"))
    dimensions = []
    if industry:
        dimensions.append("industry")
    if concepts:
        dimensions.append("concept")
    if indexes:
        dimensions.append("index")
    universe_contexts = [
        context
        for context in contexts
        if str(context.get("group_type")) in {"industry", "concept", "index"}
    ]
    score_bonus = universe_score_bonus(dimensions, universe_contexts)
    return {
        "available": bool(dimensions or has_universe_context(item)),
        "dimensions": dimensions,
        "dimension_count": len(dimensions),
        "industry": industry or None,
        "concept_count": len(concepts),
        "index_membership_count": len(indexes),
        "context_count": len(universe_contexts),
        "top_contexts": [compact_scan_context(context) for context in universe_contexts[:4]],
        "score_bonus": score_bonus,
        "explain": universe_context_explain(industry, concepts, indexes, universe_contexts, score_bonus),
    }


def universe_score_bonus(dimensions: List[str], contexts: List[Dict[str, object]]) -> float:
    if not dimensions:
        return 0.0
    bonus = min(len(dimensions) * 3, 8)
    if len(contexts) >= 2:
        bonus += 3
    if len(contexts) >= 4:
        bonus += 2
    if any(float(context.get("score") or 0) >= 70 for context in contexts):
        bonus += 3
    return round(min(bonus, 16), 2)


def universe_context_explain(
    industry: str,
    concepts: List[str],
    indexes: List[str],
    contexts: List[Dict[str, object]],
    score_bonus: float,
) -> str:
    parts = []
    if industry:
        parts.append("行业=%s" % industry)
    if concepts:
        parts.append("概念=%s" % "/".join(concepts[:2]))
    if indexes:
        parts.append("指数=%s" % "/".join(indexes[:2]))
    if not parts:
        return ""
    best = contexts[0] if contexts else {}
    suffix = ""
    if best:
        suffix = "，最强%s%s %s" % (
            group_type_label(best.get("group_type")),
            best.get("name"),
            best.get("score"),
        )
    return "全 A 归属 %s%s，评分加成 %.0f" % ("；".join(parts), suffix, score_bonus)


def compact_universe_context(value: Dict[str, object]) -> Dict[str, object]:
    return {
        "available": bool(value.get("available")),
        "dimensions": list(value.get("dimensions", []))[:3] if isinstance(value.get("dimensions"), list) else [],
        "dimension_count": value.get("dimension_count", 0),
        "industry": value.get("industry"),
        "concept_count": value.get("concept_count", 0),
        "index_membership_count": value.get("index_membership_count", 0),
        "context_count": value.get("context_count", 0),
        "top_contexts": list(value.get("top_contexts", []))[:3] if isinstance(value.get("top_contexts"), list) else [],
        "score_bonus": value.get("score_bonus", 0),
        "explain": value.get("explain"),
    }


def compact_scan_context(value: Dict[str, object]) -> Dict[str, object]:
    return {
        "group_type": value.get("group_type"),
        "name": value.get("name"),
        "score": value.get("score"),
        "rank": value.get("rank"),
        "member_count": value.get("member_count", 0),
        "active_member_count": value.get("active_member_count", 0),
    }


def candidate_review_headline(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: str,
) -> str:
    best = contexts[0] if contexts else {}
    context_text = "%s%s" % (group_type_label(best.get("group_type")), best.get("name")) if best else "%s/%s" % (item.primary_layer, item.primary_sub_sector)
    return "%s %s | %s | %+s%% | 覆盖 %s" % (
        item.symbol,
        item.name,
        context_text,
        quote.change_pct,
        coverage_state,
    )


def candidate_classification(item: PoolItem, contexts: List[Dict[str, object]]) -> Dict[str, object]:
    primary_context = contexts[0] if contexts else {}
    return {
        "industry": item.raw.get("universe_industry"),
        "concepts": split_universe_values(item.raw.get("universe_concepts"))[:6],
        "index_membership": split_universe_values(item.raw.get("universe_index_membership"))[:6],
        "primary_layer": item.primary_layer,
        "primary_sub_sector": item.primary_sub_sector,
        "primary_context": {
            "group_type": primary_context.get("group_type"),
            "name": primary_context.get("name"),
            "score": primary_context.get("score"),
            "rank": primary_context.get("rank"),
        }
        if primary_context
        else {},
    }


def candidate_signal_drivers(quote: Quote, contexts: List[Dict[str, object]]) -> List[str]:
    drivers = [
        "change_pct=%+s" % quote.change_pct,
        "amount_ratio=%.2f" % quote.amount_ratio,
    ]
    if quote.is_stage_high:
        drivers.append("stage_high")
    if quote.is_limit_up:
        drivers.append("limit_up")
    if contexts:
        best = contexts[0]
        drivers.append(
            "context=%s%s score=%s"
            % (group_type_label(best.get("group_type")), best.get("name"), best.get("score"))
        )
    return drivers


def candidate_commands(symbol: object, coverage_state: str, pool: str) -> List[str]:
    commands = ["market-intel pool explain %s --text%s" % (symbol, pool_arg(pool))]
    if coverage_state == "foundation":
        commands.append("market-intel pool research --runtime --dry-run --json%s" % pool_arg(pool))
        commands.append("market-intel import research data/runtime/research_notes.todo.csv --dry-run --json")
    return commands


def candidate_done_when(coverage_state: str) -> str:
    if coverage_state == "foundation":
        return "已补齐 reviewed research_notes，且核心逻辑、关键证据、证伪风险三项齐全。"
    if coverage_state == "draft":
        return "已确认候选补池行的行业/主题链路、角色、公司逻辑和证伪风险。"
    return "已解释今日板块上下文、行情来源、主要风险和后续证伪条件。"


def candidate_sort_key(row: Dict[str, object]):
    quote = row.get("quote", {}) if isinstance(row.get("quote"), dict) else {}
    return (
        -float(row.get("review_score") or 0),
        not bool(row.get("is_holding")),
        -float(quote.get("change_pct") or 0),
        str(row.get("symbol") or ""),
    )


def build_candidate_queue(candidates: List[Dict[str, object]]) -> Dict[str, object]:
    buckets = {
        "review_now": {
            "label": "先看",
            "summary": "分数高、共振较强或持仓相关，适合优先复盘。",
            "items": [],
        },
        "deprioritized": {
            "label": "降权",
            "summary": "追高、回落、弱共振或缺上下文，先降权解读。",
            "items": [],
        },
        "data_first": {
            "label": "补数据",
            "summary": "覆盖或研究证据不足，先补资料再正式复盘。",
            "items": [],
        },
    }
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        lane = candidate_queue_lane(candidate)
        row = compact_candidate_queue_item(candidate, lane)
        buckets[lane]["items"].append(row)

    for bucket in buckets.values():
        items = bucket["items"]
        items.sort(key=lambda row: (-float(row.get("review_score") or 0), int(row.get("rank") or 9999)))
        bucket["count"] = len(items)
        bucket["items"] = items[:5]

    return {
        "summary": candidate_queue_summary(buckets),
        "buckets": buckets,
    }


def candidate_queue_lane(candidate: Dict[str, object]) -> str:
    coverage_state = str(candidate.get("coverage_state") or "")
    risk_flags = candidate.get("risk_flags", []) if isinstance(candidate.get("risk_flags"), list) else []
    ranking = candidate.get("ranking_breakdown", {}) if isinstance(candidate.get("ranking_breakdown"), dict) else {}
    penalty_score = float(ranking.get("penalty_score") or 0)
    review_score = float(candidate.get("review_score") or 0)

    if coverage_state in {"foundation", "draft"} or "invalid_symbol" in risk_flags:
        return "data_first"
    if (
        penalty_score >= 8
        or "intraday_fade_risk" in risk_flags
        or "weak_price_context" in risk_flags
        or ("chase_high_risk" in risk_flags and review_score < 90)
    ):
        return "deprioritized"
    return "review_now"


def compact_candidate_queue_item(candidate: Dict[str, object], lane: str) -> Dict[str, object]:
    commands = candidate.get("commands", []) if isinstance(candidate.get("commands"), list) else []
    return {
        "rank": candidate.get("rank"),
        "symbol": candidate.get("symbol"),
        "name": candidate.get("name"),
        "lane": lane,
        "review_score": candidate.get("review_score"),
        "coverage_state": candidate.get("coverage_state"),
        "is_holding": bool(candidate.get("is_holding")),
        "reason": candidate_queue_reason(candidate, lane),
        "next_command": commands[0] if commands else "",
    }


def candidate_queue_reason(candidate: Dict[str, object], lane: str) -> str:
    ranking = candidate.get("ranking_breakdown", {}) if isinstance(candidate.get("ranking_breakdown"), dict) else {}
    summary = str(ranking.get("summary") or "").strip()
    coverage_state = str(candidate.get("coverage_state") or "")
    if lane == "data_first":
        return "覆盖 %s，先补关键字段或研究证据；%s" % (coverage_state or "-", summary)
    if lane == "deprioritized":
        return "风险降权 %.0f；%s" % (float(ranking.get("penalty_score") or 0), summary)
    return summary or str(candidate.get("why_now") or "")


def candidate_queue_summary(buckets: Dict[str, Dict[str, object]]) -> str:
    return "先看 %s，降权 %s，补数据 %s。" % (
        buckets["review_now"].get("count", 0),
        buckets["deprioritized"].get("count", 0),
        buckets["data_first"].get("count", 0),
    )


def scan_summary(
    quotes: List[Quote],
    quoted_items: List[Tuple[PoolItem, Quote]],
    groups: List[Dict[str, object]],
    candidates: List[Dict[str, object]],
    scan_mode: str,
    market_breadth: Dict[str, object],
) -> str:
    mode_text = "全 A 基础清单" if scan_mode == "all_a_universe" else "复盘池链路种子"
    top_group = groups[0] if groups else {}
    top_candidate = candidates[0] if candidates else {}
    group_text = "暂无板块强弱"
    if top_group:
        group_text = "%s%s %.2f" % (
            group_type_label(top_group.get("group_type")),
            top_group.get("name"),
            float(top_group.get("score") or 0),
        )
    candidate_text = "暂无候选"
    if top_candidate:
        candidate_text = "%s %s" % (top_candidate.get("symbol"), top_candidate.get("name"))
    breadth_text = market_breadth.get("summary") or "暂无宽度摘要。"
    return "%s 扫描：行情 %s 条，匹配复盘池 %s 条，板块 %s 个；%s；最强 %s；首个候选 %s。" % (
        mode_text,
        len(quotes),
        len(quoted_items),
        len(groups),
        breadth_text.rstrip("。"),
        group_text,
        candidate_text,
    )


def scan_questions(groups: List[Dict[str, object]], candidates: List[Dict[str, object]], scan_mode: str) -> List[str]:
    questions = []
    if scan_mode != "all_a_universe":
        questions.append("当前扫描仍依赖种子池链路，是否需要先导入更完整的 A 股行业、概念和指数成分？")
    if groups:
        strongest = groups[0]
        questions.append("%s%s 的强度来自多标的共振，还是少数标的拉动？" % (group_type_label(strongest.get("group_type")), strongest.get("name")))
    if any(candidate.get("coverage_state") != "confirmed" for candidate in candidates):
        questions.append("哪些候选仍是 foundation/draft 覆盖，需要补研究证据后才能进入正式复盘？")
    if any("intraday_fade_risk" in candidate.get("risk_flags", []) for candidate in candidates):
        questions.append("哪些候选的强度被日内回落削弱，需要降权解读？")
    return dedupe(questions)[:5]


def scan_next_actions(scan_mode: str, pool: str) -> List[Dict[str, object]]:
    actions = [
        {
            "rank": 1,
            "id": "review_scan_candidates",
            "command": "market-intel scan --runtime --text%s" % pool_arg(pool),
            "done_when": "已确认板块强弱、候选复盘标的和覆盖状态。",
        }
    ]
    if scan_mode != "all_a_universe":
        actions.append(
            {
                "rank": 2,
                "id": "import_a_share_universe",
                "command": "market-intel import universe <a_share_universe.csv> --runtime --dry-run --json",
                "done_when": "已导入行业、概念、指数成分字段，scan_mode 变为 all_a_universe。",
            }
        )
    actions.append(
        {
            "rank": len(actions) + 1,
            "id": "handoff_to_focus",
            "command": "market-intel focus --runtime --text%s" % pool_arg(pool),
            "done_when": "已把扫描候选和个人持仓复盘放到同一张日常第一屏里核对。",
        }
    )
    return actions


def scan_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.summary",
            "data.scan_mode",
            "data.market_breadth",
            "data.market_breadth.confidence",
            "data.coverage_context",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.top_data_quality_queue",
            "data.sector_groups",
            "data.sector_groups[].group_type",
            "data.sector_groups[].score",
            "data.sector_groups[].leaders",
            "data.candidate_securities",
            "data.candidate_queue",
            "data.candidate_queue.buckets.review_now.items",
            "data.candidate_queue.buckets.deprioritized.items",
            "data.candidate_queue.buckets.data_first.items",
            "data.candidate_securities[].review_score",
            "data.candidate_securities[].ranking_breakdown",
            "data.candidate_securities[].universe_context",
            "data.candidate_securities[].coverage_state",
            "data.candidate_securities[].research_status",
            "data.candidate_securities[].review_focus",
            "data.candidate_securities[].review_focus.classification",
            "data.candidate_securities[].review_focus.coverage",
            "data.candidate_securities[].review_focus.universe_context",
            "data.candidate_securities[].review_focus.ranking_breakdown",
            "data.candidate_securities[].review_focus.next_command",
            "data.candidate_securities[].why_now",
            "data.candidate_securities[].checklist",
            "data.candidate_securities[].commands",
            "data.next_actions",
        ],
        "priority_values": ["high_review", "medium_review", "normal_review"],
        "boundary": "scan 是全 A/复盘池扫描工具，不生成交易动作、目标价或仓位建议。",
    }


def has_universe_context(item: PoolItem) -> bool:
    raw = item.raw if isinstance(item.raw, dict) else {}
    return bool(raw.get("universe_schema") or str(raw.get("pool_source") or "").startswith("universe:"))


def group_type_label(value: object) -> str:
    labels = {
        "industry": "行业",
        "concept": "概念",
        "index": "指数",
        "chain": "链路",
        "unknown": "分组",
    }
    return labels.get(str(value), str(value or "分组"))


def pool_arg(pool: str) -> str:
    return "" if pool == "all-a" else " --pool %s" % pool


def priority_label(score: float) -> str:
    if score >= 70:
        return "high_review"
    if score >= 40:
        return "medium_review"
    return "normal_review"


def leader_names(leaders: List[Dict[str, object]]) -> str:
    parts = [str(leader.get("name") or leader.get("symbol")) for leader in leaders[:3] if isinstance(leader, dict)]
    return "、".join(parts) if parts else "无"


def average(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0
    return sum(values) / len(values)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def dedupe(values: List[str]) -> List[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
