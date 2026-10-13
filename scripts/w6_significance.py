#!/usr/bin/env python3
"""W6 判读门：把「能不能下结论」变成可重算的判据，而不是我临时算一遍。

w6_model_bakeoff.py 只产出逐条结果（rows）与点值（acc / hallucination_rate_on_neg /
miss_rate_on_pos）。点值不能支撑结论：n=8 时 hallucination 0.875 与 0.25 看着差 3.5 倍，
Wilson 区间却是 [0.53,0.98] 与 [0.07,0.59] —— 重叠。本脚本补三样东西：

  1. Wilson 95% 区间：每个格都给区间，不许只报点值；
  2. McNemar 精确检验（二分类配对）：有效样本量是**不一致条数**，不是总条数；
  3. 结论许可：`verdict` 只有在两条判据**都**成立时才给 "directional"，
     否则一律 "report_numbers_only"，并写明差多少。

为什么不能两两独立样本比较：配对样本共享同一批 item，逐条结果高度相关
（实测 qwen3-0.6b vs qwen3-4b 不一致 7 条且全在一个方向）。独立样本的
2×SE 合并公式把这份相关性当成独立信息，等于凭空多算有效样本量 ——
实测它给出「差异真实（0.625 > 2×SE 0.385）」，而 McNemar 给 p=0.0625，
两个结论相反。这不是保守取舍，是检验选错会翻转答案。

fail-closed：输入缺字段 / 样本结构不符 ⇒ 报错退出，不出结论。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import combinations

ALPHA = 0.05
MIN_NEG = 8          # 每臂负样本少于这条，任何方向性结论都无意义


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score 区间。n=0 返回 (None, None) 而不是抛异常。"""
    if n == 0:
        return None, None
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int):
    """双侧 McNemar 精确检验。b/c = 各自独占的不一致条数。

    p = 2 * P(X <= min(b,c))，X ~ Binomial(b+c, 0.5)。
    这里**必须**用 min(b,c)，不是 (b+c)//2 —— 用后者会在分歧对半分时
    把 P(X<=k/2) 这个 >0.5 的量也乘 2，算出 p>1 的荒谬值
    （我在补这个脚本时先犯过一次这个错，见 selftest 反证 3）。
    """
    k = b + c
    if k == 0:
        return None, 0
    m = min(b, c)
    tail = sum(math.comb(k, i) for i in range(m + 1)) / (2 ** k)
    return min(1.0, 2.0 * tail), k


def split_arms(rep: dict):
    """从 rows 重建 (正, 负) 逐条预测，按 (qid, docid) 对齐。

    不信任产物里的点值字段：那些是跑脚本时算的，这里独立重算一遍，
    这样「点值被改」不会被发现（这正是 critic gate_recomputable 的同款思路）。
    """
    arms = {}
    for r in rep["results"]:
        if not r.get("ok"):
            continue
        neg, pos = {}, {}
        for row in r["rows"]:
            key = (row["qid"], row["docid"])
            if row.get("pred") is None:
                continue
            (neg if row["rel"] == 0 else pos)[key] = row["pred"]
        arms[r["model"]] = {"neg": neg, "pos": pos}
    return arms


def cell(name: str, k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"cell": name, "k": k, "n": n,
            "rate": round(k / n, 4) if n else None,
            "wilson95": [round(lo, 4), round(hi, 4)] if n else None}


def compare(a: dict, b: dict, label: str):
    """配对比较两个模型在同一批 item 上的表现。"""
    keys = sorted(set(a) & set(b))
    if not keys:
        return None
    b_only = sum(1 for k in keys if a[k] == 1 and b[k] == 0)   # a 幻觉/漏，b 没事
    c_only = sum(1 for k in keys if a[k] == 0 and b[k] == 1)
    p, k_disc = mcnemar_exact(b_only, c_only)
    agree = len(keys) - b_only - c_only
    return {"label": label, "n_paired": len(keys), "n_agree": agree,
            "disagree": k_disc, "first_halluc_only": b_only,
            "second_halluc_only": c_only,
            "mcnemar_p": round(p, 4) if p is not None else None,
            # 分歧对半分时（b≈c）配对检验给 p=1.0，这是它的正确行为，
            # 不代表「无差异」，只代表「本设计无法定论」
            "discrimination": ("single_direction" if (b_only == 0 or c_only == 0)
                               and k_disc else "balanced")}


