# market-intel

面向全 A 的本地复盘工作台：把行情、持仓、覆盖边界、研究证据和 journal 留痕串成可复跑流程。

不是行情 App、交易 App 或荐股工具；不输出买卖指令、目标价或仓位建议。

## 竞争力

- **全 A 边界清楚**：区分 `confirmed/foundation/draft/missing/blocked`，不把“收录”包装成“研究完成”。
- **持仓优先**：先发现自己的票缺行情、缺覆盖、缺证据或暴露过度。
- **证据闭环**：`coverage -> research -> import -> coverage -> journal` 可复验。
- **agent-native**：JSON 稳定，带 `next_commands`、`done_when` 和可接手路径。
- **本地私有**：runtime 数据不提交，公开文档不写个人信息。

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
market-intel focus --mock --text
```

## 本地数据

```bash
market-intel init runtime --json
market-intel import quotes examples/quotes.csv.example --runtime --json
market-intel import holdings examples/holdings.csv.example --runtime --json
market-intel import universe examples/a_share_universe.csv.example --runtime --json
market-intel import research examples/research_notes.csv.example --runtime --json
```

日常入口：

```bash
market-intel status runtime --text
market-intel dashboard --text
market-intel agent briefing --text
market-intel daily --runtime --text
market-intel journal save --runtime --json
```

## 补数闭环

```bash
market-intel pool coverage --runtime --text
market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --text
market-intel import universe data/runtime/a_share_universe_patch.csv --runtime --merge --dry-run --text
market-intel import universe data/runtime/a_share_universe_patch.csv --runtime --merge --json
market-intel pool coverage --runtime --text
```

研究证据：

```bash
market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --text
market-intel import research data/runtime/research_notes.todo.csv --dry-run --json
market-intel import research data/runtime/research_notes.todo.csv --runtime --json
market-intel agent next --text
```

## 文档

- `docs/product.md`：定位、边界、路线。
- `docs/data-model.md`：稳定 JSON 和核心字段。
- `docs/design.md`：架构与流程。
- `docs/review.md`：开发验收清单。

## 隐私

- 不提交 `data/runtime/`。
- 不在公开文档、样例或 CI 配置里写 token、本机路径、账号或真实持仓。
- 提交前运行 `make privacy-scan`。
