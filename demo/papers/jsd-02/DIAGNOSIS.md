# jsd-02: why the early-warning arm fails

Hit rate 5/7 LOO (Wilson 95% [0.359, 0.918]). The hit rate is the least
informative thing about this arm; the failure structure is the finding.

## Both failures are rank inversions, both underpredictions

| held-out | predicted rank | true rank | direction |
|---|---|---|---|
| gpt4o-cross | 3 | 6 | underpredicted severity |
| multiexecutor | 1 | 3 | underpredicted severity |

## Why this is not a tuning problem

A rank inversion is invariant under any strictly increasing transform of the
predictor. No better formula for the same disagreement statistic -- JSD,
entropy, KL, a learned monotone map -- can convert a wrong order into the right
one. The remaining error is in the feature set, not in the fit.

## Why it matters that both are underpredictions

A disagreement-based signal measures how far apart two judges are. When both
judges share a bias, they are close, the signal is quiet, and the collapse can
still be large. Both missed conditions are cross-evaluator conditions with large
gaps and only moderate disagreement: the shared-bias regime.

That is the worst possible failure direction for an early-warning system, because
the cases it misses are the cases where both evaluators are confidently wrong
together. An early-warning claim that reports 5/7 without this observation
misdescribes its own blind spot.

## What a replacement needs

Features that are not agreement-based:

- absolute confidence (top-1 vote share, top-1 minus top-2 margin)
- the numeric distance between the two evaluators' preferred answers, rather than
  the distance between their vote *distributions*
- answer-side entropy within a single evaluator

Evaluation must be leave-one-condition-out over more than seven conditions, and
must report the shared-bias subset separately rather than averaged away.

Status: specified, not run. Until then early warning is reported as a diagnosed
failure mode and is not in the paper's title.
