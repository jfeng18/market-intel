from scripts.privacy_scan import scan_file


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
