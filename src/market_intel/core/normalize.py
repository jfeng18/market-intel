import re
from typing import Dict, List, Optional, Tuple

from .models import Exposure, PoolItem
from .symbols import normalize_symbol_input


SYMBOL_RE = re.compile(r"^(?:\d{6}|\d{4}\.TW|\d{6}\.KS|\d{4,5}\.HK|[A-Z]{1,5}(?:\.[A-Z])?)$")
CN_A_RE = re.compile(r"^\d{6}$")
TW_RE = re.compile(r"^\d{4}\.TW$")
KR_RE = re.compile(r"^\d{6}\.KS$")
HK_RE = re.compile(r"^\d{4,5}\.HK$")
US_RE = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")
SYMBOL_IN_TEXT_RE = re.compile(r"\b(?:\d{6}|\d{4}\.TW|\d{6}\.KS|\d{4,5}\.HK|[A-Z]{1,5}(?:\.[A-Z])?)\b")

PENDING_MARKERS = {"科创板", "港股", "IPO 已过会", "IPO已过会"}
NON_SECURITY_MARKERS = {"", "—", "-", "国产化率"}
PRIORITY_RANK = {"P1": 0, "P2": 1, "P3": 2, "UNKNOWN": 9}


def normalize_row(row: Dict[str, str], raw_row: int) -> PoolItem:
    raw = {
        "raw_row": raw_row,
        "raw_status": clean(row.get("status")),
        "raw_priority": clean(row.get("priority")),
        "raw_section": clean(row.get("section")),
        "raw_level": clean(row.get("level")),
        "raw_company": clean(row.get("company")),
        "raw_code": clean(row.get("code")),
        "raw_desc": clean(row.get("desc")),
        "raw_notes": clean(row.get("notes")),
    }
    flags = []
    raw_code = raw["raw_code"]
    raw_company = raw["raw_company"]
    raw_desc = raw["raw_desc"]

    symbol = normalize_symbol(raw_code) if is_symbol(raw_code) else None
    recovered_symbol, recovered_logic = recover_symbol_from_desc(raw_desc)
    column_shift = False

    if symbol is None and recovered_symbol and can_recover_symbol(raw_code, raw_company, raw_desc):
        symbol = recovered_symbol
        column_shift = True
        flags.append("column_shift_suspected")

    if not is_symbol(raw_code):
        flags.append("invalid_symbol")

    instrument_type = infer_instrument_type(raw_code, symbol, raw_company, raw_desc)
    if instrument_type == "pending_listing":
        flags.append("pending_listing")
    if instrument_type == "non_security":
        flags.append("non_security_row")

    market = infer_market(symbol)
    tradable = instrument_type == "security" and symbol is not None
    priority = normalize_priority(raw["raw_priority"])
    layer = infer_layer(raw["raw_section"])
    sub_sector = infer_sub_sector(raw["raw_section"])
    if layer == "其他":
        flags.append("unknown_layer")

    role = infer_role(raw["raw_level"], raw_company if column_shift else "", raw_desc)
    if role is None:
        flags.append("missing_role")

    name = infer_name(raw_company, raw_code, column_shift, symbol)
    logic = recovered_logic if column_shift and recovered_logic else raw_desc
    logic = cleanup_logic(logic)

    exposure = Exposure(
        layer=layer,
        sub_sector=sub_sector,
        section=raw["raw_section"],
        role=role,
        priority=priority,
        logic=logic,
        raw_row=raw_row,
    )

    return PoolItem(
        symbol=symbol,
        name=name,
        market=market,
        instrument_type=instrument_type,
        priority=priority,
        tradable=tradable,
        primary_layer=layer,
        primary_sub_sector=sub_sector,
        primary_role=role,
        logic=logic,
        exposures=[exposure],
        raw=raw,
        data_quality_flags=flags,
    )


