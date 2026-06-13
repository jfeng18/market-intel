"""End-to-end integration test: init → sync(mock) → review → journal flow."""

import json
from unittest.mock import MagicMock, patch

import pytest

from market_intel.cli import (
    handle_import_holdings,
    handle_import_research,
    handle_import_universe,
    handle_init_runtime,
    handle_review,
    handle_status_runtime,
    handle_sync_quotes,
)
from market_intel.core.fixtures import load_quotes_file
from market_intel.core.html_report import render_review_html
from market_intel.core.text_report import render_review_text


def _mock_spot_dataframe():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")
    return pd.DataFrame({
        "代码": ["600519", "002837", "300750"],
        "名称": ["贵州茅台", "英维克", "宁德时代"],
        "最新价": [1800.0, 25.5, 220.0],
        "涨跌幅": [2.5, 10.02, -1.2],
        "涨跌额": [44.0, 2.3, -2.7],
        "成交量": [10000, 50000, 80000],
        "成交额": [1800000000, 127500000, 1760000000],
        "振幅": [3.1, 12.5, 2.8],
        "最高": [1820.0, 25.5, 223.0],
        "最低": [1780.0, 22.8, 218.0],
        "今开": [1790.0, 23.2, 222.0],
        "昨收": [1756.0, 23.2, 222.7],
        "量比": [1.2, 3.5, 0.9],
        "换手率": [0.5, 4.2, 0.3],
    })


def _mock_zt():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")
    return pd.DataFrame({"代码": ["002837"], "名称": ["英维克"]})


def _mock_strong():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")
    return pd.DataFrame({
        "代码": ["600519"],
        "名称": ["贵州茅台"],
        "是否新高": ["是"],
    })


def _setup_mock_ak():
    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.return_value = _mock_spot_dataframe()
    mock_ak.stock_zt_pool_em.return_value = _mock_zt()
    mock_ak.stock_zt_pool_strong_em.return_value = _mock_strong()
    return mock_ak


def test_full_flow_init_sync_review_journal(tmp_path, monkeypatch):
    """Complete flow: init runtime → sync quotes → review → journal saved."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    # Step 1: Init runtime
    init_result = handle_init_runtime(force=False)
    assert init_result["ok"] is True

    # Step 2: Sync quotes (mocked akshare)
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        sync_result = handle_sync_quotes(dry_run=False, trade_date="20260608")
    assert sync_result["ok"] is True
    assert sync_result["data"]["record_count"] == 3

    # Verify quotes are loadable
    quotes = load_quotes_file(tmp_path / "runtime" / "quotes.json")
    assert len(quotes) == 3
    assert {quote.trade_date for quote in quotes} == {"2026-06-08"}

    status_result = handle_status_runtime("all-a", max_quote_age_days=9999)
    assert status_result["data"]["freshness"]["errors"] == []
    assert status_result["data"]["freshness"]["latest_trade_date"] == "2026-06-08"

    # Step 3: Review still skips journal while holdings/universe/research are samples.
    review_result = handle_review(no_sync=True, no_save=False)
    assert review_result["command"] == "review"
    data = review_result["data"]
    assert data["journal_saved"] is False
    assert data["journal_status"]["code"] == "sample_runtime"

    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)
    handle_import_universe("examples/a_share_universe.csv.example", use_runtime=True)
    handle_import_research("examples/research_notes.csv.example", use_runtime=True)

    # Step 4: Review after all runtime datasets are real saves journal.
    review_result = handle_review(no_sync=True, no_save=False)
    data = review_result["data"]
    assert data["journal_saved"] is True
    assert data["journal_entry"] is not None

    # Step 5: Verify journal was saved
    journal_dir = tmp_path / "runtime" / "journal"
    assert journal_dir.exists()
    entries = list(journal_dir.glob("*.json"))
    assert len(entries) == 1

    # Step 6: Second review should show changes
    review2 = handle_review(no_sync=True, no_save=False)
    data2 = review2["data"]
    assert data2["changes"]["available"] is True
    assert data2["journal_saved"] is True

    # Now have 2 journal entries
    entries2 = list(journal_dir.glob("*.json"))
    assert len(entries2) == 2


def test_full_flow_text_output(tmp_path, monkeypatch):
    """Text output is complete and human-friendly for the full flow."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    handle_init_runtime(force=False)
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        handle_sync_quotes(dry_run=False, trade_date="20260608")

    review_result = handle_review(no_sync=True, no_save=True)
    text = render_review_text(review_result)

    assert "market-intel review" in text
    assert "数据同步" in text
    assert "今日摘要" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_full_flow_html_output(tmp_path, monkeypatch):
    """HTML output is a valid self-contained page for the full flow."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    handle_init_runtime(force=False)
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        handle_sync_quotes(dry_run=False, trade_date="20260608")

    review_result = handle_review(no_sync=True, no_save=True)
    html = render_review_html(review_result)

    assert "<!DOCTYPE html>" in html
    assert "复盘报告" in html
    assert "</html>" in html

    output_path = tmp_path / "review.html"
    output_path.write_text(html, encoding="utf-8")
    assert output_path.exists()
    assert output_path.stat().st_size > 2000


def test_full_flow_no_runtime_gives_guidance(tmp_path, monkeypatch):
    """Without runtime, review shows clear setup instructions."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    review_result = handle_review(no_sync=True, no_save=True)
    text = render_review_text(review_result)

    assert "错误" in text
    assert "init runtime" in text
    assert "sync quotes" in text


def test_full_flow_sample_runtime_does_not_save_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    handle_init_runtime(force=False)
    review_result = handle_review(no_sync=True, no_save=False)
    text = render_review_text(review_result)

    assert review_result["data"]["journal_saved"] is False
    assert review_result["data"]["journal_status"]["code"] == "sample_runtime"
    assert "样例数据" in text
    assert "market-intel sync quotes" in text
    assert "import holdings <holdings.csv> --runtime" in text
    assert not (tmp_path / "runtime" / "journal").exists()


def test_full_flow_review_sync_failure_does_not_save_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    handle_init_runtime(force=False)
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        handle_sync_quotes(dry_run=False, trade_date="20260608")

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("network down")
    with patch.dict("sys.modules", {"akshare": mock_ak}):
        review_result = handle_review(no_sync=False, no_save=False, provider="akshare")

    assert review_result["ok"] is False
    assert review_result["data"]["sync"]["status"] == "failed"
    assert review_result["data"]["journal_saved"] is False
    assert not (tmp_path / "runtime" / "journal").exists()
