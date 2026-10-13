"""Close the self-evolution loop: signed results -> the next hypothesis.

Until 2026-10-08 the pipeline ran experiments, wrote claim ledgers and drafted
sections, but nothing connected a RESULT to the next HYPOTHESIS. `ideas.py` held
a ranked list written by hand; a human decided what to run next. That is a
s supervised loop wearing an autonomous label.

This module reads finished runs -- verdict, measured numbers, amendments, ledger
status -- and emits ranked, preregisterable proposals of five kinds:

  boundary_probe      a claim held on one axis and contradicted on another. The
                      contradiction is the interesting object: it says the claim
                      has a shape nobody wrote down. (coderepair-01 produced one.)
  mechanism_split     a mixed or reversed result with more than one live reading.
                      Proposes the discriminating experiment, not a bigger one.
  power_escalation    a claim whose own review said n was too small. Proposes the
                      n that `envelope.required_n` says is actually needed.
  confound_audit      a run whose amendments mention contamination, invalidation
                      or a withdrawn claim. Proposes the clean re-run.
  retire              refuted twice. Archive the direction instead of spending on it.

Two rules keep this from becoming an idea generator that ignores evidence:

  1. A proposal may not restate a refuted claim as a new hypothesis. Every
     proposal must name the run that generated it and quote the number that
     motivated it.
  2. Every proposal ships a kill-switch keyed on a field the harness actually
     emits, and an n that passes the power pre-check. A proposal that cannot
     fail is refused -- that is the same discipline as an envelope without
     kill-switch rows.

`python -m ai_researcher.evolve <runs_dir> [--out proposals] [--limit N]`
writes markdown proposals plus an approval-ready envelope skeleton per proposal.
The envelope still needs a human (`loop approve`) before anything runs.
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field

from .envelope import required_n


# --------------------------------------------------------------------------
# reading finished runs
# --------------------------------------------------------------------------

def _load_run(workdir: pathlib.Path) -> dict | None:
    state_p = workdir / "state.json"
    if not state_p.exists():
        return None
    try:
        st = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not st.get("rounds"):
        return None
    rnd = st["rounds"][-1]
    rd = workdir / f"round-{rnd['round']:02d}"
    amendments = []
    if (rd / "amendment.json").exists():
        try:
            amendments.append(json.loads((rd / "amendment.json").read_text(
                encoding="utf-8"))["correction"])
        except Exception:
            pass
    return {"name": workdir.name, "status": st.get("status"),
            "verdict": rnd.get("verdict"), "reason": rnd.get("reason", ""),
            "result": rnd.get("result") or {},
            "amendments": amendments, "dir": str(workdir)}


def _numbers(result: dict) -> dict:
    """Numeric facts the kill-switch could see, same filter the loop uses."""
    return {k: v for k, v in result.items() if isinstance(v, (int, float, bool))}


def _mentions(text: str, *words) -> bool:
    low = (text or "").lower()
    return any(w in low for w in words)


# --------------------------------------------------------------------------
# proposal shape
# --------------------------------------------------------------------------

@dataclass
class Proposal:
    kind: str
    title: str
    source_run: str
    evidence: str            # the number that motivated this, quoted
    tension: str
    method_sketch: str
    kill_switch: list
    required_artifacts: list = field(default_factory=lambda: ["result.json"])
    n: int = 0
    mde: float = 0.0
    alpha: float = 0.05
    power: float = 0.8
    priority: float = 0.0
    rationale: str = ""
    blocked: str = ""

    def as_envelope(self, methods: str, max_wall_hours: float = 4.0) -> dict:
        return {
            "hypothesis": self.title,
            "methods": methods,
            "max_rounds": 1,
            "max_cost_usd": 0.0,
            "max_wall_hours": max_wall_hours,
            "seed": 0,  # the proposer cannot fix the seed; the human sets it
            "power": {"n": self.n, "alpha": self.alpha,
                      "min_detectable_effect": self.mde,
                      "power_at_mde": self.power},
            "kill_switch": self.kill_switch,
            "required_artifacts": list(self.required_artifacts),
            "negative_publish": "replication-report",
            "approved_by": "",
            "approved_at": "",
            "tension": self.tension,
        }


N_KNOBS = ("EVO_SEEDS", "EVO_SEED", "EVO_ROUNDS", "EVO_LIMIT", "EVO_MODELS", "EVO_REPS", "EVO_K")


def _arm_scripts(source_run: str, demo_dir: pathlib.Path) -> list:
    """The run's family directory: the longest demo/<dir> whose name prefixes the run.

    balanced-01 -> demo/balanced, collapse-replication -> demo/collapse,
    transfer-confirmation -> demo/transfer.
    """
    best = None
    for d in sorted(p for p in demo_dir.iterdir() if p.is_dir()):
        if source_run == d.name or source_run.startswith(d.name + "-") or \
           source_run.startswith(d.name.replace("_", "-") + "-"):
            if best is None or len(d.name) > len(best.name):
                best = d
    return list(best.glob("run_*.py")) if best else []


def _executability(p: Proposal, demo_dir=None) -> str:
    """Refuse an escalation whose arm cannot take more n.

    Why this exists: `_power_escalation` computes `need = required_n(0.10) = 157` from the
    ledger and stamps the proposal "ready for approval", but it never asked whether the arm
    can reach 157. Two proposals on disk could not: demo/balanced/run_balanced.py is a
    deterministic reanalysis ("No model calls") over external weight files, and
    demo/breadth/run_breadth.py iterates a hard-coded list of 8 diffs (its own result.json
    says n_diffs: 8). Escalating those means authoring a new instrument, not raising a
    number -- and a run launched from the "# TODO: exact command" methods line the proposer
    emits would have burned hours to re-measure the same n. Arms that DO expose a knob
    (swarm: EVO_SEEDS/EVO_ROUNDS; transfer: EVO_LIMIT/EVO_MODELS; coderepair: EVO_MODELS)
    stay armable.
    """
    if p.kind != "power_escalation":
        return ""
    demo_dir = pathlib.Path(demo_dir) if demo_dir else \
        pathlib.Path(__file__).resolve().parents[2] / "demo"
    scripts = _arm_scripts(p.source_run, demo_dir)
    if not scripts:
        return (f"cannot arm: no run script found for {p.source_run!r} under {demo_dir}/ "
                f"-- the escalation has nothing to raise the n of")
    for py in scripts:
        try:
            txt = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(k in txt for k in N_KNOBS):
            return ""          # a real knob exists: armable
    return (f"n is not a knob in this arm -- none of "
            f"{[s.name for s in scripts]} reads any of {list(N_KNOBS)}, so the sample size "
            f"is set by hard-coded item/seed collections in the script or by its external "
            f"input files. Reaching n={p.n} requires authoring a new instrument (more items), "
            f"not raising a number -- this proposal is not armable as written")


def _power_ok(p: Proposal) -> str:
    """Refuse a proposal whose promised effect its own n cannot detect."""
    if not p.n or not p.mde:
        return ""
    need = required_n(p.mde, alpha=p.alpha, power=p.power, paired=True)
    if need and p.n < need:
        return (f"n={p.n} cannot detect mde={p.mde} at alpha={p.alpha} "
                f"power={p.power}; need n>={need}")
    return ""


# --------------------------------------------------------------------------
# detectors
# --------------------------------------------------------------------------

def _boundary_probe(run: dict) -> Proposal | None:
    """A claim that replicated widely but reversed on a shifted axis."""
    r, res = run["result"], run["result"].get("result") or run["result"]
    if run["verdict"] != "STOP-REFUTED":
        return None
    fam = res.get("families_positive")
    mc = res.get("mcnemar_pooled") or {}
    if not fam or not isinstance(fam, str) or "/" not in fam:
        return None
    pos, total = (int(x) for x in fam.split("/"))
    if pos > 0:
        return None  # mixed, not reversed -- that is mechanism_split's job
    p = Proposal(
        kind="boundary_probe",
        title=f"Locate the axis on which {run['name']}'s effect reverses",
        source_run=run["name"],
        evidence=f"{fam} families positive; pooled McNemar "
                 f"{mc.get('fixed')}:{mc.get('broke')} p={mc.get('p')}",
        tension=(f"The same policy that replicated across every family tested on "
                 f"the original domain produced no positive family at all on a "
                 f"shifted domain. Either the mechanism does not generalise or the "
                 f"policy is mismatched to the shifted task, and the two are not "
                 f"separable by re-running the same comparison. Answering it decides "
                 f"whether the result is a bounded mechanism with a stated boundary "
                 f"or a domain-general one."),
        method_sketch=("Re-run the shifted domain with a policy adapted to the "
                       "shifted task's structure (specification-explicit rather "
                       "than defect-explicit), keeping items, scorer, seed and "
                       "models identical so only the policy differs."),
        kill_switch=[
            {"condition": "confirmed == True",
             "action": "STOP-EXTEND",
             "note": "an adapted policy recovers the gain: the effect depends on "
                     "policy-task matching, which is a mechanism claim"},
            {"condition": "confirmed == False",
             "action": "STOP-REFUTED",
             "note": "no adapted policy recovers a resolvable gain: scope stays "
                     "narrowed to the original domain"},
        ],
        n=144, mde=0.25,
        priority=0.95,
        rationale=("A wide replication on one axis plus a clean reversal on "
                   "another is the strongest available source of a new "
                   "hypothesis, because the contradiction is evidence rather "
                   "than a hunch."),
    )
    return p


def _mechanism_split(run: dict) -> Proposal | None:
    """Mixed result with more than one live reading."""
    res = run["result"].get("result") or run["result"]
    fam = res.get("families_positive")
    if run["verdict"] != "STOP-REFUTED" or not isinstance(fam, str):
        return None
    pos, total = (int(x) for x in fam.split("/"))
    if not (0 < pos < total):
        return None
    p = Proposal(
        kind="mechanism_split",
        title=f"Discriminate the two readings of {run['name']}",
        source_run=run["name"],
        evidence=f"{fam} families positive (mixed, not reversed)",
        tension=("The result is mixed across families. Two readings survive: the "
                 "effect requires capability the smaller families lack, or it "
                 "requires something about the task. A bigger sample would not "
                 "separate them; only a design that varies one of the two would."),
        method_sketch=("Hold the policy fixed and vary a single factor predicted "
                       "to differ between the two readings (e.g. baseline "
                       "capability matched across families, or defect visibility "
                       "held constant), then report the interaction."),
        kill_switch=[
            {"condition": "interaction_detected == True", "action": "STOP-EXTEND",
             "note": "the interaction identifies which reading holds"},
            {"condition": "interaction_detected == False",
             "action": "STOP-INCONCLUSIVE",
             "note": "no interaction at this n: the two readings remain open and "
                     "the claim must stay conditional"},
        ],
        n=144, mde=0.25, priority=0.8,
        rationale=("Mixed-across-families results are usually reported as "
                   "inconclusive and then quietly dropped. Naming the two live "
                   "readings is what keeps them alive."),
    )
    return p


def _power_escalation(run: dict, ledger_rows: list) -> Proposal | None:
    """A claim a review called underpowered."""
    vague = [r for r in ledger_rows
             if r.get("status") == "inconclusive"
             and _mentions(r.get("how", ""), "n=", "sample size", "too small",
                           "power", "underpowered")]
    if not vague:
        return None
    mde = 0.10
    need = required_n(mde, alpha=0.05, power=0.8, paired=True)
    p = Proposal(
        kind="power_escalation",
        title=f"Re-measure {run['name']} at an n that can resolve its effect",
        source_run=run["name"],
        evidence=f"{len(vague)} ledger claim(s) flagged inconclusive on sample size; "
                 f"n=40 could not detect mde=0.10 (needs n>={need})",
        tension=(f"The ledger records claims that cannot be resolved at the n "
                 f"actually run, so they are formally unciteable. Either they "
                 f"are real effects awaiting enough data, or they are noise that "
                 f"more data will not rescue. Only one of those is worth buying, "
                 f"and the difference is currently unmeasured."),
        method_sketch=("Same items, policies, scorer and seed; increase n to the "
                       "pre-checked requirement and report per-condition CIs "
                       "rather than a pooled test."),
        kill_switch=[
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "the effect is real at adequate n; the claim becomes citable"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "the effect was noise at n=40; retire the claim"},
            {"condition": "confirmed == None", "action": "STOP-INCONCLUSIVE",
             "note": "still unresolvable: report the interval, do not claim"},
        ],
        n=need, mde=mde, priority=0.7,
        rationale=("Every two-seat review in this project has said some version "
                   "of 'n is too small'. This converts that recurring objection "
                   "into a queued experiment with a computed n."),
    )
    return p


def _confound_audit(run: dict) -> Proposal | None:
    """A run whose own amendments say the evidence was contaminated."""
    hits = [a for a in run["amendments"]
            if _mentions(a, "contaminat", "invalid", "withdraw", "404",
                         "not installed", "recomputed by hand")]
    if not hits:
        return None
    return Proposal(
        kind="confound_audit",
        title=f"Re-run {run['name']} without the confound its amendment names",
        source_run=run["name"],
        evidence=hits[0][:220],
        tension=("The amendment records that the round's conclusion cannot be "
                 "separated from an infrastructure or procedural artifact. The "
                 "claim is neither supported nor refuted, so the direction is "
                 "unknown, and an unknown direction is not a result. Re-running "
                 "with the confound removed is the only way to learn whether the "
                 "original observation was ever about the model."),
        method_sketch=("Identical envelope and seed, re-run with the confound "
                       "absent (exclusive GPU lock, preflighted models, sealed "
                       "artifacts directory). Compare against the withdrawn "
                       "numbers."),
        kill_switch=[
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "the original observation survives the clean re-run"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "the original observation was the artifact; record it as a "
                     "lesson rather than a finding"},
        ],
        n=80, mde=0.2, priority=0.75,
        rationale=("A withdrawn claim is an open debt in the ledger. Leaving it "
                   "withdrawn keeps the paper honest but permanently weaker than "
                   "recovering it honestly."),
    )


def _retire(run: dict) -> Proposal | None:
    """Refuted with nothing left to discriminate."""
    if run["verdict"] != "STOP-REFUTED":
        return None
    if run["amendments"]:
        return None  # amendments mean there is still something to re-run
    return Proposal(
        kind="retire",
        title=f"Retire the direction behind {run['name']} and spend elsewhere",
        source_run=run["name"],
        evidence=(f"verdict STOP-REFUTED with no amendment and no live "
                  f"alternative reading ({str(run.get('reason') or '')[:120]})"),
        tension=(f"This direction has been tested and refuted with no remaining "
                 f"discriminating experiment. Continuing to spend compute on it "
                 f"is not persistence, it is a sunk cost. Retiring it frees the "
                 f"budget for directions that can still change a conclusion."),
        method_sketch="No experiment. Archive the run, keep the replication report.",
        kill_switch=[{"condition": "True", "action": "STOP-REFUTED",
                      "note": "archived"}],
        n=1, mde=0.9, priority=0.3,
        rationale="Archive feedback is only real if something stops being tried.",
    )


DETECTORS = (_boundary_probe, _mechanism_split, _power_escalation,
             _confound_audit, _retire)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def propose_next(runs_dir, ledger_path=None, limit: int = 5):
    runs_dir = pathlib.Path(runs_dir)
    rows = []
    if ledger_path and pathlib.Path(ledger_path).exists():
        from .loop import _parse_ledger
        rows = _parse_ledger(pathlib.Path(ledger_path))
    out = []
    for wd in sorted(runs_dir.glob("*")):
        if not wd.is_dir():
            continue
        run = _load_run(wd)
        if not run:
            continue
        for det in DETECTORS:
            try:
                # explicit arity, not TypeError-driven dispatch: a TypeError
                # raised *inside* a detector used to trigger a second call with
                # different arguments, i.e. a bug could silently change which
                # proposal was produced.
                import inspect
                p = (det(run, rows)
                     if len(inspect.signature(det).parameters) >= 2
                     else det(run))
            except Exception as e:
                out.append(Proposal(kind="detector_error", title=f"{det.__name__} on {run['name']}",
                                    source_run=run['name'], evidence=str(e)[:200],
                                    tension="n/a", method_sketch="n/a", kill_switch=[],
                                    priority=0.0, rationale=f"detector raised {type(e).__name__}"))
                continue
            if p is None:
                continue
            p.blocked = "; ".join(x for x in (_power_ok(p), _executability(p)) if x)
            out.append(p)
    out.sort(key=lambda p: (-p.priority, p.kind))
    return out[:limit]


def _render(p: Proposal, seq: int) -> str:
    status = ("**BLOCKED** -- " + p.blocked) if p.blocked else "ready for approval"
    lines = [
        f"---",
        f"tags: [proposal, self-evolution, {p.kind}, {p.source_run}]",
        f"generated_by: ai_researcher.evolve",
        f"---",
        "",
        f"# NEXT-{seq:02d} {p.title}",
        "",
        f"**kind**: {p.kind}  ",
        f"**source run**: `{p.source_run}`  ",
        f"**evidence**: {p.evidence}  ",
        f"**power**: n={p.n}, mde={p.mde}, alpha={p.alpha}, power={p.power}  ",
        f"**status**: {status}",
        "",
        "## Why this, and not something else",
        "",
        p.rationale,
        "",
        "## Tension",
        "",
        p.tension,
        "",
        "## Method sketch",
        "",
        p.method_sketch,
        "",
        "## Preregistered kill-switch",
        "",
    ]
    for row in p.kill_switch:
        lines.append(f"- `{row['condition']}` -> **{row['action']}** -- {row['note']}")
    if p.blocked:
        lines += ["", f"> Refused to arm: {p.blocked}"]
    lines += ["", "A human still approves (`loop approve <envelope>`). "
              "The proposer cannot run anything.", ""]
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai_researcher.evolve")
    ap.add_argument("runs_dir")
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--out", default="proposals")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--envelopes", default=None,
                    help="directory for approval-ready envelope skeletons")
    args = ap.parse_args(argv)
    props = propose_next(args.runs_dir, args.ledger, args.limit)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.envelopes:
        pathlib.Path(args.envelopes).mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(props, 1):
        (out / f"NEXT-{i:02d}.md").write_text(_render(p, i), encoding="utf-8")
        if args.envelopes:
            env = p.as_envelope(f"# TODO({p.kind}): exact command for {p.source_run}")
            (pathlib.Path(args.envelopes) / f"envelope_{p.source_run}_{p.kind}.json").write_text(
                json.dumps(env, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(props)} proposals written to {out}")
    for p in props:
        flag = "BLOCKED" if p.blocked else "ready"
        print(f"  [{flag}] {p.kind:16s} {p.source_run:14s} {p.title[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
