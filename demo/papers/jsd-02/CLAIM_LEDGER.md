# CLAIM_LEDGER.md

源运行: demo/runs/jsd-02 | 假设: evaluator-pair JSD predicts collapse ordering on 7 conditions (leave-one-out rank within 1, hit rate
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-n_conditions | n_conditions = 7 (n=0) | round-01/artifacts/result.json -> n_conditions | 7 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[0]-pred_rank | loo[0].pred_rank = 2 (n=0) | round-01/artifacts/result.json -> loo[0].pred_rank | 2 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[0]-true_rank | loo[0].true_rank = 1 (n=0) | round-01/artifacts/result.json -> loo[0].true_rank | 1 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[1]-pred_rank | loo[1].pred_rank = 1 (n=0) | round-01/artifacts/result.json -> loo[1].pred_rank | 1 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[1]-true_rank | loo[1].true_rank = 0 (n=0) | round-01/artifacts/result.json -> loo[1].true_rank | 0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[2]-pred_rank | loo[2].pred_rank = 3 (n=0) | round-01/artifacts/result.json -> loo[2].pred_rank | 3 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[2]-true_rank | loo[2].true_rank = 6 (n=0) | round-01/artifacts/result.json -> loo[2].true_rank | 6 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[3]-pred_rank | loo[3].pred_rank = 1 (n=0) | round-01/artifacts/result.json -> loo[3].pred_rank | 1 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[3]-true_rank | loo[3].true_rank = 3 (n=0) | round-01/artifacts/result.json -> loo[3].true_rank | 3 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[4]-pred_rank | loo[4].pred_rank = 5 (n=0) | round-01/artifacts/result.json -> loo[4].pred_rank | 5 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[4]-true_rank | loo[4].true_rank = 4 (n=0) | round-01/artifacts/result.json -> loo[4].true_rank | 4 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[5]-pred_rank | loo[5].pred_rank = 1 (n=0) | round-01/artifacts/result.json -> loo[5].pred_rank | 1 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[5]-true_rank | loo[5].true_rank = 2 (n=0) | round-01/artifacts/result.json -> loo[5].true_rank | 2 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[6]-pred_rank | loo[6].pred_rank = 4 (n=0) | round-01/artifacts/result.json -> loo[6].pred_rank | 4 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-loo[6]-true_rank | loo[6].true_rank = 5 (n=0) | round-01/artifacts/result.json -> loo[6].true_rank | 5 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-hit_rate | hit_rate = 0.7140 (n=0) | round-01/artifacts/result.json -> hit_rate | 0.714 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-n_predictable | n_predictable = 7 (n=0) | round-01/artifacts/result.json -> n_predictable | 7 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-n_conditions —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[0]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[0]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[1]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[1]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[2]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[2]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[3]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[3]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[4]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[4]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[5]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[5]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[6]-pred_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-loo[6]-true_rank —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-hit_rate —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-n_predictable —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
