# 交接

方向：全 A、本地、证据闭环、agent 可接力。

## 主工作流

```
market-intel serve          # 浏览器复盘工作台（推荐）
market-intel review --text  # 命令行一键复盘
```

`review` 内部流程：sync quotes（akshare 拉取行情）→ daily（生成报告）→ journal compare（变化追踪）→ journal save（留档）。

`serve` 启动本地 HTTP 服务，自动打开浏览器，提供刷新按钮和只读命令执行按钮。支持 `--host 0.0.0.0` 局域网手机访问。

## 外部依赖

- **akshare**：唯一外部依赖（pip install akshare），用于 sync quotes 从东方财富拉取全 A 日行情。

## 优先级

1. 覆盖边界准确。
2. 持仓和证据缺口清楚。
3. 文本短且可执行，JSON 稳。
4. 写入先 dry-run，再复验。

## 开发规则

- 先读代码和测试，再改。
- 小步提交，直接推 `main`。
- 不读、不输出本机 token。
- 公开文档不写个人信息。
- 新增写入命令必须在 `agent.py:command_state_effect()` 注册。

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
