---
tags: [proposal, self-evolution, confound_audit, coderepair-01]
generated_by: ai_researcher.evolve
---

# NEXT-02 Re-run coderepair-01 without the confound its amendment names

**kind**: confound_audit  
**source run**: `coderepair-01`  
**evidence**: MODEL-EXISTENCE CORRECTION: 80 of 320 calls (40 per policy) targeted llama3.2:3b, which is not installed locally (only llama3.2:1b). Every such call returned HTTP 404, the harness caught the exception and recorded it as   
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
