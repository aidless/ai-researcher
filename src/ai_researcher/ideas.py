"""Idea engine: limitations sections + failure-mode library -> ranked hypotheses.

A top-tier paper starts from a gap, not a method. This module mines the two
places where the account has already written its gaps down:

  1. Limitations / Future Work sections of its own manuscripts. Each "future
     work should ..." is a hypothesis the authors already believe is worth
     testing -- structured here with an explicit falsification criterion.
  2. The failure-mode library (references/failure-modes.md). Each FM's
     meta-lesson names a dimension along which current practice is wrong;
     "换稿件域就是新的误报来源" is itself a research program.

Every candidate is cost-tiered, because cost determines what "fully automatic"
can actually attempt unattended:
  T0 analysis-only  -- reanalysis of already-committed data. No new calls.
                      The machine can do all of it tonight.
  T1 local-compute  -- runs on this machine's ollama / GPU. Bounded, free.
  T2 api-budget     -- needs paid calls. Requires a human-approved spend.

Ranking is publishability x cheapness: a T0 that answers a stated limitation
outranks a T2 that needs a new dataset. The output is envelope drafts, not
prose -- each candidate maps directly onto envelope.py fields.

Usage:
    python -m ai_researcher.ideas mine <paper_dir>... --fm references/failure-modes.md
    python -m ai_researcher.ideas rank --out ideas_ranked.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# Manually curated from the account's own manuscripts. Each entry names the
# source line so the gap stays traceable. Machine extraction of Limitations
# sections is left as follow-up; hand curation is more reliable and these do
# not change often.
SEED_GAPS = [
    {"id": "mm-epc-bounded-metric",
     "source": "mm-epc/paper/mm_epc_paper.tex:175",
     "gap": "gamma is unbounded above; simplex geometry deflates it for high-PCI references",
     "hypothesis": "Jensen-Shannon divergence (or Hellinger / total variation) gives the same qualitative pattern (cross-model >> self-eval) with stable cross-condition comparisons",
     "falsifies": "JS divergence reverses the ordering (self-eval >= cross-model)",
     "tier": "T0",
     "needs": "committed weight vectors + PCI values from mm-epc evidence",
     "venue": "workshop or appendix extension",
     "tension": "Gamma is unbounded above and deflated by simplex geometry for high-PCI references, so every cross-condition comparison inherits an unknown distortion. A bounded metric preserving the ordering would make the numbers comparable; without it they are suggestive, not comparable.",
     "importance": "",
     "bold": False},
    {"id": "mm-epc-balanced-design",
     "source": "mm-epc/paper/mm_epc_paper.tex:491",
     "gap": "8 text-domain vs 3 visual-domain strategies biases weights toward text before any evaluator effect",
     "hypothesis": "reanalysis on a balanced 3+3 subset preserves the cross-model >> self-eval pattern with a cleaner modality estimate",
     "falsifies": "balanced subset erases the cross-model excess (pattern was an artifact of slot counts)",
     "tier": "T0",
     "needs": "committed per-strategy weights",
     "venue": "workshop or appendix extension",
     "tension": "The published cross-model excess rests on 8 text vs 3 visual strategies, so text has more slots before any evaluator acts. If the excess is slot artifact, a headline result misattributes bias to evaluators that belongs to design. Balancing decides which story is true.",
     "importance": "",
     "bold": False},
    {"id": "mm-epc-evaluator-diversity",
     "source": "mm-epc/paper/mm_epc_paper.tex:489",
     "gap": "findings specific to GPT-4o as evaluator; Claude/Gemini/Qwen-VL unknown",
     "hypothesis": "at least one other multimodal evaluator shows PCI magnification >= 2x over self-eval",
     "falsifies": "no tested evaluator exceeds 1.5x (collapse is GPT-4o-specific, not general)",
     "tier": "T2",
     "needs": "paid multimodal API calls, ~2000 per evaluator",
     "venue": "full paper if positive, workshop if mixed",
     "tension": "Every number in the collapse finding conditions on GPT-4o as evaluator. If no other evaluator reproduces it, the phenomenon is a single-model quirk cited as a general law. One replication on a second family settles generality either way.",
     "importance": "",
     "bold": False},
    {"id": "gsm8k-cross-model-transfer",
     "source": "gsm8k round-2 established step-calc on qwen2.5:7b only",
     "gap": "policy effect may be model-specific; no cross-family evidence",
     "hypothesis": "step-calc shows positive gain on llama3.1:8b heldout40",
     "falsifies": "gain <= 0 on the second family (effect does not transfer)",
     "tier": "T1",
     "needs": "local ollama, 160 calls, ~25 min",
     "venue": "workshop replication or extension section",
     "tension": "Step-calc was established on one model family. Prompting policies routinely fail to transfer, and every citation of the effect outside qwen2.5 assumes what was never tested. One second family decides whether this is a policy property or a model quirk.",
     "importance": "",
     "bold": False},
    {"id": "fm-detector-false-positive-rate",
     "source": "FM-30/FM-31 meta-lesson: detector false-positive rate decides its credibility",
     "gap": "no measured false-positive rate for any of the account's own checkers on held-out manuscripts",
     "hypothesis": "scan_number_consistency reports <= 1 false mismatch per 10 clean pages on manuscripts it has never seen",
     "falsifies": "> 3 false mismatches per 10 pages (the gate trains users to ignore it)",
     "tier": "T1",
     "needs": "2-3 clean manuscripts + local runs",
     "venue": "methods note, strengthens every paper that cites the checker",
     "tension": "Every paper on this account cites checkers whose false-positive rate was never measured. An uncalibrated gate trains users to ignore it (FM-30), so all downstream verifications rest on an unknown foundation. Measuring it is one clean experiment away.",
     "importance": "every paper on this account cites these checkers; an unmeasured "
                   "false-positive rate means every cited verification is uncalibrated",
     "bold": False},
    {"id": "mimicry-detector",
     "source": "Chen & Wang 2026 (arXiv:2606.07410): R1 shows topological mimicry -- surface form of reasoning without functional role; reflection effective only within deduction; spinning-wheel traces unpenalized",
     "gap": "the field rewards the appearance of reasoning; no operational detector separates mimicry traces from genuine deductive traces",
     "hypothesis": "a checker combining cross-trace stability (same question, resampled) with reflection-placement scoring (reflection inside deduction vs inside analysis loops) separates successful from failed long-CoT traces above chance on local reasoning models",
     "falsifies": "no separation above chance on deepseek-r1:7b traces (mimicry undetectable at this scale, or the proposed signals carry no information)",
     "tier": "T1",
     "needs": "local deepseek-r1:7b traces (verified working tonight) + checker infrastructure already in repo",
     "venue": "full paper if positive (new metric + validation); methods note if partial",
     "importance": "every lab now trains long-CoT models and none can tell mimicry from reasoning; a working detector changes training (penalize spinning-wheel) and evaluation (score deduction, not length)",
     "tension": "Reasoning models are scaled on the assumption that longer chains mean deeper thought, yet Chen & Wang 2026 show R1 loops through local checks without logical progress while being rewarded for it. There is no operational test distinguishing a trace that reasons from one that performs reasoning. Without it, every long-CoT benchmark confounds verbosity with deduction.",
     "bold": True},
    {"id": "swarm-evaluator-collapse",
     "source": "Kimi K2.5/K2.6 Agent Swarm (100-300 subagents, 1500-4000 steps) meets the account's evaluator-collapse line (mm-epc: MPCI=1.449 cross-model)",
     "gap": "evaluator bias measured only for single-agent TTRL; swarm orchestration may amplify it (more outputs to cherry-pick) or dampen it (diversity across subagents) -- unknown either way",
     "hypothesis": "evaluator-preferred strategies concentrate faster (higher PCI per round) as the number of parallel subagents grows, holding evaluator and task fixed",
     "falsifies": "flat PCI-vs-swarm-size curve (swarm diversity cancels evaluator bias, bounding the phenomenon to single-agent settings)",
     "tier": "T1",
     "needs": "local models as executor swarm (2-8 parallel) + single evaluator; playground/evoagent as harness",
     "venue": "workshop first (new setting), full paper if the curve is clean",
     "importance": "the industry is deploying 100+ agent swarms with no characterization of how evaluator bias scales with swarm size; a clean curve here is the first",
     "tension": "Agent swarms went from 0 to 300 subagents in eighteen months with no measurement of whether the evaluator bias documented for single agents amplifies or cancels at swarm scale. Deploying unevaluated scaling is how reward hacking ships to production.",
     "bold": True},
    {"id": "inference-sweet-spot",
     "source": "Thoughtology (Marjanovic et al., TMLR 2025): DeepSeek-R1 has a reasoning sweet spot where extra inference impairs performance; persistent rumination obstructs exploration",
     "gap": "sweet-spot claim established on frontier R1; unknown whether it replicates on small local reasoning models and whether it is task-dependent",
     "hypothesis": "on deepseek-r1:7b, accuracy as a function of capped reasoning length is non-monotonic (rises then falls) on at least one of math/code/logic task families",
     "falsifies": "monotone non-decreasing accuracy with length on all families (sweet spot is a frontier-scale or task-specific artifact)",
     "tier": "T1",
     "needs": "local deepseek-r1:7b, length caps via num_predict, fixed seeds, McNemar across caps",
     "venue": "replication/extension note; strengthens any paper citing the sweet spot",
     "importance": "inference budgets are real money; if the sweet spot replicates locally, every practitioner should cap reasoning length per task family instead of maximizing it",
     "tension": "Practitioners pay per reasoning token on the assumption that more thinking is better, yet the only systematic study says extra inference can hurt -- on one model family, at frontier scale. Nobody has checked whether the people who can least afford to waste tokens (small-model users) face the same curve.",
     "bold": False},
    {"id": "fail-closed-eval-infrastructure",
     "source": "ICLR 2026 hallucinated-reference desk rejects at scale + AAAI-26 AI-review pilot (AI reviews rated more thorough than human) + this account's 49 gates and mutation-control jobs",
     "gap": "venues detect broken evaluation after submission (desk rejects) or augment reviewers with AI; no published pipeline makes evaluation fail closed before submission",
     "hypothesis": "a pre-submission pipeline (claim ledger + citation verifier + mutation-controlled gates + two-seat review) catches 100% of seeded defects across hallucinated refs, number drift, and swallowed exits on the account's own manuscripts",
     "falsifies": "seeded-defect escape rate above 20% (the pipeline is theater, not enforcement)",
     "tier": "T1",
     "needs": "the account's own repos as test corpus; seeded-defect harness (already partially built as mutation-control)",
     "venue": "systems paper (NeurIPS E&D track: Reproducibility/Auditing/Stress-Testing) or TMLR",
     "importance": "every venue is currently bolting AI onto a broken evaluation pipeline after the fact; a working pre-submission enforcement pipeline is infrastructure the whole field needs",
     "tension": "ICLR 2026 desk-rejected papers for hallucinated references that a script could have caught before submission, while AAAI pilots AI reviewers to cope with 30,000 submissions. Detection after submission wastes everyone's time; enforcement before submission exists nowhere as a published, tested pipeline.",
     "bold": True},
    {"id": "bold-evaluator-disagreement-predicts-collapse",
     "source": "against consensus: the field measures collapse after the fact; "
               "prediction from cheap evaluator disagreement is untested",
     "gap": "no one predicts collapse before running the full protocol; JSD r=0.969 is retrospective",
     "hypothesis": "evaluator-pair JSD computed on <10 probe tasks predicts the full-protocol collapse ordering",
     "falsifies": "probe JSD uncorrelated with full collapse (prediction needs the full run after all)",
     "tier": "T1",
     "needs": "local models, probe tasks, committed full-protocol weights as ground truth",
     "venue": "full paper if positive (actionable early-warning); workshop if mixed",
     "tension": "The field measures collapse after paying for the full protocol, while a retrospective JSD correlation of 0.969 sits unused. If cheap evaluator disagreement predicts collapse, practitioners choose evaluators before spending, not after. If it does not, the correlation is descriptive trivia. One probe experiment decides.",
     "importance": "turns a retrospective measurement into a prospective tool; "
                   "changes how practitioners choose evaluators",
     "bold": True},
]


def rank(ideas: list) -> list:
    """Publishability x cheapness. T0 first, then T1, then T2. Stable order."""
    tier_rank = {"T0": 0, "T1": 1, "T2": 2}
    return sorted(ideas, key=lambda x: (tier_rank.get(x.get("tier", "T2"), 2), x["id"]))


def hamming_rerank(ideas: list) -> list:
    """Hamming (1986): which important problem is each idea working on?

    Re-sorts by importance-first: ideas that answer a stated important problem
    (importance field set, with a reason) outrank ideas that are merely cheap.
    Cheapness decides ties. An idea with no importance claim sorts last no
    matter how cheap -- that is the point: "if it is not important, why do it?"
    """
    tier_rank = {"T0": 0, "T1": 1, "T2": 2}
    def key(x):
        imp = 0 if x.get("importance") else 1
        return (imp, tier_rank.get(x.get("tier", "T2"), 2), x["id"])
    return sorted(ideas, key=key)


def archive_feedback(ideas: list, archive: list) -> list:
    """Close the loop Sakana-style: completed runs feed back into ranking.

    archive: list of {source_gap, verdict, note} from past loop runs
    (STOP-EXTEND / STOP-REFUTED / STOP-INVALID and kill-switch verdicts).
    Rules, all explicit:
    - an idea whose source_gap already produced STOP-EXTEND twice without a
      paper is demoted (diminishing returns; write it up or drop it)
    - an idea refuted twice on independent data is retired, not re-ranked
      (retrying refuted ideas until one passes by chance is p-hacking)
    - an idea whose runs keep dying STOP-INVALID gets a harness flag, not a
      lower rank (broken harness is not a property of the idea)
    Returns (ranked_ideas, actions) where actions lists retire/demote/harness
    decisions with reasons. The archive itself is never rewritten by this
    function -- it is append-only.
    """
    from collections import Counter
    verdicts: dict = {}
    for rec in archive:
        verdicts.setdefault(rec.get("source_gap", "?"), []).append(rec.get("verdict"))
    actions, retired, demoted = [], set(), set()
    for gid, vs in verdicts.items():
        n_ext = sum(1 for v in vs if v == "STOP-EXTEND")
        n_ref = sum(1 for v in vs if v in ("STOP-REFUTED", "STOP-REFUTED-REVERSE"))
        n_inv = sum(1 for v in vs if v == "STOP-INVALID")
        if n_ref >= 2:
            retired.add(gid)
            actions.append({"gap": gid, "action": "retire",
                            "reason": f"refuted {n_ref}x on independent data"})
        elif n_ext >= 2:
            demoted.add(gid)
            actions.append({"gap": gid, "action": "demote",
                            "reason": f"extended {n_ext}x with no paper; write up or drop"})
        if n_inv >= 2:
            actions.append({"gap": gid, "action": "harness-flag",
                            "reason": f"{n_inv}x invalid runs; fix harness, not rank"})
    kept = [x for x in ideas if x.get("source_gap", x.get("id")) not in retired]
    ranked = hamming_rerank(kept)
    # demoted sink below non-demoted at equal importance+tier
    dem = {a["gap"] for a in actions if a["action"] == "demote"}
    ranked.sort(key=lambda x: (x.get("source_gap", x.get("id")) in dem,))
    return ranked, actions


def to_envelope(idea: dict, methods: str, rounds: int = 1) -> dict:
    """Draft an envelope skeleton from a ranked idea. Human fills methods.

    Includes every field envelope.validate() requires, except power numbers
    and approval: power_at_mde ships as 0.0 so validate() REFUSES the draft
    until a human does the power analysis, and approved_by ships empty.
    A draft that passed validation without human input would defeat the
    one-human-decision design.
    """
    return {
        "hypothesis": idea["hypothesis"],
        "methods": methods,
        "max_rounds": rounds,
        "max_cost_usd": 0.0 if idea["tier"] in ("T0", "T1") else 50.0,
        "max_wall_hours": 3.0,
        "kill_switch": [
            {"condition": "confirmed == true", "action": "STOP-EXTEND",
             "note": f"pattern holds: extend to full scale ({idea['venue']})"},
            {"condition": "confirmed == false", "action": "STOP-REFUTED",
             "note": f"falsified as stated: {idea['falsifies']}"},
        ],
        "required_artifacts": ["result.json"],
        "approved_by": "",
        "approved_at": "",
        "seed": 20261006,
        "power": {"n": 0, "alpha": 0.05, "min_detectable_effect": 0.0,
                  "power_at_mde": 0.0},
        "negative_publish": "replication-report",
        "tension": idea.get("tension", ""),
        "source_gap": idea["id"],
    }


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.ideas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--out", default="")
    h = sub.add_parser("hamming")
    h.add_argument("--out", default="")
    e = sub.add_parser("envelope")
    e.add_argument("idea_id")
    e.add_argument("--methods", required=True)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd in ("rank", "hamming"):
        ranked = hamming_rerank(SEED_GAPS) if a.cmd == "hamming" else rank(SEED_GAPS)
        doc = [{"rank": i + 1, **g} for i, g in enumerate(ranked)]
        if a.out:
            Path(a.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(doc, indent=1, ensure_ascii=False)[:2000])
    elif a.cmd == "envelope":
        idea = next(g for g in SEED_GAPS if g["id"] == a.idea_id)
        Path(a.out).write_text(
            json.dumps(to_envelope(idea, a.methods), indent=2, ensure_ascii=False) + "\n")
        print(f"envelope draft for {a.idea_id} -> {a.out} (needs human approval)")


if __name__ == "__main__":
    sys.exit(main())
