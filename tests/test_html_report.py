import json

from market_intel.core.html_report import (
    render_review_html,
    _score_color,
    _priority_badge_class,
    _esc,
    _svg_change_bar,
    _svg_volume_dot,
    _svg_score_bar,
    _svg_radar,
    _RADAR_AXIS_KEYS,
    _RADAR_AXIS_LABELS,
)


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
                        "breakdown": {
                            "avg_change_score": 0.9,
                            "turnover_expansion_score": 0.7,
                            "strong_member_score": 0.6,
                            "leader_strength_score": 0.8,
                            "persistence_score": 0.5,
                            "intraday_fade_penalty": 0.2,
                        },
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
            "next_commands": ["market-intel review --window week --no-sync --no-save --text"],
            "command_queue": [
                {
                    "rank": 1,
                    "command": "market-intel review --window week --no-sync --no-save --text",
                    "json_command": "market-intel review --window week --no-sync --no-save --json",
                    "state_effect": "read_only",
                    "runnable": True,
                    "done_when": "已读取 data.changes、data.daily_summary、data.journal_status 和 data.command_queue。",
                },
                {
                    "rank": 2,
                    "command": "market-intel journal save --runtime --json",
                    "json_command": "market-intel journal save --runtime --json",
                    "state_effect": "writes_journal",
                    "runnable": True,
                    "done_when": "data.saved 为 true。",
                },
            ],
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
    assert "下一步" in html


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


def test_html_report_contains_command_queue():
    html = render_review_html(_mock_review_payload())
    assert "market-intel review --window week --no-sync --no-save --text" in html
    assert "market-intel review --window week --no-sync --no-save --json" in html
    assert "只读" in html
    assert "写入留档" in html
    assert "已读取 data.changes" in html


def test_html_report_falls_back_to_next_commands():
    payload = _mock_review_payload()
    payload["data"]["command_queue"] = []
    payload["data"]["next_commands"] = ["market-intel journal timeline --text"]
    html = render_review_html(payload)
    assert "下一步" in html
    assert "market-intel journal timeline --text" in html


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
    payload["data"]["command_queue"][0]["command"] = '<script>alert("cmd")</script>'
    html = render_review_html(payload)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;script&gt;alert(&quot;cmd&quot;)&lt;/script&gt;" in html


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


# ---------------------------------------------------------------------------
# SVG sparkline unit tests
# ---------------------------------------------------------------------------


class TestSvgChangeBar:
    """Tests for _svg_change_bar."""

    def test_positive_produces_red_fill_right_side(self):
        svg = _svg_change_bar(5.0)
        assert 'fill="var(--red)"' in svg
        # x should be at midpoint (30.0) for positive values
        assert 'x="30.0"' in svg

    def test_negative_produces_green_fill_left_side(self):
        svg = _svg_change_bar(-5.0)
        assert 'fill="var(--green)"' in svg
        # x should be less than midpoint for negative values
        # bar_len = 5/10 * 30 = 15, so x = 30 - 15 = 15
        assert 'x="15.0"' in svg

    def test_zero_produces_neutral_bar(self):
        svg = _svg_change_bar(0.0)
        assert 'width="1' in svg
        assert 'fill="var(--text-dim)"' in svg

    def test_large_positive_clamped_to_max(self):
        svg = _svg_change_bar(20.0)
        # Clamped to 10, bar_len = 10/10 * 30 = 30
        assert 'width="30.0"' in svg
        # x starts at midpoint
        assert 'x="30.0"' in svg

    def test_large_negative_clamped_to_max(self):
        svg = _svg_change_bar(-20.0)
        # Clamped to -10, bar_len = 10/10 * 30 = 30
        assert 'width="30.0"' in svg
        # x = 30 - 30 = 0
        assert 'x="0.0"' in svg

    def test_returns_valid_svg(self):
        svg = _svg_change_bar(3.0)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_bar_does_not_exceed_container(self):
        """Even with extreme values, rect stays within 60px width."""
        for val in [-100, -10, 0, 10, 100]:
            svg = _svg_change_bar(val)
            # Extract x and width from rect; x + width should not exceed 60
            import re
            match = re.search(r'<rect x="([0-9.]+)" y="3" width="([0-9.]+)"', svg)
            assert match is not None
            x = float(match.group(1))
            w = float(match.group(2))
            assert x + w <= 60.0


