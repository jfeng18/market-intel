import json
from unittest.mock import MagicMock, patch

import pytest

from market_intel.core.sync import (
    sync_quotes,
    _transform_quotes,
    _safe_float,
    _is_st,
    _limit_up_threshold,
)


def _mock_spot_dataframe():
    """Build a minimal DataFrame-like object mimicking akshare output."""
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")

    data = {
        "代码": ["600519", "002837", "300750", "000001", "688001"],
        "名称": ["贵州茅台", "英维克", "宁德时代", "平安银行", "*ST科创"],
        "最新价": [1800.0, 25.5, 220.0, 12.3, 8.0],
        "涨跌幅": [2.5, 10.02, 15.5, 0.5, 18.0],
        "涨跌额": [44.0, 2.3, 30.0, 0.06, 1.2],
        "成交量": [10000, 50000, 80000, 200000, 5000],
        "成交额": [1800000000, 127500000, 1760000000, 246000000, 40000000],
        "振幅": [3.1, 12.5, 2.8, 1.0, 5.0],
        "最高": [1820.0, 25.5, 223.0, 12.4, 8.2],
        "最低": [1780.0, 22.8, 218.0, 12.2, 7.5],
        "今开": [1790.0, 23.2, 222.0, 12.3, 7.6],
        "昨收": [1756.0, 23.2, 222.7, 12.24, 6.8],
        "量比": [1.2, 3.5, 0.9, 1.0, 2.0],
        "换手率": [0.5, 4.2, 0.3, 0.8, 1.5],
    }
    return pd.DataFrame(data)


def _mock_zt_dataframe():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")
    return pd.DataFrame({"代码": ["002837"], "名称": ["英维克"]})


def _mock_strong_dataframe():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")
    return pd.DataFrame({
        "代码": ["600519", "300750"],
        "名称": ["贵州茅台", "宁德时代"],
        "是否新高": ["是", "否"],
    })


def _setup_mock_ak():
    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.return_value = _mock_spot_dataframe()
    mock_ak.stock_zt_pool_em.return_value = _mock_zt_dataframe()
    mock_ak.stock_zt_pool_strong_em.return_value = _mock_strong_dataframe()
    return mock_ak


def _records_by_symbol(result):
    """Build a symbol->record dict from preview (all records fit in preview[:5])."""
    return {r["symbol"]: r for r in result.get("preview", [])}


def test_sync_quotes_dry_run_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    assert not result["errors"]
    assert result["dry_run"] is True
    assert result["written"] is False
    assert result["record_count"] == 5
    assert not (tmp_path / "runtime" / "quotes.json").exists()


def test_sync_quotes_writes_to_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, trade_date="20260608")

    assert not result["errors"]
    assert result["written"] is True
    assert result["record_count"] == 5

    quotes_path = tmp_path / "runtime" / "quotes.json"
    assert quotes_path.exists()
    data = json.loads(quotes_path.read_text(encoding="utf-8"))
    assert len(data["quotes"]) == 5

    symbols = {q["symbol"] for q in data["quotes"]}
    assert symbols == {"600519", "002837", "300750", "000001", "688001"}


