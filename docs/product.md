# 产品

`market-intel` 是全 A 本地复盘工具，服务对象是股民和接力工作的 agent。

## 做什么

- 通过 akshare（东方财富）同步全 A 日行情到本地。
- 一键复盘：同步行情 → 生成日报 → 追踪变化 → 自动留档（`review`）。
- 浏览器复盘工作台：本地 HTTP 服务，支持刷新和局域网手机访问（`serve`）。
- 生成自包含 HTML 报告，含 SVG 可视化（涨跌条、量能点、评分雷达）。
- 标出缺行情、缺覆盖、缺研究证据和集中暴露。
- 支持持仓盈亏显示（cost_price → P&L%）。
- 命令行管理覆盖池（`pool add/remove`）。
- CSV 导入自动检测 GBK/GB18030 编码。
- 输出稳定 JSON + agent 接力队列（command_queue）。

## 不做什么

- 不做实时行情终端、资讯流、社区或交易入口。
- 不做黑盒诊股。
- 不输出买卖建议、目标价或仓位建议。

## 差异化

- 多数股票 App 强在行情、资讯和交易入口；本项目强在复盘流程、证据状态和本地留痕。
- `foundation` 只表示全 A 基础清单收录，不能等同研究完成。
- `confirmed` 必须有 reviewed research notes 或复盘池正式覆盖。
- AI 产业链池只是种子样例和回归底座；默认产品范围是 `all-a`。

## 核心命令

| 命令 | 说明 |
|------|------|
| `serve` | 浏览器复盘工作台 |
| `review` | 一键复盘（sync + daily + changes + journal） |
| `sync quotes` | 同步全 A 行情 |
| `pool add/remove` | 管理覆盖池 |
| `daily` | 每日综合报告 |
| `scan` | 全市场扫描 |
| `portfolio review` | 持仓复核 |
| `journal save/compare/timeline` | 日报留档与对比 |
