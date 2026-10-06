# Step-Calc Transfers Across Model Families (and What Almost Broke the Claim)

## Abstract

The step-calc prompting policy (solve step by step, one arithmetic step per
line, final number after `Answer:`) was established on qwen2.5:7b with a
0.780→0.925 gain. We ask whether the effect transfers to a second model
family. On 40 held-out GSM8K-style cases, exact float match, preregistered
with kill-switch rows: **qwen2.5:7b gain +0.75 [0.60, 0.875], McNemar 30:0,
p=1.9e-9; llama3.1:8b gain +0.775 [0.65, 0.90], McNemar 31:0, p=9.3e-10**
(BH across 2 models: both 2.0e-9). Transfer confirmed as a directional claim.
We do **not** claim equal magnitude: the CIs overlap substantially and McNemar
tests within-model significance only. A companion reanalysis of published
evaluator-collapse weights shows the cross-model excess survives strategy-set
balancing in 46/56 subsets (82%) — reported as MOSTLY-HOLDS, not as holds.

## 1. Question and preregistration

Policy effects in prompt engineering are routinely reported on a single model
family, then cited as if they were properties of the policy. The transfer
question — does it survive a change of family? — is asked far less often than
it should be, because the answer is sometimes no.

We preregistered (envelope, approved before the run): hypothesis, exact methods
command, budget (max 1 round, $0, 3h wall), kill-switch rows
(`transfer_gain >= 0.10` → STOP-EXTEND to a 200-item run;
`>= 0` → STOP-INCONCLUSIVE; `< 0` → STOP-REFUTED), required artifacts
(`result.json`), fixed seed, power fields, and a negative-publication plan
(replication report on refute — a refute without a publication plan is
publication bias by design).

## 2. Method

40 held-out cases never used for policy selection. Two policies (direct,
step-calc), two models (qwen2.5:7b for replication, llama3.1:8b for transfer),
local ollama, temperature default, exact float match against the reference
answer. Paired design: same 40 cases under both policies, so McNemar's exact
binomial test applies. BH correction across the 2 models; 5000-rep bootstrap
CIs for each gain. Every artifact SHA-256-manifested and Ed25519-signed at run
time; the bundle verifies.

## 3. Results

| model | direct | step-calc | gain [95% CI] | McNemar | p (BH) |
|---|---|---|---|---|---|
| qwen2.5:7b | 0.150 | 0.900 | +0.75 [0.60, 0.875] | 30:0 | 2.0e-9 |
| llama3.1:8b | 0.025 | 0.800 | +0.775 [0.65, 0.90] | 31:0 | 2.0e-9 |

Kill-switch verdict: **STOP-EXTEND** (transfer_gain 0.775 ≥ 0.10).

What we claim: step-calc produces a large positive gain on both families.
What we explicitly do **not** claim: equal magnitude. The CIs overlap
substantially ([0.60, 0.875] vs [0.65, 0.90]); a claim of "undiminished effect"
would require a cross-model equivalence test we did not preregister and did not
run. The two-seat review flagged exactly this, and the claim was downgraded
before drafting.

## 4. Companion: balancing does not explain away evaluator collapse (mostly)

Separately, on published evaluator-collapse weights (11 strategies, 8 text +
3 visual): full set cross PCI 1.619 > self 1.265. Restricting to balanced 3+3
subsets (top-3 per modality, renormalized): 46/56 subsets preserve the ordering
(82%). Reported as MOSTLY-HOLDS. Magnitude comparisons across set sizes are
invalid (PCI normalization differs); only the ordering is compared. An initial
top-3-only analysis reversed the pattern — an unlucky 18% draw, caught by the
reviewers and corrected by full enumeration. Selection rules are now audited
automatically.

## 5. Limitations (stated, not buried)

- n=40 per model. Adequate for the directional claim (p≈2e-9), inadequate for
  magnitude equivalence. The 200-item extension is preregistered, not run.
- Exact float match is brittle (3.0 vs 3.00 counts as miss). Both policies face
  the same metric, so the comparison is fair, but absolute levels understate.
- Two families is the minimum for a transfer claim, not coverage. gemma,
  deepseek-r1, and qwen3 sit on the same machine and are the obvious next runs.
- All calls local ollama, default temperature. No API models, no cost, no excuse.

## Reproduce

```bash
git clone <this-repo> && cd <this-repo>
# every number: artifacts/result.json -> field (see CLAIM_LEDGER.md)
# verify: python -m ai_researcher.loop verify <rundir>
```

## References (to be completed on submission)

GSM8K (Cobbe et al.); McNemar (1947); Benjamini–Hochberg (1995).
