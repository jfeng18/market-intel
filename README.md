# market-intel

全 A 本地复盘工作台：把行情、持仓、覆盖边界、研究证据和 journal 串成可复跑流程。

不做行情 App、交易入口或荐股工具；不输出买卖指令、目标价或仓位建议。

## 为什么

- 一条命令完成日常复盘：同步行情 → 生成报告 → 变化追踪 → 日报留档。
- 区分 `confirmed/foundation/draft/missing/blocked`，避免把基础清单当研究结论。
- 持仓优先暴露缺行情、缺覆盖、主题重叠和集中风险。
- JSON 字段稳定，agent 可以接力读取。
- runtime 数据留在本地，公开仓库只放样例和代码。

## 快速开始

需要 Python 3.10+。

```bash
pip install akshare
pip install -e .

# 1. 初始化运行时目录
market-intel init runtime

# 2. 同步今日行情（从东方财富拉取全 A 数据）
market-intel sync quotes

# 3. 导入持仓
market-intel import holdings holdings.csv --runtime

# 4. 一键复盘（同步 + 报告 + 变化追踪 + 留档）
market-intel review --text

# 5. 生成 HTML 可视化报告
market-intel review --html --output review.html
```

## 日常使用

收盘后只需一条命令：

```bash
# 默认：同步行情 + 生成日报 + 对比昨天变化 + 保存留档
market-intel review --text

# 周级视角：对比本周变化
market-intel review --window week --text

# 月级视角
market-intel review --window month --text

# 生成 HTML 报告
market-intel review --html
```

## 覆盖池管理

```bash
# 添加标的到 universe
market-intel pool add 600519 --name 贵州茅台 --industry 白酒

# 移除标的
market-intel pool remove 600519

# 查看覆盖率
market-intel pool coverage --runtime --text
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `review` | 一键复盘（同步+报告+变化追踪+留档） |
| `sync quotes` | 同步全 A 行情（akshare） |
| `pool add/remove` | 添加/移除覆盖池标的 |
| `pool coverage` | 覆盖率分析 |
| `scan` | 全市场扫描 |
| `daily` | 每日综合报告 |
| `brief` | 每日简报 |
| `watchlist` | 观察清单 |
| `map` | 产业链地图 |
| `portfolio review` | 持仓复核 |
| `hotspots` | 热点板块排名 |
| `focus` | 聚焦视图 |
| `dashboard` | 一屏工作台 |
| `journal save/list/compare` | 日报留档与对比 |
| `import quotes/holdings/universe/research` | CSV 数据导入 |
| `status runtime` | 运行时状态诊断 |
| `agent plan/briefing/run/next` | Agent 工作流 |

运行 `market-intel --help` 查看所有命令及说明。

## Agent 入口

- `data.agent_contract`：稳定字段列表和读取顺序。
- `data.changes`：与历史日报的变化对比。
- `data.coverage_context`：全 A 覆盖边界和补数队列。
- `data.command_queue`：可接力执行的 JSON 命令。

## 文档

- `docs/product.md`：产品边界。
- `docs/data-model.md`：稳定 JSON 口径。
- `docs/review.md`：验收清单。

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
```
