# 产品

`market-intel` 是面向全 A 的本地复盘工作台。

## 不做

- 实时行情终端。
- 交易入口。
- 资讯流或社区。
- 黑盒诊股。
- 买卖建议、目标价、仓位建议。

## 差异化

- 覆盖边界清楚：`confirmed/foundation/draft/missing/blocked`。
- 持仓优先：先看自己的票是否缺行情、缺覆盖、缺证据或暴露集中。
- 证据闭环：基础清单只说明存在，研究证据齐全才算 confirmed。
- agent 可接力：稳定 JSON、`next_commands`、`done_when`。
- journal 留痕：每天的判断能被下一次复盘验证或推翻。

## 默认流程

```text
status runtime
-> dashboard / agent briefing
-> coverage / scan / portfolio review
-> universe / research 补数
-> import --dry-run
-> import --runtime
-> journal save / compare
```

## 全 A 原则

- `all-a` 是默认目标范围。
- AI 池只作为种子样例和回归底座。
- 新板块沉到通用字段：行业、概念、指数成分、研究状态、持仓覆盖、风险暴露。
- 不为每个板块写特殊规则，除非字段可验证、可复用、能进入 JSON contract。

## 路线

P0：全 A 基础清单、覆盖边界、补数 dry-run。

P1：研究证据闭环、候选队列、持仓复核卡片。

P2：journal 假设跟踪、轻量 GUI。