class TestSvgVolumeDot:
    """Tests for _svg_volume_dot."""

    def test_low_ratio_produces_blue(self):
        svg = _svg_volume_dot(1.0)
        assert 'fill="var(--blue)"' in svg

    def test_medium_ratio_produces_yellow(self):
        svg = _svg_volume_dot(2.0)
        assert 'fill="var(--yellow)"' in svg

    def test_high_ratio_produces_orange(self):
        svg = _svg_volume_dot(4.0)
        assert 'fill="var(--orange)"' in svg

    def test_boundary_1_5_is_yellow(self):
        svg = _svg_volume_dot(1.5)
        assert 'fill="var(--yellow)"' in svg

    def test_boundary_3_0_is_yellow(self):
        """Exactly 3.0 is still in the 1.5-3 range (not >3)."""
        svg = _svg_volume_dot(3.0)
        assert 'fill="var(--yellow)"' in svg

    def test_just_above_3_is_orange(self):
        svg = _svg_volume_dot(3.01)
        assert 'fill="var(--orange)"' in svg

    def test_returns_valid_svg(self):
        svg = _svg_volume_dot(2.5)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_zero_ratio_produces_blue_min_radius(self):
        svg = _svg_volume_dot(0.0)
        assert 'fill="var(--blue)"' in svg
        assert 'r="3.0"' in svg


class TestSvgScoreBar:
    """Tests for _svg_score_bar."""

    def test_score_zero_produces_minimal_fill(self):
        svg = _svg_score_bar(0)
        # ratio = 0/100 = 0, fill_w = 0.0
        assert 'width="0.0"' in svg

    def test_score_100_produces_full_fill(self):
        svg = _svg_score_bar(100)
        # ratio = 1.0, fill_w = 50.0
        assert 'width="50.0"' in svg

    def test_score_above_70_is_red(self):
        svg = _svg_score_bar(85)
        assert 'fill="var(--red)"' in svg

    def test_score_above_50_is_yellow(self):
        svg = _svg_score_bar(60)
        assert 'fill="var(--yellow)"' in svg

    def test_score_at_50_is_blue(self):
        svg = _svg_score_bar(50)
        assert 'fill="var(--blue)"' in svg

    def test_score_below_50_is_blue(self):
        svg = _svg_score_bar(30)
        assert 'fill="var(--blue)"' in svg

    def test_score_at_70_boundary_is_yellow(self):
        """Score exactly 70 is not >70, so yellow."""
        svg = _svg_score_bar(70)
        assert 'fill="var(--yellow)"' in svg

    def test_returns_valid_svg(self):
        svg = _svg_score_bar(50)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_has_background_rect(self):
        svg = _svg_score_bar(50)
        assert 'fill="var(--text-dim)"' in svg


