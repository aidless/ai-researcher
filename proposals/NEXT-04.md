---
tags: [proposal, self-evolution, confound_audit, swarm-fd]
generated_by: ai_researcher.evolve
---

# NEXT-04 Re-run swarm-fd without the confound its amendment names

**kind**: confound_audit  
**source run**: `swarm-fd`  
**evidence**: Threshold recomputed by hand-editing result.json (max(2,len-1)->max(1,len-1) for n=1). This VOIDED the bundle signature: verify now correctly FAILS on hash mismatch. Superseded by swarm-fd2 (fixed code from the start). D  
**power**: n=80, mde=0.2, alpha=0.05, power=0.8  
**status**: ready for approval

## Why this, and not something else

A withdrawn claim is an open debt in the ledger. Leaving it withdrawn keeps the paper honest but permanently weaker than recovering it honestly.

## Tension

The amendment records that the round's conclusion cannot be separated from an infrastructure or procedural artifact. The claim is neither supported nor refuted, so the direction is unknown, and an unknown direction is not a result. Re-running with the confound removed is the only way to learn whether the original observation was ever about the model.

## Method sketch

Identical envelope and seed, re-run with the confound absent (exclusive GPU lock, preflighted models, sealed artifacts directory). Compare against the withdrawn numbers.

## Preregistered kill-switch

- `confirmed == True` -> **STOP-EXTEND** -- the original observation survives the clean re-run
- `confirmed == False` -> **STOP-REFUTED** -- the original observation was the artifact; record it as a lesson rather than a finding

A human still approves (`loop approve <envelope>`). The proposer cannot run anything.
