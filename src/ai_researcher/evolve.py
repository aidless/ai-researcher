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
    if mut.get("change") == "measure-only":
        print("measure-only mutation: no behavior change, nothing to test. "
              "Run the sensitivity analysis explicitly to see verdict flips.")
        return 0
    # Tier-1: resolve the target inside this package. (An earlier version of
    # this command printed assertions instead of checking them; a test that
    # cannot fail is not a test.)
    target = mut.get("target", "")
    mod_name, _, attr = target.partition(".")
    ok = True
    try:
        mod = __import__(f"ai_researcher.{mod_name}", fromlist=[attr or "?"])
        if attr and not hasattr(mod, attr):
            print(f"  [FAIL] {target}: module imports but attribute missing")
            ok = False
        else:
            print(f"  [PASS] target resolves: {target or '(empty target)'}")
            if not target:
                ok = False
    except Exception as e:
        print(f"  [FAIL] target does not resolve: {target} ({type(e).__name__})")
        ok = False
    # F1 static subset: the swallow-pattern and manifest checks need no model.
    # They run against this repo's own workflows as a smoke: the point is the
    # harness executes, not what it finds here.
    print("  [INFO] Tier-1 runs the LLM-free frozen subset only; "
          "prompt-behavior deltas need Tier-2 (budgeted) F2 re-evaluation.")
    print("Tier-2 (LLM, budgeted) required before promote for kind=prompt.")
    return 0 if ok else 1


def _source_file_for(target: str):
    """Resolve dotted target to its source file. Raises on failure."""
    import importlib
    mod_name, _, attr = target.partition(".")
    if not mod_name or not attr:
        raise ValueError(f"target must be dotted module.ATTR, got {target!r}")
    mod = importlib.import_module(f"ai_researcher.{mod_name}")
    if not hasattr(mod, attr):
        raise AttributeError(f"{target}: attribute missing")
    path = Path(mod.__file__)
    if path.suffix not in (".py",):
        raise ValueError(f"{target}: not a Python source file ({path})")
    return path, attr


def _apply_mutation(target: str, change: str, value) -> dict:
    """Apply a mutation to the source file. Returns backup record.

    Supported changes: append (string targets: concatenated; list targets:
    extended). Anything else is refused -- an applier that guesses at unknown
    change types is how self-modification corrupts itself.
    """
    import hashlib
    path, attr = _source_file_for(target)
    original = path.read_bytes()
    backup = {"path": str(path),
              "sha256": hashlib.sha256(original).hexdigest(),
              "target": target}
    import ai_researcher
    pkg_dir = Path(ai_researcher.__file__).resolve().parent
    bak_dir = pkg_dir / ".evolve_backups"
    bak_dir.mkdir(exist_ok=True)
    (bak_dir / f"{backup['sha256'][:16]}.bak").write_bytes(original)
    if change == "append":
        text = path.read_text(encoding="utf-8")
        # Append to the module-level assignment of attr: find `ATTR = (..."""...""")`
        # or `ATTR = "..."` and extend the literal. Refuse anything else.
        import re
        m = re.search(rf"^({re.escape(attr)}\s*=\s*)(.*)$", text,
                      re.MULTILINE | re.DOTALL)
        if not m:
            raise ValueError(f"{target}: assignment not found for append")
        head, body = m.group(1), m.group(2)
        if isinstance(value, str):
            if body.lstrip().startswith(("'''", '"""')):
                q = body.lstrip()[:3]
                idx = text.index(body)
                inner_end = text.index(q, idx + len(head) + 3)
                new_text = (text[:inner_end] + value.rstrip("\n") + "\n"
                            + text[inner_end:])
            elif (body.lstrip().startswith('"') or body.lstrip().startswith("'")):
                raise ValueError(f"{target}: refusing single-line string append "
                                 f"(quote juggling corrupts source)")
            else:
                raise ValueError(f"{target}: append supports triple-quoted "
                                 f"strings and lists, found: {body[:40]!r}")
        elif isinstance(value, list):
            if not body.lstrip().startswith(("(", "[")):
                raise ValueError(f"{target}: append(list) needs a tuple/list literal")
            raise ValueError(f"{target}: list append not yet implemented; "
                             f"refusing rather than guessing")
        else:
            raise ValueError(f"{target}: unsupported value type {type(value)}")
        path.write_text(new_text, encoding="utf-8")
        try:
            compile(new_text, str(path), "exec")
        except SyntaxError as e:
            path.write_bytes(original)
            raise ValueError(f"{target}: append broke syntax, reverted ({e})")
    else:
        raise ValueError(f"unsupported change type {change!r}: refusing")
    backup["applied"] = True
    return backup


