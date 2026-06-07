from typing import Optional


A_SHARE_EXCHANGES = ("SH", "SZ", "BJ")


def normalize_symbol_input(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    normalized = normalize_a_share_symbol(text)
    return normalized if normalized is not None else text


def normalize_symbol_text(value: object) -> str:
    return normalize_symbol_input(value) or ""


def normalize_a_share_symbol(text: str) -> Optional[str]:
    for prefix in A_SHARE_EXCHANGES:
        for separator in (":", ".", "-", " "):
            marker = "%s%s" % (prefix, separator)
            if text.startswith(marker) and is_six_digit_code(text[len(marker) :]):
                return text[len(marker) :]
        if text.startswith(prefix) and is_six_digit_code(text[len(prefix) :]):
            return text[len(prefix) :]
    for suffix in (".SH", ".SZ", ".BJ"):
        if text.endswith(suffix) and is_six_digit_code(text[: -len(suffix)]):
            return text[: -len(suffix)]
    return None


def is_six_digit_code(value: str) -> bool:
    return len(value) == 6 and value.isdigit()
