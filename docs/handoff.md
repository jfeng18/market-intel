# 交接

方向：全 A、本地、证据闭环、agent 可接力。

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

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
