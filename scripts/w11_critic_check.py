#!/usr/bin/env python3
"""W11 判读器（HumanEval pass@1 代码生成）。

职责（沿用 W7/W8/W9 判读纪律，形状按 W11 设计适配）：
1. **重算门**：从 store/w11_humaneval_items.jsonl **独立重算** pass@1、
   Wilson95、失败原因分布、锚差，与 summary 逐项对比——数字对不上即 fail。
   独立性是硬要求：judge 的 check_task 在 runner 里，判读器**不 import**
   w11_humaneval_pass1，改在这里重写一遍子进程执行（冤枉好人比漏抓坏人
   更不可修，同源错误互检是检不出来的）。
2. **分母完整性门**：必须 164 题、task_id 与数据全集逐位一致。
3. **锚差校准门**：本实验是量级测量，claim 必须带「本实验」「量级测量」
   与口径词，禁「复现/达到锚/超过锚/SOTA/优于」。
4. **verdict 语义**（沿用 W8 约定 ALLOWED=(pass, insufficient)）：
   - 重算不过 / 门不过 ⇒ fail（不进结论链）
   - 重算过、且方向性结论成立（CI 上界低于锚下界，即"可区分地低于"）
     ⇒ pass
   - 重算过、但区间与锚重叠 ⇒ insufficient（只报数字，不下方向性）
   锚用的是 Codex 表 1 的同口径 k=1 列（pass@1 单采样）。
"""
from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(ROOT, "ai-researcher", "store")
DATA = os.path.join(ROOT, "ai-researcher", "data", "humaneval", "HumanEval.jsonl")
OUT_ITEMS = os.path.join(STORE, "w11_humaneval_items.jsonl")
OUT_SUMMARY = os.path.join(STORE, "w11_humaneval_summary.json")
OUT_VERDICT = os.path.join(STORE, "w11_critic_verdict.json")
N_TASKS = 164
ALPHA = 0.05

REQUIRED_IN_CLAIM = ("本实验", "pass@1", "量级")
FORBIDDEN_IN_CLAIM = ("复现", "达到锚", "超过锚", "SOTA", "优于", "显著优于")


# ── 独立重算（不 import runner）────────────────────────────────────────
def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load_tasks() -> list[dict]:
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
    return rows


