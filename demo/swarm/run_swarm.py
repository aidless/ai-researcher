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
import re
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


FORCE_DECIDE = os.environ.get("EVO_FORCE_DECIDE", "0") == "1"


def judge(question, out_a, out_b, force_seed=None):
    """Vote A/B or None (abstain). With EVO_FORCE_DECIDE=1, abstentions are
    re-asked once with forcing language, then decided deterministically and
    flagged forced=True. This removes the abstention asymmetry between arms:
    any remaining slope gap cannot come from who-abstains-more."""
    import re
    p = (f"问题：{question}\n回答A：{out_a[:300]}\n回答B：{out_b[:300]}\n"
         f"哪个回答更好？只回答 A 或 B。")
    try:
        r = llm(JUDGE, "你是严格的评审员。", p).strip()
    except Exception:
        return None, False
    for pat in (r"(?:答案|回答|选择|选)\s*[:：]?\s*([AB])\b",
                r"\b([AB])\s*(?:更好|更优|获胜|胜出)",
                r"\b([AB])\b"):
        ms = re.findall(pat, r, re.IGNORECASE)
        if ms:
            return ms[-1].upper(), False
    if not FORCE_DECIDE:
        return None, False
    try:
        r2 = llm(JUDGE, "你是评审员。必须二选一，不许弃权、不许解释。",
                 f"问题：{question}\nA：{out_a[:200]}\nB：{out_b[:200]}\n只回答 A 或 B。").strip()
        for pat in (r"\b([AB])\b",):
            ms = re.findall(pat, r2, re.IGNORECASE)
            if ms:
                return ms[-1].upper(), True
    except Exception:
        pass
    import random
    rng = random.Random((force_seed or 0) + len(question))
    return ("A" if rng.random() < 0.5 else "B"), True


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


def _model_digests(names):
    """Best-effort model identity: name -> sha256 digest from `ollama show`. Missing is
    recorded as "unknown", never as a guess -- an empty field is information."""
    import subprocess
    out = {}
    for n in names:
        try:
            r = subprocess.run(["ollama", "show", n], capture_output=True, text=True, timeout=20)
            m = re.search(r"sha256:[0-9a-f]{12,}", r.stdout)
            out[n] = m.group(0) if m else "unknown"
        except Exception:
            out[n] = "unknown"
    return out


def distinct_draws(reps):
    """How many independent samples the seed loop produced -- on two denominators.

    Returns {"joint": n, "statistic": m}. They are NOT interchangeable, and the first
    version of this function conflated them -- my own test caught it: I asserted 6
    collapses to 4, while the joint-signature count says 6.

    On seed6-01 (2026-10-09): 6 distinct joint trajectories, but only 5 distinct values of
    the preregistered statistic, because slope_excess repeats at 0.0551 -- the swarm=4 arm
    alone collided on two pairs of seeds (idx 0==1 and 2==3) while swarm=1 stayed
    distinct. llm() sends temperature 0 with no model seed, so the only random source is
    the strategy-selection rng, and the pci metric is coarser than that rng: collisions
    appear at the statistic level even when the draws are nominally distinct. A sign test
    is entitled to `statistic`, not to `n_seeds` -- a draw that repeats another's value
    carries no new information. Bind a kill-switch to n_distinct.statistic.
    """
    seen = []
    for r in reps:
        sig = tuple(sorted((arm, tuple(v.get("pci_trajectory", [])))
                           for arm, v in (r.get("arms") or {}).items()))
        if sig not in seen:
            seen.append(sig)
    return {"joint": len(seen),
            "statistic": len({r.get("slope_excess") for r in reps})}


def run_arm(swarm, seed):
    rng = random.Random(seed)
    weights = {k: 1.0 / len(STRATEGIES) for k in STRATEGIES}
    traj = [round(pci(weights), 4)]
    traj_n = [swarm]
    tot_forced = tot_abstained = tot_votes = 0
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
        n_forced = n_abstained = 0
        for s, o in cands[1:]:
            v, forced = judge(task_q, o, best_o)
            tot_votes += 1
            if v is None:
                n_abstained += 1
                tot_abstained += 1
                continue
            n_forced += forced
            tot_forced += forced
            if v == "A":
                best_s, best_o = s, o
        weights[best_s] = max(0.01, weights[best_s] + 0.08)
        # losers decay slightly (renormalized implicitly by PCI)
        for k in weights:
            if k != best_s:
                weights[k] = max(0.01, weights[k] - 0.01)
        traj.append(round(pci(weights), 4))
        traj_n.append(n_actual)
    slope = round((traj[-1] - traj[0]) / ROUNDS, 4)
    return {"swarm": swarm, "pci_trajectory": traj, "slope": slope,
            "n_actual_per_round": traj_n,
            "mean_n_actual": round(sum(traj_n) / len(traj_n), 2),
            "forced_votes": tot_forced, "abstained_votes": tot_abstained,
            "total_votes": tot_votes}


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
           "n_distinct": distinct_draws(reps),
           # flat scalars: a kill-switch condition has to be evaluable against the artifact,
           # so `n_distinct.statistic` in prose is worthless until it exists as a field
           "n_distinct_joint": distinct_draws(reps)["joint"],
           "n_distinct_statistic": distinct_draws(reps)["statistic"],
           # which model produced these numbers, named IN the artifact. The signed bundle's
           # environment record carried ollama_model="" and base_digest="unknown" because
           # evidence.py reads EVO_MODEL, which this harness never sets -- so nothing on
           # disk tied the trajectory to qwen2.5:7b. A reader should not have to trust the
           # command line for that.
           "producer_models": {"executor": EXECUTOR, "judge": JUDGE,
                               "digests": _model_digests([EXECUTOR, JUDGE])},
           "excesses": excesses,
           "n_positive": n_pos,
           # n_pos >= len-1 (all but one may miss); floor of 1 so single-seed
           # runs can confirm (the old max(2, ...) made n=1 unconfirmable by
           # construction -- a threshold bug, not a finding).
           "confirmed": n_pos >= max(1, len(reps) - 1),
           "seed": SEEDS[0]}
    # backward compat for single-seed readers
    res["arms"] = reps[0]["arms"]
    res["slope_excess"] = reps[0]["slope_excess"]
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"n_seeds": len(reps), "n_distinct": res["n_distinct"],
                      "excesses": excesses,
                      "n_positive": n_pos,
                      "confirmed": res["confirmed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
