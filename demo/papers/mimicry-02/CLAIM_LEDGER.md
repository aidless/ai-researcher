# CLAIM_LEDGER.md

源运行: demo/runs/mimicry-02 | 假设: cross-trace stability (S1) and reflection-inside-deduction placement (S2) jointly separate correct-m
最终裁决: STOP-REFUTED | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-k | k = 3 (n=0) | round-01/artifacts/result.json -> k | 3 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-syllogism-s1_stability | questions.syllogism.s1_stability = 0.6670 (n=0) | round-01/artifacts/result.json -> questions.syllogism.s1_stability | 0.667 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-syllogism-n_ok | questions.syllogism.n_ok = 1 (n=0) | round-01/artifacts/result.json -> questions.syllogism.n_ok | 1 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-coins-s1_stability | questions.coins.s1_stability = 1.0000 (n=0) | round-01/artifacts/result.json -> questions.coins.s1_stability | 1.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-coins-n_ok | questions.coins.n_ok = 0 (n=0) | round-01/artifacts/result.json -> questions.coins.n_ok | 0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-gcd-s1_stability | questions.gcd.s1_stability = 0.6670 (n=0) | round-01/artifacts/result.json -> questions.gcd.s1_stability | 0.667 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-questions-gcd-n_ok | questions.gcd.n_ok = 2 (n=0) | round-01/artifacts/result.json -> questions.gcd.n_ok | 2 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-separation_gap | separation_gap = -0.1660 (n=0) | round-01/artifacts/result.json -> separation_gap | -0.166 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-round_cost_usd | round_cost_usd = 0.0000 (n=0) | round-01/artifacts/result.json -> round_cost_usd | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-k —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-syllogism-s1_stability —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-syllogism-n_ok —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-coins-s1_stability —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-coins-n_ok —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-gcd-s1_stability —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-questions-gcd-n_ok —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-separation_gap —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-round_cost_usd —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
