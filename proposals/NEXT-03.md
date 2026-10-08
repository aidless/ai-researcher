---
tags: [proposal, self-evolution, confound_audit, lineage-01]
generated_by: ai_researcher.evolve
---

# NEXT-03 Re-run lineage-01 without the confound its amendment names

**kind**: confound_audit  
**source run**: `lineage-01`  
**evidence**: INFRASTRUCTURE CONTAMINATION: 2-8 explicit connection errors + 12-35 short outputs per version (v2:8/35, v3:2/12, v3b:5/15, v3c:8/32). Four experiments shared one ollama server with no locking. The v3b-vs-v3c McNemar 1:1  
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