def merge_pool_items(items: List[PoolItem]) -> List[PoolItem]:
    merged = {}
    order = []
    for item in items:
        key = item.symbol if item.symbol else "__row_%s" % item.raw.get("raw_row")
        if key not in merged:
            merged[key] = item
            order.append(key)
            continue

        existing = merged[key]
        existing_flags = list(existing.data_quality_flags)
        existing.exposures.extend(item.exposures)
        existing.data_quality_flags.extend(item.data_quality_flags)
        existing.data_quality_flags.append("duplicate_symbol_exposure")
        existing.priority = best_priority(existing.priority, item.priority)
        existing.raw.setdefault("merged_raw_rows", [existing.raw.get("raw_row")])
        existing.raw["merged_raw_rows"].append(item.raw.get("raw_row"))
        merge_flag_sources(existing.raw, existing_flags, item.raw, item.data_quality_flags)
        merge_raw_metadata(existing.raw, item.raw)

    for item in merged.values():
        if len(item.exposures) > 1:
            item.data_quality_flags.append("duplicate_symbol_exposure")
        apply_primary_exposure(item)
        item.data_quality_flags = sorted(set(item.data_quality_flags))
    return [merged[key] for key in order]


def merge_flag_sources(
    existing_raw: Dict[str, object],
    existing_flags: List[str],
    incoming_raw: Dict[str, object],
    incoming_flags: List[str],
) -> None:
    sources = existing_raw.setdefault("_quality_flag_sources", {})
    if not isinstance(sources, dict):
        return
    existing_snapshot = quality_source_snapshot(existing_raw, existing_flags)
    incoming_snapshot = quality_source_snapshot(incoming_raw, incoming_flags)
    for flag in existing_flags:
        if not has_quality_source(sources, flag):
            append_quality_source(sources, flag, existing_snapshot)
    for flag in incoming_flags:
        append_quality_source(sources, flag, incoming_snapshot)
    append_quality_source(sources, "duplicate_symbol_exposure", existing_snapshot)
    append_quality_source(sources, "duplicate_symbol_exposure", incoming_snapshot)


def has_quality_source(sources: Dict[object, object], flag: object) -> bool:
    rows = sources.get(str(flag or "").strip())
    return isinstance(rows, list) and bool(rows)


def append_quality_source(sources: Dict[object, object], flag: object, snapshot: Dict[str, object]) -> None:
    flag_text = str(flag or "").strip()
    if not flag_text:
        return
    rows = sources.setdefault(flag_text, [])
    if not isinstance(rows, list):
        return
    raw_row = snapshot.get("raw_row")
    if raw_row is not None and any(isinstance(row, dict) and row.get("raw_row") == raw_row for row in rows):
        return
    rows.append(dict(snapshot))


def quality_source_snapshot(raw: Dict[str, object], flags: List[str]) -> Dict[str, object]:
    return {
        "raw_row": raw.get("raw_row"),
        "source_file": raw.get("pool_source_file"),
        "source": raw.get("pool_source"),
        "raw_status": raw.get("raw_status"),
        "raw_priority": raw.get("raw_priority"),
        "raw_company": raw.get("raw_company"),
        "raw_code": raw.get("raw_code"),
        "raw_desc": raw.get("raw_desc"),
        "raw_section": raw.get("raw_section"),
        "raw_level": raw.get("raw_level"),
        "raw_notes": raw.get("raw_notes"),
        "flags": sorted(set(flags)),
    }


def merge_raw_metadata(existing: Dict[str, object], incoming: Dict[str, object]) -> None:
    append_raw_list(existing, "merged_pool_sources", existing.get("pool_source"))
    append_raw_list(existing, "merged_pool_sources", incoming.get("pool_source"))
    append_raw_list(existing, "merged_pool_source_files", existing.get("pool_source_file"))
    append_raw_list(existing, "merged_pool_source_files", incoming.get("pool_source_file"))
    if incoming.get("universe_schema"):
        existing["universe_schema"] = incoming.get("universe_schema")
        existing["universe_source_file"] = incoming.get("universe_source_file")
        existing["universe_industry"] = incoming.get("universe_industry")
        existing["universe_concepts"] = incoming.get("universe_concepts")
        existing["universe_index_membership"] = incoming.get("universe_index_membership")
        existing["universe_listing_status"] = incoming.get("universe_listing_status")
    if incoming.get("research_schema"):
        existing["research_schema"] = incoming.get("research_schema")
        existing["research_note"] = incoming.get("research_note")
        existing["research_status"] = incoming.get("research_status")
        existing["research_source_file"] = incoming.get("research_source_file")
        existing["research_thesis"] = incoming.get("research_thesis")
        existing["research_evidence"] = incoming.get("research_evidence")
        existing["research_invalidation"] = incoming.get("research_invalidation")


