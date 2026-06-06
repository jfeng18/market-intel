import subprocess

from market_intel.cli import handle_init_runtime, handle_watchlist
from market_intel.core.fixtures import load_mock_holdings, load_mock_quotes
from market_intel.core.pool_loader import load_pool
from market_intel.core.text_report import render_watchlist_text
from market_intel.core.watchlist import build_watchlist_report


def test_watchlist_report_prioritizes_holdings():
    report = build_watchlist_report(load_pool(), load_mock_quotes(), load_mock_holdings(), top=6)

    assert report["count"] == 6
    assert report["items"]
    assert report["holding_count"] > 0
    assert report["items"][0]["is_holding"] is True
    assert report["risk_flags"]


def test_watchlist_cli_requires_source():
    payload = handle_watchlist("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "WATCHLIST_SOURCE_REQUIRED"


def test_watchlist_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_init_runtime(force=False)

    payload = handle_watchlist("ai-energy", use_mock=False, use_runtime=True, top=4)

    assert payload["ok"] is True
    assert payload["command"] == "watchlist"
    assert payload["data"]["mode"] == "runtime"
    assert 0 < payload["data"]["count"] <= 4


def test_watchlist_text_renderer():
    payload = handle_watchlist("ai-energy", use_mock=True, top=4)
    text = render_watchlist_text(payload)

    assert "market-intel watchlist" in text
    assert "观察项" in text
    assert "风险汇总" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_watchlist_text_cli_smoke(cli_cmd):
    result = subprocess.run(
        cli_cmd(
            "watchlist",
            "--mock",
            "--top",
            "3",
            "--text",
        ),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel watchlist" in result.stdout
    assert "观察项" in result.stdout
