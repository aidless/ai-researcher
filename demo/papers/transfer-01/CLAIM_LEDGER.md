# CLAIM_LEDGER.md

源运行: demo/runs/transfer-01 | 假设: step-calc transfers across model families: positive gain on llama3.1:8b heldout40, after replicating
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-replication_gain | replication_gain = 0.7500 (n=40) | round-01/artifacts/result.json -> replication_gain | 0.75 | missing: two-seat joint is absent | inconclusive |
| C-transfer_gain | transfer_gain = 0.7750 (n=40) | round-01/artifacts/result.json -> transfer_gain | 0.775 | missing: two-seat joint is absent | inconclusive |
| C-gain | gain = 0.7750 (n=40) | round-01/artifacts/result.json -> gain | 0.775 | missing: two-seat joint is absent | inconclusive |
| C-paired-qwen2.5:7b | paired wins on qwen2.5:7b: step-only 30, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.qwen2.5:7b.paired | 30:0 | missing: two-seat joint is absent | inconclusive |
| C-paired-llama3.1:8b | paired wins on llama3.1:8b: step-only 31, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.llama3.1:8b.paired | 31:0 | missing: two-seat joint is absent | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-replication_gain —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-transfer_gain —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-gain —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-qwen2.5:7b —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-llama3.1:8b —— missing: two-seat joint is absent
