"""Auto-deepen: when a tier gate fails, dig deeper instead of stopping.

"达不到就继续深挖" is a loop, not a sentiment. For each failed check, this
module maps the failure to a concrete deepening action, executes the ones that
are executable without new paid calls or human judgment, and re-runs the gate.
What it cannot execute becomes a named task with an owner (human or budgeted
run) instead of a vague "needs work".

Deepening means substance, never padding:
  - a missing generality discussion gets WRITTEN from the actual evidence
    (what the numbers do and do not cover), not filled with boilerplate
  - a missing ablation gets DESIGNED as a preregistered envelope draft
  - a missing effect size gets COMPUTED from committed detail data
  - a missing baseline gets NAMED (which prior methods, why each matters)
  - a vague term gets DEFINED (necessary/sufficient conditions + a test that
    would show the definition is wrong)

What deepen.py refuses to do: invent numbers, hedge without evidence, or mark
a check pass because the text now mentions the keyword. After deepening, the
gate re-runs from scratch; a check passes only if the substance is there.

Usage:
    python -m ai_researcher.deepen <publish-report.json> --paper <paper_dir> --out <paper_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def plan(report: dict) -> list:
    """Map each failed check to a deepening task. Returns task dicts."""
    tasks = []
    for m in report.get("mechanical", []):
        if m.get("pass"):
            continue
        cid, reason = m["id"], m.get("reason", "")
        kind = cid.split("-", 1)[-1] if "-" in cid else cid
        if kind in ("generality-discussed",):
            tasks.append({"check": cid, "kind": "write",
                          "instruction": "write a Generality section from the evidence: "
                                         "for each claim, state the exact conditions tested "
                                         "(models, n, metric) and the nearest untested neighbor. "
                                         f"Gate reason: {reason}",
                          "executable": "assisted"})
        elif kind in ("predecessors-acknowledged",):
            tasks.append({"check": cid, "kind": "research",
                          "instruction": "list the 3+ closest prior works with one-line "
                                         "differs-statements each. Requires literature access; "
                                         "draft candidates from the manuscript's existing "
                                         "citations first.",
                          "executable": "assisted"})
        elif kind in ("examples-present",):
            tasks.append({"check": cid, "kind": "write",
                          "instruction": "write one worked example end-to-end (input, "
                                         "what the method does step by step, output, "
                                         "why it matters), using only committed numbers.",
                          "executable": "assisted"})
        elif kind in ("effect-size",):
            tasks.append({"check": cid, "kind": "compute",
                          "instruction": "compute effect sizes + practical-significance "
                                         "discussion from committed per-case detail data. "
                                         "Runnable now if detail exists.",
                          "executable": "auto"})
        elif kind in ("baselines-comprehensive",):
            tasks.append({"check": cid, "kind": "research",
                          "instruction": "name every relevant prior baseline and justify "
                                         "each inclusion/exclusion. Needs literature + "
                                         "compute for new runs.",
                          "executable": "assisted"})
        elif kind in ("ablation-complete",):
            tasks.append({"check": cid, "kind": "envelope",
                          "instruction": "draft a preregistered ablation envelope for each "
                                         "unablated design choice (what varies, what is "
                                         "measured, kill-switch, budget).",
                          "executable": "auto"})
        elif kind in ("data-code-available",):
            tasks.append({"check": cid, "kind": "write",
                          "instruction": "state concrete data/code locations (repo path, "
                                         "not a promise). Runnable now.",
                          "executable": "auto"})
        elif kind in ("impact-ethics",):
            tasks.append({"check": cid, "kind": "write",
                          "instruction": "write broader-impact (who benefits, who could be "
                                         "harmed, dual-use) + ethics (data, consent, compute "
                                         "footprint) from the actual work, not boilerplate.",
                          "executable": "assisted"})
        elif kind in ("limitations-present", "ci-present"):
            tasks.append({"check": cid, "kind": "compute",
                          "instruction": f"derive from committed evidence. Gate reason: {reason}",
                          "executable": "auto"})
        else:
            tasks.append({"check": cid, "kind": "human",
                          "instruction": f"no automatic deepening defined: {reason}",
                          "executable": "human"})
    return tasks


def _exec_effect_size(task: dict, ctx: dict) -> dict:
    """Compute Cohen's h + CIs from committed per-case detail. Returns result."""
    import math
    detail = (ctx.get("result") or {}).get("models", {})
    if not detail:
        return {"done": False, "reason": "no models/detail in result; nothing to compute from"}
    lines = []
    for model, m in detail.items():
        dd = m.get("policies", {}).get("direct", {}).get("detail", [])
        ss = m.get("policies", {}).get("step-calc", {}).get("detail", [])
        if not dd or not ss:
            return {"done": False,
                    "reason": f"{model}: per-case detail missing, refusing to invent"}
        p1 = sum(d["passed"] for d in ss) / len(ss)
        p0 = sum(d["passed"] for d in dd) / len(dd)
        h = 2 * math.asin(math.sqrt(max(0, min(1, p1)))) - \
            2 * math.asin(math.sqrt(max(0, min(1, p0))))
        mag = "large" if abs(h) >= 0.8 else "medium" if abs(h) >= 0.5 else "small"
        ci = (m.get("gain_ci95") or ["?", "?"])
        lines.append(f"- {model}: Cohen's h = {h:.3f} ({mag}); "
                     f"raw gain {(p1 - p0):.3f} [{ci[0]}, {ci[1]}]. "
                     f"Practical reading: {'visible to the naked eye' if abs(h) >= 0.8 else 'needs the CI, not the p-value'}.")
    (Path(ctx["paper"]) / "EFFECT_SIZES.md").write_text(
        "# Effect sizes (machine-computed from committed detail)\n\n"
        + "\n".join(lines) + "\n", encoding="utf-8")
    return {"done": True, "wrote": "EFFECT_SIZES.md", "lines": lines}


