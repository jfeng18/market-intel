from collections import Counter
from typing import Dict, List, Optional

from .models import Holding, PoolItem
from .normalize import find_pool_item
from .pool_loader import pool_definition


CN_A_PREFIXES = {
    "000": "深市主板",
    "001": "深市主板",
    "002": "中小板",
    "003": "深市主板",
    "300": "创业板",
    "301": "创业板",
    "600": "沪市主板",
    "601": "沪市主板",
    "603": "沪市主板",
    "605": "沪市主板",
    "688": "科创板",
}


def build_pool_coverage(
    pool: str,
    items: List[PoolItem],
    holdings: Optional[List[Holding]] = None,
) -> Dict[str, object]:
    definition = pool_definition(pool)
    tradable = [item for item in items if item.tradable and item.symbol]
    cn_a = [item for item in tradable if item.market == "CN_A"]
    data_quality = data_quality_summary(items)
    scope = str(definition.get("scope") or "")
    holdings_coverage = build_holdings_coverage(items, holdings)
    return {
        "pool": pool,
        "scope": scope,
        "description": definition.get("description"),
        "status": coverage_status(scope, data_quality),
        "summary": coverage_summary(pool, scope, items, tradable, cn_a, data_quality),
        "counts": {
            "items": len(items),
            "tradable": len(tradable),
            "cn_a": len(cn_a),
            "non_cn_a": len(tradable) - len(cn_a),
            "non_tradable": len(items) - len(tradable),
            "data_quality_flagged": data_quality["flagged_item_count"],
        },
        "market_distribution": counter_rows(item.market for item in tradable),
        "layer_distribution": layer_rows(items),
        "cn_a_board_distribution": counter_rows(cn_a_board(item.symbol) for item in cn_a),
        "data_quality": data_quality,
        "holdings_coverage": holdings_coverage,
        "gaps": coverage_gaps(scope, items, cn_a, data_quality, holdings_coverage),
        "next_actions": coverage_next_actions(pool, scope, holdings_coverage),
        "agent_contract": coverage_contract(),
        "guardrails": coverage_guardrails(scope),
    }


def coverage_status(scope: str, data_quality: Dict[str, object]) -> str:
    if scope == "all_a_seed":
        return "seed"
    if data_quality.get("flagged_item_count"):
        return "needs_review"
    return "ready"


def coverage_summary(
    pool: str,
    scope: str,
    items: List[PoolItem],
    tradable: List[PoolItem],
    cn_a: List[PoolItem],
    data_quality: Dict[str, object],
) -> str:
    base = (
        "%s 当前 %s 个条目、%s 个可交易标的、%s 个 A 股标的；数据质量待复核 %s 个。"
        % (pool, len(items), len(tradable), len(cn_a), data_quality.get("flagged_item_count", 0))
    )
    if scope == "all_a_seed":
        return base + "这是全 A 种子覆盖，不应当作完整全 A 覆盖。"
    return base


def data_quality_summary(items: List[PoolItem]) -> Dict[str, object]:
    flag_counter = Counter()
    flagged_symbols = []
    for item in items:
        flags = sorted(set(item.data_quality_flags))
        if not flags:
            continue
        flag_counter.update(flags)
        flagged_symbols.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "flags": flags,
            }
        )
    return {
        "flagged_item_count": len(flagged_symbols),
        "top_flags": counter_dicts(flag_counter, limit=8),
        "sample_items": flagged_symbols[:8],
    }


def layer_rows(items: List[PoolItem]) -> List[Dict[str, object]]:
    rows = []
    by_layer: Dict[str, List[PoolItem]] = {}
    for item in items:
        for layer in sorted({exposure.layer for exposure in item.exposures}):
            by_layer.setdefault(layer, []).append(item)
    for layer, layer_items in by_layer.items():
        tradable = [item for item in layer_items if item.tradable and item.symbol]
        rows.append(
            {
                "layer": layer,
                "item_count": len(layer_items),
                "tradable_count": len(tradable),
                "cn_a_count": sum(1 for item in tradable if item.market == "CN_A"),
            }
        )
    rows.sort(key=lambda row: (-int(row["tradable_count"]), str(row["layer"])))
    return rows


def build_holdings_coverage(
    items: List[PoolItem],
    holdings: Optional[List[Holding]],
) -> Dict[str, object]:
    if holdings is None:
        return {
            "available": False,
            "reason": "未提供持仓；可用 --mock、--runtime 或 --holdings-file 查看个人持仓覆盖。",
            "holding_count": 0,
            "matched_count": 0,
            "unmatched_count": 0,
            "matched_ratio": 0,
            "matched": [],
            "unmatched": [],
            "by_market": [],
            "coverage_flags": [],
            "summary": "未提供持仓，当前报告只说明复盘池本身的覆盖边界。",
        }

    matched = []
    unmatched = []
    market_counter = Counter()
    for holding in holdings:
        item = find_pool_item(items, holding.symbol)
        if item is None:
            unmatched.append(
                {
                    "symbol": holding.symbol,
                    "name": holding.name,
                    "reason": "not_in_pool",
                    "suggested_action": "确认该持仓是否需要纳入当前复盘池，或保留为池外持仓单独复核。",
                }
            )
            continue

        market_counter.update([item.market])
        matched.append(
            {
                "symbol": holding.symbol,
                "name": holding.name or item.name,
                "pool_name": item.name,
                "market": item.market,
                "primary_layer": item.primary_layer,
                "primary_sub_sector": item.primary_sub_sector,
                "exposure_count": len(item.exposures),
                "data_quality_flags": sorted(set(item.data_quality_flags)),
            }
        )

    holding_count = len(holdings)
    matched_count = len(matched)
    unmatched_count = len(unmatched)
    ratio = round(matched_count / holding_count, 4) if holding_count else 0
    flags = ["unmatched_holdings"] if unmatched else []
    return {
        "available": True,
        "holding_count": holding_count,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "matched_ratio": ratio,
        "matched": matched[:20],
        "unmatched": unmatched[:20],
        "by_market": counter_dicts(market_counter),
        "coverage_flags": flags,
        "summary": build_holdings_coverage_summary(holding_count, matched_count, unmatched_count, ratio),
    }


