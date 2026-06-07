# Review

## Correctness

- readiness 遇到 validation/freshness errors 必须阻塞日报。
- 字符串布尔必须解析，不能用 Python truthiness。
- pending/non-security 行不能恢复成可交易 ticker。
- 重复 exposure 不能制造重复持仓。
- universe merge 不能删除补丁外的已有标的。

## Product

- 默认范围是 `all-a`。
- AI 池只做样例和回归底座。
- 新功能必须强化覆盖、持仓、证据、journal 或 agent 接力。
- README/docs 保持短，不写个人信息。

## Verification

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
