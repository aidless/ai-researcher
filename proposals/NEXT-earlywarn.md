---
tags: [proposal, self-evolution, feature-ablation, early-warning, shared-bias]
generated_by: manual (diagnosis from jsd-02 signed data)
---

# NEXT-EW Replace the disagreement-based collapse predictor

**kind**: feature_ablation
**source run**: `jsd-02`
**evidence**: 5/7 LOO; both failures are rank inversions and both are
*underpredictions* (`gpt4o-cross` pred 3 vs true 6; `multiexecutor` pred 1 vs true 3)

## Why this, and not a better formula

A rank inversion is invariant under any strictly increasing transform, so no
reparameterisation of the same disagreement statistic can fix it. The error is in
the feature set. Both misses are also in the same direction: large collapse with
only moderate evaluator disagreement, i.e. the shared-bias regime, where a
disagreement signal is structurally quiet.

## Method sketch

Rebuild the condition set on `demo/collapse/run_collapse.py` (in-repo, already
records per-item votes) with at least 12 conditions, and for each condition store
**both evaluators' full vote distributions**, which jsd-02 did not. Then evaluate
leave-one-condition-out rank prediction of the collapse gap under:

- disagreement-based (current): JSD, agreement rate, vote entropy, n_distinct
- non-agreement-based (new): top-1 vote share, top1−top2 margin, absolute numeric
  distance between the two evaluators' preferred answers, single-evaluator entropy

Report hit rate per feature **and separately on the shared-bias subset**, since
that subset is where the current feature is blind and an average would hide it.

## Preregistered predictions (both directions falsifiable)

1. Disagreement features score lower than non-agreement features overall.
2. On the shared-bias subset specifically, disagreement features fall to chance
   while non-agreement features do not. If disagreement features do *not* fail
   there, the shared-bias explanation of the jsd-02 failures is wrong.

## Power and kill-switch

n = 12+ conditions, exact one-sided sign test on per-condition hits at alpha=0.05,
power 0.8, minimum detectable hit-rate improvement 0.25. Kill-switch keys on
`best_feature` and `shared_bias_chance` — fields the harness must actually write,
checked with `protocols.check_emits` before approval.

## Why it is a proposal and not a queued run

The confirmation arm for the paper's only surviving effect outranks it for the
remaining GPU, and an envelope whose script does not exist yet would be exactly
the failure mode this project keeps undoing (coderepair-02's first two launches
died on a missing script and a wrong path). Specified, not half-built.
