"""Lineage capability curve: copilot-3b-lora v1..v3c on the 50-item eval.

Runs each checkpoint via local ollama through auditable's scorer, then compares
consecutive versions per reference-check type. Any regression (later version
worse than predecessor on any check type) sets any_regression=True.

Writes artifacts/result.json {versions, per_check_rates, regressions, verdict}.
~250 local calls. Deterministic seed.
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
VERSIONS = ["v1", "v2", "v3", "v3b", "v3c"]
MODEL_OF = {v: f"copilot-3b-lora-{v}:latest" if v != "v1" else "copilot-3b-lora:latest"
            for v in VERSIONS}
# v1 maps to the base tag; adjust if ollama list differs
TESTS = "/tmp/ind-audit/auditable-llm-eval/outputs/llm-lab/datasets/llm_lab_copilot/test_50.jsonl"
SCORER = "/tmp/ind-audit/auditable-llm-eval/copilot/score_copilot_run_v2.py"


def gen(model, prompt, timeout=150):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    tests = [json.loads(l) for l in open(TESTS, encoding="utf-8") if l.strip()]
    rates, details = {}, {}
    for v in VERSIONS:
        model = MODEL_OF[v]
        preds = []
        for t in tests:
            try:
                preds.append({"id": t["id"], "output": gen(model, t["prompt"])[:1500]})
            except Exception as e:
                preds.append({"id": t["id"], "output": "",
                              "error": type(e).__name__})
        pp, op, sp = out / f"pred_{v}.jsonl", out / f"out_{v}.jsonl", out / f"sum_{v}.json"
        pp.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n",
                      encoding="utf-8")
        r = subprocess.run([sys.executable, SCORER, "--tests", str(TESTS),
                            "--predictions", str(pp), "--out", str(op),
                            "--summary", str(sp)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not sp.exists():
            details[v] = {"error": (r.stderr or "")[:200]}
            rates[v] = None
            continue
        s = json.loads(sp.read_text(encoding="utf-8"))
        details[v] = s
        rates[v] = s.get("overall_reference_check_rate")
    regressions = []
    vs = [v for v in VERSIONS if rates.get(v) is not None]
    for a, b in zip(vs, vs[1:]):
        if rates[b] < rates[a]:
            regressions.append({"from": a, "to": b,
                                "drop": round(rates[a] - rates[b], 4)})
    res = {"versions": VERSIONS, "rates": rates,
           "any_regression": len(regressions) > 0,
           "regressions": regressions,
           "confirmed": len(regressions) > 0}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n",
                                      encoding="utf-8")
    print(json.dumps({"rates": rates, "any_regression": res["any_regression"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
