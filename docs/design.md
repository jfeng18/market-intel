# market-intel 首版设计文档

> 版本：v0.2 reviewed
> 日期：2026-05-22
> 项目定位：独立市场情报系统 / 投研雷达 / 人机共用分析平台

---

## 0. 一句话定义

`market-intel` 是一个独立的市场情报系统：以全 A 复盘池为目标 universe，整合宏观经济、行业景气、个股质量、消息驱动、资金行为和个人持仓，帮助人和 agent 判断：**市场真正追捧的是哪条链、哪类资产、哪种逻辑，以及当前复盘还缺哪些证据。**

它不是自动交易系统，不输出“买/卖/持有”指令；它输出结构化事实、信号、解释、风险和待验证问题。

---

## 1. 为什么要做

### 1.1 当前问题

现在的研究工作是分散的：

- HTML / 文章 / 研报 / 博主观点需要人工逐篇读。
- 股票池很大，但缺少统一结构化入口。
- 盘中看到异动后，容易只盯单票，不知道资金打的是哪条产业链。
- 持仓、观察池、外部观点、公司档案分别散在不同系统里。
- 人类需要可视化，agent 需要稳定 JSON；单纯 CLI 不够，单纯 GUI 也不够。

成熟股票 App 已经擅长实时行情、交易入口、资讯流、社区讨论、研报检索、条件选股和基础诊股。`market-intel` 的竞争力不在替代这些入口，而在把外部输入和本地数据组织成可复盘、可追踪、可交接的个人工作流。

### 1.2 核心目标

建立一个从“宏观 → 行业 → 个股 → 消息 → 资金行为”的全链路雷达：

1. 先有大池子，不临时乱找票。
2. 每天自动识别异动、热点、资金追捧。
3. 区分真共振和一日游。
4. 把持仓和观察池放进同一张地图里看。
5. 让人用 GUI 看全局，让 agent 用 CLI 做自动化分析。

### 1.3 竞争力

`market-intel` 的差异化能力：

- 个人复盘闭环：从全 A 复盘池、主题链路、行情/持仓输入、风险暴露、复核清单到 journal 留痕。
- agent-native：核心命令输出稳定 JSON、readiness 状态、下一步命令队列、完成标准和边界说明。
- 持仓优先：检查个人持仓是否被复盘池覆盖、是否重复暴露、是否缺行情或缺热点上下文。
- 可解释结构化：区分事实、信号、风险、待验证问题，不把黑盒分数伪装成结论。
- 本地私有数据友好：默认只读取仓库数据、示例数据和用户提供的 runtime 文件。

完整产品定位、竞争边界和下一阶段优先级见 `docs/product.md`。

---

## 2. 设计原则

### 2.1 独立项目

`market-intel` 必须是独立仓库，默认不依赖外部私有系统。后续可以通过 adapter 接入行情、公告、研报、持仓、公司档案或市场状态数据，但核心命令必须在离线示例数据上可测试、可运行。

原则：**可调用、可吸收、不污染、可脱离外部服务运行。**

### 2.2 CLI + GUI 双入口

- CLI 给 agent 使用，必须稳定、可脚本化、可输出 JSON。
- GUI 给人使用，必须直观、可解释、能快速看出热点与风险。
- CLI 和 GUI 共享同一套数据、评分、解释，不允许两个入口各说各话。

### 2.3 不做自动交易

系统只回答：

- 什么在动？
- 为什么动？
- 是单票还是板块？
- 是真共振还是轮动噪音？
- 持仓是否受益或承压？
- 是否出现重复暴露？
- 有哪些风险和待验证问题？

系统不回答：

- 你现在必须买什么。
- 你现在必须卖什么。
- 自动下单。

---

## 3. 总体架构

