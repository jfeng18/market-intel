import json
from pathlib import Path
from typing import List

from .models import Holding, Quote


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"


def load_mock_quotes() -> List[Quote]:
    return load_quotes_file(fixtures_dir() / "mock_quotes.json")


def load_mock_holdings() -> List[Holding]:
    return load_holdings_file(fixtures_dir() / "mock_holdings.json")


def load_quotes_file(path: Path) -> List[Quote]:
    data = read_json_file(path)
    if isinstance(data, dict):
        data = data.get("quotes", [])
    return [Quote.from_dict(value) for value in data]


def load_holdings_file(path: Path) -> List[Holding]:
    data = read_json_file(path)
    if isinstance(data, dict):
        data = data.get("holdings", [])
    return [Holding.from_dict(value) for value in data]


def read_json_fixture(filename: str):
    return read_json_file(fixtures_dir() / filename)


def read_json_file(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
