"""Cross-model transfer: does step-calc (established on qwen2.5:7b) transfer?

Reads EVO_MODELS (comma-separated, default qwen2.5:7b). For each model, runs
heldout40 under [direct, step-calc] via local ollama, exact float match.
Writes artifacts/result.json with per-model accuracy, gain, and the paired
contingency table (b = step-only wins, c = direct-only wins) for McNemar.

Must run with cwd=/tmp/ind-audit/gsm8k-self-evolve (the evaluator reads
examples/prompts/ relative to cwd). Output dir from EVO_OUT.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, "/tmp/ind-audit/gsm8k-self-evolve/examples")
import gsm8k_evaluator

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
    res["models"][model] = {"model": model, "policies": pol_res,
                            "gain": gain,
                            "paired": {"b_step_only": b, "c_direct_only": c_}}

q = res["models"].get("qwen2.5:7b", {})
l_ = res["models"].get("llama3.1:8b")
res["replication_gain"] = q.get("gain")
res["transfer_gain"] = (l_ or {}).get("gain")
res["gain"] = res["transfer_gain"] if res["transfer_gain"] is not None else res["replication_gain"]
(out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps({"replication_gain": res["replication_gain"],
                  "transfer_gain": res["transfer_gain"],
                  "gain": res["gain"]}))