def append_raw_list(raw: Dict[str, object], key: str, value: object) -> None:
    text = str(value or "").strip()
    if not text:
        return
    values = raw.setdefault(key, [])
    if isinstance(values, list) and text not in values:
        values.append(text)


def pool_item_primary_exposure(item: PoolItem) -> Exposure:
    return sorted(item.exposures, key=lambda exposure: (priority_rank(exposure.priority), exposure.raw_row))[0]


def apply_primary_exposure(item: PoolItem) -> None:
    exposure = pool_item_primary_exposure(item)
    item.primary_layer = exposure.layer
    item.primary_sub_sector = exposure.sub_sector
    item.primary_role = exposure.role
    item.logic = exposure.logic


def find_pool_item(items: List[PoolItem], symbol: str) -> Optional[PoolItem]:
    wanted = normalize_symbol(symbol)
    for item in items:
        if item.symbol and normalize_symbol(item.symbol) == wanted:
            return item
    return None


def explain_pool_item(item: PoolItem) -> Dict[str, object]:
    exposure_count = len(item.exposures)
    signals = []
    risks = []
    questions = []

    if exposure_count > 1:
        signals.append("multi_chain_exposure")
        risks.append("theme_concentration")
    if item.instrument_type != "security" or not item.tradable:
        risks.append("not_tradable")
    if item.data_quality_flags:
        questions.append("使用前先核对数据质量标记。")
    if "missing_role" in item.data_quality_flags:
        questions.append("确认该公司在子链路中的角色。")
    if not item.logic:
        questions.append("补充一句话公司逻辑。")

    facts = {
        "symbol": item.symbol,
        "name": item.name,
        "market": item.market,
        "instrument_type": item.instrument_type,
        "priority": item.priority,
        "tradable": item.tradable,
        "primary_layer": item.primary_layer,
        "primary_sub_sector": item.primary_sub_sector,
        "primary_role": item.primary_role,
        "exposure_count": exposure_count,
    }

    return {
        "item": item.to_dict(),
        "facts": facts,
        "signals": signals,
        "risks": risks,
        "questions": questions,
        "data_quality_flags": item.to_dict()["data_quality_flags"],
        "exposures": [exposure.to_dict() for exposure in item.exposures],
        "explain": build_explain_text(item),
    }


def build_explain_text(item: PoolItem) -> str:
    name = item.name
    symbol = item.symbol or "未上市"
    base = "%s (%s) 归属 %s / %s" % (
        name,
        symbol,
        item.primary_layer,
        item.primary_sub_sector,
    )
    if item.primary_role:
        base += "，角色为 %s" % item.primary_role
    if len(item.exposures) > 1:
        base += "；共有 %s 条链路暴露" % len(item.exposures)
    if item.logic:
        base += "。逻辑：%s" % item.logic
    return base + "。"


def clean(value: object) -> str:
    return str(value or "").strip()


def is_symbol(value: str) -> bool:
    symbol = normalize_symbol(value)
    return bool(symbol and SYMBOL_RE.match(symbol))


def normalize_symbol(value: Optional[str]) -> Optional[str]:
    return normalize_symbol_input(value)


def recover_symbol_from_desc(desc: str) -> Tuple[Optional[str], str]:
    match = SYMBOL_IN_TEXT_RE.search(desc or "")
    if not match:
        return None, desc
    symbol = match.group(0).upper()
    logic = desc[: match.start()] + desc[match.end() :]
    logic = logic.strip(" |")
    return symbol, logic


