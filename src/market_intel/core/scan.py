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
    symbol_context = build_symbol_context(groups)
    candidates = build_scan_candidates(quoted_items, holding_symbols, symbol_context, limit=candidate_top, pool=pool)
    scan_mode = "all_a_universe" if any(has_universe_context(item) for item, _ in quoted_items) else "pool_chain_seed"

    return {
        "summary": scan_summary(quotes, quoted_items, groups, candidates, scan_mode),
        "scan_mode": scan_mode,
        "quote_count": len(quotes),
        "matched_quote_count": len(quoted_items),
        "unmatched_quote_count": max(len(quotes) - len(quoted_items), 0),
        "holding_count": len(holdings),
        "trade_dates": sorted({quote.trade_date for quote in quotes if quote.trade_date}),
        "sector_groups": groups[:top],
        "candidate_securities": candidates,
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


def build_symbol_context(groups: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    by_symbol: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for group in groups:
        leaders = group.get("leaders", []) if isinstance(group.get("leaders"), list) else []
        for leader in leaders:
            if not isinstance(leader, dict):
                continue
            symbol = str(leader.get("symbol") or "")
            if not symbol:
                continue
            by_symbol[symbol].append(
                {
                    "key": group.get("key"),
                    "group_type": group.get("group_type"),
                    "layer": group.get("layer"),
                    "name": group.get("name"),
                    "score": group.get("score"),
                    "rank": group.get("rank"),
                    "signals": group.get("signals", []),
                    "risks": group.get("risks", []),
                }
            )
    for contexts in by_symbol.values():
        contexts.sort(key=lambda row: (-float(row.get("score") or 0), int(row.get("rank") or 9999)))
    return by_symbol


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
        review_score = candidate_review_score(item, quote, contexts, item.symbol in holding_symbols, risk_flags, research)
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
                "coverage_state": state["state"],
                "coverage_state_reasons": state["reasons"],
                "research_status": research,
                "risk_flags": risk_flags,
                "review_score": review_score,
                "priority": priority_label(review_score),
                "why_now": candidate_why_now(item, quote, contexts, state["state"], item.symbol in holding_symbols),
                "review_focus": candidate_review_focus(item, quote, contexts, state, research, risk_flags, checklist, commands, done_when),
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


def candidate_review_score(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    is_holding: bool,
    risk_flags: List[str],
    research: Dict[str, object],
) -> float:
    best_context_score = max([float(context.get("score") or 0) for context in contexts] or [0])
    score = min(max(quote.change_pct, 0) * 2.2, 22)
    score += min(quote.amount_ratio * 6, 18)
    score += min(best_context_score / 2, 40)
    if quote.is_stage_high:
        score += 8
    if is_holding:
        score += 8
    if "foundation_pool_match" in risk_flags or "draft_pool_match" in risk_flags:
        score += 10
    if research.get("available") and not research.get("confirmed"):
        score += 5
    if item.data_quality_flags:
        score += 5
    return round(clamp(score), 2)


def candidate_why_now(
    item: PoolItem,
    quote: Quote,
    contexts: List[Dict[str, object]],
    coverage_state: str,
    is_holding: bool,
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
        "signal_drivers": candidate_signal_drivers(quote, contexts),
        "risk_flags": risk_flags[:8],
        "first_check": checklist[0] if checklist else "",
        "next_command": commands[0] if commands else "",
        "done_when": done_when,
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


def scan_summary(
    quotes: List[Quote],
    quoted_items: List[Tuple[PoolItem, Quote]],
    groups: List[Dict[str, object]],
    candidates: List[Dict[str, object]],
    scan_mode: str,
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
    return "%s 扫描：行情 %s 条，匹配复盘池 %s 条，板块 %s 个；最强 %s；首个候选 %s。" % (
        mode_text,
        len(quotes),
        len(quoted_items),
        len(groups),
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
            "data.coverage_context",
            "data.coverage_context.universe.sector_profile",
            "data.coverage_context.top_data_quality_queue",
            "data.sector_groups",
            "data.sector_groups[].group_type",
            "data.sector_groups[].score",
            "data.sector_groups[].leaders",
            "data.candidate_securities",
            "data.candidate_securities[].review_score",
            "data.candidate_securities[].coverage_state",
            "data.candidate_securities[].research_status",
            "data.candidate_securities[].review_focus",
            "data.candidate_securities[].review_focus.classification",
            "data.candidate_securities[].review_focus.coverage",
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
