"""sweetspot-04: is the cap-1000 cliff real at an n that can resolve it?

sweetspot-03 measured accuracy across reasoning caps (150 / 400 / 1000) on 18
calibrated discriminative items and saw a flat-then-cliff shape in the code family
(0.833, 0.833, 0.333). Both seats refused it: n=6 per family, indistinguishable
from noise. The power pre-check added 2026-10-08 now requires n>=63 paired
observations for a 0.25 effect, so this arm runs the same comparison with enough
items to resolve it.

Two deliberate design choices:

1. Items come from the code-repair bank (run_coderepair.TESTS, 48 items across four
   bug classes), not a freshly invented set. That bank is already covered by an
   executable self-test -- every buggy source fails its own hidden tests, known-good
   implementations pass -- so the item validity argument does not have to be made
   twice, and three scorer bugs that would each have looked like a result cannot
   reappear here.
2. The only factor that varies is the reasoning budget (`num_predict`). Items,
   prompts, scorer, seed and models are fixed, so a cap effect cannot be
   confounded with item difficulty the way a fresh item bank could.

Statistic: exact binomial (McNemar) on the paired discordant items between cap 400
and cap 1000, per model and pooled. A "cliff" is confirmed only if the pooled test
resolves AND the direction is negative AND at least one model shows it -- a single
model moving is not a length effect, it is that model.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import sys
from math import comb

def _repo_root(start: pathlib.Path) -> pathlib.Path:
    """Walk up to the directory that holds src/ai_researcher.

    Counting `parents[n]` is how this file failed twice: parents[1] put
    demo/coderepair at <root>/coderepair, and "fixing" it to parents[2] put the
    root one level above the repository. A marker directory cannot be miscounted.
    """
    d = start.resolve()
    for cand in [d, *d.parents]:
        if (cand / "src" / "ai_researcher").is_dir():
            return cand
    raise SystemExit(f"no repository root above {start} (no src/ai_researcher)")


HERE = pathlib.Path(__file__).resolve().parent
REPO = _repo_root(HERE)
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "demo" / "shared"))
sys.path.insert(0, str(REPO / "demo" / "coderepair"))

from run_coderepair import (  # noqa: E402
    TESTS, extract_code, resolve_models, run_tests,
    selftest as harness_selftest,
)

CAPS = [150, 400, 1000]
MODELS = ["qwen2.5:7b", "deepseek-r1:7b"]
PROMPT = ("Fix the bug. Reply with only the complete corrected function "
          "inside one ```python code block.")


def mcnemar(fixed: int, broke: int) -> float:
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def build_bank(seed: int):
    items = []
    for cls, src, tests, hinted in TESTS:
        for k in range(4):
            items.append({"cls": cls, "src": src, "tests": tests,
                          "hinted": hinted, "rep": k})
    random.Random(seed).shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = f"ss{i:02d}"
    return items


def main():
    from ollama_guard import call
    seed = int(os.environ.get("EVO_SEED", "20261008"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    models = resolve_models(
        [m for m in os.environ.get("EVO_MODELS", "").split(",") if m] or MODELS)
    if not models:
        raise SystemExit("no requested models are installed; refusing to run")
    items = build_bank(seed)
    (out / "items.json").write_text(json.dumps(
        [{**{k: v for k, v in it.items() if k != "tests"},
          "n_tests": len(it["tests"])} for it in items], indent=1) + "\n")

    detail = {}
    for model in models:
        detail[model] = {}
        for cap in CAPS:
            rows, passed = [], 0
            for it in items:
                user = f"```python\n{it['src']}```\n\n{PROMPT}"
                try:
                    txt = call(model, user, timeout=200, num_predict=cap)
                    ok, why = run_tests(extract_code(txt), it["tests"])
                except Exception as e:
                    # Truncation at the cap is an infrastructure event, not a model
                    # failure: the model may have been correct past the budget. It is
                    # recorded separately so a cap effect is never manufactured out of
                    # our own budget setting.
                    msg = str(e)
                    ok = False
                    why = ("TRUNCATED" if "truncated" in msg
                           else f"{type(e).__name__}: {msg}"[:70])
                rows.append({"id": it["id"], "cls": it["cls"],
                             "passed": ok, "why": why})
                passed += bool(ok)
            (out / f"out_{model.replace(':', '_')}_cap{cap}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            detail[model][cap] = rows
            print(f"{model} cap={cap}: acc={passed / len(items):.4f}", flush=True)

    acc = {m: {c: round(sum(1 for r in detail[m][c] if r["passed"]) / len(items), 4)
               for c in CAPS} for m in models}
    trunc = {m: {c: sum(1 for r in detail[m][c] if r["why"] == "TRUNCATED")
                 for c in CAPS} for m in models}

    # cliff test: cap1000 worse than cap400, paired
    per_model, pf, pb = {}, 0, 0
    for m in models:
        f_ = b_ = 0
        for a, b in zip(detail[m][400], detail[m][1000]):
            f_ += bool(b["passed"] and not a["passed"])
            b_ += bool(a["passed"] and not b["passed"])
        per_model[m] = {"cap400_fixed": f_, "cap1000_broke": b_,
                        "p": round(mcnemar(f_, b_), 6),
                        "delta": round(acc[m][1000] - acc[m][400], 4)}
        pf += f_
        pb += b_
    pooled_p = mcnemar(pf, pb)
    negatives = sum(1 for m in models if acc[m][1000] < acc[m][400])
    cliff = bool(pooled_p < 0.05 and pb > pf and negatives >= 1
                 and all(v["delta"] < 0 for v in per_model.values()))
    res = {
        "domain": "code_repair_budget",
        "caps": CAPS, "n_items": len(items),
        "models_requested": MODELS, "models_measured": models,
        "acc": acc, "truncated": trunc, "per_model": per_model,
        "pooled": {"cap400_fixed": pf, "cap1000_broke": pb,
                   "mcnemar_p": round(pooled_p, 6)},
        "families_negative": f"{negatives}/{len(models)}",
        "cliff_confirmed": cliff,
        "confirmed": cliff,
    }
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"acc": acc, "pooled_p": round(pooled_p, 6),
                      "cliff_confirmed": cliff}, ensure_ascii=False))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(harness_selftest())
    main()
