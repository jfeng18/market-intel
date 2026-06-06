import shutil
import os
from pathlib import Path
from typing import Dict, List

from .pool_loader import repo_root


EXAMPLES_DIR = repo_root() / "examples"
EXAMPLE_QUOTES = EXAMPLES_DIR / "quotes.example.json"
EXAMPLE_HOLDINGS = EXAMPLES_DIR / "holdings.example.json"


def init_runtime(force: bool = False) -> Dict[str, object]:
    runtime_dir = runtime_dir_path()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    quotes_path = runtime_quotes_path()
    holdings_path = runtime_holdings_path()
    files = [
        copy_template(EXAMPLE_QUOTES, quotes_path, force),
        copy_template(EXAMPLE_HOLDINGS, holdings_path, force),
    ]
    return {
        "runtime_dir": str(runtime_dir),
        "files": files,
        "next_steps": [
            "Edit %s with current quote values." % quotes_path,
            "Edit %s with current holdings." % holdings_path,
            "Run: market-intel brief --runtime --text",
        ],
    }


def runtime_paths() -> Dict[str, str]:
    return {
        "quotes": str(runtime_quotes_path()),
        "holdings": str(runtime_holdings_path()),
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


def copy_template(source: Path, target: Path, force: bool) -> Dict[str, object]:
    if target.exists() and not force:
        return {
            "path": str(target),
            "status": "kept",
            "message": "Existing file kept. Use --force to overwrite.",
        }
    shutil.copyfile(source, target)
    return {
        "path": str(target),
        "status": "written",
        "message": "Template written.",
    }
