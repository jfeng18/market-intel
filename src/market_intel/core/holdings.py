from collections import Counter
from typing import Dict, List

from .models import Holding, PoolItem
from .normalize import find_pool_item


RISK_LABELS = {
    "multi_chain_exposure": "多链路暴露",
    "theme_overlap": "主题重叠",
    "not_in_pool": "未匹配池子",
}


def calculate_holding_impacts(items: List[PoolItem], holdings: List[Holding]) -> Dict[str, object]:
    impacts = [build_holding_impact(items, holding) for holding in holdings]
    exposure_counter = Counter()
    overlap_groups = Counter()

    for impact in impacts:
        exposure_groups = set()
        for exposure in impact["exposures"]:
            exposure_groups.add("%s/%s" % (exposure["layer"], exposure["sub_sector"]))
        exposure_counter.update(exposure_groups)
        for group in set(impact["overlap_groups"]):
            overlap_groups[group] += 1

    repeated_exposures = [
        {"group": group, "holding_count": count}
        for group, count in sorted(exposure_counter.items())
        if count >= 2
    ]
    repeated_overlap_groups = [
        {"group": group, "holding_count": count}
        for group, count in sorted(overlap_groups.items())
        if count >= 2
    ]
    risk_flags = []
    if repeated_exposures or repeated_overlap_groups:
        risk_flags.append("theme_concentration")
    unmatched = [impact["holding_symbol"] for impact in impacts if not impact["matched_pool_item"]]
    if unmatched:
        risk_flags.append("unmatched_holdings")

    return {
        "holding_count": len(holdings),
        "impacts": impacts,
        "repeated_exposures": repeated_exposures,
        "repeated_overlap_groups": repeated_overlap_groups,
        "risk_flags": risk_flags,
        "explain": build_summary_explain(repeated_exposures, repeated_overlap_groups, unmatched),
    }


def build_holding_impact(items: List[PoolItem], holding: Holding) -> Dict[str, object]:
    item = find_pool_item(items, holding.symbol)
    if item is None:
        return {
            "holding_symbol": holding.symbol,
            "holding_name": holding.name,
            "market": "UNKNOWN",
            "matched_pool_item": False,
            "exposures": [],
            "overlap_groups": [],
            "impact": {
                "benefit_hotspots": [],
                "pressure_hotspots": [],
                "risk_flags": ["not_in_pool"],
            },
            "explain": "%s 未匹配到 AI 能量池。" % holding.symbol,
        }

    exposures = [
        {
            "layer": exposure.layer,
            "sub_sector": exposure.sub_sector,
            "role": exposure.role,
        }
        for exposure in item.exposures
    ]
    overlap_groups = infer_overlap_groups(item)
    risk_flags = []
    if len(item.exposures) > 1:
        risk_flags.append("multi_chain_exposure")
    if overlap_groups:
        risk_flags.append("theme_overlap")

    return {
        "holding_symbol": holding.symbol,
        "holding_name": holding.name or item.name,
        "market": item.market,
        "matched_pool_item": True,
        "exposures": exposures,
        "overlap_groups": overlap_groups,
        "impact": {
            "benefit_hotspots": sorted(set(exposure["sub_sector"] for exposure in exposures)),
            "pressure_hotspots": [],
            "risk_flags": risk_flags,
        },
        "explain": build_holding_explain(holding, item, overlap_groups, risk_flags),
    }


def infer_overlap_groups(item: PoolItem) -> List[str]:
    text = " ".join(
        [item.name, item.logic, item.primary_sub_sector, item.primary_role or ""]
        + [exposure.logic for exposure in item.exposures]
        + [exposure.sub_sector for exposure in item.exposures]
    )
    groups = set()
    if "华为" in text or "昇腾" in text or "鲲鹏" in text:
        groups.add("华为昇腾")
    if "信创" in text:
        groups.add("信创服务器")
    if "光模块" in text or "CPO" in text or "硅光" in text:
        groups.add("光通信")
    if "半导体设备" in text or "测试" in text or "分选" in text:
        groups.add("半导体设备")
    if "IDC" in text or "AIDC" in text or "算力租赁" in text:
        groups.add("AIDC/IDC")
    return sorted(groups)


def build_holding_explain(
    holding: Holding,
    item: PoolItem,
    overlap_groups: List[str],
    risk_flags: List[str],
) -> str:
    groups = "，".join(overlap_groups) if overlap_groups else "无"
    risks = "，".join(label_risks(risk_flags)) if risk_flags else "无"
    return (
        "%s (%s) 对应 %s 条链路暴露。重叠主题：%s。风险标签：%s。"
        % (item.name, holding.symbol, len(item.exposures), groups, risks)
    )


def build_summary_explain(
    repeated_exposures: List[Dict[str, object]],
    repeated_overlap_groups: List[Dict[str, object]],
    unmatched: List[str],
) -> str:
    parts = []
    if repeated_exposures:
        parts.append("存在重复链路暴露。")
    if repeated_overlap_groups:
        parts.append("存在重复主题暴露。")
    if unmatched:
        parts.append("存在未匹配池子的持仓。")
    if not parts:
        parts.append("未发现重复暴露。")
    return " ".join(parts)


def label_risks(risk_flags: List[str]) -> List[str]:
    return [RISK_LABELS.get(flag, flag) for flag in risk_flags]
