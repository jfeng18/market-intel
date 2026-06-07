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

## 核心对象

- `PoolItem`：证券、链路、角色、`exposures[]`、`raw`、`data_quality_flags`。
- `Quote`：`symbol/trade_date/last_price/change_pct/amount/...`；字符串布尔必须显式解析。
- `Holding`：按 distinct symbol 计数，重复 exposure 不制造重复持仓。
- `research_notes_v1`：`symbol/name/status/thesis/evidence/invalidation/updated_at/source`。
- `journal`：日报、假设、补充笔记和对比结果。

## Dashboard

Agent 优先读：

- `data.action_summary.decision_card`：今日动作卡。
- `decision_card.json_command`：下一条可执行命令。
- `decision_card.why`：为什么先做这项。
- `decision_card.done_when`：完成标准。
- `decision_card.next_json_command`：接力命令。
- `decision_card.check_status/check_done_when`：留档前门槛。
- `data.coverage_context`、`data.market_pulse`、`data.portfolio_pulse`、`data.evidence_gaps`：上下文。
- `data.review_plan.items[]`：完整接力队列。

## CSV 口径

- Universe：`symbol,name,industry,concepts,index_membership,listing_status,source`
- Research：`symbol,name,status,thesis,evidence,invalidation,updated_at,source`

`status=reviewed` 时必须补齐 `thesis/evidence/invalidation`。

## 禁止字段

- `action=buy/sell/hold`
- `recommendation=buy/sell/hold`
- `target_price`
- `position_size`
- `must_buy`
- `must_sell`
