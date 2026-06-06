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


def load_pool(pool: str = DEFAULT_POOL, path: Optional[Path] = None) -> List[PoolItem]:
    definition = pool_definition(pool)
    pool_path = path or default_pool_path(pool)
    rows = []
    with pool_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row, row in enumerate(reader, start=2):
            rows.append(normalize_row(row, raw_row))
    items = merge_pool_items(rows)
    for item in items:
        item.raw["pool"] = pool
        item.raw["pool_scope"] = definition["scope"]
    return items


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
