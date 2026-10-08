# CLAIM_LEDGER.md

源运行: demo/runs/transfer-confirmation | 假设: structured step-by-step scoring beats direct answering on held-out arithmetic for every local model 
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-per_model-qwen2-5:7b-gain | per_model.qwen2.5:7b.gain = 0.2438 (n=160) | round-01/artifacts/result.json -> per_model.qwen2.5:7b.gain | 0.2438 | missing: two-seat joint is absent | inconclusive |
| C-per_model-qwen2-5:7b-fixed | per_model.qwen2.5:7b.fixed = 45 (n=160) | round-01/artifacts/result.json -> per_model.qwen2.5:7b.fixed | 45 | missing: two-seat joint is absent | inconclusive |
| C-per_model-qwen2-5:7b-broke | per_model.qwen2.5:7b.broke = 6 (n=160) | round-01/artifacts/result.json -> per_model.qwen2.5:7b.broke | 6 | missing: two-seat joint is absent | inconclusive |
| C-per_model-qwen2-5:7b-p | per_model.qwen2.5:7b.p = 0.0000 (n=160) | round-01/artifacts/result.json -> per_model.qwen2.5:7b.p | 0.0 | missing: two-seat joint is absent | inconclusive |
| C-per_model-gemma3:4b-gain | per_model.gemma3:4b.gain = 0.5188 (n=160) | round-01/artifacts/result.json -> per_model.gemma3:4b.gain | 0.5188 | missing: two-seat joint is absent | inconclusive |
| C-per_model-gemma3:4b-fixed | per_model.gemma3:4b.fixed = 88 (n=160) | round-01/artifacts/result.json -> per_model.gemma3:4b.fixed | 88 | missing: two-seat joint is absent | inconclusive |
| C-per_model-gemma3:4b-broke | per_model.gemma3:4b.broke = 5 (n=160) | round-01/artifacts/result.json -> per_model.gemma3:4b.broke | 5 | missing: two-seat joint is absent | inconclusive |
| C-per_model-gemma3:4b-p | per_model.gemma3:4b.p = 0.0000 (n=160) | round-01/artifacts/result.json -> per_model.gemma3:4b.p | 0.0 | missing: two-seat joint is absent | inconclusive |
| C-gain_mean | gain_mean = 0.3813 (n=160) | round-01/artifacts/result.json -> gain_mean | 0.3813 | missing: two-seat joint is absent | inconclusive |
| C-mcnemar_pooled-fixed | mcnemar_pooled.fixed = 133 (n=160) | round-01/artifacts/result.json -> mcnemar_pooled.fixed | 133 | missing: two-seat joint is absent | inconclusive |
| C-mcnemar_pooled-broke | mcnemar_pooled.broke = 11 (n=160) | round-01/artifacts/result.json -> mcnemar_pooled.broke | 11 | missing: two-seat joint is absent | inconclusive |
| C-mcnemar_pooled-p | mcnemar_pooled.p = 0.0000 (n=160) | round-01/artifacts/result.json -> mcnemar_pooled.p | 0.0 | missing: two-seat joint is absent | inconclusive |
| C-paired_observations | paired_observations = 320 (n=160) | round-01/artifacts/result.json -> paired_observations | 320 | missing: two-seat joint is absent | inconclusive |
| C-sign_test_p | sign_test_p = 0.2500 (n=160) | round-01/artifacts/result.json -> sign_test_p | 0.25 | missing: two-seat joint is absent | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-per_model-qwen2-5:7b-gain —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-qwen2-5:7b-fixed —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-qwen2-5:7b-broke —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-qwen2-5:7b-p —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-gemma3:4b-gain —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-gemma3:4b-fixed —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-gemma3:4b-broke —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-per_model-gemma3:4b-p —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-gain_mean —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-mcnemar_pooled-fixed —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-mcnemar_pooled-broke —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-mcnemar_pooled-p —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-paired_observations —— missing: two-seat joint is absent
- 降级 inconclusive + hedge：C-sign_test_p —— missing: two-seat joint is absent
