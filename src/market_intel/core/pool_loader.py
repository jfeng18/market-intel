import csv
import os
from pathlib import Path
from typing import List, Optional

from .models import PoolItem
from .normalize import merge_pool_items, normalize_row


DEFAULT_POOL = "ai-energy"
DEFAULT_POOL_FILENAME = "ai_energy_pool_2026-05-19.csv"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_pool_path() -> Path:
    configured = os.environ.get("MARKET_INTEL_POOL_PATH")
    if configured:
        return Path(configured)
    return repo_root() / "data" / "pools" / DEFAULT_POOL_FILENAME


def load_pool(pool: str = DEFAULT_POOL, path: Optional[Path] = None) -> List[PoolItem]:
    if pool != DEFAULT_POOL:
        raise ValueError("Unsupported pool: %s" % pool)
    pool_path = path or default_pool_path()
    rows = []
    with pool_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row, row in enumerate(reader, start=2):
            rows.append(normalize_row(row, raw_row))
    return merge_pool_items(rows)

