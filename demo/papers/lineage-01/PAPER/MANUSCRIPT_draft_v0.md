# DRAFT v0 — 作者复核前不得引用、不得投稿

> 状态：初稿（agent 执笔，2026-10-09）。每个数字后跟载体；无载体的句子已标 [NEEDS-CARRIER]。
> 作者必须逐句复核、修改、签字后才进入投稿流程。本稿不出 PAPER/ 目录。

---

# The Judge Deleted the Correct Answers: A Text-Pattern Grading Bug in Failure-Diagnosis Tasks That Manufactured a Capability Regression

## Abstract

A published checkpoint regression in the `copilot-3b-lora` lineage — v3b→v3c,
McNemar 1:14, exact p=0.001 — was withdrawn, re-run clean, and found wrong in
both directions at once. Scoring only answered items, v3c beats v3b 0.7778 to
0.7317 (+0.0461; paired Wilcoxon exact two-sided p=0.03125, 6 better in v3c, 0
in v3b, 36 ties over 42 common items): no capability regression. The
production judge had deleted ten answers from a family scoring a perfect 1.0 (tied-highest with `reviewer_qa`) because a
text-pattern runtime rule (`classify_runtime`) flags short outputs containing
`timeout` — and the deleted items (c021–c030) are `failure_diagnosis`
questions whose prompts contain that exact phrase. The same rule had been
patched in 2026-07; the August model rebuild expired the fix because no
regression test pinned short-but-correct diagnoses. A structural patch (no
length threshold; prompt-supplied cues are never runtime evidence) deletes
0/10 where the old rule deleted 10/10, with test suite 39→47 green.
Separately, v3c fails to terminate on 8/50 items, characterized across
cold, hot, and deliberately contended legs with byte-identical outputs —
an availability defect orthogonal to capability.
Evidence is single-task-family (all 16 deletions are `failure_diagnosis`);
all claims are bounded accordingly.

## 1. Introduction

A p=0.001 significant regression is the kind of result that ends an
investigation. This one restarted it. The v3b→v3c step of the `copilot-3b-lora`
checkpoint lineage scored 1 fixed against 14 broken on an exact McNemar test
(p=0.0010), was published internally, and was then withdrawn when four
experiments were found sharing one unlocked inference server. A clean re-run
under an exclusive lock reproduced no regression — and then the numbers did
something stranger: on the same clean data, three defensible scorings of the
identical 50 items give −0.0234, +0.0461, and −0.0784. A single published
number was wrong in both directions at once: it invented a capability loss
that does not exist, and it hid an availability loss that does.

This paper is about the judge, not the model. Its scope is deliberately
narrow: one text-pattern grading rule, one task family (`failure_diagnosis`),
sixteen deleted correct answers, and one expired patch. The v3c checkpoint's
8/50 non-terminations are characterized in §5 (three-leg termination line,
STOP-EXTEND): an availability defect on a separate axis from capability.

No sentence of this paper asserts a v3c capability regression. That claim is
dead (STOP-REFUTED on the pre-registered criterion).

## 2. Background and lineage

The `copilot-3b-lora` lineage (v1, v2, v3, v3b, v3c) was evaluated on a fixed
50-item copilot eval (10 items each of `eval_yaml`, `failure_diagnosis`,
`report_summary`, `reviewer_qa`, `verifier_design`). Two facts about the
lineage must be stated before any rate is quoted. First, v1 never produced a
single model output: both runs show 50/50 HTTPError, and the artifact is
unloadable (HTTP 500 tensor-shape mismatch; blob 3.58 GB against 6.18 GB for
all four siblings; NOT_RECOVERABLE — a rebuild would yield a new arm). There
is no five-checkpoint lineage; four checkpoints were measured. Second, the
original round found per-version runtime-error rates of 2/50 (v3), 5/50
(v3b), and 18/50 (v3c), and a v3b→v3c McNemar of 1:14 (exact p=0.0010,
recomputed from the raw `out_*.jsonl` under the rule "not `runtime_error`").

