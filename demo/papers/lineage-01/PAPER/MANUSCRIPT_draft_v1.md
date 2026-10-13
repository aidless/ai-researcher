# DRAFT v1 — 作者复核前不得引用、不得投稿

> 状态：Major Revision 改写稿（agent 执笔，2026-10-10），回应两轮最高标准审稿。
> 相对 v0 的结构性变化：标题换方向；"能力"拆三轴；端到端为主分析；
> "correct" 操作化定义＋12/4 分层；敏感性分析进正文；§3 加判据盒；
> 相关工作搭骨架（引用待验，无一条编造）。
> 作者必须逐句复核、修改、签字后才进入投稿流程。本稿不出 PAPER/ 目录。

---

# The Judge Deleted Correct Answers: Text-Pattern Coupling in Failure-Diagnosis Evaluation Masks an Availability Regression

## Abstract

A published checkpoint regression in the `copilot-3b-lora` lineage — v3b→v3c,
McNemar 1:14, exact two-sided p=0.0010 — was withdrawn, re-run clean, and found
wrong in both directions at once. We split "capability" into three axes and
report all three. **End-to-end task success** (non-answers scored 0, n=50):
v3b 0.7317 vs v3c 0.6533, diff −0.0783, paired Wilcoxon p=0.0490 (marginal),
sign test 6+/8− p=0.79, bootstrap 95% CI [−0.1717, +0.0050] crossing zero.
**Conditional answer quality** (answered items only, n=42): v3b 0.7282 vs
v3c 0.7778, diff +0.0496, paired Wilcoxon p=0.03125 (6 better in v3c, 0 in
v3b, 36 ties; post-hoc, not pre-registered). **Availability** (termination):
v3c fails to terminate on 8/50 items, characterized across cold, hot, and
deliberately contended legs with byte-identical outputs. The production judge
had deleted ten v3c answers from a family scoring a perfect 1.0
(tied-highest with `reviewer_qa`) because a text-pattern runtime rule
(`classify_runtime`) flags short outputs containing `timeout` — and the
deleted items (c021–c030) are `failure_diagnosis` questions whose prompts
contain that exact phrase. Twelve of sixteen rescued items across both arms
are substantive diagnoses; four are bare trigger-phrase repeats that pass the
keyword checks vacuously (reported separately, §4). The same rule had been
patched in 2026-07; the August model rebuild expired the fix because no
regression test pinned short-but-correct diagnoses. A structural patch (no
length threshold; prompt-supplied cues are never runtime evidence) deletes 0
where the old rule deleted (10 v3c + 6 v2), with 47 tests passing. Evidence
is single-task-family; all claims are bounded accordingly.

## 1. Introduction

A p=0.0010 significant regression is the kind of result that ends an
investigation. This one restarted it — twice. The v3b→v3c step of the
`copilot-3b-lora` checkpoint lineage scored 1 fixed against 14 broken on an
exact McNemar test, was published internally, and was withdrawn when four
experiments were found sharing one unlocked inference server. A clean re-run
under an exclusive lock reproduced no answered-only regression — and then the numbers did
something stranger: on the same clean data, defensible scorings of the
identical 50 items give −0.0784, +0.0496, and −0.0234, and the headline
direction flips again if non-answers receive half instead of zero credit
(§6). A single published number, −0.0234, was wrong in both directions at
once: it invented a conditional-quality loss that does not exist, and it hid
an end-to-end availability loss that does.

This paper's central claim is methodological, not empirical: **when the
scoring rule, the denominator, and availability are entangled, the word
"regression" is undefined until each is fixed.** We therefore split the
vague "capability" into three axes and report all three with their
fragilities stated: (1) end-to-end task success (non-answers 0, primary);
(2) conditional answer quality (answered items only, secondary);
(3) availability/termination (separate axis, §5). No sentence of this paper
asserts an unconditional capability regression in either direction. The
original "v3c regressed" claim is dead (STOP-REFUTED); so is its mirror image
"v3c did not regress" as an unconditional statement — the end-to-end
evidence is marginal (p=0.0490, CI crossing zero) and convention-dependent
(§6).

