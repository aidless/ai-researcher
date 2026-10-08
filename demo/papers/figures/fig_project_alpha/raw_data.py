"""Figure 2 data: project-level multiplicity across every primary endpoint.

Read from scripts/project_alpha.py's output rather than recomputed here, so the
figure cannot disagree with the audit. The audit recomputes each endpoint from
per-item evidence and applies Benjamini-Hochberg across the project; this file
only reshapes its result.

What the figure has to make obvious: within-run significance and project-level
significance are different claims, and only two of eight endpoints are the second
kind. Three of the five that do not survive were reported in earlier drafts of this
paper as findings.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT = ROOT / "demo/papers/PROJECT-LEVEL-ALPHA.json"

LABELS = {
    "matrix-01": "8 families, arithmetic (matrix-01)",
    "transfer-01": "2 families, arithmetic (transfer-01)",
    "failclosed-01": "seeded-defect detection (failclosed-01)",
    "exp-01": "exploratory gain (exp-01)",
    "swarm-ms": "swarm amplification (swarm-ms)",
    "coderepair-01": "code-repair refutation (coderepair-01)",
    "swarm-fd": "swarm, fixed disagreement (swarm-fd)",
    "swarm-fd2": "swarm, forced decisions (swarm-fd2)",
    "sweetspot-04": "inference budget (sweetspot-04)",
}


def build() -> dict:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    dirs = d.get("directions", {})
    rows = []
    for label, e in d["endpoints"].items():
        run = e["run"]
        p_bh = e["p_bh"]
        rows.append({
            "run": run,
            "label": LABELS.get(run, run),
            "p_bh": p_bh,
            "survives": e["survives"],
            "direction": dirs.get(run, {}).get("direction", "unstated"),
            "plot_p": max(p_bh, 1e-18),
        })
    rows.sort(key=lambda r: r["plot_p"])
    return {
        "rows": rows,
        "family_size": d["family_size"],
        "alpha": d["alpha"],
        "n_surviving": sum(1 for r in rows if r["survives"]),
        "untested_directional_claims": d.get("untested_directional_claims", []),
        "n_supporting": len(d.get("surviving_supporting_claim", [])),
        "n_contradicting": len(d.get("surviving_contradicting_claim", [])),
        "withdrawn": list(d.get("withdrawn", {})),
        "in_flight": d.get("in_flight", []),
        "source_audit": "demo/papers/PROJECT-LEVEL-ALPHA.json",
    }


DATA = build()

if __name__ == "__main__":
    print(json.dumps(DATA, indent=1))
