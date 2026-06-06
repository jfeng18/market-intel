import subprocess

from market_intel.cli import handle_init_runtime, handle_pool_explain, handle_pool_list
from market_intel.core.text_report import render_pool_explain_text


def test_pool_list_returns_json_envelope():
    payload = handle_pool_list("ai-energy")

    assert payload["ok"] is True
    assert payload["command"] == "pool.list"
    assert payload["version"] == "0.1.0"
    assert payload["data"]["count"] > 0
    assert payload["errors"] == []
    assert payload["meta"]["schema_version"] == "0.1"


def test_pool_explain_acceptance_sample_shape():
    payload = handle_pool_explain("ai-energy", "002837")
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "pool.explain"
    assert data["facts"]["symbol"] == "002837"
    assert data["facts"]["name"] == "英维克"
    assert data["facts"]["primary_layer"] == "电力"
    assert data["facts"]["primary_sub_sector"] == "液冷"
    assert "facts" in data
    assert "signals" in data
    assert "risks" in data
    assert "questions" in data
    assert "data_quality_flags" in data
    assert "exposures" in data


def test_pool_explain_not_found_returns_error_envelope():
    payload = handle_pool_explain("ai-energy", "NOPE")

    assert payload["ok"] is False
    assert payload["data"] == {}
    assert payload["errors"][0]["code"] == "POOL_ITEM_NOT_FOUND"


def test_pool_explain_text_renderer():
    payload = handle_pool_explain("ai-energy", "002281")
    text = render_pool_explain_text(payload)

    assert "market-intel pool explain" in text
    assert "光迅科技" in text
    assert "链路暴露" in text
    assert "CPO / 硅光" in text
    assert "交易动作" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_pool_explain_runtime_context(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_pool_explain("ai-energy", "002281", use_runtime=True)
    context = payload["data"]["runtime_context"]

    assert payload["ok"] is True
    assert context["quote"]["symbol"] == "002281"
    assert context["holding"]["symbol"] == "002281"


def test_pool_explain_text_cli_smoke():
    result = subprocess.run(
        [
            ".venv/bin/market-intel",
            "pool",
            "explain",
            "002837",
            "--text",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel pool explain" in result.stdout
    assert "英维克" in result.stdout
    assert "主链路" in result.stdout