```text
market-intel/
├── README.md
├── pyproject.toml
├── docs/
│   ├── design.md              # 本文档
│   ├── product.md             # 后续产品说明
│   ├── data-model.md          # 数据模型与 JSON 契约
│   ├── design-review.md       # 设计审查意见
│   └── review.md              # 开发前 review 结论
├── data/
│   ├── pools/                 # 大池子：AI能量公式、观察池等
│   ├── runtime/               # 运行期数据，不入 git
│   └── cache/                 # 行情/新闻缓存，不入 git
├── src/market_intel/
│   ├── cli.py                 # CLI 入口
│   ├── core/                  # 核心数据模型、评分、解释
│   ├── adapters/              # 对接现有 CLI / 数据源
│   ├── engines/               # 宏观/行业/个股/消息/异动引擎
│   ├── gui/                   # GUI 后端接口或前端桥接
│   └── services/              # 定时任务、数据同步
└── tests/
```

---

## 4. 核心数据底座：全 A 复盘池

### 4.1 来源

当前默认池子：

- `all-a`：面向全 A 的目标 universe，目前以种子覆盖运行。
- `ai-energy`：保留为主题池，用于 AI 算力、运力、存力、电力等链路的结构化样例。

首批种子数据来自：

- `data/pools/ai_energy_map_2026-05-17.md`
- `data/pools/ai_energy_pool_2026-05-19.csv`

当前提取结果：

- 表格记录：354 条
- 子节：约 45 个
- 初步分层：P1 / P2 / P3

### 4.2 原始池子质量边界

`ai_energy_pool_2026-05-19.csv` 是原始研究池，不是已经清洗完成的证券主数据。开发时必须保留原始字段，同时生成标准化字段。

当前已知问题：

- `code` 字段不总是可交易代码，存在 `科创板`、`港股`、`—`、公司名、国产化率等表格错位值。
- 同一证券会出现在多个子链路中，这是合理的多链路暴露，不应简单去重。
- 部分 Markdown 表格列结构不同，CSV 中 `company/code/desc` 可能发生错位。
- `level` 字段大量为空，不能作为唯一角色来源。
- 原始池子包含非公司条目，例如缺口、国产化率、环节说明等，需要标记为 `instrument_type=non_security` 或进入数据质量告警。

首版 loader 要做两件事：

1. 原样保留 `raw_status/raw_priority/raw_section/raw_level/raw_company/raw_code/raw_desc/raw_notes`。
2. 派生 `symbol/name/market/layer/sub_sector/role/logic/priority/tradable/data_quality_flags`。

全 A 化的下一步是接入更完整的 A 股基础池，包括行业、概念、指数成分、自选股和持仓导入。任何全市场结论都必须标明当前覆盖范围，`all-a` 在完整基础池接入前只能标记为种子覆盖。

### 4.3 标的标准字段

每个标的至少应有：

| 字段 | 含义 |
|---|---|
| `symbol` | 股票代码 |
| `name` | 股票名称 |
| `market` | A股 / 港股 / 美股 / 其他 |
| `instrument_type` | security / pending_listing / index_or_theme / non_security / unknown |
| `layer` | 算力 / 运力 / 存力 / 电力 / 人才密度 |
| `sub_sector` | AI服务器 / 光模块 / HBM / 液冷等 |
| `role` | 龙头 / 龙二 / 梯队 / 后排 / 弹性 |
| `logic` | 一句话核心逻辑 |
| `priority` | P1/P2/P3 |
| `tradable` | 是否可交易 |
| `profile_status` | 是否已有公司档案或基础资料 |
| `research_status` | 是否已有研究证据或观点记录 |
| `validation_signals` | 后续验证信号 |
| `exposures` | 同一证券在不同链路中的暴露列表 |
| `data_quality_flags` | 代码异常、字段错位、非证券条目、重复归属等 |

### 4.4 标准化规则 v0

首版不追求一次清洗完所有历史脏数据，但必须保证输出可解释、可追踪、可测试。

