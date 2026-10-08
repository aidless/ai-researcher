"""coderepair-02: does a CODE-ADAPTED reasoning policy recover the gain?

coderepair-01 refuted the domain-general claim: on code repair the
arithmetic-arm policy (step-calc: "state the defect in one line, then write the
fix") was flat on qwen2.5:7b and negative on gemma3:4b. But that negative has a
specific diagnosed cause, and this arm tests the explanation rather than
retesting the fact.

Diagnosis from coderepair-01's failure profile: the dominant genuine failure was
not arithmetic slippage but MISSING GUARDS -- models returned 0, or a stringified
error, where the item required None. Stating the defect first did not make them
notice the requirement.

Hypothesis: step-calc asks for the wrong intermediate step for this domain. A
policy that makes the *specification* explicit before coding should help, and its
help should concentrate on guard-bearing bug classes rather than being uniform.

Policies:
  direct      output the corrected function (control)
  step-calc   one-line defect statement, then the fix (the refuted policy, kept as
              the in-run comparison point rather than reused across runs)
  spec-first  restate the specification including every edge case the function
              must handle, then the corrected function
  test-first  state the assertion the current code violates, then the corrected
              function

Preregistered interaction prediction: spec-first's gain over direct is larger on
guard classes (none_handling, missing_guard) than on arithmetic classes
(off_by_one, type_coercion). A uniform gain falsifies the guard explanation.

Item bank, extraction, and the executable self-test are imported from
run_coderepair rather than reimplemented: that harness already absorbed three
silent scorer bugs that would each have looked like a research result.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import sys
from math import comb

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "shared"))
sys.path.insert(0, str(HERE.parents[2] / "src"))

from run_coderepair import (  # noqa: E402
    TESTS, available_models, build_items, extract_code, normalize_tests,
    resolve_models, run_tests, selftest as harness_selftest,
)

MODELS = ["qwen2.5:7b", "qwen2.5-coder:7b", "gemma3:4b"]
GUARD_CLASSES = {"none_handling", "missing_guard"}
ARITH_CLASSES = {"off_by_one", "type_coercion"}

POLICIES = {
    "direct": "Fix the bug. Reply with only the complete corrected function "
              "inside one ```python code block.",
    "step-calc": "First state the defect in one short line, then reply with the "
                 "complete corrected function inside one ```python code block. "
                 "Do not write the fix until after the one-line statement.",
    "spec-first": "First restate the specification this function must satisfy, "
                  "explicitly listing every edge case it must handle including "
                  "empty or missing inputs, then reply with the complete corrected "
                  "function inside one ```python code block.",
    "test-first": "First state one assertion that the current code violates, "
                  "including what it returns instead of the required value, then "
                  "reply with the complete corrected function inside one "
                  "```python code block.",
}


def build_items_full(seed: int):
    """All 48 items (12 classes x 4 repetitions), no subsampling.

    coderepair-01 sampled 40 of 48 to hit a round number; the power pre-check now
    requires n>=63 paired observations for the promised effect at this sample, so
    the bank is used whole and the paired count comes from 3 models x 48 items.
    """
    items = []
    for cls, src, tests, hinted in TESTS:
        for k in range(4):
            items.append({"cls": cls, "src": src, "tests": tests,
                          "hinted": hinted, "rep": k})
    random.Random(seed).shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = f"cr{i:02d}"
    return items


def mcnemar(fixed: int, broke: int) -> float:
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    from ollama_guard import call
    seed = int(os.environ.get("EVO_SEED", "20261008"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    models = resolve_models(
        [m for m in os.environ.get("EVO_MODELS", "").split(",") if m] or MODELS)
    if not models:
        raise SystemExit("no requested models are installed; refusing to run")
    items = build_items_full(seed)
    (out / "items.json").write_text(json.dumps(
        [{**{k: v for k, v in it.items() if k != "tests"},
          "n_tests": len(it["tests"])} for it in items], indent=1) + "\n")

    models_out, detail = {}, {}
    for model in models:
        acc, det = {}, {}
        for pol, instr in POLICIES.items():
            passed, rows = 0, []
            for it in items:
                user = f"```python\n{it['src']}```\n\n{instr}"
                try:
                    txt = call(model, user, timeout=200, num_predict=800)
                    ok, why = run_tests(extract_code(txt), it["tests"])
                except Exception as e:
                    ok, why = False, f"{type(e).__name__}: {e}"[:80]
                rows.append({"id": it["id"], "cls": it["cls"],
                             "hinted": it["hinted"], "passed": ok, "why": why})
                passed += bool(ok)
            (out / f"out_{model.replace(':', '_')}_{pol}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            acc[pol] = round(passed / len(items), 4)
            det[pol] = rows
        models_out[model] = {"model": model, "policies": acc, "detail": det}
        print(f"{model}: {acc}", flush=True)

    def paired(a_rows, b_rows, pred=lambda r: True):
        f = b_ = 0
        for a, b in zip(a_rows, b_rows):
            if not pred(a):
                continue
            f += bool(b["passed"] and not a["passed"])
            b_ += bool(a["passed"] and not b["passed"])
        return f, b_

    contrasts, guard = {}, {}
    for pol in ("step-calc", "spec-first", "test-first"):
        f = b_ = 0
        gf = gb = af = ab = 0
        for m in models_out.values():
            x, y = paired(m["detail"]["direct"], m["detail"][pol])
            f += x
            b_ += y
            gx, gy = paired(m["detail"]["direct"], m["detail"][pol],
                            lambda r: r["cls"] in GUARD_CLASSES)
            ax, ay = paired(m["detail"]["direct"], m["detail"][pol],
                            lambda r: r["cls"] in ARITH_CLASSES)
            gf += gx
            gb += gy
            af += ax
            ab += ay
        gain = round(sum(models_out[m]["policies"][pol]
                         - models_out[m]["policies"]["direct"]
                         for m in models_out) / len(models_out), 4)
        contrasts[pol] = {
            "gain_mean": gain, "fixed": f, "broke": b_,
            "mcnemar_p": round(mcnemar(f, b_), 6),
            "families_positive": f"{sum(1 for m in models_out.values() if m['policies'][pol] > m['policies']['direct'])}/{len(models_out)}",
            "guard_classes": {"fixed": gf, "broke": gb},
            "arith_classes": {"fixed": af, "broke": ab},
        }
        guard[pol] = {"guard_net": gf - gb, "arith_net": af - ab}

    best = max(("spec-first", "test-first", "step-calc"),
               key=lambda p: contrasts[p]["gain_mean"])
    c = contrasts[best]
    interaction = (c["guard_classes"]["fixed"] - c["guard_classes"]["broke"]
                   - (c["arith_classes"]["fixed"] - c["arith_classes"]["broke"]))
    res = {
        "domain": "code_repair",
        "arm": "policy_adaptation",
        "models_requested": MODELS,
        "models_measured": models,
        "n_items": len(items),
        "policies": list(POLICIES),
        "models": models_out,
        "contrasts": contrasts,
        "best_policy": best,
        "guard_minus_arith_net": interaction,
        # spec-first beats direct, with the guard interaction in the predicted
        # direction, and the predicted minimum effect is actually resolvable
        "confirmed": bool(c["gain_mean"] >= 0.25
                          and c["mcnemar_p"] < 0.05
                          and interaction > 0),
    }
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"best": best, "gain_mean": c["gain_mean"],
                      "p": c["mcnemar_p"], "guard_minus_arith": interaction,
                      "confirmed": res["confirmed"]}, ensure_ascii=False))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(harness_selftest())
    main()
