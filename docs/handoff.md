# market-intel 交接与分工

> 日期：2026-05-19  
> 目的：明确后续多 agent 协作边界，避免设计、开发、review、验收混在一起。

---

## 1. 总分工

| 角色 | 职责 | 产出 |
|---|---|---|
| Codex | 抠设计、抠 review、找边界漏洞、提出验收问题 | `docs/design-review.md`、`docs/review.md`、问题清单 |
| Claude | 按设计开发、补测试、跑验证、修复 review 问题 | 代码、测试、实现说明 |
| Livermore | 最终验收、接入工作流判断、确认是否真的可用于交易辅助 | `docs/acceptance-result.md` 或最终验收段落 |

---

## 2. Codex 阶段：设计审查 / Review

Codex 不急着写代码，先做设计和边界审查。

重点检查：

1. `docs/design.md` 是否足够清楚，Claude 能否直接照着开发。
2. CLI / GUI 是否共享同一套数据和评分口径。
3. 项目是否保持独立，不污染 tradegov / researchgov / companygov / decision-cockpit。
4. 是否明确“不输出买卖指令，只输出事实、信号、解释、风险”。
5. 数据模型是否支撑：宏观、行业、个股、消息、资金行为。
6. MVP 是否太大，是否需要切成更小的 P0/P1。
7. 测试和验收标准是否可执行。

建议 Codex 产出：

- `docs/design-review.md`：设计审查意见。
- `docs/review.md`：开发前 review 总结，列出必须修改项 / 可延后项。
- 如设计不够清楚，直接修改 `docs/design.md`，但保留变更说明。

---

## 3. Claude 阶段：开发 / 测试

Claude 按 Codex review 后的设计开发。

优先顺序：

1. 数据模型：PoolItem / Quote / Hotspot / NewsEvent / CompanySignal。
2. Pool loader：读取 `data/pools/ai_energy_pool_2026-05-19.csv`。
3. CLI MVP：
   - `market-intel pool list --json`
   - `market-intel pool explain <symbol> --json`
   - `market-intel hotspots --mock --json`
   - `market-intel holdings impact --mock --json`
4. 测试：pytest 覆盖核心解析、评分、JSON schema。
5. 文档：补 `docs/data-model.md`、`docs/usage.md`。

Claude 不做：

- 不接真实交易下单。
- 不输出买卖指令。
- 不擅自改 tradegov / researchgov / companygov。
- 不把 GUI 做成漂亮空壳；底层数据和 CLI 先稳定。

---

## 4. Livermore 阶段：最终验收

Livermore 最终验收标准：

1. `knowledge-gc scan /Users/alice/Desktop/market-intel --json` 无 errors。
2. pytest 通过。
3. CLI 输出稳定 JSON。
4. 能解释至少 5 个样例标的：英维克、拓维信息、光迅科技、长川科技、数据港。
5. 能用 mock 行情跑出热点子链路排行。
6. 能识别持仓/观察池重复暴露，但不输出买卖指令。
7. 文档足够清楚，可被 Livermore 接入日常盘前/盘中工作流。

验收结果写入：

- `docs/acceptance-result.md`，或
- `docs/review.md` 的最终验收章节。

---

## 5. 当前状态

- 项目仓库已创建：`/Users/alice/Desktop/market-intel`
- 首版设计：`docs/design.md`
- AI 大池子 Markdown：`data/pools/ai_energy_map_2026-05-17.md`
- AI 大池子 CSV：`data/pools/ai_energy_pool_2026-05-19.csv`
- `knowledge-gc scan` 当前 0 errors / 0 warnings。

---

## 6. 下一步建议

1. 交给 Codex 做设计 review。
2. Codex 输出 `docs/design-review.md` 和 `docs/review.md`。
3. 根据 Codex 意见压缩 MVP。
4. 再交给 Claude 开发 CLI MVP 和测试。
5. Livermore 最终验收。
