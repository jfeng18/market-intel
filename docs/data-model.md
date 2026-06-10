# 数据合同

实现细节以 `src/market_intel/core/` 和测试为准；这里只记录稳定读取口径。

## JSON 外壳

所有 JSON 命令使用同一外壳：

```json
{
  "ok": true,
  "command": "dashboard",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {}
}
```

失败时 `ok=false`，`errors[]` 使用 `{code,message,detail}`，不把 traceback 放入 `data`。

## 覆盖状态

- `confirmed`：复盘池正式覆盖，或 foundation 标的已补 reviewed research notes。
- `foundation`：全 A 基础清单收录，但研究证据未完成。
- `draft`：候选或待确认补池行。
- `missing`：持仓或行情标的不在复盘池/基础清单。
- `blocked`：数据错误导致无法可信复盘。
- `quote_only`：有行情数据但不在复盘池或基础清单中。

## 核心对象

### PoolItem

`symbol, name, market, instrument_type, priority, tradable, primary_layer, primary_sub_sector, primary_role, logic, exposures[], raw, data_quality_flags`

### Exposure

`layer, sub_sector, section, role, priority, logic, raw_row`

### Quote

`symbol, name, trade_date, last_price, change_pct, amount, amount_ratio, turnover_rate, amplitude_pct, is_limit_up, is_stage_high, intraday_fade_pct, source`

字符串布尔必须显式解析（是/否/涨停/√）。

### Holding

`symbol, name, quantity, cost_price, source`

`quantity` 和 `cost_price` 均为 `Optional[float]`。`cost_price` 用于 HTML 报告计算浮动盈亏。

### Hotspot

`layer, sub_sector, score, member_count, active_member_count, leaders[], score_breakdown, signals[], risks[], explain`

`score_breakdown` 含六个维度：`avg_change_score, turnover_expansion_score, strong_member_score, leader_strength_score, persistence_score, intraday_fade_penalty`。

### research_notes_v1

`symbol, name, status, thesis, evidence, invalidation, updated_at, source`

### journal

日报留档、假设跟踪、补充笔记和对比结果。支持 save/list/latest/show/compare/timeline/note/notes。

## Dashboard

Agent 优先读：

- `data.action_summary.decision_card`：今日动作卡。
- `data.coverage_context`、`data.market_pulse`、`data.portfolio_pulse`、`data.evidence_gaps`：上下文。
- `data.review_plan.items[]`：完整接力队列。

## Review

- `data.changes`：与历史日报的变化对比（日/周/月窗口）。
- `data.command_queue[]`：agent 接力队列；每项包含 `command/json_command/state_effect/runnable/done_when`。
- `state_effect=read_only` 才适合自动执行；`writes_runtime`、`writes_journal`、`writes_runtime_journal` 需人工确认。
- 复盘后的 follow-up 命令默认带 `--no-sync --no-save`，只读对比。

## CSV 口径

| 数据 | 字段 |
|------|------|
| Quote | `symbol, name, trade_date, last_price, change_pct, amount, amount_ratio, turnover_rate, amplitude_pct, is_limit_up, is_stage_high, intraday_fade_pct, source` |
| Holding | `symbol, name, quantity, cost_price, source` |
| Universe | `symbol, name, industry, concepts, index_membership, listing_status, source` |
| Research | `symbol, name, status, thesis, evidence, invalidation, updated_at, source` |

所有 CSV 支持 UTF-8/GBK/GB18030 编码自动检测。列名支持中英文别名。

`status=reviewed` 时必须补齐 `thesis/evidence/invalidation`。

## 禁止字段

- `action=buy/sell/hold`
- `recommendation=buy/sell/hold`
- `target_price`
- `position_size`
- `must_buy`
- `must_sell`
