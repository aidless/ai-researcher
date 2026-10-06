"""Swarm-size pilot: does evaluator bias scale with parallel subagents?

Kimi runs 100-300 subagent swarms with no measurement of evaluator bias at
swarm scale. This pilot tests the direction on local models: 1 vs 4 parallel
executors, single evaluator, same tasks. If per-round PCI rises faster with
more parallel executors (more outputs to cherry-pick from), bias amplifies.
If flat, swarm diversity cancels it.

Design: executor qwen2.5:7b, evaluator qwen2.5:7b (self, holds evaluator fixed
so only swarm size varies), 4 strategies, 4 tasks, 6 rounds. Two arms:
swarm=1 (sequential single executor) vs swarm=4 (4 parallel executors, best
output by evaluator vote advances). Metric: PCI trajectory slope per arm.

Writes artifacts/result.json {arms, slopes, verdict}.
~48 local calls. Deterministic seeds.
"""
import json
import math
import os
import pathlib
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OLLAMA = "http://127.0.0.1:11434/api/generate"
EXECUTOR = "qwen2.5:7b"
JUDGE = "qwen2.5:7b"
STRATEGIES = {
    "step_by_step": "逐步推理，每步显式写出",
    "critical_check": "先答后审，指出漏洞并修正",
    "evidence_cite": "引用具体知识依据",
    "counterfactual": "考虑反例和边界情况",
}
TASKS = [
    "1+2*3等于？", "Python中5//2的结果？", "二分查找的时间复杂度？",
    "8枚硬币1枚假币更轻，天平最少称几次？",
]
ROUNDS = int(os.environ.get("EVO_ROUNDS", "6"))
SEED = int(os.environ.get("EVO_SEED", "20261006"))


def llm(model, system, user, timeout=120):
    body = json.dumps({"model": model, "system": system or " ",
                       "prompt": user or " ", "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def judge(question, out_a, out_b):
    p = (f"问题：{question}\n回答A：{out_a[:300]}\n回答B：{out_b[:300]}\n"
         f"哪个回答更好？只回答 A 或 B。")
    try:
        r = llm(JUDGE, "你是严格的评审员。", p).strip().upper()
        return "A" if "A" in r[:10] else "B"
    except Exception:
        return "B"


def pci(w):
    vals = list(w.values())
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / len(vals)
    return math.sqrt(var) / mu if mu > 1e-10 else 0.0


def gen_one(args):
    strategy, task_q = args
    try:
        return llm(EXECUTOR, f"你是专家AI助手。策略：{STRATEGIES[strategy]}", task_q)
    except Exception:
        return ""


def run_arm(swarm, seed):
    rng = random.Random(seed)
    weights = {k: 1.0 / len(STRATEGIES) for k in STRATEGIES}
    traj = [round(pci(weights), 4)]
    for rnd in range(ROUNDS):
        task_q = TASKS[rnd % len(TASKS)]
        cands = []
        with ThreadPoolExecutor(max_workers=swarm) as ex:
            futs = []
            for _ in range(swarm):
                rv = rng.random() * sum(weights.values())
                cu, s = 0.0, "step_by_step"
                for k, v in weights.items():
                    cu += v
                    if rv <= cu:
                        s = k
                        break
                futs.append((s, ex.submit(gen_one, (s, task_q))))
            for s, f in futs:
                try:
                    cands.append((s, f.result(timeout=150)))
                except Exception:
                    pass
        if not cands:
            traj.append(traj[-1])
            continue
        # evaluator picks the best; its strategy gets the update
        best_s, best_o = cands[0]
        for s, o in cands[1:]:
            if judge(task_q, o, best_o) == "A":
                best_s, best_o = s, o
        weights[best_s] = max(0.01, weights[best_s] + 0.08)
        # losers decay slightly (renormalized implicitly by PCI)
        for k in weights:
            if k != best_s:
                weights[k] = max(0.01, weights[k] - 0.01)
        traj.append(round(pci(weights), 4))
    slope = round((traj[-1] - traj[0]) / ROUNDS, 4)
    return {"swarm": swarm, "pci_trajectory": traj, "slope": slope}


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    a1 = run_arm(1, SEED)
    a4 = run_arm(4, SEED + 1)
    res = {"arms": {"swarm1": a1, "swarm4": a4},
           "slope_excess": round(a4["slope"] - a1["slope"], 4),
           "confirmed": (a4["slope"] - a1["slope"]) >= 0.01,
           "seed": SEED}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"swarm1_slope": a1["slope"], "swarm4_slope": a4["slope"],
                      "confirmed": res["confirmed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
