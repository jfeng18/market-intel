# market-intel 产品定位与竞争力

> 日期：2026-06-07
> 范围：全 A 复盘工作台 / agent-native 投研流程

## 1. 基本判断

成熟股票 App 已经覆盖实时行情、交易入口、财经资讯、社区讨论、智能选股、研报数据和基础个股分析。`market-intel` 不应该把资源投入到复制这些入口。

它应该成为“复盘后的工作系统”：把外部 App、行情源、持仓文件和用户判断组织成一个可复核、可接力、可留痕的每日流程。

一句话定位：

```text
market-intel 是面向全 A 的个人复盘操作系统，不是行情 App、交易 App 或买卖建议引擎。
```

## 2. 不正面竞争的能力

这些能力已有强势产品和数据壁垒，不作为短期主战场：

- 实时行情、盘口、Level-2 和交易通道。
- 资讯流、快讯、社区互动和大 V 内容分发。
- 券商账户、下单、组合交易和资金管理。
- 通用条件选股、技术指标画线和传统行情终端。
- 黑盒 AI 诊股、目标价、买卖点和仓位建议。

`market-intel` 可以接入这些输入，但不把它们当作核心差异化。

## 3. 我们的赢面

竞争力不来自“比行情 App 更像行情 App”，而来自把用户每天真实要完成的复盘动作做成结构化闭环。成熟 App 解决的是信息获取、交易入口和通用分析；`market-intel` 解决的是“我今天基于自己的持仓、证据和历史留档，该先复核什么，为什么，怎样算完成”。

### 3.1 个人复盘闭环

核心价值是把每天的复盘拆成可执行步骤：

1. 今天市场在追哪几条链路。
2. 我的持仓是否在这些链路里。
3. 哪些持仓缺行情、缺池子覆盖或缺解释。
4. 哪些主题/链路出现重复暴露。
5. 今天要先复核哪几只票、为什么、完成标准是什么。
6. 复核结论如何写入 journal，下一次怎么回看。

这比“给一个分数”更有价值，因为它能减少盘后复盘的遗漏和漂移。

### 3.2 持仓优先

大多数行情工具从市场热度出发，用户再手工映射到自己的组合。`market-intel` 的默认视角应该反过来：

- 先看持仓是否被全 A 复盘池覆盖。
- 再区分覆盖是 `confirmed`、`draft`、`foundation` 还是 `missing`。
- 再看持仓在热点、风险、重复暴露中的位置。
- 最后给出补池、补行情、补行业/主题逻辑、补证据和单票复核命令。

这让系统更像用户自己的投研台账，而不是另一个通用资讯入口。

尤其是全 A 方向，基础证券清单只能说明“这只票存在且有行业/概念字段”，不能说明已经完成研究覆盖。`foundation` 标的必须继续输出待补证据、证伪风险和 journal 模板，不能被当作已确认池内标的。

当前实现用 `research_notes_v1` 作为轻量研究证据层：一只基础清单标的只有在 `status=reviewed` 且核心逻辑、关键证据、证伪风险三项齐全时，才会从 `foundation` 升级为 `confirmed`。这让“覆盖率提升”不是因为股票被导入了，而是因为研究证据闭环完成了。

`pool research` 则把 foundation 持仓导出成可编辑的 research notes 待办 CSV。它不替用户写结论，只把缺口变成明确的 `symbol/name/status/thesis/evidence/invalidation` 工作项，方便人补证据、agent 校验导入、coverage 复跑验证。

### 3.3 agent-native

每个核心输出都必须给 agent 稳定读取路径：

- `ok/errors/warnings/readiness`：先判断能不能继续。
- `agent_contract.stable_fields`：告诉外部 agent 哪些字段可依赖。
- `next_commands/command_queue`：给下一步动作，而不是只给自然语言。
- `done_when`：让复核有完成标准。
- `requires_prior_command`：避免 agent 跳过留档、校验或人工确认。

这类结构化接力能力是通用股票 App 很难优先满足的。

### 3.4 可解释与可审计

系统必须区分：

- 事实：行情、持仓、池子归属、数据质量。
- 信号：热点强度、链路共振、成交放大、回落。
- 风险：追高、一日游、重复暴露、缺上下文。
- 待验证问题：还需要用户或 agent 查证的点。
- 边界：当前覆盖是否只是 seed，是否缺数据，是否不能当作全市场结论。

任何报告都不应该把黑盒分数包装成买卖建议。

### 3.5 本地私有数据友好

用户可以把持仓和行情放在 runtime 文件里，本仓库只输出本地复盘结果。文档、示例和默认输出不应暴露用户身份、真实持仓路径或本机目录。

### 3.6 与股票 App 的差异

