"""Venue-indexed quality gates: workshop / conference-main / TMLR / SCI-journal / zone1.

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
  zone1             -- SCI Zone 1 (JCR Q1 / CAS Zone 1: top-25% journals). Everything
                       in sci-journal, PLUS the bars that separate Zone 1 from
                       Zone 2: effect sizes with practical-significance discussion
                       (not p-values alone); comprehensive baselines (every
                       relevant prior method run, not a convenience subset);
                       ablation completeness (every design choice ablated or
                       explicitly justified as unablatable); no salami slicing
                       (the contribution is a complete unit, not one experiment
                       stretched thin); data + code availability as a hard
                       requirement (not a link promise); broader-impact and
                       ethics discussion. Judgment bar 8.0: both seats must rate
                       every dimension at clear-accept or above.

Each gate has two halves. The mechanical half runs without any model and cannot
be argued with: numbers trace to evidence, CIs present, limitations section
exists, references resolve, anonymity holds where required. The judgment half
(significance, clarity, novelty, generality) goes to the two-seat review scored
against the tier's rubric. A paper passes a tier only if BOTH halves pass.
"""
from __future__ import annotations

TIERS = ("workshop", "conference-main", "tmlr", "sci-journal", "zone1")

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
        ("C7-contribution-delta", "the contribution is stated as a concrete change (output/operation/representation/assumption), not a novelty label"),
        ("C8-comparison-purpose", "every comparison states what decision it resolves, what stays fixed, and what changes"),
        ("C9-bounded-lesson", "ends with what readers can reconsider, separating observation / interpretation / proposed action, plus transfer limits"),
        ("C10-ai-disclosure", "AI use declared or explicitly denied; named systems only in camera-ready, never in blind text"),
    ],
    "tmlr": [
        ("T1-numbers-trace", "every number traces to evidence file + field"),
        ("T2-ci-present", "every quantitative claim carries a CI or an explicit why-not"),
        ("T3-limitations-present", "a Limitations section exists"),
        ("T4-double-blind", "manuscript anonymized; author info only in OpenReview metadata"),
        ("T5-references-resolve", "every citation has a resolvable target"),
        ("T6-not-survey", "not a survey paper (refused since 2026-09)"),
        ("T7-ai-disclosure", "AI use declared or explicitly denied; named systems only in camera-ready"),
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
        ("J11-ai-disclosure", "AI use declared or explicitly denied; named systems only in camera-ready"),
    ],
    "zone1": [
        ("Z1-numbers-trace", "every number traces to evidence file + field"),
        ("Z2-ci-present", "every quantitative claim carries a CI or an explicit why-not"),
        ("Z3-effect-size", "every significant result reports an effect size with a practical-significance discussion, not p-values alone"),
        ("Z4-baselines-comprehensive", "every relevant prior method is run as a baseline, not a convenience subset; exclusions named with reasons"),
        ("Z5-ablation-complete", "every design choice is ablated, or explicitly justified as unablatable with a reason"),
        ("Z6-generality-discussed", "strengths AND limitations AND generality each get explicit text"),
        ("Z7-predecessors-acknowledged", "related work names predecessors, states what differs, and cites the closest 3+ prior works"),
        ("Z8-examples-present", "at least one worked example a general ML reader can follow"),
        ("Z9-new-terms-justified", "every new term/technique states why existing ones are insufficient"),
        ("Z10-not-narrow", "the contribution is framed for a broad ML audience, not one subfield"),
        ("Z11-not-applications-only", "not an application of ML to another domain without method contribution"),
        ("Z12-not-salami", "the contribution is a complete unit: question + method + evidence + boundary, not one experiment stretched thin"),
        ("Z13-data-code-available", "data + code availability is stated with a concrete location, not a link promise"),
        ("Z14-impact-ethics", "broader-impact and ethics discussion present"),
        ("Z15-references-resolve", "every citation has a resolvable target"),
        ("Z16-revision-ready", "every recorded objection maps to a checkable change or an explicit wont-fix reason"),
        ("Z17-ai-disclosure", "AI use declared or explicitly denied; named systems only in camera-ready"),
    ],
}

# Judgment dimensions per tier, scored 1-10 by each seat (NeurIPS scale).
JUDGMENT = {
    "workshop": ["novelty-of-idea", "honesty", "clarity"],
    "conference-main": ["quality", "clarity", "significance", "originality"],
    "tmlr": ["correctness", "clarity", "scope-fit"],
    "sci-journal": ["significance", "correctness", "clarity", "generality",
                    "predecessor-acknowledgment"],
    "zone1": ["significance", "correctness", "clarity", "generality",
              "predecessor-acknowledgment", "completeness", "breadth-of-interest"],
}