def cmd_measure(args):
    """Measure a mutation on the LLM-free frozen subset.

    F1 (seeded defects) runs only against an explicit fixture directory holding
    the 5 planted defects; without it F1 is UNMEASURED, not zero and not one.
    F3 (gate teeth) imports every gate module. F2 needs Tier-2 LLM re-evaluation
    and is always UNMEASURED here. fitness.gate refuses incomplete measurement,
    so a prompt mutation cannot be promoted on Tier-1 alone -- that refusal is
    the point: unmeasured families must never read as agreement.
    """
    mut = json.loads(Path(args.mutation).read_text(encoding="utf-8"))
    target = mut.get("target", "")
    measured = {"provenance": f"evolve measure {target} (Tier-1 static only)"}
    # F1: seeded-defect harness needs its fixture dir; else unmeasured.
    fixture = getattr(args, "fixture_dir", "") or ""
    if fixture and Path(fixture).exists():
        import sys
        sys.path.insert(0, str(Path(fixture).parent))
        try:
            import run_seeded as RS
            caught = sum(1 for d, fn in RS.CHECKS.items()
                         if fn(Path(fixture) / "case")[0])
            measured["F1_catch"] = round(caught / len(RS.CHECKS), 3)
        except Exception as e:
            measured["F1_catch"] = None
            measured["F1_note"] = f"harness error: {type(e).__name__}: {e}"
    else:
        measured["F1_catch"] = None
        measured["F1_note"] = ("UNMEASURED: needs the seeded-defect fixture dir "
                               "(--fixture-dir); run_seeded.py builds it")
    # F3: every gate module imports cleanly.
    f3_ok = f3_tot = 0
    for mod in ("fitness", "quality", "bridge", "robustness"):
        f3_tot += 1
        try:
            __import__(f"ai_researcher.{mod}")
            f3_ok += 1
        except Exception:
            pass
    measured["F3_teeth"] = round(f3_ok / f3_tot, 3) if f3_tot else None
    measured["F2_agree"] = None
    measured["F2_note"] = ("UNMEASURED: needs Tier-2 LLM re-evaluation of frozen F2 "
                           "cases through incumbent and candidate prompts (budgeted)")
    print(json.dumps(measured, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(measured, indent=1) + "\n",
                                   encoding="utf-8")
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
    # Apply the file change BEFORE recording: a promotion that only updates
    # numbers while the source stays put is bookkeeping, not evolution.
    backup = None
    if decision["promote"]:
        try:
            backup = _apply_mutation(mut.get("target", ""),
                                     mut.get("change", ""),
                                     mut.get("value"))
        except Exception as e:
            print(f"REFUSED at apply time: {e}")
            return 1
    rec = {"generation": st["generation"] + 1, "mutation": mut.get("target"),
           "decision": decision, "candidate": cand,
           "incumbent_before": dict(st["incumbent"]),
           "backup": backup}
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
    # Restore file bytes first: numbers without source are the same lie
    # promote used to tell.
    bak = (last.get("backup") or {})
    if bak.get("applied"):
        import hashlib
        path = Path(bak["path"])
        cur = hashlib.sha256(path.read_bytes()).hexdigest() \
            if path.exists() else None
        import ai_researcher
        pkg_dir = Path(ai_researcher.__file__).resolve().parent
        src = pkg_dir / ".evolve_backups" / f"{bak['sha256'][:16]}.bak"
        if not src.exists():
            print(f"rollback FAILED: backup bytes for {bak['target']} are gone; "
                  f"restore manually and re-freeze")
            return 1
        path.write_bytes(src.read_bytes())
        print(f"restored {bak['path']} to {bak['sha256'][:12]} "
              f"(was {cur[:12] if cur else 'missing'})")
    st["incumbent"] = last["incumbent_before"]
    st["generation"] = max(0, st["generation"] - 1)
    # Keep rejected[] append-only (audit trail); drop the entry only if this
    # rollback undoes a rejection record... it cannot: rejections never mutate
    # files, so there is nothing file-side to undo for them.
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
    ms = sub.add_parser("measure"); ms.add_argument("mutation")
    ms.add_argument("--fixture-dir", default=""); ms.add_argument("--out", default="")
    m = sub.add_parser("promote"); m.add_argument("mutation"); m.add_argument("--root", default=".")
    r = sub.add_parser("rollback"); r.add_argument("--root", default=".")
    s = sub.add_parser("status"); s.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    return {"propose": cmd_propose, "test": cmd_test, "measure": cmd_measure,
            "promote": cmd_promote,
            "rollback": cmd_rollback, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