def load_rows(items_path: str) -> list[dict]:
    if not os.path.exists(items_path):
        raise FileNotFoundError(items_path)
    out = []
    for l in open(items_path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return out


def rerun_judge(task: dict, code: str, timeout_s: int = 20,
                python: str = sys.executable) -> tuple[bool, str]:
    """**独立实现**的 judge：拼 src → 子进程跑 → returncode==0 即 pass。
    与 runner.check_task 逻辑相同但代码独立写（防同源错误）。"""
    src = task["prompt"] + code + "\n\n" + task["test"] + \
        f"\n\ncheck({task['entry_point']})\n"
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "recheck.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        try:
            r = subprocess.run([python, "-I", "-S", path], capture_output=True,
                               text=True, timeout=timeout_s, cwd=td)
        except subprocess.TimeoutExpired:
            return False, "exec_timeout"
        except OSError:
            return False, "exec_error"
    return (r.returncode == 0), ("pass" if r.returncode == 0 else "assert_or_error")


def recompute(items_path: str = OUT_ITEMS, rerun: bool = True) -> dict:
    tasks = {t["task_id"]: t for t in load_tasks()}
    rows = load_rows(items_path)
    by_tid = {}
    for r in rows:
        by_tid[r["task_id"]] = r          # 后写覆盖先写（断点续跑语义）
    missing = [t for t in tasks if t not in by_tid]
    n = len(by_tid)
    k = sum(1 for r in by_tid.values() if r["passed"])
    fail_reasons: dict[str, int] = {}
    for r in by_tid.values():
        if not r["passed"]:
            fail_reasons[r["check"]] = fail_reasons.get(r["check"], 0) + 1
    lo, hi = wilson(k, n) if n else (None, None)
    # 独立重跑：抽全部 pass 的（必须全部复现 pass）与抽 5 个 fail 的
    # （必须全部复现 fail）。抽全部 pass 是因为 pass 是我们对外报的数。
    rerun_pass_mismatch = []
    rerun_fail_mismatch = []
    if rerun:
        for tid, r in by_tid.items():
            if r["passed"]:
                ok, how = rerun_judge(tasks[tid], r["code"])
                if not ok:
                    rerun_pass_mismatch.append(tid)
        fails = [tid for tid, r in by_tid.items() if not r["passed"]]
        for tid in fails[:5]:
            r = by_tid[tid]
            if not r["code"]:
                continue
            ok, how = rerun_judge(tasks[tid], r["code"])
            if ok:
                rerun_fail_mismatch.append(tid)
    return {
        "pass_at_1": round(k / n, 4) if n else None,
        "wilson95": [round(lo, 4), round(hi, 4)] if n else None,
        "n_pass": k, "n_tasks": n,
        "n_missing": len(missing),
        "missing_ids": missing[:10],
        "fail_reasons": fail_reasons,
        "n_truncated": sum(1 for r in by_tid.values() if r["truncated"]),
        "n_unparsed": sum(1 for r in by_tid.values() if r["extract"] == "unparsed"),
        "sec_mean": round(statistics.mean([r["sec"] for r in by_tid.values()]), 1)
                    if n else None,
        "rerun_pass_mismatch": rerun_pass_mismatch,
        "rerun_fail_mismatch": rerun_fail_mismatch,
    }


def diff_dict(mine: dict, theirs: dict) -> dict:
    return {k: (mine.get(k), theirs.get(k))
            for k in set(mine) | set(theirs)
            if mine.get(k) != theirs.get(k)}


# runner 的 summary 只记 3 个「对比锚」（不是全部 13 个）。判读器必须
# **自己从 protocol.anchors 推出这 3 个键名与数值**，而不是拿 summary 的
# 键当标准——否则 summary 少记/多记/键名写错一个锚都查不出来（实测：判读器
# 按「分数原样格式化」推出 vs_GPT-Neo-125M_0.01，而 runner 的真键名是
# vs_GPT-Neo-125M_0.75——锚值 0.0075 是分数、键名里是百分数，
# 重算门报 3 处 null 差异，掩盖了真正该查的东西）。
# selftest 里有跨模块交叉断言（import runner 的 summarize 比对键集），
# 键名规则只允许写一份。
COMPARE_ANCHORS = ("Codex-12M", "GPT-Neo 125M", "GPT-J 6B")


def anchor_key(name: str, pct: float) -> str:
    """summary.gap_to_anchor 的键名规则：`vs_<锚名空格改连字符>_<锚的百分数两位小数>`。

    ⚠️ **单位**：`protocol.anchors` 存的是论文 Table 1 的**百分数**原值
    （GPT-Neo 125M = 0.75 表示 0.75%，Codex-12B = 28.81 表示 28.81%），
    键名里也是这个百分数；而 pass@1 与所有差值都是**分数**。
    所以任何比较都必须先 `pct / 100`——初版直接拿 0.75 当分数比，
    等于把「0.75% 的锚」当成「75% 的锚」，方向性判据整个反了。
    selftest 里有跨模块交叉断言（import runner 的 summarize 比对键集+数值），
    键名规则与单位只允许存在一份。
    """
    return "vs_%s_%.2f" % (name.replace(" ", "-"), pct)


def anchors_frac(anchors: dict) -> dict[str, float]:
    """百分数 → 分数。名字里必须带 _frac，否则和 anchors 混用就是这次的 bug。"""
    return {k: v / 100.0 for k, v in anchors.items()}


def expected_gap_keys(anchors: dict) -> dict[str, float]:
    """从 anchors 自己推出 summary 应有的对比锚键（不读 summary）。
    返回 {键名: 该锚的分数值}。"""
    out = {}
    for name in COMPARE_ANCHORS:
        if name not in anchors:
            raise KeyError(f"summary.protocol.anchors 缺对比锚 {name}")
        out[anchor_key(name, anchors[name])] = anchors[name] / 100.0
    return out


def anchor_gap(pass_at_1: float, anchors: dict) -> dict:
    """全部锚的差（**分数制**，anchor_gap=我方−锚）。注意 anchors 是百分数，
    这里已除过 100；直接减会把 28.81% 当 28.81 用，差值毫无意义。"""
    return {name: round(pass_at_1 - v, 4)
            for name, v in anchors_frac(anchors).items()}


def gap_dict(mine: dict, theirs: dict) -> dict:
    return {k: (mine.get(k), theirs.get(k))
            for k in set(mine) | set(theirs)
            if mine.get(k) != theirs.get(k)}


def scope_and_caliber(claim: str, directional: bool) -> dict:
    missing = [w for w in REQUIRED_IN_CLAIM if w not in claim]
    banned = [w for w in FORBIDDEN_IN_CLAIM if w in claim]
    ok = not missing and not banned
    why = []
    if missing:
        why.append(f"缺必备词：{missing}")
    if banned:
        why.append(f"含禁词：{banned}")
    return {"pass": ok, "reason": "；".join(why)}


def build_claim(rc: dict, anchors: dict) -> tuple[str, bool]:
    """结论只能从重算数字来。

    方向性判据（**双向**，不是只判「低于」）：本实验 95% Wilson 区间与
    最小锚/最大锚的区间真分离 ⇒ 方向性结论成立（高于或低于都说得清）；
    与最大锚也重叠 ⇒ 只报数字，不下方向性结论。
    ⚠️ anchors 是百分数，比较前一律先 anchors_frac()——把 28.81 当 0.2881
    之外的 28.81 直接比，会把 0.3537 判成「低于所有锚」，方向整个反掉。
    """
    lo, hi = rc["wilson95"]
    p = rc["pass_at_1"]
    n = rc["n_tasks"]
    af = anchors_frac(anchors)
    min_name = min(af, key=af.get)
    max_name = max(af, key=af.get)
    a_min, a_max = af[min_name], af[max_name]
    above_min = lo > a_min          # 可区分地高于最小锚
    below_max = hi < a_max          # 可区分地低于最大锚
    directional = above_min or below_max
    missing_cmp = [n2 for n2 in COMPARE_ANCHORS if n2 not in anchors]
    if missing_cmp:
        raise KeyError(f"anchors 缺对比锚 {missing_cmp}——不能出缺数字的 claim")
    gap_s = "、".join(
        f"{name} {p - af[name]:+.4f}"
        for name in sorted(COMPARE_ANCHORS, key=lambda x: af[x]))
    if directional and below_max and not above_min:
        rel = (f"本实验 95% Wilson 区间 [{lo}, {hi}] 整体低于表中最大锚 "
               f"{max_name}（{anchors[max_name]}%），可区分地低于该锚")
    elif directional and above_min and not below_max:
        rel = (f"本实验 95% Wilson 区间 [{lo}, {hi}] 下界 {lo} 高于表中最小锚 "
               f"{min_name}（{anchors[min_name]}%），可区分地高于该锚；"
               f"但上界 {hi} 与最大锚 {max_name}（{anchors[max_name]}%）重叠，"
               f"故不声称高于最大锚")
    else:
        rel = (f"本实验 95% Wilson 区间 [{lo}, {hi}] 同时高于表中最小锚 "
               f"{min_name}（{anchors[min_name]}%）并低于最大锚 {max_name}"
               f"（{anchors[max_name]}%）")
    claim = (
        f"本实验迷你口径实测：Qwen3-0.6B（bf16，CPU 贪心，每题单采样）"
        f"在 HumanEval 全量 {n} 题上的 pass@1 = {p}"
        f"（Wilson 95% CI [{lo}, {hi}]，n={n}，分母=全部题，无抽样）；"
        f"失败原因分布 {rc['fail_reasons']}，其中截断 {rc['n_truncated']} 题、"
        f"无可抽取代码 {rc['n_unparsed']} 题。"
        f"{rel}。对 Codex 论文 Table 1 pass@1 锚（不同模型不同数据配比，"
        f"同口径 k=1 单采样）为量级测量、非受控比较；anchor_gap=我方−锚"
        f"（负=我方更差）：{gap_s}。")
    return claim, directional


def judge(items_path: str = OUT_ITEMS, summary_path: str = OUT_SUMMARY) -> dict:
    rc = recompute(items_path)
    summary = json.load(open(summary_path, encoding="utf-8"))
    anchors = summary.get("protocol", {}).get("anchors", {})
    if not anchors:
        raise ValueError("summary 里没有锚——不能凭空造锚")
    # 关键：对照基准由「锚 + 键名规则」推出，**不是**由 summary 的
    # gap_to_anchor 本身推出，否则 summary 写错键名/漏锚就永远查不出。
    exp = expected_gap_keys(anchors)
    p = rc["pass_at_1"]
    want_gap = {k: round(p - anchor, 4) for k, anchor in exp.items()}

    diffs = {}
    diffs["pass_at_1"] = (rc["pass_at_1"], summary.get("pass_at_1"))
    diffs["wilson95"] = (rc["wilson95"], summary.get("wilson95"))
    diffs["n_pass"] = (rc["n_pass"], summary.get("n_pass"))
    diffs["n_tasks"] = (rc["n_tasks"], summary.get("n_tasks"))
    diffs["fail_reasons"] = (rc["fail_reasons"], summary.get("fail_reasons"))
    diffs["n_truncated"] = (rc["n_truncated"], summary.get("n_truncated"))
    diffs["n_unparsed"] = (rc["n_unparsed"], summary.get("n_unparsed"))
    diffs["sec_mean"] = (rc["sec_mean"], summary.get("sec_mean"))
    # 锚差有两层门：① 键集与数值必须等于「由 anchors 推出的期望」；
    # ② summary 必须确实只记了 COMPARE_ANCHORS 这三个（多记也要报出来）。
    got_gap = summary.get("gap_to_anchor", {})
    diffs["gap_to_anchor"] = gap_dict(want_gap, got_gap)
    diffs["gap_keys_scope"] = (sorted(got_gap), sorted(want_gap))
    # gap_to_anchor 的「diff 本身」是个 dict（内含每项的 (mine, theirs)），
    # 不能和标量项一起用 v[0]!=v[1] 展开——那会对 dict 取下标 0 而 KeyError。
    # 统一规则：一个 diff 值若自身是 dict，则「非空即不一致」。
    def _mismatched(v):
        if isinstance(v, dict):
            return bool(v)
        return v[0] != v[1]

    recomputable = not any(_mismatched(v) for v in diffs.values())

    # 分母完整性：必须 164 题、零缺题、逐位 task_id 一致
    tasks = {t["task_id"] for t in load_tasks()}
    got_ids = {r["task_id"] for r in load_rows(items_path)}
    denom_ok = (rc["n_tasks"] == N_TASKS and rc["n_missing"] == 0
                and tasks == got_ids)

    # 独立重跑门：所有报 pass 的必须复现 pass；抽检的 fail 必须仍 fail
    rerun_ok = not rc["rerun_pass_mismatch"] and not rc["rerun_fail_mismatch"]

    claim, directional = build_claim(rc, anchors)
    cal = scope_and_caliber(claim, directional)

    gates = {
        "recomputable": {"pass": recomputable, "diffs": diffs},
        "denominator_complete": {"pass": denom_ok,
                                 "reason": "" if denom_ok else
                                 f"n={rc['n_tasks']}（应 {N_TASKS}）、"
                                 f"缺 {rc['n_missing']} 题 {rc['missing_ids']}"},
        "independent_rerun": {"pass": rerun_ok,
                               "reason": "" if rerun_ok else
                               f"复跑不一致：pass 侧 {rc['rerun_pass_mismatch'][:5]}、"
                               f"fail 侧 {rc['rerun_fail_mismatch'][:5]}"},
        "scope_caliber_in_claim": cal,
    }
    hard_fail = any(not g["pass"] for g in gates.values())
    if hard_fail:
        verdict = "fail"
    elif directional:
        verdict = "pass"
    else:
        verdict = "insufficient"
    return {"claim": claim, "verdict": verdict,
            "recomputed": rc, "gates": gates,
            "anchors_used": anchors,
            "design_note": "全量 164 题、无抽样、每题单采样（pass@1）。"
                           "方向性判据=本实验 CI 上界 < 表中最小锚（保守）。"
                           "对锚=量级测量非受控比较，不做显著性声明。"}


def selftest() -> int:
    bad = []
    ck_n = [0]

    def ck(name, got, want):
        ck_n[0] += 1
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # 1. Wilson 教科书值（7/8）
    lo, hi = wilson(7, 8)
    ck("Wilson 7/8", (round(lo, 3), round(hi, 3)), (0.529, 0.978))

    # 2. 独立 rerun_judge：对的过、错的不过（门必须能失败）
    tasks = load_tasks()
    t0 = tasks[0]
    ok, how = rerun_judge(t0, t0["canonical_solution"])
    ck("canonical 复跑通过", (ok, how), (True, "pass"))
    ok, how = rerun_judge(t0, "\n    pass")
    ck("空实现复跑失败", ok, False)

    # 3. 分母完整性门能失败：只喂 3 题 ⇒ denom_ok=False
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "items.jsonl")
        with open(ip, "w", encoding="utf-8") as fh:
            for t in tasks[:3]:
                fh.write(json.dumps({"task_id": t["task_id"],
                                     "passed": True, "check": "pass",
                                     "extract": "fence", "truncated": False,
                                     "sec": 1.0, "code": t["canonical_solution"]},
                                    ensure_ascii=False) + "\n")
        rc3 = recompute(ip, rerun=False)
        ck("3 题时 n_tasks=3", rc3["n_tasks"], 3)
        ck("3 题时 n_missing=161", rc3["n_missing"], N_TASKS - 3)

    # 4. 方向性判定（**双向**）。anchors 一律用**百分数**原值，与真实
    #    protocol.anchors 同单位——夹具用分数是这个 bug 的根源。
    #    真实锚集：最小 GPT-Neo 125M = 0.75%，最大 Codex-12B = 28.81%。
    pct_anchors = {"GPT-Neo 125M": 0.75, "GPT-Neo 2.7B": 6.41,
                   "GPT-J 6B": 11.62, "Codex-12M": 2.00,
                   "Codex-12B": 28.81}

    def rc_of(lo, hi, p):
        return {"wilson95": [lo, hi], "pass_at_1": p, "n_tasks": 164,
                "fail_reasons": {"assert_or_error": 164 - round(p * 164)},
                "n_truncated": 0, "n_unparsed": 0}

    # 实测那一次的区间 [0.2846, 0.4294]：下界 > 0.0075（高于最小锚），
    # 上界 < 0.2881（低于最大锚）⇒ 两个方向都成立，但都只对**部分**锚成立。
    rc_real = rc_of(0.2846, 0.4294, 0.3537)
    claim_real, dir_real = build_claim(rc_real, pct_anchors)
    ck("实测区间可下方向性（两侧都分离）", dir_real, True)
    ck("实测 claim 说高于最小锚", "高于表中最小锚" in claim_real, True)
    ck("实测 claim 说不声称高于最大锚",
       "不声称高于最大锚" in claim_real, True)
    ck("实测 claim 带分数制 gap", "+0.2375" in claim_real, True)

    # pass@1≈0：CI [0, 0.023] 不高于最小锚（0.0 < 0.0075），但**低于最大锚**
    # （0.023 < 0.2881）⇒ 按双向判据仍是可下方向的（只对最大锚那侧成立）。
    _, dir_zero = build_claim(rc_of(0.0, 0.023, 0.0), pct_anchors)
    ck("pass@1≈0 时可区分低于最大锚 28.81%", dir_zero, True)
    cl_zero, _d = build_claim(rc_of(0.0, 0.023, 0.0), pct_anchors)
    ck("该情形说的是低于最大锚", "低于表中最大锚" in cl_zero, True)
    # **真正无法下方向**的夹具：区间同时压住最小锚与最大锚（两头都重叠）
    rc_mid = {"wilson95": [0.005, 0.30], "pass_at_1": 0.15, "n_tasks": 164,
              "fail_reasons": {"assert_or_error": 139}, "n_truncated": 0,
              "n_unparsed": 0}
    claim_mid, dir_mid = build_claim(rc_mid, pct_anchors)
    ck("两头都重叠⇒无方向", dir_mid, False)
    ck("两头都重叠的措辞", "同时高于表中最小锚" in claim_mid, True)
    # 锚顺序颠倒，判据不变（反向夹具）。两个夹具都测：两头重叠的、
    # 以及单侧分离的——判据若依赖 dict 顺序，这两个都会翻。
    rev = {k: pct_anchors[k] for k in reversed(list(pct_anchors))}
    _, dir_rev = build_claim(rc_mid, rev)
    ck("锚顺序颠倒不改变判据（重叠夹具）", dir_rev, dir_mid)
    # 全通过：下界远高于最大锚 0.2881 ⇒ 可区分地高于最大锚
    _, dir_hi = build_claim(rc_of(0.9, 1.0, 0.95), pct_anchors)
    ck("pass@1=0.95 时可下方向（高于最大锚）", dir_hi, True)
    # 锚顺序颠倒，判据不变（反向夹具）
    rev2 = {k: pct_anchors[k] for k in reversed(list(pct_anchors))}
    _, dir_rev2 = build_claim(rc_of(0.0, 0.023, 0.0), rev2)
    ck("锚顺序颠倒不改变判据（单侧夹具）", dir_rev2, dir_zero)

    # 4b. 单位反证：把百分数当分数用（=这次的 bug）必须被这一组断言挡住
    ck("anchors_frac 把百分数换成分数",
       anchors_frac({"GPT-Neo 125M": 0.75})["GPT-Neo 125M"], 0.0075)
    ck("百分数当分数会翻转方向（反证）",
       build_claim(rc_of(0.2846, 0.4294, 0.3537),
                   {k: v / 100 for k, v in pct_anchors.items()})[1], True)

    # 5. claim 口径门
    claim_ok, dir_ok = build_claim(rc_real, pct_anchors)
    cal_ok = scope_and_caliber(claim_ok, dir_ok)
    ck("干净 claim 过口径门", cal_ok["pass"], True)
    ck("干净 claim 带必备词",
       all(w in claim_ok for w in REQUIRED_IN_CLAIM), True)
    ck("禁词被口径门抓",
       scope_and_caliber("本实验 pass@1 量级 优于锚", True)["pass"], False)

    # 5b. **跨模块交叉断言**：判读器推出的 gap 键集必须与 runner 的
    # summarize 完全相同。键名规则（锚值是分数、键名里是百分数）只允许
    # 存在一份；两边各写一遍必然漂移，实测就漂过一次（0.01 vs 0.75）。
    import importlib.util
    rspec = importlib.util.spec_from_file_location(
        "w11_runner", os.path.join(HERE, "w11_humaneval_pass1.py"))
    runner = importlib.util.module_from_spec(rspec)
    rspec.loader.exec_module(runner)
    fake = [{"task_id": f"t{i}", "passed": i < 7, "sec": 1.0,
             "truncated": False, "extract": "fence",
             "check": "pass" if i < 7 else "assert_or_error"}
            for i in range(N_TASKS)]
    r_sum = runner.summarize(runner.load_tasks(), fake, "flag", 1.0)
    ck("gap 键集与 runner 逐字相同",
       sorted(expected_gap_keys(r_sum["protocol"]["anchors"])),
       sorted(r_sum["gap_to_anchor"]))
    ck("gap 数值与 runner 逐字相同",
       {k: round(r_sum["pass_at_1"] - v, 4)
        for k, v in expected_gap_keys(
            r_sum["protocol"]["anchors"]).items()},
       r_sum["gap_to_anchor"])

    # 6. 篡改 summary 数字被重算门抓（端到端 fail）
    with tempfile.TemporaryDirectory() as td:
        ip = os.path.join(td, "i.jsonl")
        sp = os.path.join(td, "s.json")
        rows = []
        for i, t in enumerate(tasks):
            passed = i < 5
            rows.append({"task_id": t["task_id"], "passed": passed,
                         "check": "pass" if passed else "assert_or_error",
                         "extract": "fence", "truncated": False, "sec": 1.0,
                         "code": t["canonical_solution"] if passed else "\n    pass"})
        with open(ip, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        good = recompute(ip, rerun=False)
        fanchors = {"Codex-12M": 2.00, "GPT-Neo 125M": 0.75,
                    "GPT-J 6B": 11.62}
        fexp = expected_gap_keys(fanchors)
        summary = {"pass_at_1": good["pass_at_1"], "wilson95": good["wilson95"],
                   "n_pass": good["n_pass"], "n_tasks": good["n_tasks"],
                   "fail_reasons": good["fail_reasons"],
                   "n_truncated": 0, "n_unparsed": 0, "sec_mean": 1.0,
                   "protocol": {"anchors": fanchors},
                   "gap_to_anchor": {
                       k: round(good["pass_at_1"] - a, 4)
                       for k, a in fexp.items()}}
        json.dump(summary, open(sp, "w", encoding="utf-8"))
        v = judge(ip, sp)
        ck("干净夹具重算过", v["gates"]["recomputable"]["pass"], True)
        ck("干净夹具分母满", v["gates"]["denominator_complete"]["pass"], True)
        tampered = json.loads(json.dumps(summary))
        tampered["pass_at_1"] = 0.9
        json.dump(tampered, open(sp, "w", encoding="utf-8"))
        v2 = judge(ip, sp)
        ck("篡改 pass@1⇒fail", v2["verdict"], "fail")
        ck("篡改被重算门点名", v2["gates"]["recomputable"]["pass"], False)
        # 键集门必须能失败：summary 少记一个对比锚也要报出来
        missing_anchor = json.loads(json.dumps(summary))
        missing_anchor["gap_to_anchor"].pop("vs_GPT-J-6B_11.62")
        json.dump(missing_anchor, open(sp, "w", encoding="utf-8"))
        v3 = judge(ip, sp)
        ck("少记一个对比锚⇒fail", v3["verdict"], "fail")
        ck("键集门点名", v3["gates"]["recomputable"]["pass"], False)
        # 锚值被改（不是键被删）也要被抓：want_gap 由 anchors 推出
        wrong_anchor = json.loads(json.dumps(summary))
        wrong_anchor["protocol"]["anchors"]["Codex-12M"] = 0.5
        json.dump(wrong_anchor, open(sp, "w", encoding="utf-8"))
        v4 = judge(ip, sp)
        ck("锚值被改⇒锚差门失败", v4["verdict"], "fail")
        # 锚缺对比项 ⇒ 直接报错，不静默出结论
        bad_anchor = json.loads(json.dumps(summary))
        del bad_anchor["protocol"]["anchors"]["Codex-12M"]
        json.dump(bad_anchor, open(sp, "w", encoding="utf-8"))
        try:
            judge(ip, sp)
            ck("锚缺对比项抛错", "没抛", "抛 KeyError")
        except KeyError:
            ck("锚缺对比项抛错", "抛了", "抛了")

    print(f"selftest: 失败 {len(bad)} / {ck_n[0]} 断言")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    v = judge()
    json.dump(v, open(OUT_VERDICT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("verdict:", v["verdict"], "| gates:",
          {k: g["pass"] for k, g in v["gates"].items()})
    print("wrote", OUT_VERDICT)
    return 0 if v["verdict"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())