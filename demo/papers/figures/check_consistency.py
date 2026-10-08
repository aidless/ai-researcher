"""Figure/text/audit consistency check.

A figure whose caption quotes numbers that no longer match its data is worse than
no figure, because it is checked by eye and believed. This script recomputes every
number the two figure captions quote and fails if any disagrees with the artifact
it came from.

Three ways to drift:
  1. a bundle is amended        -> raw_data.py recomputes, caption goes stale
  2. the audit is re-run        -> PROJECT-LEVEL-ALPHA.json changes, caption goes stale
  3. the figure is re-plotted    -> caption goes stale

So the caption is checked against recomputed values, not against the image.
Writes figure_check.md.

Run: PYTHONPATH=src python3 demo/papers/figures/check_consistency.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]  # figures/ -> papers/ -> demo/ -> repo root
FIGDIR = ROOT / "demo/papers/figures"
MANUSCRIPT = ROOT / "demo/papers/SYNTHESIS.md"
REPORT = FIGDIR / "figure_check.md"


def load(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def fmt(v):
    return f"{v:.3f}".lstrip("0") if abs(v) < 1 else f"{v:.3f}"


def main():
    text = MANUSCRIPT.read_text(encoding="utf-8")
    problems, checked = [], 0

    f1 = load("fig1_raw", FIGDIR / "fig_transfer_forest" / "raw_data.py")
    for r in f1.DATA["rows"]:
        if r["family"] not in text:
            problems.append(f"Fig1: family {r['family']} plotted but never named in the manuscript")
        for key in ("gain", "ci_lo", "ci_hi"):
            v = fmt(r[key])
            if v not in text:
                problems.append(f"Fig1: {r['family']} {key}={v} absent from the manuscript")
            checked += 1
        if r["gain"] <= 0:
            problems.append(f"Fig1: {r['family']} gain is not positive, so 'all families improve' would be false")
    if f"{f1.DATA['n_families']}/{f1.DATA['n_families']}" not in text:
        problems.append("Fig1: the all-families-improve count is not stated")
    if str(f1.DATA["n_items"]) not in text:
        problems.append("Fig1: per-family item count is not stated")

    f2 = load("fig2_raw", FIGDIR / "fig_project_alpha" / "raw_data.py")
    audit = json.loads((ROOT / "demo/papers/PROJECT-LEVEL-ALPHA.json").read_text(encoding="utf-8"))
    if f2.DATA["family_size"] != audit["family_size"]:
        problems.append(f"Fig2: figure family_size {f2.DATA['family_size']} != audit {audit['family_size']}")
    n_surv = len(audit["surviving"])
    if f2.DATA["n_surviving"] != n_surv:
        problems.append("Fig2: surviving count disagrees with the audit")
    for want in (f"{audit['family_size'] - n_surv} of {audit['family_size']}", str(audit["family_size"])):
        if want not in text:
            problems.append(f"Fig2: manuscript does not state {want!r}")
    checked += 3
    n_untested = len(audit.get("untested_directional_claims", []))
    if n_untested and not any(w in text for w in (f"{n_untested} further arms", f"{n_untested} arms")):
        problems.append(f"Fig2: the {n_untested} untested arms are not disclosed, so the figure would overstate coverage")

    figs = sorted(FIGDIR.glob("*/*.png"))
    if len(figs) < 2:
        problems.append(f"expected 2 rendered figures, found {len(figs)}")

    lines = ["---", "tags: [figure, consistency, check]", "---", "",
             "# Figure consistency check", "",
             f"- values checked: {checked}",
             f"- rendered figures: {', '.join(f.relative_to(ROOT).as_posix() for f in figs)}",
             f"- verdict: **{'PASS' if not problems else 'FAIL'}**", ""]
    if problems:
        lines += ["## Problems", ""] + [f"- {p}" for p in problems] + [""]
    else:
        lines += ["Every number the captions quote was recomputed from the signed bundle or the "
                  "audit output and matched. Re-run after any amendment or any re-run of "
                  "`scripts/project_alpha.py`; the captions are what goes stale silently.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
