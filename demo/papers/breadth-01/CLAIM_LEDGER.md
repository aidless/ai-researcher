# CLAIM_LEDGER.md

源运行: demo/runs/breadth-01 | 假设: three competent local evaluators disagree substantially on the same real code diffs (pairwise agreem
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-n_diffs | n_diffs = 8 (n=0) | round-01/artifacts/result.json -> n_diffs | 8 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-abstentions | abstentions = 9 (n=0) | round-01/artifacts/result.json -> abstentions | 9 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-pairwise_agreement | pairwise_agreement = 0.4290 (n=0) | round-01/artifacts/result.json -> pairwise_agreement | 0.429 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-flip_cases | flip_cases = 0 (n=0) | round-01/artifacts/result.json -> flip_cases | 0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-n_diffs —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-abstentions —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-pairwise_agreement —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-flip_cases —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
