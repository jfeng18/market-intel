from typing import Dict, List, Optional

from .holdings import calculate_holding_impacts
from .models import Holding, Hotspot, PoolItem, Quote
from .scoring import calculate_hotspots


LAYER_ORDER = ["算力", "运力", "存力", "电力", "人才密度", "其他"]


def build_market_map(
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    top: int = 3,
) -> Dict[str, object]:
    all_hotspots = calculate_hotspots(items, quotes, top=max(1000, len(items)))
    holding_impact = calculate_holding_impacts(items, holdings)
    layers = [
        build_layer_row(layer, items, quotes, holdings, holding_impact, all_hotspots, top=top)
        for layer in ordered_layers(items, all_hotspots, holding_impact)
    ]
    strongest = next((hotspot for hotspot in all_hotspots if hotspot.score > 0), None)
    unmatched = unmatched_holdings(holding_impact)
    risk_flags = set(flag for layer in layers for flag in layer["risk_flags"])
    if unmatched:
        risk_flags.add("unmatched_holdings")

    return {
        "summary": build_summary(layers, holdings, strongest, risk_flags),
        "layer_count": len(layers),
        "holding_count": len(holdings),
        "hotspot_count": len(all_hotspots),
        "strongest_hotspot": strongest.to_dict() if strongest else None,
        "layers": layers,
        "risk_flags": sorted(risk_flags),
        "unmatched_holdings": unmatched,
        "guardrails": [
            "这是链路地图，不是交易指令。",
            "只展示题材、持仓暴露和风险复核点，不生成交易动作、目标价或仓位建议。",
        ],
    }


def ordered_layers(
    items: List[PoolItem],
    hotspots: List[Hotspot],
    holding_impact: Dict[str, object],
) -> List[str]:
    seen = {
        exposure.layer
        for item in items
        for exposure in item.exposures
    }
    seen.update(hotspot.layer for hotspot in hotspots)
    for impact in holding_impact.get("impacts", []):
        if not isinstance(impact, dict):
            continue
        for exposure in impact.get("exposures", []):
            if isinstance(exposure, dict):
                seen.add(str(exposure.get("layer") or "其他"))

    ordered = [layer for layer in LAYER_ORDER if layer in seen]
    ordered.extend(sorted(layer for layer in seen if layer not in LAYER_ORDER))
    return ordered


def build_layer_row(
    layer: str,
    items: List[PoolItem],
    quotes: List[Quote],
    holdings: List[Holding],
    holding_impact: Dict[str, object],
    hotspots: List[Hotspot],
    top: int,
) -> Dict[str, object]:
    quote_by_symbol = {quote.symbol: quote for quote in quotes}
    layer_items = items_in_layer(items, layer)
    layer_hotspots = [hotspot for hotspot in hotspots if hotspot.layer == layer]
    layer_hotspots.sort(key=lambda hotspot: (-hotspot.score, hotspot.sub_sector))
    layer_holdings = holdings_in_layer(holdings, holding_impact, quote_by_symbol, layer)
    repeated = repeated_exposures_for_layer(holding_impact, layer)
    risks = layer_risks(layer_hotspots, layer_holdings, repeated)

    return {
        "layer": layer,
        "pool_item_count": len(layer_items),
        "quoted_item_count": sum(1 for item in layer_items if item.symbol in quote_by_symbol),
        "hotspot_count": len(layer_hotspots),
        "top_hotspots": [hotspot.to_dict() for hotspot in layer_hotspots[:top]],
        "holding_count": len(layer_holdings),
        "holdings": layer_holdings,
        "repeated_exposures": repeated,
        "risk_flags": risks,
        "explain": build_layer_explain(layer, layer_hotspots, layer_holdings, repeated, risks),
    }


def items_in_layer(items: List[PoolItem], layer: str) -> List[PoolItem]:
    results = []
    for item in items:
        if any(exposure.layer == layer for exposure in item.exposures):
            results.append(item)
    return results


