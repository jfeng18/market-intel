# 设计概览

`market-intel` 是本地全 A 复盘工具。核心不是替代行情 App，而是把数据、持仓、证据和留痕组织成可复跑流程。

## 架构

```text
CLI -> core -> data/runtime + examples
       |
       -> text reports for humans
       -> JSON contracts for agents
```

职责：

- `src/market_intel/cli.py`：参数解析、输出选择、命令入口。
- `src/market_intel/core/`：模型、导入、覆盖、扫描、组合、日报、agent 工作流。
- `data/pools/`：内置种子池。
- `data/runtime/`：用户本地数据，不提交。
- `examples/`：公开样例数据。

## 核心流程

```text
init runtime
-> import quotes/holdings/universe/research
-> status runtime
-> dashboard / agent briefing
-> pool coverage / scan / portfolio review
-> pool universe / pool research
-> import --dry-run
-> import --runtime
-> journal save / note / compare
```

## 关键对象

- `PoolItem`：复盘池或基础清单中的标的。
- `Quote`：行情输入。
- `Holding`：持仓输入。
- `Hotspot`：行业/概念/链路强弱结果。
- `research_notes_v1`：研究证据层。
- `journal`：日报和复盘笔记留痕。

## 覆盖状态

- `confirmed`：有 reviewed 研究证据。
- `foundation`：只命中 A 股基础清单。
- `draft`：来自临时补池草稿。
- `missing`：持仓未覆盖。
- `blocked`：数据错误或缺关键字段。

基础清单只说明“这只票存在且有分类字段”，不等于完成研究。

## 全 A 底座

`all-a` 是默认目标范围。全 A 能力依赖：

1. A 股基础清单：代码、名称、行业、概念、指数成分、上市状态。
2. 字段补数队列：`pool universe`。
3. 导入前复验：`import universe --dry-run --text/json`。
4. coverage 复跑：确认缺口是否减少。
5. 研究证据：`pool research -> import research -> coverage`。

## Agent 合同

核心 JSON 输出必须保留：

- `ok/errors/warnings`
- `data`
- `meta.generated_at`
- `next_commands` 或 `next_actions`
- `agent_contract.stable_fields`
- `done_when`，适用于任务队列项

文本输出服务人类阅读，不能替代 JSON contract。

## 禁止项

- 不输出买卖指令。
- 不输出目标价。
- 不输出仓位建议。
- 不自动下单。
- 不把 seed/foundation 覆盖包装成完整研究结论。
- 不把本机路径、账号、token、真实持仓写入公开文档。

## GUI 原则

GUI 后置。只有 core/CLI 输出稳定后才做界面；GUI 只展示稳定结构，不重新计算评分或解释。
