"""P1 prompt ablation: is the transfer effect robust to wording, or is it one prompt's accident?

The devil never asked this directly, but every reviewer thinks it: step-calc is
ONE wording ("First write the arithmetic step by step, one operation per line,
with no explanation. Then write the final line as '#### <number>'"). If the
entire effect lives or dies on that exact phrasing, it is a prompt artifact
rather than a policy effect, and the paper's central claim is mislabeled.

Design: the canonical step-calc plus three pre-specified variants, all on a
fixed 80-item subset of confirm160 (first 80 by id, fixed before running), three
models that exist locally. Direct is the common control.

  v0-canonical  the exact step-calc wording from the confirmation arms
  v1-terse      "Show your work, then give the final answer after ####."
  v2-verbose    "Think carefully about this problem. Work through it gradually, "
                "explaining each calculation, and conclude with #### followed by "
                "the final number."
  v3-numbers    "Output only a sequence of equations, one per line, ending with "
                "#### <number>. No words."

Preregistered prediction: all three variants beat direct (the effect is the
policy, not the phrasing), with no predicted ordering among variants. If any
variant fails while others succeed, the effect is wording-sensitive and the
paper's claim narrows to the canonical phrasing.

Kill-switch keys on fields this harness writes (checked against the emit
contract before approval). Power: 80 items x 3 models = 240 paired observations
per contrast, against required n=63 for mde 0.25.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from math import comb

HERE = pathlib.Path(__file__).resolve().parent


def _repo_root(start: pathlib.Path) -> pathlib.Path:
    d = start.resolve()
    for cand in [d, *d.parents]:
        if (cand / "src" / "ai_researcher").is_dir():
            return cand
    raise SystemExit(f"no repository root above {start}")


REPO = _repo_root(HERE)
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "demo" / "shared"))
sys.path.insert(0, str(REPO / "demo" / "transfer"))

from run_confirmation import (  # noqa: E402
    ITEMS, PROMPTS, available_models, extract_number, mcnemar,
)
from ollama_guard import call  # noqa: E402

MODELS = ["qwen2.5:7b", "gemma3:4b", "llama3.1:8b"]
N_ITEMS = 80

VARIANTS = {
    "v0-canonical": PROMPTS["step-calc"],
    "v1-terse": ("Question: {q}\nShow your work, then give the final answer "
                 "after ####."),
    "v2-verbose": ("Question: {q}\nThink carefully about this problem. Work "
                   "through it gradually, explaining each calculation, and "
                   "conclude with #### followed by the final number."),
    "v3-numbers": ("Question: {q}\nOutput only a sequence of equations, one per "
                   "line, ending with #### <number>. No words."),
}


def selftest() -> int:
    problems = []
    bank = json.loads(ITEMS.read_text(encoding="utf-8"))["cases"]
    if len(bank) < N_ITEMS:
        problems.append(f"bank has {len(bank)} items, need {N_ITEMS}")
    ids = [c["id"] for c in bank[:N_ITEMS]]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids in subset")
    if set(VARIANTS) != {"v0-canonical", "v1-terse", "v2-verbose", "v3-numbers"}:
        problems.append("variant set changed without updating the preregistration")
    for p in problems:
        print(f"  [SELFTEST FAIL] {p}")
    if not problems:
        print(f"  [SELFTEST OK] {N_ITEMS}-item subset, 4 variants, "
              f"canonical matches confirmation wording: "
              f"{VARIANTS['v0-canonical'] == PROMPTS['step-calc']}")
    return 1 if problems else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if selftest():
        return 1
    seed = int(os.environ.get("EVO_SEED", "20261011"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    requested = [m.strip() for m in
                 os.environ.get("EVO_MODELS", ",".join(MODELS)).split(",") if m.strip()]
    have = available_models()
    models = [m for m in requested if m in have]
    dropped = [m for m in requested if m not in have]
    if dropped:
        print(f"[preflight] not installed, excluded: {dropped}")
    if not models:
        print("no requested models installed; refusing to run")
        return 1
    cases = json.loads(ITEMS.read_text(encoding="utf-8"))["cases"][:N_ITEMS]
    (out / "items.json").write_text(json.dumps(
        [{"id": c["id"], "expected": c["expected"]} for c in cases], indent=1) + "\n")

    direct_acc, var_acc, detail = {}, {}, {}
    for model in models:
        base = []
        for c in cases:
            try:
                txt = call(model, PROMPTS["direct"].format(q=c["input"]),
                           timeout=180, num_predict=400)
                got = extract_number(txt, "direct")
                ok = got is not None and abs(got - float(c["expected"])) < 1e-6
            except Exception:
                ok = False
            base.append(ok)
        direct_acc[model] = round(sum(base) / len(base), 4)
        detail[model] = {"direct": base}
        print(f"{model} direct: {direct_acc[model]:.4f}", flush=True)
        for vname, tmpl in VARIANTS.items():
            rows = []
            for c in cases:
                try:
                    key = "step-calc" if "####" in tmpl else "direct"
                    txt = call(model, tmpl.format(q=c["input"]),
                               timeout=180, num_predict=400)
                    got = extract_number(txt, key)
                    ok = got is not None and abs(got - float(c["expected"])) < 1e-6
                except Exception:
                    ok = False
                rows.append(ok)
            (out / f"out_{model.replace(':', '_')}_{vname}.jsonl").write_text(
                "".join(json.dumps({"passed": bool(x)}) + "\n" for x in rows),
                encoding="utf-8")
            var_acc.setdefault(vname, {})[model] = round(sum(rows) / len(rows), 4)
            detail[model][vname] = rows
            print(f"{model} {vname}: {var_acc[vname][model]:.4f}", flush=True)

    contrasts = {}
    for vname in VARIANTS:
        f = b_ = 0
        gains = {}
        for m in models:
            a, b = detail[m]["direct"], detail[m][vname]
            fx = sum(1 for x, y in zip(a, b) if y and not x)
            br = sum(1 for x, y in zip(a, b) if x and not y)
            f += fx
            b_ += br
            gains[m] = round(sum(b) / len(b) - sum(a) / len(a), 4)
        npos = sum(1 for g in gains.values() if g > 0)
        contrasts[vname] = {
            "gain_mean": round(sum(gains.values()) / len(gains), 4),
            "gains": gains, "fixed": f, "broke": b_,
            "mcnemar_p": round(mcnemar(f, b_), 6),
            "families_positive": f"{npos}/{len(models)}",
        }
    beats = {v: c["gain_mean"] > 0 and c["mcnemar_p"] < 0.05
             for v, c in contrasts.items()}
    res = {"domain": "arithmetic", "arm": "prompt_ablation",
           "models_requested": MODELS, "models_measured": models,
           "n_items": N_ITEMS, "variants": list(VARIANTS),
           "direct_acc": direct_acc, "variant_acc": var_acc,
           "contrasts": contrasts,
           "all_variants_beat_direct": bool(all(beats.values())),
           "confirmed": bool(all(beats.values())),
           "_config": {"n_items": N_ITEMS, "models": len(models),
                       "variants": len(VARIANTS)},
           "measurable": True}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n",
                                     encoding="utf-8")
    print(json.dumps({"contrasts": {k: {"gain": v["gain_mean"], "p": v["mcnemar_p"],
                                        "fam": v["families_positive"]}
                                    for k, v in contrasts.items()},
                      "confirmed": res["confirmed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
