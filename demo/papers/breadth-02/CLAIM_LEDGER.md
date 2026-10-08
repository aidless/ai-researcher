# CLAIM_LEDGER.md

源运行: demo/runs/breadth-02 | 假设: on a larger, harder diff set, at least one real code-review decision flips with the evaluator, so ev
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-n_diffs | n_diffs = 24 (n=0) | round-01/artifacts/result.json -> n_diffs | 24 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-_config-n_diffs | _config.n_diffs = 24 (n=0) | round-01/artifacts/result.json -> _config.n_diffs | 24 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-_config-evaluators | _config.evaluators = 3 (n=0) | round-01/artifacts/result.json -> _config.evaluators | 3 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-_config-abstention_rate | _config.abstention_rate = 0.0000 (n=0) | round-01/artifacts/result.json -> _config.abstention_rate | 0.0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-abstention_rate | abstention_rate = 0.0000 (n=0) | round-01/artifacts/result.json -> abstention_rate | 0.0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-abstentions | abstentions = 0 (n=0) | round-01/artifacts/result.json -> abstentions | 0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-pairwise_agreement | pairwise_agreement = 0.5000 (n=0) | round-01/artifacts/result.json -> pairwise_agreement | 0.5 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-flip_cases | flip_cases = 16 (n=0) | round-01/artifacts/result.json -> flip_cases | 16 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-n_diffs —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-_config-n_diffs —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-_config-evaluators —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-_config-abstention_rate —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-abstention_rate —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-abstentions —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-pairwise_agreement —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-flip_cases —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
