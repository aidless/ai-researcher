"""Cross-model transfer: does step-calc (established on qwen2.5:7b) transfer?

Reads EVO_MODELS (comma-separated, default qwen2.5:7b). For each model, runs
heldout40 under [direct, step-calc] via local ollama, exact float match.
Writes artifacts/result.json with per-model accuracy, gain, and the paired
contingency table (b = step-only wins, c = direct-only wins) for McNemar.

Must run with cwd=/tmp/ind-audit/gsm8k-self-evolve (the evaluator reads
examples/prompts/ relative to cwd). Output dir from EVO_OUT.
"""
import json
import math
import os
import pathlib
import random
import sys

sys.path.insert(0, "/tmp/ind-audit/gsm8k-self-evolve/examples")
import gsm8k_evaluator


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided binomial p-value for McNemar's test (b vs c discordants)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def bh_correct(pvals: list) -> list:
    """Benjamini-Hochberg adjusted p-values, same order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 1.0
    for rank, i in enumerate(reversed(order), 1):
        prev = min(prev, pvals[i] * m / (m - rank + 1))
        adj[i] = min(1.0, prev)
    return adj


def bootstrap_gain_ci(d_flags: list, s_flags: list, seed: int,
                      B: int = 5000) -> list:
    """95% bootstrap CI for (step-calc acc minus direct acc), paired resampling."""
    rng = random.Random(seed)
    n = len(d_flags)
    diffs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(s_flags[i] for i in idx) / n
                     - sum(d_flags[i] for i in idx) / n)
    diffs.sort()
    return [round(diffs[int(0.025 * B)], 4), round(diffs[int(0.975 * B)], 4)]

MODELS = [m.strip() for m in
          os.environ.get("EVO_MODELS",
                         os.environ.get("EVO_MODEL", "qwen2.5:7b")).split(",")]
out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
out.mkdir(parents=True, exist_ok=True)
cases = json.load(open("/tmp/ind-audit/gsm8k-self-evolve/examples/heldout40.json"))["cases"]
limit = int(os.environ.get("EVO_LIMIT", "0")) or len(cases)
cases = cases[:limit]

res = {"models": {}, "n": len(cases)}
for model in MODELS:
    gsm8k_evaluator.MODEL = model
    pol_res = {}
    for pol in ("direct", "step-calc"):
        detail = []
        for c in cases:
            try:
                raw, lat = gsm8k_evaluator.call_model(
                    gsm8k_evaluator.PROMPTS[pol].format(q=c["input"]))
                got = gsm8k_evaluator.extract_number(raw, pol)
                passed = got is not None and got == float(c["expected"])
            except Exception:
                passed, lat, got = False, 0.0, None
            detail.append({"id": c["id"], "passed": passed,
                           "lat": round(lat, 2)})
        pol_res[pol] = {"acc": sum(d["passed"] for d in detail) / len(detail),
                        "detail": detail}
    d_d, d_s = pol_res["direct"]["detail"], pol_res["step-calc"]["detail"]
    b = sum(1 for a, z in zip(d_d, d_s) if not a["passed"] and z["passed"])
    c_ = sum(1 for a, z in zip(d_d, d_s) if a["passed"] and not z["passed"])
    gain = pol_res["step-calc"]["acc"] - pol_res["direct"]["acc"]
    p_raw = mcnemar_exact(b, c_)
    d_flags = [1 if a["passed"] else 0 for a in d_d]
    s_flags = [1 if z["passed"] else 0 for z in d_s]
    seed = int(os.environ.get("EVO_SEED", "0")) or 20261006
    ci = bootstrap_gain_ci(d_flags, s_flags, seed)
    res["models"][model] = {"model": model, "policies": pol_res,
                            "gain": gain, "gain_ci95": ci, "p_raw": round(p_raw, 6),
                            "paired": {"b_step_only": b, "c_direct_only": c_}}

q = res["models"].get("qwen2.5:7b", {})
l_ = res["models"].get("llama3.1:8b")
# BH across models: the ledger reads p_bh, never p_raw.
raws = [res["models"][m].get("p_raw", 1.0) for m in MODELS if m in res["models"]]
adjs = bh_correct(raws)
for m, pa in zip([x for x in MODELS if x in res["models"]], adjs):
    res["models"][m]["p_bh"] = round(pa, 6)
res["replication_gain"] = q.get("gain")
res["transfer_gain"] = (l_ or {}).get("gain")
res["gain"] = res["transfer_gain"] if res["transfer_gain"] is not None else res["replication_gain"]
(out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps({"replication_gain": res["replication_gain"],
                  "transfer_gain": res["transfer_gain"],
                  "gain": res["gain"]}))
