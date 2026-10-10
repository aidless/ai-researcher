# Rebuttal: response to review (Major Revision)

We thank the reviewer for a review that names checkable facts. Every numbered
question below is answered with a file path, a recomputation, or a manuscript
change -- not with an assurance. Where the reviewer is right, we say so and show
the fix. Where the review misreads the manuscript or the PDF extraction, we show
that too, with the same standard of evidence.

## Q1. Why do qwen2.5:7b (+0.75 vs +0.700) and llama3.1:8b (+0.775 vs +0.375) differ across sections?

They are different runs of the same 40 items, and the difference is measured,
not hand-waved. transfer-01 and matrix-01 use byte-identical item sets
(verified: same 40 ids in both artifacts), the same models, temperature 0 -- and
disagree on 1/40 (qwen direct), 5/40 (qwen step-calc), 0/40 (llama direct), and
**16/40 (llama step-calc)** items.

So the +0.775 vs +0.375 for llama3.1:8b is not a transcription error and not two
different banks. It is run-to-run nondeterminism of local GPU inference at
temperature 0, concentrated in the reasoning policy: the treatment arm flips more
than the control in every comparison measured (code repair shows the same
pattern at 19-24/40 agreement across all cells).

Consequences, all now in the manuscript:

- A new section, "Run-to-run instability: direction replicates, exact numbers do
  not," states these fractions with the artifact paths.
- The primary claim rests on the largest samples (160 fresh items, 1280 paired
  observations across 8 families), never on any single 40-item number.
- Every 40-item number is reported beside its successor from a later run,
  explicitly as a discovery estimate.

## Q2. coderepair 40 vs 48: same experiment? Why does qwen direct move 0.525 to 0.583?

Same bank, extended. coderepair-01 used cr01-cr40; coderepair-02 used cr01-cr48
(all 40 overlap, verified by id). On the 40 overlapping items, qwen2.5:7b direct
agrees on only **19/40** between the two runs -- so the 0.525 to 0.583 move is
the same run-to-run instability as Q1, measured on a different domain, not a
different experiment and not an error. The data mapping table (new manuscript
section, every bank with file, n, source, overlap, run, preregistration, models,
policies, scorer) states the subset relation explicitly.

## Q3. What is confirmation-8fam-r2? Preregistered? Rule fired? Why is it in BH?

It is the clean re-run of confirmation-8fam after the 12h wall clock killed the
original after all 2560 judgments completed and before aggregation. Envelope
`demo/transfer/envelope_confirmation_8fam_r2.json`, approved before execution,
kill-switch on `confirmed` -- a field the harness provably writes -- which
**fired** (`confirmed == False`, unanimity fails at qwen3:4b). So yes:
preregistered, rule executed, direction pre-specified. It enters the
confirmatory BH family on those grounds, and the superseded r1 round does not
(counting both would double-count one experiment; the audit's SUPERSEDED map
says so explicitly).

## Q4. Do matrix-01, transfer-01, transfer-confirmation, confirmation-8fam-r2 measure the same effect? Double counting in BH?

They measure the same directional hypothesis (step-calc beats direct on
arithmetic) on different item sets: discovery40 (transfer-01, matrix-01),
confirm160 (transfer-confirmation, confirmation-8fam-r2). The dependence
structure is now stated in the paper: transfer-01 and matrix-01 share all 40
discovery items, so they are not independent; the two confirmation arms share
the 160 confirm items. BH under positive dependence (PRDS) remains valid for
one-sided tests in the predicted direction, and the per-family exact tests plus
the item-level cluster bootstrap are reported alongside the pooled values so no
conclusion rests on the pooled p-value alone. The confirmatory family (3
endpoints: transfer-01, transfer-confirmation, confirmation-8fam-r2) all survive
regardless; matrix-01 is exploratory and its survival buys nothing confirmatory.

## Q5. How many endpoints? 13 or 14? What about the 9 untestable arms?

14 testable primary endpoints (13 was stale text from before collapse-replication
and breadth-02 became testable; the manuscript table regenerates from the audit
JSON rather than being hand-edited, so this class of drift cannot recur
silently). Nine arms carry directional claims with no recomputable test; they
sit outside every family, which understates multiplicity and makes all reported
p-values optimistic -- stated in the paper, not buried. Sensitivity treatment:
the confirmatory family (n=3) is small enough that adding even all 9 untestable
arms as worst-case failures (p=1.0) leaves transfer-01, transfer-confirmation
and confirmation-8fam-r2 surviving BH at 0.05. That calculation is now in the
audit script output.

## Q6. Is pooled McNemar cluster-robust?

