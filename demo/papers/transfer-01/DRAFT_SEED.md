# Results (draft seed, machine-generated)

Hypothesis under test: step-calc transfers across model families: positive gain on llama3.1:8b heldout40, after replicating the qwen2.5:7b effect in the same harness

- replication_gain = 0.7500 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: two-seat joint is absent]
- transfer_gain = 0.7750 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: two-seat joint is absent]
- gain = 0.7750 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: two-seat joint is absent]
- paired wins on qwen2.5:7b: step-only 30, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: two-seat joint is absent]
- paired wins on llama3.1:8b: step-only 31, direct-only 0 (n=40). [INCONCLUSIVE — hedge required: report as observed on n=40, do not generalize. To upgrade: missing: two-seat joint is absent]

## Objections and responses

- No recorded objections (review absent or joint READY without objection — treat as weak signal per the two-seat rule).

## What would change this section
- C-replication_gain: missing: two-seat joint is absent
- C-transfer_gain: missing: two-seat joint is absent
- C-gain: missing: two-seat joint is absent
- C-paired-qwen2.5:7b: missing: two-seat joint is absent
- C-paired-llama3.1:8b: missing: two-seat joint is absent

## Bounded lesson

Observation: replication_gain = 0.7500 (n=40).
Interpretation: see kill-switch verdict and robustness distribution above; neither is stated here as fact about any other setting.
Proposed action: replicate the exact procedure before citing; do not port the numbers to a different model, metric, or n.
Transfer limits: single-replication evidence unless the ledger says otherwise; magnitude comparisons across different-sized sets are invalid.
