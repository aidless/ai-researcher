---
tags: [proposal, self-evolution, mechanism_split, coderepair-01]
generated_by: ai_researcher.evolve
---

# NEXT-01 Discriminate the two readings of coderepair-01

**kind**: mechanism_split  
**source run**: `coderepair-01`  
**evidence**: 1/4 families positive (mixed, not reversed)  
**power**: n=144, mde=0.25, alpha=0.05, power=0.8  
**status**: ready for approval

## Why this, and not something else

Mixed-across-families results are usually reported as inconclusive and then quietly dropped. Naming the two live readings is what keeps them alive.

## Tension

The result is mixed across families. Two readings survive: the effect requires capability the smaller families lack, or it requires something about the task. A bigger sample would not separate them; only a design that varies one of the two would.

## Method sketch

Hold the policy fixed and vary a single factor predicted to differ between the two readings (e.g. baseline capability matched across families, or defect visibility held constant), then report the interaction.

## Preregistered kill-switch

- `interaction_detected == True` -> **STOP-EXTEND** -- the interaction identifies which reading holds
- `interaction_detected == False` -> **STOP-INCONCLUSIVE** -- no interaction at this n: the two readings remain open and the claim must stay conditional

A human still approves (`loop approve <envelope>`). The proposer cannot run anything.
