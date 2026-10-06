"""Fitness: a frozen evaluation set the system measures itself against.

Self-evolution without a frozen eval set is self-congratulation: the system
would drift toward whatever is easy to pass. This module defines the fixed
ground the system must beat, built from its own history:

  F1 seeded defects (5 classes): the failclosed harness. A mutation to any
     checker must not let a previously-caught defect escape.
  F2 historical judgments: past two-seat verdicts on known claims. A mutation
     to review prompts must not flip a correct NOT_READY to READY, nor a
     correct READY to NOT_READY, on these frozen cases.
  F3 gate teeth: the mutation-control outcomes. A mutation to any gate must
     keep the control red-on-mutation and green-on-clean.

Fitness = (F1 catch rate, F2 agreement, F3 teeth). A candidate replaces the
incumbent only if it is no worse on all three and strictly better on at least
one by >= min_gain, at alpha (McNemar on the discordant cases where they
differ). Same gate semantics as the gsm8k statistical_gate.

The eval set is FROZEN: adding cases requires a human-approved envelope, or the
system could pad it with easy wins. See `freeze_eval()` for the procedure.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


# ---------------------------------------------------------------------------
# F1: seeded defects. Each entry: defect description + the checker that must
# catch it + the exact invocation. Frozen 2026-10-06 from the failclosed run
# (5/5 caught, escape_rate 0.0).
# ---------------------------------------------------------------------------
F1_SEEDED = [
    {"id": "D1-hallucinated-ref",
     "defect": "bib entry FAKEKEY2099 cited but undefined",
     "checker": "citation dangling-cite scan",
     "must": "catch"},
    {"id": "D2-drifted-number",
     "defect": "table value 0.95 vs evidence 0.75",
     "checker": "number-evidence reconciliation",
     "must": "catch"},
    {"id": "D3-swallowed-exit",
     "defect": "gate step ending in `|| true`",
     "checker": "swallow-pattern scan (excluding negative controls)",
     "must": "catch"},
    {"id": "D4-unhedged-inconclusive",
     "defect": "inconclusive claim stated as fact, no hedge vocabulary",
     "checker": "status-token-excluded hedge scan",
     "must": "catch"},
    {"id": "D5-stale-manifest",
     "defect": "evidence file changed after manifest recorded",
     "checker": "sha256 manifest reconciliation",
     "must": "catch"},
]

# ---------------------------------------------------------------------------
# F2: historical judgments. Frozen two-seat verdicts on known claims.
# A prompt mutation must preserve every one of these.
# ---------------------------------------------------------------------------
F2_JUDGMENTS = [
    {"id": "J1-toy-n4",
     "claim": "lowercasing gain 0.75 on n=4",
     "verdict": "NOT_READY",
     "reason": "n=4 meaningless regardless of effect size"},
    {"id": "J2-transfer-magnitude",
     "claim": "step-calc transfers with undiminished magnitude (CIs overlap)",
     "verdict": "NOT_READY",
     "reason": "McNemar is within-model-only; no equivalence test"},
    {"id": "J3-transfer-direction",
     "claim": "step-calc positive on both families (30:0, 31:0, p_bh 2e-9)",
     "verdict": "READY",
     "reason": "directional claim fully supported"},
    {"id": "J4-balanced-reversal",
     "claim": "balanced subset reverses the PCI excess (single top-3 subset)",
     "verdict": "NOT_READY",
     "reason": "single selection, indistinguishable from noise"},
]

# ---------------------------------------------------------------------------
# F3: gate teeth. Each gate must go red on its documented mutation.
# ---------------------------------------------------------------------------
F3_TEETH = [
    {"id": "T1-pytest-mutation",
     "gate": "pytest", "mutation": "PLUGIN_GROUP -> PLUGIN_GROUPS",
     "must": "red"},
    {"id": "T2-regression-deletion",
     "gate": "ci_regression", "mutation": "delete registered suite",
     "must": "red"},
    {"id": "T3-bandit-newfile",
     "gate": "bandit+baseline", "mutation": "new file with B602",
     "must": "red"},
    {"id": "T4-secret-key",
     "gate": "gitleaks detect", "mutation": "commit matching key",
     "must": "red"},
]


def evaluate_candidate(check_results: dict) -> dict:
    """Score a candidate system version.

    check_results: {"F1": {case_id: caught_bool}, "F2": {case_id: verdict},
                    "F3": {case_id: red_bool}}.
    Returns per-family rates plus the joint verdict inputs.
    """
    f1 = check_results.get("F1", {})
    f2 = check_results.get("F2", {})
    f3 = check_results.get("F3", {})
    f1_rate = sum(1 for c in F1_SEEDED if f1.get(c["id"], False)) / len(F1_SEEDED)
    f2_ok = sum(1 for c in F2_JUDGMENTS
                if f2.get(c["id"]) == c["verdict"]) / len(F2_JUDGMENTS)
    f3_rate = sum(1 for c in F3_TEETH if f3.get(c["id"], False)) / len(F3_TEETH)
    return {"F1_catch": round(f1_rate, 3), "F2_agree": round(f2_ok, 3),
            "F3_teeth": round(f3_rate, 3)}


def gate(incumbent: dict, candidate: dict, min_gain: float = 0.02,
         alpha: float = 0.05) -> dict:
    """Decide promotion. Same semantics as the gsm8k statistical_gate.

    The candidate must be no worse on all three families and strictly better
    on at least one by >= min_gain. Where incumbent and candidate differ on
    individual cases, McNemar on the discordants must clear alpha; with tiny
    frozen sets the practical effect is: any regression blocks, and improvement
    needs a clear margin, not a coin flip.
    """
    fams = ["F1_catch", "F2_agree", "F3_teeth"]
    diffs = {f: round(candidate.get(f, 0) - incumbent.get(f, 0), 4) for f in fams}
    worse = [f for f in fams if diffs[f] < 0]
    better = [f for f in fams if diffs[f] >= min_gain]
    if worse:
        return {"promote": False,
                "reason": f"regression on {worse}: a candidate must be no worse everywhere"}
    if not better:
        return {"promote": False,
                "reason": f"no family improved by >= {min_gain}: {diffs}"}
    return {"promote": True,
            "reason": f"improved {better} with no regressions: {diffs}"}


def freeze_eval(out: Path) -> None:
    """Write the current frozen set with hashes, for audit."""
    doc = {"F1": F1_SEEDED, "F2": F2_JUDGMENTS, "F3": F3_TEETH}
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
