---
tags: [proposal, self-evolution, power_escalation, balanced-01]
generated_by: ai_researcher.evolve
---

# NEXT-05 Re-measure balanced-01 at an n that can resolve its effect

**kind**: power_escalation  
**source run**: `balanced-01`  
**evidence**: 136 ledger claim(s) flagged inconclusive on sample size; n=40 could not detect mde=0.10 (needs n>=157)  
**power**: n=157, mde=0.1, alpha=0.05, power=0.8  
**status**: ready for approval

## Why this, and not something else

Every two-seat review in this project has said some version of 'n is too small'. This converts that recurring objection into a queued experiment with a computed n.

## Tension

The ledger records claims that cannot be resolved at the n actually run, so they are formally unciteable. Either they are real effects awaiting enough data, or they are noise that more data will not rescue. Only one of those is worth buying, and the difference is currently unmeasured.

## Method sketch

Same items, policies, scorer and seed; increase n to the pre-checked requirement and report per-condition CIs rather than a pooled test.

## Preregistered kill-switch

- `confirmed == True` -> **STOP-EXTEND** -- the effect is real at adequate n; the claim becomes citable
- `confirmed == False` -> **STOP-REFUTED** -- the effect was noise at n=40; retire the claim
- `confirmed == None` -> **STOP-INCONCLUSIVE** -- still unresolvable: report the interval, do not claim

A human still approves (`loop approve <envelope>`). The proposer cannot run anything.