"Correct", throughout this paper, means one operational thing: **passes every
reference check the judge itself applies**. Twelve of the sixteen rescued
items additionally contain causal explanation and remediation beyond the
prompt phrase (exemplified by c021, quoted in §4); four are bare
trigger-phrase repeats that satisfy the keyword checks vacuously. We report
both layers and do not conflate them; whether keyword checks measure human
correctness is a validity question about the checks, separate from this
paper's claim that the judge contradicted them.

## 2. Background and lineage

The `copilot-3b-lora` lineage (v1, v2, v3, v3b, v3c) was evaluated on a fixed
50-item copilot eval (10 items each of `eval_yaml`, `failure_diagnosis`,
`report_summary`, `reviewer_qa`, `verifier_design`). Scores below are mean
partial credits over {0.3333, 0.5, 0.6667, 0.75, 1.0} — not success
proportions; every "rate" in this paper is a mean unless stated. Two facts
about the lineage must be stated before any number is quoted. First, v1 never
produced a single model output: both runs show 50/50 HTTPError, and the
artifact is unloadable (HTTP 500 tensor-shape mismatch; v1 blob 3.58 GB per
amendment A7 against 6.18 GB for all four siblings, the sibling sizes verified
from the blob store; NOT_RECOVERABLE
— a rebuild would yield a new arm). There is no five-checkpoint lineage; four
checkpoints were measured. Second, the original round found per-version
runtime-error counts of 50/50 (v1), 14/50 (v2), 2/50 (v3), 5/50 (v3b), and
18/50 (v3c), and a v3b→v3c McNemar of 1:14 (exact two-sided p=0.0010,
recomputed from the raw `out_*.jsonl` under the rule "not `runtime_error`").

The published v3c rate of 0.7083 (n=32) was withdrawn after the shared-server
confound was identified: four experiments calling one unlocked ollama
instance, with timeouts and short outputs baked into prediction files and
scored as model failures. Exclusive access heals v3b completely — its 5
original timeouts vanish and it becomes the first 50/50 unexcluded version —
which confirms the infrastructure lesson without explaining the 1:14.

## 3. Clean re-run and the decision rules

The envelope specified 250 items over five versions; the run delivered v3b
and v3c at 50 items each (v1 unloadable; v2/v3 outside the paired comparison;
`result.json` must not be cited as a five-version lineage). Generation used
the production `gen()` verbatim (temperature 0, no `num_predict`, 150 s
timeout, `[:1500]` truncation). The single deliberate difference from the
original round is exclusive inference access, held via a file lock with a
30 s sidecar poller (121 polls, 0 competing processes in
`watch_sidecar_20261009.jsonl`, window 01:06:37–02:06:46).

**Registration status, stated exactly** (the envelope was drafted but never
signed before the run; we conducted against the draft and label everything
post-hoc — post-hoc analysis with pre-written criteria, not pre-registered
analysis):
- Registered criterion: the kill-switch table in the envelope
  (`confirmed == True` → STOP-EXTEND; `confirmed == False` → STOP-REFUTED),
  where "confirmed" means the v3b→v3c regression reproduces on clean data.
- STOP-REFUTED fired on the original claim because the answered-only
  comparison reverses it (§6), not because nothing is significant: the clean
  exclusion-status table is [[both-kept 32, b-kept/c-cut 18], [b-cut/c-kept 0,
  both-cut 0]] — McNemar discordants 18:0, exact p≈8e-6, direction v3c
  excluded more. That table measures the *judge* (who it excludes), and a
  significant exclusion asymmetry with reversed substantive outcome is
  precisely the finding: the instrument, not the model, moved.
- The answered-only Wilcoxon, the end-to-end Wilcoxon, and the sensitivity
  grid below were NOT pre-registered; they are post-hoc analyses presented
  with full fragility (§6). The primary designation of end-to-end success
  was made in revision (this draft), not before data.

Results on the production scorer: v3b 0 exclusions in 50; v3c 18 exclusions
in 50 — 8 harness timeouts plus 10 items deleted by `classify_runtime` (next
section).

## 4. The grading defect

