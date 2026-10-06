# CLAIM_LEDGER.md

源运行: demo/runs/swarm-02 | 假设: evaluator-preferred strategies concentrate faster as parallel subagents grow (swarm=4 PCI slope exce
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-arms-swarm1-swarm | arms.swarm1.swarm = 1 (n=0) | round-01/artifacts/result.json -> arms.swarm1.swarm | 1 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-arms-swarm1-slope | arms.swarm1.slope = 0.0400 (n=0) | round-01/artifacts/result.json -> arms.swarm1.slope | 0.04 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-arms-swarm1-mean_n_actual | arms.swarm1.mean_n_actual = 1.0000 (n=0) | round-01/artifacts/result.json -> arms.swarm1.mean_n_actual | 1.0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-arms-swarm4-swarm | arms.swarm4.swarm = 4 (n=0) | round-01/artifacts/result.json -> arms.swarm4.swarm | 4 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-arms-swarm4-slope | arms.swarm4.slope = 0.0765 (n=0) | round-01/artifacts/result.json -> arms.swarm4.slope | 0.0765 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-arms-swarm4-mean_n_actual | arms.swarm4.mean_n_actual = 4.0000 (n=0) | round-01/artifacts/result.json -> arms.swarm4.mean_n_actual | 4.0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-slope_excess | slope_excess = 0.0365 (n=0) | round-01/artifacts/result.json -> slope_excess | 0.0365 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-round_cost_usd | round_cost_usd = 0.0000 (n=0) | round-01/artifacts/result.json -> round_cost_usd | 0.0 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-arms-swarm1-swarm —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-arms-swarm1-slope —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-arms-swarm1-mean_n_actual —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-arms-swarm4-swarm —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-arms-swarm4-slope —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-arms-swarm4-mean_n_actual —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-slope_excess —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-round_cost_usd —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