def holdings_in_layer(
    holdings: List[Holding],
    holding_impact: Dict[str, object],
    quote_by_symbol: Dict[str, Quote],
    layer: str,
) -> List[Dict[str, object]]:
    holding_by_symbol = {holding.symbol: holding for holding in holdings}
    rows = []
    for impact in holding_impact.get("impacts", []):
        if not isinstance(impact, dict):
            continue
        exposures = [
            exposure
            for exposure in impact.get("exposures", [])
            if isinstance(exposure, dict) and exposure.get("layer") == layer
        ]
        if not exposures:
            continue
        symbol = str(impact.get("holding_symbol"))
        quote = quote_by_symbol.get(symbol)
        holding = holding_by_symbol.get(symbol)
        rows.append(
            {
                "symbol": symbol,
                "name": impact.get("holding_name") or (holding.name if holding else ""),
                "sub_sectors": sorted(set(str(exposure.get("sub_sector") or "") for exposure in exposures)),
                "exposure_count": len(exposures),
                "change_pct": quote.change_pct if quote else None,
                "amount_ratio": quote.amount_ratio if quote else None,
                "intraday_fade_pct": quote.intraday_fade_pct if quote else None,
                "risks": list(impact.get("impact", {}).get("risk_flags", []))
                if isinstance(impact.get("impact"), dict)
                else [],
                "has_quote": quote is not None,
            }
        )
    rows.sort(key=holding_sort_key)
    return rows


def holding_sort_key(row: Dict[str, object]):
    change_pct = row.get("change_pct")
    if change_pct is None:
        return (1, 0, str(row.get("symbol") or ""))
    return (0, -float(change_pct), str(row.get("symbol") or ""))


def repeated_exposures_for_layer(
    holding_impact: Dict[str, object],
    layer: str,
) -> List[Dict[str, object]]:
    prefix = "%s/" % layer
    return [
        group
        for group in holding_impact.get("repeated_exposures", [])
        if isinstance(group, dict) and str(group.get("group") or "").startswith(prefix)
    ]


def layer_risks(
    hotspots: List[Hotspot],
    holdings: List[Dict[str, object]],
    repeated_exposures: List[Dict[str, object]],
) -> List[str]:
    risks = set()
    for hotspot in hotspots:
        risks.update(hotspot.risks)
    for holding in holdings:
        risks.update(str(risk) for risk in holding.get("risks", []))
        if not holding.get("has_quote"):
            risks.add("holding_missing_quote")
    if repeated_exposures:
        risks.add("theme_concentration")
    if holdings and not hotspots:
        risks.add("no_hotspot_context")
    return sorted(risks)


def build_layer_explain(
    layer: str,
    hotspots: List[Hotspot],
    holdings: List[Dict[str, object]],
    repeated_exposures: List[Dict[str, object]],
    risks: List[str],
) -> str:
    parts = [
        "%s: 热点 %s 个，持仓暴露 %s 个。" % (layer, len(hotspots), len(holdings)),
    ]
    if hotspots:
        top = hotspots[0]
        parts.append("最强子链路为 %s，分数 %.2f。" % (top.sub_sector, top.score))
    if repeated_exposures:
        parts.append("存在重复持仓暴露。")
    if risks:
        parts.append("风险标签 %s 个。" % len(risks))
    return "".join(parts)


def build_summary(
    layers: List[Dict[str, object]],
    holdings: List[Holding],
    strongest: Optional[Hotspot],
    risk_flags: List[str],
) -> str:
    active_layers = sum(1 for layer in layers if layer.get("hotspot_count"))
    holding_layers = sum(1 for layer in layers if layer.get("holding_count"))
    parts = [
        "链路层级 %s 个，存在热点的层级 %s 个，持仓覆盖层级 %s 个，持仓标的 %s 个。"
        % (len(layers), active_layers, holding_layers, len(holdings))
    ]
    if strongest:
        parts.append(
            "当前最强子链路：%s / %s，分数 %.2f。"
            % (strongest.layer, strongest.sub_sector, strongest.score)
        )
    if risk_flags:
        parts.append("需复核风险标签 %s 个。" % len(risk_flags))
    return "".join(parts)


def unmatched_holdings(holding_impact: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for impact in holding_impact.get("impacts", []):
        if not isinstance(impact, dict) or impact.get("matched_pool_item"):
            continue
        rows.append(
            {
                "symbol": impact.get("holding_symbol"),
                "name": impact.get("holding_name"),
                "risks": impact.get("impact", {}).get("risk_flags", [])
                if isinstance(impact.get("impact"), dict)
                else [],
            }
        )
    return rows
