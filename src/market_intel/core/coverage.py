from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
import csv

from .models import Holding, PoolItem
from .normalize import find_pool_item, normalize_row
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

POOL_CSV_FIELDS = ["status", "priority", "section", "level", "company", "code", "desc", "notes"]


def build_pool_coverage(
    pool: str,
    items: List[PoolItem],
    holdings: Optional[List[Holding]] = None,
) -> Dict[str, object]:
    definition = pool_definition(pool)
    tradable = [item for item in items if item.tradable and item.symbol]
    cn_a = [item for item in tradable if item.market == "CN_A"]
    data_quality = data_quality_summary(items)
    universe = universe_summary(items)
    scope = str(definition.get("scope") or "")
    holdings_coverage = build_holdings_coverage(items, holdings)
    expansion_queue = build_expansion_queue(pool, scope, holdings_coverage)
    return {
        "pool": pool,
        "scope": scope,
        "description": definition.get("description"),
        "status": coverage_status(scope, data_quality),
        "summary": coverage_summary(pool, scope, items, tradable, cn_a, data_quality, universe),
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
        "universe": universe,
        "holdings_coverage": holdings_coverage,
        "expansion_queue": expansion_queue,
        "gaps": coverage_gaps(scope, items, cn_a, data_quality, holdings_coverage, universe),
        "next_actions": coverage_next_actions(pool, scope, holdings_coverage, expansion_queue, universe),
        "agent_contract": coverage_contract(),
        "guardrails": coverage_guardrails(scope, universe),
    }


def export_expansion_queue_csv(
    expansion_queue: List[Dict[str, object]],
    output_path: Path,
    dry_run: bool = False,
) -> Dict[str, object]:
    rows = expansion_candidate_rows(expansion_queue)
    written = False
    if rows and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=POOL_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        written = True
    return {
        "output": str(output_path),
        "record_count": len(rows),
        "written": written,
        "dry_run": dry_run,
        "fields": list(POOL_CSV_FIELDS),
        "rows": rows,
        "warnings": expansion_export_warnings(rows),
        "next_commands": expansion_export_next_commands(output_path, written, rows),
    }


def review_expansion_csv(csv_path: Path) -> Dict[str, object]:
    if not csv_path.exists():
        return expansion_review_result(
            csv_path,
            rows=[],
            blockers=[
                {
                    "code": "POOL_EXPANSION_FILE_NOT_FOUND",
                    "message": "Expansion CSV file does not exist.",
                    "detail": {"path": csv_path.name},
                }
            ],
            warnings=[],
        )

    rows = []
    blockers = []
    warnings = []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [field for field in POOL_CSV_FIELDS if field not in fieldnames]
        if missing:
            blockers.append(
                {
                    "code": "POOL_EXPANSION_COLUMNS_MISSING",
                    "message": "Expansion CSV is missing required columns.",
                    "detail": {"missing": missing, "expected": list(POOL_CSV_FIELDS)},
                }
            )
        for index, row in enumerate(reader, start=2):
            row_result = review_expansion_row(row, index)
            rows.append(row_result)
            blockers.extend(row_result["blockers"])
            warnings.extend(row_result["warnings"])

    if not rows and not blockers:
        blockers.append(
            {
                "code": "POOL_EXPANSION_EMPTY",
                "message": "Expansion CSV has no rows.",
                "detail": {"path": csv_path.name},
            }
        )
    return expansion_review_result(csv_path, rows, blockers, warnings)