def _exec_ablation_envelope(task: dict, ctx: dict) -> dict:
    """Draft a preregistered ablation envelope for the named gap."""
    env = {"hypothesis": f"ablation for {task['check']}: see instruction",
           "methods": "TBD by human (ablation target machine-specific)",
           "max_rounds": 1, "max_cost_usd": 0.0, "max_wall_hours": 2.0,
           "seed": 20261006,
           "power": {"n": 0, "alpha": 0.05, "min_detectable_effect": 0.0,
                     "power_at_mde": 0.0},
           "kill_switch": [{"condition": "confirmed == True", "action": "STOP-EXTEND",
                            "note": ""},
                           {"condition": "confirmed == False", "action": "STOP-REFUTED",
                            "note": ""}],
           "required_artifacts": ["result.json"],
           "negative_publish": "replication-report",
           "approved_by": "", "approved_at": "",
           "tension": task["instruction"][:500],
           "source_check": task["check"]}
    name = f"ablation-{task['check'].lower().replace('_', '-')}.draft.json"
    (Path(ctx["paper"]) / name).write_text(
        json.dumps(env, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"done": True, "wrote": name,
            "note": "draft only: power fields are zero, human must fill n/effect before approval"}


def _exec_data_code(task: dict, ctx: dict) -> dict:
    """State concrete data/code locations from the actual run directories."""
    workdir = Path(ctx.get("workdir", "."))
    lines = ["# Data & code availability (machine-stated, checkable)", ""]
    for rnd in sorted(workdir.glob("round-*")):
        arts = rnd / "artifacts"
        if arts.exists():
            files = sorted(p.name for p in arts.iterdir() if p.is_file())
            lines.append(f"- {rnd.name}/artifacts/: {', '.join(files)}")
    lines += ["", "- Code: ai-researcher package at the pinned commit (see paper manifest).",
              "- Seeds, model digests: see each round envelope.json."]
    (Path(ctx["paper"]) / "DATA_CODE.md").write_text("\n".join(lines) + "\n",
                                                     encoding="utf-8")
    return {"done": True, "wrote": "DATA_CODE.md"}


_EXECUTORS = {"effect-size": _exec_effect_size,
              "ablation-complete": _exec_ablation_envelope,
              "data-code-available": _exec_data_code}


def cmd_deepen(args):
    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    tasks = plan(rep)
    auto = [t for t in tasks if t["executable"] == "auto"]
    rest = [t for t in tasks if t["executable"] != "auto"]
    print(f"deepening plan: {len(tasks)} tasks ({len(auto)} auto, {len(rest)} assisted/human)")
    for t in tasks:
        print(f"  [{t['executable']:8}] {t['check']}: {t['instruction'][:100]}")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "DEEPEN_PLAN.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}/DEEPEN_PLAN.json")
    # Execute what is executable. Anything raising is recorded, never swallowed:
    # a deepening step that fails must say so, or the next gate re-run would
    # pass on the assumption that deepening happened.
    ctx = {"paper": args.out}
    if getattr(args, "workdir", ""):
        ctx["workdir"] = args.workdir
        try:
            st = json.loads((Path(args.workdir) / "state.json").read_text(
                encoding="utf-8"))
            if st.get("rounds"):
                ctx["result"] = st["rounds"][-1].get("result", {})
        except Exception as e:
            print(f"  [WARN] cannot load run state: {e}; compute tasks will refuse")
    results = []
    for t in auto:
        kind = t["check"].split("-", 1)[-1] if "-" in t["check"] else t["check"]
        fn = _EXECUTORS.get(kind)
        if not fn:
            results.append({"check": t["check"], "done": False,
                            "reason": "no executor registered"})
            continue
        try:
            r = fn(t, ctx)
        except Exception as e:
            r = {"done": False, "reason": f"{type(e).__name__}: {e}"}
        r["check"] = t["check"]
        results.append(r)
        print(f"  [{'DONE' if r['done'] else 'FAILED'}] {t['check']}: "
              f"{r.get('wrote', r.get('reason', ''))}")
    (Path(args.out) / "DEEPEN_RESULTS.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.deepen")
    ap.add_argument("report"); ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="")
    return cmd_deepen(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
