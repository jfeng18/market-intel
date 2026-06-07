# 产品定位

`market-intel` 是面向全 A 的个人复盘操作系统。

不做：

- 实时行情终端。
- 交易入口。
- 社区/资讯流。
- 黑盒诊股。
- 买卖建议、目标价、仓位建议。

## 差异化

1. **覆盖边界清楚**：区分 `confirmed/foundation/draft/missing/blocked`。
2. **持仓优先**：先看自己的持仓是否有行情、覆盖、证据和风险。
3. **agent 可接力**：输出稳定 JSON、`next_commands`、`done_when`。
4. **证据闭环**：基础清单只说明“存在”，研究证据齐全才算 `confirmed`。
5. **journal 留痕**：每天的判断能被下一次复盘验证或推翻。

## 默认路径

```text
status runtime
-> dashboard / agent briefing
-> pool coverage / scan / portfolio review
-> pool universe / pool research
-> import --dry-run
-> import --runtime
-> journal save / note / compare
```

## 全 A 原则

- `all-a` 是默认目标范围。
- AI 池只保留为种子样例和回归测试底座。
- 新板块优先沉到通用字段：行业、概念、指数成分、研究状态、持仓覆盖、风险暴露。
- 不为每个板块写一套特殊规则，除非字段可验证、可复用、能进入 JSON contract。

## 功能准入

新增能力必须至少满足一项：

- 减少复盘遗漏。
- 让覆盖边界更清楚。
- 连接持仓、市场、证据或 journal。
- 给 agent 稳定读取路径和下一步命令。
- 改善本地隐私和可审计性。

坚决避免：

- 只增加信息量，不进入复盘闭环。
- 只输出结论，没有证据和完成标准。
- 依赖私有账号或云端个人数据。
- 把 seed 覆盖包装成完整全 A 结论。

## 当前优先级

P0：

- 全 A 基础清单字段补齐。
- `pool coverage` / `dashboard` 覆盖边界更清楚。
- `pool universe` / `import universe --dry-run` 补数闭环。

P1：

- 研究证据闭环：`pool research -> import research -> coverage -> agent next`。
- 持仓复核卡片更短、更可执行。

P2：

- journal 假设跟踪。
- 轻量 GUI，只展示 core/CLI 已稳定结构。
