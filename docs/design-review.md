# market-intel 设计审查

> 日期：2026-05-22
> 审查人：设计审查
> 输入文档：`docs/design.md` v0.1、`docs/handoff.md`、AI 能量公式 CSV
> 输出目标：让开发阶段可以按清晰边界开发 P0/P1，不把系统做成追涨或漂亮空壳。

---

## 1. 总体判断

方向成立，但原始设计的 MVP 过宽。宏观、行业、个股、消息、资金行为、GUI、adapter 同时推进，会导致第一版既难测试，也难判断输出是否可信。

已在 `docs/design.md` v0.2 中把首版拆为：

- P0：离线池子解释器。
- P1：mock 热点与 mock 持仓影响。
- P2：真实行情与轻量 GUI。

这个拆法保留原始愿景，但先把最重要的主数据、JSON 契约和风控边界做稳。

---

## 2. 必须修正项

### 2.1 原始 CSV 不能直接当证券主数据

检查结果：

- CSV 记录数：354。
- `priority` 分布：P1 109、P2 135、P3 110。
- `section` 数量：45。
- `code` 疑似非标准证券代码：85 条。
- 重复 code：47 个。

典型问题：

- `code=科创板`、`code=港股` 代表上市状态，不是证券代码。
- `code=—` 代表非证券或信息行。
- 部分行出现 `company=🇨🇳 硅片`、`code=沪硅产业`，属于 Markdown 表格列错位。
- `链路五：光通信升级周期` 下有国产化率/环节说明，不应进入证券热点计算。

设计结论：

- Loader 必须保留 raw 字段。
- Loader 必须生成标准化字段。
- 非证券行和字段错位必须进入 `data_quality_flags`。
- 同一 symbol 多链路出现时，合并为一个 PoolItem，并保留 exposures。

### 2.2 CLI / GUI 必须共享 core

设计里已经写了“双入口共享口径”，但开发时最容易变成 CLI 一套、GUI 一套。

必须约束：

- 评分、解释、风险都在 `core/` 或 `engines/` 内实现。
- CLI 只做参数解析和 JSON 输出。
- GUI 只消费 core/API 输出，不重新计算热点。

### 2.3 禁止买卖建议需要变成字段级约束

“不做自动交易”不能只写原则，必须落到 schema 和测试。

禁止字段：

- `action=buy/sell/hold`
- `recommendation=buy/sell/hold`
- `target_price`
- `position_size`
- `must_buy/must_sell`

P0/P1 测试应扫描 JSON 输出，确保不出现这些字段。

### 2.4 热点评分需要单位和归一化

原始公式混合了涨幅、成交额放大、家数、持续天数和惩罚项，量纲不同，不能直接相加。

已调整为：

- 每个子项先归一到 0-100。
- 总分裁剪到 0-100。
- 输出完整 `score_breakdown`。
- `signals` 和 `risks` 同级展示。

### 2.5 Adapter 必须默认只读

外部私有系统和外部市场状态源都只能作为只读输入源。任何写入必须是后续显式命令，且不能在 P0/P1 做。

---

## 3. 可延后项

以下内容保留在愿景里，但不进入 P0/P1：

- 宏观 regime 自动判断。
- 真实新闻扫描。
- 外资投研/会议材料自动抓取。
- 复杂 GUI。
- 实时高频盘口。
- 真实外部私有系统 adapter。
- 机器学习评分。
- 自动写入任何外部系统。

---

## 4. 建议的 P0 实现顺序

1. `docs/data-model.md` 对齐数据模型和 JSON 契约。
2. 建 `src/market_intel/core/models.py`。
3. 建 `src/market_intel/core/pool_loader.py`。
4. 读取 `data/pools/ai_energy_pool_2026-05-19.csv`。
5. 实现 section 到 layer/sub_sector 的映射。
6. 实现 symbol/market/instrument_type/tradable 推断。
7. 合并重复 symbol exposures。
8. 实现 `market-intel pool list --json`。
9. 实现 `market-intel pool explain <symbol> --json`。
10. pytest 覆盖英维克、拓维信息、光迅科技、长川科技、数据港。

---

## 5. 建议的 P1 实现顺序

1. 建 mock quote fixture。
2. 建 mock holding fixture。
3. 实现 Quote / Hotspot / HoldingExposure。
4. 实现 hotspot score breakdown。
5. 实现风险标签：重复暴露、追高、一日游、后排。
6. 实现 `market-intel hotspots --mock --json`。
7. 实现 `market-intel holdings impact --mock --json`。
8. pytest 覆盖评分、风险、禁止买卖建议字段。

---

## 6. 验收问题

交给开发阶段前，需要接受以下验收问题：

1. `pool explain 002837` 能否说明英维克在哪个 layer/sub_sector/role，且不输出买卖指令？
2. `pool explain 002261` 能否说明拓维信息和华为/昇腾/信创服务器链路的关系？
3. `pool explain 002281` 能否展示光迅科技的多链路暴露？
4. `pool explain 300604` 能否展示长川科技在半导体设备和存储测试链路的重复暴露？
5. `pool explain 603881` 能否识别数据港的 AIDC/IDC 属性？
6. `hotspots --mock` 是否能输出子链路排行和完整 score_breakdown？
7. `holdings impact --mock` 是否能识别同链路集中暴露？
8. 所有命令失败时是否仍返回统一 JSON 外壳？
9. JSON 输出是否完全不包含买/卖/持有、目标价、仓位建议？
10. 数据质量告警是否能解释为什么某些原始行没有进入热点计算？
