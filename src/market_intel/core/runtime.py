import shutil
import os
from pathlib import Path
from typing import Dict, List

from .pool_loader import repo_root


EXAMPLES_DIR = repo_root() / "examples"
EXAMPLE_QUOTES = EXAMPLES_DIR / "quotes.example.json"
EXAMPLE_HOLDINGS = EXAMPLES_DIR / "holdings.example.json"
EXAMPLE_UNIVERSE = EXAMPLES_DIR / "a_share_universe.csv.example"


def init_runtime(force: bool = False) -> Dict[str, object]:
    runtime_dir = runtime_dir_path()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    quotes_path = runtime_quotes_path()
    holdings_path = runtime_holdings_path()
    universe_path = runtime_universe_path()
    files = [
        copy_template(EXAMPLE_QUOTES, quotes_path, force),
        copy_template(EXAMPLE_HOLDINGS, holdings_path, force),
        copy_template(EXAMPLE_UNIVERSE, universe_path, force),
    ]
    return {
        "runtime_dir": display_path(runtime_dir),
        "files": files,
        "next_steps": [
            "Edit %s with current quote values." % display_path(quotes_path),
            "Edit %s with current holdings." % display_path(holdings_path),
            "Edit %s with A-share universe rows if you want broader all-a coverage." % display_path(universe_path),
            "Run: market-intel brief --runtime --text",
        ],
    }


def runtime_paths() -> Dict[str, str]:
    return {
        "quotes": str(runtime_quotes_path()),
        "holdings": str(runtime_holdings_path()),
        "universe": str(runtime_universe_path()),
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