| 维度 | 常见股票 App | market-intel |
| --- | --- | --- |
| 默认入口 | 行情、资讯、社区、交易 | runtime readiness、持仓覆盖、今日复核队列 |
| 解释对象 | 个股或板块的通用信息 | 用户持仓在全 A/主题池/热点/风险中的位置 |
| 输出形态 | 页面、资讯流、指标、诊股结论 | JSON 契约、命令链、done_when、journal 模板 |
| 研究状态 | 通常弱化数据覆盖边界 | 明确 `confirmed/draft/foundation/missing` |
| 决策边界 | 容易滑向买卖点和推荐 | 只做复盘、证据、风险和留档，不做交易指令 |

这意味着短期不追求“信息最全”，而是追求“每一次复盘最不容易漏、最容易接力、最容易回看”。

## 4. 最小可赢产品

短期最有价值的入口不是完整 GUI，而是以下闭环：

```text
import/runtime -> status/readiness -> pool coverage -> pool expansion review
-> focus/agent briefing -> agent next -> journal save/note/compare
```

这个闭环回答四个问题：

1. 今天能不能跑复盘。
2. 全 A 复盘池是否覆盖我的持仓。
3. 今天先看什么，为什么。
4. 这次判断如何留档，下次如何验证。

## 5. 全 A 方向

`all-a` 是默认目标 universe，但在完整基础池接入前必须继续标记为 seed 覆盖。全 A 化的优先级：

1. A 股基础证券清单：代码、名称、交易所、行业、上市状态。
2. 行业/概念/指数成分：形成基础链路，不局限于 AI。
3. 持仓驱动补池：从未覆盖持仓生成 `expansion_queue`，人工复核后叠加验证。
4. 研究证据闭环：用 `research_notes_v1` 记录核心逻辑、关键证据和证伪风险，关闭 `foundation` 待复核状态。
5. 覆盖状态分层：`confirmed/foundation/draft/missing/blocked`，避免把草稿或基础清单当成正式结论。
6. 热点与风险模型泛化：支持金融、消费、医药、周期、TMT、制造、能源等板块。

全 A 不是一次性导入大表，而是先建立覆盖状态和复核流程，逐步提高可解释覆盖率。

## 6. 北极星指标

项目不应只看命令数量或覆盖股票数量，应看复盘闭环是否完成：

- `daily_review_completed`：当天是否完成 readiness、focus、journal 留档。
- `confirmed_holding_coverage_ratio`：持仓被正式复盘池覆盖的比例。
- `unresolved_review_queue_count`：仍需人工复核的持仓/补池/数据问题数量。
- `agent_handoff_success`：`agent next` 是否能给出可继续执行的命令链。
- `hypothesis_followup_closed`：上一轮 journal 假设是否在本轮被验证或失效。

## 7. 下一阶段优先级

### P0：全 A 覆盖底座

- 引入 A 股基础清单和行业/概念/指数成分输入格式；当前可通过 `MARKET_INTEL_A_SHARE_UNIVERSE_PATHS` 叠加 `a_share_universe_v1` CSV。
- 让 `pool coverage` 明确展示全 A 覆盖范围、缺口和草稿状态。
- 保持所有输出不泄露本机路径和用户身份信息。

### P1：复盘工作台

- 强化 `focus` 和 `agent next`，让它们成为“今天先看什么”的默认入口。
- 把持仓覆盖、重复暴露、风险标签、数据缺口和 journal 前置条件合并成单票卡片。
- 每个单票卡片必须有 `why_now/checklist/done_when/note_command`。

### P2：证据与留档回路

- journal 不只保存日报，还要追踪上次假设、本次验证结果和未完成 follow-up。
- 把“缺证据”作为一等对象输出，而不是隐藏在自然语言里。
- 让 `import research`、`pool coverage`、`portfolio review` 和 `agent next` 共用同一套 research status，使人和 agent 都能看到证据是否足以关闭基础覆盖缺口。
- 用 `pool research` 把 foundation 缺口导出成可编辑队列，形成“发现缺口 -> 补证据 -> dry-run 校验 -> runtime 导入 -> coverage 复跑”的闭环。
- 让 `agent next` 的单票卡片和交接命令链直接承接 research workflow，避免 agent 只报告缺口却不给可执行路径。

### P3：轻量 GUI

- GUI 只展示 CLI/core 已稳定的结构，不重写解释逻辑。
- 第一屏展示数据状态、今日焦点、组合压力、补池队列和 journal 状态。

## 8. 产品边界

必须长期坚持：

- 不自动下单。
- 不输出买卖指令、目标价或仓位建议。
- 不把 seed 覆盖伪装成完整全 A 覆盖。
- 不把用户私有路径、身份信息或真实持仓细节写进公开文档。
- 不为了做“像 App”而牺牲 JSON 契约和可审计性。
