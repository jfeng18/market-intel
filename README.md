# market-intel

全 A 本地复盘工作台：把行情、持仓、覆盖边界、研究证据和 journal 串成可复跑流程。

不做行情 App、交易入口或荐股工具；不输出买卖指令、目标价或仓位建议。

## 为什么

- 一屏回答：先看什么、为什么、完成标准、下一条命令。
- 区分 `confirmed/foundation/draft/missing/blocked`，避免把基础清单当研究结论。
- 持仓优先暴露缺行情、缺覆盖、主题重叠和集中风险。
- JSON 字段稳定，agent 可以接力读 `data.action_summary.decision_card`。
- runtime 数据留在本地，公开仓库只放样例和代码。

## 快速试跑

需要 Python 3.10+。

```bash
make install
market-intel dashboard --mock --text
```

未安装 console script 时：

```bash
PYTHONPATH=src python3 -m market_intel.cli dashboard --mock --text
```

## 正式使用

```bash
market-intel init runtime --json
market-intel import schema --json
market-intel status runtime --text
market-intel dashboard --text
```

补 universe/research/coverage 前先 dry-run，确认后再写 runtime。

## Agent 入口

- `data.action_summary.decision_card`：今日动作卡。
- `data.coverage_context`：全 A 覆盖边界和补数队列。
- `data.market_pulse`：全市场强弱和候选。
- `data.portfolio_pulse`：持仓优先级和集中暴露。
- `data.evidence_gaps`：缺证据标的和完成标准。
- `data.review_plan.items[]`：可接力 JSON 命令。

## 文档

- `docs/product.md`：产品边界。
- `docs/data-model.md`：稳定 JSON 口径。
- `docs/review.md`：验收清单。

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