The published v3c rate of 0.7083 (n=32) was withdrawn after the shared-server
confound was identified: four experiments calling one unlocked ollama
instance, with timeouts and short outputs baked into prediction files and
scored as model failures. Exclusive access heals v3b completely — its 5
original timeouts vanish and it becomes the first 50/50 unexcluded version —
which confirms the infrastructure lesson without explaining the 1:14.

## 3. Clean re-run

The pre-registered envelope specified 250 items over five versions; the run
delivered v3b and v3c at 50 items each (v1 unloadable; v2/v3 outside the
paired comparison; `result.json` must not be cited as a five-version
lineage). Generation used the production `gen()` verbatim (temperature 0, no
`num_predict`, 150 s timeout, `[:1500]` truncation). The single deliberate
difference from the original round is exclusive inference access, held via a
file lock with a 30 s sidecar poller (121 polls, 0 competing processes
in `watch_sidecar_20261009.jsonl`, window 01:06:37–02:06:46).

Results on the production scorer: v3b 0 exclusions in 50; v3c 18 exclusions
in 50 — 8 harness timeouts plus 10 items deleted by `classify_runtime` (next
section). Under the registered rule the McNemar is significant and the
criterion returns STOP-REFUTED for the original regression claim. The
registered verdict stands; what follows re-examines what the rule counted.

## 4. The grading defect

`classify_runtime` marks an answer a runtime error — excluding it from the
denominator with `score=None` — when a short (<200 character) output contains
`timeout`, `connection refused`, or `240s`. Items c021–c030 are
`failure_diagnosis` questions whose prompts contain `connection refused after
240s timeout`. Ten correct, concise v3c answers (38–101 characters) were
therefore deleted; v3b answered the same family verbosely (all ten ≥873
characters, vs the 200-char guard; one item reaches the harness's own
1500-char truncation cap, so the true maximum is unobserved) and was immune. Verbosity decided who was excluded — the exact
asymmetry a paired test must not be given.

The differential was proven both ways on the committed answers
(`prove_red_differential.py`, re-run for this paper): the old rule deletes
10/10 of v3c's c021–c030 and 0 of v3b's answers to the same family; the
structural replacement (prompt-supplied cues are never runtime evidence; no
length threshold) deletes 0 on both arms. Rescoring changes nothing already
counted: clean v3b stays 0 excluded at 0.7317 (n=50); clean v3c keeps the
same 8 harness-failure ids at 0.7778 over 42 answered items.

The defect is not new. A 2026-07 analysis of the same scorer on the same
task family documented the same deletions (c021/c022/c024, verbatim) and
patched them — with a length guard (`len(text) >= 200` exempts). The five
`copilot-3b-lora*` manifests were rebuilt that August; October's v3c answers
concisely (median 27 characters) and detonated the residual hole. The test
suite pinned long-answer immunity and due echoes, but nothing pinned
short-but-correct diagnoses. A fix verified once, against a rebuildable
artifact, without a regression test, has a shelf life. The replacement patch
ships 47 tests (from 39), including the real c021 case and a same-content /
two-lengths agreement test.

Blast radius, measured rather than asserted: a full-tree scan of 83
`out_*.jsonl` finds 196 `runtime_error` entries, all in lineage-01; the 16
judge deletions (10 v3c + 6 v2, independently recomputed from raw files) are
all `failure_diagnosis`. The other 30 pipeline files contain zero. The claim
of this paper is bounded to this task class accordingly.

## 5. Availability defect: v3c does not terminate on 8/50 items

The same eight ids as the original round (c001–c004, c006–c008, c035) fail
to terminate: a numbered list past item 75 with no EOS (shape as documented
in the preregistration draft §0; this run measured stop vs non-stop only).
Three legs, one verdict
(`runs/lineage-01-termination/round-01/termination.jsonl`, 134 rows):

| leg | condition | outcome |
|---|---|---|
| L1 | v3c, 8 items × 5 reps, no cap | 40/40 hit the 150 s client timeout, 0 chars |
| L2 | v3b, same items × 5 | 40/40 `done_reason="stop"`, byte-identical outputs per item |
| L3a / L3b / L3c | cold / hot + 30 warmups / deliberate qwen3:0.6b contention (14 calls) | 8/8 `length` (1024-token ceiling) each leg; outputs byte-identical across all three legs per item |

