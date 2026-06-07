from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .symbols import normalize_symbol_text


@dataclass
class Exposure:
    layer: str
    sub_sector: str
    section: str
    role: Optional[str]
    priority: str
    logic: str
    raw_row: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "sub_sector": self.sub_sector,
            "section": self.section,
            "role": self.role,
            "priority": self.priority,
            "logic": self.logic,
            "raw_row": self.raw_row,
        }


@dataclass
class PoolItem:
    symbol: Optional[str]
    name: str
    market: str
    instrument_type: str
    priority: str
    tradable: bool
    primary_layer: str
    primary_sub_sector: str
    primary_role: Optional[str]
    logic: str
    exposures: List[Exposure] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    data_quality_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "instrument_type": self.instrument_type,
            "priority": self.priority,
            "tradable": self.tradable,
            "primary_layer": self.primary_layer,
            "primary_sub_sector": self.primary_sub_sector,
            "primary_role": self.primary_role,
            "logic": self.logic,
            "exposures": [exposure.to_dict() for exposure in self.exposures],
            "raw": self.raw,
            "data_quality_flags": sorted(set(self.data_quality_flags)),
        }


@dataclass
class Quote:
    symbol: str
    trade_date: str
    last_price: Optional[float]
    change_pct: float
    amount: float
    amount_ratio: float
    turnover_rate: float
    amplitude_pct: float
    is_limit_up: bool
    is_stage_high: bool
    intraday_fade_pct: float
    name: str = ""
    source: str = "mock"

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Quote":
        return cls(
            symbol=normalize_symbol_text(value["symbol"]),
            trade_date=str(value.get("trade_date") or ""),
            last_price=optional_float(value.get("last_price")),
            change_pct=float(value.get("change_pct") or 0),
            amount=float(value.get("amount") or 0),
            amount_ratio=float(value.get("amount_ratio") or 0),
            turnover_rate=float(value.get("turnover_rate") or 0),
            amplitude_pct=float(value.get("amplitude_pct") or 0),
            is_limit_up=parse_bool(value.get("is_limit_up")),
            is_stage_high=parse_bool(value.get("is_stage_high")),
            intraday_fade_pct=float(value.get("intraday_fade_pct") or 0),
            name=str(value.get("name") or ""),
            source=str(value.get("source") or "mock"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "trade_date": self.trade_date,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "amount": self.amount,
            "amount_ratio": self.amount_ratio,
            "turnover_rate": self.turnover_rate,
            "amplitude_pct": self.amplitude_pct,
            "is_limit_up": self.is_limit_up,
            "is_stage_high": self.is_stage_high,
            "intraday_fade_pct": self.intraday_fade_pct,
            "source": self.source,
        }


@dataclass
class Hotspot:
    layer: str
    sub_sector: str
    score: float
    member_count: int
    active_member_count: int
    leaders: List[Dict[str, Any]]
    score_breakdown: Dict[str, float]
    signals: List[str]
    risks: List[str]
    explain: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "sub_sector": self.sub_sector,
            "score": self.score,
            "member_count": self.member_count,
            "active_member_count": self.active_member_count,
            "leaders": self.leaders,
            "score_breakdown": self.score_breakdown,
            "signals": self.signals,
            "risks": self.risks,
            "explain": self.explain,
        }


@dataclass
class Holding:
    symbol: str
    name: str
    quantity: Optional[float] = None
    source: str = "mock"

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Holding":
        return cls(
            symbol=normalize_symbol_text(value["symbol"]),
            name=str(value.get("name") or ""),
            quantity=optional_float(value.get("quantity")),
            source=str(value.get("source") or "mock"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "source": self.source,
        }


def optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"", "-", "--", "nan", "none", "null"}:
        return False
    if text in {"1", "true", "yes", "y", "是", "涨停", "新高", "√"}:
        return True
    if text in {"0", "false", "no", "n", "否", "未涨停", "不是", "x"}:
        return False
    raise ValueError("invalid boolean value: %r" % value)
