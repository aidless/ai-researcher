# CLAIM_LEDGER.md

源运行: demo/runs/lineage-01 | 假设: capability on the 50-item copilot eval is non-monotonic across copilot-3b-lora v1..v3c (some checkpo
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-rates-v2 | rates.v2 = 0.6759 (n=0) | round-01/artifacts/result.json -> rates.v2 | 0.6759 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3 | rates.v3 = 0.7326 (n=0) | round-01/artifacts/result.json -> rates.v3 | 0.7326 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3b | rates.v3b = 0.7241 (n=0) | round-01/artifacts/result.json -> rates.v3b | 0.7241 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3c | rates.v3c = 0.7083 (n=0) | round-01/artifacts/result.json -> rates.v3c | 0.7083 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-regressions[0]-drop | regressions[0].drop = 0.0085 (n=0) | round-01/artifacts/result.json -> regressions[0].drop | 0.0085 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-regressions[1]-drop | regressions[1].drop = 0.0158 (n=0) | round-01/artifacts/result.json -> regressions[1].drop | 0.0158 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-rates-v2 —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3 —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3b —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3c —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-regressions[0]-drop —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-regressions[1]-drop —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
