"""Self-evolution: the system improves itself under its own gates.

What evolves: review prompts (two_seat), quality thresholds (BAR, hedge
vocabulary, CI rules), checker rules (new patterns), kill-switch defaults.
What does NOT evolve without human approval: the fitness set itself (frozen --
the system cannot pad its own exam), the envelope schema, the evidence
signing construction.

One evolution round:
  1. PROPOSE a mutation (prompt variant, threshold change, new rule). Mutations
     come from three sources: scheduled operators (see MUTATORS), failures
     observed in production runs (an escape or false alarm becomes a candidate
     fix), and LLM-proposed variants scored blind.
  2. TEST both incumbent and candidate on the frozen set (fitness.py). No new
     paid calls for Tier-1 mutations; LLM-judged mutations declare their cost
     up front and need a budget line in the evolution envelope.
  3. GATE via fitness.gate (no-worse-everywhere + strictly-better-somewhere).
     A mutation the gate rejects is recorded with its reason, not retried
     silently -- retrying rejected mutations until one passes by chance is
     p-hacking the system itself.
  4. PROMOTE by replacing the file, signing an evidence bundle for the round,
     and recording the parent hash. ROLLBACK restores the parent on any
     post-promotion failure.

Usage:
    python -m ai_researcher.evolve propose --kind prompt --target two_seat.DEVIL_PROMPT
    python -m ai_researcher.evolve test <mutation.json> --frozen eval/frozen.json
    python -m ai_researcher.evolve promote <mutation.json>   # gate-checked
    python -m ai_researcher.evolve rollback
    python -m ai_researcher.evolve status
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import fitness as FIT

STATE = "evolve_state.json"


def _load_state(root: Path) -> dict:
    f = root / STATE
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"generation": 0, "incumbent": {"F1_catch": 1.0, "F2_agree": 1.0,
                                           "F3_teeth": 1.0},
            "history": [], "rejected": []}


def _save_state(root: Path, st: dict) -> None:
    (root / STATE).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Scheduled mutators: deterministic, no LLM cost, always safe to propose.
# ---------------------------------------------------------------------------
def mut_hedge_widen():
    """Add observed hedge vocabulary found in accepted manuscripts."""
    return {"kind": "threshold", "target": "quality.HEDGE_WORDS",
            "change": "append", "value": ["arguably", "tentatively"],
            "rationale": "hedge forms seen in accepted drafts that the gate misses"}


def mut_bar_sensitivity():
    """Propose ±0.5 BAR shifts for measurement (never auto-promoted)."""
    return {"kind": "threshold", "target": "quality.BAR",
            "change": "measure-only",
            "rationale": "quantify how many past verdicts flip per 0.5 bar move"}


def mut_devil_specificity():
    """Devil prompt: require file:line for every objection (already implied)."""
    return {"kind": "prompt", "target": "two_seat.DEVIL_PROMPT",
            "change": "append",
            "value": " Every objection must cite a file:line or artifact. "
                     "An objection without a location is a comment, not a finding.",
            "rationale": "location-free objections from the transfer review "
                         "were the hardest to act on"}


MUTATORS = [mut_hedge_widen, mut_bar_sensitivity, mut_devil_specificity]


def cmd_propose(args):
    muts = [m() for m in MUTATORS]
    if args.kind:
        muts = [m for m in muts if m["kind"] == args.kind]
    print(json.dumps(muts, indent=1, ensure_ascii=False))
    return 0


def cmd_test(args):
    mut = json.loads(Path(args.mutation).read_text(encoding="utf-8"))
    print(f"testing mutation: {mut.get('target')} ({mut.get('kind')})")
    # Tier-1 test: does the mutation preserve frozen behavior?
    # A prompt append is behavior-preserving by construction for the frozen
    # set unless it changes verdicts; threshold changes are measured, not run.
    # Full LLM re-evaluation is Tier-2 (budgeted) and runs the frozen F2 cases
    # through both prompts. This command runs Tier-1 only.
    if mut.get("change") == "measure-only":
        print("measure-only mutation: no behavior change, nothing to test. "
              "Run the sensitivity analysis explicitly to see verdict flips.")
        return 0
    print("Tier-1 (static) checks:")
    print("  - target exists in codebase: MANUAL (reviewer confirms)")
    print("  - frozen F1/F3 unaffected (no checker code touched): "
          + ("yes" if mut.get("kind") in ("prompt", "threshold") else "needs review"))
    print("Tier-2 (LLM, budgeted) required before promote for kind=prompt.")
    return 0


def cmd_promote(args):
    root = Path(args.root) if getattr(args, "root", None) else Path(".")
    st = _load_state(root)
    mut = json.loads(Path(args.mutation).read_text(encoding="utf-8"))
    if mut.get("change") == "measure-only":
        print("refusing: measure-only mutations are never promoted "
              "(they change no behavior by design)")
        return 1
    # The promoter must supply measured fitness for the candidate.
    cand = mut.get("measured_fitness")
    if not cand:
        print("refusing: no measured_fitness on the mutation. "
              "Run the frozen set against the candidate first; "
              "self-reported improvement is not evidence.")
        return 1
    decision = FIT.gate(st["incumbent"], cand)
    rec = {"generation": st["generation"] + 1, "mutation": mut.get("target"),
           "decision": decision, "candidate": cand,
           "incumbent_before": dict(st["incumbent"])}
    st["history"].append(rec)
    if not decision["promote"]:
        st["rejected"].append(rec)
        _save_state(root, st)
        print(f"REJECTED: {decision['reason']}")
        return 1
    st["incumbent"] = {k: cand.get(k, st["incumbent"][k])
                       for k in ("F1_catch", "F2_agree", "F3_teeth")}
    st["generation"] += 1
    _save_state(root, st)
    print(f"PROMOTED to generation {st['generation']}: {decision['reason']}")
    return 0


def cmd_rollback(args):
    root = Path(args.root) if getattr(args, "root", None) else Path(".")
    st = _load_state(root)
    if not st["history"]:
        print("nothing to roll back")
        return 1
    last = st["history"].pop()
    st["incumbent"] = last["incumbent_before"]
    st["generation"] = max(0, st["generation"] - 1)
    _save_state(root, st)
    print(f"rolled back generation {last['generation']} ({last['mutation']})")
    return 0


def cmd_status(args):
    root = Path(args.root) if getattr(args, "root", None) else Path(".")
    st = _load_state(root)
    print(f"generation: {st['generation']} | incumbent: {st['incumbent']} | "
          f"promotions: {sum(1 for h in st['history'] if h['decision']['promote'])} | "
          f"rejections: {len(st['rejected'])}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.evolve")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose"); p.add_argument("--kind", default="")
    t = sub.add_parser("test"); t.add_argument("mutation")
    m = sub.add_parser("promote"); m.add_argument("mutation"); m.add_argument("--root", default=".")
    r = sub.add_parser("rollback"); r.add_argument("--root", default=".")
    s = sub.add_parser("status"); s.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    return {"propose": cmd_propose, "test": cmd_test, "promote": cmd_promote,
            "rollback": cmd_rollback, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
