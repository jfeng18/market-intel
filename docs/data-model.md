# market-intel 数据模型 v0

> 日期：2026-05-22  
> 状态：P0/P1 开发契约  
> 范围：AI 能量公式池子、mock 行情、mock 持仓影响  

---

## 1. 统一 JSON 外壳

所有 CLI 命令必须返回同一外壳：

```json
{
  "ok": true,
  "command": "pool.list",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "generated_at": "2026-05-22T09:30:00+08:00",
    "schema_version": "0.1",
    "source": "data/pools/ai_energy_pool_2026-05-19.csv"
  }
}
```

失败时：

- `ok=false`
- `data` 返回 `{}` 或可安全消费的部分结果
- `errors` 放结构化错误
- 不把 Python traceback 放入 `data`

错误对象：

```json
{
  "code": "POOL_ITEM_NOT_FOUND",
  "message": "Pool item not found: 002837",
  "detail": {
    "symbol": "002837"
  }
}
```

---

## 2. PoolItem

`PoolItem` 是标准化后的证券或非证券池子条目。原始 CSV 行必须可追溯。

```json
{
  "symbol": "002837",
  "name": "英维克",
  "market": "CN_A",
  "instrument_type": "security",
  "priority": "P1",
  "tradable": true,
  "primary_layer": "电力",
  "primary_sub_sector": "液冷",
  "primary_role": "龙头",
  "logic": "数据中心温控与液冷方案",
  "exposures": [],
  "raw": {},
  "data_quality_flags": []
}
```

字段约束：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|---:|---|
| `symbol` | string/null | 是 | 标准证券代码；非证券或未上市可为 null |
| `name` | string | 是 | 标准名称 |
| `market` | enum | 是 | `CN_A` / `HK` / `US` / `TW` / `KR` / `OTHER` / `UNKNOWN` |
| `instrument_type` | enum | 是 | `security` / `pending_listing` / `index_or_theme` / `non_security` / `unknown` |
| `priority` | enum | 是 | `P1` / `P2` / `P3` / `UNKNOWN` |
| `tradable` | bool | 是 | 是否能进入交易相关分析；不是买卖建议 |
| `primary_layer` | enum | 是 | `算力` / `运力` / `存力` / `电力` / `人才密度` / `应用` / `其他` |
| `primary_sub_sector` | string | 是 | 由 section 清洗得到 |
| `primary_role` | string | 否 | 龙头、龙二、梯队、后排、弹性等 |
| `logic` | string | 否 | 一句话逻辑，优先来自 desc |
| `exposures` | array | 是 | 多链路暴露列表 |
| `raw` | object | 是 | 原始 CSV 字段 |
| `data_quality_flags` | array | 是 | 数据质量标记 |

---

## 3. Exposure

同一证券可属于多个链路。不要简单去重丢信息。

```json
{
  "layer": "运力",
  "sub_sector": "光模块",
  "section": "2.1 光模块",
  "role": "龙头",
  "priority": "P1",
  "logic": "800G/1.6T 光模块核心供应商",
  "raw_row": 135
}
```

---

## 4. DataQualityFlag

数据质量标记必须可测试、可解释。

建议枚举：

| 标记 | 触发条件 |
|---|---|
| `invalid_symbol` | `raw_code` 不是标准证券代码 |
| `pending_listing` | `raw_code` 是 `科创板`、`港股`、`IPO 已过会` 等上市状态 |
| `column_shift_suspected` | `company/code/desc` 疑似错位 |
| `non_security_row` | 原始行是缺口、国产化率、环节说明等 |
| `duplicate_symbol_exposure` | 同一证券有多条链路暴露 |
| `missing_role` | 角色无法从 level 或 desc 推断 |
| `unknown_layer` | section 无法映射到五层结构 |

---

## 5. Quote

P1 使用 mock quote；真实行情接入放到 P2。

```json
{
  "symbol": "002837",
  "trade_date": "2026-05-22",
  "last_price": 38.42,
  "change_pct": 6.8,
  "amount": 1850000000,
  "amount_ratio": 2.4,
  "turnover_rate": 8.6,
  "amplitude_pct": 10.2,
  "is_limit_up": false,
  "is_stage_high": true,
  "intraday_fade_pct": 1.5,
  "source": "mock"
}
```

---

## 6. Hotspot

热点是子链路级别结果，不是单票推荐。

```json
{
  "layer": "电力",
  "sub_sector": "液冷",
  "score": 82.5,
  "member_count": 8,
  "active_member_count": 5,
  "leaders": [
    {
      "symbol": "002837",
      "name": "英维克",
      "change_pct": 6.8,
      "role": "龙头"
    }
  ],
  "score_breakdown": {
    "avg_change_score": 76,
    "turnover_expansion_score": 88,
    "strong_member_score": 80,
    "leader_strength_score": 90,
    "persistence_score": 70,
    "intraday_fade_penalty": 12
  },
  "signals": ["sector_resonance", "leader_strength"],
  "risks": ["valuation_pressure", "one_day_rotation_risk"],
  "explain": "液冷链路多点上涨，龙头强于后排，但需验证持续性。"
}
```

评分约束：

- 所有 score 为 0-100。
- `score_breakdown` 必须完整输出。
- `risks` 必须和 `signals` 同级展示。
- 禁止输出买入、卖出、持有、目标价、仓位建议。

---

## 7. HoldingExposure

P1 使用 mock holdings；真实 tradegov 只读接入放到后续阶段。

```json
{
  "holding_symbol": "002261",
  "holding_name": "拓维信息",
  "market": "CN_A",
  "matched_pool_item": true,
  "exposures": [
    {
      "layer": "算力",
      "sub_sector": "AI 服务器",
      "role": "信创服务器"
    }
  ],
  "overlap_groups": ["华为昇腾", "信创服务器"],
  "impact": {
    "benefit_hotspots": ["AI 服务器"],
    "pressure_hotspots": [],
    "risk_flags": ["theme_concentration"]
  },
  "explain": "该持仓与 AI 服务器和华为昇腾链路相关，需关注同链路重复暴露。"
}
```

---

## 8. NewsEvent / CompanySignal

P0/P1 只定义模型，不实现真实新闻扫描。

`NewsEvent`：

```json
{
  "event_id": "mock-20260522-001",
  "event_time": "2026-05-22T09:30:00+08:00",
  "source": "mock",
  "source_type": "news",
  "rating": "B",
  "title": "液冷订单验证",
  "summary": "mock 事件摘要",
  "affected_layers": ["电力"],
  "affected_sub_sectors": ["液冷"],
  "affected_symbols": ["002837"],
  "confidence": 0.6,
  "risks": ["source_not_verified"]
}
```

`CompanySignal`：

```json
{
  "symbol": "002837",
  "name": "英维克",
  "facts": [],
  "signals": [],
  "risks": [],
  "questions": []
}
```