def can_recover_symbol(raw_code: str, raw_company: str, raw_desc: str) -> bool:
    return infer_instrument_type(raw_code, None, raw_company, raw_desc) == "unknown"


def infer_instrument_type(raw_code: str, symbol: Optional[str], raw_company: str, raw_desc: str) -> str:
    if symbol:
        return "security"
    if raw_code in PENDING_MARKERS:
        return "pending_listing"
    if raw_code in NON_SECURITY_MARKERS or raw_code.startswith("~"):
        return "non_security"
    text = " ".join([raw_code, raw_company, raw_desc])
    if "国产化率" in text or "缺口" in raw_company or "细分环节" in raw_company:
        return "non_security"
    return "unknown"


def infer_market(symbol: Optional[str]) -> str:
    if not symbol:
        return "UNKNOWN"
    symbol = symbol.upper()
    if CN_A_RE.match(symbol):
        return "CN_A"
    if TW_RE.match(symbol):
        return "TW"
    if KR_RE.match(symbol):
        return "KR"
    if HK_RE.match(symbol):
        return "HK"
    if US_RE.match(symbol):
        return "US"
    return "OTHER"


def normalize_priority(priority: str) -> str:
    priority = (priority or "").strip().upper()
    return priority if priority in PRIORITY_RANK else "UNKNOWN"


def best_priority(left: str, right: str) -> str:
    return left if priority_rank(left) <= priority_rank(right) else right


def priority_rank(priority: str) -> int:
    return PRIORITY_RANK.get(priority, PRIORITY_RANK["UNKNOWN"])


def infer_layer(section: str) -> str:
    section = section or ""
    if section.startswith("行业 /"):
        return "行业"
    if section.startswith("1."):
        return "算力"
    if section.startswith("2."):
        return "运力"
    if section.startswith("3."):
        return "存力"
    if section.startswith("4."):
        return "电力"
    if section.startswith("5."):
        return "人才密度"
    return "其他"


def infer_sub_sector(section: str) -> str:
    text = re.sub(r"^\d+(?:\.\d+)?\s*", "", section or "").strip()
    text = text.replace("🆕", "").strip()
    if text.startswith("行业 /"):
        return text.split("/", 1)[1].strip() or "行业待补"
    if "AI 服务器" in text:
        return "AI 服务器"
    if "半导体设备" in text:
        return "半导体设备"
    if "算力租赁" in text or "AIDC" in text:
        return "算力租赁与 AIDC"
    if "光模块" in text:
        return "光模块"
    if "CPO" in text or "硅光" in text:
        return "CPO / 硅光"
    if "PCB" in text:
        return "PCB"
    if "HBM" in text:
        return "HBM"
    if "液冷" in text:
        return "液冷"
    return text or "其他"


def infer_role(level: str, shifted_role: str, desc: str) -> Optional[str]:
    for candidate in (level, shifted_role):
        role = strip_role_marker(candidate)
        if role:
            return role
    for token in ("龙头", "龙一", "龙二", "龙三", "梯队", "后排", "弹性", "核心", "IDC"):
        if token in (desc or ""):
            return token
    return None


def strip_role_marker(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    if value in {"待确认", "待确认 / 持仓补充"} or value.startswith("待确认 /"):
        return None
    value = value.replace("🇨🇳", "").replace("🌍", "").strip()
    value = re.sub(r"\s+", " ", value)
    return value or None


def infer_name(raw_company: str, raw_code: str, column_shift: bool, symbol: Optional[str]) -> str:
    if column_shift and raw_code:
        return raw_code
    if raw_company:
        return raw_company
    return symbol or "UNKNOWN"


def cleanup_logic(logic: str) -> str:
    logic = (logic or "").strip()
    logic = logic.strip(" |")
    if logic == "—":
        return ""
    return logic


# Small compatibility shim for merge_pool_items.
PoolItem.primary_exposure = pool_item_primary_exposure  # type: ignore[attr-defined]
