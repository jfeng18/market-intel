from scripts.privacy_scan import LINE_BUDGETS, scan_line_budget, scan_file


def test_privacy_scan_flags_public_path_and_secret(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(
        "bad path /Users/localuser/project\n"
        "token='not-a-real-token-value'\n",
        encoding="utf-8",
    )

    findings = scan_file(path)

    assert any("LOCAL_USER_PATH" in finding for finding in findings)
    assert any("SECRET_ASSIGNMENT" in finding for finding in findings)


def test_privacy_scan_allows_public_examples(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(
        "Use MARKET_INTEL_RUNTIME_DIR to point at runtime data.\n"
        "Run market-intel import schema --json.\n",
        encoding="utf-8",
    )

    assert scan_file(path) == []


def test_privacy_scan_flags_overlong_public_docs(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("\n".join("line" for _ in range(3)), encoding="utf-8")
    original = LINE_BUDGETS.get(path)
    LINE_BUDGETS[path] = 2
    try:
        findings = scan_line_budget(path)
    finally:
        if original is None:
            LINE_BUDGETS.pop(path, None)
        else:
            LINE_BUDGETS[path] = original

    assert findings == [f"{path}: DOC_TOO_LONG 3>2"]


def test_current_public_docs_stay_within_line_budget():
    for path, budget in LINE_BUDGETS.items():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= budget, f"{path} has {line_count} lines; budget is {budget}"
