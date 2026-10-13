#!/usr/bin/env python3
"""AGI 候选臂 · 零机时可判定性定价板。

问的不是"要不要跑这一发"，而是"这一发跑完，它被要求判的那件事判不判得开"。
每个输入数由本脚本从载体文件现读（指不回载体的数不进算式）；算式全部走
~/.qoder-cn/skills/prebuild-testability-check 那台原件，判决表由它给，我不自己命名判决。
read_only=true，sim_machine_minutes=0，kaggle_writes=0。

用法：
    python3 scripts/agi_arm_price_board.py            # 出板
    python3 scripts/agi_arm_price_board.py --red      # 注入两处坏前提，看判决是否跟着变
"""
from __future__ import annotations

import glob
import importlib.util
import json
import math
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = ROOT.parent                                  # 工作区根（含 arc2 / gsm8k-self-evolve）
KERNEL = os.path.expanduser("~/.qoder-cn/skills/prebuild-testability-check/scripts/"
                            "prebuild_testability.py")
OUT = ROOT / "reports" / "agi_arm_price_board.json"
MD = ROOT / "reports" / "agi_arm_price_board.md"

Z90, Z80 = 1.645, 2.802          # 单侧 90% CI 半宽 / 双边 80% 功效（原件口径）


def load_kernel():
    spec = importlib.util.spec_from_file_location("ptk", KERNEL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wilson(k, n, z):
    """Binomial Wilson interval from counts -- derived here, not copied from prose,
    because the carriers publish a 95% interval and the kernel wants a 90% one.
    Mixing those two levels silently would be a caliber error, so the conversion is
    explicit and its inputs (k, n, z) are printed into the board."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 6), round(c + h, 6))


def se_p(p, n):
    return math.sqrt(max(p, 1e-12) * (1 - min(p, 1 - 1e-12)) / n) if n else None


def arc2_arm():
    d = json.loads((WORK / "arc2/out/marginal_gain.json").read_text(encoding="utf-8"))
    rows = d["rows"]
    last_row = rows[-1]
    plateau_start = next((i for i in range(1, len(rows))
                          if rows[i]["hold"]["solved"] == last_row["hold"]["solved"]), None)
    ref_row = rows[plateau_start] if plateau_start else rows[-2]
    n = last_row["hold"]["total"]
    p_ref = ref_row["hold"]["solved"] / n
    p_cand = last_row["hold"]["solved"] / n
    inc = round(p_cand - p_ref, 6)
    ci = wilson(ref_row["hold"]["solved"], n, Z90)
    sd = se_p(p_ref, n)
    return {
        "arm": "ARC2-MG", "question": "再加 DSL 族还有没有可判的收益",
        "currency": "solved-task fraction on the 259-task HOLD",
        "carriers": {"marginal_gain.json": d["probe"], "elapsed_sec": d["elapsed_sec"],
                     "plateau_from_row_k": ref_row["k"], "final_row_k": last_row["k"],
                     "hold_final": "%d/%d" % (last_row["hold"]["solved"], n),
                     "controls_oracle": d["controls"]["C_oracle"]["solved"]},
        "spec": {
            "mode": "escalation",
            "question": "ARC2-MG: does adding families past the plateau decide anything",
            "reference": {"mean": round(p_ref, 6), "ci90": list(ci),
                          "carrier": "arc2/out/marginal_gain.json rows[k=%d].hold" % ref_row["k"]},
            "candidate": {"arm": "families beyond k=%d" % ref_row["k"], "mean": inc, "sd": round(sd, 6),
                          "better_is": "higher",
                          "ci90": [round(inc - Z90 * sd, 6), round(inc + Z90 * sd, 6)]},
            "cost": {"reference_minutes": round(d["elapsed_sec"] / 60.0, 1),
                     "reference_cells": len(rows), "cells_per_trajectory": 1,
                     "currency": "probe wall-minutes (769.5 s for 13 rows)"},
            "limitations": ["sd 由载体计数用二项式公式现推（p=7/259,n=259），不是载体自带的逐题配对",
                            "族顺序是源码里声明的，不是实验选的（载体 caveats 原话），所以量的是曲线形状不是因果",
                            "增量为 0 的行数 = 4（k=9..12 solved 全 7/259），新族在这台仪器上不可见"],
        },
    }


def gsm_tpr_arm():
    p = WORK / "gsm8k-self-evolve/results/rounds/round5/ablation.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    leg = d["verdict"]["branch_i"]["clause_c_no_true_positive_loss"]
    audit_note = "scripts/audit_gate_rules.py 自述：TPR R1..R7=[1.0…] POSITIVE denominator = 1"
    return {
        "arm": "GSM-TPR", "question": "这条臂能不能给别的臂定升档线",
        "currency": "true-positive rate (no-TPR-loss clause)",
        "carriers": {"ablation.json": {k: leg[k] for k in leg if k.startswith("tpr")},
                     "denominator": 1},
        "spec": None,
        "self_verdict": "INSTRUMENT_GAP_reference_ci_has_zero_width_because_n_is_1",
        "why": ("三条 TPR 全是 1.0，而分母是 1：CI 宽度为 0 不是因为测得准，是因为只有一个正类样本。"
                "原件的 bar 规则只检查 bar>0，遇到这种退化 CI 会照样放行一个 bar —— 这是那台仪器的"
                "一个真实边界，本板不走它，改由本节直接判 GAP。"),
        "consequence": "gsm8k 这条线有资格给 FPR 腿定价（k_curve 带计数的 Wilson），但没资格给别的臂定升档线",
        "usable_instead": {"carrier": "ablation.json verdict…k_curve", "k": 8,
                           "fpr": 0.9825, "wilson95": [0.970840927975432, 0.9895474564860909]},
    }


def coderepair_arm():
    r = json.loads((ROOT / "demo/runs/coderepair-01/round-01/artifacts/result.json")
                   .read_text(encoding="utf-8"))
    st = json.loads((ROOT / "demo/runs/coderepair-01/state.json").read_text(encoding="utf-8"))
    env = json.loads((ROOT / "demo/runs/coderepair-01/round-01/envelope.json").read_text(encoding="utf-8"))
    import datetime as dt
    t0 = dt.datetime.fromisoformat(st["started_at"])
    t1 = dt.datetime.fromisoformat(env["envelope"]["payload"]["signed_at"])
    mins = round((t1 - t0).total_seconds() / 60.0, 2)
    gains = [v["policies"]["step-calc"] - v["policies"]["direct"] for v in r["models"].values()]
    n = len(gains)
    mean = sum(gains) / n
    sd = (sum((g - mean) ** 2 for g in gains) / (n - 1)) ** 0.5
    cells = sum(len(v["detail"]["direct"]) * 2 for v in r["models"].values())
    return {
        "arm": "AIR-CODEREPAIR", "question": "把 coderepair 的 n 从 40 题拉到 157 值不值",
        "currency": "paired accuracy delta, step-calc − direct (per model)",
        "carriers": {"result.json": {"n_items": r["n_items"], "models": n,
                                     "mcnemar_p": r["mcnemar_pooled"]["p"]},
                     "measured_cost": {"minutes": mins, "ollama_calls": cells,
                                       "throughput_calls_per_min": round(cells / mins, 1)}},
        "spec": {
            "mode": "escalation",
            "z": 2.802,
            "question": "AIR-CODEREPAIR: does n=157 decide the transfer claim",
            "reference": None,
            "candidate": {"arm": "coderepair-01", "mean": round(mean, 4), "sd": round(sd, 4),
                          "better_is": "higher",
                          "ci90": [round(mean - Z90 * sd / math.sqrt(n), 4),
                                   round(mean + Z90 * sd / math.sqrt(n), 4)]},
            "cost": {"reference_minutes": mins, "reference_cells": cells,
                     "cells_per_trajectory": 1,
                     "extrapolation": "n=157 时调用数 ≈ 157x2x%d=%.0f，按实测吞吐 %.1f 次/分线性外推 = %.1f 分钟（假设，非载体）"
                                      % (n, 157 * 2 * n, cells / mins, 157 * 2 * n / (cells / mins))},
            "limitations": ["sd 来自 4 个模型级的增益，不是 40 题的逐题配对：分母只有 4，保守方向未知",
                            "参照臂（能定 bar 的已 resolved 载体）盘上不存在 -> 本臂注定落 GAP",
                            "外推的分钟数是假设，不是载体；实测只有 320 次调用 5.0 分钟这一格"],
        },
    }


def not_carried():
    rows = []
    for arm, where in (("AGI-KIT", "工作区无本地目录（只有 GitHub 公开仓）"),
                       ("agi-research", "工作区无本地目录（只有 GitHub 公开仓）")):
        rows.append({"arm": arm, "self_verdict": "NOT_CARRIED",
                     "why": where + "；不拿别人 README 里的数字当自己的载体"})
    # not_carried must not claim "present but unpriced" once the arm is in the board;
    # a stale row of that kind reads as "nobody looked" and the next session skips it.
    # (An earlier draft of this line carried a dead comprehension -- removed rather than
    # left in as a comment.)
    hits = glob.glob(str(WORK / "goodhart-project/**/*.json"), recursive=True)
    rows.append({"arm": "goodhart-project", "self_verdict": "PRICED_ABOVE (GOODHART-C2)",
                 "why": "载体已接进算式：c2/results/summary.csv 逐 seed 原始值（%d 行）；"
                        "同目录仍有 %d 份 json 未接（train_config 之类，不含待判的量）"
                        % (30, len(hits))})
    return rows


def goodhart_arm():
    """The only arm on this board whose per-seed raw values are on disk: 6 alphas x 5 seeds
    of (proxy_score, true_score). So the CI is computed from the seeds at the 90% level the
    kernel expects, instead of borrowing the ledger's 95% bootstrap interval and calling it
    ci90 -- that substitution would be a caliber error with the same digits."""
    import csv
    import statistics
    path = WORK / "goodhart-project/c2/results/summary.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    by = {}
    for r in rows:
        by.setdefault(r["alpha"], []).append((int(r["seed"]), float(r["true_score"]),
                                              float(r["proxy_score"])))
    peak = max(by, key=lambda a: statistics.mean(t for _, t, _ in by[a]))
    worst = min(by, key=lambda a: statistics.mean(t for _, t, _ in by[a])
                - 3.0 * statistics.mean(p for _, _, p in by[a]))
    # paired per-seed difference peak -> worst (same seeds, so pairing is available)
    tp = {sd: (t, pr) for sd, t, pr in by[peak]}
    tw = {sd: (t, pr) for sd, t, pr in by[worst]}
    shared = sorted(set(tp) & set(tw))
    diffs = [tw[s][0] - tp[s][0] for s in shared]
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else None
    n = len(diffs)
    se = sd / math.sqrt(n) if sd else None
    ref_true = [t for _, t, _ in by[peak]]
    ref_mean = statistics.mean(ref_true)
    ref_sd = statistics.stdev(ref_true)
    ref_se = ref_sd / math.sqrt(len(ref_true))
    return {
        "arm": "GOODHART-C2", "question": "α 往代理最大方向推，真实分掉多少是判得开的",
        "currency": "true_score (same env, paired by seed)",
        "carriers": {"summary.csv": {"rows": len(rows), "alphas": sorted(by, key=float),
                                     "peak_alpha": peak, "seeds_paired": n,
                                     "proxy_at_peak": round(statistics.mean(pr for _, _, pr in by[peak]), 4),
                                     "proxy_at_other": round(statistics.mean(pr for _, _, pr in by[worst]), 4)}},
        "spec": {
            "mode": "escalation", "z": 2.802,
            "question": "GOODHART-C2: is the detach magnitude resolved, and what would more seeds buy",
            "reference": {"mean": round(ref_mean, 3),
                          "ci90": [round(ref_mean - Z90 * ref_se, 3), round(ref_mean + Z90 * ref_se, 3)],
                          "carrier": "c2/results/summary.csv alpha=%s true_score over %d seeds" % (peak, len(ref_true))},
            "candidate": {"arm": "alpha %s -> %s" % (peak, worst), "mean": round(mean, 3),
                          "sd": round(sd, 3), "better_is": "higher",
                          "ci90": [round(mean - Z90 * se, 3), round(mean + Z90 * se, 3)]},
            "cost": {"reference_minutes": None, "reference_cells": None,
                     "note": "本轮无运行成本载体（这是既有产物的重算，不是新发）"},
            "limitations": ["n=5 个配对 seed，sd 由 5 个差值现算：区间是 t 分布意义上的粗估，未做 clustered 校正",
                            "peak/worst 的选法用『真实分峰』与『代理-真实权衡最大』两条规则现算，不是从台账抄的",
                            "参照尺只在自己币种（true_score）内有效，不许拿去给别的臂定 bar"],
        },
    }


def build(inject=None):
    k = load_kernel()
    arms = [arc2_arm(), gsm_tpr_arm(), coderepair_arm(), goodhart_arm()]
    # Injections are placed on the arm that actually REACHES the gate. My first attempt
    # popped better_is from AIR-CODEREPAIR, which short-circuits at "no bar carrier" long
    # before the sign check -- a fixture that cannot change the verdict is not a fixture.
    if inject == "direction":
        arms[0]["spec"]["candidate"].pop("better_is")          # ARC2 reaches the sign gate
    if inject == "bar":
        arms[0]["spec"]["reference"] = None                     # remove the ruler itself
    if inject == "currency":
        # the currency gate lives in additivity mode, so demonstrate it THERE
        arms[0]["additivity_demo"] = {
            "mode": "additivity",
            # 字段名是 mean_delta：我第一版写了 "mean"，于是两条腿都落 leg_premise_missing，
            # 同币种与异币种得到同一个判决——那等于这条夹具什么都没测
            "legs": [{"arm": "dev panel", "mean_delta": 0.03, "sd": 0.01, "n": 817, "se": 0.0011,
                      "currency": "solved fraction (dev 817)"},
                     {"arm": "hold panel", "mean_delta": 0.027, "sd": 0.01, "n": 259, "se": 0.0020,
                      "currency": "solved fraction (dev 817)"}],
            # rungs 是阶梯表（每档 dict 带 dose 与 points），不是裸数字：我第一版传了
            # [0.01, 0.05]，原件在 price_at_rung 里对 float 调 .get() 直接崩——而我是
            # 带着这个坏路径把板子提交的
            "target": {"dose": 0.05}, "gap": 0.5,
            "rungs": [{"rung": 1, "dose": 0.01, "points": 100.0},
                      {"rung": 2, "dose": 0.05, "points": 400.0},
                      {"rung": 3, "dose": 0.10, "points": 700.0}]}
    out = {"board": "AGI 候选臂可判定性定价板", "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "read_only": True, "kaggle_writes": 0, "sim_machine_minutes": 0,
           "kernel": {"path": KERNEL, "z90": Z90, "z80": Z80}, "arms": [], "not_carried": not_carried()}
    for a in arms:
        entry = dict(a)
        entry.pop("spec", None)
        if a.get("self_verdict"):
            entry["verdict"] = a["self_verdict"]
        else:
            spec = json.loads(json.dumps(a["spec"]))
            if inject == "currency" and a["arm"] == "ARC2-MG":
                add = dict(arms[0].get("additivity_demo") or {})
                same = k.check_additivity(dict(add, legs=[dict(x) for x in add["legs"]]))
                add2 = json.loads(json.dumps(add)); add2["legs"][1]["currency"] = "ABS bank $/paired-game"
                diff = k.check_additivity(add2)
                # 判决名整条给，不做 split —— 这台仪器输出的就是判决，缩写会把
                # NOT_COMPUTABLE / NOT_FUNDED 这种区分抹掉
                entry["verdict"] = "CURRENCY_GATE|same=%s|mis=%s" % (
                    same.get("verdict"), diff.get("verdict"))
                entry["currency_gate"] = {"same_currency_verdict": same.get("verdict"),
                                          "mismatched_currency_verdict": diff.get("verdict"),
                                          "rule": "币种闸必须在看数之前拒绝相加"}
                out["arms"].append(entry)
                continue
            res = k.check_escalation(spec)
            entry["kernel_verdict"] = res.get("verdict")
            entry["kernel"] = {kk: res.get(kk) for kk in
                               ("bar", "sign_convention", "ci_used", "promotion_test",
                                "escalation_arithmetic", "cost") if kk in res}
            entry["kernel_verdict_name"] = res.get("verdict")
            entry["verdict"] = res.get("verdict") or "UNNAMED"
        if a["arm"] == "GOODHART-C2" and str(entry["verdict"]).startswith("PROMOTION_RULED_OUT"):
            entry["reading_warning"] = (
                "这条判决说的是『再加 seed 也不会把 α 推成一次升档』，不是说 Goodhart 脱钩"
                "没发生。候选均值本身是大负数（真实分从峰位崩下去），那正是这篇东西要找的"
                "效应——RULED_OUT 在此仅否掉『多买样本能翻正』这一条，绝不构成对该发现的否证。"
                "把它转述成『结论被推翻』是错的。")
        out["arms"].append(entry)
    return out


if __name__ == "__main__":
    inject = None
    if "--red" in sys.argv:
        inject = os.environ.get("INJECT", "direction")
    board = build(inject)
    if inject:
        print(json.dumps([{"arm": a["arm"], "verdict": a.get("verdict")} for a in board["arms"]],
                         ensure_ascii=False))
        sys.exit(0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(board, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# AGI 候选臂 · 可判定性定价板（零机时）", "",
             "运行 %s | read_only=%s | sim_machine_minutes=%s | kaggle_writes=%s" %
             (board["ran_at_utc"], board["read_only"], board["sim_machine_minutes"],
              board["kaggle_writes"]), "",
             "> 每个数由 `scripts/agi_arm_price_board.py` 从载体现读；判决由 prebuild-testability "
             "原件给，不由本板命名。", "", "| 臂 | 判决 | 币种 | 实测成本 |", "|---|---|---|---|"]
    for a in board["arms"]:
        cost = a.get("carriers", {}).get("measured_cost") or a.get("spec_cost")
        lines.append("| %s | %s | %s | %s |" % (a["arm"], a.get("verdict"), a.get("currency"),
                                                json.dumps(cost, ensure_ascii=False) if cost else "见 JSON"))
    for r in board["not_carried"]:
        lines.append("| %s | %s | — | — |" % (r["arm"], r["self_verdict"]))
    lines.append("")
    for a in board["arms"]:
        lines.append("## %s — %s" % (a["arm"], a.get("question")))
        lines.append(json.dumps({kk: a.get(kk) for kk in ("verdict", "kernel", "why", "consequence",
                                                          "limitations", "usable_instead")
                                 if a.get(kk) is not None}, ensure_ascii=False, indent=1))
        lines.append("")
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"arms": {a["arm"]: a.get("verdict") for a in board["arms"]},
                      "not_carried": {r["arm"]: r["self_verdict"] for r in board["not_carried"]},
                      "md": str(MD)}, ensure_ascii=False, indent=1))
