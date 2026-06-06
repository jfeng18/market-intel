from typing import Dict, List, Set

from .holdings import calculate_holding_impacts
from .models import Holding, PoolItem, Quote
from .scoring import calculate_hotspots


def build_watchlist_report(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    top: int = 20,
) -> Dict[str, object]:
    hotspots = calculate_hotspots(items, quotes, top=top)
    holding_impact = calculate_holding_impacts(items, holdings)
    holding_symbols = {
        impact["holding_symbol"]
        for impact in holding_impact.get("impacts", [])
        if impact.get("matched_pool_item")
    }
    holding_risks = {
        impact["holding_symbol"]: impact.get("impact", {}).get("risk_flags", [])
        for impact in holding_impact.get("impacts", [])
    }
    quote_by_symbol = {quote.symbol: quote for quote in quotes}
    rows = []
    seen: Set[str] = set()

    for hotspot in hotspots:
        for leader in hotspot.leaders:
            symbol = str(leader["symbol"])
            if symbol in seen:
                continue
            seen.add(symbol)
            quote = quote_by_symbol.get(symbol)
            risk_flags = list(hotspot.risks) + list(holding_risks.get(symbol, []))
            rows.append(
                {
                    "symbol": symbol,
                    "name": leader["name"],
                    "is_holding": symbol in holding_symbols,
                    "layer": hotspot.layer,
                    "sub_sector": hotspot.sub_sector,
                    "hotspot_score": hotspot.score,
                    "change_pct": leader["change_pct"],
                    "amount_ratio": quote.amount_ratio if quote else None,
                    "intraday_fade_pct": quote.intraday_fade_pct if quote else None,
                    "signals": hotspot.signals,
                    "risks": sorted(set(risk_flags)),
                    "focus": focus_label(symbol in holding_symbols, hotspot.score, leader["change_pct"], risk_flags),
                }
            )

    rows.sort(key=lambda row: (not row["is_holding"], -float(row["hotspot_score"]), -float(row["change_pct"])))
    rows = rows[:top]
    return {
        "count": len(rows),
        "items": rows,
        "holding_count": sum(1 for row in rows if row["is_holding"]),
        "risk_flags": sorted(set(flag for row in rows for flag in row["risks"])),
        "explain": build_watchlist_explain(rows),
    }


def focus_label(is_holding: bool, hotspot_score: float, change_pct: float, risk_flags: List[str]) -> str:
    if is_holding and "theme_concentration" in risk_flags:
        return "holding_risk_review"
    if is_holding:
        return "holding_watch"
    if hotspot_score >= 70 and change_pct >= 5:
        return "hotspot_leader_watch"
    if "single_name_or_thin_resonance" in risk_flags:
        return "thin_resonance_verify"
    return "watch"


def build_watchlist_explain(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "暂无观察清单。"
    holding_count = sum(1 for row in rows if row["is_holding"])
    return "观察项 %s 个，其中持仓 %s 个。" % (len(rows), holding_count)

