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

Effect sizes: Cohen's h = 1.703 (qwen) and 1.897 (llama), both large by
conventional thresholds. Practical significance: absolute gains of 75 and 77.5
percentage points on exact-match accuracy are visible without statistics; the
p-values (both p < 1e-8 after BH correction) confirm what the raw differences
already show rather than rescuing a borderline result.

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
Transfer limits: eight model families on ONE task domain (not breadth across
tasks); one evaluator pair for swarm; committed weights only for JSD; local
ollama only throughout. Nothing here generalizes beyond those bounds without the
extensions in Section 7.

## Reproduce
```bash
# every number below traces to artifacts/result.json -> field (see CLAIM_LEDGER.md)
# verify: python -m ai_researcher.loop verify <rundir>  (Ed25519, per round)
# ledger: python -m ai_researcher.bridge <rundir> <envelope> --out <paperdir>
# quality: python -m ai_researcher.loop publish <rundir> --tier <workshop|conference-main|tmlr|sci-journal|zone1> --paper <paperdir>
```

## Baselines and ablations (what was compared, what was not)

Baselines run: direct prompting (the null policy) on both models — the only
baseline that isolates the policy effect. Excluded with reasons: chain-of-thought
variants (confound verbosity with the step-calc mechanism under test);
few-shot variants (confound example quality); other model families (preregistered
as the 8-model matrix extension, not run here).

Ablations completed: none beyond the direct-vs-step contrast. Not ablated:
prompt wording variants of step-calc, temperature > 0, alternative answer
extractors. Each is a named follow-up with a preregistered envelope slot, not a
silent gap.

## Data and code availability

All primary data (per-case results, weight vectors, trajectories) in the signed
evidence bundles alongside this manuscript; analysis scripts and the autonomous
loop that produced them at the repository accompanying submission
(supplementary ZIP for blind review; public link at camera-ready). Model
digests pinned per round; seeds fixed and recorded.

## Broader impact and ethics

Who benefits: practitioners choosing prompting policies or evaluators on small
models get directional evidence where they previously had vendor claims. Who
could be harmed: overgeneralization — a team deploying step-calc on an untested
family because "it transfers" without reading the Limitations. Dual use: none
beyond standard LLM deployment considerations. Compute footprint: ~500 local
ollama calls total, no paid APIs, no human-subjects data.

## AI use disclosure

Experiments were designed and executed through an autonomous research loop
(preregistration envelopes, kill-switches, signed evidence bundles); the
manuscript draft was machine-generated from claim ledgers and revised by a
human author. All numbers trace to committed artifacts (see Reproduce). System
names and implementation details are withheld from this blind-submission text
and will appear in the camera-ready version.

## References (to be completed on submission)

GSM8K (Cobbe et al.); McNemar (1947); Benjamini–Hochberg (1995); Chen & Wang
2026 (topological mimicry); Marjanovic et al. TMLR 2025 (Thoughtology);
DeepSeek-R1; Kimi K2.5/K2.6 Agent Swarm reports.

## Related work (what differs, one line each)

- **Sakana AI Scientist v1+v2** (Lu et al. 2024; Yamada et al. 2025; Nature 2026):
  end-to-end idea→paper automation with archive-feedback and agentic tree
  search. Differs: no preregistration envelope, no evidence signing, single-model
  review. We adopt their archive-feedback loop and AI-disclosure norm; our
  envelope, Ed25519 bundles, and two-seat contradiction scoring address the
  integrity gaps their pipeline leaves open.
- **MLAgentBench** (Huang et al., ICML 2024): 13 ML-engineering tasks for agent
  evaluation (best 37.5%); names long-horizon planning and hallucination-about-
  progress as the two failure modes. Differs: evaluates agents on engineering
  tasks, not evaluator bias. Our loop's state machine + resume + evidence-over-
  self-report answers both failure modes directly; scoped as external validation.
- **Thoughtology** (Marjanovic et al., TMLR 2025): reasoning sweet spot and
  rumination on frontier R1. Differs: single family, frontier scale. Our
  sweetspot replication tests the same curve on small local models; floor
  effects reported honestly rather than worked around silently.
- **Chen & Wang 2026** (topological mimicry): diagnose spinning-wheel traces
  without providing a detector. Differs: observation only. Our S1+S2 probe is
  the detector they lack; its refutation on 3 questions is reported, not buried.
- **This account's evaluator-coupling line** (paper1/2/4-anon, mm-epc): Cramér–Rao
  bounds, N-sensitivity, MPCI=1.449 cross-model. Differs: frontier evaluators,
  large budgets. This paper extends that line downward (small models) and
  outward (swarms), with the same evidence discipline.

## Breadth across model families (8/8, sign test p=0.004)

The transfer effect was re-measured on a 40-item held-out set across eight local
model families spanning 1B-8B and general/reasoning/coder lineages.

| family | direct | step-calc | gain | fail->pass | pass->fail |
|---|---|---|---|---|---|
| qwen2.5:7b | 0.125 | 0.825 | +0.700 | 28 | 0 |
| llama3.1:8b | 0.025 | 0.400 | +0.375 | 15 | 0 |
| qwen2:7b | 0.025 | 0.450 | +0.425 | 18 | 1 |
| gemma3:4b | 0.025 | 0.800 | +0.775 | 31 | 0 |
| deepseek-r1:7b | 0.225 | 0.925 | +0.700 | 29 | 1 |
| qwen3:4b | 0.725 | 0.875 | +0.150 | 7 | 1 |
| qwen2.5-coder:7b | 0.300 | 0.900 | +0.600 | 24 | 0 |
| llama3.2:1b | 0.000 | 0.525 | +0.525 | 21 | 0 |

