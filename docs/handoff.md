# 交接

方向：做一个对股民和 agent 都好用的全 A 本地复盘工具。

## 优先级

1. 覆盖边界准确。
2. 持仓和证据缺口清楚。
3. 文本给人读，JSON 给 agent 接力。
4. 写入先 dry-run，再正式导入，再 coverage 复验。

## 开发规则

- 先读代码和测试，再改。
- 小步提交，直接推 `main`。
- 不读、不输出本机 token。
- 公开文档保持短，不写个人信息。
- 新功能必须有测试和可运行命令。

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```

推送后确认 GitHub Actions 通过。