| 原始情况 | v0 处理 |
|---|---|
| 6 位数字代码 | 视为 A 股候选，按首位推断 `SSE/SZSE/BSE` 或先标 `CN_A` |
| 全大写美股代码，如 `NVDA` | 标为 `US` |
| 带后缀代码，如 `2382.TW`、`005930.KS` | 按后缀标市场 |
| `科创板`、`港股`、`IPO 已过会` | `instrument_type=pending_listing`，`tradable=false` |
| `—`、国产化率、缺口描述 | `instrument_type=non_security`，默认不进入热点计算 |
| `company/code/desc` 疑似错位 | 尽量恢复 `name/symbol/logic`，并写入 `data_quality_flags` |
| 同一 symbol 多行 | 合并为一个 PoolItem，保留多条 `exposures` |

### 4.5 关键认知

AI 产业链不是“一个 AI 概念”。它应按公式拆开：

```text
AI 推理/Agent 能力 = AI 算力 × AI 人才密度 × AI 电力
AI 算力 = 算力 × 运力 × 存力
```

交易上必须追问：

- 资金今天打的是算力、运力、存力、电力，还是应用？
- 是核心瓶颈，还是后排蹭概念？
- 是趋势主线，还是一日轮动？

---

## 5. 四层分析框架

## 5.1 宏观层 Macro

### 目标

判断大环境是顺风、逆风，还是高不确定性。

### 关注维度

| 维度 | 例子 |
|---|---|
| 经济增长 | GDP、PMI、消费、出口、地产、就业 |
| 政策 | 财政政策、产业政策、监管政策、地方政策 |
| 货币 | 利率、降准降息、流动性、汇率、美联储 |
| 地缘政治 | 中美、台海、俄乌、中东、关税、制裁 |
| 黑天鹅 | 疫情、战争、金融机构暴雷、自然灾害、供应链中断 |

### 输出

```json
{
  "macro_regime": "neutral_to_supportive",
  "risk_flags": ["geopolitical_tension", "fed_uncertainty"],
  "support_flags": ["domestic_policy_support", "liquidity_stable"],
  "impact": "AI hardware risk appetite can recover, but position sizing should remain controlled."
}
```

## 5.2 行业层 Industry

### 目标

判断产业链景气度、供需关系、空间和生命周期。

### 关注维度

| 维度 | 例子 |
|---|---|
| 景气度 | 订单、价格、开工率、库存、产能利用率 |
| 供需 | 供给紧缺/过剩、需求扩张/收缩 |
| 空间 | TAM、渗透率、国产替代空间 |
| 生命周期 | 导入期、成长期、成熟期、衰退期 |
| 周期属性 | 存储从强周期转向 AI 拉动成长？ |
| 产业链位置 | 上游材料、中游设备、下游应用 |

### 输出

```json
{
  "sub_sector": "liquid_cooling",
  "cycle_stage": "growth",
  "supply_demand": "demand_accelerating",
  "hotness_score": 82,
  "risk": "valuation and one-day rotation risk"
}
```

## 5.3 个股层 Company

### 目标

判断公司是不是硬逻辑，还是蹭概念。

### 关注维度

| 维度 | 例子 |
|---|---|
| 护城河 | 技术、客户、渠道、成本、牌照、生态位 |
| 订单 | 在手订单、合同负债、中标、交付节奏 |
| 成长性 | 收入、利润、扣非、现金流、毛利率 |
| 估值 | 当前估值是否透支 |
| 板块效应 | 板块核心 / 后排补涨 / 蹭概念 |
| 资金属性 | 趋势票 / 情绪票 / 机构票 / 游资票 / 量化票 |
| 风险 | 应收账款、存货、商誉、减持、监管、治理问题 |

### 输出

```json
{
  "symbol": "002837",
  "name": "英维克",
  "company_quality": "strong",
  "sector_role": "liquid_cooling_leader",
  "moat": ["data_center_temperature_control", "liquid_cooling_solution"],
  "risks": ["valuation", "order_confirmation"],
  "explain": "Strong thematic and business fit in AI power/cooling layer."
}
```

## 5.4 消息驱动层 News / Event

### 目标

识别国内外重要消息、研报、论坛讨论和龙头公司高管讲话，并判断影响范围与持续性。

### 来源类型

