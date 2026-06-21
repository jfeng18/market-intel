import shutil
import os
import json
from pathlib import Path
from typing import Dict, List, Optional

from .pool_loader import repo_root


EXAMPLES_DIR = repo_root() / "examples"
EXAMPLE_QUOTES = EXAMPLES_DIR / "quotes.example.json"
EXAMPLE_HOLDINGS = EXAMPLES_DIR / "holdings.example.json"
EXAMPLE_UNIVERSE = EXAMPLES_DIR / "a_share_universe.csv.example"
EXAMPLE_RESEARCH = EXAMPLES_DIR / "research_notes.csv.example"


def init_runtime(force: bool = False) -> Dict[str, object]:
    runtime_dir = runtime_dir_path()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    quotes_path = runtime_quotes_path()
    holdings_path = runtime_holdings_path()
    universe_path = runtime_universe_path()
    research_path = runtime_research_path()
    files = [
        copy_template(EXAMPLE_QUOTES, quotes_path, force),
        copy_template(EXAMPLE_HOLDINGS, holdings_path, force),
        copy_template(EXAMPLE_UNIVERSE, universe_path, force),
        copy_template(EXAMPLE_RESEARCH, research_path, force),
    ]
    manifest = write_runtime_manifest(
        {
            "mode": "sample",
            "source": "init.runtime",
            "datasets": {
                "quotes": "sample",
                "holdings": "sample",
                "universe": "sample",
                "research": "sample",
            },
        }
    )
    return {
        "runtime_dir": display_path(runtime_dir),
        "files": files,
        "profile": runtime_profile(),
        "manifest": manifest,
        "next_steps": [
            "Replace sample quotes via: market-intel import quotes <quotes.csv> --runtime --dry-run --json",
            "Replace sample holdings via: market-intel import holdings <holdings.csv> --runtime --dry-run --json",
            "Replace sample universe via: market-intel import universe <a_share_universe.csv> --runtime --dry-run --json",
            "Replace sample research notes via: market-intel import research <research_notes.csv> --runtime --dry-run --json",
            "Run: market-intel status runtime --text",
            "Run: market-intel dashboard --text",
        ],
    }


def runtime_paths() -> Dict[str, str]:
    return {
        "quotes": str(runtime_quotes_path()),
        "holdings": str(runtime_holdings_path()),
        "universe": str(runtime_universe_path()),
        "research": str(runtime_research_path()),
        "manifest": str(runtime_manifest_path()),
    }


def runtime_missing_files() -> List[str]:
    missing = []
    quotes_path = runtime_quotes_path()
    holdings_path = runtime_holdings_path()
    if not quotes_path.exists():
        missing.append(str(quotes_path))
    if not holdings_path.exists():
        missing.append(str(holdings_path))
    return missing


def runtime_dir_path() -> Path:
    configured = os.environ.get("MARKET_INTEL_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return repo_root() / "data" / "runtime"


def runtime_quotes_path() -> Path:
    return runtime_dir_path() / "quotes.json"


def runtime_holdings_path() -> Path:
    return runtime_dir_path() / "holdings.json"


def runtime_universe_path() -> Path:
    return runtime_dir_path() / "a_share_universe.csv"


def runtime_research_path() -> Path:
    return runtime_dir_path() / "research_notes.csv"


def runtime_manifest_path() -> Path:
    return runtime_dir_path() / "runtime_manifest.json"


def runtime_profile() -> Dict[str, object]:
    manifest = read_runtime_manifest()
    mode = str(manifest.get("mode") or "runtime")
    datasets = manifest.get("datasets", {}) if isinstance(manifest.get("datasets"), dict) else {}
    sample_datasets = sorted(key for key, value in datasets.items() if str(value) == "sample")
    warnings = []
    if mode == "sample" or sample_datasets:
        warnings.append(
            {
                "code": "RUNTIME_SAMPLE_DATA",
                "message": "runtime 当前来自 init 示例数据，只适合试跑流程；正式复盘前请导入真实行情、持仓、全 A 清单和研究证据。",
                "detail": {"sample_datasets": sample_datasets},
            }
        )
    return {
        "mode": "sample" if mode == "sample" or sample_datasets else "runtime",
        "manifest": display_path(runtime_manifest_path()),
        "sample_datasets": sample_datasets,
        "warnings": warnings,
    }


def read_runtime_manifest() -> Dict[str, object]:
    path = runtime_manifest_path()
    if not path.exists():
        return {"mode": "runtime", "datasets": {}}
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {"mode": "runtime", "datasets": {}}
    return data if isinstance(data, dict) else {"mode": "runtime", "datasets": {}}


def write_runtime_manifest(data: Dict[str, object]) -> Dict[str, object]:
    path = runtime_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"path": display_path(path), "status": "written"}


def mark_runtime_dataset_imported(kind: str, source: str = "import", metadata: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    manifest = read_runtime_manifest()
    datasets = manifest.get("datasets", {}) if isinstance(manifest.get("datasets"), dict) else {}
    datasets[str(kind)] = "runtime"
    manifest["datasets"] = datasets
    manifest["source"] = source
    if metadata:
        manifest[str(kind)] = metadata
    manifest["mode"] = "sample" if any(str(value) == "sample" for value in datasets.values()) else "runtime"
    return write_runtime_manifest(manifest)


def copy_template(source: Path, target: Path, force: bool) -> Dict[str, object]:
    if target.exists() and not force:
        return {
            "path": display_path(target),
            "status": "kept",
            "message": "Existing file kept. Use --force to overwrite.",
        }
    shutil.copyfile(source, target)
    return {
        "path": display_path(target),
        "status": "written",
        "message": "Template written.",
    }


def display_path(path: Path) -> str:
    root = repo_root()
    try:
        return str(path.relative_to(root))
    except ValueError:
        if path.is_absolute() and path.parent.name:
            return "%s/%s" % (path.parent.name, path.name)
        return str(path)
