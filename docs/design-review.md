# 设计审查

避免做成行情 App、追涨工具或漂亮空壳。

## 必守

- 原始 pool CSV 不是证券主数据；保留 `raw` 和数据质量标记。
- `symbol` 合并后保留多链路 `exposures[]`。
- CLI、GUI、agent 共享 core 口径。
- 写入 runtime 前先 dry-run。
- 禁止买卖建议、目标价、仓位建议。

## 看三件事

```bash
market-intel pool coverage --runtime --text
market-intel scan --mock --text
market-intel portfolio review --mock --text
```

输出必须说明覆盖边界、下一步命令、无交易指令。