def build_holdings_coverage_summary(
    holding_count: int,
    matched_count: int,
    unmatched_count: int,
    ratio: float,
) -> str:
    if holding_count == 0:
        return "已提供持仓源，但持仓为空。"
    if unmatched_count:
        return "持仓覆盖率 %.1f%%，%s 个持仓未匹配当前复盘池。" % (ratio * 100, unmatched_count)
    return "持仓覆盖率 %.1f%%，当前持仓均已匹配复盘池。" % (ratio * 100)


def coverage_gaps(
    scope: str,
    items: List[PoolItem],
    cn_a: List[PoolItem],
    data_quality: Dict[str, object],
    holdings_coverage: Dict[str, object],
) -> List[Dict[str, object]]:
    gaps = []
    if scope == "all_a_seed":
        gaps.append(
            {
                "id": "all_a_seed_only",
                "severity": "high",
                "message": "当前 all-a 仍是种子覆盖，尚未接入完整 A 股行业、概念或指数成分。",
            }
        )
    if len(cn_a) < max(100, len(items) // 2):
        gaps.append(
            {
                "id": "cn_a_coverage_thin",
                "severity": "medium",
                "message": "A 股覆盖偏薄，全市场复盘应先接入更完整的 A 股基础池。",
            }
        )
    if data_quality.get("flagged_item_count"):
        gaps.append(
            {
                "id": "data_quality_flags",
                "severity": "medium",
                "message": "复盘池存在数据质量标记，需要清理 pending、非证券行、列偏移或缺角色问题。",
            }
        )
    if holdings_coverage.get("available") and holdings_coverage.get("unmatched_count"):
        gaps.append(
            {
                "id": "holding_coverage_gap",
                "severity": "high",
                "message": "存在持仓未匹配当前复盘池，个人复盘会遗漏这些标的的链路暴露。",
            }
        )
    return gaps


def coverage_next_actions(
    pool: str,
    scope: str,
    holdings_coverage: Dict[str, object],
) -> List[Dict[str, object]]:
    pool_arg = "" if pool == "all-a" else " --pool %s" % pool
    actions = [
        {
            "rank": 1,
            "id": "inspect_coverage",
            "command": "market-intel pool coverage --text%s" % pool_arg,
            "done_when": "已确认当前复盘池的覆盖边界、市场分布、层级分布和数据质量短板。",
        }
    ]
    if scope == "all_a_seed":
        actions.append(
            {
                "rank": 2,
                "id": "expand_all_a_sources",
                "command": "market-intel import schema --json",
                "done_when": "已准备行业、概念、指数成分或自选股 CSV/JSON 的导入格式。",
            }
        )
    if not holdings_coverage.get("available"):
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "check_holdings_coverage",
                "command": "market-intel pool coverage --runtime --text%s" % pool_arg,
                "done_when": "已确认个人持仓是否被当前复盘池覆盖。",
            }
        )
    elif holdings_coverage.get("unmatched_count"):
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "review_unmatched_holdings",
                "command": "market-intel portfolio review --runtime --text%s" % pool_arg,
                "done_when": "已确认未覆盖持仓是否补入复盘池、暂列池外，或修正代码/名称。",
            }
        )
    actions.append(
        {
            "rank": len(actions) + 1,
            "id": "run_focus",
            "command": "market-intel focus --runtime --text%s" % pool_arg,
            "done_when": "已用当前复盘池生成日常第一屏，并理解其覆盖边界。",
        }
    )
    return actions


def coverage_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 errors=[]",
        "stable_fields": [
            "data.pool",
            "data.scope",
            "data.status",
            "data.counts",
            "data.market_distribution",
            "data.layer_distribution",
            "data.cn_a_board_distribution",
            "data.data_quality",
            "data.holdings_coverage",
            "data.gaps",
            "data.next_actions",
            "data.guardrails",
        ],
        "boundary": "覆盖度报告只说明复盘池边界，不生成交易动作、目标价或仓位建议。",
    }


def coverage_guardrails(scope: str) -> List[str]:
    guardrails = ["覆盖度用于判断复盘池边界，不生成买卖指令、目标价或仓位建议。"]
    if scope == "all_a_seed":
        guardrails.append("all-a 当前为种子覆盖；接入行业/概念/指数成分数据前，应降权解读全 A 结论。")
    else:
        guardrails.append("主题池只说明该主题覆盖，不代表全市场结论。")
    return guardrails


def cn_a_board(symbol: object) -> str:
    text = str(symbol or "")
    for prefix, board in CN_A_PREFIXES.items():
        if text.startswith(prefix):
            return board
    return "其他 A 股"


def counter_rows(values) -> List[Dict[str, object]]:
    return counter_dicts(Counter(str(value or "UNKNOWN") for value in values))


def counter_dicts(counter: Counter, limit: int = 20) -> List[Dict[str, object]]:
    rows = [{"name": key, "count": count} for key, count in counter.items()]
    rows.sort(key=lambda row: (-int(row["count"]), str(row["name"])))
    return rows[:limit]
