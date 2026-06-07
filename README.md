# market-intel

面向全 A 的本地复盘工具。它把行情、持仓、基础清单、研究证据和 journal 留痕组织成一条可复跑的工作流。

它不是行情 App、交易 App 或荐股工具；不输出买卖指令、目标价或仓位建议。

## 竞争力

- **全 A 复盘闭环**：先看覆盖边界，再看市场、持仓、证据缺口和复核队列。
- **持仓优先**：检查持仓是否有行情、是否被覆盖、是否集中暴露。
- **agent-native**：核心命令有稳定 JSON、`next_commands`、`done_when` 和边界说明。
- **证据留痕**：基础清单命中不等于已研究，需补核心逻辑、关键证据和证伪风险。
- **本地私有**：默认读取仓库数据、示例数据和用户提供的 runtime 文件；公开文档不写个人信息。

## 安装与验证

需要 Python 3.10+。

```bash
make install
make ci
```

未安装 console script 时：

```bash
PYTHONPATH=src python3 -m market_intel.cli dashboard --mock --text
```

## 5 分钟试跑

```bash
market-intel dashboard --mock --text
market-intel scan --mock --text
market-intel portfolio review --mock --text
market-intel focus --mock --text
```

## Runtime 工作流

初始化本地 runtime：

```bash
market-intel init runtime --json
```

导入示例数据：

```bash
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
market-intel agent run --text
market-intel daily --runtime --text
market-intel journal save --runtime --json
```

## 全 A 补数闭环

看覆盖状态：

```bash
market-intel pool coverage --runtime --text
```

导出 A 股基础清单补数字段：

```bash
market-intel pool universe --runtime --output data/runtime/a_share_universe_patch.csv --text
```

填好 CSV 后先 dry-run，看覆盖率是否改善：

```bash
market-intel import universe data/runtime/a_share_universe_patch.csv --runtime --merge --dry-run --text
```

确认后再写入并复验：

```bash
market-intel import universe data/runtime/a_share_universe_patch.csv --runtime --merge --json
market-intel pool coverage --runtime --text
```

## 研究证据闭环

导出 foundation 持仓的研究证据草稿：

```bash
market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --text
```

人工补齐 `thesis/evidence/invalidation` 后：

```bash
market-intel import research data/runtime/research_notes.todo.csv --dry-run --json
market-intel import research data/runtime/research_notes.todo.csv --runtime --json
market-intel agent next --text
```

## 常用命令

```bash
market-intel import schema --json
market-intel validate runtime --json
market-intel pool quality invalid_symbol --text
market-intel pool explain 002837 --text
market-intel portfolio explain 002837 --runtime --text
market-intel journal latest --text
market-intel journal compare --text
market-intel journal timeline --text
```

## 文档

- `docs/product.md`：产品定位与取舍。
- `docs/data-model.md`：JSON 外壳和核心数据模型。
- `docs/design.md`：较完整的历史设计稿。
- `docs/handoff.md`：协作与验收边界。

## 隐私边界

- 不提交 `data/runtime/`。
- 不在 README/docs/examples/.github 写 token、本机路径、账号或真实持仓。
- 提交前运行：

```bash
make privacy-scan
```
