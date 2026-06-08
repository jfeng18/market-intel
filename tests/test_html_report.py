import json

from market_intel.core.html_report import render_review_html, _score_color, _priority_badge_class, _esc


def _mock_review_payload():
    return {
        "ok": True,
        "command": "review",
        "data": {
            "window": "day",
            "changes": {
                "available": True,
                "window": "day",
                "window_label": "日级",
                "base_trade_date": "2026-06-07",
                "summary": "对比 2026-06-07（日级）；风险 +1/-1；观察 +2/-0/~1。",
                "risk_flags": {
                    "added": ["持仓集中度偏高"],
                    "removed": ["量比异常"],
                    "unchanged": [],
                },
                "watchlist": {
                    "added": [{"symbol": "002837", "name": "英维克"}],
                    "removed": [],
                    "changed": [{"symbol": "600519", "name": "贵州茅台"}],
                },
                "portfolio_review": {"added": [], "removed": [], "changed": []},
                "hotspots": {
                    "added": [{"key": "算力/AI 服务器"}],
                    "removed": [],
                },
            },
            "sync": {
                "ok": True,
                "record_count": 5200,
                "trade_date": "20260608",
                "summary": {"total": 5200, "limit_up": 48, "stage_high": 120},
            },
            "daily_summary": "市场震荡偏强，算力链活跃，光模块板块领涨。",
            "risk_flags": ["持仓集中度偏高", "追高风险"],
            "brief": {
                "top_hotspots": [
                    {
                        "layer": "算力",
                        "sub_sector": "AI 服务器",
                        "score": 78.5,
                        "active_member_count": 8,
                        "member_count": 12,
                        "leaders": [
                            {"symbol": "002837", "name": "英维克", "change_pct": 10.02},
                            {"symbol": "002475", "name": "立讯精密", "change_pct": 5.3},
                        ],
                        "signals": ["放量突破", "龙头效应"],
                        "risks": [],
                    },
                    {
                        "layer": "运力",
                        "sub_sector": "光模块",
                        "score": 65.2,
                        "active_member_count": 5,
                        "member_count": 9,
                        "leaders": [{"symbol": "300502", "name": "新易盛", "change_pct": 7.8}],
                        "signals": ["板块轮动"],
                        "risks": ["高位震荡"],
                    },
                ],
            },
            "watchlist": {
                "count": 3,
                "items": [
                    {
                        "symbol": "002837",
                        "name": "英维克",
                        "layer": "算力",
                        "sub_sector": "AI 服务器",
                        "change_pct": 10.02,
                        "amount_ratio": 3.5,
                        "hotspot_score": 78.5,
                        "is_holding": False,
                        "focus": "涨停突破关注",
                    },
                    {
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "layer": "消费",
                        "sub_sector": "白酒",
                        "change_pct": 2.5,
                        "amount_ratio": 1.2,
                        "hotspot_score": 45.0,
                        "is_holding": True,
                        "focus": "持仓标的跟踪",
                    },
                ],
            },
            "portfolio_review": {
                "review_count": 2,
                "summary": "2 个持仓标的需要复核。",
                "items": [
                    {
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "priority": "high_review",
                        "quote": {"change_pct": 2.5, "amount_ratio": 1.2},
                        "risk_flags": ["追高风险"],
                        "review_points": ["检查阶段高点", "确认支撑位"],
                    },
                ],
            },
            "validation": {"ok": True, "summary": {}, "warnings": [], "errors": []},
            "journal_saved": True,
            "journal_entry": {"id": "2026-06-08_review", "trade_date": "2026-06-08"},
            "next_commands": ["market-intel review --window week --text"],
            "warnings": [],
            "errors": [],
        },
        "meta": {"generated_at": "2026-06-08T16:30:00+08:00"},
        "errors": [],
        "warnings": [],
    }


def test_html_report_is_valid_html():
    html = render_review_html(_mock_review_payload())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>" in html
    assert "utf-8" in html


def test_html_report_contains_key_sections():
    html = render_review_html(_mock_review_payload())
    assert "变化追踪" in html
    assert "数据同步" in html
    assert "今日摘要" in html
    assert "热点板块" in html
    assert "观察清单" in html
    assert "持仓复核" in html


def test_html_report_contains_change_badges():
    html = render_review_html(_mock_review_payload())
    assert "持仓集中度偏高" in html
    assert "量比异常" in html
    assert "英维克" in html
    assert "badge-red" in html
    assert "badge-green" in html


def test_html_report_contains_hotspot_data():
    html = render_review_html(_mock_review_payload())
    assert "AI 服务器" in html
    assert "78.5" in html
    assert "光模块" in html
    assert "放量突破" in html


def test_html_report_contains_watchlist_data():
    html = render_review_html(_mock_review_payload())
    assert "002837" in html
    assert "10.02" in html
    assert "贵州茅台" in html


def test_html_report_contains_portfolio_data():
    html = render_review_html(_mock_review_payload())
    assert "high_review" in html
    assert "追高风险" in html


def test_html_report_no_trading_advice():
    html = render_review_html(_mock_review_payload())
    assert "不产生交易指令" in html
    assert "buy" not in html.lower().replace("立讯", "").replace("sub", "")


def test_html_report_self_contained():
    """HTML should have embedded CSS, no external dependencies."""
    html = render_review_html(_mock_review_payload())
    assert "<style>" in html
    assert "link rel=" not in html
    assert "<script src=" not in html


def test_html_report_escapes_user_data():
    payload = _mock_review_payload()
    payload["data"]["daily_summary"] = '<script>alert("xss")</script>'
    html = render_review_html(payload)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_html_report_handles_empty_data():
    payload = {"ok": False, "data": {}, "meta": {}, "errors": [], "warnings": []}
    html = render_review_html(payload)
    assert "<!DOCTYPE html>" in html
    assert "无" in html


def test_html_report_handles_no_changes():
    payload = _mock_review_payload()
    payload["data"]["changes"] = {
        "available": False,
        "summary": "无历史数据可对比。",
    }
    html = render_review_html(payload)
    assert "无历史数据可对比" in html


def test_html_report_shows_unsaved_journal_reason():
    payload = _mock_review_payload()
    payload["data"]["journal_saved"] = False
    payload["data"]["journal_entry"] = None
    payload["data"]["journal_status"] = {
        "code": "sample_runtime",
        "reason": "runtime 仍包含样例数据，未写入 journal。",
    }
    html = render_review_html(payload)
    assert "日报留档" in html
    assert "样例数据" in html
    assert "未保存" in html


def test_score_color():
    assert "red" in _score_color(75)
    assert "orange" in _score_color(55)
    assert "yellow" in _score_color(35)
    assert "dim" in _score_color(10)


def test_priority_badge_class():
    assert "red" in _priority_badge_class("high_review")
    assert "yellow" in _priority_badge_class("medium_review")
    assert "dim" in _priority_badge_class("normal")


def test_esc():
    assert _esc("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"
    assert _esc('"quoted"') == "&quot;quoted&quot;"


def test_html_cli_flag(tmp_path, monkeypatch):
    """CLI --html flag writes file to disk."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_review
    from market_intel.core.html_report import render_review_html

    payload = handle_review(no_sync=True, no_save=True)
    html_content = render_review_html(payload)

    output_path = tmp_path / "test_review.html"
    output_path.write_text(html_content, encoding="utf-8")

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "复盘报告" in content
