from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from .models import Hotspot, PoolItem, Quote


def calculate_hotspots(items: List[PoolItem], quotes: List[Quote], top: int = 10) -> List[Hotspot]:
    quote_by_symbol = {quote.symbol: quote for quote in quotes}
    groups: Dict[Tuple[str, str], List[Tuple[PoolItem, Quote]]] = defaultdict(list)

    for item in items:
        if not item.symbol or not item.tradable:
            continue
        quote = quote_by_symbol.get(item.symbol)
        if quote is None:
            continue
        seen = set()
        for exposure in item.exposures:
            key = (exposure.layer, exposure.sub_sector)
            if key in seen:
                continue
            groups[key].append((item, quote))
            seen.add(key)

    hotspots = [
        build_hotspot(layer, sub_sector, members)
        for (layer, sub_sector), members in groups.items()
        if members
    ]
    hotspots.sort(key=lambda hotspot: (-hotspot.score, hotspot.layer, hotspot.sub_sector))
    return hotspots[:top]


def build_hotspot(layer: str, sub_sector: str, members: List[Tuple[PoolItem, Quote]]) -> Hotspot:
    quotes = [quote for _, quote in members]
    avg_change = average(quote.change_pct for quote in quotes)
    avg_amount_ratio = average(quote.amount_ratio for quote in quotes)
    strong_count = sum(1 for quote in quotes if quote.change_pct >= 5 or quote.is_limit_up)
    active_count = sum(1 for quote in quotes if quote.change_pct >= 3 or quote.amount_ratio >= 1.5)
    leader_item, leader_quote = max(members, key=lambda pair: pair[1].change_pct)
    leader_bonus = 15 if is_leader_role(leader_item.primary_role) else 0
    stage_high_ratio = sum(1 for quote in quotes if quote.is_stage_high) / len(quotes)
    avg_fade = average(quote.intraday_fade_pct for quote in quotes)

    breakdown = {
        "avg_change_score": clamp(avg_change * 10),
        "turnover_expansion_score": clamp(avg_amount_ratio * 25),
        "strong_member_score": clamp((strong_count / len(quotes)) * 100),
        "leader_strength_score": clamp(leader_quote.change_pct * 9 + leader_bonus),
        "persistence_score": clamp(stage_high_ratio * 70 + min(len(quotes), 5) * 6),
        "intraday_fade_penalty": clamp(avg_fade * 12),
    }
    score = clamp(
        breakdown["avg_change_score"] * 0.20
        + breakdown["turnover_expansion_score"] * 0.20
        + breakdown["strong_member_score"] * 0.20
        + breakdown["leader_strength_score"] * 0.20
        + breakdown["persistence_score"] * 0.10
        - breakdown["intraday_fade_penalty"] * 0.10
    )
    if active_count <= 1 or len(members) == 1:
        score = min(score, 45)

    leaders = [
        {
            "symbol": item.symbol,
            "name": item.name,
            "change_pct": quote.change_pct,
            "role": item.primary_role,
        }
        for item, quote in sorted(members, key=lambda pair: pair[1].change_pct, reverse=True)[:3]
    ]
    signals = hotspot_signals(score, active_count, len(members), strong_count, leader_item, leader_quote)
    risks = hotspot_risks(avg_fade, active_count, len(members), leader_quote, score)

    return Hotspot(
        layer=layer,
        sub_sector=sub_sector,
        score=round(score, 2),
        member_count=len(members),
        active_member_count=active_count,
        leaders=leaders,
        score_breakdown={key: round(value, 2) for key, value in breakdown.items()},
        signals=signals,
        risks=risks,
        explain=build_hotspot_explain(layer, sub_sector, score, leaders, signals, risks),
    )


def hotspot_signals(
    score: float,
    active_count: int,
    member_count: int,
    strong_count: int,
    leader_item: PoolItem,
    leader_quote: Quote,
) -> List[str]:
    signals = []
    if active_count >= 2:
        signals.append("sector_resonance")
    elif active_count == 1:
        signals.append("single_name_move")
    if strong_count >= 1:
        signals.append("strong_members")
    if leader_quote.change_pct >= 5 and is_leader_role(leader_item.primary_role):
        signals.append("leader_strength")
    if score >= 70:
        signals.append("high_hotspot_score")
    return signals


def hotspot_risks(
    avg_fade: float,
    active_count: int,
    member_count: int,
    leader_quote: Quote,
    score: float,
) -> List[str]:
    risks = []
    if member_count == 1 or active_count <= 1:
        risks.append("single_name_or_thin_resonance")
    if avg_fade >= 3:
        risks.append("intraday_fade_risk")
    if leader_quote.change_pct >= 8:
        risks.append("chase_high_risk")
    if score < 45:
        risks.append("weak_hotspot_score")
    if not risks:
        risks.append("continuation_needs_confirmation")
    return risks


def build_hotspot_explain(
    layer: str,
    sub_sector: str,
    score: float,
    leaders: List[Dict[str, object]],
    signals: List[str],
    risks: List[str],
) -> str:
    leader_text = "，".join("%s(%s%%)" % (leader["name"], leader["change_pct"]) for leader in leaders)
    signal_text = "，".join(signals) if signals else "暂无"
    risk_text = "，".join(risks) if risks else "暂无"
    return (
        "%s / %s 热点分 %.2f。领涨标的：%s。信号：%s。风险：%s。"
        % (layer, sub_sector, score, leader_text or "暂无", signal_text, risk_text)
    )


def is_leader_role(role: object) -> bool:
    text = str(role or "")
    return any(token in text for token in ("龙头", "龙一", "龙二", "核心", "全球"))


def average(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0
    return sum(values) / len(values)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))
