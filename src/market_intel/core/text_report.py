from typing import Dict, Iterable, List


LABELS = {
    "chase_high_risk": "追高风险",
    "theme_concentration": "主题集中",
    "single_name_or_thin_resonance": "单票或弱共振",
    "intraday_fade_risk": "冲高回落风险",
    "weak_hotspot_score": "热点强度偏弱",
    "continuation_needs_confirmation": "持续性待确认",
    "sector_resonance": "板块共振",
    "single_name_move": "单票异动",
    "strong_members": "强势成员",
    "leader_strength": "龙头强",
    "high_hotspot_score": "热点分高",
    "broad_sector_strength": "板块扩散",
    "stage_high_members": "阶段新高",
    "turnover_expansion": "成交放大",
    "multi_chain_exposure": "多链路暴露",
    "theme_overlap": "主题重叠",
    "leader_in_hotspot": "热点领涨",
    "active_name_to_verify": "活跃标的待验证",
    "holding_risk_review": "持仓风险复核",
    "holding_watch": "持仓观察",
    "hotspot_leader_watch": "热点领涨观察",
    "thin_resonance_verify": "弱共振核验",
    "watch": "观察",
    "duplicate_symbol_exposure": "多链路重复归属",
    "holding_missing_quote": "持仓缺行情",
    "missing_role": "角色待确认",
    "invalid_symbol": "代码异常",
    "column_shift_suspected": "原始表格疑似错位",
    "not_tradable": "不可交易或待确认",
    "no_hotspot_context": "缺少热点上下文",
    "not_in_pool": "未匹配池子",
    "foundation_pool_match": "基础清单覆盖",
    "draft_pool_match": "草稿池覆盖",
    "a_share_universe_foundation": "全 A 基础清单",
    "candidate_status": "候选状态",
    "extra_pool_overlay": "扩展池叠加",
    "pending_fields": "字段待补",
    "unmatched_holdings": "持仓未匹配池子",
    "turnover_expansion_watch": "成交放大待复核",
    "weak_price_context": "价格上下文偏弱",
    "high_review": "重点复核",
    "medium_review": "中等复核",
    "normal_review": "常规复核",
    "read_only": "只读",
    "writes_journal": "写入留档",
    "writes_runtime": "写入 runtime",
    "portfolio_review": "持仓复核",
    "watchlist": "观察清单",
    "data_quality": "数据质量",
    "current_change": "当前变化",
    "data_repair": "数据修复",
    "current_vs_latest": "当前变化",
    "history_transition": "历史转折",
    "holding_review": "持仓复核",
    "risk_review": "风险复核",
    "manual_followup": "人工后续",
    "evidence_checklist": "证据清单",
    "hypothesis_board": "观察假设",
    "review_completion": "复盘收尾",
    "review_handoff": "复盘交接",
    "security_cards": "单票卡片",
    "changed_holdings": "变化持仓",
    "priority_holdings": "重点持仓",
    "portfolio_pressure": "组合压力",
    "market_structure": "市场结构",
    "market_scan": "全市场扫描",
    "journal_record": "复盘留档",
}

QUESTION_LABELS = {
    "Verify data quality flags before using this item in downstream analysis.": "使用前先核对数据质量标记。",
    "Confirm the company's role in this sub-sector.": "确认该公司在子链路中的角色。",
    "Add a concise company logic statement.": "补充一句话公司逻辑。",
}


def render_brief_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel brief\n\n无数据。"

    lines = [
        "market-intel brief",
        "",
        "总览",
        str(data.get("summary") or "无简报数据。"),
        "",
        "热点",
    ]
    lines.extend(render_hotspots(data.get("top_hotspots", [])))
    lines.extend(["", "持仓暴露"])
    lines.extend(render_holding_impact(data.get("holding_impact", {})))
    lines.extend(["", "观察清单"])
    lines.extend(render_watchlist(data.get("watchlist", [])))
    lines.extend(["", "风险"])
    lines.extend(render_list(data.get("risk_flags", []), empty="暂无风险标签。"))
    lines.extend(["", "待验证问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无待验证问题。"))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_scan_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel scan\n\n无数据。"
    if not payload.get("ok"):
        lines = [
            "market-intel scan",
            "",
            "数据未就绪",
        ]
        lines.extend(render_scan_errors(payload.get("errors", [])))
        lines.extend(["", "下一步"])
        lines.extend(render_scan_actions(data.get("next_actions", [])))
        lines.extend(["", "边界"])
        lines.extend(render_list(data.get("guardrails", []), empty="scan 不生成买卖指令。"))
        return "\n".join(lines)

    lines = [
        "market-intel scan",
        "",
        "总览",
        "- %s" % (data.get("summary") or "暂无扫描摘要。"),
        "- 范围 %s | 模式 %s | 行情 %s | 匹配 %s | 候选 %s"
        % (
            data.get("pool") or "-",
            render_scan_mode(data.get("scan_mode")),
            data.get("quote_count", 0),
            data.get("matched_quote_count", 0),
            len(data.get("candidate_securities", []) if isinstance(data.get("candidate_securities"), list) else []),
        ),
    ]
    coverage = data.get("coverage_context", {}) if isinstance(data.get("coverage_context"), dict) else {}
    if coverage:
        lines.extend(["", "覆盖底座"])
        lines.extend(render_focus_coverage_context(coverage))
    lines.extend(["", "板块扫描"])
    lines.extend(render_scan_groups(data.get("sector_groups", [])))
    lines.extend(["", "候选复盘"])
    lines.extend(render_scan_candidates(data.get("candidate_securities", [])))
    lines.extend(["", "待验证问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无待验证问题。"))
    lines.extend(["", "下一步"])
    lines.extend(render_scan_actions(data.get("next_actions", [])))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_pool_explain_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel pool explain\n\n无数据。"

    facts = data.get("facts", {})
    item = data.get("item", {})
    lines = [
        "market-intel pool explain",
        "",
        "标的",
        "%s %s | %s | %s"
        % (
            facts.get("symbol"),
            facts.get("name"),
            facts.get("market"),
            "可交易" if facts.get("tradable") else "不可交易或待确认",
        ),
        "",
        "主链路",
        "%s / %s | 角色: %s | 优先级: %s"
        % (
            facts.get("primary_layer"),
            facts.get("primary_sub_sector"),
            facts.get("primary_role") or "待确认",
            facts.get("priority"),
        ),
        "",
        "核心逻辑",
        str(item.get("logic") or data.get("explain") or "暂无。"),
        "",
        "链路暴露",
    ]
    lines.extend(render_exposures(data.get("exposures", [])))
    lines.extend(["", "当前上下文"])
    lines.extend(render_runtime_context(data.get("runtime_context", {})))
    lines.extend(["", "信号"])
    lines.extend(render_list(data.get("signals", []), empty="暂无信号。"))
    lines.extend(["", "风险"])
    lines.extend(render_list(data.get("risks", []), empty="暂无风险标签。"))
    lines.extend(["", "待验证问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无待验证问题。"))
    flags = data.get("data_quality_flags", [])
    if flags:
        lines.extend(["", "数据质量"])
        lines.extend(render_list(flags, empty="无。"))
    lines.extend(["", "边界", "- 这是市场情报，不是交易指令。", "- 不生成交易动作、目标价或仓位建议。"])
    return "\n".join(lines)


def render_pool_coverage_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel pool coverage\n\n无数据。"
    counts = data.get("counts", {}) if isinstance(data.get("counts"), dict) else {}
    lines = [
        "market-intel pool coverage",
        "",
        "总览",
        "- %s | 状态 %s | 范围 %s" % (data.get("pool"), data.get("status"), data.get("scope")),
        "- %s" % (data.get("summary") or "暂无摘要。"),
        "",
        "计数",
        "- 条目 %s | 可交易 %s | A 股 %s | 非 A 股 %s | 不可交易 %s | 数据待复核 %s"
        % (
            counts.get("items", 0),
            counts.get("tradable", 0),
            counts.get("cn_a", 0),
            counts.get("non_cn_a", 0),
            counts.get("non_tradable", 0),
            counts.get("data_quality_flagged", 0),
        ),
        "",
        "市场分布",
    ]
    lines.extend(render_named_counts(data.get("market_distribution", []), empty="暂无市场分布。"))
    lines.extend(["", "A 股板块"])
    lines.extend(render_named_counts(data.get("cn_a_board_distribution", []), empty="暂无 A 股板块分布。"))
    lines.extend(["", "全 A 基础清单"])
    lines.extend(render_universe_summary(data.get("universe", {})))
    lines.extend(["", "层级分布"])
    lines.extend(render_coverage_layers(data.get("layer_distribution", [])))
    lines.extend(["", "持仓覆盖"])
    lines.extend(render_holdings_coverage(data.get("holdings_coverage", {})))
    lines.extend(["", "补池任务"])
    lines.extend(render_expansion_queue(data.get("expansion_queue", [])))
    lines.extend(["", "研究证据任务"])
    lines.extend(render_research_queue(data.get("research_queue", [])))
    lines.extend(["", "覆盖缺口"])
    lines.extend(render_coverage_gaps(data.get("gaps", [])))
    lines.extend(["", "数据质量"])
    lines.extend(render_coverage_data_quality(data.get("data_quality", {})))
    lines.extend(["", "数据质量清理队列"])
    lines.extend(render_data_quality_queue(data.get("data_quality_queue", [])))
    lines.extend(["", "下一步"])
    lines.extend(render_coverage_next_actions(data.get("next_actions", [])))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_pool_quality_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel pool quality\n\n无数据。"
    lines = [
        "market-intel pool quality",
        "",
        "总览",
        "- %s | %s | found=%s" % (data.get("pool"), data.get("flag"), data.get("found")),
        "- %s" % (data.get("summary") or "暂无摘要。"),
        "- 严重度 %s | 分类 %s | 影响 %s"
        % (data.get("severity"), data.get("category"), data.get("affected_count", 0)),
        "",
        "原因",
        "- %s" % (data.get("reason") or "暂无。"),
        "",
        "建议动作",
        "- %s" % (data.get("suggested_action") or "查看样本并修正。"),
        "",
        "完成标准",
        "- %s" % (data.get("done_when") or "重新运行 coverage 确认。"),
        "",
        "样本",
    ]
    samples = data.get("samples", []) if isinstance(data.get("samples"), list) else []
    if not samples:
        lines.append("- 暂无样本。")
    for sample in samples[:12]:
        if not isinstance(sample, dict):
            continue
        flags = sample.get("flags", []) if isinstance(sample.get("flags"), list) else []
        lines.append(
            "- %s:row %s | %s %s | code=%s | section=%s | flags=%s"
            % (
                sample.get("source_file") or "pool",
                sample.get("raw_row"),
                sample.get("symbol") or "未上市",
                sample.get("name"),
                sample.get("raw_code"),
                sample.get("raw_section"),
                ",".join(str(flag) for flag in flags[:4]),
            )
        )
        if sample.get("raw_company") or sample.get("raw_desc"):
            lines.append(
                "  原始: company=%s | desc=%s"
                % (sample.get("raw_company") or "", sample.get("raw_desc") or "")
            )
        if sample.get("fix_hint"):
            lines.append("  修复提示: %s" % sample.get("fix_hint"))
    lines.extend(["", "下一步"])
    lines.extend(render_list(data.get("next_commands", []), empty="暂无下一步。"))
    lines.extend(["", "边界", "- %s" % (data.get("write_policy") or "只读复核，不自动修改数据。")])
    return "\n".join(lines)


def render_pool_expansion_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel pool expansion\n\n无数据。"

    lines = [
        "market-intel pool expansion",
        "",
        "状态",
    ]
    if "review_state" in data:
        lines.append(
            "- review %s | 行 %s | ready %s | blocked %s"
            % (
                data.get("review_state"),
                data.get("row_count", 0),
                data.get("ready_count", 0),
                data.get("blocked_count", 0),
            )
        )
    else:
        lines.append(
            "- export | 行 %s | written %s | dry_run %s | output %s"
            % (
                data.get("record_count", 0),
                data.get("written"),
                data.get("dry_run"),
                data.get("output"),
            )
        )

    lines.extend(["", "阻断项"])
    lines.extend(render_expansion_blockers(data.get("blockers", [])))
    lines.extend(["", "可用行"])
    lines.extend(render_expansion_ready_rows(data.get("ready_rows", data.get("rows", []))))
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    lines.extend(["", "边界", "- 只导出或审查候选补池 CSV，不自动修改主复盘池。", "- 通过 review 后仍建议用 overlay 跑 coverage/focus 复核。"])
    return "\n".join(lines)


def render_pool_research_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel pool research\n\n无数据。"

    lines = [
        "market-intel pool research",
        "",
        "状态",
        "- export | 行 %s | written %s | dry_run %s | output %s"
        % (
            data.get("record_count", 0),
            data.get("written"),
            data.get("dry_run"),
            data.get("output"),
        ),
        "",
        "研究草稿",
    ]
    rows = data.get("rows", []) if isinstance(data.get("rows"), list) else []
    if not rows:
        lines.append("- 暂无 foundation 持仓需要导出研究证据草稿。")
    else:
        for row in rows[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- %s %s | %s | 待补: 核心逻辑、关键证据、证伪风险"
                % (row.get("symbol"), row.get("name"), row.get("status"))
            )
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    lines.extend(["", "边界", "- 只导出研究证据草稿，不自动生成结论。", "- 导入前需要人工补齐三项证据并设置 status=reviewed。"])
    return "\n".join(lines)


def render_universe_summary(value: object) -> List[str]:
    data = value if isinstance(value, dict) else {}
    if not data.get("available"):
        return ["- 未接入 A 股基础清单。"]
    source_files = data.get("source_files", []) if isinstance(data.get("source_files"), list) else []
    lines = [
        "- 已接入 | schema %s | 记录 %s | 行业 %s | 概念 %s | 指数 %s"
        % (
            data.get("schema") or "UNKNOWN",
            data.get("record_count", 0),
            data.get("industry_count", 0),
            data.get("concept_count", 0),
            data.get("index_membership_count", 0),
        )
    ]
    if source_files:
        lines.append("- 来源文件: %s" % ", ".join(str(item) for item in source_files[:5]))
    profile = data.get("sector_profile", {}) if isinstance(data.get("sector_profile"), dict) else {}
    if profile:
        lines.append(
            "- 字段覆盖 | 行业 %.1f%% | 概念 %.1f%% | 指数 %.1f%%"
            % (
                float(profile.get("industry_coverage_ratio") or 0) * 100,
                float(profile.get("concept_coverage_ratio") or 0) * 100,
                float(profile.get("index_coverage_ratio") or 0) * 100,
            )
        )
        industries = profile.get("top_industries", []) if isinstance(profile.get("top_industries"), list) else []
        if industries:
            lines.append(
                "- 头部行业: %s"
                % "；".join("%s(%s)" % (item.get("name"), item.get("count")) for item in industries[:5] if isinstance(item, dict))
            )
        missing_counts = profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {}
        if any(int(value or 0) for value in missing_counts.values()):
            lines.append(
                "- 缺字段 | 行业 %s | 概念 %s | 指数 %s"
                % (
                    missing_counts.get("industry", 0),
                    missing_counts.get("concepts", 0),
                    missing_counts.get("index_membership", 0),
                )
            )
            samples = profile.get("missing_field_samples", []) if isinstance(profile.get("missing_field_samples"), list) else []
            for item in samples[:3]:
                if isinstance(item, dict):
                    fields = item.get("missing_fields", []) if isinstance(item.get("missing_fields"), list) else []
                    lines.append("- 待补 %s %s | %s" % (item.get("symbol") or "-", item.get("name") or "-", "/".join(str(field) for field in fields)))
    sample_items = data.get("sample_items", []) if isinstance(data.get("sample_items"), list) else []
    for item in sample_items[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- %s %s | %s | %s | %s"
            % (
                item.get("symbol") or "-",
                item.get("name") or "-",
                item.get("industry") or "行业待补",
                item.get("concepts") or "概念待补",
                item.get("index_membership") or "指数待补",
            )
        )
    return lines


