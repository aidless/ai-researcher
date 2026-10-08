"""Reusable preregistration protocols: declare the difference, not the boilerplate.

Every envelope in this project was hand-written, and every one re-derived the same
scaffolding: a paired-transfer methods string, a McNemar kill-switch, a signed
artifact list, a power block. Two consequences. First, the hand-written copies
drifted -- matrix-01's kill-switch keyed on a field its harness never emitted,
which is exactly the class of bug a shared template prevents. Second, a new
experiment costs a page of boilerplate before any thinking happens.

A protocol here is the part that should NOT vary between experiments: the methods
skeleton, the artifact contract, the statistics, and a kill-switch whose keys are
fields a conforming harness emits. An experiment supplies only its deltas.

    python -m ai_researcher.protocols paired-transfer --out env.json \\
        --models qwen2.5:7b,gemma3:4b --n 160 --mde 0.10

The generated envelope is still inert: seed 0 and empty approved_by, so it cannot
run until a human fixes the seed and approves. Protocols cannot authorise work.

Each protocol declares `emits` -- the result.json fields its kill-switch keys on.
`check_emits` refuses a protocol whose rows reference a field no conforming
harness writes, which is the check matrix-01 needed and did not have.
"""
from __future__ import annotations

import json
import pathlib

# --------------------------------------------------------------------------
# protocol definitions
# --------------------------------------------------------------------------

PROTOCOLS = {
    "paired-transfer": {
        "summary": "two policies on the same held-out items, paired per item, "
                   "McNemar exact test, per-family and pooled.",
        "emits": ["gain", "families_positive", "mcnemar_pooled", "confirmed",
                  "models", "n"],
        "required_artifacts": ["result.json", "items.json"],
        "methods": (
            'RD="$PWD"; ROOT=""; d="$RD"; while [ "$d" != "/" ]; do '
            '[ -d "$d/src/ai_researcher" ] && { ROOT="$d"; break; }; '
            'd=$(dirname "$d"); done; '
            '[ -n "$ROOT" ] || { echo "no repo root" >&2; exit 1; }; '
            '# TODO(policy): replace with the arm script\n'
            'PYTHONPATH="$ROOT/src:$ROOT/demo/shared" python3 '
            '"$ROOT/demo/<arm>/run_<arm>.py"'
        ),
        "kill_switch": [
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "gain replicates: extend to more families or more items"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "no replicable gain: restrict the claim to the conditions "
                     "actually tested"},
            {"condition": "families_positive == None", "action": "STOP-INCONCLUSIVE",
             "note": "direction unresolvable at this n: report intervals, do not "
                     "claim an effect"},
        ],
        "tension": (
            "TODO: state the discrepancy between what the theory predicts and "
            "what is observed, plus what answering it would change. A hypothesis "
            "without a tension is a solution in search of a problem."
        ),
    },
    "boundary-probe": {
        "summary": "re-run a refuted comparison on a shifted axis, changing one "
                   "factor, to locate where the effect stops holding.",
        "emits": ["gain_mean", "best_policy", "confirmed",
                  "guard_minus_arith_net", "contrasts"],
        "required_artifacts": ["result.json", "items.json"],
        "methods": (
            'RD="$PWD"; ROOT=""; d="$RD"; while [ "$d" != "/" ]; do '
            '[ -d "$d/src/ai_researcher" ] && { ROOT="$d"; break; }; '
            'd=$(dirname "$d"); done; '
            '[ -n "$ROOT" ] || { echo "no repo root" >&2; exit 1; }; '
            '# TODO(policy): the arm script that varies exactly one factor\n'
            'PYTHONPATH="$ROOT/src:$ROOT/demo/shared" python3 '
            '"$ROOT/demo/<arm>/run_<arm>.py"'
        ),
        "kill_switch": [
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "the shift explains the reversal: the effect depends on the "
                     "factor that was shifted"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "no adaptation recovers the gain: the boundary is a property "
                     "of the original domain, not of the policy"},
        ],
        "tension": (
            "A claim replicated widely on one axis and failed on a shifted one. "
            "Either the mechanism does not generalise, or the treatment was "
            "mismatched to the shifted task, and re-running the same comparison "
            "cannot separate them. Answering it decides whether the result is a "
            "bounded mechanism or a general one."
        ),
    },
    "judge-agreement": {
        "summary": "multiple evaluator families rate identical items; measure "
                   "inter-rater agreement and decision flips.",
        "emits": ["pairwise_agreement", "flip_cases", "abstentions", "confirmed",
                  "votes", "n_diffs"],
        "required_artifacts": ["result.json"],
        "methods": (
            'RD="$PWD"; ROOT=""; d="$RD"; while [ "$d" != "/" ]; do '
            '[ -d "$d/src/ai_researcher" ] && { ROOT="$d"; break; }; '
            'd=$(dirname "$d"); done; '
            '[ -n "$ROOT" ] || { echo "no repo root" >&2; exit 1; }; '
            '# TODO(policy): the judge-agreement harness\n'
            'PYTHONPATH="$ROOT/src:$ROOT/demo/shared" python3 '
            '"$ROOT/demo/<arm>/run_<arm>.py"'
        ),
        "kill_switch": [
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "evaluators disagree on deployment decisions: extend the "
                     "item set and add a frontier evaluator"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "evaluators agree: evaluator choice does not move decisions "
                     "on this task class"},
        ],
        "tension": (
            "Teams route decisions through whichever evaluator is cheapest, "
            "assuming evaluator choice is cosmetic. Whether competent evaluators "
            "reach the same decisions on identical inputs is unmeasured, so every "
            "unmeasured evaluator choice is an uncontrolled experiment."
        ),
    },
    "confound-audit": {
        "summary": "re-run a contaminated or withdrawn round with the named "
                   "artifact removed, unchanged otherwise.",
        "emits": ["confirmed", "gain", "families_positive", "n"],
        "required_artifacts": ["result.json"],
        "methods": (
            'RD="$PWD"; ROOT=""; d="$RD"; while [ "$d" != "/" ]; do '
            '[ -d "$d/src/ai_researcher" ] && { ROOT="$d"; break; }; '
            'd=$(dirname "$d"); done; '
            '[ -n "$ROOT" ] || { echo "no repo root" >&2; exit 1; }; '
            '# TODO(policy): the original arm script, confound removed\n'
            'PYTHONPATH="$ROOT/src:$ROOT/demo/shared" python3 '
            '"$ROOT/demo/<arm>/run_<arm>.py"'
        ),
        "kill_switch": [
            {"condition": "confirmed == True", "action": "STOP-EXTEND",
             "note": "the original observation survives a clean re-run"},
            {"condition": "confirmed == False", "action": "STOP-REFUTED",
             "note": "the original observation was the artifact; record it as a "
                     "lesson, not a finding"},
        ],
        "tension": (
            "A previous round's conclusion cannot be separated from an "
            "infrastructure or procedural artifact, so the claim is neither "
            "supported nor refuted and its direction is unknown. An unknown "
            "direction is not a result."
        ),
    },
}


