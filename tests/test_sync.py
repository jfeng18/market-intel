import json
from unittest.mock import MagicMock, patch

import pytest

from market_intel.core.sync import (
    provider_health,
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


def _tencent_payload(symbol: str, name: str, price: str = "10.00", prev: str = "9.80", pct: str = "2.04") -> str:
    fields = [""] * 40
    fields[0] = "51"
    fields[1] = name
    fields[2] = symbol
    fields[3] = price
    fields[4] = prev
    fields[32] = pct
    fields[33] = str(round(float(price) * 1.02, 2))
    fields[37] = "5.00"
    prefix = "sh" if symbol.startswith("6") else "bj" if symbol.startswith(("4", "8", "9")) else "sz"
    return 'v_%s%s="%s";' % (prefix, symbol, "~".join(fields))


class _TencentResp:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload.encode("gbk")


class _BytesResp:
    def __init__(self, payload, encoding="utf-8"):
        self.payload = payload
        self.encoding = encoding

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return self.payload.encode(self.encoding)


def _eastmoney_payload(rows, total=None):
    return json.dumps({"data": {"total": len(rows) if total is None else total, "diff": rows}}, ensure_ascii=False)


def _eastmoney_row(symbol="000001", name="平安银行", price=11.2, pct=1.2):
    return {
        "f12": symbol,
        "f14": name,
        "f2": price,
        "f3": pct,
        "f6": 980000000.0,
        "f10": 1.4,
        "f8": 0.8,
        "f7": 2.1,
        "f15": price + 0.1,
    }


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
    assert {q["trade_date"] for q in data["quotes"]} == {"2026-06-08"}
    assert result["trade_date"] == "2026-06-08"


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


def test_sync_quotes_accepts_iso_trade_date_for_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    mock_ak = _setup_mock_ak()

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=False, trade_date="2026-06-08")

    assert not result["errors"]
    assert result["trade_date"] == "2026-06-08"
    mock_ak.stock_zt_pool_em.assert_called_with(date="20260608")
    data = json.loads((tmp_path / "runtime" / "quotes.json").read_text(encoding="utf-8"))
    assert {q["trade_date"] for q in data["quotes"]} == {"2026-06-08"}


def test_sync_quotes_rejects_invalid_trade_date(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=False, trade_date="20260632")

    assert result["errors"]
    assert result["errors"][0]["code"] == "SYNC_TRADE_DATE_INVALID"
    assert result["written"] is False
    assert not (tmp_path / "runtime" / "quotes.json").exists()


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


def test_sync_quotes_eastmoney_dns_failure_has_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception(
        "HTTPSConnectionPool(host='82.push2.eastmoney.com', port=443): "
        "Max retries exceeded with url: /api/qt/clist/get "
        "(Caused by NameResolutionError(\"HTTPSConnection(host='82.push2.eastmoney.com', port=443): "
        "Failed to resolve '82.push2.eastmoney.com' ([Errno 8] nodename nor servname provided, or not known)\"))"
    )

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=True)

    assert result["errors"]
    assert result["errors"][0]["code"] == "AKSHARE_EASTMONEY_DNS_FAILED"
    assert result["errors"][0]["detail"]["host"] == "82.push2.eastmoney.com"
    assert result["errors"][0]["detail"]["reason"] == "dns_resolution_failed"
    assert result["record_count"] == 0
    assert result["source"] == "akshare"
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
    assert manifest["quotes"]["provider"] == "akshare"
    assert manifest["quotes"]["requested_provider"] == "akshare"
    assert manifest["quotes"]["fallback_used"] is False
    assert manifest["quotes"]["provider_failed_using_cache"] is False


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
    assert "2026-06-08" in text
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
    assert _limit_up_threshold("920118", False) == 29.9   # BSE 920xxx


def test_sync_quotes_progress_fn_called(tmp_path, monkeypatch):
    """progress_fn receives expected messages during sync."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    messages = []

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        sync_quotes(dry_run=True, trade_date="20260608", progress_fn=messages.append)

    assert any("东方财富" in m for m in messages)
    assert any("行情记录" in m for m in messages)
    assert any("涨停板" in m for m in messages)
    assert any("强势股" in m for m in messages)


def test_sync_quotes_progress_fn_none_is_silent(tmp_path, monkeypatch):
    """progress_fn=None (default) does not raise."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, trade_date="20260608", progress_fn=None)

    assert not result["errors"]
    assert result["record_count"] == 5


