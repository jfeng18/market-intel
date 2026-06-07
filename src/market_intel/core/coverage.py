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
RESEARCH_CSV_FIELDS = ["symbol", "name", "status", "thesis", "evidence", "invalidation", "updated_at", "source"]
UNIVERSE_PATCH_CSV_FIELDS = [
    "symbol",
    "name",
    "industry",
    "concepts",
    "index_membership",
    "listing_status",
    "source",
    "missing_fields",
    "fill_hint",
]


def build_pool_coverage(
    pool: str,
    items: List[PoolItem],
    holdings: Optional[List[Holding]] = None,
) -> Dict[str, object]:
    definition = pool_definition(pool)
    tradable = [item for item in items if item.tradable and item.symbol]
    cn_a = [item for item in tradable if item.market == "CN_A"]
    data_quality = data_quality_summary(items)
    data_quality_queue = build_data_quality_queue(pool, items, data_quality)
    universe = universe_summary(items)
    scope = str(definition.get("scope") or "")
    holdings_coverage = build_holdings_coverage(items, holdings)
    expansion_queue = build_expansion_queue(pool, scope, holdings_coverage)
    research_queue = build_research_queue(pool, holdings_coverage)
    next_actions = coverage_next_actions(pool, scope, holdings_coverage, expansion_queue, research_queue, universe)
    cleanup_action = data_quality_cleanup_action(pool, data_quality_queue)
    if cleanup_action:
        next_actions.insert(1, cleanup_action)
    rerank_actions(next_actions)
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
        "data_quality_queue": data_quality_queue,
        "universe": universe,
        "holdings_coverage": holdings_coverage,
        "expansion_queue": expansion_queue,
        "research_queue": research_queue,
        "gaps": coverage_gaps(scope, items, cn_a, data_quality, holdings_coverage, universe),
        "next_actions": next_actions,
        "agent_contract": coverage_contract(),
        "guardrails": coverage_guardrails(scope, universe),
    }


def build_data_quality_detail(pool: str, items: List[PoolItem], flag: str, limit: int = 12) -> Dict[str, object]:
    clean_flag = str(flag or "").strip()
    data_quality = data_quality_summary(items)
    queue = build_data_quality_queue(pool, items, data_quality)
    queue_item = next((item for item in queue if item.get("flag") == clean_flag), None)
    if not queue_item:
        meta = data_quality_flag_meta(clean_flag)
        return {
            "pool": pool,
            "flag": clean_flag,
            "found": False,
            "summary": "未找到数据质量标记 %s 的样本。" % clean_flag,
            "severity": meta["severity"],
            "category": meta["category"],
            "reason": meta["reason"],
            "suggested_action": meta["suggested_action"],
            "done_when": meta["done_when"],
            "affected_count": 0,
            "samples": [],
            "next_commands": ["market-intel pool coverage --json%s" % pool_arg(pool)],
            "available_flags": [str(item.get("flag")) for item in queue if item.get("flag")],
            "agent_contract": data_quality_detail_contract(),
            "write_policy": "只读复核数据质量样本；不自动修改 pool CSV 或 runtime 文件。",
        }
    flagged_items = [item for item in items if clean_flag in item.data_quality_flags]
    limited_samples = data_quality_detail_samples(clean_flag, flagged_items, max(0, int(limit or 0)))
    return {
        "pool": pool,
        "flag": clean_flag,
        "found": True,
        "rank": queue_item.get("rank"),
        "summary": "%s 数据质量复核：影响 %s 个条目，优先级 %s。" % (
            clean_flag,
            queue_item.get("affected_count", 0),
            queue_item.get("severity"),
        ),
        "severity": queue_item.get("severity"),
        "category": queue_item.get("category"),
        "reason": queue_item.get("reason"),
        "suggested_action": queue_item.get("suggested_action"),
        "done_when": queue_item.get("done_when"),
        "affected_count": queue_item.get("affected_count", 0),
        "sample_count": len(limited_samples),
        "samples": limited_samples,
        "next_commands": [
            "market-intel pool quality %s --json%s" % (clean_flag, pool_arg(pool)),
            "market-intel pool coverage --json%s" % pool_arg(pool),
        ],
        "available_flags": [str(item.get("flag")) for item in queue if item.get("flag")],
        "agent_contract": data_quality_detail_contract(),
        "write_policy": "只读复核数据质量样本；不自动修改 pool CSV 或 runtime 文件。",
    }


