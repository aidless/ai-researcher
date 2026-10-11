"""Prospective confirmation of the paper's only surviving effect.

The arithmetic transfer result is the one primary endpoint that survives
project-level BH (2 of 8). It was measured on heldout40, and matrix-01's verdict
was analyst-assigned because its preregistered kill-switch keyed on a field the
harness never emitted -- so the preregistration never ran. This arm is the
prospective version: a fresh disjoint item set, a seed fixed before execution, and
a kill-switch on fields this harness actually writes.

Differences from matrix-01, all deliberate:
  * items: demo/transfer/items/confirm160.json (160 items, verified disjoint from
    heldout40 by build_confirm_set.py), not the 40 items that produced the result
  * n: 160 items x 2 models = 320 paired observations, against required_n = 157
    for a 0.10 effect at alpha=0.05, power=0.8
  * infrastructure: ollama_guard (exclusive lock, error-text and truncation
    rejection) and a model preflight, so a missing tag cannot be scored as a zero
  * self-contained: reads data/gsm8k/test.jsonl provenance from the item file and
    imports nothing from /tmp, which is where the original harness kept its bank
    and scorer

Emits `confirmed` -- the field matrix-01's kill-switch wanted and never produced.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import re
import sys
from math import comb

# __file__ must NOT be passed through resolve(): this working tree's
# absolute path contains a literal backslash (F:\deepseek), and resolve()
# doubles it, so every derived path then fails an existence check on a
# file that is present. Read __file__ as-is and build paths from that.
_HERE_RAW = pathlib.Path(__file__)
HERE = _HERE_RAW.parent
from ai_researcher import canonical
ROOT = pathlib.Path(canonical.repo_root())
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "demo/shared"))

from ollama_guard import call  # noqa: E402

ITEMS = pathlib.Path(canonical.join("demo", "transfer", "items", "confirm160.json"))
NUM = re.compile(r"-?\d[\d,]*\.?\d*")
MODELS = ["qwen2.5:7b", "gemma3:4b"]

PROMPTS = {
    "direct": ("Question: {q}\nAnswer the question with a single number and "
               "nothing else."),
    "step-calc": ("Question: {q}\nFirst write the arithmetic step by step, one "
                  "operation per line, with no explanation. Then write the final "
                  "line as '#### <number>'."),
}


def available_models() -> set:
    import urllib.request
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=15) as r:
        return {m["name"] for m in json.loads(r.read().decode()).get("models", [])}


def extract_number(text: str, pol: str):
    if pol == "step-calc" and "####" in text:
        m = NUM.search(text.split("####")[-1].replace(",", ""))
    else:
        # last number in the reply: a direct answer ends with its number, and a
        # step-calc reply's trailing number is the conclusion. Scanning for the
        # FIRST number instead was a measurement bug in an earlier arm -- it read
        # the first intermediate value as the answer.
        found = NUM.findall((text or "").replace(",", ""))
        m = None
        if found:
            class _M:
                @staticmethod
                def group(_i):
                    return found[-1]
            m = _M
    if not m:
        return None
    try:
        return float(m.group(0).rstrip("."))
    except (ValueError, AttributeError, IndexError):
        return None


def mcnemar(fixed: int, broke: int) -> float:
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def selftest() -> int:
    """Known-good and known-bad replies must be scored correctly."""
    problems = []
    cases = [
        ("The answer is 42", "direct", 42.0),
        ("step 1: 3+4=7\nstep 2: 7*2=14\n#### 14", "step-calc", 14.0),
        ("First 5 apples, then 6 more, so 11 total.\n#### 11", "step-calc", 11.0),
        ("I cannot answer that.", "direct", None),
        ("", "direct", None),
    ]
    for text, pol, want in cases:
        got = extract_number(text, pol)
        if got != want:
            problems.append(f"extract_number({text[:28]!r}, {pol}) = {got}, want {want}")
    if not ITEMS.exists():
        problems.append(f"missing item bank: {ITEMS}")
    else:
        d = json.loads(ITEMS.read_text(encoding="utf-8"))
        casesd = d.get("cases", [])
        if len(casesd) < 160:
            problems.append(f"item bank has {len(casesd)} items, expected >= 160")
        if len({c["id"] for c in casesd}) != len(casesd):
            problems.append("duplicate item ids")
        if not d.get("provenance", {}).get("verified_disjoint"):
            problems.append("item bank does not assert verified disjointness")
        for p in problems:
            print(f"  [SELFTEST FAIL] {p}")
        if not problems:
            print(f"  [SELFTEST OK] {len(casesd)} items, disjointness asserted, "
                  f"{len(cases)} extraction cases")
        return 1 if problems else 0
    for p in problems:
        print(f"  [SELFTEST FAIL] {p}")
    return 1 if problems else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if selftest():
        print("refusing to run: the scorer failed its own self-test")
        return 1
    seed = int(os.environ.get("EVO_SEED", "20261010"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    requested = [m.strip() for m in
                 os.environ.get("EVO_MODELS", ",".join(MODELS)).split(",") if m.strip()]
    have = available_models()
    models = [m for m in requested if m in have]
    dropped = [m for m in requested if m not in have]
    if dropped:
        # A tag that is not installed would otherwise be recorded as a model that
        # scored zero, which is how coderepair-01 produced a fake 0.00/0.00.
        print(f"[preflight] not installed, excluded before measurement: {dropped}")
    if not models:
        print("no requested models installed; refusing to run")
        return 1

    cases = json.loads(ITEMS.read_text(encoding="utf-8"))["cases"]
    limit = int(os.environ.get("EVO_LIMIT", "0")) or len(cases)
    cases = cases[:limit]
    res = {"models": {}, "n": len(cases), "seed": seed,
           "models_requested": requested, "models_measured": models,
           "item_bank": str(ITEMS.relative_to(ROOT))}

    fixed = broke = 0
    per_model = {}
    for model in models:
        pol_res, detail = {}, {}
        for pol, tmpl in PROMPTS.items():
            rows = []
            for c in cases:
                try:
                    txt = call(model, tmpl.format(q=c["input"]), timeout=180,
                               num_predict=400)
                    got = extract_number(txt, pol)
                    ok = got is not None and abs(got - float(c["expected"])) < 1e-6
                    why = "" if ok else f"got {got}"
                except Exception as e:
                    ok, why = False, f"{type(e).__name__}: {str(e)[:70]}"
                rows.append({"id": c["id"], "passed": ok, "why": why})
            (out / f"out_{model.replace(':', '_')}_{pol}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            pol_res[pol] = round(sum(r["passed"] for r in rows) / len(rows), 4)
            detail[pol] = rows
        f_ = b_ = 0
        for a, b in zip(detail["direct"], detail["step-calc"]):
            if b["passed"] and not a["passed"]:
                f_ += 1
            if a["passed"] and not b["passed"]:
                b_ += 1
        fixed += f_
        broke += b_
        gain = round(pol_res["step-calc"] - pol_res["direct"], 4)
        per_model[model] = {"policies": pol_res, "gain": gain,
                            "fixed": f_, "broke": b_,
                            "p": round(mcnemar(f_, b_), 6)}
        print(f"{model}: {pol_res} gain={gain}", flush=True)

    npos = sum(1 for v in per_model.values() if v["gain"] > 0)
    res["per_model"] = per_model
    res["gain_mean"] = round(sum(v["gain"] for v in per_model.values())
                             / len(per_model), 4)
    res["families_positive"] = f"{npos}/{len(per_model)}"
    res["mcnemar_pooled"] = {"fixed": fixed, "broke": broke,
                             "p": round(mcnemar(fixed, broke), 8)}
    res["paired_observations"] = len(cases) * len(models)
    res["confirmed"] = bool(npos == len(per_model)
                            and res["mcnemar_pooled"]["p"] < 0.05
                            and fixed > broke
                            and res["gain_mean"] >= 0.10)
    res["sign_test_p"] = round(0.5 ** len(per_model) if npos == len(per_model) else 1.0, 6)
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n",
                                     encoding="utf-8")
    print(json.dumps({"gain_mean": res["gain_mean"],
                      "families_positive": res["families_positive"],
                      "pooled": res["mcnemar_pooled"],
                      "paired_observations": res["paired_observations"],
                      "confirmed": res["confirmed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
