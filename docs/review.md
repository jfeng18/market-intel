# Review

## Correctness

- readiness 不能在 validation/freshness 有 errors 时放行日报。
- 字符串布尔值必须解析，不能用 truthiness。
- pending/non-security 行不能从描述里恢复成可交易 ticker。
- 重复暴露必须按 distinct holding 计数。
- universe merge 不能删除未出现在补丁里的已有标的。

## Product

- 默认范围是 `all-a`。
- AI 池只作为样例和回归底座。
- 新功能必须强化覆盖、持仓、证据、journal 或 agent 接力。
- README/docs 保持短，不写个人信息。

## Verification

```bash
PYTHONPATH=src python3 -m pytest -q
make smoke
make privacy-scan
git diff --check
```