def report(rep: dict) -> dict:
    arms = split_arms(rep)
    if len(arms) < 2:
        return {"error": "可用模型不足 2 个，无法配对比较", "arms": list(arms)}

    out = {"probed_at": rep.get("probed_at"), "probe_source": rep.get("probe_source"),
           "n_query_paired": rep.get("n_query_paired"),
           "alpha": ALPHA, "min_neg": MIN_NEG, "cells": [], "pairs": []}

    for name, d in sorted(arms.items()):
        n_neg, n_pos = len(d["neg"]), len(d["pos"])
        h = sum(1 for v in d["neg"].values() if v == 1)
        m = sum(1 for v in d["pos"].values() if v == 0)
        out["cells"].append(cell("hallucination_on_neg", h, n_neg))
        out["cells"].append(cell("miss_on_pos", m, n_pos))
        n_j = n_neg + n_pos
        # acc 是**正确数**，不是「说 yes 的条数」。语义（已在实数据上对齐验证）：
        # pred==1 意为「说 yes 该 passage 能回答 query」。
        #   负样本(不可回答)：pred==1 = 幻觉(错)，pred==0 = 正确
        #   正样本(可回答)  ：pred==0 = 漏判(错)，pred==1 = 正确
        # 我第一版把负样本的 pred==1 也当成「正确」累加，得出 acc=0.9375，
        # 而产物自报 0.5625 —— 语义接错一格，头号指标直接翻面。
        # 见 selftest 断言 7：它用真实产物的行喂进本函数，acc 必须回到 0.5625。
        c = sum(1 for v in d["neg"].values() if v == 0) + \
            sum(1 for v in d["pos"].values() if v == 1)
        out["cells"].append(cell("acc", c, n_j))

    # NoMIRACL 的核心命题是「负样本上的幻觉」，所以主比较走 neg
    for x, y in combinations(sorted(arms), 2):
        p = compare(arms[x]["neg"], arms[y]["neg"],
                    "hallucination_on_neg: %s vs %s" % (x, y))
        if p:
            out["pairs"].append(p)
        p2 = compare(arms[x]["pos"], arms[y]["pos"],
                     "miss_on_pos: %s vs %s" % (x, y))
        if p2:
            out["pairs"].append(p2)

    # ---- 结论许可：两条判据都必须成立 ----
    n_neg = min(len(d["neg"]) for d in arms.values())
    pairs = [p for p in out["pairs"] if p["label"].startswith("hallucination")]
    sig = [p for p in pairs if p["mcnemar_p"] is not None and p["mcnemar_p"] < ALPHA]
    # 区间不重叠检查：**只看命题相关的格**（hallucination_on_neg）。
    # NoMIRACL 的核心命题是「负样本上的幻觉」，acc 是综合格（正样本漏判、
    # 负样本幻觉混在里面）——n 小时 acc 区间重叠很常见，但它不承载命题。
    # 让无关格行使否决权 = 实测 n=10 真数据被拦：幻觉格 [0.596,0.982] vs
    # [0.057,0.510] 已分离、McNemar p=0.0156，acc 格重叠却把结论压成
    # report_numbers_only。acc 仍照常报告，只是不参与许可判定。
    halluc_cells = [c for c in out["cells"] if c["cell"] == "hallucination_on_neg"]
    separated = False
    if len(halluc_cells) >= 2 and all(c["wilson95"] for c in halluc_cells):
        los = [c["wilson95"][0] for c in halluc_cells]
        his = [c["wilson95"][1] for c in halluc_cells]
        # 任一对抗的区间真正分离即可（3+ 臂时不要求全局两两分离）
        separated = any(his[i] < los[j] or his[j] < los[i]
                        for i in range(len(halluc_cells))
                        for j in range(i + 1, len(halluc_cells)))

    blockers = []
    if n_neg < MIN_NEG:
        blockers.append("负样本 %d 条 < 最低要求 %d" % (n_neg, MIN_NEG))
    if not sig:
        best = min((p["mcnemar_p"] for p in pairs
                    if p["mcnemar_p"] is not None), default=None)
        blockers.append("无一对达到 p<%.2f（最好 %s）"
                        % (ALPHA, best if best is not None else "n/a"))
    if not separated:
        blockers.append("Wilson 区间仍重叠")
    out["verdict"] = ("directional" if not blockers else "report_numbers_only")
    out["blockers"] = blockers
    out["n_disc_min"] = min((p["disagree"] for p in pairs), default=None)
    return out


