"""Generate a self-contained HTML review report."""

import html
import json
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
</style>
</head>
<body>
%(body)s
</body>
</html>""" % {"body": body, "window": window_label}


def _render_header(data: Dict[str, Any], meta: Dict[str, Any]) -> str:
    sync = data.get("sync", {}) if isinstance(data.get("sync"), dict) else {}
    generated = _esc(str(meta.get("generated_at", ""))[:19])
    trade_date = _esc(str(sync.get("trade_date", "")))

    return """<h1>复盘报告</h1>
<div class="subtitle">%s &middot; 行情日期 %s &middot; 标的 %s</div>""" % (
        generated or "-",
        trade_date or "-",
        sync.get("record_count", 0),
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
                 "<th class='num'>活跃</th><th>龙头</th><th>信号</th></tr>")

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

        bar_width = max(2, min(80, int(score * 0.8)))
        lines.append(
            "<tr><td><span class='heat' style='background:%s'></span></td>"
            "<td>%s</td><td>%s</td>"
            "<td class='num'><span class='bar bar-%s' style='width:%dpx'></span> %.1f</td>"
            "<td class='num'>%s/%s</td><td>%s</td><td>%s</td></tr>"
            % (
                heat_color,
                _esc(str(hs.get("sub_sector", ""))),
                _esc(str(hs.get("layer", ""))),
                _score_bar_class(score), bar_width, score,
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

        lines.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td>"
            "<td class='num %s'>%s%.2f%%</td>"
            "<td class='num'>%.1f</td>"
            "<td class='num'>%.0f</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (
                _esc(str(item.get("symbol", ""))),
                _esc(str(item.get("name", ""))),
                _esc(str(item.get("sub_sector", item.get("layer", "")))),
                "pos" if change_pct > 0 else "neg" if change_pct < 0 else "",
                "+" if change_pct > 0 else "",
                change_pct,
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

        lines.append(
            "<tr><td>%s</td><td>%s</td>"
            '<td><span class="badge %s">%s</span></td>'
            "<td class='num %s'>%s%.2f%%</td>"
            "<td class='num'>%.1f</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (
                _esc(str(item.get("symbol", ""))),
                _esc(str(item.get("name", ""))),
                priority_class, _esc(priority),
                "pos" if change_pct > 0 else "neg" if change_pct < 0 else "",
                "+" if change_pct > 0 else "",
                change_pct,
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


def _esc(text: str) -> str:
    return html.escape(text)
