import csv
import json

from market_intel.core.pool_edit import pool_add, pool_remove


def test_pool_add_new_symbol(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("600519", name="贵州茅台", industry="白酒")

    assert not result["errors"]
    assert result["written"] is True
    assert result["symbol"] == "600519"
    assert result["record"]["name"] == "贵州茅台"
    assert result["record"]["industry"] == "白酒"

    universe_path = tmp_path / "runtime" / "a_share_universe.csv"
    assert universe_path.exists()
    with universe_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "600519"
    assert rows[0]["name"] == "贵州茅台"


def test_pool_add_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("600519", dry_run=True)

    assert not result["errors"]
    assert result["dry_run"] is True
    assert result["written"] is False
    assert not (tmp_path / "runtime" / "a_share_universe.csv").exists()


def test_pool_add_duplicate_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    pool_add("600519", name="贵州茅台")
    result = pool_add("600519", name="贵州茅台")

    assert any(w["code"] == "SYMBOL_ALREADY_EXISTS" for w in result["warnings"])
    assert result["written"] is False


def test_pool_add_invalid_symbol(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("abc")

    assert result["errors"]
    assert result["errors"][0]["code"] == "INVALID_SYMBOL"


def test_pool_add_uses_layer_as_industry_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("002837", name="英维克", layer="算力")

    assert result["record"]["industry"] == "算力"


def test_pool_add_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    pool_add("600519", name="贵州茅台", industry="白酒")
    pool_add("000001", name="平安银行", industry="银行")
    result = pool_add("002837", name="英维克", industry="算力")

    assert result["written"] is True
    universe_path = tmp_path / "runtime" / "a_share_universe.csv"
    with universe_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"600519", "000001", "002837"}


def test_pool_remove_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    pool_add("600519", name="贵州茅台")
    pool_add("000001", name="平安银行")
    result = pool_remove("600519")

    assert not result["errors"]
    assert result["written"] is True
    assert result["record"]["name"] == "贵州茅台"

    universe_path = tmp_path / "runtime" / "a_share_universe.csv"
    with universe_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "000001"


def test_pool_remove_nonexistent_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_remove("999999")

    assert any(w["code"] == "SYMBOL_NOT_FOUND" for w in result["warnings"])
    assert result["written"] is False


def test_pool_remove_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    pool_add("600519", name="贵州茅台")
    result = pool_remove("600519", dry_run=True)

    assert not result["errors"]
    assert result["dry_run"] is True
    assert result["written"] is False

    universe_path = tmp_path / "runtime" / "a_share_universe.csv"
    with universe_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1  # still there


def test_pool_remove_invalid_symbol(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_remove("")

    assert result["errors"]


def test_pool_add_next_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("600519")

    assert any("pool coverage" in cmd for cmd in result["next_commands"])


def test_handle_pool_add_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_pool_add

    payload = handle_pool_add("600519", name="贵州茅台")

    assert payload["ok"] is True
    assert payload["command"] == "pool.add"
    assert payload["data"]["symbol"] == "600519"


def test_handle_pool_remove_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_pool_add, handle_pool_remove

    handle_pool_add("600519", name="贵州茅台")
    payload = handle_pool_remove("600519")

    assert payload["ok"] is True
    assert payload["command"] == "pool.remove"


def test_handle_pool_add_error_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_pool_add

    payload = handle_pool_add("abc")

    assert payload["ok"] is False
    assert len(payload["errors"]) > 0


def test_pool_add_no_trading_advice(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = pool_add("600519", name="贵州茅台")
    result_str = json.dumps(result)
    forbidden = {"target_price", "position_size", "must_buy", "must_sell"}
    for key in forbidden:
        assert '"%s"' % key not in result_str