def data_quality_detail_samples(flag: str, items: List[PoolItem], limit: int) -> List[Dict[str, object]]:
    return [data_quality_detail_sample(flag, item) for item in items[:limit]]


def data_quality_detail_sample(flag: str, item: PoolItem) -> Dict[str, object]:
    raw = item.raw
    return {
        "symbol": item.symbol,
        "name": item.name,
        "instrument_type": item.instrument_type,
        "tradable": item.tradable,
        "raw_row": raw.get("raw_row"),
        "source_file": raw.get("pool_source_file"),
        "source": raw.get("pool_source"),
        "raw_company": raw.get("raw_company"),
        "raw_code": raw.get("raw_code"),
        "raw_desc": raw.get("raw_desc"),
        "raw_section": raw.get("raw_section"),
        "raw_level": raw.get("raw_level"),
        "flags": sorted(set(item.data_quality_flags)),
        "fix_hint": data_quality_fix_hint(flag, item),
    }


def data_quality_fix_hint(flag: str, item: PoolItem) -> str:
    raw = item.raw
    if flag == "invalid_symbol":
        if "pending_listing" in item.data_quality_flags:
            return "若该行是未上市公司，保留 pending 状态并确认 code 为上市地/阶段；若已上市，把 code 改成 6 位 A 股代码。"
        if "non_security_row" in item.data_quality_flags:
            return "若该行是行业指标或说明行，保留非证券标记；若是个股，补真实证券代码并确认公司名。"
        return "把 code 修正为 6 位 A 股代码、港股/台股/韩股/美股格式，或把该行改成明确的非证券/待上市说明。"
    if flag == "column_shift_suspected":
        return "核对 company/code/desc 是否错位；修正后应让 company=公司名、code=证券代码、desc=一句话逻辑。"
    if flag == "missing_role":
        return "在 level 或 desc 中补充该公司角色，例如龙头、核心、弹性、设备、材料、服务或其他可复核定位。"
    if flag == "unknown_layer":
        return "把 section 调整到可识别的行业/主题层级，或扩展层级映射规则覆盖该 section。"
    if flag == "duplicate_symbol_exposure":
        rows = raw.get("merged_raw_rows")
        if isinstance(rows, list) and rows:
            return "核对同一 symbol 的多行暴露是否都应保留；若是重复描述，合并 CSV 行。关联 raw_row=%s。" % ",".join(str(row) for row in rows)
        return "核对同一 symbol 的多链路暴露是否真实；保留合理暴露，合并重复行。"
    return data_quality_flag_meta(flag)["suggested_action"]


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


def export_research_queue_csv(
    research_queue: List[Dict[str, object]],
    output_path: Path,
    dry_run: bool = False,
) -> Dict[str, object]:
    rows = research_candidate_rows(research_queue)
    written = False
    if rows and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESEARCH_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        written = True
    return {
        "output": command_path(output_path),
        "record_count": len(rows),
        "written": written,
        "dry_run": dry_run,
        "fields": list(RESEARCH_CSV_FIELDS),
        "rows": rows,
        "warnings": research_export_warnings(rows),
        "next_commands": research_export_next_commands(output_path, written, rows),
    }


