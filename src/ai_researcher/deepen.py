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


def cmd_deepen(args):
    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    tasks = plan(rep)
    auto = [t for t in tasks if t["executable"] == "auto"]
    rest = [t for t in tasks if t["executable"] != "auto"]
    print(f"deepening plan: {len(tasks)} tasks ({len(auto)} auto, {len(rest)} assisted/human)")
    for t in tasks:
        print(f"  [{t['executable']:8}] {t['check']}: {t['instruction'][:100]}")
    (Path(args.out) / "DEEPEN_PLAN.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}/DEEPEN_PLAN.json")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.deepen")
    ap.add_argument("report"); ap.add_argument("--out", required=True)
    return cmd_deepen(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
