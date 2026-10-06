"""Small-model evaluator collapse: minimal TTRL protocol on local ollama.

Question: does evaluator-preference collapse occur in 7-8B local models, and is
it stronger under cross-family evaluation? The published phenomenon (MPCI=1.449
for GPT-4o-as-judge, ~3.2x self-eval) was established on frontier models. If it
replicates on small local models, it is about the protocol, not scale. If not,
the phenomenon is bounded by capability. Either answer is significant.

Design (preregistered):
  conditions: SELF (qwen2.5:7b judges qwen2.5:7b) vs CROSS (llama3.1:8b judges
              qwen2.5:7b executor)
  strategies (4): step_by_step, critical_check, evidence_cite, counterfactual
  tasks (8): verify/code/reasoning mixed, fixed order, fixed seed
  rounds: 8 per condition. Update: winner +0.08, loser -0.04 (same as published).
  metric: PCI of the weight distribution per round; collapse = PCI rises.
  claim: CROSS final PCI > SELF final PCI by >= 0.15 (preregistered threshold).

Writes artifacts/result.json {conditions, pci_trajectory, verdict}.
Deterministic seeds; model names pinned; temperature 0.
"""
import json
import math
import os
import pathlib
import random
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
EXECUTOR = "qwen2.5:7b"
SELF_JUDGE = "qwen2.5:7b"
CROSS_JUDGE = "llama3.1:8b"

STRATEGIES = {
    "step_by_step": "逐步推理，每步显式写出",
    "critical_check": "先答后审，指出漏洞并修正",
    "evidence_cite": "引用具体知识依据",
    "counterfactual": "考虑反例和边界情况",
}
TASKS = [
    ("1+2*3等于？", "7"),
    ("Python中5//2的结果？", "2"),
    ("二分查找的时间复杂度？", "log n"),
    ("8枚硬币1枚假币更轻，天平最少称几次？", "2"),
    ("写Python回文判断函数。", "def"),
    ("CAP定理是什么？", "一致性"),
    ("Docker容器和虚拟机的核心区别？", "内核"),
    ("3盏灯3个开关，如何确定对应关系？", "开关"),
]
ROUNDS = int(os.environ.get("EVO_ROUNDS", "8"))
SEED = int(os.environ.get("EVO_SEED", "20261006"))


def llm(model, system, user, timeout=120):
    body = json.dumps({"model": model, "system": system or " ",
                       "prompt": user or " ", "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def judge(judge_model, question, out_a, out_b):
    """Vote A/B or None (abstain). Never defaults: an error or ambiguous
    verdict abstains and the caller skips the update, because a default vote
    is a systematic bias, not noise."""
    import re
    p = (f"问题：{question}\n回答A：{out_a[:400]}\n回答B：{out_b[:400]}\n"
         f"哪个回答更好？只回答 A 或 B。")
    try:
        r = llm(judge_model, "你是严格的评审员。", p).strip()
    except Exception:
        return None
    # Prefer explicit verdict patterns, last occurrence wins (verdicts come last).
    # Bare-substring matching ("A" in r[:10]) misfires on "As an AI..." openers.
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


def run_condition(judge_model, seed):
    rng = random.Random(seed)
    weights = {k: 1.0 / len(STRATEGIES) for k in STRATEGIES}
    traj = [round(pci(weights), 4)]
    abstained = 0
    for rnd in range(ROUNDS):
        task_q, _ = TASKS[rnd % len(TASKS)]
        rv = rng.random() * sum(weights.values())
        cu, strategy = 0.0, "step_by_step"
        for k, v in weights.items():
            cu += v
            if rv <= cu:
                strategy = k
                break
        try:
            out = llm(EXECUTOR, f"你是专家AI助手。策略：{STRATEGIES[strategy]}", task_q)
            ctl = llm(EXECUTOR, "你是专家AI助手。策略：逐步推理。", task_q)
            winner = judge(judge_model, task_q, out, ctl)
            if winner is None:
                abstained += 1
                traj.append(traj[-1])
                continue
            weights[strategy] = max(0.01, weights[strategy] + (0.08 if winner == "A" else -0.04))
        except Exception:
            abstained += 1
            traj.append(traj[-1])
    return {"judge": judge_model, "pci_trajectory": traj,
            "pci_final": traj[-1], "pci_start": traj[0],
            "abstained": abstained}


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    self_r = run_condition(SELF_JUDGE, SEED)
    cross_r = run_condition(CROSS_JUDGE, SEED + 1)
    excess = cross_r["pci_final"] - self_r["pci_final"]
    res = {"executor": EXECUTOR, "rounds": ROUNDS, "seed": SEED,
           "self": self_r, "cross": cross_r,
           "cross_excess": round(excess, 4),
           "confirmed": excess >= 0.15,
           "n_tasks": len(TASKS), "n_strategies": len(STRATEGIES)}
    (out / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"self_final": self_r["pci_final"],
                      "cross_final": cross_r["pci_final"],
                      "excess": round(excess, 4),
                      "confirmed": res["confirmed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