def test_sync_quotes_weekend_warning(tmp_path, monkeypatch):
    """Weekend trade_date triggers a non-trading-day progress message."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    messages = []

    # 2026-06-13 is a Saturday
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        sync_quotes(dry_run=True, trade_date="20260613", progress_fn=messages.append)

    assert any("非交易日" in m and "周末" in m for m in messages)


def test_sync_quotes_weekday_no_weekend_warning(tmp_path, monkeypatch):
    """Weekday trade_date does NOT emit the weekend warning."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    messages = []

    # 2026-06-08 is a Monday
    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        sync_quotes(dry_run=True, trade_date="20260608", progress_fn=messages.append)

    assert not any("非交易日" in m for m in messages)


def test_sync_quotes_tencent_requires_symbols(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = sync_quotes(dry_run=True, provider="tencent", trade_date="20260608")

    assert result["errors"]
    assert result["errors"][0]["code"] == "TENCENT_SYMBOLS_REQUIRED"
    assert result["source"] == "tencent"


def test_sync_quotes_tencent_selected_symbols(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = (
        'v_sz002261="51~拓维信息~002261~29.81~28.92~29.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~3.08~30.59~28.90~0~11.92~0~0~0";'
    )

    def fake_urlopen(url, timeout=10, context=None):
        assert "sz002261" in url
        assert context is not None
        return _TencentResp(payload)

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)

    result = sync_quotes(
        dry_run=True,
        provider="tencent",
        symbols=["002261"],
        trade_date="20260608",
    )

    assert not result["errors"]
    assert result["source"] == "tencent"
    assert result["record_count"] == 1
    assert result["preview"][0]["symbol"] == "002261"
    assert result["preview"][0]["source"] == "sync:tencent"
    assert result["preview"][0]["intraday_fade_pct"] == 2.55


def test_sync_quotes_auto_uses_akshare_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    with patch.dict("sys.modules", {"akshare": _setup_mock_ak()}):
        result = sync_quotes(dry_run=True, provider="auto", trade_date="20260608")

    assert result["errors"] == []
    assert result["source"] == "akshare"
    assert result["requested_provider"] == "auto"
    assert result["fallback_used"] is False
    assert result["record_count"] == 5


def test_handle_sync_quotes_tencent_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = (
        'v_sz000967="51~盈峰环境~000967~9.85~9.84~9.90~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0.10~10.23~9.80~0~5.71~0~0~0";'
    )

    monkeypatch.setattr("market_intel.core.sync.urlopen", lambda *_args, **_kwargs: _TencentResp(payload))

    from market_intel.cli import handle_sync_quotes

    result = handle_sync_quotes(
        dry_run=True,
        symbols=["000967"],
        trade_date="20260608",
        provider="tencent",
    )

    assert result["ok"] is True
    assert result["meta"]["source"] == "sync:tencent"
    assert result["data"]["source"] == "tencent"


def test_sync_quotes_auto_falls_back_to_tencent_for_symbols(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("eastmoney down")
    monkeypatch.setattr(
        "market_intel.core.sync.urlopen",
        lambda *_args, **_kwargs: _TencentResp(_tencent_payload("000967", "盈峰环境", price="9.85")),
    )

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(
            dry_run=True,
            provider="auto",
            symbols=["000967"],
            trade_date="20260608",
        )

    assert result["errors"] == []
    assert result["source"] == "tencent"
    assert result["requested_provider"] == "auto"
    assert result["fallback_used"] is True
    assert any(w["code"] == "SYNC_AKSHARE_FALLBACK_TENCENT" for w in result["warnings"])
    assert result["preview"][0]["symbol"] == "000967"


def test_sync_quotes_auto_failure_envelope_includes_fallback_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("eastmoney down")

    def fail_urlopen(*_args, **_kwargs):
        raise TimeoutError("tencent timeout")

    monkeypatch.setattr("market_intel.core.sync.urlopen", fail_urlopen)

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(
            dry_run=True,
            provider="auto",
            symbols=["000967"],
            trade_date="20260608",
        )

    assert result["errors"]
    assert result["source"] == "auto"
    assert result["requested_provider"] == "auto"
    assert {error["code"] for error in result["errors"]} == {
        "AKSHARE_SPOT_FAILED",
        "EASTMONEY_DIRECT_EASTMONEY_TIMEOUT",
        "TENCENT_QUOTE_FAILED",
    }
    assert result["next_commands"] == []


def test_sync_quotes_tencent_uses_runtime_holdings_subset(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))
    (runtime_dir / "holdings.json").write_text(
        json.dumps(
            {
                "holdings": [
                    {"symbol": "000967", "name": "盈峰环境"},
                    {"symbol": "600519", "name": "贵州茅台"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payload = _tencent_payload("000967", "盈峰环境", price="9.85") + _tencent_payload("600519", "贵州茅台", price="1800.00")
    seen_urls = []

    def fake_urlopen(url, **_kwargs):
        seen_urls.append(url)
        return _TencentResp(payload)

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)

    result = sync_quotes(
        dry_run=True,
        provider="tencent",
        trade_date="20260608",
    )

    assert result["errors"] == []
    assert result["record_count"] == 2
    assert "sz000967" in seen_urls[0]
    assert "sh600519" in seen_urls[0]


def test_sync_quotes_tencent_uses_runtime_quote_watchlist_subset(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))
    (runtime_dir / "quotes.json").write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "002261",
                        "name": "拓维信息",
                        "trade_date": "2026-06-07",
                        "last_price": 28.0,
                        "change_pct": 0.0,
                        "amount": 0.0,
                        "amount_ratio": 1.0,
                        "turnover_rate": 0.0,
                        "amplitude_pct": 0.0,
                        "is_limit_up": False,
                        "is_stage_high": False,
                        "intraday_fade_pct": 0.0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen_urls = []

    def fake_urlopen(url, **_kwargs):
        seen_urls.append(url)
        return _TencentResp(_tencent_payload("002261", "拓维信息", price="29.81"))

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)

    result = sync_quotes(dry_run=True, provider="tencent", trade_date="20260608")

    assert result["errors"] == []
    assert result["record_count"] == 1
    assert result["preview"][0]["symbol"] == "002261"
    assert "sz002261" in seen_urls[0]


def test_sync_quotes_tencent_refuses_large_runtime_universe(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))
    rows = ["symbol,name,industry"]
    for index in range(121):
        rows.append("300%03d,样例%s,电子" % (index, index))
    (runtime_dir / "a_share_universe.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = sync_quotes(dry_run=True, provider="tencent", trade_date="20260608")

    assert result["errors"]
    assert result["errors"][0]["code"] == "TENCENT_SYMBOLS_REQUIRED"
    assert any(w["code"] == "TENCENT_RUNTIME_UNIVERSE_TOO_LARGE" for w in result["warnings"])


def test_sync_quotes_eastmoney_direct_fetches_paginated_full_a(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    seen_urls = []

    def fake_urlopen(request, **_kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        seen_urls.append(url)
        if "pn=1" in url:
            return _BytesResp(_eastmoney_payload([_eastmoney_row("000001", "平安银行")], total=2))
        if "pn=2" in url:
            return _BytesResp(_eastmoney_payload([_eastmoney_row("600519", "贵州茅台", price=1800.0, pct=2.5)], total=2))
        raise AssertionError(url)

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)
    monkeypatch.setattr("market_intel.core.sync.EASTMONEY_DIRECT_PAGE_SIZE", 1)
    monkeypatch.setattr("market_intel.core.sync.EASTMONEY_DIRECT_SLEEP_SECONDS", 0)

    result = sync_quotes(dry_run=True, provider="eastmoney", trade_date="20260608")

    assert result["errors"] == []
    assert result["source"] == "eastmoney"
    assert result["coverage"]["coverage"] == "full_a"
    assert result["coverage"]["requested"] == 2
    assert result["coverage"]["success"] == 2
    assert result["record_count"] == 2
    assert any("fields=f12" in url for url in seen_urls)


def test_sync_quotes_auto_falls_back_to_eastmoney_full_a(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    mock_ak = MagicMock()
    mock_ak.stock_zh_a_spot_em.side_effect = Exception("eastmoney down")
    monkeypatch.setattr(
        "market_intel.core.sync.urlopen",
        lambda *_args, **_kwargs: _BytesResp(_eastmoney_payload([_eastmoney_row("000001", "平安银行")], total=1)),
    )

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = sync_quotes(dry_run=True, provider="auto", trade_date="20260608")

    assert result["errors"] == []
    assert result["source"] == "eastmoney"
    assert result["requested_provider"] == "auto"
    assert result["fallback_used"] is True
    assert any(w["code"] == "SYNC_AKSHARE_FALLBACK_EASTMONEY" for w in result["warnings"])


def test_sync_quotes_tencent_batch_uses_runtime_universe_with_coverage(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))
    (runtime_dir / "a_share_universe.csv").write_text(
        "symbol,name,industry\n000001,平安银行,银行\n600519,贵州茅台,食品饮料\n",
        encoding="utf-8",
    )
    seen_urls = []

    def fake_urlopen(url, **_kwargs):
        seen_urls.append(url)
        return _TencentResp(_tencent_payload("000001", "平安银行") + _tencent_payload("600519", "贵州茅台"))

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)
    monkeypatch.setattr("market_intel.core.sync.TENCENT_BATCH_SLEEP_SECONDS", 0)

    result = sync_quotes(dry_run=True, provider="tencent-batch", trade_date="20260608")

    assert result["errors"] == []
    assert result["source"] == "tencent-batch"
    assert result["coverage"] == {
        "source": "tencent-batch",
        "coverage": "universe_based",
        "universe_count": 2,
        "requested": 2,
        "success": 2,
        "failed": 0,
        "coverage_pct": 100.0,
        "status": "ok",
        "failed_symbols": [],
    }
    assert "sz000001" in seen_urls[0]
    assert "sh600519" in seen_urls[0]


def test_sync_quotes_tencent_batch_marks_degraded_when_coverage_low(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(runtime_dir))
    (runtime_dir / "a_share_universe.csv").write_text(
        "symbol,name,industry\n000001,平安银行,银行\n600519,贵州茅台,食品饮料\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("market_intel.core.sync.urlopen", lambda *_args, **_kwargs: _TencentResp(_tencent_payload("000001", "平安银行")))

    result = sync_quotes(dry_run=True, provider="tencent-batch", trade_date="20260608")

    assert result["errors"] == []
    assert result["coverage"]["status"] == "degraded"
    assert result["coverage"]["coverage_pct"] == 50.0
    assert result["coverage"]["failed_symbols"] == ["600519"]
    assert any(w["code"] == "TENCENT_BATCH_COVERAGE_DEGRADED" for w in result["warnings"])


def test_sync_quotes_tencent_batch_refuses_too_many_symbols(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    symbols = ["300%03d" % index for index in range(501)]

    result = sync_quotes(dry_run=True, provider="tencent-batch", symbols=symbols, trade_date="20260608")

    assert result["errors"]
    assert result["errors"][0]["code"] == "TENCENT_BATCH_SYMBOL_LIMIT_EXCEEDED"
    assert result["coverage"]["coverage"] == "universe_based"
    assert result["coverage"]["requested"] == 501


def test_provider_health_reports_recommendation_without_full_market(monkeypatch):
    mock_ak = MagicMock()
    mock_ak.stock_bid_ask_em.return_value = [object()]

    calls = []

    def fake_urlopen(request, **_kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        if "qt.gtimg.cn" in url:
            return _TencentResp(_tencent_payload("000001", "平安银行"))
        return _BytesResp(_eastmoney_payload([_eastmoney_row("000001", "平安银行")], total=5000))

    monkeypatch.setattr("market_intel.core.sync.urlopen", fake_urlopen)
    with patch.dict("sys.modules", {"akshare": mock_ak}):
        result = provider_health(symbol="000001")

    assert result["full_market_fetch"] is False
    assert result["recommended_provider"] == "eastmoney"
    assert {item["provider"]: item["ready"] for item in result["providers"]} == {
        "akshare": True,
        "eastmoney": True,
        "tencent": True,
    }
    mock_ak.stock_bid_ask_em.assert_called_once_with(symbol="000001")
    mock_ak.stock_zh_a_spot_em.assert_not_called()
    assert any("pz=1" in url for url in calls)