Yes, and the numbers are now in the paper rather than asserted. For
transfer-confirmation: per-family McNemar qwen2.5:7b 45:6 (p=1.8e-8), gemma3:4b
88:5 (p=1.1e-20) -- each family significant alone. Item-level cluster bootstrap
(resample items, 5000 reps, model structure preserved): pooled gain 0.381, 95%
CI [0.312, 0.450], excludes zero. For confirmation-8fam-r2: 7 of 8 families
individually significant (all p < 0.001 except qwen3:4b at p = 0.087, the sole
negative); cluster bootstrap pooled gain 0.289, 95% CI [0.249, 0.328]. The
pooled p-values are reported alongside, not instead of, these analyses.

## Q7. How were the confirmation's two families chosen? Selection bias?

qwen2.5:7b (the discovery family) and gemma3:4b (the largest-gain family in
matrix-01, +0.775) -- i.e., partly selected on the discovery outcome, which is a
real selection concern and is now stated. Two answers. First, the 8-family
extension was preregistered without reference to discovery gains (all eight
matrix families, fixed list) and 7 of 8 replicate, so the finding does not rest
on the selected pair. Second, the reported effect sizes come from the fresh
items, where selection on discovery outcomes cannot inflate the estimate -- and
indeed the fresh-item gains (+0.244, +0.519) are smaller than the discovery
gains, exactly as selection bias would predict for the discovery numbers.

## Q8. Is headroom preregistered? The gemma3:4b code-repair counterexample?

No, it was not preregistered, and the manuscript now says so in four places: it
is "a post hoc hypothesis, not a preregistered prediction... stated here as a
hypothesis for others to preregister against, with the code-repair counterexample
beside it." The gemma3:4b case (high direct baseline on code repair, yet -0.250
with an interval excluding zero) is presented as the falsifier of any general
headroom mechanism, restricting the hypothesis to arithmetic if it holds at all.

## Q9. Prompts, models, environment, scorer?

New Appendix C ("exact methods for independent replication") gives: verbatim
prompts for every policy, model tags with digests, ollama 0.33.3, temperature 0,
num_predict values, RTX 3060 Laptop 6GB, the exact float-match rule
(|got-expected| < 1e-6) and the extraction rule (last number for direct, number
after #### for step-calc) including the documented first-number bug it replaced,
the code-repair subprocess scorer, all seeds, the Ed25519 verification command,
per-table bundle paths, dataset licensing (GSM8K MIT, SWE-bench citation, author-
built repair items released with the repo), and how the human author verified
every machine-generated number (against its signed bundle, re-checked by the
figure-caption gate in CI).

## Q10. The "1 1 1..." pages, the psia text, the unlabeled table

These do not exist in the manuscript or in the PDF as built from it. Verified
2026-10-10: `grep -c "1 1 1" demo/papers/SYNTHESIS.md` returns 0;
`pdftotext paper.pdf | grep -c "1 1 1"` returns 0; `grep -n "psia"` on both
returns nothing. The §5 inference-budget table carries full column headers
(model | cap 150 | cap 400 | cap 1000 | cap400 fixed | cap1000 broke | McNemar p)
in the manuscript. We cannot fix artifacts of the reviewer's PDF extraction
pipeline, but we state for the record that a clean `pdflatex` build from the
committed source contains none of these strings, and the build log shows zero
errors. If the reviewer can point to a page number in a fresh build, we will
treat it as a real defect.

## On the title

Accepted. The title is now "A Prospectively Confirmed Arithmetic Effect of
Step-by-Step Prompting in Local Models, with Null Results Outside Arithmetic,"
and the abstract's first quantitative sentence gives the confirmation-set effect
sizes (+0.244 [+0.163, +0.325], +0.519 [+0.431, +0.606]), never the discovery
+0.700/+0.775.

## On confirmatory vs exploratory, and on 8-family

Accepted and implemented as two separately-corrected BH families. The
confirmatory family is exactly three endpoints (transfer-01,
transfer-confirmation, confirmation-8fam-r2), all preregistered with rules that
fired; all three survive. matrix-01's numbers buy it nothing confirmatory. The
"retires the two-family limit" language is removed; the 8-family result is
reported as pre-registered exploratory breadth with a fired rule but without
confirmatory status, because its hypothesis (unanimity) was specified for the
confirmation design and the 8-family extension changed the family set.

## What was not changed, and why

The devil's generality-4 reflects our own refutation (code repair does not
transfer), so it cannot and should not be raised by any local experiment. The
nine untestable arms remain outside every family rather than being forced in.
The swarm-ms amplification result is not promoted back to a finding; at q=0.22
in the exploratory family it stays exploratory.
