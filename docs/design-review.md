# 设计审查

方向成立，但必须避免做成行情 App、追涨工具或漂亮空壳。

## 长期约束

- 原始 pool CSV 不是证券主数据，必须保留 raw 和数据质量标记。
- 同一 symbol 多链路合并为一个标的，保留 `exposures[]`。
- CLI、GUI、agent 共享 core 口径。
- JSON 输出遵守统一外壳。
- 文本报告给人读，JSON contract 给 agent 接力。
- 写入 runtime 前先 dry-run。
- 禁止买卖建议、目标价、仓位建议。

## 验收

```bash
market-intel pool explain 002837 --text
market-intel pool coverage --runtime --text
market-intel scan --mock --text
market-intel portfolio review --mock --text
market-intel import universe <csv> --runtime --merge --dry-run --text
```

看三件事：覆盖边界、下一步命令、无交易指令。
