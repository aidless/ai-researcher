# Zone-1 full-gate result (mechanical 17/17 PASS, judgment split)

- methodology: 8.29 (PASS >= 8.0)
- devil: 6.57 (FAIL < 8.0)
- verdict: FAIL (both seats must clear)

## Devil dimension scores (the punch list)

| dimension | score | status |
|---|---|---|
| significance | 6 | needs work |
| correctness | 8 | pass |
| clarity | 7 | borderline |
| generality | 5 | needs work |
| predecessor-acknowledgment | 9 | pass |
| completeness | 7 | borderline |
| breadth-of-interest | 6 | needs work |

## Devil's objection (verbatim core)

Generality limited by narrow scope: only two small models, GSM8K-style cases
and minimal TTRL loops, 7 committed evaluator conditions. "Exists at small
scale" overstated without broader architectures, tasks, or deployment scenarios.
Amplification/robustness methodologically sound but on controlled artificial
setups that may not translate to practical deployments.

## What closes each gap (mapped to running/planned work)

- significance 6->8: matrix-01 (8 families) + lineage capability curve. In flight.
- generality 5->8: same two runs expand architectures (8 models) and settings
  (5-checkpoint lineage). Tasks remain narrow (GSM8K-style + TTRL) -- next gap.
- breadth 6->8: needs a deployment-relevant demonstration (real task, not TTRL
  toy). Not yet preregistered -- candidate next envelope after matrix lands.
- clarity 7->8: copy-edit pass after content freezes. Cheap, last.
