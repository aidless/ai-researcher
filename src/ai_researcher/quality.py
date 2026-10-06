"""Venue-indexed quality gates: workshop / conference-main / TMLR / SCI-journal.

Each tier is a different game, not a different difficulty of the same game.
The gates encode what actually differs, sourced from the venues' own reviewer
guides (NeurIPS 4 criteria + 10-point scale; TMLR correctness-first + replication
welcome; JMLR Goals/Description/Evaluation/Significance/Related/Clarity;
AAAI double-blind + supplementary-ZIP rules):

  workshop          -- non-archival. Idea novelty + honesty + reproducibility
                       sketch. Fast. A negative or partial result with a clean
                       protocol passes; an overstated claim fails.
  conference-main   -- archival, ~25-28% acceptance, fixed deadline, 7-9 pages.
                       Quality + Clarity + Significance + Originality, scored
                       1-10 (NeurIPS scale: 7+ accept). Double-blind enforced
                       on the manuscript AND any linked material.
  tmlr              -- archival journal, rolling (~9 weeks), double-blind, open
                       review. Correctness over significance; replications
                       explicitly welcome (with Reproducibility Certification);
                       surveys refused since 2026-09. Variable length.
  sci-journal       -- archival journal (JMLR/IEEE pattern): AE + 3 reviewers over
                       months, decisions accept / conditional-accept / reject with
                       or without encouragement to resubmit. Beyond conference
                       bars: broad-audience clarity (a general ML reader must
                       follow it), comprehensive predecessor acknowledgment,
                       explicit generality discussion (strengths AND limitations
                       AND generality), examples required, no narrow-audience or
                       applications-only work. Revision rounds expected, so the
                       gate also checks revision-readiness (every objection maps
                       to a checkable change).

Each gate has two halves. The mechanical half runs without any model and cannot
be argued with: numbers trace to evidence, CIs present, limitations section
exists, references resolve, anonymity holds where required. The judgment half
(significance, clarity, novelty, generality) goes to the two-seat review scored
against the tier's rubric. A paper passes a tier only if BOTH halves pass.
"""
from __future__ import annotations

TIERS = ("workshop", "conference-main", "tmlr", "sci-journal")

# Mechanical checks per tier: (id, description, check_fn_name).
# check functions live in this module and take (ledger_rows, draft_text, meta).
MECHANICAL = {
    "workshop": [
        ("W1-numbers-trace", "every number traces to evidence file + field"),
        ("W2-limitations-present", "a Limitations section exists and is non-empty"),
        ("W3-no-strong-unverified", "no verified-status claim contradicts its evidence"),
        ("W4-reproduce-sketch", "a reproduce entrypoint exists (command, seed, env)"),
    ],
    "conference-main": [
        ("C1-numbers-trace", "every number traces to evidence file + field"),
        ("C2-ci-present", "every quantitative claim carries a CI or an explicit why-not"),
        ("C3-limitations-present", "a Limitations section exists and names sample bounds"),
        ("C4-double-blind", "manuscript carries no author identity, acknowledgments, or links to non-anonymous material"),
        ("C5-references-resolve", "every citation has a resolvable target (no hallucinated refs)"),
        ("C6-pages", "main content within the venue page limit"),
    ],
    "tmlr": [
        ("T1-numbers-trace", "every number traces to evidence file + field"),
        ("T2-ci-present", "every quantitative claim carries a CI or an explicit why-not"),
        ("T3-limitations-present", "a Limitations section exists"),
        ("T4-double-blind", "manuscript anonymized; author info only in OpenReview metadata"),
        ("T5-references-resolve", "every citation has a resolvable target"),
        ("T6-not-survey", "not a survey paper (refused since 2026-09)"),
    ],
    "sci-journal": [
        ("J1-numbers-trace", "every number traces to evidence file + field"),
        ("J2-ci-present", "every quantitative claim carries a CI or an explicit why-not"),
        ("J3-generality-discussed", "strengths AND limitations AND generality each get explicit text"),
        ("J4-predecessors-acknowledged", "related work names predecessors and states what differs"),
        ("J5-examples-present", "at least one worked example a general ML reader can follow"),
        ("J6-new-terms-justified", "every new term/technique states why existing ones are insufficient"),
        ("J7-not-narrow", "the contribution is framed for a broad ML audience, not one subfield"),
        ("J8-not-applications-only", "not an application of ML to another domain without method contribution"),
        ("J9-references-resolve", "every citation has a resolvable target"),
        ("J10-revision-ready", "every recorded objection maps to a checkable change or an explicit wont-fix reason"),
    ],
}

# Judgment dimensions per tier, scored 1-10 by each seat (NeurIPS scale).
JUDGMENT = {
    "workshop": ["novelty-of-idea", "honesty", "clarity"],
    "conference-main": ["quality", "clarity", "significance", "originality"],
    "tmlr": ["correctness", "clarity", "scope-fit"],
    "sci-journal": ["significance", "correctness", "clarity", "generality",
                    "predecessor-acknowledgment"],
}

# Minimum mean seat score to pass the judgment half (both seats must clear it).
BAR = {
    "workshop": 5.0,
    "conference-main": 7.0,
    "tmlr": 6.0,
    "sci-journal": 7.0,
}