def test_sync_quotes_limit_up_detection(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    by_sym = _records_by_symbol(result)
    assert by_sym["002837"]["is_limit_up"] is True  # in zt pool
    assert by_sym["600519"]["is_limit_up"] is False  # 2.5% < 9.9%


def test_sync_quotes_stage_high_detection(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    by_sym = _records_by_symbol(result)
    assert by_sym["600519"]["is_stage_high"] is True
    assert by_sym["300750"]["is_stage_high"] is False


def test_sync_quotes_chinext_limit_up_threshold(tmp_path, monkeypatch):
    """ChiNext (300xxx) has 20% limit — 15.5% should NOT be flagged as limit-up."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    by_sym = _records_by_symbol(result)
    assert by_sym["300750"]["is_limit_up"] is False  # 15.5% < 19.9% (ChiNext threshold)


def test_sync_quotes_star_st_limit_up_threshold(tmp_path, monkeypatch):
    """STAR Market ST (688xxx) has 20% limit — 18% should NOT be flagged."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    by_sym = _records_by_symbol(result)
    assert by_sym["688001"]["is_limit_up"] is False  # 18% < 19.9% (STAR threshold, ST same)


def test_sync_quotes_symbol_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, symbols=["600519", "000001"], trade_date="20260608")

    assert result["record_count"] == 2
    quotes_path = tmp_path / "runtime" / "quotes.json"
    data = json.loads(quotes_path.read_text(encoding="utf-8"))
    symbols = {q["symbol"] for q in data["quotes"]}
    assert symbols == {"600519", "000001"}


def test_sync_quotes_symbol_filter_zero_padding(tmp_path, monkeypatch):
    """Short symbol input '1' should match '000001' via zfill(6)."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, symbols=["1"], trade_date="20260608")

    assert result["record_count"] == 1
    quotes_path = tmp_path / "runtime" / "quotes.json"
    data = json.loads(quotes_path.read_text(encoding="utf-8"))
    assert data["quotes"][0]["symbol"] == "000001"


def test_sync_quotes_missing_symbol_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, symbols=["999999"], trade_date="20260608")

    assert result["record_count"] == 0
    assert any(w["code"] == "SYNC_SYMBOLS_NOT_FOUND" for w in result["warnings"])


def test_sync_quotes_akshare_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": None}):
        result = sync_quotes(dry_run=True)

    assert result["errors"]
    assert result["errors"][0]["code"] == "AKSHARE_NOT_INSTALLED"
    assert result["next_commands"] == []


def test_sync_quotes_api_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("Connection timeout")

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=True)

    assert result["errors"]
    assert result["errors"][0]["code"] == "AKSHARE_SPOT_FAILED"
    assert result["next_commands"] == []


def test_sync_quotes_empty_market_data(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.return_value = pd.DataFrame()

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=True)

    assert result["errors"]
    assert result["errors"][0]["code"] == "AKSHARE_SPOT_EMPTY"


def test_sync_quotes_zt_api_failure_still_works(tmp_path, monkeypatch):
    """涨停池和强势池 API 失败不阻塞主流程，is_limit_up 回退到启发式。"""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.return_value = _mock_spot_dataframe()
    mock_ak.stock_zt_pool_em.side_effect = Exception("timeout")
    mock_ak.stock_zt_pool_strong_em.side_effect = Exception("timeout")

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    assert not result["errors"]
    assert result["record_count"] == 5

    by_sym = _records_by_symbol(result)
    assert by_sym["002837"]["is_limit_up"] is True  # 10.02% >= 9.9% main board heuristic
    assert by_sym["600519"]["is_limit_up"] is False  # 2.5% < 9.9%
    assert by_sym["300750"]["is_limit_up"] is False  # 15.5% < 19.9% ChiNext heuristic


def test_sync_quotes_intraday_fade_calculation(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    by_sym = _records_by_symbol(result)
    assert by_sym["600519"]["intraday_fade_pct"] == 1.1


def test_sync_quotes_next_commands_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    assert "market-intel sync quotes" in result["next_commands"]


def test_sync_quotes_next_commands_written(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, trade_date="20260608")

    assert "market-intel dashboard --text" in result["next_commands"]


def test_sync_quotes_summary_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    assert result["summary"]["total"] == 5
    assert result["summary"]["limit_up"] == 1  # only 002837 in zt pool
    assert result["summary"]["stage_high"] == 1  # only 600519


def test_sync_quotes_marks_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, trade_date="20260608")

    manifest_path = tmp_path / "runtime" / "runtime_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["datasets"]["quotes"] == "runtime"
    assert manifest["source"] == "sync:akshare"


def test_sync_quotes_output_compatible_with_fixtures(tmp_path, monkeypatch):
    """Verify that sync output can be loaded by fixtures.load_quotes_file."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        sync_quotes(dry_run=False, trade_date="20260608")

    from market_intel.core.fixtures import load_quotes_file
    quotes = load_quotes_file(tmp_path / "runtime" / "quotes.json")
    assert len(quotes) == 5
    assert quotes[0].symbol == "600519"
    assert quotes[0].source == "sync:akshare"
    assert isinstance(quotes[0].is_limit_up, bool)
    assert isinstance(quotes[0].is_stage_high, bool)


def test_sync_quotes_no_trading_advice(tmp_path, monkeypatch):
    """Sync output must not contain trading advice keys."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608")

    forbidden = {"action", "recommendation", "target_price", "position_size", "must_buy", "must_sell"}
    result_str = json.dumps(result)
    for key in forbidden:
        assert '"%s"' % key not in result_str


def test_handle_sync_quotes_envelope(tmp_path, monkeypatch):
    """CLI handler wraps sync_quotes in a proper envelope with errors propagated."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_sync_quotes

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        payload = handle_sync_quotes(dry_run=True, trade_date="20260608")

    assert payload["ok"] is True
    assert payload["command"] == "sync.quotes"
    assert payload["data"]["record_count"] == 5
    assert payload["errors"] == []


def test_handle_sync_quotes_error_envelope(tmp_path, monkeypatch):
    """CLI handler must propagate errors to envelope and set ok=False."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_sync_quotes

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("fail")

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        payload = handle_sync_quotes(dry_run=True)

    assert payload["ok"] is False
    assert len(payload["errors"]) > 0
    assert payload["errors"][0]["code"] == "AKSHARE_SPOT_FAILED"


def test_render_sync_text(tmp_path, monkeypatch):
    """Text renderer produces valid output with key sections."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_sync_quotes
    from market_intel.core.text_report import render_sync_text

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        payload = handle_sync_quotes(dry_run=True, trade_date="20260608")

    text = render_sync_text(payload)
    assert "market-intel sync quotes" in text
    assert "akshare" in text
    assert "20260608" in text
    assert "dry_run True" in text
    assert "下一步" in text
    assert "边界" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_safe_float():
    assert _safe_float(1.5) == 1.5
    assert _safe_float("3.14") == 3.14
    assert _safe_float(None) is None
    assert _safe_float(None, 0.0) == 0.0
    assert _safe_float("abc", 0.0) == 0.0
    assert _safe_float(float("nan"), 0.0) == 0.0
    assert _safe_float(float("inf"), 0.0) == 0.0
    assert _safe_float(float("-inf"), 0.0) == 0.0


def test_is_st():
    assert _is_st({"名称": "ST海润"}) is True
    assert _is_st({"名称": "*ST信威"}) is True
    assert _is_st({"名称": "贵州茅台"}) is False


def test_limit_up_threshold():
    assert _limit_up_threshold("600519", False) == 9.9   # main board
    assert _limit_up_threshold("000001", False) == 9.9   # main board
    assert _limit_up_threshold("002837", True) == 4.9    # main board ST
    assert _limit_up_threshold("300750", False) == 19.9   # ChiNext
    assert _limit_up_threshold("300750", True) == 19.9    # ChiNext ST (same since 2020)
    assert _limit_up_threshold("688001", False) == 19.9   # STAR Market
    assert _limit_up_threshold("688001", True) == 19.9    # STAR Market ST
    assert _limit_up_threshold("830001", False) == 29.9   # BSE 8xxxxx
    assert _limit_up_threshold("430047", False) == 29.9   # BSE 43xxxx
