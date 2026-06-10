"""Generate a self-contained HTML review report."""

import html
import json
import math
from typing import Any, Dict, List, Optional

from .text_report import LABELS


def render_review_html(payload: Dict[str, Any]) -> str:
    """Render a complete self-contained HTML report from a review envelope."""
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}

    sections = []
    sections.append(_render_header(data, meta))
    sections.append(_render_changes(data))
    sections.append(_render_sync_status(data))
    sections.append(_render_summary(data))
    sections.append(_render_risk_flags(data))
    sections.append(_render_hotspots(data))
    sections.append(_render_watchlist(data))
    sections.append(_render_portfolio(data))
    sections.append(_render_validation(data))
    sections.append(_render_command_queue(data))
    sections.append(_render_footer(data))

    body = "\n".join(sections)
    return _wrap_html(body, data)


def _wrap_html(body: str, data: Dict[str, Any]) -> str:
    window_label = ""
    changes = data.get("changes", {}) if isinstance(data.get("changes"), dict) else {}
    if changes.get("window_label"):
        window_label = " (%s)" % _esc(changes["window_label"])

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>market-intel 复盘报告%(window)s</title>
<style>
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e; --text-dim: #484f58;
  --red: #f85149; --green: #3fb950; --yellow: #d29922;
  --blue: #58a6ff; --purple: #bc8cff; --orange: #d18616;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.6;
       max-width: 960px; margin: 0 auto; padding: 20px; }
h1 { font-size: 1.4em; margin-bottom: 4px; }
h2 { font-size: 1.1em; color: var(--blue); margin: 24px 0 8px;
     padding-bottom: 4px; border-bottom: 1px solid var(--border); }