| 类型 | 例子 |
|---|---|
| 国内新闻 | 财联社、证券时报、央视财经、交易所公告 |
| 国内社区 | 淘股吧、雪球、微信公众号 |
| 券商研报 | 中金、华泰、国君、招商等 |
| 外资投研 | Morgan Stanley、Goldman Sachs、JPMorgan、Citi 等 |
| 海外龙头 | NVIDIA、AMD、TSMC、Broadcom、Microsoft、Meta、Google、OpenAI |
| 行业会议 | GTC、Computex、ISSCC、Hot Chips、华为大会、WAIC |
| 黑天鹅 | 战争、疫情、制裁、金融风险、供应链中断 |

### 消息评级

| 等级 | 含义 |
|---|---|
| S | 改变产业预期或政策框架 |
| A | 影响一个子行业数周以上 |
| B | 影响一组标的数日 |
| C | 当日情绪刺激 |
| D | 噪音或重复消息 |

---

## 6. 资金行为与热点识别

## 6.1 异动指标

基础行情指标：

- 涨幅
- 涨速
- 成交额
- 成交额变化
- 量比
- 换手率
- 振幅
- 是否突破平台
- 是否创阶段新高
- 是否涨停 / 连板 / 反包 / 首板

## 6.2 板块共振识别

不能只看单票，要看同一子链路是否多点共振。

例子：

```text
光模块/CPO：光迅科技、天孚通信、联特科技、华工科技
液冷：英维克、高澜股份、申菱环境、川润股份
半导体设备：北方华创、中微公司、长川科技、江丰电子
AI服务器：工业富联、浪潮信息、拓维信息、神州数码
```

## 6.3 热点强度评分 v0

首版可用简单可解释评分：

```text
hotspot_score =
  avg_change_score * 0.20
+ turnover_expansion_score * 0.20
+ strong_member_score * 0.20
+ leader_strength_score * 0.20
+ persistence_score * 0.10
- intraday_fade_penalty * 0.10
```

所有子项先归一到 0-100，最终分数裁剪到 0-100。评分必须可解释，不追求一开始就复杂。

v0 mock 行情字段：

| 字段 | 含义 |
|---|---|
| `symbol` | 标准化代码 |
| `last_price` | 最新价，可为空 |
| `change_pct` | 涨跌幅百分比 |
| `amount` | 成交额 |
| `amount_ratio` | 成交额相对基准放大倍数 |
| `turnover_rate` | 换手率 |
| `amplitude_pct` | 振幅 |
| `is_limit_up` | 是否涨停 |
| `is_stage_high` | 是否阶段新高 |
| `intraday_fade_pct` | 冲高回落幅度 |

## 6.4 资金追捧判断

输出需要区分：

- 龙头主动强
- 后排补涨
- 板块共振
- 单票异动
- 一日游
- 高位兑现
- 缩量虚涨
- 放量突破

---

## 7. CLI 设计

CLI 给 agent 用，必须稳定 JSON。

### 7.1 命令草案

```bash
market-intel pool list --pool ai-energy --json
market-intel pool explain 002837 --json
market-intel scan --date today --pool ai-energy --json
market-intel hotspots --date today --top 10 --json
market-intel anomaly --date today --pool ai-energy --json
market-intel macro brief --date today --json
market-intel industry brief --sector liquid-cooling --json
market-intel company brief 002837 --json
market-intel news scan --query "NVIDIA GTC AI server liquid cooling" --json
market-intel holdings impact --json
```

### 7.2 P0 必须实现的 CLI

P0 只实现离线、可测试、无外部依赖的命令：

```bash
market-intel pool list --pool ai-energy --json
market-intel pool explain 002837 --json
market-intel hotspots --mock --json
market-intel holdings impact --mock --json
```

P0 不接真实行情、不接真实新闻、不读写外部私有系统，只使用本仓库数据和 mock fixtures。

### 7.3 输出原则

所有命令输出：

```json
{
  "ok": true,
  "command": "hotspots",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "generated_at": "...",
    "schema_version": "0.1"
  }
}
```