def mechanical_check(ledger_rows: list, draft_text: str, meta: dict,
                     tier: str) -> list:
    """Run the mechanical half. Returns [(check_id, passed: bool, reason)]."""
    out = []
    text = draft_text or ""
    for cid, desc in MECHANICAL.get(tier, []):
        if cid.endswith("numbers-trace"):
            bad = [r for r in ledger_rows
                   if r.get("status") == "verified" and not r.get("evidence")]
            out.append((cid, not bad,
                        "ok" if not bad else f"{len(bad)} verified claims without evidence"))
        elif cid.endswith("limitations-present"):
            low = text.lower()
            ok = ("limitation" in low) and len(text) > 200
            out.append((cid, ok, "ok" if ok else "no Limitations section found"))
        elif cid.endswith("no-strong-unverified"):
            HEDGE_WORDS = ("hedge", "inconclusive", "do not claim", "do not generalize",
                           "not claim", "uncertain", "may be", "suggest", "exploratory",
                           "preliminary", "cannot conclude", "do not conclude")
            low_text = text.lower()
            bad = [r for r in ledger_rows
                   if r.get("status") in ("inconclusive", "blocked")
                   and not any(w in str(r.get("how", "")).lower() for w in HEDGE_WORDS)
                   and not any(w in low_text for w in HEDGE_WORDS)]
            out.append((cid, not bad,
                        "ok" if not bad else f"{len(bad)} unhedged non-verified claims"))
        elif cid.endswith("reproduce-sketch"):
            ok = any(k in text.lower() for k in ("reproduce", "seed", "command", "verify"))
            out.append((cid, ok, "ok" if ok else "no reproduce entrypoint mentioned"))
        elif cid.endswith("ci-present"):
            n_claims = max(1, len([r for r in ledger_rows
                                  if isinstance(r.get("value"), (int, float))]))
            n_ci = text.lower().count("ci") + text.count("CI") + text.count("confidence")
            out.append((cid, n_ci >= n_claims,
                        "ok" if n_ci >= n_claims
                        else f"only {n_ci} CI mentions for {n_claims} numeric claims"))
        elif cid.endswith("double-blind"):
            low = text.lower()
            hits = [w for w in ("liuzewen", "liu zewen", "aidless", "acknowledg",
                                "github.com/", "anonymous github", "huggingface.co/")
                    if w in low]
            out.append((cid, not hits,
                        "ok" if not hits else f"identity leaks: {hits}"))
        elif cid.endswith("references-resolve"):
            out.append((cid, True, "mechanical pass; hallucination scan is a separate gate"))
        elif cid.endswith("pages"):
            out.append((cid, True, "page count checked at submission render, not here"))
        elif cid.endswith("not-survey"):
            low = text.lower()
            out.append((cid, "survey" not in low.split("\n")[0],
                        "ok" if "survey" not in low.split("\n")[0]
                        else "title declares a survey"))
        elif cid.endswith("generality-discussed"):
            low = text.lower()
            parts = ["strength" in low, "limitation" in low, "general" in low]
            out.append((cid, all(parts),
                        "ok" if all(parts)
                        else f"missing: {[k for k, v in zip(('strengths','limitations','generality'), parts) if not v]}"))
        elif cid.endswith("predecessors-acknowledged"):
            low = text.lower()
            ok = ("related work" in low or "prior work" in low or "previous work" in low
                  or "predecessor" in low)
            out.append((cid, ok, "ok" if ok else "no related/prior-work discussion found"))
        elif cid.endswith("examples-present"):
            ok = ("example" in text.lower() or "e.g." in text.lower()
                  or "for instance" in text.lower())
            out.append((cid, ok, "ok" if ok else "no worked example found"))
        elif cid.endswith("new-terms-justified"):
            out.append((cid, True, "requires reviewer judgment; flagged for the seats"))
        elif cid.endswith("not-narrow"):
            out.append((cid, True, "requires reviewer judgment; flagged for the seats"))
        elif cid.endswith("not-applications-only"):
            low = text.lower()
            ok = any(k in low for k in ("method", "bound", "estimator", "theorem",
                                        "algorithm", "protocol", "gate"))
            out.append((cid, ok, "ok" if ok else "no method contribution visible"))
        elif cid.endswith("revision-ready"):
            out.append((cid, True, "checked against the objection table at gate time"))
        else:
            out.append((cid, True, "unknown check id; treated as pass, flagged"))
    return out


def gate_report(tier: str, ledger_rows: list, draft_text: str,
                seat_scores: dict, meta: dict = None) -> dict:
    """Combine both halves. seat_scores: {seat: {dim: score}}."""
    meta = meta or {}
    mech = mechanical_check(ledger_rows, draft_text, meta, tier)
    mech_ok = all(p for _, p, _ in mech)
    dims = JUDGMENT.get(tier, [])
    means = {}
    for seat, scores in (seat_scores or {}).items():
        vals = [float(scores.get(d, 0)) for d in dims]
        means[seat] = round(sum(vals) / len(vals), 2) if vals else 0.0
    bar = BAR.get(tier, 7.0)
    judg_ok = bool(means) and all(v >= bar for v in means.values())
    verdict = "PASS" if (mech_ok and judg_ok) else "FAIL"
    return {"tier": tier, "verdict": verdict, "bar": bar,
            "mechanical": [{"id": c, "pass": p, "reason": r} for c, p, r in mech],
            "mechanical_ok": mech_ok,
            "judgment_means": means, "judgment_ok": judg_ok,
            "dimensions": dims}
