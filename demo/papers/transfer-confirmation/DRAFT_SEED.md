# Results (draft seed, machine-generated)

Hypothesis under test: structured step-by-step scoring beats direct answering on held-out arithmetic for every local model family tested, at a sample size pre-specified to detect a 0.10 difference

- per_model.qwen2.5:7b.gain = 0.2438 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.qwen2.5:7b.fixed = 45 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.qwen2.5:7b.broke = 6 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.qwen2.5:7b.p = 0.0000 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.gemma3:4b.gain = 0.5188 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.gemma3:4b.fixed = 88 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.gemma3:4b.broke = 5 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- per_model.gemma3:4b.p = 0.0000 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- gain_mean = 0.3813 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- mcnemar_pooled.fixed = 133 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- mcnemar_pooled.broke = 11 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- mcnemar_pooled.p = 0.0000 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- paired_observations = 320 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]
- sign_test_p = 0.2500 (n=160). [INCONCLUSIVE — hedge required: report as observed on n=160, do not generalize. To upgrade: missing: two-seat joint is absent]

## Objections and responses

- No recorded objections (review absent or joint READY without objection — treat as weak signal per the two-seat rule).

## What would change this section
- C-per_model-qwen2-5:7b-gain: missing: two-seat joint is absent
- C-per_model-qwen2-5:7b-fixed: missing: two-seat joint is absent
- C-per_model-qwen2-5:7b-broke: missing: two-seat joint is absent
- C-per_model-qwen2-5:7b-p: missing: two-seat joint is absent
- C-per_model-gemma3:4b-gain: missing: two-seat joint is absent
- C-per_model-gemma3:4b-fixed: missing: two-seat joint is absent
- C-per_model-gemma3:4b-broke: missing: two-seat joint is absent
- C-per_model-gemma3:4b-p: missing: two-seat joint is absent
- C-gain_mean: missing: two-seat joint is absent
- C-mcnemar_pooled-fixed: missing: two-seat joint is absent
- C-mcnemar_pooled-broke: missing: two-seat joint is absent
- C-mcnemar_pooled-p: missing: two-seat joint is absent
- C-paired_observations: missing: two-seat joint is absent
- C-sign_test_p: missing: two-seat joint is absent

## Bounded lesson

Observation: per_model.qwen2.5:7b.gain = 0.2438 (n=160).
Interpretation: see kill-switch verdict and robustness distribution above; neither is stated here as fact about any other setting.
Proposed action: replicate the exact procedure before citing; do not port the numbers to a different model, metric, or n.
Transfer limits: single-replication evidence unless the ledger says otherwise; magnitude comparisons across different-sized sets are invalid.
