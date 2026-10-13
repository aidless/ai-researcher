#!/usr/bin/env python3
"""W8 判读门：双臂都自己跑的**同源配对**设计（Faithful-CoT 程序执行 vs 匹配 few-shot CoT）。

与 W7 判读器的形状差异（门必须跟着设计走）：
  - W7 是单臂对文献固定锚 → 用精确二项；W8 两臂都是本机逐项数据且**逐题配对**
    （同模型/同 6-shot/同 n=100 子集）→ 噪声检验用 **McNemar 精确双侧**。
  - F vs C 是本项目第一次真正的**受控比较**（同源、配对）；对文献锚
    （code-davinci-002，0.723/0.633）仍是**量级测量**，不得说成受控/复现。
  - 机制拆分为**描述性**：C 臂错题拆「无答案抽取失败」vs「有答案算错」，
    F 臂拆「执行失败」vs「程序算错」——只报拆分，不做机制形式检验。

裁决优先级与 critic 一致：scope fail 或 caliber fail ⇒ fail；
重算不过 或 配对差不显著 ⇒ insufficient；全过 ⇒ pass。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
from ai_researcher.critic import gate_scope_discipline  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "w8", os.path.join(ROOT, "ai-researcher", "scripts", "w8_faithful_cot.py"))
w8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w8)

ALPHA = 0.05
REQUIRED_IN_CLAIM = ("0.6B", "配对", "量级测量")
FORBIDDEN_IN_CLAIM = ("复现", "达到锚", "超过锚")


def load_pairs(items_path: str) -> list[dict]:
    rows = [json.loads(l) for l in open(items_path, encoding="utf-8") if l.strip()]
    for r in rows:
        if not isinstance(r.get("f"), dict) or not isinstance(r.get("c"), dict):
            raise ValueError(f"第 {r.get('i')} 行缺完整双臂（F/C 必须都在才能判读）")
    if len({r["i"] for r in rows}) != len(rows):
        raise ValueError("行号重复")
    return rows


def recompute(items_path: str, summary: dict) -> dict:
    """从逐项配对证据重算全部头条数字；与 summary 不一致=重算门不过。"""
    rows = load_pairs(items_path)
    n = len(rows)
    kf = sum(1 for r in rows if r["f"]["correct"] is True)
    kc = sum(1 for r in rows if r["c"]["correct"] is True)
    b = sum(1 for r in rows if r["f"]["correct"] is True and r["c"]["correct"] is False)
    c = sum(1 for r in rows if r["f"]["correct"] is False and r["c"]["correct"] is True)
    lo_f, hi_f = w8.wilson(kf, n)
    lo_c, hi_c = w8.wilson(kc, n)
    p = w8.mcnemar_two_sided(b, c)
    got = {
        # 注意：真实 summary 契约没有顶层 n（n 只在 arm_f/arm_c/pairing_with_w7 里），
        # 判读器不得虚构契约键——顶层样本量用 pairing_with_w7.n_ours 交叉核对。
        "arm_f": {"n": n, "n_correct": kf, "acc": round(kf / n, 4),
                  "wilson95": [round(lo_f, 4), round(hi_f, 4)],
                  "n_unparsed": sum(1 for r in rows if r["f"]["how"] in
                                    ("unparsed", "exec_timeout", "exec_error", "no_number_in_stdout")),
                  "n_truncated": sum(1 for r in rows if r["f"]["truncated"])},
        "arm_c": {"n": n, "n_correct": kc, "acc": round(kc / n, 4),
                  "wilson95": [round(lo_c, 4), round(hi_c, 4)],
                  "n_unparsed": sum(1 for r in rows if r["c"]["how"] == "unparsed"),
                  "n_truncated": sum(1 for r in rows if r["c"]["truncated"])},
        "paired_f_vs_c": {"b_f_right_c_wrong": b, "c_f_wrong_c_right": c,
                          "n_discordant": b + c,
                          "p_exact_two_sided": round(p, 6)},
        "gap_to_anchor": {"f_vs_0.723": round(kf / n - w8.ANCHOR_F, 4),
                          "c_vs_0.633": round(kc / n - w8.ANCHOR_C, 4)},
    }
    diffs = {}
    for k, v in got.items():
        if k in ("arm_f", "arm_c"):
            for kk, vv in v.items():
                if summary.get(k, {}).get(kk) != vv:
                    diffs[f"{k}.{kk}"] = (summary.get(k, {}).get(kk), vv)
        elif summary.get(k) != v:
            diffs[k] = (summary.get(k), v)
    # 与 W7 的 gold 序列配对校验（同子集声明必须可验证）
    w7_items = os.path.join(os.path.dirname(items_path), "w7_gsm8k_anchor_items.jsonl")
    if os.path.exists(w7_items):
        w7_golds = [json.loads(l)["gold"] for l in open(w7_items, encoding="utf-8") if l.strip()]
        our = [r["gold"] for r in rows]
        if not (len(w7_golds) == len(our) and
                all(abs(x - y) < 1e-9 for x, y in zip(w7_golds, our))):
            diffs["pairing_with_w7"] = ("matched", "gold 序列不一致")
    # 顶层样本量交叉核对（真实契约字段）
    pw = summary.get("pairing_with_w7") or {}
    if pw and pw.get("n_ours") != n:
        diffs["pairing_with_w7.n_ours"] = (pw.get("n_ours"), n)
    return {"ok": not diffs, "recomputed": got, "diffs": diffs}


def caliber_in_claim(claim: str) -> dict:
    stripped = claim
    for w in FORBIDDEN_IN_CLAIM:
        stripped = re.sub(r"(?:非|而非|并非|不是)%s" % re.escape(w), "", stripped)
    missing = [w for w in REQUIRED_IN_CLAIM if w not in stripped]
    hit = [w for w in FORBIDDEN_IN_CLAIM if w in stripped]
    ok = not missing and not hit
    return {"pass": ok,
            "reason": "" if ok else
            ("结论缺口径自声明 %s" % missing if missing else
             "结论含口径越界词 %s" % hit),
            "note": "F vs C 允许称受控比较（同源配对）；对锚只许量级测量"}


def mechanism_breakdown(rows: list[dict]) -> dict:
    """描述性拆分（不做形式检验）：两臂各自的失败形态。"""
    f_exec_fail = sum(1 for r in rows if r["f"]["how"] in
                      ("unparsed", "exec_timeout", "exec_error", "no_number_in_stdout"))
    f_wrong_num = sum(1 for r in rows if r["f"]["correct"] is False and r["f"]["how"] == "exec")
    c_no_ans = sum(1 for r in rows if r["c"]["correct"] is False and r["c"]["pred"] is None)
    c_wrong_num = sum(1 for r in rows if r["c"]["correct"] is False and r["c"]["pred"] is not None)
    return {"f_执行失败": f_exec_fail, "f_程序算错": f_wrong_num,
            "c_无答案": c_no_ans, "c_有答案算错": c_wrong_num,
            "note": "描述性拆分，不构成机制形式检验"}


def judge(claim: str, measured_scope: str, items_path: str,
          summary_path: str) -> dict:
    summary = json.load(open(summary_path, encoding="utf-8"))
    rec = recompute(items_path, summary)
    scope = gate_scope_discipline(claim, measured_scope)
    cal = caliber_in_claim(claim)
    rows = load_pairs(items_path)
    p = rec["recomputed"]["paired_f_vs_c"]["p_exact_two_sided"]
    b = rec["recomputed"]["paired_f_vs_c"]["b_f_right_c_wrong"]
    c = rec["recomputed"]["paired_f_vs_c"]["c_f_wrong_c_right"]
    noise_ok = p < ALPHA
    mech = mechanism_breakdown(rows)
    mech_assert = ("消除" in claim or "解决" in claim) and ("算术" in claim or "格式" in claim)
    if mech_assert and c is not None and mech["c_有答案算错"] == 0 and mech["c_无答案"] > 0:
        mech_pass, mech_reason = False, "主张称程序执行消除算术错误，但 C 臂输的题没有一题是『有答案算错』"
    else:
        mech_pass, mech_reason = None, "描述性拆分已附（不构成机制形式检验）"
    gates = {
        "recomputable": {"pass": rec["ok"], "diffs": rec["diffs"],
                         "recomputed": rec["recomputed"]},
        "effect_vs_noise_paired": {
            "pass": noise_ok,
            "reason": "" if noise_ok else
            f"McNemar 精确双侧 p={p:.4g} ≥ {ALPHA}，配对差不可区分（insufficient：只报数字）",
            "test": f"2·P(X≤{min(b, c)}|n_d={b + c},0.5), b={b}, c={c}",
            "p_value": p},
        "scope_discipline": scope,
        "caliber_in_claim": cal,
        "mechanism_alignment": {"pass": mech_pass, "reason": mech_reason,
                                "breakdown": mech},
    }
    if scope["pass"] is False or cal["pass"] is False or mech_pass is False:
        verdict = "fail"
    elif not rec["ok"] or not noise_ok:
        verdict = "insufficient"
    else:
        verdict = "pass"
    return {"claim": claim, "measured_scope": measured_scope,
            "verdict": verdict, "gates": gates,
            "design_note": "双臂同源配对（本机逐项）；F vs C=受控比较，"
                           "对文献锚=量级测量；门形状按设计适配"}


def build_claim(rec_got: dict) -> tuple[str, bool]:
    """从重算数字生成结论（结论只能从证据来，不许手写漂移）。
    返回 (claim, directional)。"""
    f, c = rec_got["arm_f"], rec_got["arm_c"]
    pr = rec_got["paired_f_vs_c"]
    gap = rec_got["gap_to_anchor"]
    directional = pr["p_exact_two_sided"] < ALPHA
    if not directional:
        dir_sen = (f"配对差 b={pr['b_f_right_c_wrong']}/c={pr['c_f_wrong_c_right']} "
                   f"McNemar 精确双侧 p={pr['p_exact_two_sided']}，"
                   "不显著——只报数字不下方向性结论")
    else:
        who = "程序执行臂优于匹配 CoT 臂" if pr["b_f_right_c_wrong"] > pr["c_f_wrong_c_right"] \
            else "匹配 CoT 臂优于程序执行臂"
        dir_sen = (f"配对差 b={pr['b_f_right_c_wrong']}/c={pr['c_f_wrong_c_right']}，"
                   f"McNemar 精确双侧 p={pr['p_exact_two_sided']}，在此设置下 {who}")
    claim = (
        "本实验迷你口径实测：Qwen3-0.6B 同源配对（同 6-shot 自编 exemplar、同 n=100 GSM8K "
        "子集 seed 20261003、CPU 贪心、截断计错）：程序执行臂 acc="
        f"{f['acc']}（CI {f['wilson95'][0]}~{f['wilson95'][1]}），"
        f"匹配 few-shot CoT 臂 acc={c['acc']}（CI {c['wilson95'][0]}~{c['wilson95'][1]}）。"
        f"{dir_sen}。对文献锚（code-davinci-002，不同源）为量级测量非受控比较："
        f"程序执行臂 0.723 差 {gap['f_vs_0.723']}，CoT 臂 0.633 差 {gap['c_vs_0.633']}。"
        f"F 臂执行失败 {f['n_unparsed']}、截断 {f['n_truncated']}；"
        f"C 臂无答案 {c['n_unparsed']}、截断 {c['n_truncated']}。")
    return claim, directional


def selftest() -> int:
    bad = []
    ck = lambda name, got, want: bad.append(f"{name}: got {got!r} want {want!r}") \
        if got != want else None
    import tempfile
    # ── 夹具：100 题配对，both=57, f_only=15, c_only=3, neither=25 ──
    def mk(bv, cv, both):
        rows = []
        i = 0
        for _ in range(both):
            rows.append((True, True)); i += 1
        for _ in range(bv):
            rows.append((True, False)); i += 1
        for _ in range(cv):
            rows.append((False, True)); i += 1
        while i < 100:
            rows.append((False, False)); i += 1
        out = []
        for idx, (fr, cr) in enumerate(rows, 1):
            out.append({"i": idx, "gold": 1.0 * idx,
                        "f": {"pred": 1.0, "how": "exec", "correct": fr,
                              "truncated": False, "n_new_tokens": 30, "sec": 90.0,
                              "exec_ms": 5, "code_tail": "print(1)"},
                        "c": {"pred": (1.0 if cr else None),
                              "how": ("hash" if cr else "unparsed"),
                              "correct": cr, "truncated": False,
                              "n_new_tokens": 200, "sec": 80.0,
                              "raw_tail": ("#### 1" if cr else "…无答案…")}})
        return out

    def write_items(td, rows, name="i.jsonl"):
        p = os.path.join(td, name)
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return p

    def mk_summary(rows, b, c):
        n = len(rows)
        kf = sum(1 for r in rows if r["f"]["correct"])
        kc = sum(1 for r in rows if r["c"]["correct"])
        fu = sum(1 for r in rows if r["f"]["how"] in
                 ("unparsed", "exec_timeout", "exec_error", "no_number_in_stdout"))
        cu = sum(1 for r in rows if r["c"]["how"] == "unparsed")
        lof, hif = w8.wilson(kf, n); loc, hic = w8.wilson(kc, n)
        return {"arm_f": {"n": n, "n_correct": kf, "acc": round(kf / n, 4),
                          "wilson95": [round(lof, 4), round(hif, 4)],
                          "n_unparsed": fu, "n_truncated": 0, "sec_mean": 90.0},
                "arm_c": {"n": n, "n_correct": kc, "acc": round(kc / n, 4),
                          "wilson95": [round(loc, 4), round(hic, 4)],
                          "n_unparsed": cu, "n_truncated": 0, "sec_mean": 80.0},
                "paired_f_vs_c": {"b_f_right_c_wrong": b, "c_f_wrong_c_right": c,
                                  "n_discordant": b + c,
                                  "p_exact_two_sided": round(w8.mcnemar_two_sided(b, c), 6)},
                "gap_to_anchor": {"f_vs_0.723": round(kf / n - 0.723, 4),
                                  "c_vs_0.633": round(kc / n - 0.633, 4)},
                "pairing_with_w7": {"matched": True, "n_w7": n, "n_ours": n}}

    with tempfile.TemporaryDirectory() as td:
        # 需要 w7 items 才能跳过配对校验——放一份一致的
        with open(os.path.join(td, "w7_gsm8k_anchor_items.jsonl"), "w") as fh:
            for idx in range(1, 101):
                fh.write(json.dumps({"i": idx, "gold": 1.0 * idx}) + "\n")

        rows = mk(15, 3, 57)
        items_p = write_items(td, rows)
        summ = mk_summary(rows, 15, 3)
        rec = recompute(items_p, summ)
        ck("干净数据重算过", rec["ok"], True)
        ck("配对 p 值", rec["recomputed"]["paired_f_vs_c"]["p_exact_two_sided"], 0.007538)
        claim, directional = build_claim(rec["recomputed"])
        ck("方向性成立", directional, True)
        rep = judge(claim, "0.6B 双臂 n=100 seed 20261003", items_p,
                    write_items(td, [], "s.json") if False else _dump(td, summ))
        ck("全绿判 pass", rep["verdict"], "pass")

        # ── 不显著 ⇒ insufficient（不是 fail）──
        rows2 = mk(15, 7, 55)   # p=0.1338
        items2 = write_items(td, rows2, "i2.jsonl")
        summ2 = mk_summary(rows2, 15, 7)
        rec2 = recompute(items2, summ2)
        ck("弱差重算过", rec2["ok"], True)
        claim2, dir2 = build_claim(rec2["recomputed"])
        ck("弱差无方向", dir2, False)
        rep2 = judge(claim2, "0.6B 双臂 n=100", items2, _dump(td, summ2))
        ck("不显著=insufficient", rep2["verdict"], "insufficient")

        # ── 篡改 acc ⇒ 重算门抓 ──
        summ_t = dict(summ)
        summ_t["arm_f"] = dict(summ["arm_f"], acc=0.999)
        rep3 = judge(claim, "0.6B", items_p, _dump(td, summ_t))
        ck("篡改被抓", rep3["gates"]["recomputable"]["pass"], False)
        ck("篡改判 fail/insufficient", rep3["verdict"], "insufficient")

        # ── 顶层样本量契约（真实形状字段）：pairing n_ours 篡改 ⇒ 抓 ──
        summ_p2 = dict(summ)
        summ_p2["pairing_with_w7"] = dict(summ["pairing_with_w7"], n_ours=99)
        rec_t2 = recompute(items_p, summ_p2)
        ck("n_ours 篡改被抓", rec_t2["ok"], False)
        ck("n_ours diff 键", "pairing_with_w7.n_ours" in rec_t2["diffs"], True)
        ck("夹具无虚构顶层n", "n" not in summ, True)

        # ── 配对行缺 c 臂 ⇒ 拒载 ──
        bad_rows = [dict(rows[0], c=None)]
        with open(os.path.join(td, "bad.jsonl"), "w") as fh:
            fh.write(json.dumps(bad_rows[0]) + "\n")
        try:
            load_pairs(os.path.join(td, "bad.jsonl"))
            bad.append("缺 c 臂应抛错")
        except ValueError:
            pass

        # ── 口径门 ──
        ck("口径缺配对声明", caliber_in_claim("0.6B 双臂差异 0.007538 量级测量")["pass"], False)
        ck("口径含复现词", caliber_in_claim("0.6B 配对 复现了 0.723 量级测量")["pass"], False)
        ck("口径合格", caliber_in_claim("0.6B 配对比较；对锚量级测量")["pass"], True)
        # ── scope 门复用 ──
        ck("scope 越界", gate_scope_discipline("该方法普遍解决数学问题", "")["pass"], False)
        # ── 机制门：主张消除算术错但拆分为 0 ⇒ fail ──
        rep4 = judge("0.6B 配对：程序执行消除了算术格式错误 量级测量",
                     "0.6B", items_p, _dump(td, summ))
        ck("机制主张无拆分支撑=fail", rep4["gates"]["mechanism_alignment"]["pass"], False)
        ck("机制 fail 判 fail", rep4["verdict"], "fail")

    print(f"selftest: 失败 {len(bad)}")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def _dump(td, obj):
    p = os.path.join(td, "summary_dump.json")
    json.dump(obj, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    store = os.path.join(ROOT, "ai-researcher", "store")
    items = os.path.join(store, "w8_faithful_cot_items.jsonl")
    summ_p = os.path.join(store, "w8_faithful_cot_summary.json")
    if not (os.path.exists(items) and os.path.exists(summ_p)):
        print("缺产物（两臂必须都完成才可判读）")
        return 2
    summary = json.load(open(summ_p, encoding="utf-8"))
    rec = recompute(items, summary)
    if not rec["ok"]:
        print("重算门不过：", rec["diffs"])
        return 1
    claim, directional = build_claim(rec["recomputed"])
    scope_txt = ("Qwen3-0.6B 双臂（程序执行 vs 匹配 few-shot CoT）；GSM8K test n=100 "
                 "seed 20261003；CPU 贪心 max_new_tokens=384；6 个自编 exemplar；"
                 "锚为 code-davinci-002 已发表固定点（不同源）")
    rep = judge(claim, scope_txt, items, summ_p)
    out = os.path.join(store, "w8_critic_verdict.json")
    json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("claim:", claim)
    print("verdict:", rep["verdict"])
    for g, d in rep["gates"].items():
        print(f"  {g}: pass={d['pass']} {d.get('reason', '')[:80]}")
    print("wrote", out)
    return 0 if rep["verdict"] in ("pass", "insufficient") else 1


if __name__ == "__main__":
    sys.exit(main())
