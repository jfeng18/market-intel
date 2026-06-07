# market-intel

面向全 A 的本地复盘工作台。它把行情、持仓、覆盖边界、研究证据和 journal 留痕串成一条可复跑流程。

它不是行情 App、交易入口或荐股工具；不输出买卖指令、目标价或仓位建议。

## 竞争力

- 覆盖边界清楚：区分 `confirmed/foundation/draft/missing/blocked`。
- 持仓优先：先看自己的票缺什么、重叠在哪里、风险暴露是否集中。
- 证据闭环：基础清单、研究备注、dry-run 导入、coverage 复验、journal 留痕连起来。
- agent 友好：稳定 JSON、`next_commands`、`done_when` 和接力路径。
- 本地私有：runtime 数据不提交，公开文档不写个人信息。

## 安装

需要 Python 3.10+。

```bash
make install
make ci
```

未安装 console script 时：

```bash
PYTHONPATH=src python3 -m market_intel.cli dashboard --mock --text
```

## 快速试跑

```bash
market-intel dashboard --mock --text
market-intel scan --mock --text
market-intel portfolio review --mock --text
```

## 日常流程

```bash
market-intel init runtime --json
market-intel status runtime --text
market-intel dashboard --text
market-intel scan --runtime --text
```

补数先 dry-run，确认后再写入：

```bash
market-intel pool coverage --runtime --text
market-intel pool universe --runtime --dry-run --text
market-intel pool research --runtime --dry-run --text
market-intel import universe data/runtime/a_share_universe_patch.csv --runtime --merge --dry-run --text
market-intel import research data/runtime/research_notes.todo.csv --dry-run --json
market-intel journal save --runtime --json
```

## 文档

- `docs/product.md`：定位、边界、路线。
- `docs/design.md`：架构和流程。
- `docs/data-model.md`：稳定 JSON 口径。
- `docs/review.md`：验收清单。

## 隐私

- 不提交 `data/runtime/`。
- 不在公开文档、样例或 CI 配置里写 token、本机路径、账号或真实持仓。
- 提交前运行 `make privacy-scan`。
