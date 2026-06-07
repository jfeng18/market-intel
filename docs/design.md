# 设计

核心目标：把数据、持仓、证据和留痕组织成可复跑流程；CLI、agent、未来 GUI 共享同一套 core 口径。

## 架构

```text
CLI -> core -> data/runtime + examples
       |
       -> text reports
       -> JSON contracts
```

- `cli.py`：参数解析、输出选择、命令入口。
- `core/`：模型、导入、覆盖、扫描、组合、日报、agent 工作流。
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
-> journal save / compare
```

## 关键对象

- `PoolItem`：复盘池或基础清单标的。
- `Quote`：行情输入。
- `Holding`：持仓输入。
- `Hotspot`：行业、概念、链路强弱。
- `research_notes_v1`：研究证据。
- `journal`：日报和复盘笔记。

## 约束

- 文本给人读，JSON 给 agent 接力。
- 所有 JSON 输出使用统一外壳。
- 写入 runtime 前先 dry-run。
- 基础清单不等于研究完成。
- GUI 后置，只展示稳定结构，不重新计算评分。
- 禁止输出买卖指令、目标价、仓位建议。
