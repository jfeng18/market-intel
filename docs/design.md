# 设计

目标：CLI、人读文本、agent JSON 和未来 GUI 共用同一套 core 口径。

## 架构

```text
CLI -> core -> examples + data/runtime
       |
       -> text reports
       -> JSON contracts
```

- `core/`：模型、导入、覆盖、扫描、组合、日报、agent 工作流。
- `examples/`：公开样例。
- `data/runtime/`：用户本地数据，不提交。
- `data/pools/`：内置种子池和来源说明。

## 流程

```text
init runtime
-> status runtime
-> dashboard / agent briefing
-> coverage / scan / portfolio review
-> universe / research 补数
-> import --dry-run
-> import --runtime
-> journal save / compare
```

## 约束

- 文本给人读，JSON 给 agent 接力。
- 写入 runtime 前先 dry-run。
- 基础清单不等于研究完成。
- 同一证券多链路合并为一个标的，保留 `exposures[]`。
- GUI 只展示稳定结构，不重新计算评分。
- 禁止买卖建议、目标价、仓位建议。
