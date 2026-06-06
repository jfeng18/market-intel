from datetime import datetime
from typing import Any, Dict, List, Optional

from market_intel import __version__


SCHEMA_VERSION = "0.1"


def envelope(
    command: str,
    data: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    source: Optional[str] = None,
    ok: Optional[bool] = None,
) -> Dict[str, Any]:
    error_list = errors or []
    return {
        "ok": len(error_list) == 0 if ok is None else ok,
        "command": command,
        "version": __version__,
        "data": data or {},
        "warnings": warnings or [],
        "errors": error_list,
        "meta": {
            "generated_at": datetime.now().astimezone().isoformat(),
            "schema_version": SCHEMA_VERSION,
            "source": source,
        },
    }


def error(code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "detail": detail or {},
    }