失败也必须输出同一外壳，`ok=false`，错误写入 `errors`，不要把 traceback 作为 JSON 数据返回。

所有事实类输出必须区分：

- `facts`：从数据源可追溯得到。
- `signals`：规则计算得到。
- `explain`：系统解释。
- `risks`：风险和证伪条件。
- `questions`：待验证问题。

禁止输出字段：

- `action=buy/sell/hold`
- `recommendation=buy/sell/hold`
- `target_price`
- `position_size`
- `must_buy/must_sell`

---

## 8. GUI 设计

GUI 给人用，核心是降低认知负担。

### 8.1 首页 Dashboard

模块：

1. 今日市场温度
2. 今日最强子链路 Top 10
3. AI 能量公式热力图
4. 异动标的榜
5. 持仓影响
6. 观察池提醒
7. 重大消息流
8. 风险提示

### 8.2 AI 产业链地图页

以公式为主结构：

```text
AI 能力
├── 算力
│   ├── 芯片
│   ├── AI服务器
│   ├── 半导体设备
│   └── AIDC
├── 运力
│   ├── 光模块
│   ├── CPO
│   ├── PCB
│   └── 铜互连
├── 存力
│   ├── DRAM
│   ├── NAND
│   └── HBM
├── 电力
│   ├── 液冷
│   ├── 储能/UPS
│   ├── 核电
│   └── 输配电
└── 人才密度
```

每个节点显示：

- 今日涨幅
- 成交额变化
- 龙头
- 异动家数
- 消息数量
- 持仓关联

### 8.3 个股页

展示：

- 公司基础信息
- 所属链路
- 角色定位
- 资金异动
- 消息驱动
- 公司档案摘要
- 研究证据和观点记录
- 风险点
- 待验证问题

---

## 9. Adapters 设计

## 9.1 holdings adapter

读取：

- 当前持仓
- 可卖数量
- 成本
- 行为标签

用途：

- 判断持仓是否受益
- 判断重复暴露
- 判断仓位压力

## 9.2 research adapter

读取：

- source
- report
- claim
- claim status
- validation signals

用途：

- 消息层解释
- 行业/个股逻辑验证
- 信源质量回顾

## 9.3 company adapter

读取：

- 公司档案
- 核心逻辑
- 风险点
- 待验证问题

用途：

- 个股质量解释
- 是否已有研究基础
- 是否需要补档案

## 9.4 market regime adapter

读取：

- 市场状态
- 风险偏好
- 持仓相对强弱

用途：

- 宏观/市场温度输入

---

## 10. 数据源规划

### 10.1 第一阶段可用源

- 腾讯实时行情接口
- AkShare / 东方财富行情
- 本地研究观点记录
- 本地公司档案
- 用户导入的持仓
- 用户手工导入的 HTML / 研报 / 文章

### 10.2 后续增强源

- 国内公告
- 财联社 / 证券时报 / 央视财经
- 微信公众号 / 淘股吧 / 雪球
- 券商研报
- 海外搜索：Morgan Stanley / Goldman Sachs / JPMorgan / Citi
- 英伟达、AMD、台积电、博通等公司官网、财报、会议实录
- 行业会议与论坛

---

## 11. MVP 范围

### MVP 目标

先做一个可用的“全 A 种子复盘雷达”，不一开始追求全能。

### 11.1 P0：离线池子解释器

目标：无网络、无外部系统依赖，先让 agent 稳定读取和解释默认复盘池。

必须完成：

1. 读取默认复盘池 CSV。
2. 标准化 `symbol/name/market/layer/sub_sector/role/priority/tradable`。
3. 标记 `instrument_type` 和 `data_quality_flags`。
4. 合并同一证券的多链路 `exposures`。
5. `market-intel pool list --pool all-a --json`。
6. `market-intel pool explain <symbol> --json`。
7. pytest 覆盖 CSV 解析、字段错位、重复暴露、JSON 外壳。

验收样例必须覆盖：

- 英维克 `002837`
- 拓维信息 `002261`
- 光迅科技 `002281`
- 长川科技 `300604`
- 数据港 `603881`

