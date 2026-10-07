# CLAIM_LEDGER.md

源运行: demo/runs/matrix-01 | 假设: step-calc gain is positive on all 8 local instruction-model families, with magnitude varying by fami
最终裁决: STOP-ROUNDS-EXHAUSTED | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-replication_gain | replication_gain = 0.7000 (n=40) | round-01/artifacts/result.json -> replication_gain | 0.7 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-transfer_gain | transfer_gain = 0.3750 (n=40) | round-01/artifacts/result.json -> transfer_gain | 0.375 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-gain | gain = 0.3750 (n=40) | round-01/artifacts/result.json -> gain | 0.375 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-qwen2.5:7b | paired wins on qwen2.5:7b: step-only 28, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.qwen2.5:7b.paired | 28:0 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-llama3.1:8b | paired wins on llama3.1:8b: step-only 15, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.llama3.1:8b.paired | 15:0 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-qwen2:7b | paired wins on qwen2:7b: step-only 18, direct-only 1 (n=40) | round-01/artifacts/result.json -> models.qwen2:7b.paired | 18:1 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-gemma3:4b | paired wins on gemma3:4b: step-only 31, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.gemma3:4b.paired | 31:0 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-deepseek-r1:7b | paired wins on deepseek-r1:7b: step-only 29, direct-only 1 (n=40) | round-01/artifacts/result.json -> models.deepseek-r1:7b.paired | 29:1 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-qwen3:4b | paired wins on qwen3:4b: step-only 7, direct-only 1 (n=40) | round-01/artifacts/result.json -> models.qwen3:4b.paired | 7:1 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-qwen2.5-coder:7b | paired wins on qwen2.5-coder:7b: step-only 24, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.qwen2.5-coder:7b.paired | 24:0 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |
| C-paired-llama3.2:1b | paired wins on llama3.2:1b: step-only 21, direct-only 0 (n=40) | round-01/artifacts/result.json -> models.llama3.2:1b.paired | 21:0 | missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-replication_gain —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-transfer_gain —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-gain —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-qwen2.5:7b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-llama3.1:8b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-qwen2:7b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-gemma3:4b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-deepseek-r1:7b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-qwen3:4b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-qwen2.5-coder:7b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- 降级 inconclusive + hedge：C-paired-llama3.2:1b —— missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
