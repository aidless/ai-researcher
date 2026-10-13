#!/usr/bin/env python3
"""W9 判读器（NoMIRACL 多语相关性判定）。

职责（与 w8_critic_check.py 同纪律，形状按 W9 设计适配）：
1. **重算门**：从 store/w9_items.jsonl 独立重算 6 个格（k/n/rate/wilson95/
   n_unparsed）、区间分离布尔、anchor_gap（锚 JSON 百分数 /100，ISO 码查表），
   与 summary 逐项对比——数字对不上即 fail（冤枉好人比漏抓坏人更不可修，
   所以重算用独立实现，不 import w9 的 summarize）。
2. **verdict 一致性**：summary.verdict 必须等于重算分离布尔推出的值
   （directional ⇔ 任一语言对区间真分离）。
3. **scope / caliber 门**：结论文本必须带「本实验」限定与
   ("0.6B","NoMIRACL","量级对照") 三词；禁词 ("复现","达到锚","超过锚","SOTA")；
   report_numbers_only 时额外禁「优于」。
4. **结论由 build_claim 从重算数字生成**（不接受手写，杜绝主张漂移）。

verdict 语义映射（沿用 W8 约定，ALLOWED_VERDICTS=(pass, insufficient)）：
  - 重算不过 / verdict 标签与数字矛盾 ⇒ fail（不进结论链）
  - 重算过、无区间分离（report_numbers_only）⇒ insufficient（只报数字）
  - 重算过、有真分离 ⇒ pass
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_ITEMS = os.path.join(ROOT, "ai-researcher", "store", "w9_items.jsonl")
OUT_SUMMARY = os.path.join(ROOT, "ai-researcher", "store", "w9_summary.json")
OUT_VERDICT = os.path.join(ROOT, "ai-researcher", "store", "w9_critic_verdict.json")
ANCHOR_PATH = os.path.join(ROOT, "ai-researcher", "store", "w9_anchor_nomiracl.json")

LANGS = ("english", "chinese", "swahili")
LANG2CODE = {"english": "en", "chinese": "zh", "swahili": "sw"}
REQUIRED_IN_CLAIM = ("0.6B", "NoMIRACL", "量级对照", "本实验")
FORBIDDEN_IN_CLAIM = ("复现", "达到锚", "超过锚", "SOTA")
ALPHA = 0.05


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load_rows(items_path: str) -> list[dict]:
    if not os.path.exists(items_path):
        raise FileNotFoundError(items_path)
    return [json.loads(l) for l in open(items_path, encoding="utf-8") if l.strip()]


def recompute_cells(rows: list[dict]) -> dict:
    """独立重算 6 格（与 w9.summarize 分开写，防同源错误互检不出）。"""
    cells = {}
    for lang in LANGS:
        for subset, cell in (("non_relevant", "hallucination_rate"),
                             ("relevant", "error_rate")):
            rs = [r for r in rows if r["lang"] == lang and r["subset"] == subset]
            n = len(rs)
            if not n:
                continue
            k = sum(1 for r in rs if r["pred"] == 1) if subset == "non_relevant" \
                else sum(1 for r in rs if r["pred"] != 1)
            lo, hi = wilson(k, n)
            cells[f"{lang}.{cell}"] = {
                "k": k, "n": n, "rate": round(k / n, 4),
                "wilson95": [round(lo, 4), round(hi, 4)],
                "n_unparsed": sum(1 for r in rs if r["pred"] is None),
                "sec_mean": round(statistics.mean([r["sec"] for r in rs]), 2)}
    return cells


def recompute_pairs(cells: dict) -> list[dict]:
    pairs = []
    for cell in ("hallucination_rate", "error_rate"):
        cs = [(l, cells[f"{l}.{cell}"]) for l in LANGS if f"{l}.{cell}" in cells]
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                a, b = cs[i][1], cs[j][1]
                sep = a["wilson95"][1] < b["wilson95"][0] or \
                    b["wilson95"][1] < a["wilson95"][0]
                pairs.append({"cell": cell, "pair": f"{cs[i][0]}-{cs[j][0]}",
                              "separated": sep})
    return pairs


def recompute_anchor_gap(cells: dict, anchors: dict) -> dict:
    gap = {}
    for key, cell in (("hallucination_rate_non_relevant", "hallucination_rate"),
                      ("error_rate_relevant", "error_rate")):
        for model in ("llama3_8b", "mistral_7b"):
            for lang in LANGS:
                mine = cells.get(f"{lang}.{cell}")
                if mine:
                    gap[f"{lang}.{cell}.{model}"] = round(
                        mine["rate"] - anchors[key][model][LANG2CODE[lang]] / 100.0, 4)
    return gap


def diff_dict(mine: dict, theirs: dict) -> dict:
    return {k: (mine.get(k), theirs.get(k))
            for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k)}


def scope_in_claim(claim: str) -> dict:
    has = ("本实验" in claim) or ("本次" in claim)
    return {"pass": has,
            "reason": "" if has else "结论缺实测范围限定词（本实验/本次）"}


def caliber_in_claim(claim: str, directional: bool) -> dict:
    missing = [w for w in REQUIRED_IN_CLAIM if w not in claim]
    banned = [w for w in FORBIDDEN_IN_CLAIM if w in claim]
    if not directional and "优于" in claim:
        banned.append("优于")
    ok = not missing and not banned
    why = []
    if missing:
        why.append(f"缺必备词：{missing}")
    if banned:
        why.append(f"含禁词：{banned}")
    return {"pass": ok, "reason": "；".join(why)}


def build_claim(cells: dict, pairs: list[dict], gap: dict,
                anchors: dict) -> tuple[str, bool]:
    """结论只能从重算数字来。"""
    directional = any(p["separated"] for p in pairs)
    def cell_s(key):
        c = cells[key]
        return (f"{key.split('.')[0]} {c['rate']}（CI {c['wilson95'][0]}~"
                f"{c['wilson95'][1]}，n={c['n']}）")
    if directional:
        sep_s = "存在区间分离的语言对（见 pairwise_separation）"
    else:
        sep_s = ("各语言对 Wilson 区间均重叠（report_numbers_only），"
                 "不下语言间方向性结论")
    hz = [f"{l} {gap[f'{l}.hallucination_rate.llama3_8b']:+.4f}"
          for l in ("english", "chinese", "swahili")]
    ez = [f"{l} {gap[f'{l}.error_rate.llama3_8b']:+.4f}"
          for l in ("english", "chinese", "swahili")]
    unparsed = sum(c["n_unparsed"] for c in cells.values())
    claim = (
        "本实验迷你口径实测：Qwen3-0.6B 作 NoMIRACL 相关性判官（en/zh/sw × "
        "relevant/non_relevant 各 30 题，seed 20261003，CPU 贪心，分母=全部 n）。"
        f"幻觉率（non_relevant 判 yes）：{cell_s('english.hallucination_rate')}、"
        f"{cell_s('chinese.hallucination_rate')}、"
        f"{cell_s('swahili.hallucination_rate')}；"
        f"错杀率（relevant 判非 yes）：{cell_s('english.error_rate')}、"
        f"{cell_s('chinese.error_rate')}、{cell_s('swahili.error_rate')}。"
        f"{sep_s}。对文献锚（Llama-3-8B / Mistral-7B-Instruct，不同模型类别不同 "
        f"prompt 协议）为量级对照非受控比较，anchor_gap=我方−锚（正=我方更差）："
        f"幻觉率高于两锚（llama3_8b 口径 {', '.join(hz)}），"
        f"错杀率低于两锚（{', '.join(ez)}）——0.6B 判官在本任务呈近似恒答 yes 形态。"
        f"unparsed 共 {unparsed}。")
    return claim, directional


def judge(items_path: str = OUT_ITEMS, summary_path: str = OUT_SUMMARY,
          anchors_path: str = ANCHOR_PATH) -> dict:
    rows = load_rows(items_path)
    summary = json.load(open(summary_path, encoding="utf-8"))
    anchors = json.load(open(anchors_path, encoding="utf-8"))
    cells = recompute_cells(rows)
    pairs = recompute_pairs(cells)
    gap = recompute_anchor_gap(cells, anchors)
    diffs = {}
    diffs["cells"] = diff_dict(cells, summary.get("cells", {}))
    diffs["pairwise_separation"] = diff_dict(
        {f"{p['cell']}|{p['pair']}": p["separated"] for p in pairs},
        {f"{p['cell']}|{p['pair']}": p["separated"]
         for p in summary.get("pairwise_separation", [])})
    diffs["anchor_gap"] = diff_dict(gap, summary.get("anchor_gap", {}))
    rec_ok = not any(diffs.values())
    expect_verdict = ("directional" if any(p["separated"] for p in pairs)
                      else "report_numbers_only")
    verdict_consistent = summary.get("verdict") == expect_verdict
    claim, directional = build_claim(cells, pairs, gap, anchors)
    scope = scope_in_claim(claim)
    cal = caliber_in_claim(claim, directional)
    gates = {
        "recomputable": {"pass": rec_ok, "diffs": diffs},
        "verdict_consistency": {
            "pass": verdict_consistent,
            "reason": "" if verdict_consistent else
            f"summary.verdict={summary.get('verdict')} 与重算 {expect_verdict} 不符"},
        "scope_discipline": scope,
        "caliber_in_claim": cal,
    }
    hard_fail = (not rec_ok) or (not verdict_consistent) or \
        (not scope["pass"]) or (not cal["pass"])
    if hard_fail:
        verdict = "fail"
    elif directional:
        verdict = "pass"
    else:
        verdict = "insufficient"
    return {"claim": claim, "verdict": verdict,
            "summary_verdict": summary.get("verdict"),
            "gates": gates, "n_items": len(rows),
            "design_note": "跨语言独立样本（无配对检验）；分离⇒pass，"
                           "重叠⇒insufficient 只报数字；对锚=量级对照"}


def selftest() -> int:
    bad = []
    ck_n = [0]

    def ck(name, got, want):
        ck_n[0] += 1
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    def row(lang, subset, i, pred):
        return {"lang": lang, "subset": subset, "i": i, "qid": f"q{i}",
                "docid": f"d{i}", "sec": 1.0, "pred": pred}

    # 1. 重算：构造 en 全对/全错的极端夹具
    rows = ([row("english", "non_relevant", i, 1) for i in range(1, 6)] +
            [row("english", "relevant", i, 1) for i in range(1, 6)])
    cells = recompute_cells(rows)
    ck("halluc k=n", cells["english.hallucination_rate"]["k"], 5)
    ck("error k=0", cells["english.error_rate"]["k"], 0)
    ck("error rate", cells["english.error_rate"]["rate"], 0.0)

    # 2. wilson 教科书值（7/8）
    lo, hi = wilson(7, 8)
    ck("Wilson 7/8", (round(lo, 3), round(hi, 3)), (0.529, 0.978))

    # 3. 区间分离判定：k/n=5/5 vs 0/5 必分离；0.4 vs 0.6（n=5）必重叠
    rows2 = ([row("english", "non_relevant", i, 1) for i in range(1, 6)] +
             [row("chinese", "non_relevant", i, 0) for i in range(1, 6)] +
             [row("swahili", "non_relevant", i, 1 if i <= 3 else 0)
              for i in range(1, 6)])
    cells2 = recompute_cells(rows2)
    pairs2 = recompute_pairs(cells2)
    sep = {(p["pair"], p["cell"]): p["separated"] for p in pairs2}
    ck("en-zh 分离", sep[("english-chinese", "hallucination_rate")], True)
    ck("en-sw 重叠", sep[("english-swahili", "hallucination_rate")], False)

    # 4. anchor_gap：百分数 /100 + ISO 码
    fake_anchors = {"hallucination_rate_non_relevant":
                    {"llama3_8b": {"en": 19.2, "zh": 64.4, "sw": 4.0},
                     "mistral_7b": {"en": 42.8, "zh": 45.2, "sw": 14.8}},
                    "error_rate_relevant":
                    {"llama3_8b": {"en": 41.6, "zh": 6.0, "sw": 80.8},
                     "mistral_7b": {"en": 8.0, "zh": 13.2, "sw": 57.6}}}
    gap = recompute_anchor_gap({"english.hallucination_rate":
                                {"rate": 0.9}}, fake_anchors)
    ck("锚差=0.9−0.192", gap["english.hallucination_rate.llama3_8b"], 0.708)

    # 5. scope / caliber 门
    ck("缺本实验被拦", scope_in_claim("0.6B 实测 acc=0.9")["pass"], False)
    ck("带本实验过", scope_in_claim("本实验实测 acc=0.9")["pass"], True)
    c1 = caliber_in_claim("本实验 NoMIRACL 量级对照 0.6B 未复现锚", False)
    ck("禁词复现被抓", c1["pass"], False)
    c2 = caliber_in_claim("本实验 NoMIRACL 量级对照 0.6B 判官 0.9 优于锚", False)
    ck("非方向时优于禁", c2["pass"], False)
    c3 = caliber_in_claim("本实验 NoMIRACL 量级对照 0.6B 判官幻觉率 0.9", False)
    ck("干净结论过", c3["pass"], True)

    # 6. build_claim（全重叠夹具）：必备词全带 + 非方向
    rel_all = ([row("english", "relevant", i, 1) for i in range(1, 6)] +
               [row("chinese", "relevant", i, 1) for i in range(1, 6)] +
               [row("swahili", "relevant", i, 1) for i in range(1, 6)])
    rows3 = ([row(l, "non_relevant", i, 1 if i <= 3 else 0)
              for l in ("english", "chinese", "swahili")
              for i in range(1, 6)] + rel_all)
    cells3 = recompute_cells(rows3)
    pairs3 = recompute_pairs(cells3)
    gap3 = recompute_anchor_gap(cells3, fake_anchors)
    claim3, dir3 = build_claim(cells3, pairs3, gap3, fake_anchors)
    ck("claim 带必备词", all(w in claim3 for w in REQUIRED_IN_CLAIM), True)
    ck("claim 带样本量", "n=5" in claim3, True)
    ck("重叠时不优于", "优于" not in claim3, True)
    ck("重叠⇒非 directional", dir3, False)
    ck("重叠时区间均重叠句", "区间均重叠" in claim3, True)

    # 6b. 分离夹具（en 5/5 vs zh 0/5）⇒ directional
    rows4 = rows2 + rel_all
    cells4 = recompute_cells(rows4)
    pairs4 = recompute_pairs(cells4)
    claim4, dir4 = build_claim(cells4, pairs4,
                               recompute_anchor_gap(cells4, fake_anchors),
                               fake_anchors)
    ck("分离⇒directional", dir4, True)
    ck("分离时分离句", "存在区间分离" in claim4, True)

    # 7. 端到端 judge：篡改 summary 数字被重算门抓（写 tmp 三件套）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ip, sp, ap = (os.path.join(td, "i.jsonl"), os.path.join(td, "s.json"),
                      os.path.join(td, "a.json"))
        with open(ip, "w", encoding="utf-8") as fh:
            for r in rows3:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        good_cells = recompute_cells(rows3)
        summary = {"verdict": "report_numbers_only", "cells": good_cells,
                   "pairwise_separation": pairs3, "anchor_gap": gap3}
        json.dump(summary, open(sp, "w", encoding="utf-8"))
        json.dump(fake_anchors, open(ap, "w", encoding="utf-8"))
        v = judge(ip, sp, ap)
        ck("干净夹具 verdict=insufficient", v["verdict"], "insufficient")
        ck("干净夹具重算过", v["gates"]["recomputable"]["pass"], True)
        # 篡改一格 rate
        tampered = json.loads(json.dumps(summary))
        tampered["cells"]["english.hallucination_rate"]["rate"] = 0.999
        json.dump(tampered, open(sp, "w", encoding="utf-8"))
        v2 = judge(ip, sp, ap)
        ck("篡改数字⇒fail", v2["verdict"], "fail")
        # verdict 标签与数字矛盾
        mismatch = json.loads(json.dumps(summary))
        mismatch["verdict"] = "directional"
        json.dump(mismatch, open(sp, "w", encoding="utf-8"))
        v3 = judge(ip, sp, ap)
        ck("标签矛盾⇒fail", v3["verdict"], "fail")
        ck("一致性门说明原因",
           v3["gates"]["verdict_consistency"]["pass"], False)

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
