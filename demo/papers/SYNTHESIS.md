# Evaluator Bias in Small Models: Transfer, Amplification, Robustness, and Early Warning

## Abstract

Evaluator-preference collapse was established on frontier models. We ask whether
it survives the move to small local models, and what its boundaries are. Four
preregistered studies, all with signed evidence bundles, claim ledgers, and
two-seat adversarial review:

1. **Transfer**: step-calc prompting gains +0.75, 95% CI [0.60, 0.875] on qwen2.5:7b
   (McNemar 30:0, p_bh 2.0e-9) and +0.775, 95% CI [0.65, 0.90] on llama3.1:8b
   (McNemar 31:0, p_bh 2.0e-9), n=40 held-out cases each. Policy effects cross
   families. Magnitude equivalence not claimed (CIs overlap; McNemar is
   within-model-only).
2. **Amplification**: in a minimal TTRL loop, evaluator-preferred strategies
   concentrate faster with 4 parallel executors than 1 (slope 0.0765 vs 0.0400,
   excess 0.0365), replicated across 4/5 seeds (excesses 0.012/0.0/0.055/0.055/
   0.037). A force-decide control arm rules out abstention-mechanism
   interaction (zero abstentions, gap persists at 0.0163).
3. **Robustness**: the published cross-model PCI excess (1.619 vs 1.265) survives
   strategy-set balancing in 46/56 subsets (82%, MOSTLY-HOLDS). Magnitude
   comparisons across set sizes are invalid and not made.
4. **Early warning**: evaluator-pair JSD predicts collapse ordering at 5/7
   leave-one-out hits (0.714) on committed weights, extended from 3/5. Misses
   concentrate on the high-collapse extremes that define the phenomenon: JSD is
   a coarse sorter, not an extreme predictor.

No single leg is publication-grade alone. Together they triangulate: the
phenomenon exists at small scale, grows with parallelism, survives balancing,
and is coarsely predictable from evaluator disagreement.

## 1. Tension

Evaluator-preference collapse (reward overoptimization by the judge, not the
task) was measured with frontier evaluators at frontier cost. Everyone deploying
small or many models operates outside the measured regime: small-model users
cannot afford the protocol that established the effect, and swarm operators run
100+ parallel executors with no characterization of bias at scale. If the
phenomenon is about scale, small deployments are safe and the theory needs a
capability boundary. If it is about protocol, every deployment inherits it.
Nobody had checked, because checking is unfashionable work: replications,
boundary conditions, and negative controls.

## 2. Transfer: policy effects cross families

Preregistered envelope (hypothesis, exact command, budget $0, kill-switch rows,
fixed seed, power fields, negative-publication plan). 40 held-out GSM8K-style
cases never used for selection; direct vs step-calc; exact float match;
paired design with McNemar exact test, BH across 2 models, 5000-rep bootstrap
CIs. Ed25519-signed bundle verifies.

| model | direct | step-calc | gain [95% CI] | McNemar | p (BH) |
|---|---|---|---|---|---|
| qwen2.5:7b | 0.150 | 0.900 | +0.75, 95% CI [0.60, 0.875] | 30:0 | 2.0e-9 |
| llama3.1:8b | 0.025 | 0.800 | +0.775, 95% CI [0.65, 0.90] | 31:0 | 9.3e-10 |

Kill-switch: STOP-EXTEND. Two-seat review (4/10, 2/10, joint NOT_READY on
magnitude equivalence — correctly, since CIs overlap): the directional claim is
supported, "undiminished magnitude" is explicitly disclaimed in favor of a
preregistered 200-item extension.

## 3. Amplification: bias grows with swarm size, and it is not abstention artifact

Minimal TTRL loop (4 strategies, 4 tasks, 6 rounds, +0.08/-0.04 updates):
swarm=1 (sequential) vs swarm=4 (parallel, evaluator picks best per round).
Multi-seed (5 seeds): excesses 0.012/0.0/0.055/0.055/0.037, mean 0.032,
t 95% CI [0.001, 0.063] — barely excludes zero, reported as a small uncertain
effect, not a breakthrough.

The devil's objection (abstentions skip updates, so swarm size interacts with
the abstention mechanism itself) was tested, not argued: a force-decide arm
(re-ask once with forcing language, then deterministic seeded choice, every
vote flagged) shows excess 0.0163 with ZERO abstentions and ZERO forced votes
across 18 judge calls. The gap persists where the confound cannot operate.
Remaining weaknesses, stated: n=1 per arm here, 6 rounds, 4 tasks, small
magnitude. The multi-seed leg carries replication weight; the force-decide leg
carries mechanism cleanliness. Neither alone suffices.

