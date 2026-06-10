# market-intel

A 股本地复盘工具：收盘后一条命令同步行情、生成报告、对比昨日变化、自动留档。

不做行情 App、交易入口或荐股工具；不输出买卖指令、目标价或仓位建议。

## 谁适合用

- 有复盘习惯的 A 股投资者，想把"每天该看什么"结构化
- 希望 AI agent 接力做复盘分析的开发者
- 想在本地跑数据、不想把持仓上传云端的人

## 快速开始

需要 Python 3.10+（[下载 Python](https://www.python.org/downloads/)）。

**国内用户安装建议加镜像源：**

```bash
pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 1. 初始化
market-intel init runtime

# 2. 同步今日行情（从东方财富拉取全 A 数据）
market-intel sync quotes

# 3. 导入持仓（从券商软件导出 CSV）
market-intel import holdings holdings.csv --runtime

# 4. 启动浏览器复盘工作台（推荐）
market-intel serve
```

浏览器自动打开，看到可视化复盘报告，点"刷新复盘"按钮更新数据。

**手机查看（同一 WiFi）：**

```bash
market-intel serve --host 0.0.0.0
# 终端会打印局域网 IP，手机浏览器打开即可
```

## 日常使用

收盘后只需一步：

```bash
# 推荐：浏览器工作台
market-intel serve

# 或命令行文本报告
market-intel review --text

# 或生成 HTML 文件
market-intel review --html --output review.html
```

变化追踪支持多时间窗口：

```bash
market-intel review --window week --text   # 对比本周
market-intel review --window month --text  # 对比本月
```

## 覆盖池管理

```bash
market-intel pool add 600519 --name 贵州茅台 --industry 白酒
market-intel pool remove 600519
market-intel pool coverage --runtime --text
```

## 进阶命令

| 命令 | 说明 |
|------|------|
| `review` | 一键复盘（同步+报告+变化追踪+留档） |
| `serve` | 启动浏览器复盘工作台 |
| `sync quotes` | 同步全 A 行情（akshare/东方财富） |
| `pool add/remove` | 添加/移除观察池标的 |
| `scan` | 全市场扫描 |
| `daily` | 每日综合报告 |
| `watchlist` | 观察清单 |
| `portfolio review` | 持仓复核 |
| `hotspots` | 热点板块排名 |
| `journal save/list/compare` | 日报留档与对比 |
| `import quotes/holdings` | CSV 数据导入 |
| `status runtime` | 运行时状态诊断 |

运行 `market-intel --help` 查看所有命令。

## Agent 入口

AI agent 集成请参考 [AGENTS.md](AGENTS.md)。

- `data.agent_contract`：稳定字段列表和读取顺序。
- `data.command_queue`：可接力执行的 JSON 命令（含 state_effect 和 runnable 标记）。
- `data.changes`：与历史日报的变化对比。

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