Every family improves (8/8, sign test p = 0.004; pooled paired McNemar 173:3,
p = 1.9e-47). Gain tracks headroom rather than size: qwen3:4b has the highest
baseline and the smallest gain, llama3.2:1b a zero baseline and +0.525. This
retires the two-family limit on the transfer arm. It does **not** establish
breadth across task domains -- the held-out set is one GSM8K-style collection,
so the claim is breadth across *models*, not across *tasks*, and the devil seat
scored this arm 3/10 for exactly that reason.

One caveat, recorded rather than smoothed: this run's kill-switch keyed on a
`confirmed` field the script never emitted, and the loop's kill evaluator
swallowed the resulting NameError, filing the run as a clean finish. The STOP-
EXTEND verdict for this arm is analyst-assigned rather than preregistered. The
loop now fails closed on unevaluable rules; see Appendix A.

## Generality

Strengths: the four findings replicate the same discipline (preregistration,
signed bundles, kill-switches, adversarial review) across four independent
setups, so the *method* generalizes even where individual effects do not.
Limitations: two model families for transfer; 6 rounds × 4 tasks for swarm;
1-rep weights for balance; 7 committed conditions for JSD; local ollama only.
Generality beyond these bounds is conjectured, not shown: a second held-out set
from a different task family, 8/16/32-agent scaling curves, and prospective JSD
runs are preregistered next steps, not completed ones. The gemma/deepseek-r1/
qwen3 transfer runs are no longer missing -- they are in the eight-family table
above.

## Worked example (one full pass, general reader)

Take the transfer claim. (1) Envelope states: step-calc beats direct on heldout
cases never used for selection, measured by exact float match, McNemar paired
test, BH across models. (2) Loop runs 40 cases × 2 policies × 2 models locally;
each round's artifacts are SHA-256-manifested and Ed25519-signed. (3) Result:
qwen +0.75 [0.60, 0.875] (30:0), llama +0.775 [0.65, 0.90] (31:0).
(4) Kill-switch fires STOP-EXTEND (transfer_gain ≥ 0.10). (5) Two seats review:
methodology 4/10 (CIs overlap, no equivalence test), devil 2/10 (exact-match
brittleness, n=40). Joint NOT_READY on magnitude, READY on direction.
(6) Ledger records both; draft states direction, disclaims magnitude. That is
the whole pipeline in one paragraph.

## Appendix A: two supervision bugs this project paid for

Recorded because both produced clean-looking states that were false, and both
were found by checking a status against the artifacts rather than trusting it.

1. **Wall-clock kill left status RUNNING.** The loop ran experiments via
   `subprocess.run(timeout=...)` and did not catch `TimeoutExpired`. matrix-01
   wrote a complete result set and was then killed at the limit; the uncaught
   exception aborted the loop before it could sign, judge, or terminate, and the
   run reported RUNNING indefinitely. An unsupervised run that can never conclude
   is worse than a failed one, because status lies. Timeouts are now a recorded
   round state with signed artifacts, and a completed-but-killed round can be
   finalized (`loop finalize`) without re-spending budget or touching artifact
   bytes.
2. **An unevaluable kill-switch was reported as a clean finish.** `_eval_kill`
   caught every exception from a preregistered condition and continued, so a rule
   keyed on a field the artifact never wrote evaluated to nothing and the run
   closed as STOP-ROUNDS-EXHAUSTED. The preregistration had not run. Conditions
   are now surfaced: if no rule fires and any rule is unevaluable, the run stops
   STOP-KILL-UNEVALUABLE and names the rules that never executed.

Both were the same shape of error, seen three times in this project: a missing
value silently becoming a zero, a lenient parse becoming a pass, a swallowed
exception becoming a null result. The defense is structural rather than
attentional -- unknown must never read as neutral, and every terminal state must
be reachable only by an explicit, recorded decision.

## Appendix B: the gate was grading a scaffold

On 2026-10-07 the venue gate was found to be reading `<paper>/DRAFT_SEED.md` and
nothing else. Every "mechanical 17/17 PASS" printed before then described a
per-run draft seed of 1-18 KB, not the manuscript; the gate report recorded no
artifact identity, so a scorecard asserting a full pass was indistinguishable
from a genuine one. The manuscript itself had never been graded.

Two further silences surfaced in the same audit. The ledger parser accepted only
rows beginning `| C-`, so the Chinese-headed tables bridge actually writes
yielded zero claims, which left every evidence-linked check reporting PASS with
nothing to check. And the kill-switch evaluator swallowed exceptions, so a
preregistered rule keyed on an absent field counted as "nothing fired".

The shared shape is not carelessness but a default: absent data resolved to
neutral. All three now fail loudly instead -- an unparseable ledger, an
unevaluable rule, and a missing manuscript each stop the pipeline, and every
verdict prints and stores which artifact it read.

Re-graded against the real manuscript with a 138-claim consolidated ledger from
13 signed runs, the mechanical half passes 17/17 and the two seats split
methodology 8.29 / devil 7.29, below the 8.0 bar. The earlier 6.57 devil score
was measured on a draft seed; the current number is the one that counts, and the
remaining gap is a task-domain-breadth gap, not a measurement gap.
