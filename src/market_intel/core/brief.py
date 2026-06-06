from typing import Dict, List

from .holdings import calculate_holding_impacts
from .models import Holding, Hotspot, PoolItem, Quote
from .scoring import calculate_hotspots


RISK_LABELS = {
    "chase_high_risk": "追高风险",
    "theme_concentration": "主题集中",
    "single_name_or_thin_resonance": "单票或弱共振",
    "intraday_fade_risk": "冲高回落风险",
    "weak_hotspot_score": "热点强度偏弱",
    "continuation_needs_confirmation": "持续性待确认",
    "no_hotspot_data": "缺少热点数据",
    "unmatched_holdings": "存在未匹配持仓",
}


def build_daily_brief(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    top: int = 5,
) -> Dict[str, object]:
    hotspots = calculate_hotspots(items, quotes, top=top)
    holding_impact = calculate_holding_impacts(items, holdings)
    top_hotspots = [hotspot.to_dict() for hotspot in hotspots]
    risk_flags = collect_brief_risks(hotspots, holding_impact)
    watchlist = build_watchlist(hotspots, holding_impact)
    questions = build_questions(hotspots, holding_impact)

    return {
        "summary": build_summary(hotspots, holding_impact, risk_flags),
        "top_hotspots": top_hotspots,
        "holding_impact": holding_impact,
        "watchlist": watchlist,
        "risk_flags": risk_flags,
        "questions": questions,
        "guardrails": [
            "这是市场情报，不是交易指令。",
            "不生成交易动作、目标价或仓位建议。",
            "信号需要结合来源核验和个人风险约束。",
        ],
    }


def collect_brief_risks(hotspots: List[Hotspot], holding_impact: Dict[str, object]) -> List[str]:
    risks = set(holding_impact.get("risk_flags", []))
    for hotspot in hotspots:
        risks.update(hotspot.risks)
    if not hotspots:
        risks.add("no_hotspot_data")
    return sorted(risks)


def build_watchlist(hotspots: List[Hotspot], holding_impact: Dict[str, object]) -> List[Dict[str, object]]:
    holding_symbols = {
        impact["holding_symbol"]
        for impact in holding_impact.get("impacts", [])
        if impact.get("matched_pool_item")
    }
    watch_items = []
    seen = set()
    for hotspot in hotspots:
        for leader in hotspot.leaders:
            symbol = leader["symbol"]
            if symbol in seen:
                continue
            seen.add(symbol)
            watch_items.append(
                {
                    "symbol": symbol,
                    "name": leader["name"],
                    "layer": hotspot.layer,
                    "sub_sector": hotspot.sub_sector,
                    "change_pct": leader["change_pct"],
                    "is_holding": symbol in holding_symbols,
                    "reason": "leader_in_hotspot" if hotspot.score >= 60 else "active_name_to_verify",
                }
            )
    return watch_items[:10]


def build_questions(hotspots: List[Hotspot], holding_impact: Dict[str, object]) -> List[str]:
    questions = []
    if hotspots:
        strongest = hotspots[0]
        questions.append(
            "%s / %s 是否能维持多标的共振，而不是单日异动？"
            % (strongest.layer, strongest.sub_sector)
        )
    if holding_impact.get("repeated_exposures"):
        questions.append("哪些持仓本质上暴露在同一条产业链？")
    if holding_impact.get("repeated_overlap_groups"):
        questions.append("重复主题暴露是否会放大同涨同跌风险？")
    questions.append("哪些信号有价格以外的来源证据？")
    return questions


def build_summary(
    hotspots: List[Hotspot],
    holding_impact: Dict[str, object],
    risk_flags: List[str],
) -> str:
    if hotspots:
        top = hotspots[0]
        top_text = "最强链路是 %s / %s，分数 %.2f" % (top.layer, top.sub_sector, top.score)
    else:
        top_text = "未识别到热点链路"
    holding_count = holding_impact.get("holding_count", 0)
    risk_text = ", ".join(label_risks(risk_flags)) if risk_flags else "暂无主要风险标签"
    return "%s。已检查持仓 %s 个。关键风险标签：%s。" % (
        top_text,
        holding_count,
        risk_text,
    )


def label_risks(risk_flags: List[str]) -> List[str]:
    return [RISK_LABELS.get(flag, flag) for flag in risk_flags]
