# 数据合同

本文件只记录稳定读取口径。实现细节以 `src/market_intel/core/` 和测试为准。

## JSON 外壳

所有 CLI JSON 输出使用同一外壳：

```json
{
  "ok": true,
  "command": "pool.coverage",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "generated_at": "2026-06-07T09:30:00+08:00",
    "schema_version": "0.1",
    "source": "pool:all-a"
  }
}
```

失败时：

- `ok=false`
- `errors[]` 使用 `{code,message,detail}`
- 不把 traceback 放入 `data`

## PoolItem

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

约束：

- 非证券或待上市行可 `symbol=null`。
- 同一证券多链路不丢弃，放入 `exposures[]`。
- 原始字段保留在 `raw`。
- 数据问题进入 `data_quality_flags`。

## Quote

```json
{
  "symbol": "002837",
  "trade_date": "2026-06-07",
  "last_price": 38.42,
  "change_pct": 6.8,
  "amount": 1850000000,
  "amount_ratio": 2.4,
  "turnover_rate": 8.6,
  "amplitude_pct": 10.2,
  "is_limit_up": false,
  "is_stage_high": true,
  "intraday_fade_pct": 1.5,
  "source": "runtime"
}
```

布尔字段接受常见字符串，但无效字符串必须报错，不能按 Python truthiness 处理。

## Holding

```json
{
  "symbol": "002837",
  "name": "英维克",
  "quantity": 1000,
  "source": "runtime"
}
```

持仓复核以 distinct holding 计数；单个标的内部重复 exposure 不应制造 `theme_concentration`。

## Universe CSV

标准字段：

```text
symbol,name,industry,concepts,index_membership,listing_status,source
```

常见中文列名也支持：

```text
证券代码,证券名称,行业,概念,指数成分,上市状态
```

导入前用：

```bash
market-intel import universe <csv> --runtime --merge --dry-run --text
```

稳定读取字段：

- `data.coverage_delta.write_mode`
- `data.coverage_delta.before`
- `data.coverage_delta.after`
- `data.coverage_delta.improvement`
- `data.coverage_delta.recommendation.requires_import`
- `data.next_commands`

## Research CSV

标准字段：

```text
symbol,name,status,thesis,evidence,invalidation,updated_at,source
```

`status=reviewed` 时必须补齐：

- `thesis`
- `evidence`
- `invalidation`

只有 reviewed 且三项齐全，foundation 标的才可升级为 confirmed。

## 禁止字段

公开 JSON 和文本报告不得输出：

- `action=buy/sell/hold`
- `recommendation=buy/sell/hold`
- `target_price`
- `position_size`
- `must_buy`
- `must_sell`