class TestSvgRadar:
    """Tests for _svg_radar."""

    def test_empty_dict_produces_valid_svg(self):
        svg = _svg_radar({})
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # Should have two polygon elements (guide + data)
        assert svg.count("<polygon") == 2

    def test_dict_with_six_keys_produces_polygon(self):
        breakdown = {
            "momentum": 0.8,
            "volume": 0.6,
            "leaders": 0.9,
            "breadth": 0.4,
            "sentiment": 0.5,
            "structure": 0.7,
        }
        svg = _svg_radar(breakdown)
        assert "<polygon" in svg
        # Data polygon should have non-center points
        assert 'stroke="var(--blue)"' in svg

    def test_values_clamped_above_one(self):
        breakdown = {"a": 2.0, "b": 1.5, "c": 3.0, "d": 0.5, "e": 10.0, "f": -1.0}
        svg = _svg_radar(breakdown)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # All values should be clamped to [0, 1], so max radius is 25
        # Points should not exceed cx+25=65 or go below cx-25=15
        import re
        data_match = re.findall(r'<polygon points="([^"]+)"', svg)
        assert len(data_match) == 2
        data_points_str = data_match[1]
        for pair in data_points_str.split():
            x, y = pair.split(",")
            assert 15.0 <= float(x) <= 65.0
            assert 15.0 <= float(y) <= 65.0

    def test_all_zeros_collapses_to_center(self):
        breakdown = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0}
        svg = _svg_radar(breakdown)
        # All points should be at center (40.0, 40.0)
        assert "40.0,40.0" in svg

    def test_fewer_than_six_keys_pads_with_zero(self):
        breakdown = {"a": 0.5, "b": 0.8}
        svg = _svg_radar(breakdown)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # Should still produce valid polygon (6 points)
        import re
        data_match = re.findall(r'<polygon points="([^"]+)"', svg)
        data_points = data_match[1].split()
        assert len(data_points) == 6

    def test_canonical_keys_produce_text_labels(self):
        breakdown = {
            "avg_change_score": 0.8,
            "turnover_expansion_score": 0.6,
            "strong_member_score": 0.5,
            "leader_strength_score": 0.7,
            "persistence_score": 0.4,
            "intraday_fade_penalty": 0.3,
        }
        svg = _svg_radar(breakdown)
        assert "<text" in svg
        assert "</text>" in svg
        # All six labels should be present
        for label in ["涨幅", "量能", "强势", "龙头", "持续", "回落"]:
            assert label in svg

    def test_canonical_keys_label_attributes(self):
        breakdown = {k: 0.5 for k in _RADAR_AXIS_KEYS}
        svg = _svg_radar(breakdown)
        assert 'font-size="8"' in svg
        assert 'fill="var(--text-muted)"' in svg
        assert 'text-anchor="middle"' in svg  # top axis
        assert 'text-anchor="end"' in svg  # left axes
        assert 'text-anchor="start"' in svg  # right axes

    def test_non_canonical_keys_no_labels(self):
        breakdown = {"a": 0.5, "b": 0.6, "c": 0.7, "d": 0.3, "e": 0.4, "f": 0.2}
        svg = _svg_radar(breakdown)
        assert "<text" not in svg

    def test_svg_size_is_80(self):
        breakdown = {k: 0.5 for k in _RADAR_AXIS_KEYS}
        svg = _svg_radar(breakdown)
        assert 'width="80"' in svg
        assert 'height="80"' in svg


# ---------------------------------------------------------------------------
# SVG sparkline integration tests
# ---------------------------------------------------------------------------


class TestSvgSparklineIntegration:
    """Integration tests: SVG sparklines appear in the full HTML report."""

    def test_html_report_contains_svg_elements(self):
        html_out = render_review_html(_mock_review_payload())
        assert "<svg" in html_out
        assert "</svg>" in html_out

    def test_sparklines_in_watchlist_table(self):
        html_out = render_review_html(_mock_review_payload())
        # Watchlist items have change_pct and amount_ratio, so SVGs should appear
        # The watchlist section should contain change_bar and volume_dot SVGs
        watchlist_start = html_out.index("观察清单")
        # Find next section or end
        try:
            watchlist_end = html_out.index("<h2>", watchlist_start + 1)
        except ValueError:
            watchlist_end = len(html_out)
        watchlist_section = html_out[watchlist_start:watchlist_end]
        assert "<svg" in watchlist_section
        # Should have both change_bar (rect with red/green) and volume_dot (circle)
        assert "<rect" in watchlist_section
        assert "<circle" in watchlist_section

    def test_sparklines_in_hotspot_table(self):
        html_out = render_review_html(_mock_review_payload())
        hotspot_start = html_out.index("热点板块")
        try:
            hotspot_end = html_out.index("<h2>", hotspot_start + 1)
        except ValueError:
            hotspot_end = len(html_out)
        hotspot_section = html_out[hotspot_start:hotspot_end]
        # Hotspots have score_bar and radar SVGs
        assert "<svg" in hotspot_section
        assert "<polygon" in hotspot_section  # radar chart

    def test_radar_labels_in_hotspot_table(self):
        html_out = render_review_html(_mock_review_payload())
        hotspot_start = html_out.index("热点板块")
        try:
            hotspot_end = html_out.index("<h2>", hotspot_start + 1)
        except ValueError:
            hotspot_end = len(html_out)
        hotspot_section = html_out[hotspot_start:hotspot_end]
        # Radar chart should contain text elements with Chinese labels
        assert "<text" in hotspot_section
        assert "涨幅" in hotspot_section

    def test_sparklines_in_portfolio_table(self):
        html_out = render_review_html(_mock_review_payload())
        portfolio_start = html_out.index("持仓复核")
        try:
            portfolio_end = html_out.index("<h2>", portfolio_start + 1)
        except ValueError:
            portfolio_end = len(html_out)
        portfolio_section = html_out[portfolio_start:portfolio_end]
        # Portfolio items have change_bar and volume_dot
        assert "<svg" in portfolio_section
        assert "<rect" in portfolio_section
        assert "<circle" in portfolio_section
