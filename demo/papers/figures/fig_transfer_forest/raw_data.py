"""Figure 1 data: per-family transfer gains with paired-bootstrap intervals.

Pure data, recomputed from the signed bundle. Nothing here is typed by hand: run

    PYTHONPATH=src python3 scripts/project_alpha.py     # for the BH panel
    python3 demo/papers/figures/fig_transfer_forest/raw_data.py

and every number below is derived from
demo/runs/matrix-01/round-01/artifacts/result.json, whose per-item flags are what
the interval is bootstrapped over. The caption quotes these values, so if the
bundle is amended the figure and the caption must be regenerated together.
"""
from __future__ import annotations

import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[4]
BUNDLE = ROOT / "demo/runs/matrix-01/round-01/artifacts/result.json"
BOOT_REPS = 5000
BOOT_SEED = 20261010


def _boot_paired(direct, step, reps=BOOT_REPS, seed=BOOT_SEED):
    rng = random.Random(seed)
    n = len(direct)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(step[i] for i in idx) / n
                     - sum(direct[i] for i in idx) / n)
    diffs.sort()
    return round(diffs[int(0.025 * reps)], 4), round(diffs[int(0.975 * reps)], 4)


def build() -> dict:
    d = json.loads(BUNDLE.read_text(encoding="utf-8"))
    rows = []
    for name, v in d["models"].items():
        dd = [1 if r["passed"] else 0 for r in v["policies"]["direct"]["detail"]]
        sd = [1 if r["passed"] else 0 for r in v["policies"]["step-calc"]["detail"]]
        lo, hi = _boot_paired(dd, sd)
        fixed = sum(1 for a, b in zip(dd, sd) if b and not a)
        broke = sum(1 for a, b in zip(dd, sd) if a and not b)
        rows.append({
            "family": name,
            "direct": v["policies"]["direct"]["acc"],
            "step_calc": v["policies"]["step-calc"]["acc"],
            "gain": round(v["policies"]["step-calc"]["acc"]
                          - v["policies"]["direct"]["acc"], 4),
            "ci_lo": lo, "ci_hi": hi,
            "fixed": fixed, "broke": broke,
            "n_items": len(dd),
        })
    rows.sort(key=lambda r: r["gain"])
    return {
        "rows": rows,
        "n_items": rows[0]["n_items"],
        "n_families": len(rows),
        "families_positive": f"{sum(1 for r in rows if r['gain'] > 0)}/{len(rows)}",
        "boot_reps": BOOT_REPS, "boot_seed": BOOT_SEED,
        "source_bundle": "demo/runs/matrix-01/round-01/artifacts/result.json",
    }


DATA = build()

if __name__ == "__main__":
    print(json.dumps(DATA, indent=1))
