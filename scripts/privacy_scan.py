#!/usr/bin/env python3
import re
import sys
from pathlib import Path


SCAN_ROOTS = [Path("README.md"), Path("docs"), Path("examples"), Path(".github")]
LINE_BUDGETS = {
    Path("README.md"): 160,
    Path("docs/data-model.md"): 180,
    Path("docs/design.md"): 120,
    Path("docs/design-review.md"): 80,
    Path("docs/handoff.md"): 80,
    Path("docs/product.md"): 100,
    Path("docs/review.md"): 80,
}

PATTERNS = [
    ("LOCAL_USER_PATH", re.compile(r"/Users/[^\s:'\"`]+")),
    ("DESKTOP_PATH", re.compile(r"\bDesktop/[^\s:'\"`]+")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("GITEE_TOKEN", re.compile(r"\bgitee[_-]?token\b\s*[:=]", re.IGNORECASE)),
    ("SECRET_ASSIGNMENT", re.compile(r"\b(?:token|secret|password|passwd|api[_-]?key)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE)),
]


def public_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for code, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{line_no}: {code}")
    return findings


def scan_line_budget(path: Path) -> list[str]:
    budget = LINE_BUDGETS.get(path)
    if budget is None:
        return []
    try:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        return []
    if line_count <= budget:
        return []
    return [f"{path}: DOC_TOO_LONG {line_count}>{budget}"]


def main() -> int:
    findings = []
    for path in public_files():
        findings.extend(scan_file(path))
        findings.extend(scan_line_budget(path))
    if findings:
        print("privacy scan found possible public data leaks:", file=sys.stderr)
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
