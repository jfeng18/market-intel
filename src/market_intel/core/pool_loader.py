import csv
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import PoolItem
from .normalize import merge_pool_items, normalize_row


ALL_A_POOL = "all-a"
AI_ENERGY_POOL = "ai-energy"
DEFAULT_POOL = ALL_A_POOL
AI_ENERGY_POOL_FILENAME = "ai_energy_pool_2026-05-19.csv"
A_SHARE_UNIVERSE_ENV = "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS"

POOL_REGISTRY: Dict[str, Dict[str, str]] = {
    ALL_A_POOL: {
        "filename": AI_ENERGY_POOL_FILENAME,
        "scope": "all_a_seed",
        "description": "全 A 复盘 universe 的种子覆盖；当前复用 AI 主题池，后续可扩展行业/概念/指数成分数据。",
    },
    AI_ENERGY_POOL: {
        "filename": AI_ENERGY_POOL_FILENAME,
        "scope": "theme",
        "description": "AI 算力、运力、存力、电力和人才密度主题池。",
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_pool_path(pool: str = DEFAULT_POOL) -> Path:
    configured = os.environ.get("MARKET_INTEL_POOL_PATH")
    if configured:
        return Path(configured)
    return repo_root() / "data" / "pools" / pool_definition(pool)["filename"]


def extra_pool_paths() -> List[Path]:
    configured = os.environ.get("MARKET_INTEL_POOL_EXTRA_PATHS")
    if not configured:
        return []
    return [Path(value) for value in configured.split(os.pathsep) if value.strip()]


def a_share_universe_paths() -> List[Path]:
    configured = os.environ.get(A_SHARE_UNIVERSE_ENV)
    if not configured:
        return []
    return [Path(value) for value in configured.split(os.pathsep) if value.strip()]


def load_pool(pool: str = DEFAULT_POOL, path: Optional[Path] = None) -> List[PoolItem]:
    definition = pool_definition(pool)
    pool_path = path or default_pool_path(pool)
    rows = read_pool_items(pool_path, source="base")
    if path is None:
        if pool == ALL_A_POOL:
            for universe_path in a_share_universe_paths():
                rows.extend(read_a_share_universe_items(universe_path))
        for extra_path in extra_pool_paths():
            rows.extend(read_pool_items(extra_path, source="extra:%s" % extra_path.name))
    items = merge_pool_items(rows)
    for item in items:
        item.raw["pool"] = pool
        item.raw["pool_scope"] = definition["scope"]
    return items


def read_pool_items(path: Path, source: str) -> List[PoolItem]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row, row in enumerate(reader, start=2):
            item = normalize_row(row, raw_row)
            item.raw["pool_source"] = source
            item.raw["pool_source_file"] = path.name
            rows.append(item)
    return rows


def read_a_share_universe_items(path: Path) -> List[PoolItem]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for raw_row, row in enumerate(reader, start=2):
            item = normalize_row(a_share_universe_pool_row(row), raw_row)
            item.raw["pool_source"] = "universe:%s" % path.name
            item.raw["pool_source_file"] = path.name
            item.raw["universe_source_file"] = path.name
            item.raw["universe_schema"] = "a_share_universe_v1"
            item.raw["universe_industry"] = first_value(row, ["industry", "行业", "申万行业", "中信行业"])
            item.raw["universe_concepts"] = first_value(row, ["concepts", "概念", "主题", "概念板块"])
            item.raw["universe_index_membership"] = first_value(row, ["index_membership", "indices", "指数", "指数成分"])
            item.raw["universe_listing_status"] = first_value(row, ["listing_status", "上市状态", "状态"])
            rows.append(item)
    return rows


def a_share_universe_pool_row(row: Dict[str, str]) -> Dict[str, str]:
    symbol = first_value(row, ["symbol", "code", "证券代码", "股票代码", "代码"])
    name = first_value(row, ["name", "company", "证券名称", "股票名称", "名称"])
    industry = first_value(row, ["industry", "行业", "申万行业", "中信行业"])
    concepts = first_value(row, ["concepts", "概念", "主题", "概念板块"])
    index_membership = first_value(row, ["index_membership", "indices", "指数", "指数成分"])
    listing_status = first_value(row, ["listing_status", "上市状态", "状态"]) or "listed"
    section = "行业 / %s" % (industry or "行业待补")
    desc_parts = []
    if concepts:
        desc_parts.append("概念：%s" % concepts)
    if index_membership:
        desc_parts.append("指数成分：%s" % index_membership)
    desc_parts.append("上市状态：%s" % listing_status)
    return {
        "status": "reviewed",
        "priority": "P3",
        "section": section,
        "level": industry or "行业待补",
        "company": name,
        "code": symbol,
        "desc": "；".join(desc_parts),
        "notes": "source=a_share_universe; schema=a_share_universe_v1",
    }


def first_value(row: Dict[str, str], names: List[str]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def pool_definition(pool: str) -> Dict[str, str]:
    try:
        return POOL_REGISTRY[pool]
    except KeyError as exc:
        supported = ", ".join(sorted(POOL_REGISTRY))
        raise ValueError("Unsupported pool: %s. Supported pools: %s" % (pool, supported)) from exc


def list_pools() -> List[Dict[str, str]]:
    return [
        {
            "id": pool,
            "filename": definition["filename"],
            "scope": definition["scope"],
            "description": definition["description"],
        }
        for pool, definition in sorted(POOL_REGISTRY.items())
    ]
