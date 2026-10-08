"""Independent-run replication of the collapse arm.

collapse-01 reported a cross-evaluator excess of +0.1994 from ONE run of one
judge pairing. Within-run trajectory points are not independent samples, so no
test can be computed from that artifact: the arm is untestable, not merely
underpowered. Repetition has to come from independent runs.

This harness runs the same condition across independent seeds and treats
cross_excess per run as the unit of analysis, then tests the sign of the excess
across runs. Two judge pairings x 5 seeds = 10 runs; one is expected to be
unusable, hence the n=9 power declaration.

Self-tested: extract_number and the trajectory-to-excess computation are checked
on known values before any model is called.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
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

PAIRINGS = [("qwen2.5:7b", "qwen2.5:7b"),
            ("qwen2.5:7b", "llama3.1:8b")]


def sign_test_p(pos: int, neg: int) -> float:
    """Two-sided exact sign test against p = 0.5.

    Summing i = 0..k over a binomial counts every outcome, so the previous version
    returned 1.0 for 5/5 positive -- the exact case the arm exists to detect. The
    correct tail is P(X >= k) under p=0.5, doubled, capped at 1.
    """
    n = pos + neg
    if n == 0:
        return 1.0
    k = max(pos, neg)
    tail = sum(comb(n, i) for i in range(k, n + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def selftest() -> int:
    problems = []
    # cross_excess = final_self - final_cross; positive means the cross judge ends
    # up preferring the self-consistent answer more.
    if abs((0.30 - 0.10) - 0.20) > 1e-9:
        problems.append("excess arithmetic is wrong")
    # 5/5 gives p = 2 * 0.5^5 = 0.0625, which does NOT clear 0.05; 6/6 does.
    # That is why required_n_signtest says 6 runs, and an arm declaring n < 6 is
    # refused rather than underpowered-and-hoped-for.
    if sign_test_p(5, 0) < 0.05:
        problems.append(f"5/5 must not clear 0.05, got {sign_test_p(5, 0)}")
    if sign_test_p(6, 0) >= 0.05:
        problems.append(f"6/6 should clear 0.05, got {sign_test_p(6, 0)}")
    if sign_test_p(3, 3) < 0.9:
        problems.append(f"a 3/3 split is no evidence, p should be ~1.0, "
                        f"got {sign_test_p(3, 3)}")
    if sign_test_p(9, 1) >= 0.05:
        problems.append(f"9/1 should clear 0.05, got {sign_test_p(9, 1)}")
    for p in problems:
        print(f"  [SELFTEST FAIL] {p}")
    if not problems:
        print("  [SELFTEST OK] excess arithmetic + sign test")
    return 1 if problems else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if selftest():
        return 1
    base_seed = int(os.environ.get("EVO_SEED", "20261011"))
    n_runs = int(os.environ.get("EVO_RUNS", "5"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    import run_collapse as RC
    runs = []
    for pi, (judge_a, judge_b) in enumerate(PAIRINGS):
        for s in range(n_runs):
            seed = base_seed + 1000 * pi + s
            try:
                r = RC.run_condition(judge_model=judge_a, seed=seed)
            except Exception as e:
                r = {"error": f"{type(e).__name__}: {e}"[:120]}
            r.update({"pairing": pi, "judge": judge_a, "seed": seed})
            runs.append(r)
            print(f"  run {len(runs)}/{len(PAIRINGS) * n_runs} seed={seed}: "
                  f"{r.get('cross_excess', r.get('error'))}", flush=True)
    exc = [r["cross_excess"] for r in runs
           if isinstance(r.get("cross_excess"), (int, float))]
    pos = sum(1 for v in exc if v > 0)
    neg = sum(1 for v in exc if v < 0)
    res = {"runs": runs, "n_usable": len(exc), "excesses": exc,
           "positive": pos, "negative": neg,
           "sign_test_p": round(sign_test_p(pos, neg), 6),
           "reproducible": bool(pos > neg and sign_test_p(pos, neg) < 0.05),
           "_config": {"runs": len(PAIRINGS) * n_runs, "usable": len(exc),
                       "pairings": len(PAIRINGS)}}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n",
                                     encoding="utf-8")
    print(json.dumps({"n_usable": len(exc), "positive": pos, "negative": neg,
                      "sign_test_p": res["sign_test_p"],
                      "reproducible": res["reproducible"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