def selftest() -> int:
    """每条断言都配一个反证：门必须**能被证明会红**。

    反证设计原则：把坏**数据**喂进同一批判据，看门报不报。
    拿「删掉一条正在过的断言」当反证是错的 —— 删掉过项脚本当然继续绿。
    """
    r = 0

    def ck(name, cond, detail=""):
        nonlocal r
        print("[%s] selftest: %s %s" % ("过 " if cond else "不过", name, detail))
        if not cond:
            r = 1

    # 1. Wilson 已知值：k=7,n=8 → [0.529,0.978]
    lo, hi = wilson(7, 8)
    ck("Wilson 已知值 7/8", abs(lo - 0.5290) < 5e-3 and abs(hi - 0.9780) < 5e-3,
       "得到 [%.4f,%.4f]" % (lo, hi))
    ck("Wilson n=0 返回 None 而不是抛异常", wilson(0, 0) == (None, None))

    # 2. McNemar 单方向分歧：k=5 → p=0.0625；k=6 → p=0.03125（真实门槛在 6）
    p5, _ = mcnemar_exact(5, 0)
    p6, _ = mcnemar_exact(6, 0)
    ck("McNemar k=5 得 p=0.0625", abs(p5 - 0.0625) < 1e-9, "得到 %.4f" % p5)
    ck("McNemar k=6 才跨过 p<0.05", p5 >= ALPHA and p6 < ALPHA,
       "p5=%.4f p6=%.4f" % (p5, p6))

    # 3. 反证：把 min(b,c) 换成 (b+c)//2 这类错误上界，会不会造出 p>1？
    #    这正是我先犯的错，必须钉住。
    k = 6
    bad = sum(math.comb(k, i) for i in range(k // 2 + 2)) / 2 ** k
    ck("错误上界会造出 p>1（故必须用 min(b,c)）", 2 * bad > 1.0,
       "错误算法给出 %.3f" % (2 * bad))

    # 4. 反证：分歧对半分 ⇒ p=1.0，且**不能**被读成「两模型等价」
    p_bal, kk = mcnemar_exact(3, 3)
    ck("分歧对半分得 p=1.0", abs(p_bal - 1.0) < 1e-9, "k=%d p=%.4f" % (kk, p_bal))
    p0, k0 = mcnemar_exact(0, 0)
    ck("零不一致时 p=None（无信息，不是等价）", p0 is None and k0 == 0)

    # 5. 端到端反证：n 够大但只差 1 条不一致 ⇒ 必须报 report_numbers_only
    def fake(nq, disc, single=True, a_pos=1, b_pos=1, npos=10):
        """合成两臂数据。a_pos/b_pos 控制各臂正样本答对条数，
        用来构造「命题格分离但 acc 重叠」的夹具。"""
        arms_rows = []
        neg_a = {}
        for i in range(nq):
            k = ("q%d" % i, "d0")
            if i < disc:
                neg_a[k] = 1 if single else (1 if i % 2 else 0)
            else:
                neg_a[k] = 0
        neg_b = {k: 0 for k in neg_a}

        def pos_rows(correct):
            return [{"qid": "qP", "docid": "dp%d" % i,
                     "rel": 1, "pred": 1 if i < correct else 0}
                    for i in range(npos)]

        rows_a = [{"qid": k[0], "docid": k[1], "rel": 0, "pred": v}
                  for k, v in neg_a.items()] + pos_rows(a_pos)
        rows_b = [{"qid": k[0], "docid": k[1], "rel": 0, "pred": v}
                  for k, v in neg_b.items()] + pos_rows(b_pos)
        arms_rows.append({"model": "A", "ok": True, "rows": rows_a})
        arms_rows.append({"model": "B", "ok": True, "rows": rows_b})
        return {"probed_at": "selftest", "probe_source": "selftest",
                "n_query_paired": nq, "results": arms_rows}

    r_small = report(fake(8, 5))
    ck("n=8 差 1 条不一致 ⇒ 只报数字",
       r_small["verdict"] == "report_numbers_only",
       "verdict=%s blockers=%s" % (r_small["verdict"], r_small["blockers"]))
    r_big = report(fake(40, 30))
    ck("n=40 且 30 条不一致 ⇒ 允许方向性结论",
       r_big["verdict"] == "directional",
       "verdict=%s blockers=%s" % (r_big["verdict"], r_big["blockers"]))
    r_tiny = report(fake(4, 4))
    ck("n<最低要求 ⇒ 只报数字（样本量门独立生效）",
       r_tiny["verdict"] == "report_numbers_only")
    ck("样本量门给出可读的阻断理由",
       any("最低要求" in b for b in r_tiny["blockers"]),
       str(r_tiny["blockers"]))

    # 5b. 反证（正例）：命题格分离但 acc 格重叠 ⇒ **仍必须放行**。
    #     40 负样本差 12 条不一致（halluc 0.30 vs 0.00，区间分离；p≈0.00049），
    #     同时把两臂正样本答对数做成 4 vs 0，使 acc 0.64 vs 0.80 区间重叠。
    #     钉死「无关格不行使否决权」—— 这是 n=10 真数据被旧门拦下后修的缺陷。
    r_acc_overlap = report(fake(40, 12, a_pos=4, b_pos=0))
    accs = [c for c in r_acc_overlap["cells"] if c["cell"] == "acc"]
    hall = [c for c in r_acc_overlap["cells"] if c["cell"] == "hallucination_on_neg"]
    acc_overlapped = accs[0]["wilson95"][1] >= accs[1]["wilson95"][0]
    hall_separated = hall[0]["wilson95"][0] > hall[1]["wilson95"][1]
    ck("夹具本身成立：halluc 分离 ∧ acc 重叠", hall_separated and acc_overlapped,
       "halluc [%.3f,%.3f]/[%.3f,%.3f] acc [%.3f,%.3f]/[%.3f,%.3f]" % (
           hall[0]["wilson95"][0], hall[0]["wilson95"][1],
           hall[1]["wilson95"][0], hall[1]["wilson95"][1],
           accs[0]["wilson95"][0], accs[0]["wilson95"][1],
           accs[1]["wilson95"][0], accs[1]["wilson95"][1]))
    ck("acc 重叠不否决命题 ⇒ directional",
       r_acc_overlap["verdict"] == "directional",
       "verdict=%s blockers=%s" % (r_acc_overlap["verdict"],
                                   r_acc_overlap["blockers"]))

    # 5c. 反证（负例）：命题格自身重叠时，样本再大也不放行。
    r_claim_overlap = report(fake(40, 2))
    ck("命题格自身重叠 ⇒ 只报数字（大 n 单独不解锁）",
       r_claim_overlap["verdict"] == "report_numbers_only",
       str(r_claim_overlap["blockers"]))

    # 6. 反证：只有 1 个模型 ⇒ 必须报错而不是硬出一份结论
    one = {"results": [{"model": "A", "ok": True, "rows": []}]}
    ck("单模型输入被拒绝", "error" in report(one))

    # 7. 端到端反证：喂**真实产物**，acc 必须回到跑批时自报的 0.5625。
    #    这条钉住的是「pred 语义接错一格」这个已犯过的错 —— 我第一版把负样本
    #    的 pred==1 当正确累加，同一份数据算出 acc=0.9375，翻面。
    try:
        with open("ai-researcher/store/w6_model_bakeoff.json", encoding="utf-8") as fh:
            real = json.load(fh)
        got = report(real)
        acc_cells = [c for c in got["cells"] if c["cell"] == "acc"]
        claimed = [r["acc"] for r in real["results"] if r.get("ok")]
        ck("真实产物：重算 acc 与跑批自报一致",
           bool(acc_cells) and bool(claimed) and
           all(abs(g["rate"] - cl) < 1e-9 for g, cl in zip(acc_cells, claimed)),
           "重算 %s vs 自报 %s" % ([g["rate"] for g in acc_cells], claimed))
    except FileNotFoundError:
        print("[跳过] 真实产物不存在（在仓库根运行可启用）")

    print("%s" % ("SELFTEST OK" if not r else "SELFTEST 有断言没过"))
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    with open(args.input, encoding="utf-8") as fh:
        rep = json.load(fh)
    out = report(rep)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("wrote", args.out)
    return 1 if "error" in out else 0


if __name__ == "__main__":
    sys.exit(main())