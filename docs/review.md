# market-intel 开发前 Review

> 日期：2026-05-22  
> Review：Codex  
> 状态：可以进入 P0 开发，但必须按本文件边界执行。  

---

## 1. 结论

可以开发，但不要先做 GUI、真实行情或外部 adapter。第一阶段只做离线 CLI 和可测试 core。

开发入口：

- 主设计：`docs/design.md`
- 数据契约：`docs/data-model.md`
- 设计审查：`docs/design-review.md`

---

## 2. 必须执行

P0 必须完成：

1. 读取 `data/pools/ai_energy_pool_2026-05-19.csv`。
2. 保留 raw 字段并生成标准化 PoolItem。
3. 标记 `instrument_type`、`tradable`、`data_quality_flags`。
4. 合并同一 symbol 的多链路 exposures。
5. 实现统一 JSON 外壳。
6. 实现：
   - `market-intel pool list --pool ai-energy --json`
   - `market-intel pool explain <symbol> --json`
7. pytest 覆盖：
   - CSV 解析。
   - 字段错位。
   - 非证券行。
   - 重复暴露。
   - JSON 外壳。
   - 禁止买卖建议字段。

P1 必须完成：

1. mock quotes。
2. mock holdings。
3. `market-intel hotspots --mock --json`。
4. `market-intel holdings impact --mock --json`。
5. 热点评分输出完整 `score_breakdown`。
6. 风险提示和信号同级展示。

---

## 3. 必须禁止

P0/P1 禁止：

- 接真实交易。
- 输出买入/卖出/持有。
- 输出目标价。
- 输出仓位建议。
- 写入 tradegov/researchgov/companygov。
- GUI 重新实现一套评分逻辑。
- 直接把原始 `code` 当可靠 symbol。
- 简单去重导致多链路暴露丢失。

---

## 4. 建议目录

```text
src/market_intel/
├── cli.py
├── core/
│   ├── __init__.py
│   ├── models.py
│   ├── pool_loader.py
│   ├── normalize.py
│   ├── scoring.py
│   └── json_output.py
└── fixtures/
    ├── mock_quotes.json
    └── mock_holdings.json
tests/
├── test_pool_loader.py
├── test_cli_pool.py
├── test_hotspots.py
└── test_no_trading_advice.py
```

---

## 5. 样例验收

P0 完成后至少验证：

```bash
market-intel pool explain 002837 --json
market-intel pool explain 002261 --json
market-intel pool explain 002281 --json
market-intel pool explain 300604 --json
market-intel pool explain 603881 --json
```

每个输出必须包含：

- `facts`
- `signals`
- `risks`
- `questions`
- `data_quality_flags`
- `exposures`

P1 完成后至少验证：

```bash
market-intel hotspots --mock --json
market-intel holdings impact --mock --json
```

---

## 6. 残留风险

1. 原始池子来自 Markdown 转换，部分行结构错位。P0 只能做到可追踪和可告警，不能保证所有证券一次清洗正确。
2. 热点评分 v0 是解释性规则，不代表预测模型。
3. mock 行情只能验证链路，不代表真实盘面。
4. 后续接入真实行情时，需要重新校验停牌、复权、涨跌停、港美股时区和币种。
5. GUI 若提前做，会放大脏数据问题，应等 core 输出稳定后再做。