.subtitle { color: var(--text-muted); font-size: 0.85em; }
.card { background: var(--surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 12px 16px; margin: 8px 0; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 0.78em; font-weight: 500; margin: 2px; }
.badge-red { background: rgba(248,81,73,0.15); color: var(--red); }
.badge-green { background: rgba(63,185,80,0.15); color: var(--green); }
.badge-yellow { background: rgba(210,153,34,0.15); color: var(--yellow); }
.badge-blue { background: rgba(88,166,255,0.15); color: var(--blue); }
.badge-purple { background: rgba(188,140,255,0.15); color: var(--purple); }
.badge-dim { background: rgba(72,79,88,0.2); color: var(--text-muted); }
table { width: 100%%; border-collapse: collapse; font-size: 0.88em; }
th { text-align: left; color: var(--text-muted); font-weight: 500;
     padding: 6px 8px; border-bottom: 1px solid var(--border); }
td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
tr:hover { background: rgba(88,166,255,0.04); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.pos { color: var(--red); }
.neg { color: var(--green); }
.bar { display: inline-block; height: 14px; border-radius: 2px;
       vertical-align: middle; min-width: 2px; }
.bar-red { background: var(--red); }
.bar-green { background: var(--green); }
.bar-yellow { background: var(--yellow); }
.bar-blue { background: var(--blue); }
.heat { display: inline-block; width: 8px; height: 8px;
        border-radius: 50%%; margin-right: 4px; vertical-align: middle; }
.empty { color: var(--text-dim); font-style: italic; }
.changes-summary { font-size: 0.95em; margin: 6px 0; }
.guardrails { color: var(--text-dim); font-size: 0.8em;
              margin-top: 24px; padding-top: 8px;
              border-top: 1px solid var(--border); }
@media (prefers-color-scheme: light) {
  :root {
    --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
    --text: #1f2328; --text-muted: #656d76; --text-dim: #8c959f;
    --red: #cf222e; --green: #1a7f37; --yellow: #9a6700;
    --blue: #0969da; --purple: #8250df; --orange: #bc4c00;
  }
  .badge-red { background: rgba(207,34,46,0.1); }
  .badge-green { background: rgba(26,127,55,0.1); }
  .badge-yellow { background: rgba(154,103,0,0.1); }
  .badge-blue { background: rgba(9,105,218,0.1); }
  .badge-purple { background: rgba(130,80,223,0.1); }
  .badge-dim { background: rgba(140,149,159,0.15); }
  tr:hover { background: rgba(9,105,218,0.04); }
}
</style>
</head>
<body>
%(body)s
</body>
</html>""" % {"body": body, "window": window_label}


def _render_header(data: Dict[str, Any], meta: Dict[str, Any]) -> str:
    sync = data.get("sync", {}) if isinstance(data.get("sync"), dict) else {}
    changes = data.get("changes", {}) if isinstance(data.get("changes"), dict) else {}
    generated = _esc(str(meta.get("generated_at", ""))[:19])
    trade_date = _esc(str(sync.get("trade_date", "")))
    window_label = _esc(str(changes.get("window_label", "")))

    return """<h1>复盘报告</h1>
<div class="subtitle">%s &middot; %s &middot; 行情日期 %s &middot; 标的 %s</div>""" % (
        generated or "-",
        window_label or "日级",
        trade_date or "-",
        _esc(str(sync.get("record_count", 0))),
    )


def _render_changes(data: Dict[str, Any]) -> str:
    changes = data.get("changes", {}) if isinstance(data.get("changes"), dict) else {}
    if not changes.get("available"):
        summary = _esc(str(changes.get("summary", "无历史数据可对比。")))
        return '<h2>变化追踪</h2><div class="card"><span class="empty">%s</span></div>' % summary

    lines = ['<h2>变化追踪（%s）</h2>' % _esc(changes.get("window_label", "日级"))]
    lines.append('<div class="card">')
    lines.append('<div class="changes-summary">%s</div>' % _esc(changes.get("summary", "")))

    risk = changes.get("risk_flags", {}) if isinstance(changes.get("risk_flags"), dict) else {}
    added_risks = risk.get("added", []) if isinstance(risk.get("added"), list) else []
    removed_risks = risk.get("removed", []) if isinstance(risk.get("removed"), list) else []
    if added_risks or removed_risks:
        lines.append("<div>")
        for r in added_risks:
            lines.append('<span class="badge badge-red">+ %s</span>' % _esc(str(r)))
        for r in removed_risks:
            lines.append('<span class="badge badge-green">- %s</span>' % _esc(str(r)))
        lines.append("</div>")

    watchlist = changes.get("watchlist", {}) if isinstance(changes.get("watchlist"), dict) else {}
    _append_change_badges(lines, watchlist, "观察")

    portfolio = changes.get("portfolio_review", {}) if isinstance(changes.get("portfolio_review"), dict) else {}
    _append_change_badges(lines, portfolio, "持仓")

    hotspots = changes.get("hotspots", {}) if isinstance(changes.get("hotspots"), dict) else {}
    _append_hotspot_badges(lines, hotspots)

    lines.append("</div>")
    return "\n".join(lines)


def _append_change_badges(lines: List[str], change: Dict[str, Any], label: str) -> None:
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    changed = change.get("changed", []) if isinstance(change.get("changed"), list) else []
    if not added and not removed and not changed:
        return
    lines.append("<div>")
    lines.append('<span class="badge badge-dim">%s</span>' % _esc(label))
    for item in added[:5]:
        sym = _item_label(item)
        lines.append('<span class="badge badge-red">+ %s</span>' % _esc(sym))
    for item in removed[:5]:
        sym = _item_label(item)
        lines.append('<span class="badge badge-green">- %s</span>' % _esc(sym))
    for item in changed[:5]:
        sym = _item_label(item)
        lines.append('<span class="badge badge-yellow">~ %s</span>' % _esc(sym))
    lines.append("</div>")


def _append_hotspot_badges(lines: List[str], hotspots: Dict[str, Any]) -> None:
    added = hotspots.get("added", []) if isinstance(hotspots.get("added"), list) else []
    removed = hotspots.get("removed", []) if isinstance(hotspots.get("removed"), list) else []
    if not added and not removed:
        return
    lines.append("<div>")
    lines.append('<span class="badge badge-dim">热点</span>')
    for item in added[:5]:
        key = str(item.get("key", "")) if isinstance(item, dict) else str(item)
        lines.append('<span class="badge badge-red">+ %s</span>' % _esc(key))
    for item in removed[:5]:
        key = str(item.get("key", "")) if isinstance(item, dict) else str(item)
        lines.append('<span class="badge badge-green">- %s</span>' % _esc(key))
    lines.append("</div>")


def _render_sync_status(data: Dict[str, Any]) -> str:
    sync = data.get("sync", {}) if isinstance(data.get("sync"), dict) else {}
    summary = sync.get("summary", {}) if isinstance(sync.get("summary"), dict) else {}
    ok = sync.get("ok", False)
    if sync.get("skipped"):
        status_badge = '<span class="badge badge-dim">已跳过</span>'
    else:
        status_badge = '<span class="badge badge-green">成功</span>' if ok else '<span class="badge badge-red">失败</span>'
    return """<h2>数据同步</h2>
<div class="card">
%s 标的 %s &middot; 涨停 %s &middot; 阶段新高 %s
</div>""" % (
        status_badge,
        _esc(str(sync.get("record_count", 0))),
        _esc(str(summary.get("limit_up", 0))),
        _esc(str(summary.get("stage_high", 0))),
    )


def _render_summary(data: Dict[str, Any]) -> str:
    summary = _esc(str(data.get("daily_summary") or ""))
    if not summary:
        return '<h2>今日摘要</h2><div class="card"><span class="empty">无摘要数据。</span></div>'
    return '<h2>今日摘要</h2><div class="card">%s</div>' % summary


def _render_risk_flags(data: Dict[str, Any]) -> str:
    flags = data.get("risk_flags", []) if isinstance(data.get("risk_flags"), list) else []
    if not flags:
        return ""
    lines = ["<h2>风险标记</h2>", "<div>"]
    for flag in flags:
        lines.append('<span class="badge badge-red">%s</span>' % _esc(_label(str(flag))))
    lines.append("</div>")
    return "\n".join(lines)


def _render_hotspots(data: Dict[str, Any]) -> str:
    brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
    hotspots = brief.get("top_hotspots", []) if isinstance(brief.get("top_hotspots"), list) else []
    if not hotspots:
        return ""

    lines = ["<h2>热点板块</h2>", "<table>"]
    lines.append("<tr><th></th><th>板块</th><th>层级</th><th class='num'>评分</th>"
                 "<th>雷达</th><th class='num'>活跃</th><th>龙头</th><th>信号</th></tr>")

    for i, hs in enumerate(hotspots[:8]):
        if not isinstance(hs, dict):
            continue
        score = _safe_float(hs.get("score"), 0)
        heat_color = _score_color(score)
        leaders = hs.get("leaders", []) if isinstance(hs.get("leaders"), list) else []
        leader_text = ", ".join(
            _esc(str(ldr.get("name", ldr.get("symbol", "")))) for ldr in leaders[:3] if isinstance(ldr, dict)
        ) or "-"
        signals = hs.get("signals", []) if isinstance(hs.get("signals"), list) else []
        signal_text = ", ".join(_esc(_label(str(s))) for s in signals[:3]) or "-"

        score_bar = _svg_score_bar(score)
        breakdown = hs.get("breakdown", {}) if isinstance(hs.get("breakdown"), dict) else {}
        radar = _svg_radar(breakdown)

        lines.append(
            "<tr><td><span class='heat' style='background:%s'></span></td>"
            "<td>%s</td><td>%s</td>"
            "<td class='num'>%s <span>%.1f</span></td>"
            "<td>%s</td>"
            "<td class='num'>%s/%s</td><td>%s</td><td>%s</td></tr>"
            % (
                heat_color,
                _esc(str(hs.get("sub_sector", ""))),
                _esc(str(hs.get("layer", ""))),
                score_bar, score,
                radar,
                _esc(str(hs.get("active_member_count", 0))),
                _esc(str(hs.get("member_count", 0))),
                leader_text,
                signal_text,
            )
        )

    lines.append("</table>")
    return "\n".join(lines)


def _render_watchlist(data: Dict[str, Any]) -> str:
    watchlist = data.get("watchlist", {}) if isinstance(data.get("watchlist"), dict) else {}
    items = watchlist.get("items", []) if isinstance(watchlist.get("items"), list) else []
    if not items:
        return ""

    count = _safe_int(watchlist.get("count", len(items)))
    lines = ["<h2>观察清单 (%s)</h2>" % _esc(str(count)), "<table>"]
    lines.append("<tr><th>代码</th><th>名称</th><th>板块</th>"
                 "<th class='num'>涨跌幅</th><th class='num'>量比</th>"
                 "<th class='num'>热点</th><th>持仓</th><th>聚焦</th></tr>")

    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        change_pct = _safe_float(item.get("change_pct"), 0)
        amount_ratio = _safe_float(item.get("amount_ratio"), 0)
        hotspot_score = _safe_float(item.get("hotspot_score"), 0)
        holding_badge = '<span class="badge badge-purple">持仓</span>' if item.get("is_holding") else ""

        change_bar = _svg_change_bar(change_pct)
        volume_dot = _svg_volume_dot(amount_ratio)

        lines.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td>"
            "<td class='num %s'>%s <span>%s%.2f%%</span></td>"
            "<td class='num'>%s <span>%.1f</span></td>"
            "<td class='num'>%.0f</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (
                _esc(str(item.get("symbol", ""))),
                _esc(str(item.get("name", ""))),
                _esc(str(item.get("sub_sector", item.get("layer", "")))),
                "pos" if change_pct > 0 else "neg" if change_pct < 0 else "",
                change_bar,
                "↑+" if change_pct > 0 else "↓" if change_pct < 0 else "",
                change_pct,
                volume_dot,
                amount_ratio,
                hotspot_score,
                holding_badge,
                _esc(_label(str(item.get("focus", item.get("reason", ""))))[:40]),
            )
        )

    lines.append("</table>")
    return "\n".join(lines)


def _render_portfolio(data: Dict[str, Any]) -> str:
    portfolio = data.get("portfolio_review", {}) if isinstance(data.get("portfolio_review"), dict) else {}
    items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    if not items:
        return ""

    summary = _esc(str(portfolio.get("summary", "")))
    review_count = _safe_int(portfolio.get("review_count", len(items)))
    lines = ["<h2>持仓复核 (%s)</h2>" % _esc(str(review_count))]
    if summary:
        lines.append('<div class="card">%s</div>' % summary)
    lines.append("<table>")
    lines.append("<tr><th>代码</th><th>名称</th><th>优先级</th>"
                 "<th class='num'>涨跌幅</th><th class='num'>量比</th>"
                 "<th>风险</th><th>复核要点</th></tr>")

    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority", ""))
        priority_class = _priority_badge_class(priority)
        quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
        change_pct = _safe_float(quote.get("change_pct"), 0)
        amount_ratio = _safe_float(quote.get("amount_ratio"), 0)
        risk_flags = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        review_points = item.get("review_points", []) if isinstance(item.get("review_points"), list) else []

        risk_badges = " ".join(
            '<span class="badge badge-red">%s</span>' % _esc(_label(str(r))) for r in risk_flags[:3]
        )
        review_text = _esc("; ".join(str(p) for p in review_points[:2])[:60])

        change_bar = _svg_change_bar(change_pct)
        volume_dot = _svg_volume_dot(amount_ratio)

        lines.append(
            "<tr><td>%s</td><td>%s</td>"
            '<td><span class="badge %s">%s</span></td>'
            "<td class='num %s'>%s <span>%s%.2f%%</span></td>"
            "<td class='num'>%s <span>%.1f</span></td>"
            "<td>%s</td><td>%s</td></tr>"
            % (
                _esc(str(item.get("symbol", ""))),
                _esc(str(item.get("name", ""))),
                priority_class, _esc(priority),
                "pos" if change_pct > 0 else "neg" if change_pct < 0 else "",
                change_bar,
                "↑+" if change_pct > 0 else "↓" if change_pct < 0 else "",
                change_pct,
                volume_dot,
                amount_ratio,
                risk_badges or "-",
                review_text or "-",
            )
        )

    lines.append("</table>")
    return "\n".join(lines)


def _render_validation(data: Dict[str, Any]) -> str:
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    if not validation:
        return ""
    ok = validation.get("ok")
    summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []

    if ok and not warnings and not errors:
        return ""

    status = '<span class="badge badge-green">通过</span>' if ok else '<span class="badge badge-yellow">告警</span>'
    lines = ["<h2>数据验证</h2>", '<div class="card">', status]
    warn_count = summary.get("warning_count", len(warnings))
    error_count = summary.get("error_count", len(errors))
    if warn_count:
        lines.append(' 告警 %d' % warn_count)
    if error_count:
        lines.append(' 错误 %d' % error_count)
    lines.append("</div>")
    return "\n".join(lines)


def _render_command_queue(data: Dict[str, Any]) -> str:
    queue = data.get("command_queue", []) if isinstance(data.get("command_queue"), list) else []
    if queue:
        lines = ["<h2>下一步</h2>", "<table>"]
        lines.append("<tr><th>#</th><th>状态</th><th>命令</th><th>JSON</th><th>完成标准</th></tr>")
        for item in queue[:8]:
            if not isinstance(item, dict):
                continue
            state = str(item.get("state_effect") or "read_only")
            badge_class = "badge-dim" if state == "read_only" else "badge-yellow"
            lines.append(
                "<tr><td>%s</td><td><span class='badge %s'>%s</span></td>"
                "<td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    _esc(str(item.get("rank", ""))),
                    badge_class,
                    _esc(_label(state)),
                    _esc(str(item.get("command", ""))),
                    _esc(str(item.get("json_command", ""))),
                    _esc(str(item.get("done_when", ""))),
                )
            )
        lines.append("</table>")
        return "\n".join(lines)

    commands = data.get("next_commands", []) if isinstance(data.get("next_commands"), list) else []
    if not commands:
        return ""
    lines = ["<h2>下一步</h2>", '<div class="card">']
    for command in commands[:8]:
        lines.append('<div><span class="badge badge-dim">命令</span> %s</div>' % _esc(str(command)))
    lines.append("</div>")
    return "\n".join(lines)


def _render_footer(data: Dict[str, Any]) -> str:
    journal = data.get("journal_entry", {}) if isinstance(data.get("journal_entry"), dict) else {}
    journal_status = data.get("journal_status", {}) if isinstance(data.get("journal_status"), dict) else {}
    lines = []
    if data.get("journal_saved") and journal:
        lines.append('<div class="card">日报留档: %s</div>' % _esc(str(journal.get("id", ""))))
    elif journal_status:
        lines.append('<div class="card">日报留档: 未保存，%s</div>' % _esc(str(journal_status.get("reason", ""))))

    lines.append('<div class="guardrails">')
    lines.append("不产生交易指令、目标价或仓位建议。由 market-intel 生成。")
    lines.append("</div>")
    return "\n".join(lines)


def _item_label(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("symbol") or "?")
    return str(item)


def _score_color(score: float) -> str:
    if score >= 70:
        return "var(--red)"
    if score >= 50:
        return "var(--orange)"
    if score >= 30:
        return "var(--yellow)"
    return "var(--text-dim)"


def _score_bar_class(score: float) -> str:
    if score >= 70:
        return "red"
    if score >= 50:
        return "yellow"
    return "blue"


def _priority_badge_class(priority: str) -> str:
    p = priority.lower()
    if "high" in p or "重点" in p:
        return "badge-red"
    if "medium" in p or "中" in p:
        return "badge-yellow"
    return "badge-dim"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
        if result != result or result == float("inf") or result == float("-inf"):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _label(key: str) -> str:
    return LABELS.get(key, key)


# ---------------------------------------------------------------------------
# Inline SVG sparkline generators
# ---------------------------------------------------------------------------


def _svg_change_bar(change_pct: float) -> str:
    """Horizontal bar centered at midpoint. Red right (positive), green left (negative).

    Max width 60px, height 14px. 10% = full half-width (30px).
    """
    width = 60
    height = 14
    mid = width / 2
    clamped = max(-10.0, min(10.0, change_pct))
    bar_len = abs(clamped) / 10.0 * mid
    bar_len = max(1, bar_len)

    if clamped >= 0:
        color = "var(--red)"
        x = mid
    else:
        color = "var(--green)"
        x = mid - bar_len

    return (
        '<svg width="%d" height="%d" style="vertical-align:middle">'
        '<rect x="%.1f" y="3" width="%.1f" height="8" rx="1" fill="%s" opacity="0.85"/>'
        '<line x1="%.1f" y1="1" x2="%.1f" y2="13" stroke="var(--text-dim)" stroke-width="0.5"/>'
        "</svg>"
    ) % (width, height, x, bar_len, color, mid, mid)


def _svg_volume_dot(amount_ratio: float) -> str:
    """Circle with radius proportional to amount_ratio.

    Min radius 3px, max 8px. Color: blue (<1.5), yellow (1.5-3), orange (>3).
    SVG canvas 18x18px.
    """
    size = 18
    clamped = max(0.0, min(5.0, amount_ratio))
    radius = 3 + (clamped / 5.0) * 5  # 3..8
    radius = max(3.0, min(8.0, radius))

    if amount_ratio > 3:
        color = "var(--orange)"
    elif amount_ratio >= 1.5:
        color = "var(--yellow)"
    else:
        color = "var(--blue)"

    return (
        '<svg width="%d" height="%d" style="vertical-align:middle">'
        '<circle cx="9" cy="9" r="%.1f" fill="%s" opacity="0.8"/>'
        "</svg>"
    ) % (size, size, radius, color)


def _svg_score_bar(score: float, max_score: float = 100) -> str:
    """Thin horizontal progress bar. Width 50px, height 8px.

    Background dim. Fill colored by score: red >70, yellow >50, blue <=50.
    """
    width = 50
    height = 8
    ratio = max(0.0, min(1.0, score / max_score)) if max_score > 0 else 0
    fill_w = ratio * width

    if score > 70:
        color = "var(--red)"
    elif score > 50:
        color = "var(--yellow)"
    else:
        color = "var(--blue)"

    return (
        '<svg width="%d" height="%d" style="vertical-align:middle">'
        '<rect x="0" y="0" width="%d" height="%d" rx="2" fill="var(--text-dim)" opacity="0.3"/>'
        '<rect x="0" y="0" width="%.1f" height="%d" rx="2" fill="%s" opacity="0.8"/>'
        "</svg>"
    ) % (width, height, width, height, fill_w, height, color)


def _svg_radar(breakdown: dict) -> str:
    """6-point radar chart, 36x36px.

    Each axis 0-1 normalized from breakdown dict values.
    Fill: semi-transparent blue. Stroke: theme blue.
    """
    size = 36
    cx = size / 2
    cy = size / 2
    max_r = 14  # max radius for points

    # Take up to 6 values, pad with 0 if fewer
    values: List[float] = []
    if isinstance(breakdown, dict):
        for v in list(breakdown.values())[:6]:
            values.append(max(0.0, min(1.0, _safe_float(v, 0))))
    while len(values) < 6:
        values.append(0.0)

    # Compute polygon points
    points = []
    for i in range(6):
        angle = math.pi / 2 + i * (2 * math.pi / 6)
        r = values[i] * max_r
        px = cx + r * math.cos(angle)
        py = cy - r * math.sin(angle)
        points.append("%.1f,%.1f" % (px, py))

    # Background hexagon (guides)
    guide_points = []
    for i in range(6):
        angle = math.pi / 2 + i * (2 * math.pi / 6)
        px = cx + max_r * math.cos(angle)
        py = cy - max_r * math.sin(angle)
        guide_points.append("%.1f,%.1f" % (px, py))

    return (
        '<svg width="%d" height="%d" style="vertical-align:middle">'
        '<polygon points="%s" fill="none" stroke="var(--text-dim)" stroke-width="0.5" opacity="0.4"/>'
        '<polygon points="%s" fill="var(--blue)" fill-opacity="0.25" stroke="var(--blue)" stroke-width="1"/>'
        "</svg>"
    ) % (size, size, " ".join(guide_points), " ".join(points))


def _esc(text: str) -> str:
    return html.escape(text)
