# paper2 theory gap: proposition in attackable form

## What the paper proves vs what the pipeline does

**Proven** (Prop. Conditional product bound): under a logistic observation model
with independent Bernoulli observations, a compact parameter space, and a
positive lower bound on strategy entropy, the coupling--diversity--precision
product has a positive lower bound via the Cramer--Rao inequality for a
**regular unbiased estimator** of the scalar coupling parameter γ.

**Done in practice**: γ is estimated by the logit of the sample proportion
(`p2_mle_and_theorem_coverage_20260808.py`). The manuscript's own coverage
section reports this estimator **fails the bound in 10 of 21 probed cells**,
with first-order finite-sample bias E[γ̂]−γ ≈ (1−2s)/(2Ns(1−s)) that inflates
exactly where N is small or s(γ) nears the boundary. The MLE is undefined in 9
of 11 conditions (every repetition positively coupled, rate 1.0).

So the theorem is true and the estimator is wrong for it. The gap is
quantitative (bias formula above), not hand-waving.

## Two closable forms (pick one)

**Option A — construct the regular estimator.**
Find an unbiased (or bias-corrected) estimator of γ under the stated logistic
model that attains the regularity conditions, then re-run the 21-cell coverage
grid. Success = 21/21 meet the bound within simulation error. This keeps the
theorem and fixes the pipeline.

**Option B — finite-sample corrected bound.**
Keep the logit estimator and derive the bound it actually satisfies: CR floor
plus the first-order bias term (1−2s)/(2Ns(1−s)) as an explicit function of
(N, s). Predicts the observed failure pattern (small N, boundary s) as a
theorem rather than a post-hoc observation. Success = the corrected bound holds
in all 21 cells including the 10 that fail the uncorrected one.

## What the machine already did (simulation, CPU-only)

- Reproduced the bias scaling: failures concentrate at small N and boundary s,
  matching the (1−2s)/(2Ns(1−s)) form.
- The manuscript's threshold-robustness (gamma-cuts × CV-cuts grid) and
  seed-subset CV ranges are committed and recomputable.

## What remains (human)

The proof. Either the regularity verification for the candidate estimator (A)
or the corrected-bound derivation (B). No simulation substitutes for it, and
no simulation is claimed to.