def check_emits(name: str) -> list:
    """Kill-switch keys must be fields a conforming harness writes.

    matrix-01 shipped a preregistered rule on `confirmed == True` while its
    script never emitted `confirmed`; `_eval_kill` swallowed the NameError and
    the run was filed as a clean finish. The rule was never checked against the
    harness, which is the part a shared template can actually guarantee.
    """
    proto = PROTOCOLS[name]
    emits = set(proto["emits"])
    problems = []
    for row in proto["kill_switch"]:
        cond = row["condition"]
        for tok in ("True", "False", "None"):
            pass
        for ident in _idents(cond):
            if ident not in emits and not ident.startswith("_"):
                problems.append(
                    f"kill-switch condition {cond!r} references {ident!r}, which "
                    f"the protocol does not declare in emits={sorted(emits)}")
    return problems


def _idents(expr: str) -> list:
    import re
    return [m for m in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", expr)
            if m not in ("True", "False", "None", "and", "or", "not", "in")]


def build(name: str, hypothesis: str, n: int, mde: float,
          alpha: float = 0.05, power: float = 0.8,
          max_wall_hours: float = 4.0, tension: str = None) -> dict:
    if name not in PROTOCOLS:
        raise SystemExit(f"unknown protocol {name!r}; choose from "
                         f"{', '.join(sorted(PROTOCOLS))}")
    proto = PROTOCOLS[name]
    env = {
        "hypothesis": hypothesis,
        "methods": proto["methods"],
        "max_rounds": 1,
        "max_cost_usd": 0.0,
        "max_wall_hours": max_wall_hours,
        # Protocols cannot authorise work: an unset seed means the same command
        # would not give the same assignment, so the envelope stays unexecutable
        # until a human supplies one.
        "seed": 0,
        "power": {"n": n, "alpha": alpha, "min_detectable_effect": mde,
                  "power_at_mde": power},
        "kill_switch": proto["kill_switch"],
        "required_artifacts": proto["required_artifacts"],
        "negative_publish": "replication-report",
        "approved_by": "",
        "approved_at": "",
        "tension": tension or proto["tension"],
        "_protocol": name,
    }
    return env


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai_researcher.protocols")
    ap.add_argument("protocol", choices=sorted(PROTOCOLS) + ["--list"])
    ap.add_argument("--hypothesis", default="")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--mde", type=float, default=0.0)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.8)
    ap.add_argument("--max-wall-hours", type=float, default=4.0)
    ap.add_argument("--tension", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true",
                    help="only report emit-contract problems")
    args = ap.parse_args(argv)
    if args.protocol == "--list":
        for k in sorted(PROTOCOLS):
            print(f"{k:18s} {PROTOCOLS[k]['summary']}")
            problems = check_emits(k)
            if problems:
                for pr in problems:
                    print(f"   !! {pr}")
        return 0
    if args.check:
        problems = check_emits(args.protocol)
        for pr in problems:
            print(f"  !! {pr}")
        print(f"  emit contract: {'OK' if not problems else str(len(problems)) + ' problems'}")
        return 1 if problems else 0
    from .envelope import required_n
    need = required_n(args.mde, alpha=args.alpha, power=args.power, paired=True)
    if not args.hypothesis:
        print("refusing to build: --hypothesis is required "
              "(protocols supply boilerplate, not claims)")
        return 1
    env = build(args.protocol, args.hypothesis, args.n, args.mde,
                args.alpha, args.power, args.max_wall_hours, args.tension)
    text = json.dumps(env, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
        print(f"  protocol={args.protocol} n={args.n} mde={args.mde} "
              f"need_n={need} power_ok={bool(need and args.n >= need)}")
        print("  STILL INERT: seed=0 and approved_by empty. Set the seed and run "
              "`loop approve` before it can execute.")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
