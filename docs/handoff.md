# 协作交接

## 当前方向

做一个对股民和 agent 都好用的全 A 复盘工具。

优先级：

1. 覆盖边界准确。
2. 持仓和证据缺口清楚。
3. 文本输出给人看，JSON 输出给 agent 接力。
4. 所有写入先 dry-run，再正式导入，再 coverage 复验。

## 开发规则

- 先读代码和测试，再改。
- 小步提交，直接推 `main`。
- 不读、不输出本机 token。
- README/docs 保持简短，不写个人信息。
- 新功能必须有测试和可运行命令。
- 修改公开文档后跑 `make privacy-scan`。

## 验证

常规验证：

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
```

重要改动再补：

```bash
git diff --check
gh run watch <run-id> --exit-status
```

## 不做

- 不输出买卖指令、目标价、仓位建议。
- 不接交易下单。
- 不把 seed 覆盖当完整全 A 覆盖。
- 不把长篇产品说明堆进 README。