### 11.2 P1：mock 热点与持仓影响

目标：用 mock 行情和 mock 持仓跑通评分链路，不接真实交易和真实行情。

必须完成：

1. 定义 Quote / Hotspot / HoldingExposure。
2. 用 fixture 更新当日行情。
3. 输出热点子链路排行。
4. 输出异动标的排行。
5. `market-intel hotspots --mock --json`。
6. `market-intel holdings impact --mock --json`。
7. 输出风险提示：重复暴露、追高、一日游、后排。
8. pytest 覆盖热点评分、风险提示、mock 持仓重复暴露。

### 11.3 P2：真实数据与轻量 GUI

目标：在 CLI 契约稳定后，再接真实行情和最小 GUI。

可做：

1. 手工或脚本更新当日行情。
2. 接入 AkShare / 东方财富 / 腾讯行情中的一个。
3. GUI 暂时可以先是本地静态页面或轻量 Web 页面。
4. GUI 只展示 CLI/core 已稳定输出，不另写一套解释逻辑。

### 暂不做

- 自动交易
- 复杂机器学习
- 实时高频盘口
- 一开始接入所有海外数据源
- 一开始做复杂 GUI
- 自动写入外部私有系统

---

## 12. 里程碑

### M0：项目骨架与池子标准化

- 建仓库
- 迁入 AI 能量公式池子
- 设计数据模型
- 能 list / explain 一个标的
- 记录数据质量告警
- 合并多链路暴露

### M1：行情扫描与热点识别

- 用 mock 行情先跑通评分
- 计算异动指标
- 计算子链路热度
- 输出 JSON 报告

### M2：持仓联动

- 用 mock 持仓先跑通重复暴露识别
- 显示持仓受益/承压
- 识别重复暴露

### M3：观点与公司档案联动

- 只读接入研究记录和公司档案
- 输出逻辑解释和待验证问题

### M4：GUI MVP

- 首页 dashboard
- 产业链热力图
- 个股详情页

### M5：宏观与消息驱动增强

- 宏观简报
- 国内外消息扫描
- 重要消息影响评级

---

## 13. 风险与防护

### 13.1 最大风险：系统变成追涨机器

防护：

- 输出“风险”和“证伪条件”必须和“机会”同级展示。
- 默认不输出买卖信号。
- 高涨幅、高拥挤、高冲高回落必须警告。

### 13.2 数据噪音

防护：

- 记录来源和时间。
- 区分公告、研报、博主、论坛、传闻。
- 每个信号必须有置信度。

### 13.3 GUI 漂亮但无用

防护：

- 先 CLI 和数据模型，再 GUI。
- GUI 只展示已有稳定字段，不手工编故事。

### 13.4 和外部系统边界混乱

防护：

- adapters 默认只读外部数据，写入必须显式命令。
- market-intel 不替代行情、交易、研究、档案或社区系统。

---

## 14. 产品意义

这个项目不是为了“找到神票”，也不是为了复制一个行情 App。

它真正服务三件事：

1. **看清资金在哪一层。** 不是所有题材都处在同一个产业位置。
2. **避免重复暴露。** 同一持仓组合可能在主题、客户、供应链或情绪风格上高度重叠。
3. **让交易有上下文。** 宏观、行业、个股、消息、资金行为同时看，而不是只看分时。

最终目标：

> 少追噪音，多等共振；少靠感觉，多靠结构；少做赌徒，多像交易员。

---

## 15. 下一步

建议下一步不是立刻写 GUI，而是先完成：

1. `docs/data-model.md`：定义 PoolItem / Quote / Hotspot / NewsEvent / CompanySignal。
2. `market-intel pool list`：读取 CSV 输出 JSON。
3. `market-intel pool explain <symbol>`：解释某标的在哪条链。
4. `market-intel hotspots --mock`：用模拟行情跑通热点评分。
5. `market-intel holdings impact --mock`：用模拟持仓跑通重复暴露。
6. 写 `docs/review.md`，用于开发前对齐边界。
