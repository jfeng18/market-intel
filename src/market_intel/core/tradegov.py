import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .csv_importer import command_path, write_json_records
from .runtime import display_path
from .symbols import normalize_symbol_input


TRADEGOV_COMMAND = ["tradegov", "status-current", "--json"]
TRADEGOV_REPO = Path("/Users/alice/Desktop/tradegov")
TRADEGOV_MODULE_COMMAND = ["python3", "-m", "tradegov.cli", "status-current", "--json"]


def import_tradegov_holdings(
    output_path: Optional[Path],
    dry_run: bool = False,
    runtime: bool = False,
    command: Optional[List[str]] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, object]:
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    source_command = command or TRADEGOV_COMMAND
    payload: Dict[str, Any] = {}

    if raw_payload is not None:
        payload = raw_payload
    else:
        payload, command_errors = read_tradegov_status(source_command)
        errors.extend(command_errors)

    records: List[Dict[str, object]] = []
    if not errors:
        records, warnings, errors = tradegov_holdings_records(payload)
    if not errors and not records:
        errors.append(issue("TRADEGOV_HOLDINGS_EMPTY", "tradegov status-current 未返回可导入持仓。", {}))

    written = False
    if not errors and not dry_run and output_path is not None:
        write_json_records(output_path, "holdings", records)
        written = True

    return {
        "kind": "holdings",
        "source_kind": "tradegov.status_current",
        "source": "tradegov status-current",
        "input": "tradegov:status-current",
        "output": command_path(output_path) if output_path else None,
        "record_key": "holdings",
        "record_count": len(records),
        "dry_run": dry_run,
        "written": written,
        "read_only_source": True,
        "tradegov_written": False,
        "preview": records[:5],
        "source_metadata": {
            "provider": "tradegov",
            "command": " ".join(source_command),
            "read_only": True,
            "output": display_path(output_path) if output_path else None,
        },
        "next_commands": next_commands(written, dry_run, runtime, bool(errors)),
        "warnings": warnings,
        "errors": errors,
    }


def read_tradegov_status(command: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, object]]]:
    executable = command[0] if command else ""
    cwd = None
    effective_command = list(command or TRADEGOV_COMMAND)
    if not executable:
        return {}, [
            issue(
                "TRADEGOV_NOT_FOUND",
                "tradegov command 不在 PATH，无法读取 status-current。",
                {"command": " ".join(command or TRADEGOV_COMMAND)},
            )
        ]
    if shutil.which(executable) is None:
        if effective_command == TRADEGOV_COMMAND and TRADEGOV_REPO.exists():
            effective_command = TRADEGOV_MODULE_COMMAND
            cwd = str(TRADEGOV_REPO)
        else:
            return {}, [
                issue(
                    "TRADEGOV_NOT_FOUND",
                    "tradegov command 不在 PATH，无法读取 status-current。",
                    {"command": " ".join(command or TRADEGOV_COMMAND)},
                )
            ]
    try:
        completed = subprocess.run(effective_command, check=False, capture_output=True, text=True, timeout=30, cwd=cwd)
    except subprocess.TimeoutExpired:
        return {}, [issue("TRADEGOV_TIMEOUT", "tradegov status-current 超时。", {"timeout_seconds": 30})]
    except Exception as exc:
        return {}, [
            issue(
                "TRADEGOV_STATUS_FAILED",
                "tradegov status-current 执行失败。",
                {"exception": type(exc).__name__},
            )
        ]
    if completed.returncode != 0:
        return {}, [
            issue(
                "TRADEGOV_STATUS_NONZERO",
                "tradegov status-current 返回非零退出码。",
                {"returncode": completed.returncode},
            )
        ]
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}, [issue("TRADEGOV_STATUS_BAD_JSON", "tradegov status-current 未返回 JSON。", {})]
    if not isinstance(payload, dict):
        return {}, [issue("TRADEGOV_STATUS_BAD_JSON", "tradegov status-current JSON 顶层不是对象。", {})]
    return payload, []