def render_expansion_blockers(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无阻断项。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
        lines.append(
            "- %s | row %s | %s | %s"
            % (
                row.get("code"),
                detail.get("row", "-"),
                detail.get("symbol") or detail.get("path") or "",
                row.get("message"),
            )
        )
    return lines


def render_expansion_ready_rows(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无可用行。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        normalized = row.get("normalized", {}) if isinstance(row.get("normalized"), dict) else {}
        lines.append(
            "- row %s | %s %s | %s / %s | %s"
            % (
                row.get("row", "-"),
                row.get("symbol") or "",
                row.get("name") or "",
                normalized.get("primary_layer") or "",
                normalized.get("primary_sub_sector") or "",
                row.get("review_state") or "",
            )
        )
    return lines


def render_scan_mode(value: object) -> str:
    labels = {
        "all_a_universe": "全 A 基础清单",
        "pool_chain_seed": "复盘池链路种子",
    }
    return labels.get(str(value), str(value or "未知"))


def render_scan_errors(value: object) -> List[str]:
    errors = value if isinstance(value, list) else []
    if not errors:
        return ["- 暂无错误明细。"]
    lines = []
    for item in errors[:5]:
        if isinstance(item, dict):
            lines.append("- %s: %s" % (item.get("code"), item.get("message")))
    return lines or ["- 暂无错误明细。"]


def render_scan_groups(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无板块扫描结果。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "- #%s %s%s | 分 %.2f | 活跃 %s/%s | 涨幅 %.2f%% | 成交 %.2f | 风险 %s"
            % (
                row.get("rank") or "-",
                scan_group_type_label(row.get("group_type")),
                row.get("name") or "-",
                float(row.get("score") or 0),
                row.get("active_member_count", 0),
                row.get("member_count", 0),
                float(row.get("avg_change_pct") or 0),
                float(row.get("avg_amount_ratio") or 0),
                render_labels(row.get("risks", [])) if row.get("risks") else "无",
            )
        )
        leaders = row.get("leaders", []) if isinstance(row.get("leaders"), list) else []
        if leaders:
            lines.append("   领涨: %s" % render_scan_leaders(leaders))
        signals = row.get("signals", []) if isinstance(row.get("signals"), list) else []
        if signals:
            lines.append("   信号: %s" % render_labels(signals))
    return lines


def render_scan_candidates(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无候选复盘标的。"]
    lines = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        quote = row.get("quote", {}) if isinstance(row.get("quote"), dict) else {}
        mark = "持仓" if row.get("is_holding") else "观察"
        lines.append(
            "- #%s %s %s | %s | %s | 分 %.2f | %+s%% | 覆盖 %s"
            % (
                row.get("rank") or "-",
                row.get("symbol"),
                row.get("name"),
                mark,
                label(row.get("priority")),
                float(row.get("review_score") or 0),
                quote.get("change_pct", 0),
                row.get("coverage_state") or "-",
            )
        )
        if row.get("why_now"):
            lines.append("   为何现在看: %s" % row.get("why_now"))
        focus = row.get("review_focus", {}) if isinstance(row.get("review_focus"), dict) else {}
        if focus.get("headline"):
            lines.append("   复核焦点: %s" % focus.get("headline"))
        classification = focus.get("classification", {}) if isinstance(focus.get("classification"), dict) else {}
        if classification:
            parts = []
            if classification.get("industry"):
                parts.append("行业=%s" % classification.get("industry"))
            concepts = classification.get("concepts", []) if isinstance(classification.get("concepts"), list) else []
            if concepts:
                parts.append("概念=%s" % ",".join(str(value) for value in concepts[:3]))
            indexes = classification.get("index_membership", []) if isinstance(classification.get("index_membership"), list) else []
            if indexes:
                parts.append("指数=%s" % ",".join(str(value) for value in indexes[:3]))
            if parts:
                lines.append("   分类: %s" % " | ".join(parts))
        checklist = row.get("checklist", []) if isinstance(row.get("checklist"), list) else []
        if checklist:
            lines.append("   核对: %s" % "；".join(str(item) for item in checklist[:3]))
        commands = row.get("commands", []) if isinstance(row.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if row.get("done_when"):
            lines.append("   完成: %s" % row.get("done_when"))
    return lines


def render_scan_leaders(value: object) -> str:
    leaders = value if isinstance(value, list) else []
    parts = []
    for leader in leaders[:4]:
        if not isinstance(leader, dict):
            continue
        parts.append(
            "%s %s %+s%%"
            % (
                leader.get("symbol"),
                leader.get("name"),
                leader.get("change_pct"),
            )
        )
    return "；".join(parts) if parts else "无"


def render_scan_actions(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无下一步。"]
    lines = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        lines.append("- #%s %s" % (row.get("rank") or "-", row.get("command") or row.get("id")))
        if row.get("done_when"):
            lines.append("   完成: %s" % row.get("done_when"))
    return lines


def scan_group_type_label(value: object) -> str:
    labels = {
        "industry": "行业",
        "concept": "概念",
        "index": "指数",
        "chain": "链路",
        "unknown": "分组",
    }
    return labels.get(str(value), str(value or "分组"))


def render_named_counts(value: object, empty: str) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- %s" % empty]
    lines = []
    for row in rows[:8]:
        if isinstance(row, dict):
            lines.append("- %s: %s" % (row.get("name"), row.get("count")))
    return lines or ["- %s" % empty]


def render_coverage_layers(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无层级分布。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "- %s | 条目 %s | 可交易 %s | A 股 %s"
            % (row.get("layer"), row.get("item_count"), row.get("tradable_count"), row.get("cn_a_count"))
        )
    return lines


def render_holdings_coverage(value: object) -> List[str]:
    coverage = value if isinstance(value, dict) else {}
    if not coverage.get("available"):
        return ["- %s" % (coverage.get("reason") or "未提供持仓。")]

    ratio = coverage.get("matched_ratio", 0)
    try:
        ratio_text = "%.1f%%" % (float(ratio) * 100)
    except (TypeError, ValueError):
        ratio_text = "0.0%"
    lines = [
        "- 持仓 %s | 已覆盖 %s | 未覆盖 %s | 覆盖率 %s"
        % (
            coverage.get("holding_count", 0),
            coverage.get("matched_count", 0),
            coverage.get("unmatched_count", 0),
            ratio_text,
        )
    ]
    if coverage.get("needs_review_count"):
        lines.append(
            "   待复核覆盖: %s | 正式覆盖: %s | 基础覆盖: %s | 草稿匹配: %s"
            % (
                coverage.get("needs_review_count", 0),
                coverage.get("confirmed_count", 0),
                coverage.get("foundation_matched_count", 0),
                coverage.get("draft_matched_count", 0),
            )
        )
    if coverage.get("summary"):
        lines.append("   摘要: %s" % coverage.get("summary"))

    review_queue = coverage.get("review_queue", []) if isinstance(coverage.get("review_queue"), list) else []
    if review_queue:
        rendered = []
        for row in review_queue[:6]:
            if isinstance(row, dict):
                reasons = row.get("reasons", []) if isinstance(row.get("reasons"), list) else []
                rendered.append("%s %s[%s]" % (row.get("symbol"), row.get("name") or "", ",".join(str(reason) for reason in reasons[:3])))
        if rendered:
            lines.append("   待复核: %s" % "；".join(rendered))

    unmatched = coverage.get("unmatched", []) if isinstance(coverage.get("unmatched"), list) else []
    if unmatched:
        rendered = []
        for row in unmatched[:6]:
            if isinstance(row, dict):
                rendered.append("%s %s" % (row.get("symbol"), row.get("name") or ""))
        if rendered:
            lines.append("   未覆盖: %s" % "；".join(rendered))

    matched = coverage.get("matched", []) if isinstance(coverage.get("matched"), list) else []
    if matched:
        rendered = []
        for row in matched[:5]:
            if isinstance(row, dict):
                research_text = render_research_status(row.get("research_status", {}))
                suffix = " | %s" % research_text if research_text else ""
                rendered.append("%s %s/%s%s" % (row.get("symbol"), row.get("primary_layer"), row.get("primary_sub_sector"), suffix))
        if rendered:
            lines.append("   已覆盖样例: %s" % "；".join(rendered))
    return lines


def render_expansion_queue(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无补池任务。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        candidate = row.get("candidate_pool_row", {}) if isinstance(row.get("candidate_pool_row"), dict) else {}
        lines.append(
            "- #%s %s %s | %s | 必填: %s"
            % (
                row.get("rank"),
                row.get("symbol"),
                row.get("name"),
                row.get("reason"),
                "、".join(str(field) for field in row.get("required_fields", [])[:5])
                if isinstance(row.get("required_fields"), list)
                else "待确认",
            )
        )
        lines.append(
            "   候选行: %s,%s,%s,%s,%s,%s"
            % (
                candidate.get("status"),
                candidate.get("priority"),
                candidate.get("section"),
                candidate.get("level"),
                candidate.get("company"),
                candidate.get("code"),
            )
        )
        questions = row.get("review_questions", []) if isinstance(row.get("review_questions"), list) else []
        if questions:
            lines.append("   复核: %s" % "；".join(str(question) for question in questions[:3]))
    return lines


def render_research_queue(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无研究证据任务。"]
    lines = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        required = row.get("required_fields", []) if isinstance(row.get("required_fields"), list) else []
        lines.append(
            "- #%s %s %s | %s | 必填: %s"
            % (
                row.get("rank"),
                row.get("symbol"),
                row.get("name"),
                row.get("reason"),
                "、".join(str(field) for field in required[:5]) if required else "核心逻辑、关键证据、证伪风险",
            )
        )
        commands = row.get("commands", []) if isinstance(row.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
    return lines


def render_coverage_gaps(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无覆盖缺口。"]
    lines = []
    for row in rows[:6]:
        if isinstance(row, dict):
            lines.append("- %s | %s: %s" % (row.get("severity"), row.get("id"), row.get("message")))
    return lines


def render_coverage_data_quality(value: object) -> List[str]:
    quality = value if isinstance(value, dict) else {}
    lines = ["- 待复核条目: %s" % quality.get("flagged_item_count", 0)]
    top_flags = quality.get("top_flags", []) if isinstance(quality.get("top_flags"), list) else []
    if top_flags:
        lines.append("   标记: %s" % "；".join("%s(%s)" % (row.get("name"), row.get("count")) for row in top_flags[:5] if isinstance(row, dict)))
    samples = quality.get("sample_items", []) if isinstance(quality.get("sample_items"), list) else []
    if samples:
        rendered = []
        for row in samples[:4]:
            if not isinstance(row, dict):
                continue
            flags = row.get("flags", []) if isinstance(row.get("flags"), list) else []
            rendered.append("%s %s[%s]" % (row.get("symbol") or "未上市", row.get("name"), ",".join(str(flag) for flag in flags[:3])))
        lines.append("   样例: %s" % "；".join(rendered))
    return lines


def render_data_quality_queue(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无清理项。"]
    lines = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        lines.append(
            "- #%s %s | %s | 影响 %s | %s"
            % (
                row.get("rank"),
                row.get("flag"),
                row.get("severity"),
                row.get("affected_count", 0),
                row.get("suggested_action") or "查看样本并修正。",
            )
        )
        samples = row.get("samples", []) if isinstance(row.get("samples"), list) else []
        rendered = []
        for sample in samples[:3]:
            if not isinstance(sample, dict):
                continue
            rendered.append(
                "%s %s(row %s)"
                % (
                    sample.get("symbol") or sample.get("raw_code") or "未上市",
                    sample.get("name"),
                    sample.get("raw_row"),
                )
            )
        if rendered:
            lines.append("   样例: %s" % "；".join(rendered))
    return lines


def render_coverage_next_actions(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无下一步。"]
    lines = []
    for row in rows[:5]:
        if isinstance(row, dict):
            lines.append("- #%s %s | %s" % (row.get("rank"), row.get("id"), row.get("command")))
    return lines


def render_watchlist_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel watchlist\n\n无数据。"
    lines = [
        "market-intel watchlist",
        "",
        "总览",
        str(data.get("explain") or "暂无观察清单。"),
        "",
        "观察项",
    ]
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        lines.append("- 暂无观察项。")
    else:
        for item in items:
            if not isinstance(item, dict):
                continue
            mark = "持仓" if item.get("is_holding") else "观察"
            lines.append(
                "- %s %s | %s | %s / %s | 涨幅 %+s%% | 热点 %s | 成交放大 %s | 回落 %s%% | %s"
                % (
                    item.get("symbol"),
                    item.get("name"),
                    mark,
                    item.get("layer"),
                    item.get("sub_sector"),
                    item.get("change_pct"),
                    item.get("hotspot_score"),
                    item.get("amount_ratio"),
                    item.get("intraday_fade_pct"),
                    label(item.get("focus")),
                )
            )
            if item.get("signals"):
                lines.append("   信号: %s" % render_labels(item.get("signals", [])))
            if item.get("risks"):
                lines.append("   风险: %s" % render_labels(item.get("risks", [])))
    lines.extend(["", "风险汇总"])
    lines.extend(render_list(data.get("risk_flags", []), empty="暂无风险标签。"))
    lines.extend(["", "边界", "- 这是观察清单，不是交易指令。", "- 不生成交易动作、目标价或仓位建议。"])
    return "\n".join(lines)


def render_portfolio_review_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel portfolio review\n\n无数据。"
    lines = [
        "market-intel portfolio review",
        "",
        "总览",
        str(data.get("summary") or "暂无持仓复盘。"),
        "",
        "持仓复核",
    ]
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        lines.append("- 暂无持仓。")
    else:
        for item in items:
            if not isinstance(item, dict):
                continue
            lines.extend(render_portfolio_item(item))
    lines.extend(["", "重复暴露"])
    lines.extend(render_portfolio_repeated_exposure_detail(data))
    lines.extend(["", "待复核问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无待复核问题。"))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_portfolio_explain_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel portfolio explain\n\n无数据。"
    if not data.get("found"):
        lines = [
            "market-intel portfolio explain",
            "",
            "状态",
            "- %s" % (data.get("summary") or "未找到。"),
            "",
            "下一步",
        ]
        lines.extend(render_command_list(data.get("next_commands", [])))
        return "\n".join(lines)
    item = data.get("item", {}) if isinstance(data.get("item"), dict) else {}
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    related = data.get("related", {}) if isinstance(data.get("related"), dict) else {}
    lines = [
        "market-intel portfolio explain",
        "",
        "总览",
        str(data.get("summary") or item.get("explain") or "暂无。"),
        "",
        "行情",
    ]
    if quote:
        lines.append(
            "- 涨幅 %+s%% | 成交放大 %s | 回落 %s%% | 日期 %s"
            % (quote.get("change_pct"), quote.get("amount_ratio"), quote.get("intraday_fade_pct"), quote.get("trade_date"))
        )
    else:
        lines.append("- 无行情。")
    lines.extend(["", "热点"])
    if hotspot:
        lines.append("- %s / %s | 热点 %s" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score")))
        if hotspot.get("signals"):
            lines.append("   信号: %s" % render_labels(hotspot.get("signals", [])))
        if hotspot.get("risks"):
            lines.append("   风险: %s" % render_labels(hotspot.get("risks", [])))
    else:
        lines.append("- 无热点上下文。")
    lines.extend(["", "链路"])
    lines.append("- %s" % render_portfolio_exposures(item.get("exposures", [])))
    lines.extend(["", "风险"])
    lines.extend(render_list(item.get("risk_flags", []), empty="暂无风险标签。"))
    lines.extend(["", "相关持仓"])
    lines.extend(render_related_holdings(related))
    lines.extend(["", "复核问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无复核问题。"))
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_market_map_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel map\n\n无数据。"
    lines = [
        "market-intel map",
        "",
        "总览",
        str(data.get("summary") or "暂无链路地图。"),
        "",
        "链路",
    ]
    layers = data.get("layers", [])
    if not isinstance(layers, list) or not layers:
        lines.append("- 暂无链路数据。")
    else:
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            lines.append(
                "- %s | 池子 %s | 行情覆盖 %s | 热点 %s | 持仓 %s"
                % (
                    layer.get("layer"),
                    layer.get("pool_item_count"),
                    layer.get("quoted_item_count"),
                    layer.get("hotspot_count"),
                    layer.get("holding_count"),
                )
            )
            hotspot_text = render_layer_hotspots(layer.get("top_hotspots", []))
            if hotspot_text:
                lines.append("   热点: %s" % hotspot_text)
            holding_text = render_layer_holdings(layer.get("holdings", []))
            if holding_text:
                lines.append("   持仓: %s" % holding_text)
            repeated_text = render_group_counts(layer.get("repeated_exposures", []))
            if repeated_text != "无":
                lines.append("   重复暴露: %s" % repeated_text)
            risks = layer.get("risk_flags", [])
            if isinstance(risks, list) and risks:
                lines.append("   风险: %s" % render_labels(risks))
    unmatched = data.get("unmatched_holdings", [])
    if isinstance(unmatched, list) and unmatched:
        lines.extend(["", "未匹配持仓"])
        for item in unmatched:
            if not isinstance(item, dict):
                continue
            lines.append("- %s %s | %s" % (item.get("symbol"), item.get("name"), render_labels(item.get("risks", []))))
    lines.extend(["", "风险汇总"])
    lines.extend(render_list(data.get("risk_flags", []), empty="暂无风险标签。"))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_daily_report_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel daily\n\n无数据。"
    lines = [
        "market-intel daily",
        "",
        "总览",
        str(data.get("summary") or "暂无日报。"),
        "",
        "数据检查",
    ]
    lines.extend(render_validation_summary(data.get("validation", {})))
    brief = data.get("brief", {}) if isinstance(data.get("brief"), dict) else {}
    lines.extend(["", "热点摘要"])
    lines.extend(render_hotspots(brief.get("top_hotspots", [])[:3] if isinstance(brief.get("top_hotspots"), list) else []))
    market_map = data.get("map", {}) if isinstance(data.get("map"), dict) else {}
    lines.extend(["", "链路地图"])
    lines.extend(render_daily_map_lines(market_map.get("layers", [])))
    watchlist = data.get("watchlist", {}) if isinstance(data.get("watchlist"), dict) else {}
    lines.extend(["", "观察清单"])
    lines.extend(render_daily_watchlist_lines(watchlist.get("items", [])))
    portfolio_review = data.get("portfolio_review", {}) if isinstance(data.get("portfolio_review"), dict) else {}
    lines.extend(["", "持仓复核"])
    lines.extend(render_daily_portfolio_lines(portfolio_review.get("items", [])))
    lines.extend(["", "组合暴露"])
    lines.extend(render_portfolio_repeated_exposure_detail(portfolio_review))
    lines.extend(["", "复盘路径"])
    lines.extend(render_review_path(data.get("review_path", [])))
    lines.extend(["", "今日复核任务"])
    lines.extend(render_daily_review_tasks(data.get("review_tasks", [])))
    lines.extend(["", "标的复核队列"])
    lines.extend(render_daily_security_queue(data.get("security_review_queue", [])))
    lines.extend(["", "标的风险画像"])
    lines.extend(render_security_risk_profile(data.get("security_risk_profile", [])))
    lines.extend(["", "风险汇总"])
    lines.extend(render_risk_register(data.get("risk_register", []), data.get("risk_flags", [])))
    lines.extend(["", "留档入口"])
    lines.extend(render_daily_journal_actions(data.get("journal_actions", [])))
    lines.extend(["", "命令队列"])
    lines.extend(render_command_queue_lines(data.get("command_queue", []), limit=10))
    lines.extend(["", "下一步问题"])
    lines.extend(render_list(data.get("next_questions", []), empty="暂无问题。"))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_focus_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel focus\n\n无数据。"
    lines = [
        "market-intel focus",
        "",
        "总览",
        str(data.get("headline") or "暂无聚焦摘要。"),
        "",
        "数据状态",
    ]
    lines.extend(render_focus_data_status(data.get("data_status", {})))
    coverage = data.get("coverage_context", {}) if isinstance(data.get("coverage_context"), dict) else {}
    if coverage:
        lines.extend(["", "覆盖底座"])
        lines.extend(render_focus_coverage_context(coverage))
    lines.extend(["", "市场焦点"])
    lines.extend(render_focus_market(data.get("market_focus", {})))
    lines.extend(["", "组合压力"])
    lines.extend(render_focus_portfolio_pressure(data.get("portfolio_pressure", {})))
    lines.extend(["", "优先标的"])
    lines.extend(render_focus_securities(data.get("priority_securities", [])))
    lines.extend(["", "下一步"])
    first = data.get("first_runnable_command")
    if first:
        lines.append("- 先跑: %s" % first)
    lines.extend(render_focus_steps(data.get("next_steps", [])))
    lines.extend(["", "边界"])
    lines.extend(render_list(data.get("guardrails", []), empty="无。"))
    return "\n".join(lines)


def render_focus_data_status(value: object) -> List[str]:
    status = value if isinstance(value, dict) else {}
    state_label = {"ok": "可用", "warning": "有告警", "blocked": "阻塞"}.get(str(status.get("state")), str(status.get("state") or "未知"))
    lines = [
        "- %s | 行情 %s | 持仓 %s | 错误 %s | 告警 %s"
        % (
            state_label,
            status.get("quote_count", 0),
            status.get("holding_count", 0),
            status.get("error_count", 0),
            status.get("warning_count", 0),
        )
    ]
    issues = status.get("top_errors") or status.get("top_warnings")
    if isinstance(issues, list) and issues:
        rendered = []
        for issue in issues[:4]:
            if not isinstance(issue, dict):
                continue
            target = issue.get("symbol") or issue.get("path") or ""
            rendered.append("%s:%s" % (issue.get("code"), target) if target else str(issue.get("code")))
        lines.append("   重点: %s" % "；".join(rendered))
    if status.get("command"):
        lines.append("   命令: %s" % status.get("command"))
    return lines


def render_focus_coverage_context(value: object) -> List[str]:
    coverage = value if isinstance(value, dict) else {}
    if not coverage.get("available"):
        return ["- %s" % (coverage.get("summary") or "暂无复盘池覆盖上下文。")]
    lines = [
        "- %s | %s | 缺口 %s"
        % (
            coverage.get("pool") or "-",
            coverage.get("status") or "-",
            coverage.get("gap_count", 0),
        )
    ]
    if coverage.get("summary"):
        lines.append("   摘要: %s" % coverage.get("summary"))
    universe = coverage.get("universe", {}) if isinstance(coverage.get("universe"), dict) else {}
    profile = universe.get("sector_profile", {}) if isinstance(universe.get("sector_profile"), dict) else {}
    if universe:
        lines.append(
            "   全 A: %s | 记录 %s | 行业 %s | 概念 %s | 指数 %s"
            % (
                "已接入" if universe.get("available") else "未接入",
                universe.get("record_count", 0),
                universe.get("industry_count", 0),
                universe.get("concept_count", 0),
                universe.get("index_membership_count", 0),
            )
        )
    if profile:
        lines.append(
            "   字段覆盖: 行业 %.1f%% | 概念 %.1f%% | 指数 %.1f%%"
            % (
                float(profile.get("industry_coverage_ratio") or 0) * 100,
                float(profile.get("concept_coverage_ratio") or 0) * 100,
                float(profile.get("index_coverage_ratio") or 0) * 100,
            )
        )
        missing_counts = profile.get("missing_field_counts", {}) if isinstance(profile.get("missing_field_counts"), dict) else {}
        if any(int(count or 0) for count in missing_counts.values()):
            lines.append(
                "   缺字段: 行业 %s | 概念 %s | 指数 %s"
                % (
                    missing_counts.get("industry", 0),
                    missing_counts.get("concepts", 0),
                    missing_counts.get("index_membership", 0),
                )
            )
    gaps = coverage.get("top_gaps", []) if isinstance(coverage.get("top_gaps"), list) else []
    for gap in gaps[:3]:
        if isinstance(gap, dict):
            lines.append("   缺口: %s | %s" % (gap.get("severity"), gap.get("id")))
    actions = coverage.get("next_actions", []) if isinstance(coverage.get("next_actions"), list) else []
    for action in actions[:2]:
        if isinstance(action, dict) and action.get("command"):
            lines.append("   下一步: %s" % action.get("command"))
    return lines


def render_focus_market(value: object) -> List[str]:
    market = value if isinstance(value, dict) else {}
    strongest = market.get("strongest_chain", {}) if isinstance(market.get("strongest_chain"), dict) else {}
    lines = []
    if strongest:
        lines.append(
            "- 最强: %s / %s | 热点 %s | 活跃 %s/%s"
            % (
                strongest.get("layer"),
                strongest.get("sub_sector"),
                strongest.get("score"),
                strongest.get("active_member_count"),
                strongest.get("member_count"),
            )
        )
        leaders = strongest.get("leaders", []) if isinstance(strongest.get("leaders"), list) else []
        if leaders:
            lines.append("   领涨: %s" % "；".join(str(item) for item in leaders[:3]))
        risks = strongest.get("risks", []) if isinstance(strongest.get("risks"), list) else []
        if risks:
            lines.append("   风险: %s" % render_labels(risks))
    else:
        lines.append("- 暂无强链路。")
    chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
    if len(chains) > 1:
        lines.append("- 备选链路:")
        for item in chains[1:3]:
            if isinstance(item, dict):
                lines.append("   %s / %s | 热点 %s" % (item.get("layer"), item.get("sub_sector"), item.get("score")))
    return lines


def render_focus_portfolio_pressure(value: object) -> List[str]:
    pressure = value if isinstance(value, dict) else {}
    lines = [
        "- 重复链路 %s 组 | 重复主题 %s 组 | 高风险 %s 项"
        % (
            pressure.get("repeated_exposure_count", 0),
            pressure.get("repeated_overlap_count", 0),
            pressure.get("high_risk_count", 0),
        )
    ]
    groups = []
    if isinstance(pressure.get("repeated_exposures"), list):
        groups.extend(("链路", item) for item in pressure["repeated_exposures"][:2])
    if isinstance(pressure.get("repeated_overlap_groups"), list):
        groups.extend(("主题", item) for item in pressure["repeated_overlap_groups"][:2])
    for group_type, item in groups[:3]:
        if not isinstance(item, dict):
            continue
        symbols = item.get("symbols", []) if isinstance(item.get("symbols"), list) else []
        lines.append(
            "   %s: %s(%s) | %s"
            % (group_type, item.get("group"), item.get("holding_count"), "；".join(str(symbol) for symbol in symbols[:4]) or "无标的")
        )
    questions = pressure.get("questions", []) if isinstance(pressure.get("questions"), list) else []
    if questions:
        lines.append("   核对: %s" % questions[0])
    return lines


def render_focus_securities(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- 暂无优先标的。"]
    lines = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        marker = "持仓" if item.get("is_holding") else "观察"
        lines.append(
            "- #%s %s %s | %s | 分 %s | 涨幅 %s%% | 热点 %s"
            % (
                item.get("rank"),
                item.get("symbol"),
                item.get("name") or "",
                marker,
                item.get("priority_score"),
                item.get("change_pct"),
                item.get("hotspot_score"),
            )
        )
        if item.get("chain"):
            lines.append("   链路: %s" % item.get("chain"))
        if item.get("why_now"):
            lines.append("   为何现在看: %s" % item.get("why_now"))
        risks = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        if risks:
            lines.append("   风险: %s" % render_labels(risks))
        checklist = item.get("checklist", []) if isinstance(item.get("checklist"), list) else []
        if checklist:
            lines.append("   核对: %s" % "；".join(str(row) for row in checklist[:3]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % commands[0])
        note_command = item.get("note_command")
        if note_command:
            lines.append("   记录: %s" % note_command)
        if item.get("journal_ready"):
            lines.append("   留痕: %s" % item.get("journal_ready"))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines


def render_focus_steps(value: object) -> List[str]:
    steps = value if isinstance(value, list) else []
    if not steps:
        return ["- 暂无下一步。"]
    lines = []
    for item in steps[:5]:
        if not isinstance(item, dict):
            continue
        runnable = "可执行" if item.get("runnable") else "需前置"
        lines.append(
            "- #%s %s | %s | %s"
            % (item.get("rank"), runnable, item.get("title"), item.get("command") or "暂无命令")
        )
    return lines


def render_runtime_status_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel status runtime\n\n无数据。"
    readiness = data.get("readiness", {}) if isinstance(data.get("readiness"), dict) else {}
    freshness = data.get("freshness", {}) if isinstance(data.get("freshness"), dict) else {}
    universe = data.get("universe", {}) if isinstance(data.get("universe"), dict) else {}
    lines = [
        "market-intel status runtime",
        "",
        "状态",
        "- %s | %s" % (readiness.get("state"), readiness.get("reason")),
        "",
        "数据检查",
    ]
    lines.extend(render_validation_summary(data.get("validation", {})))
    lines.extend(["", "行情新鲜度"])
    lines.append(
        "- 最新交易日 %s | 距今 %s 天 | 阈值 %s 天 | %s"
        % (
            freshness.get("latest_trade_date") or "无",
            freshness.get("quote_age_days") if freshness.get("quote_age_days") is not None else "无",
            freshness.get("max_quote_age_days") if freshness.get("max_quote_age_days") is not None else "无",
            "过期" if freshness.get("is_stale") else "可用",
        )
    )
    if freshness.get("warnings"):
        lines.append("   告警: %s" % render_issue_codes(freshness.get("warnings", [])))
    if freshness.get("errors"):
        lines.append("   错误: %s" % render_issue_codes(freshness.get("errors", [])))
    if universe:
        lines.extend(["", "全 A 基础清单"])
        lines.append(
            "- %s | 记录 %s | 行业 %s | required %s"
            % (
                universe.get("state"),
                universe.get("record_count", 0),
                universe.get("industry_count", 0),
                universe.get("required"),
            )
        )
        if universe.get("warnings"):
            lines.append("   告警: %s" % render_issue_codes(universe.get("warnings", [])))
    lines.extend(["", "下一步"])
    lines.extend(render_next_actions(data.get("next_actions", [])))
    return "\n".join(lines)


def render_agent_plan_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel agent plan\n\n无数据。"
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    readiness = runtime.get("readiness", {}) if isinstance(runtime.get("readiness"), dict) else {}
    journal = data.get("journal", {}) if isinstance(data.get("journal"), dict) else {}
    execution = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    steps = data.get("steps", []) if isinstance(data.get("steps"), list) else []
    lines = [
        "market-intel agent plan",
        "",
        "状态",
        "- %s | %s" % (data.get("state"), data.get("summary")),
        "- runtime: %s | %s" % (readiness.get("state"), readiness.get("reason")),
        "",
        "留档",
        "- 条目 %s | 可对比 %s" % (journal.get("entry_count"), "是" if journal.get("can_compare") else "否"),
    ]
    compare_pair = journal.get("compare_pair", {}) if isinstance(journal.get("compare_pair"), dict) else {}
    if compare_pair:
        lines.append("- 对比命令: %s" % compare_pair.get("command"))
    lines.extend(["", "下一跳"])
    command = execution.get("next_runnable_command")
    lines.append("- %s" % (command or "暂无可执行命令。"))
    lines.extend(["", "步骤"])
    lines.extend(render_agent_steps(steps))
    return "\n".join(lines)


def render_agent_run_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel agent run\n\n无数据。"
    lines = [
        "market-intel agent run",
        "",
        "状态",
        "- %s | %s" % (data.get("state"), data.get("summary")),
    ]
    source = data.get("source_briefing", {}) if isinstance(data.get("source_briefing"), dict) else {}
    if source:
        lines.append("- 来源: %s | %s" % (source.get("command"), source.get("summary")))
    limits = data.get("run_limits", {}) if isinstance(data.get("run_limits"), dict) else {}
    lines.append("- 只读步骤上限 %s | 跳过写入 %s" % (limits.get("max_steps"), "是" if limits.get("writes_are_skipped") else "否"))
    lines.extend(["", "复盘摘要"])
    lines.extend(render_agent_run_digest(data.get("review_digest", {})))
    lines.extend(["", "已运行"])
    lines.extend(render_agent_run_results(data.get("results", [])))
    lines.extend(["", "已跳过"])
    lines.extend(render_agent_run_skipped(data.get("skipped", [])))
    lines.extend(["", "人工后续"])
    lines.extend(render_agent_run_followups(data.get("manual_followups", [])))
    return "\n".join(lines)


def render_dashboard_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel dashboard\n\n无数据。"
    lines = [
        "market-intel dashboard",
        "",
        "状态",
        "- %s | %s" % (data.get("state"), data.get("summary") or "暂无摘要。"),
    ]
    tiles = data.get("tiles", []) if isinstance(data.get("tiles"), list) else []
    if tiles:
        lines.extend(["", "概览"])
        for item in tiles:
            if isinstance(item, dict):
                lines.append("- %s: %s | %s" % (item.get("label"), item.get("value"), item.get("detail") or ""))
    coverage = data.get("coverage_context", {}) if isinstance(data.get("coverage_context"), dict) else {}
    if coverage:
        lines.extend(["", "覆盖底座"])
        lines.extend(render_focus_coverage_context(coverage))
    market = data.get("market_pulse", {}) if isinstance(data.get("market_pulse"), dict) else {}
    if market:
        lines.extend(["", "全市场"])
        lines.extend(render_dashboard_market_pulse(market))
    portfolio = data.get("portfolio_pulse", {}) if isinstance(data.get("portfolio_pulse"), dict) else {}
    if portfolio:
        lines.extend(["", "持仓"])
        lines.extend(render_dashboard_portfolio_pulse(portfolio))
    evidence = data.get("evidence_gaps", {}) if isinstance(data.get("evidence_gaps"), dict) else {}
    if evidence:
        lines.extend(["", "证据缺口"])
        lines.extend(render_dashboard_evidence_gaps(evidence))
    plan = data.get("review_plan", {}) if isinstance(data.get("review_plan"), dict) else {}
    if plan:
        lines.extend(["", "复盘计划"])
        lines.extend(render_dashboard_review_plan(plan))
    actions = data.get("action_lane", {}) if isinstance(data.get("action_lane"), dict) else {}
    if actions:
        lines.extend(["", "行动队列"])
        lines.extend(render_dashboard_action_lane(actions))
    handoff = data.get("handoff", {}) if isinstance(data.get("handoff"), dict) else {}
    if handoff:
        lines.extend(["", "交接"])
        lines.extend(render_dashboard_handoff(handoff))
    guardrails = data.get("guardrails", []) if isinstance(data.get("guardrails"), list) else []
    if guardrails:
        lines.extend(["", "边界"])
        lines.extend(render_list(guardrails, empty="不生成交易指令。"))
    return "\n".join(lines)


def render_dashboard_market_pulse(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无全市场扫描。")]
    if value.get("quote_count") is not None:
        lines.append("- 行情匹配: %s/%s | 模式 %s" % (
            value.get("matched_quote_count", 0),
            value.get("quote_count", 0),
            render_scan_mode(value.get("scan_mode")),
        ))
    groups = value.get("top_groups", []) if isinstance(value.get("top_groups"), list) else []
    for group in groups[:3]:
        if isinstance(group, dict):
            lines.append(
                "   板块: #%s %s%s | 分 %s | 活跃 %s/%s"
                % (
                    group.get("rank"),
                    scan_group_type_label(group.get("group_type")),
                    group.get("name"),
                    group.get("score"),
                    group.get("active_member_count", 0),
                    group.get("member_count", 0),
                )
            )
    candidates = value.get("candidates", []) if isinstance(value.get("candidates"), list) else []
    for item in candidates[:3]:
        if isinstance(item, dict):
            lines.append(
                "   候选: #%s %s %s | 分 %s | 覆盖 %s"
                % (
                    item.get("rank"),
                    item.get("symbol"),
                    item.get("name"),
                    item.get("review_score"),
                    label(item.get("coverage_state")),
                )
            )
            if item.get("why_now"):
                lines.append("      原因: %s" % item.get("why_now"))
            if item.get("json_command"):
                lines.append("      命令: %s" % item.get("json_command"))
    questions = value.get("questions", []) if isinstance(value.get("questions"), list) else []
    if questions:
        lines.append("   问题: %s" % "；".join(str(item) for item in questions[:3]))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_dashboard_portfolio_pulse(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无持仓复盘。")]
    buckets = value.get("buckets", {}) if isinstance(value.get("buckets"), dict) else {}
    if buckets:
        lines.append(
            "- 分布: 重点 %s | 变化 %s | 缺行情 %s | 缺热点 %s | 重叠 %s"
            % (
                value.get("high_review_count", buckets.get("high_review", 0)),
                value.get("changed_holding_count", 0),
                buckets.get("missing_quote", 0),
                buckets.get("without_hotspot", 0),
                buckets.get("with_overlap", 0),
            )
        )
    holdings = value.get("top_holdings", []) if isinstance(value.get("top_holdings"), list) else []
    for item in holdings[:3]:
        if isinstance(item, dict):
            lines.append(
                "   持仓: #%s %s %s | %s | 分 %s | 覆盖 %s"
                % (
                    item.get("rank"),
                    item.get("symbol"),
                    item.get("name"),
                    label(item.get("priority")),
                    item.get("review_score"),
                    label(item.get("coverage_state")),
                )
            )
            if item.get("primary_question"):
                lines.append("      问题: %s" % item.get("primary_question"))
            if item.get("primary_json_command"):
                lines.append("      命令: %s" % item.get("primary_json_command"))
    groups = value.get("pressure_groups", []) if isinstance(value.get("pressure_groups"), list) else []
    for group in groups[:2]:
        if isinstance(group, dict):
            group_type = {"chain": "链路", "theme": "主题"}.get(str(group.get("group_type")), label(group.get("group_type")))
            lines.append("   压力: %s %s | 持仓 %s" % (group_type, group.get("group"), group.get("holding_count")))
            if group.get("priority_question"):
                lines.append("      问题: %s" % group.get("priority_question"))
    questions = value.get("questions", []) if isinstance(value.get("questions"), list) else []
    if questions:
        lines.append("   持仓问题: %s" % "；".join(str(item) for item in questions[:3]))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_dashboard_evidence_gaps(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无证据缺口。")]
    repair = value.get("data_repair", {}) if isinstance(value.get("data_repair"), dict) else {}
    if repair.get("available"):
        lines.append("   数据修复: %s" % (repair.get("summary") or "需处理数据问题。"))
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    if not items and not repair.get("available"):
        lines.append("   暂无待读证据。")
    for item in items[:5]:
        if isinstance(item, dict):
            lines.append(
                "   #%s %s | %s | %s"
                % (
                    item.get("rank"),
                    item.get("title"),
                    label(item.get("item_type")),
                    item.get("coverage_label") or label(item.get("coverage_status")),
                )
            )
            missing = item.get("missing_evidence", []) if isinstance(item.get("missing_evidence"), list) else []
            if missing:
                lines.append("      待补: %s" % "；".join(str(row) for row in missing[:3]))
            if item.get("json_command"):
                lines.append("      命令: %s" % item.get("json_command"))
            if item.get("done_when"):
                lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_dashboard_action_lane(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无关注队列。")]
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    for item in items[:5]:
        if isinstance(item, dict):
            state = "已读" if item.get("already_read") else "可读" if item.get("runnable") else "人工"
            lines.append(
                "   #%s %s | %s | %s"
                % (item.get("rank"), item.get("title"), label(item.get("item_type")), state)
            )
            if item.get("reason"):
                lines.append("      原因: %s" % item.get("reason"))
            if item.get("json_command"):
                lines.append("      命令: %s" % item.get("json_command"))
            if item.get("done_when"):
                lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_dashboard_review_plan(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无复盘计划。")]
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        state = "已读" if item.get("already_read") else "只读" if item.get("step_type") == "read" else "人工"
        lines.append(
            "   #%s %s | %s | %s"
            % (item.get("rank"), item.get("title"), label(item.get("item_type")), state)
        )
        if item.get("reason"):
            lines.append("      原因: %s" % item.get("reason"))
        symbols = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        if symbols:
            lines.append("      标的: %s" % "、".join(str(symbol) for symbol in symbols[:5]))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("      证据: %s" % "；".join(str(row) for row in evidence[:3]))
        if item.get("json_command"):
            lines.append("      命令: %s" % item.get("json_command"))
        if item.get("done_when"):
            lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_dashboard_handoff(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无交接信息。")]
    if value.get("resume_prompt"):
        lines.append("- 接手提示: %s" % value.get("resume_prompt"))
    completion = value.get("completion", {}) if isinstance(value.get("completion"), dict) else {}
    if completion:
        lines.append(
            "- 收尾: %s | 可记录 %s | 阻塞 %s | 人工 %s | 待读 %s"
            % (
                completion.get("completion_state"),
                "是" if completion.get("ready_for_journal_note") else "否",
                completion.get("blocking_count", 0),
                completion.get("manual_required_count", 0),
                completion.get("pending_count", 0),
            )
        )
    next_read = value.get("next_read", []) if isinstance(value.get("next_read"), list) else []
    if next_read:
        lines.append("- 下一条只读:")
        for item in next_read[:3]:
            if isinstance(item, dict):
                lines.append("   #%s %s | %s" % (item.get("rank"), item.get("title"), item.get("json_command")))
    manual = value.get("manual_items", []) if isinstance(value.get("manual_items"), list) else []
    if manual:
        lines.append("- 人工确认:")
        for item in manual[:3]:
            if isinstance(item, dict):
                lines.append("   #%s %s | %s" % (item.get("rank"), item.get("title"), item.get("json_command")))
    records = value.get("record_templates", []) if isinstance(value.get("record_templates"), list) else []
    if records:
        lines.append("- 记录模板:")
        for item in records[:2]:
            if isinstance(item, dict):
                lines.append("   #%s %s | %s" % (item.get("rank"), item.get("section"), item.get("prefilled_note_command")))
    return lines


def render_agent_next_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel agent next\n\n无数据。"
    lines = [
        "market-intel agent next",
        "",
        "状态",
        "- %s | %s" % (data.get("state"), data.get("summary")),
    ]
    if data.get("symbol"):
        lines.append("- 聚焦标的: %s" % data.get("symbol"))
    coverage = data.get("coverage_context", {}) if isinstance(data.get("coverage_context"), dict) else {}
    if coverage:
        lines.extend(["", "覆盖底座"])
        lines.extend(render_focus_coverage_context(coverage))
    scan = data.get("market_scan", {}) if isinstance(data.get("market_scan"), dict) else {}
    if scan:
        lines.extend(["", "全市场扫描"])
        lines.extend(render_agent_next_market_scan(scan))
    handoff = data.get("review_handoff", {}) if isinstance(data.get("review_handoff"), dict) else {}
    if handoff:
        lines.extend(["", "交接"])
        lines.extend(render_agent_next_handoff(handoff))
    cards = data.get("security_cards", {}) if isinstance(data.get("security_cards"), dict) else {}
    if cards:
        lines.extend(["", "单票卡片"])
        lines.extend(render_agent_run_security_cards(cards))
    completion = data.get("review_completion", {}) if isinstance(data.get("review_completion"), dict) else {}
    if completion:
        lines.extend(["", "收尾"])
        lines.extend(render_agent_run_review_completion(completion))
    return "\n".join(lines)


def render_agent_next_handoff(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无。")]
    if value.get("resume_prompt"):
        lines.append("- 接手提示: %s" % value.get("resume_prompt"))
    chain = value.get("command_chain", []) if isinstance(value.get("command_chain"), list) else []
    if chain:
        lines.append("- 命令链:")
        for item in chain[:6]:
            if isinstance(item, dict):
                lines.append("   #%s %s | %s | %s" % (
                    item.get("rank"),
                    item.get("step_type"),
                    item.get("title"),
                    item.get("json_command"),
                ))
    return lines


def render_agent_next_market_scan(value: Dict[str, object]) -> List[str]:
    lines = ["- %s" % (value.get("summary") or "暂无。")]
    groups = value.get("top_groups", []) if isinstance(value.get("top_groups"), list) else []
    for group in groups[:2]:
        if isinstance(group, dict):
            lines.append(
                "   板块: #%s %s%s | 分 %s | 活跃 %s/%s"
                % (
                    group.get("rank"),
                    scan_group_type_label(group.get("group_type")),
                    group.get("name"),
                    group.get("score"),
                    group.get("active_member_count", 0),
                    group.get("member_count", 0),
                )
            )
    candidates = value.get("top_candidates", []) if isinstance(value.get("top_candidates"), list) else []
    for item in candidates[:2]:
        if isinstance(item, dict):
            lines.append(
                "   候选: #%s %s %s | 分 %s | 覆盖 %s"
                % (
                    item.get("rank"),
                    item.get("symbol"),
                    item.get("name"),
                    item.get("review_score"),
                    item.get("coverage_state"),
                )
            )
    return lines


def render_agent_run_digest(value: object) -> List[str]:
    digest = value if isinstance(value, dict) else {}
    if not digest:
        return ["- 暂无复盘摘要。"]
    lines = ["- %s" % (digest.get("headline") or "暂无摘要。")]
    data_quality = digest.get("data_quality", {}) if isinstance(digest.get("data_quality"), dict) else {}
    if data_quality:
        lines.append("- 数据质量: %s" % (data_quality.get("summary") or "暂无。"))
    coverage = digest.get("coverage_context", {}) if isinstance(digest.get("coverage_context"), dict) else {}
    if coverage:
        lines.append("- 覆盖底座:")
        lines.extend("   %s" % line.lstrip("- ") for line in render_focus_coverage_context(coverage)[:6])
    scan = digest.get("market_scan", {}) if isinstance(digest.get("market_scan"), dict) else {}
    if scan:
        lines.append("- 全市场扫描: %s" % (scan.get("summary") or "暂无。"))
        groups = scan.get("top_groups", []) if isinstance(scan.get("top_groups"), list) else []
        for group in groups[:2]:
            if isinstance(group, dict):
                lines.append(
                    "   板块: #%s %s%s | 分 %s | 活跃 %s/%s"
                    % (
                        group.get("rank"),
                        scan_group_type_label(group.get("group_type")),
                        group.get("name"),
                        group.get("score"),
                        group.get("active_member_count", 0),
                        group.get("member_count", 0),
                    )
                )
        candidates = scan.get("top_candidates", []) if isinstance(scan.get("top_candidates"), list) else []
        for item in candidates[:2]:
            if isinstance(item, dict):
                lines.append(
                    "   候选: #%s %s %s | 分 %s | 覆盖 %s"
                    % (
                        item.get("rank"),
                        item.get("symbol"),
                        item.get("name"),
                        item.get("review_score"),
                        item.get("coverage_state"),
                    )
                )
    repair = digest.get("data_repair_plan", {}) if isinstance(digest.get("data_repair_plan"), dict) else {}
    if repair and repair.get("available"):
        lines.extend(render_agent_run_data_repair_plan(repair))
    market = digest.get("market_structure", {}) if isinstance(digest.get("market_structure"), dict) else {}
    if market:
        lines.append("- 市场结构: %s" % (market.get("summary") or "暂无。"))
        chains = market.get("top_chains", []) if isinstance(market.get("top_chains"), list) else []
        for chain in chains[:2]:
            if isinstance(chain, dict):
                lines.append("   链路: #%s %s | 热点 %s | 活跃 %s/%s" % (
                    chain.get("rank"),
                    chain.get("chain"),
                    chain.get("score"),
                    chain.get("active_member_count"),
                    chain.get("member_count"),
                ))
    pressure = digest.get("portfolio_pressure", {}) if isinstance(digest.get("portfolio_pressure"), dict) else {}
    if pressure:
        lines.append("- 组合压力: %s" % (pressure.get("summary") or "暂无。"))
        groups = pressure.get("groups", []) if isinstance(pressure.get("groups"), list) else []
        for group in groups[:2]:
            if isinstance(group, dict):
                group_type = {"chain": "链路", "theme": "主题"}.get(str(group.get("group_type")), label(group.get("group_type")))
                lines.append(
                    "   暴露: %s | %s | 持仓 %s | 变化成员 %s"
                    % (group_type, group.get("group"), group.get("holding_count"), group.get("changed_member_count", 0))
                )
                changed = group.get("changed_members", []) if isinstance(group.get("changed_members"), list) else []
                if changed:
                    lines.append("      变化成员: %s" % "；".join(render_changed_pressure_member(item) for item in changed[:4] if isinstance(item, dict)))
                if group.get("priority_question"):
                    lines.append("      问题: %s" % group.get("priority_question"))
                if group.get("primary_json_command"):
                    lines.append("      命令: %s" % group.get("primary_json_command"))
    dashboard = digest.get("holding_dashboard", {}) if isinstance(digest.get("holding_dashboard"), dict) else {}
    if dashboard:
        lines.extend(render_agent_run_holding_dashboard(dashboard))
    securities = digest.get("securities_to_review", []) if isinstance(digest.get("securities_to_review"), list) else []
    if securities:
        lines.append("- 标的复核:")
        for item in securities[:3]:
            if not isinstance(item, dict):
                continue
            labels = item.get("risk_labels", []) if isinstance(item.get("risk_labels"), list) else []
            lines.append("   #%s %s %s | %s | 分 %s | %s" % (
                item.get("rank"),
                item.get("symbol"),
                item.get("name") or "",
                item.get("severity"),
                item.get("priority_score"),
                "、".join(str(value) for value in labels[:3]) or "暂无风险标签",
            ))
    risks = digest.get("risk_watch", []) if isinstance(digest.get("risk_watch"), list) else []
    if risks:
        lines.append("- 风险观察:")
        for item in risks[:3]:
            if isinstance(item, dict):
                lines.append("   #%s %s | %s | 涉及 %s" % (item.get("rank"), item.get("label"), item.get("severity"), item.get("affected_count")))
    change_tracking = digest.get("change_tracking", {}) if isinstance(digest.get("change_tracking"), dict) else {}
    if change_tracking:
        lines.extend(render_agent_run_change_tracking(change_tracking))
    workbench = digest.get("security_workbench", []) if isinstance(digest.get("security_workbench"), list) else []
    if workbench:
        lines.extend(render_agent_run_security_workbench(workbench))
    cards = digest.get("security_cards", {}) if isinstance(digest.get("security_cards"), dict) else {}
    if cards:
        lines.extend(render_agent_run_security_cards(cards))
    evidence_checklist = digest.get("evidence_checklist", {}) if isinstance(digest.get("evidence_checklist"), dict) else {}
    if evidence_checklist:
        lines.extend(render_agent_run_evidence_checklist(evidence_checklist))
    hypothesis_board = digest.get("hypothesis_board", {}) if isinstance(digest.get("hypothesis_board"), dict) else {}
    if hypothesis_board:
        lines.extend(render_agent_run_hypothesis_board(hypothesis_board))
    journal_draft = digest.get("journal_draft", {}) if isinstance(digest.get("journal_draft"), dict) else {}
    if journal_draft:
        lines.extend(render_agent_run_journal_draft(journal_draft))
    attention_queue = digest.get("attention_queue", {}) if isinstance(digest.get("attention_queue"), dict) else {}
    if attention_queue:
        lines.extend(render_agent_run_attention_queue(attention_queue))
    followup_watch = digest.get("followup_watch", {}) if isinstance(digest.get("followup_watch"), dict) else {}
    if followup_watch:
        lines.extend(render_agent_run_followup_watch(followup_watch))
    completion = digest.get("review_completion", {}) if isinstance(digest.get("review_completion"), dict) else {}
    if completion:
        lines.extend(render_agent_run_review_completion(completion))
    handoff = digest.get("review_handoff", {}) if isinstance(digest.get("review_handoff"), dict) else {}
    if handoff:
        lines.extend(render_agent_run_review_handoff(handoff))
    next_steps = digest.get("next_steps", []) if isinstance(digest.get("next_steps"), list) else []
    if next_steps:
        lines.append("- 下一步:")
        for step in next_steps[:4]:
            if isinstance(step, dict):
                lines.append("   #%s %s | %s" % (step.get("rank"), step.get("title"), step.get("command")))
    return lines


def render_changed_pressure_member(value: Dict[str, object]) -> str:
    reasons = value.get("reasons", []) if isinstance(value.get("reasons"), list) else []
    suffix = " | %s" % "、".join(str(reason) for reason in reasons[:3]) if reasons else ""
    return "%s %s%s" % (value.get("symbol"), value.get("name") or "", suffix)


def render_agent_run_attention_queue(value: Dict[str, object]) -> List[str]:
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    if not items:
        return ["- 关注队列: 暂无。"]
    lines = ["- 关注队列: %s" % (value.get("summary") or "暂无。")]
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        runnable = "可只读执行" if item.get("runnable") else "需人工确认" if item.get("requires_manual") else "待处理"
        lines.append(
            "   #%s %s | %s | %s"
            % (item.get("rank"), item.get("title"), label(item.get("item_type")), runnable)
        )
        if item.get("reason"):
            lines.append("      原因: %s" % item.get("reason"))
        symbols = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        if symbols:
            lines.append("      标的: %s" % "、".join(str(symbol) for symbol in symbols[:5]))
        if item.get("json_command") or item.get("command"):
            lines.append("      命令: %s" % (item.get("json_command") or item.get("command")))
        linked = item.get("linked_result", {}) if isinstance(item.get("linked_result"), dict) else {}
        if linked:
            lines.append("      已读: #%s %s | %s" % (
                linked.get("run_rank"),
                linked.get("payload_command"),
                linked.get("summary") or "",
            ))
        context = item.get("linked_context", {}) if isinstance(item.get("linked_context"), dict) else {}
        if context and not linked:
            lines.append("      上下文: %s | %s" % (context.get("source") or context.get("payload_command"), context.get("summary") or ""))
        note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
        if note.get("available"):
            lines.append("      记录: %s | %s" % (note.get("section"), note.get("prefilled_note_command")))
            if note.get("run_after"):
                lines.append("      记录前置: %s" % note.get("run_after"))
        if item.get("requires_prior_command"):
            lines.append("      前置: %s" % item.get("requires_prior_command"))
        if item.get("done_when"):
            lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_workflow_step(step: Dict[str, object]) -> str:
    command = step.get("json_command")
    if command:
        return "%s: %s" % (step.get("title"), command)
    return "%s: %s" % (step.get("title"), step.get("done_when"))


def render_agent_run_security_cards(value: Dict[str, object]) -> List[str]:
    cards = value.get("cards", []) if isinstance(value.get("cards"), list) else []
    if not cards:
        return ["- 单票卡片: 暂无。"]
    lines = ["- 单票卡片: %s" % (value.get("summary") or "暂无。")]
    for item in cards[:4]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "   #%s %s %s | %s | 分 %s"
            % (
                item.get("rank"),
                item.get("symbol"),
                item.get("name") or "",
                label(item.get("priority")),
                item.get("review_score"),
            )
        )
        if item.get("next_json_command"):
            lines.append("      命令: %s" % item.get("next_json_command"))
        coverage_state = item.get("coverage_state")
        if coverage_state and coverage_state != "confirmed":
            reasons = item.get("coverage_state_reasons", []) if isinstance(item.get("coverage_state_reasons"), list) else []
            reason_text = " | 原因: %s" % render_labels(reasons) if reasons else ""
            lines.append("      覆盖: %s%s" % (label(coverage_state), reason_text))
        research_text = render_research_status(item.get("research_status", {}))
        if research_text:
            lines.append("      研究: %s" % research_text)
        workflow = item.get("research_workflow", []) if isinstance(item.get("research_workflow"), list) else []
        if workflow:
            lines.append("      研究流程: %s" % "；".join(render_workflow_step(step) for step in workflow[:3] if isinstance(step, dict)))
        hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
        if hotspot:
            lines.append("      热点: %s | 分 %s" % (hotspot.get("chain"), hotspot.get("score")))
        risks = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        if risks:
            lines.append("      风险: %s" % "、".join(str(row) for row in risks[:4]))
        evidence = item.get("supporting_evidence", []) if isinstance(item.get("supporting_evidence"), list) else []
        if evidence:
            lines.append("      证据: %s" % "；".join(str(row) for row in evidence[:3]))
        gaps = item.get("open_gaps", []) if isinstance(item.get("open_gaps"), list) else []
        if gaps:
            lines.append("      待补: %s" % "；".join(str(row) for row in gaps[:3]))
        questions = item.get("questions", []) if isinstance(item.get("questions"), list) else []
        if questions:
            lines.append("      问题: %s" % "；".join(str(row) for row in questions[:2]))
        note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
        if note.get("prefilled_note_command"):
            lines.append("      记录: %s" % note.get("prefilled_note_command"))
            if note.get("run_after"):
                lines.append("      记录前置: %s" % note.get("run_after"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_evidence_checklist(value: Dict[str, object]) -> List[str]:
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    if not items:
        return ["- 证据清单: 暂无。"]
    lines = ["- 证据清单: %s" % (value.get("summary") or "暂无。")]
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "   #%s %s | %s | %s"
            % (
                item.get("rank"),
                item.get("title"),
                label(item.get("item_type")),
                item.get("coverage_label") or item.get("coverage_status") or "",
            )
        )
        symbols = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        if symbols:
            lines.append("      标的: %s" % "、".join(str(symbol) for symbol in symbols[:5]))
        if item.get("question"):
            lines.append("      问题: %s" % item.get("question"))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("      已有: %s" % "；".join(str(row) for row in evidence[:3]))
        missing = item.get("missing_evidence", []) if isinstance(item.get("missing_evidence"), list) else []
        if missing:
            lines.append("      待补: %s" % "；".join(str(row) for row in missing[:3]))
        if item.get("json_command"):
            lines.append("      命令: %s" % item.get("json_command"))
        note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
        if note.get("prefilled_note_command"):
            lines.append("      记录: %s" % note.get("prefilled_note_command"))
            if note.get("run_after"):
                lines.append("      记录前置: %s" % note.get("run_after"))
        if item.get("done_when"):
            lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_hypothesis_board(value: Dict[str, object]) -> List[str]:
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    if not items:
        return ["- 观察假设: 暂无。"]
    lines = ["- 观察假设: %s" % (value.get("summary") or "暂无。")]
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "   #%s %s | %s | 置信 %s"
            % (
                item.get("rank"),
                item.get("hypothesis"),
                label(item.get("item_type")),
                item.get("confidence") or "",
            )
        )
        symbols = item.get("related_symbols", []) if isinstance(item.get("related_symbols"), list) else []
        if symbols:
            lines.append("      标的: %s" % "、".join(str(symbol) for symbol in symbols[:5]))
        if item.get("why_it_matters"):
            lines.append("      意义: %s" % item.get("why_it_matters"))
        supporting = item.get("supporting_evidence", []) if isinstance(item.get("supporting_evidence"), list) else []
        if supporting:
            lines.append("      支持: %s" % "；".join(str(row) for row in supporting[:3]))
        weak = item.get("weak_points", []) if isinstance(item.get("weak_points"), list) else []
        if weak:
            lines.append("      薄弱: %s" % "；".join(str(row) for row in weak[:3]))
        if item.get("validation_step"):
            lines.append("      验证: %s" % item.get("validation_step"))
        if item.get("invalidation_signal"):
            lines.append("      失效: %s" % item.get("invalidation_signal"))
        if item.get("json_command"):
            lines.append("      命令: %s" % item.get("json_command"))
        note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
        if note.get("prefilled_note_command"):
            lines.append("      记录: %s" % note.get("prefilled_note_command"))
            if note.get("run_after"):
                lines.append("      记录前置: %s" % note.get("run_after"))
        if item.get("done_when"):
            lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_followup_watch(value: Dict[str, object]) -> List[str]:
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    if not items:
        return ["- 下次观察: 暂无。"]
    lines = ["- 下次观察: %s" % (value.get("summary") or "暂无。")]
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        lines.append("   #%s %s | %s" % (item.get("rank"), item.get("title"), label(item.get("item_type"))))
        if item.get("reason"):
            lines.append("      原因: %s" % item.get("reason"))
        symbols = item.get("symbols", []) if isinstance(item.get("symbols"), list) else []
        if symbols:
            lines.append("      标的: %s" % "、".join(str(symbol) for symbol in symbols[:6]))
        if item.get("check_question"):
            lines.append("      问题: %s" % item.get("check_question"))
        if item.get("json_command"):
            lines.append("      命令: %s" % item.get("json_command"))
        note = item.get("journal_note", {}) if isinstance(item.get("journal_note"), dict) else {}
        if note.get("prefilled_note_command"):
            lines.append("      记录: %s" % note.get("prefilled_note_command"))
            if note.get("run_after"):
                lines.append("      记录前置: %s" % note.get("run_after"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_review_completion(value: Dict[str, object]) -> List[str]:
    checks = value.get("checks", []) if isinstance(value.get("checks"), list) else []
    if not checks:
        return ["- 复盘收尾: 暂无。"]
    lines = ["- 复盘收尾: %s" % (value.get("summary") or "暂无。")]
    lines.append(
        "   状态: %s | 可记录: %s | 阻塞 %s | 需人工 %s | 待读 %s"
        % (
            value.get("completion_state"),
            "是" if value.get("ready_for_journal_note") else "否",
            value.get("blocking_count", 0),
            value.get("manual_required_count", 0),
            value.get("pending_count", 0),
        )
    )
    for item in checks[:6]:
        if not isinstance(item, dict):
            continue
        lines.append("   #%s %s | %s" % (item.get("check_id"), item.get("title"), item.get("status")))
        if item.get("reason"):
            lines.append("      原因: %s" % item.get("reason"))
        if item.get("json_command"):
            lines.append("      命令: %s" % item.get("json_command"))
        if item.get("done_when"):
            lines.append("      完成: %s" % item.get("done_when"))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_review_handoff(value: Dict[str, object]) -> List[str]:
    if not value.get("available"):
        return ["- 复盘交接: 暂无。"]
    lines = ["- 复盘交接: %s" % (value.get("summary") or "暂无。")]
    if value.get("resume_prompt"):
        lines.append("   接手提示: %s" % value.get("resume_prompt"))
    next_read = value.get("next_read", []) if isinstance(value.get("next_read"), list) else []
    if next_read:
        lines.append("   待读:")
        for item in next_read[:4]:
            if isinstance(item, dict):
                lines.append("      #%s %s | %s" % (item.get("rank"), item.get("title"), item.get("json_command")))
    manual = value.get("manual_items", []) if isinstance(value.get("manual_items"), list) else []
    if manual:
        lines.append("   人工:")
        for item in manual[:4]:
            if isinstance(item, dict):
                lines.append("      #%s %s | %s" % (item.get("rank"), item.get("title"), item.get("json_command")))
    records = value.get("record_templates", []) if isinstance(value.get("record_templates"), list) else []
    if records:
        lines.append("   记录模板:")
        for item in records[:3]:
            if isinstance(item, dict):
                lines.append("      #%s %s | %s" % (item.get("rank"), item.get("section"), item.get("prefilled_note_command")))
    watches = value.get("watch_items", []) if isinstance(value.get("watch_items"), list) else []
    if watches:
        lines.append("   下次观察:")
        for item in watches[:3]:
            if isinstance(item, dict):
                symbols = item.get("symbols", []) if isinstance(item.get("symbols"), list) else []
                lines.append("      #%s %s | %s | %s" % (
                    item.get("rank"),
                    item.get("title"),
                    "、".join(str(symbol) for symbol in symbols[:5]) or "暂无标的",
                    item.get("check_question") or "",
                ))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_holding_dashboard(value: Dict[str, object]) -> List[str]:
    lines = ["- 持仓仪表盘: %s" % (value.get("summary") or "暂无。")]
    buckets = value.get("buckets", {}) if isinstance(value.get("buckets"), dict) else {}
    if buckets:
        lines.append(
            "   分布: 重点 %s | 中等 %s | 常规 %s | 变化 %s | 缺行情 %s | 缺热点 %s | 主题重叠 %s | 基础/草稿 %s"
            % (
                buckets.get("high_review", 0),
                buckets.get("medium_review", 0),
                buckets.get("normal_review", 0),
                value.get("changed_holding_count", 0),
                buckets.get("missing_quote", 0),
                buckets.get("without_hotspot", 0),
                buckets.get("with_overlap", 0),
                buckets.get("foundation_coverage", 0) + buckets.get("draft_coverage", 0),
            )
        )
    holdings = value.get("top_holdings", []) if isinstance(value.get("top_holdings"), list) else []
    for item in holdings[:3]:
        if not isinstance(item, dict):
            continue
        quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
        hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
        quote_text = "无行情" if not quote else "涨幅 %s | 量比 %s | 回落 %s" % (
            quote.get("change_pct"),
            quote.get("amount_ratio"),
            quote.get("intraday_fade_pct"),
        )
        hotspot_text = hotspot.get("chain") if hotspot else "无热点上下文"
        lines.append(
            "   %s %s | %s | 分 %s | %s | %s"
            % (
                item.get("symbol"),
                item.get("name") or "",
                item.get("priority"),
                item.get("review_score"),
                quote_text,
                hotspot_text,
            )
        )
        change = item.get("change", {}) if isinstance(item.get("change"), dict) else {}
        reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
        if reasons:
            lines.append("      变化: %s" % "；".join(str(reason) for reason in reasons[:4]))
        coverage_state = item.get("coverage_state")
        if coverage_state and coverage_state != "confirmed":
            coverage_reasons = item.get("coverage_state_reasons", []) if isinstance(item.get("coverage_state_reasons"), list) else []
            reason_text = " | 原因: %s" % render_labels(coverage_reasons) if coverage_reasons else ""
            lines.append("      覆盖: %s%s" % (label(coverage_state), reason_text))
        research_text = render_research_status(item.get("research_status", {}))
        if research_text:
            lines.append("      研究: %s" % research_text)
        if item.get("primary_question"):
            lines.append("      问题: %s" % item.get("primary_question"))
        if item.get("primary_json_command") or item.get("primary_command"):
            lines.append("      命令: %s" % (item.get("primary_json_command") or item.get("primary_command")))
    questions = value.get("questions", []) if isinstance(value.get("questions"), list) else []
    for question in questions[:2]:
        lines.append("   核对: %s" % question)
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def render_agent_run_data_repair_plan(value: Dict[str, object]) -> List[str]:
    lines = ["- 数据修复计划: %s" % (value.get("summary") or "暂无。")]
    groups = value.get("groups", []) if isinstance(value.get("groups"), list) else []
    for group in groups[:3]:
        if not isinstance(group, dict):
            continue
        symbols = group.get("symbols", []) if isinstance(group.get("symbols"), list) else []
        lines.append(
            "   %s | %s 个 | %s"
            % (
                repair_type_label_text(group.get("repair_type")),
                group.get("count", 0),
                "、".join(str(symbol) for symbol in symbols[:5]) or "无 symbol",
            )
        )
    items = value.get("items", []) if isinstance(value.get("items"), list) else []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        lines.append("   处理: %s | %s" % (item.get("title"), item.get("repair_hint")))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("      命令: %s" % "；".join(str(command) for command in commands[:2]))
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    return lines


def repair_type_label_text(value: object) -> str:
    labels = {
        "missing_quote_data": "缺行情",
        "quote_not_in_holdings": "行情不在持仓",
        "missing_fields": "缺字段",
        "duplicate_symbol": "重复 symbol",
        "invalid_runtime_file": "runtime 文件异常",
        "pool_mismatch": "池子不匹配",
        "runtime_validation": "runtime 校验",
    }
    return labels.get(str(value), str(value))


def render_agent_run_journal_draft(value: Dict[str, object]) -> List[str]:
    sections = value.get("sections", []) if isinstance(value.get("sections"), list) else []
    if not sections:
        return ["- 留档草稿: 暂无。"]
    lines = ["- 留档草稿: %s" % (value.get("summary") or "仅生成草稿，不自动写入。")]
    if value.get("write_policy"):
        lines.append("   策略: %s" % value.get("write_policy"))
    prereq = value.get("archive_prerequisite", {}) if isinstance(value.get("archive_prerequisite"), dict) else {}
    if prereq.get("archive_command"):
        lines.append("   前置: %s" % prereq.get("archive_command"))
    for section in sections[:5]:
        if not isinstance(section, dict):
            continue
        lines.append("   %s: %s" % (section.get("title"), section.get("draft_text")))
        if section.get("prefilled_note_command"):
            lines.append("      预填命令: %s" % section.get("prefilled_note_command"))
        if section.get("run_after"):
            lines.append("      前置: %s" % section.get("run_after"))
        if section.get("note_command_template"):
            lines.append("      记录命令: %s" % section.get("note_command_template"))
    return lines


def render_agent_run_security_workbench(value: List[object]) -> List[str]:
    lines = ["- 单票工作台:"]
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "   #%s %s %s | %s | 分 %s"
            % (item.get("rank"), item.get("symbol"), item.get("name") or "", item.get("severity"), item.get("priority_score"))
        )
        if item.get("review_reason"):
            lines.append("      原因: %s" % item.get("review_reason"))
        change = item.get("change", {}) if isinstance(item.get("change"), dict) else {}
        reasons = change.get("reasons", []) if isinstance(change.get("reasons"), list) else []
        if reasons:
            lines.append("      变化: %s" % "；".join(str(reason) for reason in reasons[:4]))
        groups = item.get("exposure_groups", []) if isinstance(item.get("exposure_groups"), list) else []
        if groups:
            lines.append("      暴露: %s" % "；".join(render_security_workbench_group(group) for group in groups[:3] if isinstance(group, dict)))
        if item.get("primary_command"):
            lines.append("      命令: %s" % item.get("primary_command"))
        prereq = item.get("note_prerequisite", {}) if isinstance(item.get("note_prerequisite"), dict) else {}
        if item.get("note_command"):
            prefix = "需先留档" if prereq.get("requires_journal_entry") else "可记录"
            lines.append("      记录: %s | %s" % (prefix, item.get("note_command")))
    return lines


def render_security_workbench_group(value: Dict[str, object]) -> str:
    group_type = {"chain": "链路", "theme": "主题"}.get(str(value.get("group_type")), label(value.get("group_type")))
    peers = value.get("peer_symbols", []) if isinstance(value.get("peer_symbols"), list) else []
    suffix = " | 同组 %s" % "、".join(str(symbol) for symbol in peers[:4]) if peers else ""
    return "%s %s%s" % (group_type, value.get("group"), suffix)


def render_agent_run_change_tracking(value: Dict[str, object]) -> List[str]:
    lines = ["- 变化跟踪:"]
    history = value.get("history", {}) if isinstance(value.get("history"), dict) else {}
    if history:
        lines.append(
            "   留档: %s/%s | 可对比 %s"
            % (history.get("count", 0), history.get("total_count", 0), "是" if history.get("can_compare") else "否")
        )
        latest_note = history.get("latest_note", {}) if isinstance(history.get("latest_note"), dict) else {}
        if latest_note:
            lines.append("   最近笔记: %s | %s" % (latest_note.get("section") or "general", trim_text(latest_note.get("text"), 80)))
    transition = value.get("history_transition", {}) if isinstance(value.get("history_transition"), dict) else {}
    current = value.get("current_vs_latest", {}) if isinstance(value.get("current_vs_latest"), dict) else {}
    if transition.get("available"):
        lines.append("   历史转折: %s" % (transition.get("summary") or "暂无摘要。"))
        lines.extend(render_agent_run_change_counts(transition))
    elif current.get("available"):
        lines.append("   当前对比: %s" % (current.get("summary") or "暂无摘要。"))
        lines.extend(render_agent_run_change_counts(current))
    else:
        lines.append("   暂无可用变化对比。")
    return lines


def render_agent_run_change_counts(value: Dict[str, object]) -> List[str]:
    risk = value.get("risk_flags", {}) if isinstance(value.get("risk_flags"), dict) else {}
    watchlist = value.get("watchlist", {}) if isinstance(value.get("watchlist"), dict) else {}
    portfolio = value.get("portfolio_review", {}) if isinstance(value.get("portfolio_review"), dict) else {}
    hotspots = value.get("hotspots", {}) if isinstance(value.get("hotspots"), dict) else {}
    validation = value.get("validation", {}) if isinstance(value.get("validation"), dict) else {}
    lines = [
        "   变化: 风险 +%s/-%s | 观察 +%s/-%s/~%s | 持仓复核 +%s/-%s/~%s | 热点 +%s/-%s/~%s | 告警 %+s | 错误 %+s"
        % (
            risk.get("added_count", 0),
            risk.get("removed_count", 0),
            watchlist.get("added_count", 0),
            watchlist.get("removed_count", 0),
            watchlist.get("changed_count", 0),
            portfolio.get("added_count", 0),
            portfolio.get("removed_count", 0),
            portfolio.get("changed_count", 0),
            hotspots.get("added_count", 0),
            hotspots.get("removed_count", 0),
            hotspots.get("changed_count", 0),
            validation.get("warning_delta", 0),
            validation.get("error_delta", 0),
        )
    ]
    top = hotspots.get("top", {}) if isinstance(hotspots.get("top"), dict) else {}
    base = top.get("base", {}) if isinstance(top.get("base"), dict) else {}
    current = top.get("current", {}) if isinstance(top.get("current"), dict) else {}
    if base or current:
        lines.append("   最强链路: %s -> %s" % (base.get("key") or "无", current.get("key") or "无"))
    changed_symbols = portfolio.get("changed_symbols", []) if isinstance(portfolio.get("changed_symbols"), list) else []
    if changed_symbols:
        lines.append("   持仓变化: %s" % "、".join(str(symbol) for symbol in changed_symbols[:5]))
    return lines


def render_agent_run_results(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无已运行步骤。"]
    lines = []
    for item in rows[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- #%s %s | %s | %s"
            % (
                item.get("run_rank"),
                "ok" if item.get("ok") else "error",
                item.get("json_command") or item.get("command"),
                item.get("summary") or "",
            )
        )
        observations = item.get("observations", []) if isinstance(item.get("observations"), list) else []
        for observation in observations[:4]:
            lines.append("   观察: %s" % observation)
        errors = item.get("errors", []) if isinstance(item.get("errors"), list) else []
        if errors:
            lines.append("   错误: %s" % "；".join(str(issue) for issue in errors[:4]))
    return lines or ["- 暂无已运行步骤。"]


def render_agent_run_skipped(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无跳过步骤。"]
    lines = []
    for item in rows[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- #%s %s | %s"
            % (
                item.get("run_rank"),
                item.get("json_command") or item.get("command"),
                item.get("reason") or "已跳过。",
            )
        )
    return lines or ["- 暂无跳过步骤。"]


def render_agent_run_followups(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无人工后续。"]
    lines = []
    for item in rows[:8]:
        if not isinstance(item, dict):
            continue
        lines.append("- %s | %s" % (item.get("json_command") or item.get("command"), label(item.get("state_effect"))))
        if item.get("requires_prior_command"):
            lines.append("   前置: %s" % item.get("requires_prior_command"))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines or ["- 暂无人工后续。"]


def render_agent_briefing_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel agent briefing\n\n无数据。"
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    readiness = runtime.get("readiness", {}) if isinstance(runtime.get("readiness"), dict) else {}
    daily = data.get("daily", {}) if isinstance(data.get("daily"), dict) else {}
    market_scan = data.get("market_scan", {}) if isinstance(data.get("market_scan"), dict) else {}
    history = data.get("history", {}) if isinstance(data.get("history"), dict) else {}
    current_change = data.get("current_change", {}) if isinstance(data.get("current_change"), dict) else {}
    lines = [
        "market-intel agent briefing",
        "",
        "状态",
        "- %s | %s" % (data.get("state"), data.get("summary")),
        "- runtime: %s | %s" % (readiness.get("state"), readiness.get("reason")),
    ]
    runtime_validation = runtime.get("validation", {}) if isinstance(runtime.get("validation"), dict) else {}
    lines.extend(render_runtime_validation_brief(runtime_validation))
    lines.extend(["", "今日"])
    if not daily.get("available"):
        lines.append("- 暂无可用日报。")
    else:
        validation = daily.get("validation", {}) if isinstance(daily.get("validation"), dict) else {}
        portfolio = daily.get("portfolio_review", {}) if isinstance(daily.get("portfolio_review"), dict) else {}
        watchlist = daily.get("watchlist", {}) if isinstance(daily.get("watchlist"), dict) else {}
        lines.append(
            "- 交易日 %s | 风险 %s | 观察 %s | 持仓复核 %s | 重点复核 %s | 告警 %s"
            % (
                daily.get("trade_date") or "未知",
                len(daily.get("risk_flags", []) if isinstance(daily.get("risk_flags"), list) else []),
                watchlist.get("count", 0),
                portfolio.get("count", 0),
                portfolio.get("high_review_count", 0),
                validation.get("warning_count", 0),
            )
        )
        lines.extend(render_briefing_data_quality(validation))
        lines.extend(render_briefing_hotspots(daily.get("top_hotspots", [])))
        lines.extend(render_briefing_watchlist(watchlist.get("top_items", []) if isinstance(watchlist, dict) else []))
        lines.extend(render_briefing_portfolio(portfolio.get("top_items", []) if isinstance(portfolio, dict) else []))

    lines.extend(["", "全市场扫描"])
    lines.extend(render_briefing_market_scan(market_scan))
    lines.extend(["", "组合暴露"])
    lines.extend(render_portfolio_exposure(daily.get("portfolio_exposure", {}) if isinstance(daily, dict) else {}))
    lines.extend(["", "复盘路径"])
    lines.extend(render_review_path(daily.get("review_path", []) if isinstance(daily, dict) else []))
    lines.extend(["", "风险登记"])
    lines.extend(render_risk_register(daily.get("risk_register", []) if isinstance(daily, dict) else [], daily.get("risk_flags", []) if isinstance(daily, dict) else []))
    lines.extend(["", "标的复核队列"])
    lines.extend(render_security_review_queue(data.get("security_review_queue", [])))
    lines.extend(["", "标的风险画像"])
    lines.extend(render_security_risk_profile(daily.get("security_risk_profile", []) if isinstance(daily, dict) else []))
    lines.extend(["", "复核焦点"])
    lines.extend(render_briefing_focus(data.get("review_focus", [])))
    lines.extend(["", "复核清单"])
    lines.extend(render_briefing_checklist(data.get("review_checklist", [])))
    lines.extend(["", "当前变化"])
    lines.extend(render_briefing_current_change(current_change))
    lines.extend(["", "历史"])
    lines.extend(render_briefing_history(history))
    lines.extend(["", "问题"])
    lines.extend(render_list(data.get("questions", []), empty="暂无问题。"))
    lines.extend(["", "留档提示"])
    lines.extend(render_journal_prompt(data.get("journal_prompt", {})))
    lines.extend(["", "命令队列"])
    lines.extend(render_briefing_command_queue(data.get("command_queue", [])))
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_journal_list_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel journal list\n\n无数据。"
    lines = [
        "market-intel journal list",
        "",
        "总览",
        "- 条目 %s/%s | 目录 %s" % (data.get("count"), data.get("total_count"), data.get("journal_dir")),
        "",
        "历史",
    ]
    entries = data.get("entries", [])
    if not isinstance(entries, list) or not entries:
        lines.append("- 暂无日报留档。")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            lines.append(
                "- %s | %s | 风险 %s | 观察 %s | %s"
                % (
                    entry.get("id"),
                    entry.get("trade_date") or "无交易日",
                    len(entry.get("risk_flags", [])) if isinstance(entry.get("risk_flags"), list) else 0,
                    entry.get("watchlist_count"),
                    entry.get("summary"),
                )
            )
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_journal_entry_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel journal entry\n\n无数据。"
    if not data.get("found"):
        lines = ["market-intel journal entry", "", "状态", "- 未找到。", "", "下一步"]
        lines.extend(render_command_list(data.get("next_commands", [])))
        return "\n".join(lines)
    entry = data.get("entry", {}) if isinstance(data.get("entry"), dict) else {}
    lines = [
        "market-intel journal entry",
        "",
        "条目",
        "- %s | %s | %s" % (entry.get("id"), entry.get("trade_date") or "无交易日", entry.get("generated_at")),
        "",
        "摘要",
        str(entry.get("summary") or "暂无。"),
        "",
        "风险",
    ]
    lines.extend(render_list(entry.get("risk_flags", []), empty="暂无风险标签。"))
    lines.extend(["", "文件", "- %s" % entry.get("path")])
    lines.extend(["", "复盘笔记"])
    lines.extend(render_journal_notes(data.get("notes", [])))
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_journal_notes(value: object) -> List[str]:
    notes = value if isinstance(value, list) else []
    if not notes:
        return ["- 暂无复盘笔记。"]
    lines = []
    for note in notes[-3:]:
        if not isinstance(note, dict):
            continue
        lines.append(
            "- %s | %s | %s"
            % (
                note.get("created_at"),
                note.get("section") or "general",
                trim_text(note.get("text"), 180),
            )
        )
    return lines or ["- 暂无复盘笔记。"]


def render_journal_notes_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel journal notes\n\n无数据。"
    lines = [
        "market-intel journal notes",
        "",
        "总览",
        "- 笔记 %s/%s | 目录 %s" % (data.get("count", 0), data.get("total_count", 0), data.get("journal_dir")),
    ]
    filters = data.get("filters", {}) if isinstance(data.get("filters"), dict) else {}
    active_filters = render_note_filters(filters)
    if active_filters:
        lines.append("- 筛选: %s" % active_filters)
    lines.extend(["", "笔记"])
    notes = data.get("notes", []) if isinstance(data.get("notes"), list) else []
    if not notes:
        lines.append("- 暂无复盘笔记。")
    else:
        for note in notes:
            if not isinstance(note, dict):
                continue
            lines.append(
                "- %s | %s | %s | %s | %s"
                % (
                    note.get("created_at"),
                    note.get("trade_date") or "无交易日",
                    note.get("section") or "general",
                    note.get("entry_id"),
                    trim_text(note.get("text"), 220),
                )
            )
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_note_filters(filters: Dict[str, object]) -> str:
    parts = []
    if filters.get("section"):
        parts.append("section=%s" % filters.get("section"))
    if filters.get("query"):
        parts.append("query=%s" % filters.get("query"))
    return " | ".join(parts)


def render_journal_compare_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel journal compare\n\n无数据。"
    if not data.get("found"):
        lines = ["market-intel journal compare", "", "状态", "- 暂无可对比留档。", "", "下一步"]
        lines.extend(render_command_list(data.get("next_commands", [])))
        return "\n".join(lines)

    base_entry = data.get("base_entry", {}) if isinstance(data.get("base_entry"), dict) else {}
    current_entry = data.get("current_entry", {}) if isinstance(data.get("current_entry"), dict) else {}
    changes = data.get("changes", {}) if isinstance(data.get("changes"), dict) else {}
    risk_flags = changes.get("risk_flags", {}) if isinstance(changes.get("risk_flags"), dict) else {}
    watchlist = changes.get("watchlist", {}) if isinstance(changes.get("watchlist"), dict) else {}
    portfolio_review = changes.get("portfolio_review", {}) if isinstance(changes.get("portfolio_review"), dict) else {}
    hotspots = changes.get("hotspots", {}) if isinstance(changes.get("hotspots"), dict) else {}
    validation = changes.get("validation", {}) if isinstance(changes.get("validation"), dict) else {}
    lines = [
        "market-intel journal compare",
        "",
        "条目",
        "- base: %s | %s" % (base_entry.get("id"), base_entry.get("trade_date") or "无交易日"),
        "- current: %s | %s" % (current_entry.get("id"), current_entry.get("trade_date") or "无交易日"),
        "",
        "总览",
        str(data.get("summary") or "暂无摘要。"),
        "",
        "风险变化",
    ]
    lines.extend(render_added_removed_labels(risk_flags, empty="风险标签无新增或减少。"))
    lines.extend(["", "观察项变化"])
    lines.extend(render_watchlist_compare(watchlist))
    lines.extend(["", "持仓复核变化"])
    lines.extend(render_portfolio_compare(portfolio_review))
    lines.extend(["", "热点变化"])
    lines.extend(render_hotspot_compare(hotspots))
    lines.extend(["", "数据检查变化"])
    lines.extend(render_validation_compare(validation))
    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_journal_timeline_text(payload: Dict[str, object]) -> str:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "market-intel journal timeline\n\n无数据。"

    lines = [
        "market-intel journal timeline",
        "",
        "总览",
        "- %s" % (data.get("summary") or "暂无历史摘要。"),
        "",
        "时间线",
    ]
    points = data.get("points", []) if isinstance(data.get("points"), list) else []
    if not points:
        lines.append("- 暂无日报留档。")
    else:
        for point in points:
            if not isinstance(point, dict):
                continue
            portfolio = point.get("portfolio_review", {}) if isinstance(point.get("portfolio_review"), dict) else {}
            validation = point.get("validation", {}) if isinstance(point.get("validation"), dict) else {}
            lines.append(
                "- %s | %s | %s | 风险 %s | 观察 %s | 重点复核 %s | 告警 %s"
                % (
                    point.get("trade_date") or "无交易日",
                    point.get("entry_id"),
                    render_timeline_hotspot(point.get("top_hotspot")),
                    point.get("risk_count", 0),
                    point.get("watchlist_count", 0),
                    portfolio.get("high_review_count", 0),
                    validation.get("warning_count", 0),
                )
            )
            top_items = portfolio.get("top_items", []) if isinstance(portfolio.get("top_items"), list) else []
            if top_items:
                lines.append("   持仓: %s" % render_timeline_portfolio_items(top_items))
            latest_note = point.get("latest_note", {}) if isinstance(point.get("latest_note"), dict) else {}
            if latest_note:
                lines.append(
                    "   笔记: %s | %s"
                    % (latest_note.get("section") or "general", trim_text(latest_note.get("text"), 120))
                )

    lines.extend(["", "转折"])
    transitions = data.get("transitions", []) if isinstance(data.get("transitions"), list) else []
    if not transitions:
        lines.append("- 暂无转折；至少需要两份日报留档。")
    else:
        for item in transitions:
            if not isinstance(item, dict):
                continue
            risk_flags = item.get("risk_flags", {}) if isinstance(item.get("risk_flags"), dict) else {}
            watchlist = item.get("watchlist", {}) if isinstance(item.get("watchlist"), dict) else {}
            portfolio = item.get("portfolio_review", {}) if isinstance(item.get("portfolio_review"), dict) else {}
            hotspots = item.get("hotspots", {}) if isinstance(item.get("hotspots"), dict) else {}
            validation = item.get("validation", {}) if isinstance(item.get("validation"), dict) else {}
            lines.append(
                "- %s -> %s | 风险 %s | 观察 %s | 持仓复核 %s | 热点 %s | 告警 %+s | 错误 %+s"
                % (
                    item.get("base_trade_date") or item.get("base_entry_id"),
                    item.get("current_trade_date") or item.get("current_entry_id"),
                    render_added_removed_counts(risk_flags),
                    render_collection_counts(watchlist),
                    render_collection_counts(portfolio),
                    render_collection_counts(hotspots),
                    validation.get("warning_delta", 0),
                    validation.get("error_delta", 0),
                )
            )
            if item.get("compare_command"):
                lines.append("   深入: %s" % item.get("compare_command"))

    lines.extend(["", "下一步"])
    lines.extend(render_command_list(data.get("next_commands", [])))
    return "\n".join(lines)


def render_exposures(value: object) -> List[str]:
    exposures = value if isinstance(value, list) else []
    if not exposures:
        return ["- 暂无链路暴露。"]
    lines = []
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        lines.append(
            "- %s / %s | 角色 %s | %s"
            % (
                exposure.get("layer"),
                exposure.get("sub_sector"),
                exposure.get("role") or "待确认",
                exposure.get("logic") or "",
            )
        )
    return lines or ["- 暂无链路暴露。"]


def render_runtime_context(value: object) -> List[str]:
    context = value if isinstance(value, dict) else {}
    if not context:
        return ["- 未加载 runtime。"]
    lines = []
    quote = context.get("quote")
    if isinstance(quote, dict):
        lines.append(
            "- 行情: %+s%% | 成交放大 %s | 回落 %s%% | 来源 %s"
            % (
                quote.get("change_pct"),
                quote.get("amount_ratio"),
                quote.get("intraday_fade_pct"),
                quote.get("source"),
            )
        )
    else:
        lines.append("- 行情: runtime 中未找到。")
    holding = context.get("holding")
    if isinstance(holding, dict):
        lines.append("- 持仓: 是 | 数量 %s | 来源 %s" % (holding.get("quantity"), holding.get("source")))
    else:
        lines.append("- 持仓: 否。")
    return lines


def render_hotspots(value: object) -> List[str]:
    hotspots = value if isinstance(value, list) else []
    if not hotspots:
        return ["- 暂无热点。"]
    lines = []
    for idx, hotspot in enumerate(hotspots, start=1):
        if not isinstance(hotspot, dict):
            continue
        leaders = hotspot.get("leaders", [])
        leader_text = render_leaders(leaders if isinstance(leaders, list) else [])
        lines.append(
            "%s. %s / %s | 热点 %s | 活跃 %s/%s | %s"
            % (
                idx,
                hotspot.get("layer"),
                hotspot.get("sub_sector"),
                hotspot.get("score"),
                hotspot.get("active_member_count"),
                hotspot.get("member_count"),
                leader_text,
            )
        )
        signals = hotspot.get("signals") or []
        risks = hotspot.get("risks") or []
        if signals:
            lines.append("   信号: %s" % render_labels(signals))
        if risks:
            lines.append("   风险: %s" % render_labels(risks))
    return lines or ["- 暂无热点。"]


def render_holding_impact(value: object) -> List[str]:
    impact = value if isinstance(value, dict) else {}
    lines = []
    repeated = impact.get("repeated_exposures") or []
    repeated_groups = impact.get("repeated_overlap_groups") or []
    if repeated:
        lines.append("- 重复链路: %s" % render_group_counts(repeated))
    if repeated_groups:
        lines.append("- 重复主题: %s" % render_group_counts(repeated_groups))
    impacts = impact.get("impacts", [])
    if isinstance(impacts, list):
        for item in impacts[:8]:
            if not isinstance(item, dict):
                continue
            risk_flags = item.get("impact", {}).get("risk_flags", []) if isinstance(item.get("impact"), dict) else []
            lines.append(
                "- %s %s | 暴露 %s | 风险 %s"
                % (
                    item.get("holding_symbol"),
                    item.get("holding_name"),
                    len(item.get("exposures", [])),
                    render_labels(risk_flags) if risk_flags else "无",
                )
            )
    return lines or ["- 暂无持仓暴露数据。"]


def render_watchlist(value: object) -> List[str]:
    watchlist = value if isinstance(value, list) else []
    if not watchlist:
        return ["- 暂无观察项。"]
    lines = []
    for item in watchlist[:10]:
        if not isinstance(item, dict):
            continue
        holding_mark = "持仓" if item.get("is_holding") else "观察"
        lines.append(
            "- %s %s | %s / %s | %+s%% | %s | %s"
            % (
                item.get("symbol"),
                item.get("name"),
                item.get("layer"),
                item.get("sub_sector"),
                item.get("change_pct"),
                holding_mark,
                label(item.get("reason")),
            )
        )
    return lines or ["- 暂无观察项。"]


def render_portfolio_item(item: Dict[str, object]) -> List[str]:
    quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
    hotspot = item.get("hotspot_context", {}) if isinstance(item.get("hotspot_context"), dict) else {}
    quote_text = "无行情"
    if quote:
        quote_text = "涨幅 %+s%% | 成交放大 %s | 回落 %s%%" % (
            quote.get("change_pct"),
            quote.get("amount_ratio"),
            quote.get("intraday_fade_pct"),
        )
    hotspot_text = "无热点上下文"
    if hotspot:
        hotspot_text = "%s / %s | 热点 %s" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score"))
    lines = [
        "- %s %s | %s | 优先级 %s | %s | %s"
        % (
            item.get("symbol"),
            item.get("name"),
            label(item.get("priority")),
            item.get("priority_score"),
            quote_text,
            hotspot_text,
        )
    ]
    risks = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
    if risks:
        lines.append("   风险: %s" % render_labels(risks))
    coverage_state = item.get("coverage_state")
    if coverage_state and coverage_state != "confirmed":
        reasons = item.get("coverage_state_reasons", []) if isinstance(item.get("coverage_state_reasons"), list) else []
        reason_text = " | 原因: %s" % render_labels(reasons) if reasons else ""
        lines.append("   覆盖: %s%s" % (label(coverage_state), reason_text))
    research_text = render_research_status(item.get("research_status", {}))
    if research_text:
        lines.append("   研究: %s" % research_text)
    exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
    if exposures:
        lines.append("   链路: %s" % render_portfolio_exposures(exposures))
    review_points = item.get("review_points", []) if isinstance(item.get("review_points"), list) else []
    if review_points:
        lines.append("   复核: %s" % "；".join(str(point) for point in review_points[:3]))
    return lines


def render_portfolio_exposures(value: object) -> str:
    exposures = value if isinstance(value, list) else []
    parts = []
    for exposure in exposures[:4]:
        if not isinstance(exposure, dict):
            continue
        role = exposure.get("role") or "待确认"
        parts.append("%s/%s(%s)" % (exposure.get("layer"), exposure.get("sub_sector"), role))
    return "；".join(parts) if parts else "无"


def render_portfolio_repeated_exposure_detail(value: object) -> List[str]:
    portfolio = value if isinstance(value, dict) else {}
    items = portfolio.get("items", []) if isinstance(portfolio.get("items"), list) else []
    repeated = portfolio.get("repeated_exposures", []) if isinstance(portfolio.get("repeated_exposures"), list) else []
    overlap = (
        portfolio.get("repeated_overlap_groups", [])
        if isinstance(portfolio.get("repeated_overlap_groups"), list)
        else []
    )
    lines = []
    if repeated:
        lines.append("- 重复链路: %s" % render_portfolio_exposure_groups(repeated, items, "exposure"))
    if overlap:
        lines.append("- 重复主题: %s" % render_portfolio_exposure_groups(overlap, items, "overlap"))
    return lines or ["- 暂无重复链路或重复主题暴露。"]


def render_portfolio_exposure_groups(groups: Iterable[object], items: List[object], group_type: str) -> str:
    parts = []
    for group in groups:
        if not isinstance(group, dict) or not group.get("group"):
            continue
        group_name = str(group.get("group"))
        holdings = holdings_for_text_exposure_group(group_name, items, group_type)
        holding_count = int_or_default(group.get("holding_count"), len(holdings))
        holding_text = ", ".join(render_portfolio_exposure_holding(item) for item in holdings[:4])
        if holding_count > len(holdings):
            hidden_count = holding_count - len(holdings)
            if holding_text:
                holding_text = "%s，另有 %s 个未在当前输出持仓中" % (holding_text, hidden_count)
            else:
                holding_text = "当前输出未展开持仓明细"
        parts.append("%s(%s): %s" % (group_name, holding_count, holding_text or "无明细"))
    return "；".join(parts) if parts else "无"


def holdings_for_text_exposure_group(group_name: str, items: List[object], group_type: str) -> List[Dict[str, object]]:
    holdings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if group_type == "exposure" and not item_in_text_exposure_group(item, group_name):
            continue
        if group_type == "overlap" and not item_in_text_overlap_group(item, group_name):
            continue
        holdings.append(item)
    holdings.sort(key=lambda item: (-float_or_default(item.get("priority_score"), 0.0), str(item.get("symbol") or "")))
    return holdings


def item_in_text_exposure_group(item: Dict[str, object], group_name: str) -> bool:
    exposures = item.get("exposures", []) if isinstance(item.get("exposures"), list) else []
    for exposure in exposures:
        if not isinstance(exposure, dict):
            continue
        if "%s/%s" % (exposure.get("layer"), exposure.get("sub_sector")) == group_name:
            return True
    return False


def item_in_text_overlap_group(item: Dict[str, object], group_name: str) -> bool:
    groups = item.get("overlap_groups", []) if isinstance(item.get("overlap_groups"), list) else []
    return group_name in [str(group) for group in groups if group]


def render_portfolio_exposure_holding(item: Dict[str, object]) -> str:
    name = " %s" % item.get("name") if item.get("name") else ""
    text = "%s%s" % (item.get("symbol"), name)
    labels = []
    if item.get("priority"):
        labels.append(label(item.get("priority")))
    if item.get("priority_score") is not None:
        labels.append("复核分 %s" % item.get("priority_score"))
    return "%s[%s]" % (text, "/".join(labels)) if labels else text


def render_related_holdings(value: object) -> List[str]:
    related = value if isinstance(value, dict) else {}
    lines = []
    same_exposure = related.get("same_exposure", []) if isinstance(related.get("same_exposure"), list) else []
    same_overlap_group = related.get("same_overlap_group", []) if isinstance(related.get("same_overlap_group"), list) else []
    if same_exposure:
        lines.append("- 同链路: %s" % render_related_parts(same_exposure))
    if same_overlap_group:
        lines.append("- 同主题: %s" % render_related_parts(same_overlap_group))
    return lines or ["- 暂无相关持仓。"]


def render_related_parts(value: object) -> str:
    rows = value if isinstance(value, list) else []
    parts = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        shared = row.get("shared", []) if isinstance(row.get("shared"), list) else []
        parts.append(
            "%s %s[%s]"
            % (
                row.get("symbol"),
                row.get("name"),
                "/".join(str(item) for item in shared[:2]),
            )
        )
    return "；".join(parts) if parts else "无"


def render_layer_hotspots(value: object) -> str:
    hotspots = value if isinstance(value, list) else []
    parts = []
    for hotspot in hotspots[:3]:
        if not isinstance(hotspot, dict):
            continue
        leaders = hotspot.get("leaders", [])
        parts.append(
            "%s %.2f[%s]"
            % (
                hotspot.get("sub_sector"),
                float(hotspot.get("score") or 0),
                render_leaders(leaders if isinstance(leaders, list) else []),
            )
        )
    return "；".join(parts)


def render_layer_holdings(value: object) -> str:
    holdings = value if isinstance(value, list) else []
    parts = []
    for holding in holdings[:4]:
        if not isinstance(holding, dict):
            continue
        change_pct = holding.get("change_pct")
        change_text = "无行情" if change_pct is None else "%+s%%" % change_pct
        sub_sectors = holding.get("sub_sectors", [])
        sub_sector_text = "/".join(str(item) for item in sub_sectors[:2]) if isinstance(sub_sectors, list) else ""
        parts.append("%s %s %s" % (holding.get("name"), sub_sector_text, change_text))
    return "；".join(parts)


def render_validation_summary(value: object) -> List[str]:
    validation = value if isinstance(value, dict) else {}
    summary = validation.get("summary", {}) if isinstance(validation.get("summary"), dict) else {}
    lines = [
        "- 状态: %s | 行情 %s | 持仓 %s | 错误 %s | 告警 %s"
        % (
            "通过" if validation.get("ok") else "需处理",
            summary.get("quote_count", 0),
            summary.get("holding_count", 0),
            summary.get("error_count", 0),
            summary.get("warning_count", 0),
        )
    ]
    warnings = validation.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.append("   告警: %s" % render_issue_codes(warnings[:5]))
    errors = validation.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.append("   错误: %s" % render_issue_codes(errors[:5]))
    return lines


def render_daily_map_lines(value: object) -> List[str]:
    layers = value if isinstance(value, list) else []
    lines = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        if not layer.get("hotspot_count") and not layer.get("holding_count"):
            continue
        lines.append(
            "- %s | 热点 %s | 持仓 %s | 风险 %s"
            % (
                layer.get("layer"),
                layer.get("hotspot_count"),
                layer.get("holding_count"),
                render_labels(layer.get("risk_flags", [])) if layer.get("risk_flags") else "无",
            )
        )
    return lines or ["- 暂无活跃链路。"]


def render_daily_watchlist_lines(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    lines = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        mark = "持仓" if item.get("is_holding") else "观察"
        lines.append(
            "- %s %s | %s | %s / %s | %+s%% | %s"
            % (
                item.get("symbol"),
                item.get("name"),
                mark,
                item.get("layer"),
                item.get("sub_sector"),
                item.get("change_pct"),
                label(item.get("focus")),
            )
        )
    return lines or ["- 暂无观察项。"]


def render_daily_portfolio_lines(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    lines = []
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
        quote_text = "无行情"
        if quote:
            quote_text = "%+s%% | 回落 %s%%" % (quote.get("change_pct"), quote.get("intraday_fade_pct"))
        lines.append(
            "- %s %s | %s | %s | 风险 %s"
            % (
                item.get("symbol"),
                item.get("name"),
                label(item.get("priority")),
                quote_text,
                render_labels(item.get("risk_flags", [])) if item.get("risk_flags") else "无",
            )
        )
        review_points = item.get("review_points", []) if isinstance(item.get("review_points"), list) else []
        if review_points:
            lines.append("   复核: %s" % str(review_points[0]))
    return lines or ["- 暂无持仓复核项。"]


def render_daily_review_tasks(value: object) -> List[str]:
    tasks = value if isinstance(value, list) else []
    lines = []
    for task in tasks[:6]:
        if not isinstance(task, dict):
            continue
        lines.append(
            "- #%s %s | %s"
            % (
                task.get("priority"),
                task.get("title"),
                task.get("reason"),
            )
        )
        evidence = task.get("evidence", []) if isinstance(task.get("evidence"), list) else []
        if evidence:
            lines.append("   依据: %s" % "；".join(str(item) for item in evidence[:3]))
        commands = task.get("commands", []) if isinstance(task.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if task.get("note_command"):
            lines.append("   记录: %s" % task.get("note_command"))
            prereq = render_note_prerequisite(task.get("note_prerequisite", {}))
            if prereq:
                lines.append("   前置: %s" % prereq)
        if task.get("done_when"):
            lines.append("   完成: %s" % task.get("done_when"))
    return lines or ["- 暂无复核任务。"]


def render_daily_security_queue(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    lines = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
        lines.append(
            "- #%s %s %s | 队列分 %s | 来源 %s"
            % (
                item.get("rank"),
                item.get("symbol"),
                item.get("name") or "",
                item.get("priority_score"),
                render_labels(item.get("sources", [])) if item.get("sources") else "无",
            )
        )
        context_parts = []
        if context.get("is_holding") is not None:
            context_parts.append("持仓" if context.get("is_holding") else "观察")
        if context.get("layer") or context.get("sub_sector"):
            context_parts.append("%s/%s" % (context.get("layer") or "无链路", context.get("sub_sector") or "无子链路"))
        if context.get("change_pct") is not None:
            context_parts.append("涨幅 %+s%%" % context.get("change_pct"))
        if context.get("hotspot_score") is not None:
            context_parts.append("热点 %s" % context.get("hotspot_score"))
        if context_parts:
            lines.append("   上下文: %s" % "；".join(context_parts))
        reasons = item.get("reasons", []) if isinstance(item.get("reasons"), list) else []
        if reasons:
            lines.append("   原因: %s" % "；".join(str(reason) for reason in reasons[:3]))
        risks = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        if risks:
            lines.append("   风险: %s" % render_labels(risks[:5]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if item.get("note_command"):
            lines.append("   记录: %s" % item.get("note_command"))
            prereq = render_note_prerequisite(item.get("note_prerequisite", {}))
            if prereq:
                lines.append("   前置: %s" % prereq)
    return lines or ["- 暂无标的复核队列。"]


def render_note_prerequisite(value: object) -> str:
    prereq = value if isinstance(value, dict) else {}
    if not prereq.get("requires_journal_entry"):
        return ""
    command = prereq.get("archive_command")
    if prereq.get("archive_runnable"):
        return "先执行 %s" % command if command else "先保存日报留档"
    reason = prereq.get("archive_reason") or "需要先接入可保存的数据源。"
    return "先保存日报留档；当前保存命令不可直接执行：%s" % reason


def render_daily_journal_actions(value: object) -> List[str]:
    actions = value if isinstance(value, list) else []
    lines = []
    for action in actions[:5]:
        if not isinstance(action, dict):
            continue
        state = "可执行" if action.get("runnable") else "需接入数据"
        lines.append("- %s | %s | %s" % (action.get("title"), state, action.get("reason")))
        if action.get("command"):
            lines.append("   命令: %s" % action.get("command"))
    return lines or ["- 暂无留档入口。"]


def render_risk_register(value: object, fallback_flags: object = None) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return render_list(fallback_flags if fallback_flags is not None else [], empty="暂无风险标签。")
    lines = []
    for item in rows[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- #%s %s | %s | 涉及 %s"
            % (
                item.get("rank"),
                item.get("label") or item.get("risk_id"),
                render_severity(item.get("severity")),
                item.get("affected_count", 0),
            )
        )
        affected = item.get("affected_symbols", []) if isinstance(item.get("affected_symbols"), list) else []
        if affected:
            lines.append("   标的: %s" % "；".join(str(row) for row in affected[:5]))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("   证据: %s" % "；".join(str(row) for row in evidence[:3]))
        if item.get("review_question"):
            lines.append("   核对: %s" % item.get("review_question"))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines or render_list(fallback_flags if fallback_flags is not None else [], empty="暂无风险标签。")


def render_security_risk_profile(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无标的风险画像。"]
    lines = []
    for item in rows[:6]:
        if not isinstance(item, dict):
            continue
        title = "%s %s" % (item.get("symbol"), item.get("name") or "")
        lines.append(
            "- #%s %s | %s | 复核分 %s"
            % (item.get("rank"), title.strip(), render_severity(item.get("severity")), item.get("priority_score"))
        )
        risks = item.get("risk_ids", []) if isinstance(item.get("risk_ids"), list) else []
        if risks:
            lines.append("   风险: %s" % render_labels(risks[:6]))
        related = item.get("related_risks", []) if isinstance(item.get("related_risks"), list) else []
        if related:
            lines.append(
                "   登记: %s"
                % "；".join(
                    "%s#%s" % (risk.get("label") or risk.get("risk_id"), risk.get("rank"))
                    for risk in related[:4]
                    if isinstance(risk, dict)
                )
            )
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("   证据: %s" % "；".join(str(row) for row in evidence[:2]))
        questions = item.get("review_questions", []) if isinstance(item.get("review_questions"), list) else []
        if questions:
            lines.append("   核对: %s" % "；".join(str(row) for row in questions[:2]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if item.get("note_command"):
            lines.append("   记录: %s" % item.get("note_command"))
            prereq = render_note_prerequisite(item.get("note_prerequisite", {}))
            if prereq:
                lines.append("   前置: %s" % prereq)
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines or ["- 暂无标的风险画像。"]


def render_review_path(value: object) -> List[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- 暂无复盘路径。"]
    lines = []
    for item in rows[:6]:
        if not isinstance(item, dict):
            continue
        state = "可执行" if item.get("runnable", True) else "需前置"
        lines.append("- #%s %s | %s | %s" % (item.get("rank"), state, item.get("title"), item.get("reason")))
        risks = item.get("risk_ids", []) if isinstance(item.get("risk_ids"), list) else []
        if risks:
            lines.append("   风险: %s" % "；".join(str(risk) for risk in risks[:4]))
        affected = item.get("affected_symbols", []) if isinstance(item.get("affected_symbols"), list) else []
        if affected:
            lines.append("   标的: %s" % "；".join(str(row) for row in affected[:5]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:3]))
        if item.get("unavailable_reason"):
            lines.append("   原因: %s" % item.get("unavailable_reason"))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines or ["- 暂无复盘路径。"]


def render_severity(value: object) -> str:
    mapping = {"high": "高", "medium": "中", "low": "低"}
    return mapping.get(str(value), str(value or "无"))


def render_command_queue_lines(value: object, limit: int = 8) -> List[str]:
    queue = value if isinstance(value, list) else []
    if not queue:
        return ["- 暂无命令队列。"]
    lines = []
    visible = list(queue[:limit])
    for item in queue:
        if not isinstance(item, dict):
            continue
        if item.get("mutates_state") and item not in visible:
            visible.append(item)
        if len(visible) >= limit + 4:
            break
    for item in visible:
        if not isinstance(item, dict):
            continue
        state = "可执行" if item.get("runnable", True) else "需前置"
        mode = "写入" if item.get("mutates_state") else "读取"
        lines.append("- #%s %s | %s | %s" % (item.get("rank"), state, mode, item.get("command")))
        if item.get("requires_prior_command"):
            lines.append("   先跑: %s" % item.get("requires_prior_command"))
        if item.get("unavailable_reason"):
            lines.append("   原因: %s" % item.get("unavailable_reason"))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines or ["- 暂无命令队列。"]


def render_issue_codes(value: object) -> str:
    issues = value if isinstance(value, list) else []
    parts = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        detail = issue.get("detail", {})
        symbol = detail.get("symbol") if isinstance(detail, dict) else None
        parts.append("%s%s" % (issue.get("code"), ":%s" % symbol if symbol else ""))
    return ", ".join(parts) if parts else "无"


def render_next_actions(value: object) -> List[str]:
    actions = value if isinstance(value, list) else []
    if not actions:
        return ["- 暂无动作。"]
    lines = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        runnable = "可执行" if item.get("runnable") else "需人工处理"
        lines.append(
            "- P%s %s | %s | %s"
            % (item.get("priority"), item.get("command"), runnable, item.get("reason"))
        )
    return lines or ["- 暂无动作。"]


def render_agent_steps(value: object) -> List[str]:
    steps = value if isinstance(value, list) else []
    if not steps:
        return ["- 暂无步骤。"]
    lines = []
    for item in steps:
        if not isinstance(item, dict):
            continue
        runnable = "可执行" if item.get("runnable") else "需人工处理"
        lines.append(
            "- P%s %s | %s | %s"
            % (item.get("priority"), item.get("command"), runnable, item.get("reason"))
        )
    return lines or ["- 暂无步骤。"]


def render_briefing_hotspots(value: object) -> List[str]:
    hotspots = value if isinstance(value, list) else []
    if not hotspots:
        return ["- 最强链路: 暂无热点。"]
    lines = ["- 最强链路:"]
    for item in hotspots[:3]:
        if not isinstance(item, dict):
            continue
        leaders = item.get("leaders", []) if isinstance(item.get("leaders"), list) else []
        leader_text = render_leaders(leaders) if leaders else "领涨: 无"
        lines.append(
            "   %s / %s | 热点 %s | 活跃 %s/%s | %s"
            % (
                item.get("layer"),
                item.get("sub_sector"),
                item.get("score"),
                item.get("active_member_count"),
                item.get("member_count"),
                leader_text,
            )
        )
    return lines


def render_briefing_portfolio(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- 持仓复核: 暂无重点项。"]
    lines = ["- 持仓复核:"]
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        quote = item.get("quote", {}) if isinstance(item.get("quote"), dict) else {}
        hotspot = item.get("hotspot", {}) if isinstance(item.get("hotspot"), dict) else {}
        lines.append(
            "   %s %s | %s | 复核分 %s | 涨幅 %s | %s"
            % (
                item.get("symbol"),
                item.get("name"),
                label(item.get("priority")),
                item.get("priority_score"),
                render_signed_percent(quote.get("change_pct") if quote else None),
                "%s / %s" % (hotspot.get("layer"), hotspot.get("sub_sector")) if hotspot else "无热点上下文",
            )
        )
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("      深入: %s" % "；".join(str(command) for command in commands[:2]))
    return lines


def render_briefing_watchlist(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- 观察清单: 暂无重点项。"]
    lines = ["- 观察清单:"]
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        mark = "持仓" if item.get("is_holding") else "观察"
        lines.append(
            "   %s %s | %s | %s / %s | 涨幅 %s | 热点 %s | %s"
            % (
                item.get("symbol"),
                item.get("name"),
                mark,
                item.get("layer"),
                item.get("sub_sector"),
                render_signed_percent(item.get("change_pct")),
                item.get("hotspot_score"),
                label(item.get("focus")),
            )
        )
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("      深入: %s" % "；".join(str(command) for command in commands[:2]))
    return lines


def render_portfolio_exposure(value: object) -> List[str]:
    exposure = value if isinstance(value, dict) else {}
    if not exposure.get("has_concentration"):
        return ["- 暂无重复链路或重复主题暴露。"]
    lines = [
        "- %s" % (exposure.get("summary") or "存在重复暴露。"),
    ]
    repeated = exposure.get("repeated_exposures", []) if isinstance(exposure.get("repeated_exposures"), list) else []
    overlap = exposure.get("repeated_overlap_groups", []) if isinstance(exposure.get("repeated_overlap_groups"), list) else []
    if repeated:
        lines.append("   重复链路: %s" % render_exposure_groups(repeated[:3]))
    if overlap:
        lines.append("   重复主题: %s" % render_exposure_groups(overlap[:3]))
    questions = exposure.get("questions", []) if isinstance(exposure.get("questions"), list) else []
    if questions:
        lines.append("   核对: %s" % "；".join(str(question) for question in questions[:2]))
    return lines


def render_exposure_groups(groups: List[object]) -> str:
    parts = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        holdings = group.get("holdings", []) if isinstance(group.get("holdings"), list) else []
        holding_text = ", ".join(
            "%s%s" % (holding.get("symbol"), " %s" % holding.get("name") if holding.get("name") else "")
            for holding in holdings[:4]
            if isinstance(holding, dict)
        )
        parts.append("%s(%s): %s" % (group.get("group"), group.get("holding_count"), holding_text or "无明细"))
    return "；".join(parts) if parts else "无"


def render_security_review_queue(value: object) -> List[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- 暂无标的复核队列。"]
    lines = []
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
        title = "%s %s" % (item.get("symbol"), item.get("name") or "")
        context_text = render_security_context(context)
        if context_text:
            title = "%s | %s" % (title.strip(), context_text)
        lines.append("- #%s %s | 复核分 %s | 来源 %s" % (
            item.get("rank"),
            title.strip(),
            item.get("priority_score"),
            ",".join(str(source) for source in item.get("sources", [])[:3]) if isinstance(item.get("sources"), list) else "无",
        ))
        reasons = item.get("reasons", []) if isinstance(item.get("reasons"), list) else []
        if reasons:
            lines.append("   原因: %s" % "；".join(str(reason) for reason in reasons[:3]))
        risks = item.get("risk_flags", []) if isinstance(item.get("risk_flags"), list) else []
        if risks:
            lines.append("   风险: %s" % render_labels(risks[:5]))
        coverage_state = context.get("coverage_state")
        if coverage_state and coverage_state != "confirmed":
            coverage_reasons = context.get("coverage_state_reasons", []) if isinstance(context.get("coverage_state_reasons"), list) else []
            reason_text = " | 原因: %s" % render_labels(coverage_reasons) if coverage_reasons else ""
            lines.append("   覆盖: %s%s" % (label(coverage_state), reason_text))
        research_text = render_research_status(context.get("research_status", {}))
        if research_text:
            lines.append("   研究: %s" % research_text)
        points = item.get("review_points", []) if isinstance(item.get("review_points"), list) else []
        if points:
            lines.append("   复核: %s" % "；".join(label(point) for point in points[:2]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
    return lines or ["- 暂无标的复核队列。"]


def render_security_context(value: Dict[str, object]) -> str:
    parts = []
    if value.get("is_holding"):
        parts.append("持仓")
    if value.get("layer") or value.get("sub_sector"):
        parts.append("%s/%s" % (value.get("layer") or "无链路", value.get("sub_sector") or "无主题"))
    if value.get("change_pct") is not None:
        parts.append("涨幅 %s" % render_signed_percent(value.get("change_pct")))
    if value.get("hotspot_score") is not None:
        parts.append("热点 %s" % value.get("hotspot_score"))
    if value.get("coverage_state") and value.get("coverage_state") != "confirmed":
        parts.append("覆盖 %s" % label(value.get("coverage_state")))
    return " | ".join(parts)


def render_briefing_focus(value: object) -> List[str]:
    focus = value if isinstance(value, list) else []
    if not focus:
        return ["- 暂无复核焦点。"]
    lines = []
    for item in focus:
        if not isinstance(item, dict):
            continue
        lines.append("- P%s %s | %s" % (item.get("priority"), item.get("title"), item.get("reason")))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("   依据: %s" % "；".join(str(row) for row in evidence[:3]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
    return lines


def render_briefing_checklist(value: object) -> List[str]:
    checklist = value if isinstance(value, list) else []
    if not checklist:
        return ["- 暂无复核清单。"]
    lines = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        lines.append("- P%s %s | %s" % (item.get("priority"), item.get("title"), item.get("reason")))
        evidence = item.get("evidence", []) if isinstance(item.get("evidence"), list) else []
        if evidence:
            lines.append("   依据: %s" % "；".join(str(row) for row in evidence[:3]))
        commands = item.get("commands", []) if isinstance(item.get("commands"), list) else []
        if commands:
            lines.append("   命令: %s" % "；".join(str(command) for command in commands[:2]))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
    return lines


def render_briefing_data_quality(value: object) -> List[str]:
    validation = value if isinstance(value, dict) else {}
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    warning_count = validation.get("warning_count", len(warnings))
    error_count = validation.get("error_count", len(errors))
    if not warning_count and not error_count and not warnings and not errors:
        return []

    lines = ["- 数据告警: 告警 %s | 错误 %s" % (warning_count, error_count)]
    if errors:
        lines.append("   错误明细: %s" % render_compact_issue_summary(errors[:4]))
    if warnings:
        lines.append("   告警明细: %s" % render_compact_issue_summary(warnings[:4]))
    return lines


def render_briefing_market_scan(value: object) -> List[str]:
    scan = value if isinstance(value, dict) else {}
    if not scan.get("available"):
        return ["- %s" % (scan.get("summary") or "暂无全市场扫描。")]
    lines = [
        "- %s | 模式 %s | 匹配行情 %s/%s"
        % (
            scan.get("summary") or "暂无摘要。",
            render_scan_mode(scan.get("scan_mode")),
            scan.get("matched_quote_count", 0),
            scan.get("quote_count", 0),
        )
    ]
    groups = scan.get("sector_groups", []) if isinstance(scan.get("sector_groups"), list) else []
    for group in groups[:3]:
        if isinstance(group, dict):
            lines.append(
                "   板块: #%s %s%s | 分 %s | 活跃 %s/%s"
                % (
                    group.get("rank"),
                    scan_group_type_label(group.get("group_type")),
                    group.get("name"),
                    group.get("score"),
                    group.get("active_member_count", 0),
                    group.get("member_count", 0),
                )
            )
    candidates = scan.get("candidate_securities", []) if isinstance(scan.get("candidate_securities"), list) else []
    for item in candidates[:3]:
        if isinstance(item, dict):
            lines.append(
                "   候选: #%s %s %s | 分 %s | 覆盖 %s"
                % (
                    item.get("rank"),
                    item.get("symbol"),
                    item.get("name"),
                    item.get("review_score"),
                    item.get("coverage_state"),
                )
            )
    return lines


def render_runtime_validation_brief(value: object) -> List[str]:
    validation = value if isinstance(value, dict) else {}
    warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    errors = validation.get("errors", []) if isinstance(validation.get("errors"), list) else []
    if not warnings and not errors:
        return []
    lines = []
    if errors:
        lines.append("- runtime 错误: %s" % render_compact_issue_summary(errors[:4]))
    if warnings:
        lines.append("- runtime 告警: %s" % render_compact_issue_summary(warnings[:4]))
    return lines


def render_compact_issue_summary(value: object) -> str:
    issues = value if isinstance(value, list) else []
    parts = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        text = compact_issue_identifier(issue)
        missing = issue.get("missing")
        if isinstance(missing, list) and missing:
            text = "%s | 缺字段 %s" % (text, ",".join(str(field) for field in missing[:4]))
        elif issue.get("message"):
            text = "%s | %s" % (text, trim_text(issue.get("message"), 80))
        parts.append(text)
    return "；".join(parts) if parts else "无"


def compact_issue_identifier(issue: Dict[str, object]) -> str:
    code = str(issue.get("code") or "UNKNOWN")
    detail = issue.get("detail", {}) if isinstance(issue.get("detail"), dict) else {}
    symbol = issue.get("symbol") or detail.get("symbol")
    if symbol:
        return "%s:%s" % (code, symbol)
    path = issue.get("path") or detail.get("path")
    if path:
        return "%s:%s" % (code, path)
    return code


def render_briefing_current_change(value: object) -> List[str]:
    change = value if isinstance(value, dict) else {}
    if not change.get("available"):
        return ["- 暂无当前对比；需要至少一份日报留档。"]
    risk = change.get("risk_flags", {}) if isinstance(change.get("risk_flags"), dict) else {}
    watchlist = change.get("watchlist", {}) if isinstance(change.get("watchlist"), dict) else {}
    portfolio = change.get("portfolio_review", {}) if isinstance(change.get("portfolio_review"), dict) else {}
    hotspots = change.get("hotspots", {}) if isinstance(change.get("hotspots"), dict) else {}
    validation = change.get("validation", {}) if isinstance(change.get("validation"), dict) else {}
    lines = [
        "- %s" % (change.get("summary") or "暂无摘要。"),
        "- 风险 +%s/-%s | 观察 +%s/-%s/~%s | 持仓复核 +%s/-%s/~%s | 热点 +%s/-%s/~%s | 告警 %+s | 错误 %+s"
        % (
            risk.get("added_count", 0),
            risk.get("removed_count", 0),
            watchlist.get("added_count", 0),
            watchlist.get("removed_count", 0),
            watchlist.get("changed_count", 0),
            portfolio.get("added_count", 0),
            portfolio.get("removed_count", 0),
            portfolio.get("changed_count", 0),
            hotspots.get("added_count", 0),
            hotspots.get("removed_count", 0),
            hotspots.get("changed_count", 0),
            validation.get("warning_delta", 0),
            validation.get("error_delta", 0),
        ),
    ]
    top = hotspots.get("top", {}) if isinstance(hotspots.get("top"), dict) else {}
    current_top = top.get("current", {}) if isinstance(top.get("current"), dict) else {}
    if current_top:
        lines.append(
            "- 当前最强: %s / %s | 热点 %s"
            % (current_top.get("layer"), current_top.get("sub_sector"), current_top.get("score"))
        )
    return lines


def render_briefing_history(value: object) -> List[str]:
    history = value if isinstance(value, dict) else {}
    lines = [
        "- 留档 %s/%s | 可对比 %s"
        % (history.get("count", 0), history.get("total_count", 0), "是" if history.get("can_compare") else "否")
    ]
    latest = history.get("latest_entry", {}) if isinstance(history.get("latest_entry"), dict) else {}
    if latest:
        lines.append("- 最新留档: %s | %s" % (latest.get("trade_date") or "无交易日", latest.get("entry_id")))
        latest_note = latest.get("latest_note", {}) if isinstance(latest.get("latest_note"), dict) else {}
        if latest_note:
            lines.append("   最近笔记: %s | %s" % (latest_note.get("section") or "general", trim_text(latest_note.get("text"), 120)))
    transition = history.get("latest_transition", {}) if isinstance(history.get("latest_transition"), dict) else {}
    if transition:
        lines.append("- 最近转折: %s" % (transition.get("summary") or "暂无摘要。"))
    elif history.get("summary"):
        lines.append("- %s" % history.get("summary"))
    return lines


def render_briefing_command_queue(value: object) -> List[str]:
    queue = value if isinstance(value, list) else []
    if not queue:
        return ["- 暂无命令队列。"]
    lines = []
    for item in queue[:8]:
        if not isinstance(item, dict):
            continue
        mark = "写入" if item.get("mutates_state") else "读取"
        lines.append("- #%s %s | %s | %s" % (item.get("rank"), mark, item.get("command"), item.get("purpose") or item.get("reason")))
        read_fields = item.get("read_fields", []) if isinstance(item.get("read_fields"), list) else []
        if read_fields:
            lines.append("   读取: %s" % "；".join(str(field) for field in read_fields[:4]))
        if item.get("output_use"):
            lines.append("   用途: %s" % item.get("output_use"))
        if item.get("done_when"):
            lines.append("   完成: %s" % item.get("done_when"))
        if item.get("state_effect"):
            lines.append("   状态: %s" % label(item.get("state_effect")))
    return lines or ["- 暂无命令队列。"]


def render_journal_prompt(value: object) -> List[str]:
    prompt = value if isinstance(value, dict) else {}
    sections = prompt.get("sections", []) if isinstance(prompt.get("sections"), list) else []
    if not sections:
        return ["- 暂无留档提示。"]
    lines = []
    if prompt.get("summary"):
        lines.append("- %s" % prompt.get("summary"))
    for section in sections[:5]:
        if not isinstance(section, dict):
            continue
        lines.append("   %s: %s" % (section.get("title"), section.get("prompt")))
        if section.get("note_command"):
            lines.append("      记录命令: %s" % section.get("note_command"))
    return lines


def render_command_list(value: object) -> List[str]:
    commands = value if isinstance(value, list) else []
    if not commands:
        return ["- 暂无命令。"]
    return ["- %s" % command for command in commands]


def render_added_removed_labels(value: object, empty: str) -> List[str]:
    change = value if isinstance(value, dict) else {}
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    lines = []
    if added:
        lines.append("- 新增: %s" % render_labels(added))
    if removed:
        lines.append("- 减少: %s" % render_labels(removed))
    return lines or ["- %s" % empty]


def render_watchlist_compare(value: object) -> List[str]:
    watchlist = value if isinstance(value, dict) else {}
    lines = [
        "- 数量: %s -> %s" % (watchlist.get("base_count", 0), watchlist.get("current_count", 0)),
    ]
    added = watchlist.get("added", []) if isinstance(watchlist.get("added"), list) else []
    removed = watchlist.get("removed", []) if isinstance(watchlist.get("removed"), list) else []
    changed = watchlist.get("changed", []) if isinstance(watchlist.get("changed"), list) else []
    if not added and not removed and not changed:
        lines.append("- 无观察项新增、减少或字段变化。")
        return lines
    for item in added[:5]:
        if isinstance(item, dict):
            lines.append("- 新增: %s" % render_compare_security(item))
    for item in removed[:5]:
        if isinstance(item, dict):
            lines.append("- 减少: %s" % render_compare_security(item))
    for item in changed[:5]:
        if not isinstance(item, dict):
            continue
        change_fields = item.get("changes", {}) if isinstance(item.get("changes"), dict) else {}
        current = item.get("current", {}) if isinstance(item.get("current"), dict) else {}
        lines.append(
            "- 变化: %s %s | %s"
            % (
                item.get("symbol"),
                item.get("name") or current.get("name") or "",
                render_changed_fields(change_fields),
            )
        )
    return lines


def render_hotspot_compare(value: object) -> List[str]:
    hotspots = value if isinstance(value, dict) else {}
    lines = [
        "- 数量: %s -> %s" % (hotspots.get("base_count", 0), hotspots.get("current_count", 0)),
    ]
    top = hotspots.get("top", {}) if isinstance(hotspots.get("top"), dict) else {}
    current_top = top.get("current", {}) if isinstance(top.get("current"), dict) else {}
    if current_top:
        lines.append(
            "- 当前最强: %s / %s | 热点 %s"
            % (current_top.get("layer"), current_top.get("sub_sector"), current_top.get("score"))
        )
    added = hotspots.get("added", []) if isinstance(hotspots.get("added"), list) else []
    removed = hotspots.get("removed", []) if isinstance(hotspots.get("removed"), list) else []
    changed = hotspots.get("changed", []) if isinstance(hotspots.get("changed"), list) else []
    if not added and not removed and not changed:
        lines.append("- 无热点新增、减少或字段变化。")
        return lines
    for item in added[:5]:
        if isinstance(item, dict):
            lines.append("- 新增: %s / %s | 热点 %s" % (item.get("layer"), item.get("sub_sector"), item.get("score")))
    for item in removed[:5]:
        if isinstance(item, dict):
            lines.append("- 减少: %s / %s | 热点 %s" % (item.get("layer"), item.get("sub_sector"), item.get("score")))
    for item in changed[:5]:
        if not isinstance(item, dict):
            continue
        current = item.get("current", {}) if isinstance(item.get("current"), dict) else {}
        change_fields = item.get("changes", {}) if isinstance(item.get("changes"), dict) else {}
        lines.append(
            "- 变化: %s / %s | %s"
            % (current.get("layer"), current.get("sub_sector"), render_changed_fields(change_fields))
        )
    return lines


def render_portfolio_compare(value: object) -> List[str]:
    portfolio = value if isinstance(value, dict) else {}
    priority_counts = portfolio.get("priority_counts", {}) if isinstance(portfolio.get("priority_counts"), dict) else {}
    base_priority = priority_counts.get("base", {}) if isinstance(priority_counts.get("base"), dict) else {}
    current_priority = priority_counts.get("current", {}) if isinstance(priority_counts.get("current"), dict) else {}
    lines = [
        "- 数量: %s -> %s" % (portfolio.get("base_count", 0), portfolio.get("current_count", 0)),
        "- 重点复核: %s -> %s"
        % (base_priority.get("high_review", 0), current_priority.get("high_review", 0)),
    ]
    added = portfolio.get("added", []) if isinstance(portfolio.get("added"), list) else []
    removed = portfolio.get("removed", []) if isinstance(portfolio.get("removed"), list) else []
    changed = portfolio.get("changed", []) if isinstance(portfolio.get("changed"), list) else []
    if not added and not removed and not changed:
        lines.append("- 无持仓复核新增、减少或字段变化。")
        return lines
    for item in added[:5]:
        if isinstance(item, dict):
            lines.append("- 新增: %s" % render_portfolio_compare_item(item))
    for item in removed[:5]:
        if isinstance(item, dict):
            lines.append("- 减少: %s" % render_portfolio_compare_item(item))
    for item in changed[:5]:
        if not isinstance(item, dict):
            continue
        current = item.get("current", {}) if isinstance(item.get("current"), dict) else {}
        change_fields = item.get("changes", {}) if isinstance(item.get("changes"), dict) else {}
        lines.append(
            "- 变化: %s %s | %s"
            % (
                item.get("symbol"),
                item.get("name") or current.get("name") or "",
                render_changed_fields(change_fields),
            )
        )
    return lines


def render_portfolio_compare_item(item: Dict[str, object]) -> str:
    return "%s %s | %s | 复核分 %s | 涨幅 %s | 热点 %s" % (
        item.get("symbol"),
        item.get("name"),
        label(item.get("priority")),
        item.get("priority_score"),
        render_signed_percent(item.get("change_pct")),
        item.get("hotspot_score"),
    )


def render_validation_compare(value: object) -> List[str]:
    validation = value if isinstance(value, dict) else {}
    base = validation.get("base", {}) if isinstance(validation.get("base"), dict) else {}
    current = validation.get("current", {}) if isinstance(validation.get("current"), dict) else {}
    summary_delta = validation.get("summary_delta", {}) if isinstance(validation.get("summary_delta"), dict) else {}
    warning_codes = validation.get("warning_codes", {}) if isinstance(validation.get("warning_codes"), dict) else {}
    error_codes = validation.get("error_codes", {}) if isinstance(validation.get("error_codes"), dict) else {}
    lines = ["- 状态: %s -> %s" % (base.get("ok"), current.get("ok"))]
    if summary_delta:
        lines.append("- 摘要字段变化: %s" % render_changed_fields(summary_delta))
    lines.extend(render_added_removed_plain(warning_codes, "告警代码无新增或减少。"))
    lines.extend(render_added_removed_plain(error_codes, "错误代码无新增或减少。"))
    return lines


def render_timeline_hotspot(value: object) -> str:
    hotspot = value if isinstance(value, dict) else {}
    if not hotspot:
        return "暂无热点"
    return "%s / %s | 热点 %s" % (hotspot.get("layer"), hotspot.get("sub_sector"), hotspot.get("score"))


def render_timeline_portfolio_items(value: object) -> str:
    items = value if isinstance(value, list) else []
    parts = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        parts.append(
            "%s %s[%s/%s]"
            % (
                item.get("symbol"),
                item.get("name"),
                label(item.get("priority")),
                item.get("priority_score"),
            )
        )
    return "；".join(parts) if parts else "无"


def render_added_removed_counts(value: object) -> str:
    change = value if isinstance(value, dict) else {}
    return "+%s/-%s" % (change.get("added_count", 0), change.get("removed_count", 0))


def render_collection_counts(value: object) -> str:
    change = value if isinstance(value, dict) else {}
    return "+%s/-%s/~%s" % (
        change.get("added_count", 0),
        change.get("removed_count", 0),
        change.get("changed_count", 0),
    )


def render_compare_security(item: Dict[str, object]) -> str:
    return "%s %s | %s / %s | 涨幅 %s | 热点 %s" % (
        item.get("symbol"),
        item.get("name"),
        item.get("layer"),
        item.get("sub_sector"),
        render_signed_percent(item.get("change_pct")),
        item.get("hotspot_score"),
    )


def render_changed_fields(value: object) -> str:
    changes = value if isinstance(value, dict) else {}
    if not changes:
        return "无字段变化"
    parts = []
    for key, detail in changes.items():
        display = FIELD_LABELS.get(str(key), str(key))
        if isinstance(detail, dict) and "delta" in detail:
            parts.append("%s %s->%s(%+s)" % (display, detail.get("base"), detail.get("current"), detail.get("delta")))
        elif isinstance(detail, dict) and ("added" in detail or "removed" in detail):
            added = detail.get("added", []) if isinstance(detail.get("added"), list) else []
            removed = detail.get("removed", []) if isinstance(detail.get("removed"), list) else []
            parts.append("%s +%s -%s" % (display, len(added), len(removed)))
        elif isinstance(detail, dict):
            parts.append("%s %s->%s" % (display, detail.get("base"), detail.get("current")))
        else:
            parts.append(display)
    return "；".join(parts)


def render_added_removed_plain(value: object, empty: str) -> List[str]:
    change = value if isinstance(value, dict) else {}
    added = change.get("added", []) if isinstance(change.get("added"), list) else []
    removed = change.get("removed", []) if isinstance(change.get("removed"), list) else []
    lines = []
    if added:
        lines.append("- 告警/错误新增: %s" % ", ".join(str(item) for item in added))
    if removed:
        lines.append("- 告警/错误减少: %s" % ", ".join(str(item) for item in removed))
    return lines or ["- %s" % empty]


def render_signed_percent(value: object) -> str:
    if value is None:
        return "无"
    return "%+s%%" % value


FIELD_LABELS = {
    "rank": "排序",
    "name": "名称",
    "is_holding": "持仓标记",
    "layer": "链路",
    "sub_sector": "子链路",
    "focus": "关注点",
    "change_pct": "涨幅",
    "hotspot_score": "热点",
    "amount_ratio": "成交放大",
    "intraday_fade_pct": "回落",
    "signals": "信号",
    "risks": "风险",
    "score": "热点",
    "active_member_count": "活跃数",
    "member_count": "成员数",
    "leaders": "领涨",
    "priority": "复核优先级",
    "priority_score": "复核分",
    "has_quote": "行情状态",
    "matched_pool_item": "池子匹配",
    "hotspot_key": "热点上下文",
    "hotspot_score": "热点",
    "exposure_keys": "链路",
    "overlap_groups": "重叠主题",
    "risk_flags": "风险",
    "review_points": "复核点",
}


def render_leaders(leaders: List[object]) -> str:
    parts = []
    for leader in leaders[:3]:
        if not isinstance(leader, dict):
            continue
        parts.append("%s %s%%" % (leader.get("name"), leader.get("change_pct")))
    return "领涨: %s" % (", ".join(parts) if parts else "无")


def render_group_counts(groups: Iterable[object]) -> str:
    parts = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        parts.append("%s(%s)" % (group.get("group"), group.get("holding_count")))
    return ", ".join(parts) if parts else "无"


def int_or_default(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_list(value: object, empty: str) -> List[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- %s" % empty]
    return ["- %s" % label(item) for item in items]


def trim_text(value: object, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def render_labels(values: Iterable[object]) -> str:
    return ", ".join(label(value) for value in values)


def render_research_status(value: object) -> str:
    data = value if isinstance(value, dict) else {}
    if not data.get("available"):
        return ""
    status = str(data.get("status") or "draft")
    if data.get("confirmed"):
        source = data.get("source_file")
        return "reviewed%s" % (" | %s" % source if source else "")
    missing = data.get("missing_fields", []) if isinstance(data.get("missing_fields"), list) else []
    if missing:
        return "%s | 待补 %s" % (status, "、".join(str(field) for field in missing[:3]))
    return status


def label(value: object) -> str:
    text = str(value)
    return LABELS.get(text, QUESTION_LABELS.get(text, text))