`classify_runtime` marks an answer a runtime error — excluding it from the
denominator with `score=None` — when a short (<200 character) output contains
`timeout`, `connection refused`, or `240s`. Items c021–c030 are
`failure_diagnosis` questions whose prompts contain `connection refused after
240s timeout`. Ten v3c answers from that family were therefore deleted; v3b
answered the same family verbosely (all ten ≥873 characters, vs the 200-char
guard; one item reaches the harness's own 1500-char truncation cap, so the
true maximum is unobserved) and was immune. Verbosity decided who was
excluded — the exact asymmetry a paired test must not be given.

The differential was proven both ways on the committed answers
(`prove_red_differential.py`, re-run for this paper): the old rule deletes
10/10 of v3c's c021–c030 and 0 of v3b's answers to the same family; the
structural replacement (prompt-supplied cues are never runtime evidence; no
length threshold) deletes 0 on both arms. Rescoring changes nothing already
counted: clean v3b stays 0 excluded at 0.7317 (n=50); clean v3c keeps the
same 8 harness-failure ids at 0.7778 over 42 answered items.

Content audit of the 16 rescued items (both arms, raw texts): twelve contain
causal explanation and remediation beyond the prompt phrase (e.g. c021:
"connection refused after 240s timeout 是由于模型服务端未启动或未正确配置…
请检查…", 98 chars, fixed score 1.0). Four are bare repeats of the trigger
phrase (38 chars, v3c c030; v2 c027/c029/c030), which satisfy the keyword
checks vacuously. Both layers are reported; the paper's "deleted correct
answers" claim means "deleted items passing every reference check", with the
12/4 split stated here, not in a footnote.

The defect is not new. A 2026-07 analysis of the same scorer on the same
task family documented the same deletions (c021/c022/c024, verbatim) and
patched them — with a length guard (`len(text) >= 200` exempts). The five
`copilot-3b-lora*` manifests were rebuilt that August; October's v3c answers
concisely (median 27 characters over answered items) and detonated the
residual hole. The test suite pinned long-answer immunity and due echoes,
but nothing pinned short-but-correct diagnoses. A fix verified once, against
a rebuildable artifact, without a regression test, has a shelf life. The
replacement patch ships 47 tests passing (from 39; verified in-repo),
including the real c021 case and a same-content / two-lengths agreement test.

Blast radius, measured rather than asserted: a full-tree scan of 83
`out_*.jsonl` finds 196 `runtime_error` entries, all in lineage-01; the 16
judge deletions (10 v3c + 6 v2, independently recomputed from raw files) are
all `failure_diagnosis`. Old-vs-new rule comparison over all 600 saved
prediction texts corpus-wide: 42 rescued (6 v2 + 10 v3c, plus run mirrors),
0 newly flagged. Synthetic stress probes across the other four task families
(short correct answers embedding trigger words naturally, plus true-echo and
clean controls, 12 probes): 11/12 behave as designed; one boundary found — a
context-free bare `"timeout"` fragment is no longer flagged (old rule
flagged it). In-corpus impact of that boundary: zero texts. End-to-end
impact even if hit: near zero either way (excluded vs ~0 score). Reported as
a known boundary, not hidden. The claim of this paper is bounded to this
task class accordingly.

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

Strictly, "non-termination" here means no EOS within 1024 tokens / 150 s —
not proven infinite. Contention slows timing (114–147 s vs 109–116 s)
without changing outcomes. One L3b attempt ran 4/8 HTTPError under
GPU-trainer contention invisible to process monitoring; the whole leg was
voided by cutoff timestamp and re-run clean — the void record, not the data,
is what makes this section trustworthy. This defect is off the capability
axis (v3c outscores v3b on everything it answers, +0.0496 on common items)
and above infrastructure (reproduced under an exclusive lock): a property of
the checkpoint itself.

## 6. Three scorings, one of them primary

On the identical clean 50 items (`artifacts/fixed/comparison.json`,
`adjudicate_corrected.py`). Scores are mean partial credits over
{0.3333, 0.5, 0.6667, 0.75, 1.0} unless stated; "rates" below are means.

| scoring (primary first) | v3b | v3c | diff | n | test |
|---|---|---|---|---|---|
| end-to-end (non-answers 0) | 0.7317 | 0.6533 | −0.0783 | 50 | paired Wilcoxon p=0.0490; sign 6+/8− p=0.79; bootstrap 95% CI [−0.1717, +0.0050]; rank-biserial −0.278; Hodges-Lehmann −0.2083 |
| conditional (answered-only) | 0.7282 | 0.7778 | +0.0496 | 42 common | paired Wilcoxon p=0.03125; 6 better v3c, 0 v3b, 36 ties (post-hoc); Hodges-Lehmann +0.3333 |
| production judge | 0.7317 | 0.7083 | −0.0234 | 32 kept | exclusion McNemar 18:0, p≈8e-6 (§3) |

Sensitivity of the headline to the non-answer convention (8 items):

| non-answers scored as | v3c mean | diff | Wilcoxon p |
|---|---|---|---|
| 0 (worst) | 0.6533 | −0.0783 | 0.0490 |
| 0.5 | 0.7333 | +0.0017 | 0.55 |
| 1.0 (best) | 0.8133 | +0.0817 | 0.0002 |

Computation trap, stated so re-analysts don't trip on it: scipy's
Wilcoxon `auto` mode selects the asymptotic approximation when ties are
present, returning p=0.0235 on the answered-only data; with n=6 non-ties the
exact enumeration (2/64 = 0.03125) is trivially computable and is what we
report. Default-software p-values differ in the third decimal here —
irrelevant to conclusions, fatal to unattributed reproduction.

Methods: bootstrap resamples the 50 paired differences with replacement
(20,000 replicates, seed 20261010); Wilcoxon uses the asymptotic
tie-corrected distribution (exact enumeration is infeasible past n≈25 paired
ranks; the answered-only n=6 case is exact). Denominators nest strictly:
production-kept 32 ⊂ answered 42 ⊂ all 50 — the three rows are not three
samples but three conventions on one dataset, which is why their
disagreement is a finding about conventions, not sampling noise.
Missingness: the 8 non-answers are deterministic per item (40/40 L1
timeouts, §5), i.e. systematically missing conditional on the item —
neither MAR nor MCAR. No imputation is performed; the sensitivity grid above
*is* the missing-data analysis, spanning worst-case (0) through best-case
(1.0) with the midpoint shown.

The end-to-end verdict flips sign across defensible conventions; its own
bootstrap CI crosses zero while Wilcoxon sits at p=0.0490 and the sign test
is null (p=0.79). We report this fragility as the finding, not as a
footnote: **the "regression" verdict is identified only up to the scoring
convention for non-answers, which is a normative choice, not an empirical
discovery.** Neither "v3c regressed end-to-end" nor its mirror is robust;
what is robust is that the production number (−0.0234) coincides with none
of the convention-fixed values and that the judge deleted items passing all
its own checks. One correction to our own record: an earlier counterfactual
scored empty outputs through the checks, where vacuous passage of negative
checks awarded half credit (0.7367/+0.0050, withdrawn in amendment A6);
non-answers must score 0.0. v2 shows the same disease (published 0.6759 on
n=36 → 0.7222 answered-only on n=42 → 0.6067 with non-answers as zero), so
any monotonicity claim over the lineage is unstatable until the denominator
is fixed. Methodological moral: when the denominator moves per arm, the word
"regression" is undefined — fix the denominator first, then discuss
direction.

## 7. Related work

LLM-as-judge biases are established: Zheng et al. (2023) document position,
verbosity, and self-enhancement biases with mitigations, reporting >80%
GPT-4–human agreement once addressed (NeurIPS 2023, arXiv:2306.05685);
Wang et al. (2023) give an early meta-evaluation of ChatGPT as an NLG
evaluator, noting prompt- and dataset-sensitivity (NewSum 2023, pp. 1–11,
DOI 10.18653/v1/2023.newsum-1.1) — both verified 2026-10-10 via ACL
Anthology / NeurIPS proceedings listings.
This work adds a distinct, mechanism-level shape: **coupling between a
judge's text-pattern rules and the task text itself** — the task supplies
the cue words, the answer merely uses them, and the judge reads usage as
failure. It differs from verbosity bias (a preference gradient over length):
here length determined *exclusion* through a hard rule interacting with task
text, deleting a whole family on one arm and none on the other. The work
also documents a failure mode of fixes: verification against a rebuildable
artifact, without a regression test pinning the exact property, expires
silently. Broader evaluation-validity concerns — benchmark inflation and
contamination (e.g. BDC survey arXiv:2406.04244; ConTAM analysis
arXiv:2411.03923; retro-holdout inflation up to 16pp on TruthfulQA,
arXiv:2410.09247; all verified as existing preprints 2026-10-10, details to
be confirmed by author before submission) — share this paper's moral that
scores move for infrastructural reasons, but none addresses judge-internal
text-pattern coupling, which is this paper's scope.
(Multiplicity correction is vacuous here: a single paired test, K=1.)

## 8. Conclusion and boundaries

End-to-end task success declines under the worst-case convention (−0.0783,
marginal and convention-fragile, §6) — we do not claim more. Conditional
answer quality favors v3c (+0.0496 on common items). The judge deleted
items passing all its own checks (16 items, `failure_diagnosis`, patch
delivered with bilateral proof, merged 2026-10-10 commit `cad68c7`,
unpushed). Availability regressed independently (8/50 non-terminations,
three-leg characterization in §5). Boundaries: single task family; the v1
arm of the lineage was never measured; the rerun envelope was never signed
(conducted and labeled post-hoc); all scorer numbers refer to the fixed
scorer (base `b05cf87` plus merged patch); the pre-merge baseline is
preserved frozen. Frozen evidence, hashes, and the script index are listed in
`REPRODUCE.md`; every number above recomputes from them.

---

## 作者复核清单 v1（逐项签字后删除本节；新增项标★）

- [ ] §2 v1 段：50/50 HTTPError 为原始文件实测；"不可加载 NOT_RECOVERABLE"转引 amendment A7（本人是否接受该转引？）
- [ ] §3 独占声明：121 轮询 0 竞争（载体 `watch_sidecar_20261009.jsonl`，已数过；本人是否抽查过？）
- [ ] §3 注册状态段：post-hoc 表述是否接受？"criterion pre-written, analysis post-hoc" 的定性是否准确？
- [ ] §4 c021–c030 对照表：是否与 `judge_length_coupling_check.py` 输出逐项对过？
- [ ] §4 新增：12 实质诊断 vs 4 裸复读的分层是否接受？裸复读 4 项的列法是否恰当？
- [ ] §4 新增：裸 `"timeout"` 碎片边界（11/12 探针）是否如实？in-corpus 影响零的断言是否接受？
- [ ] §6 表格三行：是否跑过 `rescore_lineage_fixed.py` 复现 `comparison.json`？
- [ ] §6 新增：敏感性表格＋"结论随惯例翻转"段落是否接受？（这是全文最强的主张，需本人首肯）
- [ ] §6 新增：bootstrap CI 过零＋Wilcoxon p=0.049＋符号 p=0.79 三数并列——是否接受这种"自我拆台"式呈现？
- [ ] §7 引用复核：Zheng/MT-Bench 与 Wang/NewSum 已验（venue/页码/DOI）；三篇 arXiv（2406.04244/2411.03923/2410.09247）仅验存在，细节（作者/年/页码）填实前不得投。
- [ ] 标题收窄："Masks an Availability Regression" 是否接受？venue 是否仍定 workshop/short？
- [ ] 全文无"v3c 能力退化"肯定句、无无条件"no capability regression"（全文搜索逐条确认）。
- [ ] envelope 不签的决定是否维持（签了则 §3、§8 与 REPRODUCE 全改）。
- [ ] ★ L3b 作废重跑段：整腿作废（不断行修补）的处理是否接受？截断时间戳裁决规则是否恰当？
- [ ] ★ v3b-42 均值 0.7282 vs 表中 v3b 列 0.7317：§6 表已分栏注明，是否接受这种呈现？
