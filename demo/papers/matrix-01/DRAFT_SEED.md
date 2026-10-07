# Results (draft seed, machine-generated)

Hypothesis under test: step-calc gain is positive on all 8 local instruction-model families, with magnitude varying by family (reasoning-specialized vs general)

- replication_gain = 0.7000 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- transfer_gain = 0.3750 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- gain = 0.3750 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on qwen2.5:7b: step-only 28, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on llama3.1:8b: step-only 15, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on qwen2:7b: step-only 18, direct-only 1 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on gemma3:4b: step-only 31, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on deepseek-r1:7b: step-only 29, direct-only 1 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on qwen3:4b: step-only 7, direct-only 1 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on qwen2.5-coder:7b: step-only 24, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]
- paired wins on llama3.2:1b: step-only 21, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent]

## Objections and responses

- No recorded objections (review absent or joint READY without objection — treat as weak signal per the two-seat rule).

## What would change this section
- C-replication_gain: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-transfer_gain: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-gain: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-qwen2.5:7b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-llama3.1:8b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-qwen2:7b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-gemma3:4b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-deepseek-r1:7b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-qwen3:4b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-qwen2.5-coder:7b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent
- C-paired-llama3.2:1b: missing: kill-switch verdict is STOP-ROUNDS-EXHAUSTED, not STOP-EXTEND; two-seat joint is absent

## Bounded lesson

Observation: replication_gain = 0.7000 (n=40).
Interpretation: see kill-switch verdict and robustness distribution above; neither is stated here as fact about any other setting.
Proposed action: replicate the exact procedure before citing; do not port the numbers to a different model, metric, or n.
Transfer limits: single-replication evidence unless the ledger says otherwise; magnitude comparisons across different-sized sets are invalid.