# Minimum mean seat score to pass the judgment half (both seats must clear it).
BAR = {
    "workshop": 5.0,
    "conference-main": 7.0,
    "tmlr": 6.0,
    "sci-journal": 7.0,
    "zone1": 8.0,
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
            # NOTE: "inconclusive" itself is NOT hedge vocabulary -- it is the
            # status token. Counting it would make every inconclusive row
            # trivially "hedged".
            HEDGE_WORDS = ("hedge", "do not claim", "do not generalize",
                           "not claim", "uncertain", "may be", "suggest", "exploratory",
                           "preliminary", "cannot conclude", "do not conclude")
            low_text = text.lower()
            bad = []
            for r in ledger_rows:
                if r.get("status") not in ("inconclusive", "blocked"):
                    continue
                body = f"{r.get('claim','')} {r.get('how','')}".lower()
                if not any(w in body for w in HEDGE_WORDS) \
                   and not any(w in low_text for w in HEDGE_WORDS):
                    bad.append(r)
            out.append((cid, not bad,
                        "ok" if not bad else f"{len(bad)} unhedged non-verified claims"))
        elif cid.endswith("reproduce-sketch"):
            ok = any(k in text.lower() for k in ("reproduce", "seed", "command", "verify"))
            out.append((cid, ok, "ok" if ok else "no reproduce entrypoint mentioned"))
        elif cid.endswith("ci-present"):
            import re
            # Only magnitude claims need intervals: gains, accuracies, PCIs,
            # slopes, rates. Counts, ranks, seeds, indices, and config numbers
            # are exact by construction -- demanding CIs for them is noise.
            MAGNITUDE_HINT = ("gain", "acc", "pci", "slope", "excess", "rate",
                              "hit_rate", "mean", "diff")
            quants = [r for r in ledger_rows
                      if isinstance(r.get("value"), (int, float))
                      and any(h in r.get("id", "").lower() for h in MAGNITUDE_HINT)]
            n_claims = max(1, len(quants))
            # Word boundaries: bare-substring "ci" matches social/special/species.
            # Bayesian analyses report posteriors/credible intervals/Bayes factors
            # instead of frequentist CIs; those count.
            n_ci = len(re.findall(r"\bCI\b|\bCIs\b|confidence interval|"
                                  r"credible interval|posterior|Bayes factor|\bBF\b",
                                  text))
            out.append((cid, n_ci >= n_claims,
                        "ok" if n_ci >= n_claims
                        else f"only {n_ci} interval mentions for {n_claims} numeric claims"))
        elif cid.endswith("double-blind"):
            # AAAI rule: no pointers to web material in the submission at all,
            # including anonymous repositories -- supplementary goes in the ZIP.
            # So this check flags every web pointer, and data-code-available
            # accepts "see supplementary" as satisfying availability.
            low = text.lower()
            hits = [w for w in ("liuzewen", "liu zewen", "aidless", "acknowledg",
                                "github.com/", "anonymous github", "huggingface.co/",
                                "zenodo.org/", "arxiv.org/abs")
                    if w in low]
            out.append((cid, not hits,
                        "ok" if not hits else f"identity/web pointers: {hits}"))
        elif cid.endswith("references-resolve"):
            out.append((cid, True, "mechanical pass; hallucination scan is a separate gate"))
        elif cid.endswith("pages"):
            out.append((cid, True, "page count checked at submission render, not here"))
        elif cid.endswith("contribution-delta"):
            low = text.lower()
            has_change = any(k in low for k in ("compared to", "differs", "whereas",
                                                "instead of", "unlike", "whereas",
                                                "change", "difference"))
            has_label_only = ("novel" in low or "innovative" in low) and not has_change
            out.append((cid, not has_label_only,
                        "ok" if not has_label_only
                        else "novelty label without a stated concrete change"))
        elif cid.endswith("comparison-purpose"):
            low = text.lower()
            ok = ("fixed" in low or "controlled" in low or "held constant" in low
                  or "same " in low)
            out.append((cid, ok,
                        "ok" if ok else "no comparison states what stays fixed"))
        elif cid.endswith("bounded-lesson"):
            low = text.lower()
            ok = (("lesson" in low or "takeaway" in low or "reconsider" in low)
                  and ("limitation" in low or "limit" in low))
            out.append((cid, ok,
                        "ok" if ok else "no bounded lesson (takeaway + transfer limits)"))
        elif cid.endswith("ai-disclosure"):
            low = text.lower()
            declares = any(k in low for k in (
                "ai-assisted", "ai assisted", "generated with the assistance of",
                "language model", "llm-assisted", "no ai was used", "no ai use",
                "written without ai assistance", "ai use disclosure",
                "disclosure of ai"))
            names_system = any(k in low for k in (
                "ai-researcher", "ai_scientist", "ai-scientist"))
            if not declares:
                out.append((cid, False,
                            "no AI-use statement: declare assistance or explicitly "
                            "deny it (venue AI policies require one or the other)"))
            elif names_system:
                out.append((cid, False,
                            "names the AI system in review text: move system names "
                            "to camera-ready, keep blind text system-agnostic"))
            else:
                out.append((cid, True, "ok"))
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
        elif cid.endswith("effect-size"):
            low = text.lower()
            ok = (("effect size" in low or "cohen" in low or "eta" in low
                   or "practical significance" in low)
                  and "p <" in low.replace("p<", "p <"))
            out.append((cid, ok,
                        "ok" if ok
                        else "p-values without effect sizes or practical-significance discussion"))
        elif cid.endswith("baselines-comprehensive"):
            low = text.lower()
            if "baseline" not in low:
                out.append((cid, False, "no baseline comparison visible"))
            elif "exclud" in low:
                out.append((cid, True, "baselines present with explicit exclusions"))
            else:
                out.append((cid, True,
                            "baselines present; exclusions not explicitly justified "
                            "(flagged for the seats)"))
        elif cid.endswith("ablation-complete"):
            low = text.lower()
            ok = ("ablat" in low)
            out.append((cid, ok, "ok" if ok else "no ablation of design choices found"))
        elif cid.endswith("not-salami"):
            out.append((cid, True, "requires reviewer judgment; flagged for the seats"))
        elif cid.endswith("data-code-available"):
            low = text.lower()
            ok = (("code" in low and "available" in low)
                  or "github.com" in low or "zenodo" in low or "huggingface" in low
                  or "supplementary" in low)
            out.append((cid, ok,
                        "ok" if ok else "no concrete data/code availability statement"))
        elif cid.endswith("impact-ethics"):
            low = text.lower()
            ok = (("broader impact" in low or "broader-impact" in low)
                  and ("ethic" in low or "misuse" in low or "dual use" in low
                       or "dual-use" in low))
            out.append((cid, ok,
                        "ok" if ok else "missing broader-impact and/or ethics discussion"))
        else:
            out.append((cid, False,
                        f"unknown check id {cid!r}: failing closed (a typo must "
                        f"never read as a pass)"))
    return out


def gate_report(tier: str, ledger_rows: list, draft_text: str,
                seat_scores: dict, meta: dict = None) -> dict:
    """Combine both halves. seat_scores: {seat: {dim: score}}."""
    meta = meta or {}
    mech = mechanical_check(ledger_rows, draft_text, meta, tier)
    mech_ok = all(p for _, p, _ in mech)
    dims = JUDGMENT.get(tier, [])
    means = {}
    incomplete = {}
    for seat, scores in (seat_scores or {}).items():
        # Missing dimensions are INCOMPLETE, not zero: scoring an absent
        # dimension as 0 craters the mean and punishes the paper for the
        # reviewer's malformed output. A seat missing any dimension fails
        # the judgment half outright instead.
        missing = [d for d in dims if d not in (scores or {})]
        if missing:
            incomplete[seat] = missing
            continue
        try:
            vals = [float(scores[d]) for d in dims]
        except (TypeError, ValueError):
            incomplete[seat] = ["non-numeric scores"]
            continue
        means[seat] = round(sum(vals) / len(vals), 2) if vals else 0.0
    bar = BAR.get(tier, 7.0)
    judg_ok = bool(means) and not incomplete and all(v >= bar for v in means.values())
    verdict = "PASS" if (mech_ok and judg_ok) else "FAIL"
    return {"tier": tier, "verdict": verdict, "bar": bar,
            "mechanical": [{"id": c, "pass": p, "reason": r} for c, p, r in mech],
            "mechanical_ok": mech_ok,
            "judgment_means": means, "judgment_ok": judg_ok,
            "judgment_incomplete": incomplete,
            "dimensions": dims}