def tradegov_holdings_records(payload: Dict[str, Any]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    candidates = find_holdings_candidates(payload)
    warnings: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    records: List[Dict[str, object]] = []
    for index, row in enumerate(candidates):
        if not isinstance(row, dict):
            continue
        record, row_warnings, row_errors = parse_tradegov_holding(row, index)
        warnings.extend(row_warnings)
        errors.extend(row_errors)
        if record:
            records.append(record)
    records = dedupe_holdings(records)
    return records, warnings, errors


def find_holdings_candidates(payload: Dict[str, Any]) -> List[object]:
    paths = [
        ("data", "holdings"),
        ("data", "positions"),
        ("data", "current", "holdings"),
        ("data", "current", "positions"),
        ("holdings",),
        ("positions",),
        ("current", "holdings"),
        ("current", "positions"),
    ]
    for path in paths:
        value: Any = payload
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, list):
            return value
    return []


def parse_tradegov_holding(row: Dict[str, Any], index: int) -> Tuple[Optional[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    warnings: List[Dict[str, object]] = []
    symbol = normalize_symbol_input(first_value(row, ["symbol", "code", "ticker", "stock_code", "证券代码", "股票代码"]))
    if symbol and symbol.isdigit() and len(symbol) < 6:
        symbol = symbol.zfill(6)
    if not symbol or not (symbol.isdigit() and len(symbol) == 6):
        return None, warnings, [
            issue("TRADEGOV_HOLDING_SYMBOL_MISSING", "tradegov 持仓缺少有效 6 位 A 股代码。", {"index": index})
        ]
    name = first_value(row, ["name", "security_name", "stock_name", "证券名称", "股票名称"]) or symbol
    quantity = optional_float(first_value(row, ["quantity", "qty", "shares", "volume", "持仓数量", "持股数量"]))
    cost_price = optional_float(first_value(row, ["cost_price", "cost", "avg_cost", "成本价", "持仓成本"]))
    if not first_value(row, ["name", "security_name", "stock_name", "证券名称", "股票名称"]):
        warnings.append(issue("TRADEGOV_HOLDING_NAME_DEFAULTED", "tradegov 持仓名称缺失，已使用 symbol。", {"index": index, "symbol": symbol}))
    return {
        "symbol": symbol,
        "name": str(name),
        "quantity": quantity,
        "cost_price": cost_price,
        "source": "tradegov:status-current",
    }, warnings, []


def first_value(row: Dict[str, Any], names: Iterable[str]) -> object:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(str(name).lower())
        if value not in (None, ""):
            return value
    return ""


def optional_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        result = float(str(value).replace(",", ""))
        if result != result or result in (float("inf"), float("-inf")):
            return None
        return result
    except (TypeError, ValueError):
        return None


def dedupe_holdings(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    by_symbol: Dict[str, Dict[str, object]] = {}
    order: List[str] = []
    for record in records:
        symbol = str(record.get("symbol") or "")
        if not symbol:
            continue
        if symbol not in by_symbol:
            by_symbol[symbol] = dict(record)
            order.append(symbol)
            continue
        current = by_symbol[symbol]
        current["quantity"] = add_optional(current.get("quantity"), record.get("quantity"))
        if current.get("name") == symbol and record.get("name"):
            current["name"] = record.get("name")
        if current.get("cost_price") is None and record.get("cost_price") is not None:
            current["cost_price"] = record.get("cost_price")
    return [by_symbol[symbol] for symbol in order]


def add_optional(left: object, right: object) -> Optional[float]:
    left_float = optional_float(left)
    right_float = optional_float(right)
    if left_float is None:
        return right_float
    if right_float is None:
        return left_float
    return left_float + right_float


def next_commands(written: bool, dry_run: bool, runtime: bool, has_errors: bool) -> List[str]:
    if has_errors:
        return []
    if dry_run and runtime:
        return [
            "market-intel import holdings --from-tradegov --runtime --json",
            "market-intel pool coverage --runtime --json",
        ]
    if written and runtime:
        return [
            "market-intel validate runtime --json",
            "market-intel portfolio review --runtime --json",
            "market-intel agent briefing --profile livermore --json",
        ]
    return []


def issue(code: str, message: str, detail: Dict[str, object]) -> Dict[str, object]:
    return {"code": code, "message": message, "detail": detail}