def review_expansion_row(row: Dict[str, str], row_number: int) -> Dict[str, object]:
    blockers = []
    warnings = []
    normalized = normalize_row(row, row_number)
    symbol = normalized.symbol
    status = str(row.get("status") or "").strip().lower()
    required_missing = [field for field in ("section", "level", "desc") if is_pending_text(row.get(field))]
    if required_missing:
        blockers.append(
            {
                "code": "POOL_EXPANSION_REQUIRED_FIELDS_PENDING",
                "message": "Expansion row still has pending required fields.",
                "detail": {"row": row_number, "symbol": symbol or row.get("code"), "fields": required_missing},
            }
        )
    if status in {"candidate", "draft", ""}:
        blockers.append(
            {
                "code": "POOL_EXPANSION_STATUS_NOT_READY",
                "message": "Expansion row status must be reviewed before it is considered ready.",
                "detail": {"row": row_number, "symbol": symbol or row.get("code"), "status": status or "EMPTY"},
            }
        )
    if normalized.instrument_type != "security" or not normalized.tradable:
        blockers.append(
            {
                "code": "POOL_EXPANSION_NOT_TRADABLE",
                "message": "Expansion row does not normalize to a tradable security.",
                "detail": {"row": row_number, "symbol": symbol or row.get("code"), "instrument_type": normalized.instrument_type},
            }
        )
    flags = sorted(set(normalized.data_quality_flags))
    blocking_flags = [flag for flag in flags if flag in {"invalid_symbol", "missing_role", "column_shift_suspected"}]
    if blocking_flags:
        blockers.append(
            {
                "code": "POOL_EXPANSION_DATA_QUALITY_BLOCKERS",
                "message": "Expansion row has blocking data quality flags.",
                "detail": {"row": row_number, "symbol": symbol or row.get("code"), "flags": blocking_flags},
            }
        )
    nonblocking_flags = [flag for flag in flags if flag not in blocking_flags]
    if nonblocking_flags:
        warnings.append(
            {
                "code": "POOL_EXPANSION_DATA_QUALITY_WARNINGS",
                "message": "Expansion row has data quality warnings.",
                "detail": {"row": row_number, "symbol": symbol or row.get("code"), "flags": nonblocking_flags},
            }
        )

    return {
        "row": row_number,
        "symbol": symbol,
        "name": normalized.name,
        "status": status or None,
        "review_state": "ready" if not blockers else "blocked",
        "normalized": {
            "market": normalized.market,
            "instrument_type": normalized.instrument_type,
            "tradable": normalized.tradable,
            "primary_layer": normalized.primary_layer,
            "primary_sub_sector": normalized.primary_sub_sector,
            "primary_role": normalized.primary_role,
            "data_quality_flags": flags,
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def expansion_review_result(
    csv_path: Path,
    rows: List[Dict[str, object]],
    blockers: List[Dict[str, object]],
    warnings: List[Dict[str, object]],
) -> Dict[str, object]:
    ready_rows = [row for row in rows if isinstance(row, dict) and row.get("review_state") == "ready"]
    state = "ready" if rows and not blockers else "blocked"
    return {
        "input": csv_path.name,
        "row_count": len(rows),
        "ready_count": len(ready_rows),
        "blocked_count": len(rows) - len(ready_rows),
        "review_state": state,
        "rows": rows,
        "ready_rows": ready_rows,
        "blockers": blockers,
        "warnings": warnings,
        "next_commands": expansion_review_next_commands(csv_path, state),
    }


def expansion_review_next_commands(csv_path: Path, state: str) -> List[str]:
    path_text = command_path(csv_path)
    if state == "ready":
        return [
            "MARKET_INTEL_POOL_EXTRA_PATHS=%s market-intel pool coverage --runtime --text" % path_text,
            "MARKET_INTEL_POOL_EXTRA_PATHS=%s market-intel focus --runtime --text" % path_text,
        ]
    return [
        "Edit %s and resolve blockers." % csv_path.name,
        "market-intel pool expansion --review-file %s --json" % path_text,
    ]


def expansion_candidate_rows(expansion_queue: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for item in expansion_queue:
        if not isinstance(item, dict):
            continue
        candidate = item.get("candidate_pool_row")
        if not isinstance(candidate, dict):
            continue
        rows.append({field: str(candidate.get(field) or "") for field in POOL_CSV_FIELDS})
    return rows


def expansion_export_warnings(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not rows:
        return []
    return [
        {
            "code": "POOL_EXPANSION_NEEDS_REVIEW",
            "message": "Expansion CSV is a draft. Confirm section, level, desc, and notes before using it as a pool source.",
            "detail": {"record_count": len(rows), "required_fields": ["section", "level", "desc"]},
        }
    ]


def expansion_export_next_commands(
    output_path: Path,
    written: bool,
    rows: List[Dict[str, object]],
) -> List[str]:
    if not rows:
        return []
    path_text = command_path(output_path)
    commands = []
    if written:
        commands.append("MARKET_INTEL_POOL_EXTRA_PATHS=%s market-intel pool list --json" % path_text)
        commands.append("MARKET_INTEL_POOL_EXTRA_PATHS=%s market-intel pool coverage --runtime --text" % path_text)
    else:
        commands.append("market-intel pool expansion --runtime --output data/runtime/pool_expansion.csv --json")
    return commands


def command_path(path: Path) -> str:
    return str(path) if not path.is_absolute() else path.name


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
    universe: Dict[str, object],
) -> str:
    base = (
        "%s 当前 %s 个条目、%s 个可交易标的、%s 个 A 股标的；数据质量待复核 %s 个。"
        % (pool, len(items), len(tradable), len(cn_a), data_quality.get("flagged_item_count", 0))
    )
    if scope == "all_a_seed":
        if universe.get("available"):
            return base + "已接入 A 股基础清单 %s 条，但仍是种子覆盖，需要继续补行业/概念/指数成分和研究证据。" % (
                universe.get("record_count", 0)
            )
        return base + "这是全 A 种子覆盖，不应当作完整全 A 覆盖。"
    return base


def universe_summary(items: List[PoolItem]) -> Dict[str, object]:
    universe_items = [
        item
        for item in items
        if str(item.raw.get("pool_source") or "").startswith("universe:") or item.raw.get("universe_schema")
    ]
    if not universe_items:
        return {
            "available": False,
            "record_count": 0,
            "source_files": [],
            "industry_count": 0,
            "concept_count": 0,
            "index_membership_count": 0,
            "sample_items": [],
        }

    industries = {str(item.raw.get("universe_industry") or "").strip() for item in universe_items}
    concepts = set()
    indexes = set()
    for item in universe_items:
        concepts.update(split_universe_values(item.raw.get("universe_concepts")))
        indexes.update(split_universe_values(item.raw.get("universe_index_membership")))
    industries.discard("")
    source_files = sorted({str(item.raw.get("pool_source_file") or "") for item in universe_items if item.raw.get("pool_source_file")})
    return {
        "available": True,
        "schema": "a_share_universe_v1",
        "record_count": len(universe_items),
        "source_files": source_files,
        "industry_count": len(industries),
        "concept_count": len(concepts),
        "index_membership_count": len(indexes),
        "sample_items": [
            {
                "symbol": item.symbol,
                "name": item.name,
                "industry": item.raw.get("universe_industry"),
                "concepts": item.raw.get("universe_concepts"),
                "index_membership": item.raw.get("universe_index_membership"),
            }
            for item in universe_items[:8]
        ],
    }


def split_universe_values(value: object) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = []
    for chunk in text.replace("，", ";").replace(",", ";").replace("|", ";").replace("/", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


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
    review_queue = []
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
        state = matched_coverage_state(item)
        if state["state"] != "confirmed":
            review_queue.append(
                {
                    "symbol": holding.symbol,
                    "name": holding.name or item.name,
                    "coverage_state": state["state"],
                    "reasons": state["reasons"],
                    "command": "market-intel pool explain %s --runtime --text" % holding.symbol,
                    "done_when": "已确认该持仓的行业/主题链路、角色、核心逻辑和证伪风险。",
                }
            )
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
                "coverage_state": state["state"],
                "coverage_state_reasons": state["reasons"],
            }
        )

    holding_count = len(holdings)
    matched_count = len(matched)
    unmatched_count = len(unmatched)
    ratio = round(matched_count / holding_count, 4) if holding_count else 0
    draft_count = sum(1 for row in matched if row.get("coverage_state") == "draft")
    foundation_count = sum(1 for row in matched if row.get("coverage_state") == "foundation")
    needs_review_count = sum(1 for row in matched if row.get("coverage_state") != "confirmed")
    flags = []
    if unmatched:
        flags.append("unmatched_holdings")
    if needs_review_count:
        flags.append("draft_pool_matches")
    return {
        "available": True,
        "holding_count": holding_count,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "confirmed_count": matched_count - needs_review_count,
        "draft_matched_count": draft_count,
        "foundation_matched_count": foundation_count,
        "needs_review_count": needs_review_count,
        "matched_ratio": ratio,
        "matched": matched[:20],
        "unmatched": unmatched[:20],
        "review_queue": review_queue[:20],
        "by_market": counter_dicts(market_counter),
        "coverage_flags": flags,
        "summary": build_holdings_coverage_summary(holding_count, matched_count, unmatched_count, ratio, needs_review_count),
    }


def build_holdings_coverage_summary(
    holding_count: int,
    matched_count: int,
    unmatched_count: int,
    ratio: float,
    needs_review_count: int = 0,
) -> str:
    if holding_count == 0:
        return "已提供持仓源，但持仓为空。"
    if unmatched_count:
        return "持仓覆盖率 %.1f%%，%s 个持仓未匹配当前复盘池。" % (ratio * 100, unmatched_count)
    if needs_review_count:
        return "持仓覆盖率 %.1f%%，但 %s 个匹配仍是草稿或待复核状态。" % (ratio * 100, needs_review_count)
    return "持仓覆盖率 %.1f%%，当前持仓均已匹配复盘池。" % (ratio * 100)


def matched_coverage_state(item: PoolItem) -> Dict[str, object]:
    reasons = []
    raw = item.raw if isinstance(item.raw, dict) else {}
    raw_status = str(raw.get("raw_status") or "").strip().lower()
    if raw_status in {"candidate", "draft"}:
        reasons.append("candidate_status")
    if str(raw.get("pool_source") or "").startswith("extra:"):
        reasons.append("extra_pool_overlay")
    if str(raw.get("pool_source") or "").startswith("universe:") or raw.get("universe_schema"):
        reasons.append("a_share_universe_foundation")
    if any(is_pending_text(raw.get(field)) for field in ("raw_section", "raw_level", "raw_desc")):
        reasons.append("pending_fields")
    if reasons:
        if "a_share_universe_foundation" in reasons and len(reasons) == 1:
            return {"state": "foundation", "reasons": sorted(set(reasons))}
        return {"state": "draft", "reasons": sorted(set(reasons))}
    return {"state": "confirmed", "reasons": []}


def is_pending_text(value: object) -> bool:
    text = str(value or "").strip()
    return text in {"", "待确认", "待确认 / 持仓补充"} or text.startswith("待确认 /")


def build_expansion_queue(
    pool: str,
    scope: str,
    holdings_coverage: Dict[str, object],
) -> List[Dict[str, object]]:
    if not holdings_coverage.get("available"):
        return []
    unmatched = holdings_coverage.get("unmatched", [])
    if not isinstance(unmatched, list):
        return []

    queue = []
    for rank, row in enumerate(unmatched, start=1):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        name = str(row.get("name") or symbol).strip()
        queue.append(
            {
                "rank": rank,
                "id": "expand_pool_%s" % symbol,
                "symbol": symbol,
                "name": name,
                "reason": "holding_not_in_pool",
                "pool": pool,
                "scope": scope,
                "candidate_pool_row": candidate_pool_row(symbol, name),
                "required_fields": ["section", "level", "desc"],
                "review_questions": [
                    "这只持仓属于哪个行业、主题或产业链位置？",
                    "它在该链路里是龙头、梯队、后排、弹性还是待确认？",
                    "当前纳入复盘池的核心逻辑和主要证伪风险是什么？",
                ],
                "commands": [
                    "market-intel portfolio explain %s --runtime --text" % symbol,
                    "market-intel pool coverage --runtime --json%s" % pool_arg(pool),
                ],
                "done_when": "补入并确认复盘池后，重新运行 pool coverage --runtime，未覆盖持仓不再包含 %s。" % symbol,
            }
        )
    return queue


def candidate_pool_row(symbol: str, name: str) -> Dict[str, object]:
    return {
        "status": "candidate",
        "priority": "P2",
        "section": "待确认 / 持仓补充",
        "level": "待确认",
        "company": name,
        "code": symbol,
        "desc": "持仓未匹配当前复盘池；需补行业/主题链路、公司逻辑和风险证据。",
        "notes": "source=holdings_coverage; manual_review_required=true",
    }


def coverage_gaps(
    scope: str,
    items: List[PoolItem],
    cn_a: List[PoolItem],
    data_quality: Dict[str, object],
    holdings_coverage: Dict[str, object],
    universe: Dict[str, object],
) -> List[Dict[str, object]]:
    gaps = []
    if scope == "all_a_seed" and not universe.get("available"):
        gaps.append(
            {
                "id": "all_a_seed_only",
                "severity": "high",
                "message": "当前 all-a 仍是种子覆盖，尚未接入完整 A 股行业、概念或指数成分。",
            }
        )
    if scope == "all_a_seed" and universe.get("available"):
        if not universe.get("industry_count"):
            gaps.append(
                {
                    "id": "a_share_industry_missing",
                    "severity": "high",
                    "message": "A 股基础清单已接入，但缺少行业字段，无法形成全 A 行业复盘底座。",
                }
            )
        if not universe.get("concept_count") and not universe.get("index_membership_count"):
            gaps.append(
                {
                    "id": "a_share_theme_sources_missing",
                    "severity": "medium",
                    "message": "A 股基础清单缺少概念或指数成分字段，主题/板块复盘仍会偏薄。",
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
    if holdings_coverage.get("available") and holdings_coverage.get("needs_review_count"):
        gaps.append(
            {
                "id": "draft_pool_matches",
                "severity": "medium",
                "message": "存在持仓只匹配到候选或待复核补池行，不能视为已完成正式覆盖。",
            }
        )
    return gaps


def coverage_next_actions(
    pool: str,
    scope: str,
    holdings_coverage: Dict[str, object],
    expansion_queue: List[Dict[str, object]],
    universe: Dict[str, object],
) -> List[Dict[str, object]]:
    actions = [
        {
            "rank": 1,
            "id": "inspect_coverage",
            "command": "market-intel pool coverage --text%s" % pool_arg(pool),
            "done_when": "已确认当前复盘池的覆盖边界、市场分布、层级分布和数据质量短板。",
        }
    ]
    if scope == "all_a_seed" and not universe.get("available"):
        actions.append(
            {
                "rank": 2,
                "id": "expand_all_a_sources",
                "command": "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=data/runtime/a_share_universe.csv market-intel pool coverage --text",
                "done_when": "已准备 A 股基础清单 CSV，并确认 coverage 的 universe.available=true。",
            }
        )
    elif scope == "all_a_seed" and universe.get("available"):
        actions.append(
            {
                "rank": 2,
                "id": "review_a_share_universe",
                "command": "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=data/runtime/a_share_universe.csv market-intel pool coverage --json",
                "done_when": "已确认基础清单的行业、概念和指数成分字段覆盖情况。",
            }
        )
    if not holdings_coverage.get("available"):
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "check_holdings_coverage",
                "command": "market-intel pool coverage --runtime --text%s" % pool_arg(pool),
                "done_when": "已确认个人持仓是否被当前复盘池覆盖。",
            }
        )
    elif expansion_queue:
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "review_expansion_queue",
                "command": "market-intel pool coverage --runtime --json%s" % pool_arg(pool),
                "done_when": "已逐项确认 expansion_queue 中的候选补池行、必填字段和复核问题。",
            }
        )
    elif holdings_coverage.get("needs_review_count"):
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "review_draft_pool_matches",
                "command": "market-intel pool coverage --runtime --json%s" % pool_arg(pool),
                "done_when": "已确认 holdings_coverage.review_queue 中的草稿匹配，并将候选字段补齐。",
            }
        )
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "review_unmatched_holdings",
                "command": "market-intel portfolio review --runtime --text%s" % pool_arg(pool),
                "done_when": "已确认未覆盖持仓是否补入复盘池、暂列池外，或修正代码/名称。",
            }
        )
    actions.append(
        {
            "rank": len(actions) + 1,
            "id": "run_focus",
            "command": "market-intel focus --runtime --text%s" % pool_arg(pool),
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
            "data.universe",
            "data.holdings_coverage",
            "data.expansion_queue",
            "data.gaps",
            "data.next_actions",
            "data.guardrails",
        ],
        "boundary": "覆盖度报告只说明复盘池边界，不生成交易动作、目标价或仓位建议。",
    }


def pool_arg(pool: str) -> str:
    return "" if pool == "all-a" else " --pool %s" % pool


def coverage_guardrails(scope: str, universe: Dict[str, object]) -> List[str]:
    guardrails = ["覆盖度用于判断复盘池边界，不生成买卖指令、目标价或仓位建议。"]
    if scope == "all_a_seed":
        if universe.get("available"):
            guardrails.append("all-a 已接入 A 股基础清单，但基础清单只代表覆盖底座，不等于完成研究证据和主题解释。")
        else:
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
