import csv
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import PoolItem
from .normalize import merge_pool_items, normalize_row
from .symbols import normalize_symbol_text


ALL_A_POOL = "all-a"
AI_ENERGY_POOL = "ai-energy"
DEFAULT_POOL = ALL_A_POOL
AI_ENERGY_POOL_FILENAME = "ai_energy_pool_2026-05-19.csv"
A_SHARE_UNIVERSE_ENV = "MARKET_INTEL_A_SHARE_UNIVERSE_PATHS"
RESEARCH_NOTES_ENV = "MARKET_INTEL_RESEARCH_NOTES_PATHS"

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
    paths = []
    runtime_path = runtime_universe_path()
    if runtime_path.exists():
        paths.append(runtime_path)
    configured = os.environ.get(A_SHARE_UNIVERSE_ENV)
    if configured:
        paths.extend(Path(value) for value in configured.split(os.pathsep) if value.strip())
    return dedupe_paths(paths)


def research_note_paths() -> List[Path]:
    paths = []
    runtime_path = runtime_research_path()
    if runtime_path.exists():
        paths.append(runtime_path)
    configured = os.environ.get(RESEARCH_NOTES_ENV)
    if configured:
        paths.extend(Path(value) for value in configured.split(os.pathsep) if value.strip())
    return dedupe_paths(paths)


def runtime_universe_path() -> Path:
    configured = os.environ.get("MARKET_INTEL_RUNTIME_DIR")
    if configured:
        return Path(configured) / "a_share_universe.csv"
    return repo_root() / "data" / "runtime" / "a_share_universe.csv"


def runtime_research_path() -> Path:
    configured = os.environ.get("MARKET_INTEL_RUNTIME_DIR")
    if configured:
        return Path(configured) / "research_notes.csv"
    return repo_root() / "data" / "runtime" / "research_notes.csv"


def dedupe_paths(paths: List[Path]) -> List[Path]:
    result = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


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
        apply_research_notes(rows, research_note_paths())
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


def apply_research_notes(items: List[PoolItem], paths: List[Path]) -> None:
    if not paths:
        return
    notes = read_research_notes(paths)
    if not notes:
        return
    for item in items:
        if not item.symbol:
            continue
        note = notes.get(normalize_symbol_text(item.symbol))
        if not note:
            continue
        item.raw["research_note"] = note
        item.raw["research_status"] = note.get("status")
        item.raw["research_source_file"] = note.get("source_file")
        item.raw["research_schema"] = "research_notes_v1"
        item.raw["research_thesis"] = note.get("thesis")
        item.raw["research_evidence"] = note.get("evidence")
        item.raw["research_invalidation"] = note.get("invalidation")


def read_research_notes(paths: List[Path]) -> Dict[str, Dict[str, object]]:
    notes: Dict[str, Dict[str, object]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                symbol = normalize_symbol_text(first_value(row, ["symbol", "code", "证券代码", "股票代码", "代码"]))
                if not symbol:
                    continue
                note = {
                    "symbol": symbol,
                    "name": first_value(row, ["name", "company", "证券名称", "股票名称", "名称"]),
                    "status": normalize_research_status(first_value(row, ["status", "review_status", "研究状态", "状态"])),
                    "thesis": first_value(row, ["thesis", "logic", "核心逻辑", "研究结论", "逻辑"]),
                    "evidence": first_value(row, ["evidence", "key_evidence", "关键证据", "证据"]),
                    "invalidation": first_value(row, ["invalidation", "risk", "bear_case", "证伪风险", "风险"]),
                    "source": first_value(row, ["source", "来源", "数据源"]),
                    "updated_at": first_value(row, ["updated_at", "date", "日期", "更新日期"]),
                    "source_file": path.name,
                    "schema": "research_notes_v1",
                }
                notes[note["symbol"]] = note
    return notes


def normalize_research_status(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"reviewed", "confirmed", "已复核", "已确认", "确认"}:
        return "reviewed"
    if text in {"blocked", "invalid", "驳回", "阻塞"}:
        return "blocked"
    return "draft"


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


def list_pools() -> List[Dict[str, object]]:
    return [
        {
            "id": pool,
            "filename": definition["filename"],
            "scope": definition["scope"],
            "description": definition["description"],
            "is_default": pool == DEFAULT_POOL,
            "coverage_boundary": pool_coverage_boundary(definition["scope"]),
            "next_command": pool_next_command(pool),
            "done_when": "已运行 coverage 并确认覆盖状态、基础清单接入情况和下一步补数命令。",
        }
        for pool, definition in sorted(POOL_REGISTRY.items())
    ]


def pool_coverage_boundary(scope: str) -> str:
    if scope == "all_a_seed":
        return "seed_until_a_share_universe_imported"
    if scope == "theme":
        return "theme_seed"
    return "custom"


def pool_next_command(pool: str) -> str:
    if pool == DEFAULT_POOL:
        return "market-intel pool coverage --text"
    return "market-intel pool coverage --text --pool %s" % pool