Contention slows timing (114–147 s vs 109–116 s) without changing outcomes.
One L3b attempt ran 4/8 HTTPError under GPU-trainer contention invisible to
process monitoring; the whole leg was voided by cutoff timestamp and re-run
clean — the void record, not the data, is what makes this section trustworthy.
This defect is off the capability axis (v3c outscores v3b on everything it
answers, +0.0461) and above infrastructure (reproduced under an exclusive
lock): a property of the checkpoint itself.

## 6. Three rulers on one dataset

On the identical clean 50 items (`artifacts/fixed/comparison.json`,
`adjudicate_corrected.py`):

| scoring | v3b | v3c | diff |
|---|---|---|---|
| published (production judge) | 0.7317 | 0.7083 | −0.0234 |
| answered-only | 0.7317 | 0.7778 | +0.0461 (paired Wilcoxon exact p=0.03125; 6:0:36 over 42) |
| non-answers as zero | 0.7317 | 0.6533 | −0.0784 |

Error A (invented capability loss): the judge deleted v3c's best-scoring
family. Error B (hidden availability loss): the 8 non-terminations left the
denominator. One correction to our own record: an earlier counterfactual
scored empty outputs through the checks, where vacuous passage of negative
checks awarded half credit (0.7367/+0.0050, withdrawn in amendment A6);
non-answers must score 0.0. v2 shows the same disease (published 0.6759 on
n=36 → 0.7222 answered-only on n=42 → 0.6067 with non-answers as zero), so
any monotonicity claim over the lineage is unstatable until the denominator
is fixed. Methodological moral: when the denominator moves per arm, the word
"regression" is undefined — fix the denominator first, then discuss
direction.

## 7. Related work

LLM-as-judge biases (position, length, format) are established. This work
adds a new shape: **coupling between a judge's text-pattern rules and the
task text itself** — the task supplies the cue words, the answer merely uses
them, and the judge reads usage as failure. It also documents a failure mode
of fixes: verification against a rebuildable artifact, without a regression
test pinning the exact property, expires silently. No FDR machinery is
relevant here and none is invoked: the case involved a single paired test
(K=1, no p-value family), where multiplicity correction is vacuous — a fact
established separately and not relitigated.

## 8. Conclusion and boundaries

Capability did not regress (answered-only +0.0461). The judge deleted correct
answers (16 items, `failure_diagnosis`, patch delivered with bilateral
proof). Availability regressed independently (8/50 non-terminations,
three-leg characterization in §5). Boundaries:
single task family; the v1 arm of the lineage was never measured; the rerun
envelope was never signed (conducted and labeled post-hoc); all scorer
numbers refer to the fixed scorer (base `b05cf87` plus the merged patch, commit `cad68c7`, live since 2026-10-10, unpushed); the pre-merge baseline is preserved frozen (`frozen/prod_scorer_20261009.py`). Frozen evidence, hashes, and the script index are listed in
`REPRODUCE.md`; every number above recomputes from them.

---

## 作者复核清单（逐项签字后删除本节）

- [ ] §2 v1 段：50/50 HTTPError 为原始文件实测；"不可加载 NOT_RECOVERABLE"转引 amendment A7（本人是否接受该转引？）
- [ ] §3 独占声明：121 轮询 0 竞争（载体 `watch_sidecar_20261009.jsonl`，已数过 121 行 0 竞争；本人是否抽查过该文件？）
- [ ] §4 c021–c030 对照表：是否与 `judge_length_coupling_check.py` 输出逐项对过？
- [ ] §6 表格三行：是否跑过 `rescore_lineage_fixed.py` 复现 `comparison.json`？
- [ ] §6 A6 自纠：0.7367 作废声明是否准确？
- [ ] 标题收窄："in Failure-Diagnosis Tasks" 是否接受？venue 是否仍定 workshop/short？
- [ ] 全文无"v3c 能力退化"肯定句（全文搜索 regress*/退化 等价表述逐条确认）。
- [ ] envelope 不签的决定是否维持（签了则 §3、§8 与 REPRODUCE 全改）。
