# CLAIM_LEDGER.md

源运行: demo/runs/sweetspot-02 | 假设: on deepseek-r1:7b, accuracy as a function of capped reasoning length is non-monotonic (rises then fa
最终裁决: STOP-REFUTED | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-families-math-acc[0] | families.math.acc[0] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.math.acc[0] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-math-acc[1] | families.math.acc[1] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.math.acc[1] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-math-acc[2] | families.math.acc[2] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.math.acc[2] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-code-acc[0] | families.code.acc[0] = 0.5000 (n=0) | round-01/artifacts/result.json -> families.code.acc[0] | 0.5 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-code-acc[1] | families.code.acc[1] = 0.6667 (n=0) | round-01/artifacts/result.json -> families.code.acc[1] | 0.6667 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-code-acc[2] | families.code.acc[2] = 0.6667 (n=0) | round-01/artifacts/result.json -> families.code.acc[2] | 0.6667 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-logic-acc[0] | families.logic.acc[0] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.logic.acc[0] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-logic-acc[1] | families.logic.acc[1] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.logic.acc[1] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-families-logic-acc[2] | families.logic.acc[2] = 0.0000 (n=0) | round-01/artifacts/result.json -> families.logic.acc[2] | 0.0 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-families-math-acc[0] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-math-acc[1] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-math-acc[2] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-code-acc[0] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-code-acc[1] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-code-acc[2] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-logic-acc[0] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-logic-acc[1] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-families-logic-acc[2] —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
