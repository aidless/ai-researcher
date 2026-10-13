"""Cross-dataset confirmatory arm: does the arithmetic effect hold on non-GSM8K sources?

The entire confirmatory record runs on GSM8K-style items. A reviewer's first
question is whether the effect is a property of one dataset's idiom rather than
of arithmetic: GSM8K problems are word problems with particular surface features,
and a model can acquire the surface form while failing on differently-phrased
arithmetic.

This arm tests on two held-out sets with independent provenance:
  svamp   1000 items (Patel et al. 2021), a challenge set built by applying
          perturbations to GSM8K-style seed problems
  asdiv   2248 items (Miao et al. 2020), a diverse arithmetic corpus

Selection is fixed before running (first N by id, seed recorded), disjointness
from confirm160 is verified by exact text match, and ~120 items are subsampled per
set to keep the paired count above the power requirement without exceeding the
wall clock. 120 x 3 models = 360 paired observations per dataset, against
required n=157 for mde 0.25.

Kill-switch keys on `confirmed`, and the preregistered requirement is that BOTH
datasets show the effect -- one dataset alone does not confirm, because one
dataset alone is what the current record already has.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from math import comb

def _resolve_root(start: pathlib.Path) -> pathlib.Path:
    """Repo root, never derived from the process cwd.

    On this working tree (F:\\deepseek) the kernel cwd reports a DOUBLED
    backslash, so paths built from os.getcwd() fail existence checks on files that
    are present. EVO_REPO_ROOT comes from the loop, which derives it from
    __file__; the parent walk is the fallback and is only trusted when it can
    actually READ the marker.
    """
    env = os.environ.get("EVO_REPO_ROOT")
    if env:
        try:
            with open(os.path.join(env, "src", "ai_researcher", "loop.py"), "rb"):
                return pathlib.Path(env)
        except OSError:
            pass
    for cand in [start] + list(start.parents):
        try:
            with open(os.path.join(str(cand), "src", "ai_researcher", "loop.py"), "rb"):
                return cand
        except OSError:
            continue
    raise SystemExit("no repository root; set EVO_REPO_ROOT")


HERE = pathlib.Path(__file__).resolve().parent


def _repo_root(start: pathlib.Path) -> pathlib.Path:
    env = os.environ.get("EVO_REPO_ROOT")
    if env:
        try:
            with open(os.path.join(env, "src", "ai_researcher", "loop.py"), "rb"):
                return pathlib.Path(env)
        except OSError:
            pass
    for cand in [start] + list(start.parents):
        try:
            with open(os.path.join(str(cand), "src", "ai_researcher", "loop.py"), "rb"):
                return cand
        except OSError:
            continue
    raise SystemExit("no repository root; set EVO_REPO_ROOT")
from ai_researcher import canonical
REPO = pathlib.Path(canonical.repo_root())
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "demo" / "shared"))
sys.path.insert(0, str(REPO / "demo" / "transfer"))

from run_confirmation import PROMPTS, available_models, extract_number, mcnemar  # noqa: E402
from ai_researcher import canonical
from ollama_guard import call  # noqa: E402

SRC = REPO / "data" / "arithmetic"
CONFIRM = REPO / "demo/transfer/items/confirm160.json"
N_PER_SET = 120
MODELS = ["qwen2.5:7b", "gemma3:4b", "llama3.1:8b"]


def load_set(name: str) -> list:
    d = json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))
    return d["cases"]


def selftest() -> int:
    problems = []
    for name in ("svamp", "asdiv-rest"):
        p = SRC / f"{name}.json"
        if not p.exists():
            problems.append(f"missing dataset: {p}")
            continue
        cases = load_set(name)
        if len(cases) < N_PER_SET:
            problems.append(f"{name} has {len(cases)} items, need {N_PER_SET}")
        ids = [c["id"] for c in cases[:N_PER_SET]]
        if len(set(ids)) != len(ids):
            problems.append(f"{name}: duplicate ids")
        for c in cases[:N_PER_SET]:
            if c.get("expected") is None:
                problems.append(f"{name}: {c['id']} has no gold")
                break
    if CONFIRM.exists():
        gs = {c["input"].strip() for c in
              json.loads(CONFIRM.read_text(encoding="utf-8"))["cases"]}
        for name in ("svamp", "asdiv-rest"):
            if not (SRC / f"{name}.json").exists():
                continue
            cases = load_set(name)[:N_PER_SET]
            ov = {c["input"].strip() for c in cases} & gs
            if ov:
                problems.append(f"{name}: {len(ov)} items overlap confirm160")
    for p in problems:
        print(f"  [SELFTEST FAIL] {p}")
    if not problems:
        print(f"  [SELFTEST OK] svamp {N_PER_SET} + asdiv-rest {N_PER_SET}, "
              f"golds present, ids unique, no overlap with confirm160")
    return 1 if problems else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if selftest():
        return 1
    seed = int(os.environ.get("EVO_SEED", "20261012"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    requested = [m.strip() for m in
                 os.environ.get("EVO_MODELS", ",".join(MODELS)).split(",") if m.strip()]
    have = available_models()
    models = [m for m in requested if m in have]
    dropped = [m for m in requested if m not in have]
    if dropped:
        print(f"[preflight] not installed, excluded before measurement: {dropped}")
    if not models:
        print("no requested models installed; refusing to run")
        return 1

    results, per_dataset = {}, {}
    for name in ("svamp", "asdiv-rest"):
        cases = load_set(name)[:N_PER_SET]
        detail = {}
        for model in models:
            for pol, tmpl in PROMPTS.items():
                rows = []
                for c in cases:
                    try:
                        t = call(model, tmpl.format(q=c["input"]), timeout=180,
                                 num_predict=400)
                        got = extract_number(t, pol)
                        ok = got is not None and abs(got - float(c["expected"])) < 1e-6
                    except Exception:
                        ok = False
                    rows.append({"id": c["id"], "passed": ok})
                (out / f"out_{model.replace(':', '_')}_{name}_{pol}.jsonl").write_text(
                    "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
                detail.setdefault(model, {})[pol] = rows
                print(f"{name} {model} {pol}: {sum(r['passed'] for r in rows)}/{len(rows)}",
                      flush=True)
        fx = br = 0
        gains = {}
        for m in models:
            a = detail[m]["direct"]
            b = detail[m]["step-calc"]
            fx += sum(1 for x, y in zip(a, b) if y["passed"] and not x["passed"])
            br += sum(1 for x, y in zip(a, b) if x["passed"] and not y["passed"])
            gains[m] = round(sum(y["passed"] for y in b) / len(b)
                             - sum(x["passed"] for x in a) / len(a), 4)
        npos = sum(1 for g in gains.values() if g > 0)
        per_dataset[name] = {"n_items": N_PER_SET, "models": models,
                              "gains": gains, "fixed": fx, "broke": br,
                              "mcnemar_p": round(mcnemar(fx, br), 8),
                              "families_positive": f"{npos}/{len(models)}"}
        results[name] = per_dataset[name]

    both_positive = all(d["families_positive"] == f"{len(models)}/{len(models)}"
                        for d in per_dataset.values())
    both_significant = all(d["mcnemar_p"] < 0.05 for d in per_dataset.values())
    res = {"domain": "arithmetic", "arm": "cross_dataset_confirmation",
           "datasets": ["svamp", "asdiv-rest"],
           "n_per_dataset": N_PER_SET,
           "models_requested": MODELS, "models_measured": models,
           "per_dataset": per_dataset,
           "results": results,
           "paired_observations_per_dataset": N_PER_SET * len(models),
           "confirmed": bool(both_positive and both_significant),
           "_config": {"n_items": N_PER_SET, "models": len(models),
                       "datasets": 2},
           "measurable": True}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"per_dataset": {k: {"gains": v["gains"], "p": v["mcnemar_p"],
                                          "fam": v["families_positive"]}
                                      for k, v in per_dataset.items()},
                      "confirmed": res["confirmed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
