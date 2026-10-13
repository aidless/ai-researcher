# CLAIM_LEDGER.md

源运行: demo/runs/balanced-01 | 假设: reanalysis on a balanced 3-text + 3-visual strategy subset preserves the cross-model >> self-eval PC
最终裁决: STOP-REFUTED | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-full-cross | PCI full cross = 1.6191 | round-01/artifacts/result.json -> full.cross | 1.6191 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-full-self | PCI full self = 1.2653 | round-01/artifacts/result.json -> full.self | 1.2653 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-balanced-cross | PCI balanced cross = 1.1059 | round-01/artifacts/result.json -> balanced.cross | 1.1059 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-balanced-self | PCI balanced self = 1.5434 | round-01/artifacts/result.json -> balanced.self | 1.5434 | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-full_order | full_order = cross>self | round-01/artifacts/result.json -> full_order | cross>self | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-balanced_order | balanced_order = self>=cross | round-01/artifacts/result.json -> balanced_order | self>=cross | missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-full-cross —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-full-self —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-balanced-cross —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-balanced-self —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-full_order —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-balanced_order —— missing: kill-switch verdict is STOP-REFUTED, not STOP-EXTEND; two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