def export_universe_patch_csv(
    universe_items: List[PoolItem],
    output_path: Path,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, object]:
    rows = universe_patch_rows(universe_items, limit=limit)
    written = False
    if rows and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=UNIVERSE_PATCH_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        written = True
    return {
        "output": command_path(output_path),
        "record_count": len(rows),
        "written": written,
        "dry_run": dry_run,
        "limit": limit,
        "fields": list(UNIVERSE_PATCH_CSV_FIELDS),
        "rows": rows,
        "warnings": universe_patch_export_warnings(rows),
        "next_commands": universe_patch_export_next_commands(output_path, written, rows),
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


def research_candidate_rows(research_queue: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    seen = set()
    for item in research_queue:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        candidate = item.get("candidate_research_row", {}) if isinstance(item.get("candidate_research_row"), dict) else {}
        rows.append(
            {
                "symbol": symbol,
                "name": str(candidate.get("name") or item.get("name") or symbol),
                "status": str(candidate.get("status") or "draft"),
                "thesis": str(candidate.get("thesis") or ""),
                "evidence": str(candidate.get("evidence") or ""),
                "invalidation": str(candidate.get("invalidation") or ""),
                "updated_at": str(candidate.get("updated_at") or ""),
                "source": str(candidate.get("source") or "pool_research_queue"),
            }
        )
    return rows


def universe_patch_rows(universe_items: List[PoolItem], limit: Optional[int] = None) -> List[Dict[str, object]]:
    rows = []
    for item in sorted(universe_items, key=lambda value: str(value.symbol or "")):
        if not item.symbol:
            continue
        industry = str(item.raw.get("universe_industry") or "").strip()
        concepts = str(item.raw.get("universe_concepts") or "").strip()
        index_membership = str(item.raw.get("universe_index_membership") or "").strip()
        missing_fields = universe_patch_missing_fields(industry, concepts, index_membership)
        if not missing_fields:
            continue
        rows.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "industry": industry,
                "concepts": concepts,
                "index_membership": index_membership,
                "listing_status": str(item.raw.get("universe_listing_status") or "listed"),
                "source": "pool.universe.todo",
                "missing_fields": ";".join(missing_fields),
                "fill_hint": universe_patch_fill_hint(missing_fields),
            }
        )
        if limit is not None and len(rows) >= max(0, limit):
            break
    return rows


def universe_patch_missing_fields(industry: str, concepts: str, index_membership: str) -> List[str]:
    missing = []
    if not industry:
        missing.append("industry")
    if not split_universe_values(concepts):
        missing.append("concepts")
    if not split_universe_values(index_membership):
        missing.append("index_membership")
    return missing


def universe_patch_fill_hint(missing_fields: List[str]) -> str:
    labels = {
        "industry": "补行业",
        "concepts": "补概念，多个用分号分隔",
        "index_membership": "补指数成分，多个用分号分隔",
    }
    return "；".join(labels[field] for field in missing_fields if field in labels)


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


