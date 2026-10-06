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
SEEDS = [int(x) for x in os.environ.get("EVO_SEEDS", str(SEED)).split(",")]


def llm(model, system, user, timeout=120):
    body = json.dumps({"model": model, "system": system or " ",
                       "prompt": user or " ", "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def judge(question, out_a, out_b):
    """Vote A/B or None (abstain). See run_collapse.py for why no defaults."""
    import re
    p = (f"问题：{question}\n回答A：{out_a[:300]}\n回答B：{out_b[:300]}\n"
         f"哪个回答更好？只回答 A 或 B。")
    try:
        r = llm(JUDGE, "你是严格的评审员。", p).strip()
    except Exception:
        return None
    for pat in (r"(?:答案|回答|选择|选)\s*[:：]?\s*([AB])\b",
                r"\b([AB])\s*(?:更好|更优|获胜|胜出)",
                r"\b([AB])\b"):
        ms = re.findall(pat, r, re.IGNORECASE)
        if ms:
            return ms[-1].upper()
    return None


def pci(w):
    vals = list(w.values())
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / len(vals)
    return math.sqrt(var) / mu if mu > 1e-10 else 0.0


def gen_one(args):
    strategy, task_q = args
    try:
        out = llm(EXECUTOR, f"你是专家AI助手。策略：{STRATEGIES[strategy]}", task_q)
        return out if out and out.strip() else None
    except Exception:
        return None


def run_arm(swarm, seed):
    rng = random.Random(seed)
    weights = {k: 1.0 / len(STRATEGIES) for k in STRATEGIES}
    traj = [round(pci(weights), 4)]
    traj_n = [swarm]
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
                    o = f.result(timeout=150)
                    if o is not None:
                        cands.append((s, o))
                except Exception:
                    pass
        n_actual = len(cands)
        if not cands:
            traj.append(traj[-1])
            traj_n.append(0)
            continue
        # evaluator picks the best; its strategy gets the update.
        # Abstentions keep the incumbent instead of voting: a default vote is
        # bias, not noise. n_actual records how many executors REALLY ran --
        # the swarm label must not lie about dropped futures.
        best_s, best_o = cands[0]
        for s, o in cands[1:]:
            v = judge(task_q, o, best_o)
            if v == "A":
                best_s, best_o = s, o
        weights[best_s] = max(0.01, weights[best_s] + 0.08)
        # losers decay slightly (renormalized implicitly by PCI)
        for k in weights:
            if k != best_s:
                weights[k] = max(0.01, weights[k] - 0.01)
        traj.append(round(pci(weights), 4))
        traj_n.append(n_actual)
        traj_n.append(n_actual)
    slope = round((traj[-1] - traj[0]) / ROUNDS, 4)
    return {"swarm": swarm, "pci_trajectory": traj, "slope": slope,
            "n_actual_per_round": traj_n,
            "mean_n_actual": round(sum(traj_n) / len(traj_n), 2)}


def run_all(seed):
    a1 = run_arm(1, seed)
    a4 = run_arm(4, seed + 1)
    return {"arms": {"swarm1": a1, "swarm4": a4},
            "slope_excess": round(a4["slope"] - a1["slope"], 4),
            "seed": seed}


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    reps = [run_all(sd) for sd in SEEDS]
    excesses = [r["slope_excess"] for r in reps]
    n_pos = sum(1 for e in excesses if e >= 0.01)
    res = {"reps": reps, "n_seeds": len(reps),
           "excesses": excesses,
           "n_positive": n_pos,
           "confirmed": n_pos >= max(2, len(reps) - 1),
           "seed": SEEDS[0]}
    # backward compat for single-seed readers
    res["arms"] = reps[0]["arms"]
    res["slope_excess"] = reps[0]["slope_excess"]
    res = {"arms": {"swarm1": a1, "swarm4": a4},
           "slope_excess": round(a4["slope"] - a1["slope"], 4),
           "confirmed": (a4["slope"] - a1["slope"]) >= 0.01,
           "seed": SEED}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"swarm1_slope": a1["slope"], "swarm4_slope": a4["slope"],
                      "confirmed": res["confirmed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