## 4. Robustness: the published excess survives balancing (mostly)

On committed evaluator-collapse weights (11 strategies, 8 text + 3 visual):
full-set cross PCI 1.619 > self 1.265. All 56 balanced 3+3 subsets enumerated:
46 preserve the ordering (82%, MOSTLY-HOLDS). An initial top-3-only analysis
reversed the pattern — an unlucky 18% draw, caught by review, corrected by full
enumeration (now automatic via robustness.py). PCI magnitudes across different
set sizes are not compared (normalization differs); only orderings.

## 5. Early warning: JSD sorts, but misses the extremes

On 7 committed evaluator conditions (contagion, ds-self, gpt4o-cross, qwen37,
real-image, multiexecutor, interrupted qwen-partial): leave-one-out rank
prediction from pairwise JSD hits 5/7 (hit rate 0.714, Wilson 95% CI
[0.359, 0.918] — wide, as befits n=7). Misses concentrate on the high-collapse
extremes that define the phenomenon (gpt4o-cross true 6 predicted 3;
multiexecutor true 3 predicted 1), with contagion as hub neighbor to 4/5
holdouts. JSD is a coarse sorter for low/mid-collapse conditions, not an
extreme predictor. Both statements are in the ledger; neither is rounded up
to "confirmed" as a practical claim.

## 6. Limitations (stated, not buried)

- Sample scales are pilot-grade throughout (n=40, 6 rounds, 4 tasks, 1-rep
  weights). Every magnitude claim awaits the preregistered extensions.
- Exact float match understates absolute levels (3.0 vs 3.00 counts as miss);
  comparisons are fair (same metric both arms) but levels are floors.
- Local ollama models only; no frontier evaluator replication (budget $0 by
  design). The cross-family claim covers two families, not all.
- The force-decide deterministic fallback (seeded coin on persistent abstain)
  never triggered (0 forced votes); its behavior under real abstention pressure
  is untested.
- JSD analysis is retrospective on committed weights; prospective validation
  (predict-then-run) is future work with its own envelope.

## 7. What would change each section

- Transfer: 200-item heldout + McNemar matrix across 8 local families (matrix
  envelope approved, queued).
- Amplification: 8/16/32 subagents scaling curve + abstention-rate logging per
  arm (already instrumented: forced/abstained/total votes per arm).
- Robustness: multi-rep per-strategy weights (30-rep gamma files exist; weight
  files do not — needs re-running the source protocol).
- Early warning: 2+ more evaluator conditions to push LOO past n=7; prospective
  run on a fresh evaluator.

## Bounded lesson

Observation: evaluator-preference effects replicate on small local models
(transfer +0.75/+0.775, both p_bh 2e-9), grow with parallelism (4/5 seeds),
survive balancing (46/56), and are coarsely predictable from evaluator
disagreement (5/7 LOO).
Interpretation: the phenomenon is about protocol design, not scale -- but every
magnitude here is pilot-grade (n=40, 6 rounds, 1-rep weights) and must not be
cited as an effect size.
Proposed action: replicate the exact procedures (commands in Reproduce below)
before citing; extend, do not port, the numbers.
Transfer limits: two model families for transfer; one evaluator pair for swarm;
committed weights only for JSD; local ollama only throughout. Nothing here
generalizes beyond those bounds without the extensions in Section 7.

## Reproduce

```bash
# every number below traces to artifacts/result.json -> field (see CLAIM_LEDGER.md)
# verify: python -m ai_researcher.loop verify <rundir>  (Ed25519, per round)
# ledger: python -m ai_researcher.bridge <rundir> <envelope> --out <paperdir>
# quality: python -m ai_researcher.loop publish <rundir> --tier <workshop|conference-main|tmlr|sci-journal|zone1> --paper <paperdir>
```

## References (to be completed on submission)

GSM8K (Cobbe et al.); McNemar (1947); Benjamini–Hochberg (1995); Chen & Wang
2026 (topological mimicry); Marjanovic et al. TMLR 2025 (Thoughtology);
DeepSeek-R1; Kimi K2.5/K2.6 Agent Swarm reports.