def research_export_warnings(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not rows:
        return []
    return [
        {
            "code": "RESEARCH_NOTES_NEED_REVIEW",
            "message": "Research CSV is a draft. Fill thesis, evidence, invalidation, then set status=reviewed before import.",
            "detail": {"record_count": len(rows), "required_fields": ["thesis", "evidence", "invalidation"]},
        }
    ]


def universe_patch_export_warnings(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not rows:
        return []
    return [
        {
            "code": "UNIVERSE_PATCH_NEEDS_ENRICHMENT",
            "message": "Universe patch CSV is a draft. Fill missing industry, concepts, or index_membership before merge import.",
            "detail": {
                "record_count": len(rows),
                "required_fields": ["industry", "concepts", "index_membership"],
                "helper_fields": ["missing_fields", "fill_hint"],
            },
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


def research_export_next_commands(
    output_path: Path,
    written: bool,
    rows: List[Dict[str, object]],
) -> List[str]:
    if not rows:
        return []
    path_text = command_path(output_path)
    if written:
        return [
            "market-intel import research %s --dry-run --json" % path_text,
            "market-intel import research %s --runtime --json" % path_text,
            "market-intel pool coverage --runtime --text",
        ]
    return [
        "market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --json",
    ]


def universe_patch_export_next_commands(
    output_path: Path,
    written: bool,
    rows: List[Dict[str, object]],
) -> List[str]:
    if not rows:
        return []
    path_text = command_path(output_path)
    if written:
        return [
            "market-intel import universe %s --runtime --merge --dry-run --json" % path_text,
            "market-intel import universe %s --runtime --merge --json" % path_text,
            "market-intel pool coverage --runtime --text",
        ]
    return [
        "market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --json",
    ]


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
            "sector_profile": empty_sector_profile(),
            "enrichment_queue": [],
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
    sector_profile = universe_sector_profile(universe_items)
    return {
        "available": True,
        "schema": "a_share_universe_v1",
        "record_count": len(universe_items),
        "source_files": source_files,
        "industry_count": len(industries),
        "concept_count": len(concepts),
        "index_membership_count": len(indexes),
        "sector_profile": sector_profile,
        "enrichment_queue": universe_enrichment_queue(universe_items, sector_profile),
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


def empty_sector_profile() -> Dict[str, object]:
    return {
        "record_count": 0,
        "industry_covered_count": 0,
        "concept_covered_count": 0,
        "index_covered_count": 0,
        "industry_coverage_ratio": 0,
        "concept_coverage_ratio": 0,
        "index_coverage_ratio": 0,
        "top_industries": [],
        "top_concepts": [],
        "top_indexes": [],
        "missing_field_counts": {
            "industry": 0,
            "concepts": 0,
            "index_membership": 0,
        },
        "missing_field_samples": [],
        "coverage_flags": [],
    }


UNIVERSE_FIELD_META = {
    "industry": {
        "label": "行业",
        "priority": 1,
        "reason": "缺行业会削弱全 A 板块强弱和持仓行业暴露判断。",
    },
    "concepts": {
        "label": "概念",
        "priority": 2,
        "reason": "缺概念会削弱主题轮动、热点归因和重复主题暴露判断。",
    },
    "index_membership": {
        "label": "指数成分",
        "priority": 3,
        "reason": "缺指数成分会削弱宽基/风格指数归因和候选标的分组。",
    },
}


def universe_enrichment_queue(universe_items: List[PoolItem], sector_profile: Dict[str, object]) -> List[Dict[str, object]]:
    missing_counts = sector_profile.get("missing_field_counts", {}) if isinstance(sector_profile.get("missing_field_counts"), dict) else {}
    rows = []
    for field, meta in UNIVERSE_FIELD_META.items():
        count = int(missing_counts.get(field) or 0)
        if count <= 0:
            continue
        rows.append(
            {
                "rank": 0,
                "field": field,
                "label": meta["label"],
                "severity": "high" if field == "industry" else "medium",
                "missing_count": count,
                "missing_ratio": coverage_ratio(count, len(universe_items)),
                "reason": meta["reason"],
                "samples": universe_missing_field_samples(universe_items, field),
                "command": "market-intel import universe <a_share_universe_patch.csv> --runtime --merge --dry-run --json",
                "done_when": (
                    "已用 --merge 补齐 %s 字段并通过 dry-run；pool coverage 中 "
                    "universe.sector_profile.missing_field_counts.%s=0。"
                )
                % (meta["label"], field),
            }
        )
    rows.sort(key=lambda item: (UNIVERSE_FIELD_META[str(item["field"])]["priority"], -int(item["missing_count"])))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def universe_missing_field_samples(universe_items: List[PoolItem], field: str, limit: int = 5) -> List[Dict[str, object]]:
    samples = []
    for item in universe_items:
        value = item.raw.get("universe_%s" % field)
        missing = not split_universe_values(value) if field in {"concepts", "index_membership"} else not str(value or "").strip()
        if not missing:
            continue
        samples.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "industry": item.raw.get("universe_industry"),
                "concepts": item.raw.get("universe_concepts"),
                "index_membership": item.raw.get("universe_index_membership"),
            }
        )
        if len(samples) >= limit:
            break
    return samples


def universe_sector_profile(universe_items: List[PoolItem]) -> Dict[str, object]:
    record_count = len(universe_items)
    industry_counter = Counter()
    concept_counter = Counter()
    index_counter = Counter()
    missing_counts = Counter()
    missing_samples = []
    industry_covered = 0
    concept_covered = 0
    index_covered = 0
    for item in universe_items:
        industry = str(item.raw.get("universe_industry") or "").strip()
        concepts = split_universe_values(item.raw.get("universe_concepts"))
        indexes = split_universe_values(item.raw.get("universe_index_membership"))
        missing_fields = []
        if industry:
            industry_counter.update([industry])
            industry_covered += 1
        else:
            missing_counts.update(["industry"])
            missing_fields.append("industry")
        if concepts:
            concept_counter.update(concepts)
            concept_covered += 1
        else:
            missing_counts.update(["concepts"])
            missing_fields.append("concepts")
        if indexes:
            index_counter.update(indexes)
            index_covered += 1
        else:
            missing_counts.update(["index_membership"])
            missing_fields.append("index_membership")
        if missing_fields and len(missing_samples) < 8:
            missing_samples.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "missing_fields": missing_fields,
                }
            )
    flags = []
    if missing_counts.get("industry"):
        flags.append("industry_missing")
    if missing_counts.get("concepts"):
        flags.append("concepts_missing")
    if missing_counts.get("index_membership"):
        flags.append("index_membership_missing")
    return {
        "record_count": record_count,
        "industry_covered_count": industry_covered,
        "concept_covered_count": concept_covered,
        "index_covered_count": index_covered,
        "industry_coverage_ratio": coverage_ratio(industry_covered, record_count),
        "concept_coverage_ratio": coverage_ratio(concept_covered, record_count),
        "index_coverage_ratio": coverage_ratio(index_covered, record_count),
        "top_industries": counter_dicts(industry_counter, limit=10),
        "top_concepts": counter_dicts(concept_counter, limit=10),
        "top_indexes": counter_dicts(index_counter, limit=10),
        "missing_field_counts": {
            "industry": missing_counts.get("industry", 0),
            "concepts": missing_counts.get("concepts", 0),
            "index_membership": missing_counts.get("index_membership", 0),
        },
        "missing_field_samples": missing_samples,
        "coverage_flags": flags,
    }


def coverage_ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0


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


DATA_QUALITY_FLAG_META = {
    "invalid_symbol": {
        "severity": "high",
        "category": "symbol",
        "reason": "原始 code 不是可识别证券代码，可能是板块标记、待上市公司或表格错位。",
        "suggested_action": "确认该行是否证券；非证券行保留为说明行，证券行补正确 code。",
        "done_when": "invalid_symbol 样本已被删除、标记为非证券，或补齐为有效证券代码。",
    },
    "column_shift_suspected": {
        "severity": "high",
        "category": "schema",
        "reason": "系统从描述中恢复了证券代码，说明原始表格列可能错位。",
        "suggested_action": "回看原始 CSV 行，把公司、代码、描述和 notes 放回正确列。",
        "done_when": "重新运行 coverage 后，该行不再出现 column_shift_suspected。",
    },
    "pending_listing": {
        "severity": "medium",
        "category": "listing_status",
        "reason": "该行是待上市或未上市主体，不能当作可交易证券。",
        "suggested_action": "保留为产业链观察对象，或移到非证券/待上市说明区。",
        "done_when": "pending 行不会进入可交易标的、热点候选或持仓覆盖匹配。",
    },
    "non_security_row": {
        "severity": "medium",
        "category": "non_security",
        "reason": "该行更像分类标题、指标或说明，不是证券。",
        "suggested_action": "确认 section/level/company/code 是否用于分组说明，避免被当成标的。",
        "done_when": "非证券说明行保持 non_security，不参与 tradable、scan 或持仓匹配。",
    },
    "missing_role": {
        "severity": "medium",
        "category": "research_field",
        "reason": "缺少链路角色，单票解释和板块聚合会变得粗糙。",
        "suggested_action": "在 level/desc 中补齐龙头、核心、弹性、设备、材料、服务等角色定位。",
        "done_when": "重点样本已补角色，coverage 的 missing_role 数量下降。",
    },
    "unknown_layer": {
        "severity": "medium",
        "category": "taxonomy",
        "reason": "section 未能映射到已知层级，板块聚合可能丢失上下文。",
        "suggested_action": "把 section 改成可识别的行业/主题层级，或扩展层级映射规则。",
        "done_when": "unknown_layer 样本已归入明确行业/主题层级。",
    },
    "duplicate_symbol_exposure": {
        "severity": "low",
        "category": "dedupe",
        "reason": "同一证券出现在多条链路中，需要确认是合理多链路暴露还是重复行。",
        "suggested_action": "保留真实多链路暴露，合并重复描述，避免重复计数误导持仓压力。",
        "done_when": "重复样本已确认保留或合并，exposure_count 与实际研究口径一致。",
    },
}

DATA_QUALITY_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def build_data_quality_queue(
    pool: str,
    items: List[PoolItem],
    data_quality: Dict[str, object],
) -> List[Dict[str, object]]:
    if not data_quality.get("flagged_item_count"):
        return []
    by_flag: Dict[str, List[PoolItem]] = {}
    for item in items:
        for flag in sorted(set(item.data_quality_flags)):
            by_flag.setdefault(flag, []).append(item)
    rows = []
    for flag, flagged_items in by_flag.items():
        meta = data_quality_flag_meta(flag)
        rows.append(
            {
                "rank": 0,
                "flag": flag,
                "severity": meta["severity"],
                "category": meta["category"],
                "affected_count": len(flagged_items),
                "reason": meta["reason"],
                "suggested_action": meta["suggested_action"],
                "done_when": meta["done_when"],
                "review_command": "market-intel pool quality %s --json%s" % (flag, pool_arg(pool)),
                "samples": data_quality_queue_samples(flagged_items),
            }
        )
    rows.sort(
        key=lambda row: (
            DATA_QUALITY_SEVERITY_RANK.get(str(row.get("severity")), 9),
            -int(row.get("affected_count", 0)),
            str(row.get("flag") or ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def data_quality_flag_meta(flag: str) -> Dict[str, str]:
    return DATA_QUALITY_FLAG_META.get(
        flag,
        {
            "severity": "medium",
            "category": "unknown",
            "reason": "复盘池存在未分类的数据质量标记。",
            "suggested_action": "查看样本行，确认是否需要补字段、改分类或扩展校验规则。",
            "done_when": "该标记已被解释、修复或加入明确的质量规则。",
        },
    )


def data_quality_queue_samples(items: List[PoolItem]) -> List[Dict[str, object]]:
    samples = []
    for item in items[:8]:
        samples.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "raw_row": item.raw.get("raw_row"),
                "source_file": item.raw.get("pool_source_file"),
                "raw_code": item.raw.get("raw_code"),
                "raw_section": item.raw.get("raw_section"),
                "raw_level": item.raw.get("raw_level"),
                "flags": sorted(set(item.data_quality_flags)),
            }
        )
    return samples


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
        research = research_status(item)
        if state["state"] != "confirmed":
            review_queue.append(
                {
                    "symbol": holding.symbol,
                    "name": holding.name or item.name,
                    "coverage_state": state["state"],
                    "reasons": state["reasons"],
                    "research_status": research,
                    "command": "market-intel pool explain %s --runtime --text" % holding.symbol,
                    "done_when": coverage_done_when(state["state"]),
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
                "research_status": research,
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
    if foundation_count:
        flags.append("foundation_pool_matches")
    if draft_count:
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


def research_status(item: PoolItem) -> Dict[str, object]:
    raw = item.raw if isinstance(item.raw, dict) else {}
    note = raw.get("research_note", {}) if isinstance(raw.get("research_note"), dict) else {}
    if not note:
        return {
            "available": False,
            "status": "missing",
            "source_file": None,
            "has_thesis": False,
            "has_evidence": False,
            "has_invalidation": False,
            "confirmed": False,
            "missing_fields": ["thesis", "evidence", "invalidation"],
        }
    missing_fields = [
        field
        for field in ("thesis", "evidence", "invalidation")
        if not str(note.get(field) or "").strip()
    ]
    return {
        "available": True,
        "schema": note.get("schema") or raw.get("research_schema") or "research_notes_v1",
        "status": str(note.get("status") or raw.get("research_status") or "draft").strip().lower() or "draft",
        "source_file": note.get("source_file"),
        "has_thesis": bool(str(note.get("thesis") or "").strip()),
        "has_evidence": bool(str(note.get("evidence") or "").strip()),
        "has_invalidation": bool(str(note.get("invalidation") or "").strip()),
        "missing_fields": missing_fields,
        "confirmed": research_note_confirmed(note),
    }


def matched_coverage_state(item: PoolItem) -> Dict[str, object]:
    reasons = []
    raw = item.raw if isinstance(item.raw, dict) else {}
    research = raw.get("research_note", {}) if isinstance(raw.get("research_note"), dict) else {}
    has_reviewed_research = research_note_confirmed(research)
    raw_status = str(raw.get("raw_status") or "").strip().lower()
    if raw_status in {"candidate", "draft"}:
        reasons.append("candidate_status")
    if str(raw.get("pool_source") or "").startswith("extra:"):
        reasons.append("extra_pool_overlay")
    has_foundation_source = str(raw.get("pool_source") or "").startswith("universe:") or bool(raw.get("universe_schema"))
    if has_foundation_source:
        reasons.append("a_share_universe_foundation")
    if any(is_pending_text(raw.get(field)) for field in ("raw_section", "raw_level", "raw_desc")):
        reasons.append("pending_fields")
    if has_foundation_source and has_reviewed_research:
        remaining = [reason for reason in reasons if reason != "a_share_universe_foundation"]
        if not remaining:
            return {"state": "confirmed", "reasons": ["reviewed_research"]}
    if reasons:
        if "a_share_universe_foundation" in reasons and len(reasons) == 1:
            return {"state": "foundation", "reasons": sorted(set(reasons))}
        return {"state": "draft", "reasons": sorted(set(reasons))}
    return {"state": "confirmed", "reasons": []}


def research_note_confirmed(value: Dict[str, object]) -> bool:
    status = str(value.get("status") or "").strip().lower()
    if status not in {"reviewed", "confirmed"}:
        return False
    required = ("thesis", "evidence", "invalidation")
    return all(str(value.get(field) or "").strip() for field in required)


def coverage_done_when(state: object) -> str:
    if state == "foundation":
        return "已导入 reviewed research_notes，且核心逻辑、关键证据、证伪风险三项齐全。"
    if state == "draft":
        return "已确认候选补池行的行业/主题链路、角色、公司逻辑和证伪风险。"
    return "已确认该持仓的行业/主题链路、角色、核心逻辑和证伪风险。"


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


def build_research_queue(
    pool: str,
    holdings_coverage: Dict[str, object],
) -> List[Dict[str, object]]:
    if not holdings_coverage.get("available"):
        return []
    review_queue = holdings_coverage.get("review_queue", [])
    if not isinstance(review_queue, list):
        return []
    queue = []
    seen = set()
    for row in review_queue:
        if not isinstance(row, dict) or row.get("coverage_state") != "foundation":
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = str(row.get("name") or symbol).strip()
        queue.append(
            {
                "rank": len(queue) + 1,
                "id": "research_notes_%s" % symbol,
                "symbol": symbol,
                "name": name,
                "reason": "foundation_research_missing",
                "pool": pool,
                "required_fields": ["thesis", "evidence", "invalidation"],
                "candidate_research_row": candidate_research_row(symbol, name),
                "commands": [
                    "market-intel portfolio explain %s --runtime --text" % symbol,
                    "market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --json%s" % pool_arg(pool),
                    "market-intel import research data/runtime/research_notes.todo.csv --runtime --json",
                ],
                "done_when": "已补齐核心逻辑、关键证据和证伪风险，设置 status=reviewed，并导入 runtime research_notes。",
            }
        )
    return queue


def candidate_research_row(symbol: str, name: str) -> Dict[str, object]:
    return {
        "symbol": symbol,
        "name": name,
        "status": "draft",
        "thesis": "",
        "evidence": "",
        "invalidation": "",
        "updated_at": "",
        "source": "pool_research_queue",
    }


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
    if holdings_coverage.get("available") and holdings_coverage.get("foundation_matched_count"):
        gaps.append(
            {
                "id": "foundation_research_missing",
                "severity": "medium",
                "message": "存在持仓只命中 A 股基础清单，需要补 reviewed research_notes 才能视为正式覆盖。",
            }
        )
    if holdings_coverage.get("available") and holdings_coverage.get("draft_matched_count"):
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
    research_queue: List[Dict[str, object]],
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
                "command": "market-intel import universe examples/a_share_universe.csv.example --runtime --json",
                "done_when": "已导入 A 股基础清单 CSV，并确认 coverage 的 universe.available=true。",
            }
        )
    elif scope == "all_a_seed" and universe.get("available"):
        actions.append(
            {
                "rank": 2,
                "id": "review_a_share_universe",
                "command": "market-intel pool coverage --json",
                "done_when": "已确认基础清单的行业、概念和指数成分字段覆盖情况。",
            }
        )
        profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
        if profile.get("coverage_flags"):
            actions.append(
                {
                    "rank": len(actions) + 1,
                    "id": "export_a_share_universe_patch",
                    "command": "market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --json",
                    "done_when": "已导出 A 股基础清单字段补数模板，并填写缺失的行业、概念或指数成分字段。",
                }
            )
            actions.append(
                {
                    "rank": len(actions) + 1,
                    "id": "merge_a_share_universe_patch",
                    "command": "market-intel import universe <a_share_universe_patch.csv> --runtime --merge --dry-run --json",
                    "done_when": "已用 --merge 补齐 A 股基础清单缺失的行业、概念或指数成分字段，并通过 dry-run 校验。",
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
    elif research_queue:
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "export_research_queue",
                "command": "market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --json",
                "done_when": "已导出 foundation 持仓的 research_notes 草稿，并补齐核心逻辑、关键证据和证伪风险。",
            }
        )
        actions.append(
            {
                "rank": len(actions) + 1,
                "id": "review_foundation_holdings",
                "command": "market-intel import research data/runtime/research_notes.todo.csv --runtime --json",
                "done_when": "已导入 reviewed research_notes，且 coverage 的 foundation_matched_count 降为 0。",
            }
        )
    elif holdings_coverage.get("draft_matched_count"):
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


def data_quality_cleanup_action(pool: str, data_quality_queue: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if not data_quality_queue:
        return None
    first = data_quality_queue[0]
    return {
        "rank": 0,
        "id": "clean_data_quality_queue",
        "command": "market-intel pool quality %s --json%s" % (first.get("flag"), pool_arg(pool)),
        "done_when": "已按 data_quality_queue 的 rank 清理或解释高优先级标记，data_quality.flagged_item_count 下降。",
        "focus": {
            "flag": first.get("flag"),
            "severity": first.get("severity"),
            "affected_count": first.get("affected_count"),
        },
    }


def data_quality_detail_contract() -> Dict[str, object]:
    return {
        "success": "ok=true 且 data.found=true 表示该 flag 有可复核样本。",
        "stable_fields": [
            "data.pool",
            "data.flag",
            "data.found",
            "data.severity",
            "data.category",
            "data.affected_count",
            "data.samples",
            "data.samples[].raw_row",
            "data.samples[].source_file",
            "data.samples[].raw_code",
            "data.samples[].raw_company",
            "data.samples[].raw_desc",
            "data.samples[].fix_hint",
            "data.suggested_action",
            "data.done_when",
            "data.next_commands",
            "data.available_flags",
        ],
        "boundary": "pool quality 是只读数据质量复核，不自动修改 pool CSV、runtime 文件或 journal。",
    }


def rerank_actions(actions: List[Dict[str, object]]) -> None:
    for index, action in enumerate(actions, start=1):
        action["rank"] = index


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
            "data.data_quality_queue",
            "data.data_quality_queue[].samples",
            "data.data_quality_queue[].done_when",
            "data.universe",
            "data.universe.sector_profile",
            "data.universe.sector_profile.top_industries",
            "data.universe.sector_profile.missing_field_samples",
            "data.universe.enrichment_queue",
            "data.universe.enrichment_queue[].samples",
            "data.universe.enrichment_queue[].done_when",
            "data.holdings_coverage",
            "data.expansion_queue",
            "data.research_queue",
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
