#!/usr/bin/env python3
"""W7 判读门：把 L4 critic 的纪律适配到「单臂测量 vs 已发表固定锚」设计。

为什么不用 critic.adjudicate()：它要求 test/control 两个**逐项 Arm**，而锚
（MathCoder 0.838~0.907）是已发表聚合数，没有逐项数据——硬造 control Arm
就是编造证据。单臂对固定点的正统噪声检验是**精确二项检验**，本脚本用它，
并明确记录「双臂门不适用」的理由，而不是静默跳过。

四门适配：
  recomputable   逐项重算（100 行 correct 标志 → acc/CI/gap 必须与 summary 一致）
  effect_vs_noise 精确二项 P(X≤k | n, p=锚下界) < 0.05（单臂设计匹配的检验）
  scope_discipline 复用 critic.gate_scope_discipline（结论不得盖过实测范围）
  caliber_in_claim 结论必须自声明口径（0.6B 纯 prompt vs 7B 级锚、不同源、量级测量）
  mechanism      不适用（本主张不断言机制）——显式记录，不静默

裁决优先级与 critic 一致：scope fail ⇒ fail；重算/噪声不过 ⇒ insufficient；
全过 ⇒ pass。
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
from ai_researcher.critic import gate_scope_discipline  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "w7", os.path.join(ROOT, "ai-researcher", "scripts", "w7_gsm8k_anchor.py"))
w7 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w7)

ANCHOR_LO = 0.838
REQUIRED_IN_CLAIM = ("0.6B", "不同源", "量级测量")
FORBIDDEN_IN_CLAIM = ("复现", "受控比较", "达到锚", "超过锚", "解决")
ALPHA = 0.05


def binom_cdf_le(k: int, n: int, p: float) -> float:
    """精确二项分布 P(X ≤ k)。log 空间求和，k<0 或 k≥n 走端点。"""
    if not (0 <= k <= n) or not (0.0 <= p <= 1.0):
        raise ValueError(f"binom_cdf_le 非法输入 k={k} n={n} p={p}")
    if k < 0:
        return 0.0
    if p >= 1.0:
        return 1.0
    if k >= n:
        return 1.0
    total = 0.0
    log_pmf_terms = []
    logc = 0.0  # log C(n,0)=0
    for i in range(0, k + 1):
        if i > 0:
            logc += math.log(n - i + 1) - math.log(i)
        lp = logc + i * math.log(p) + (n - i) * math.log1p(-p)
        log_pmf_terms.append(lp)
    m = max(log_pmf_terms)
    for lp in log_pmf_terms:
        total += math.exp(lp - m)
    return total * math.exp(m)


def recompute(items_path: str, summary: dict) -> dict:
    """从逐项证据重算头条数字；与 summary 不一致=重算门不过。"""
    rows = [json.loads(l) for l in open(items_path, encoding="utf-8") if l.strip()]
    n = len(rows)
    correct = sum(1 for r in rows if r["correct"] is True)
    acc = correct / n
    lo, hi = w7.wilson(correct, n)
    got = {"n": n, "n_correct": correct, "acc": round(acc, 4),
           "wilson95": [round(lo, 4), round(hi, 4)],
           "gap_to_anchor_lo": round(acc - ANCHOR_LO, 4),
           "n_unparsed": sum(1 for r in rows if r["how"] == "unparsed"),
           "n_truncated": sum(1 for r in rows if r["truncated"])}
    diffs = {k: (summary.get(k), v) for k, v in got.items()
             if summary.get(k) != v}
    return {"ok": not diffs, "recomputed": got, "diffs": diffs}


def caliber_in_claim(claim: str) -> dict:
    # 否定前缀豁免：先剥掉「非/而非/并非/不是 + 词」的否定形式再匹配——
    # 否则「非受控比较」会被当成「受控比较」误伤。
    stripped = claim
    for w in FORBIDDEN_IN_CLAIM:
        stripped = re.sub(r"(?:非|而非|并非|不是)%s" % re.escape(w), "", stripped)
    missing = [w for w in REQUIRED_IN_CLAIM if w not in stripped]
    hit_forbidden = [w for w in FORBIDDEN_IN_CLAIM if w in stripped]
    ok = not missing and not hit_forbidden
    return {"pass": ok,
            "reason": "" if ok else
            ("结论缺口径自声明 %s" % missing if missing else
             "结论含口径越界词 %s" % hit_forbidden)}


def judge(claim: str, measured_scope: str, items_path: str,
          summary_path: str) -> dict:
    summary = json.load(open(summary_path, encoding="utf-8"))
    rec = recompute(items_path, summary)
    scope = gate_scope_discipline(claim, measured_scope)
    cal = caliber_in_claim(claim)
    p = binom_cdf_le(summary["n_correct"], summary["n"], ANCHOR_LO)
    noise_ok = p < ALPHA
    gates = {
        "recomputable": {"pass": rec["ok"], "diffs": rec["diffs"],
                         "recomputed": rec["recomputed"]},
        "effect_vs_noise_single_arm": {
            "pass": noise_ok,
            "reason": "" if noise_ok else
            f"精确二项 p={p:.3g} ≥ {ALPHA}，差距不可区分",
            "test": f"P(X≤{summary['n_correct']}|n={summary['n']},p={ANCHOR_LO})",
            "p_value": p,
            "note": "单臂对固定锚的检验；双臂 Arm 门不适用（锚无逐项数据，"
                    "造 Arm 即编造）"},
        "scope_discipline": scope,
        "caliber_in_claim": cal,
        "mechanism_alignment": {
            "pass": None,
            "reason": "不适用：本主张是测量主张，不断言机制（显式记录，非静默跳过）"},
    }
    if scope["pass"] is False or cal["pass"] is False:
        verdict = "fail"
    elif not rec["ok"] or not noise_ok:
        verdict = "insufficient"
    else:
        verdict = "pass"
    return {"claim": claim, "measured_scope": measured_scope,
            "verdict": verdict, "gates": gates,
            "design_note": "单臂测量 vs 已发表固定锚；与 critic 双臂形状不同，"
                           "门形状按设计适配（见各 gate.note）"}


def selftest() -> int:
    bad = []
    ck = lambda name, got, want: bad.append(f"{name}: got {got!r} want {want!r}") \
        if got != want else None
    # ── 二项已知值：P(X≤50|100,0.5)=0.5398（含 X=50 点质量的半修正）；
    #    P(X≤49|100,0.5)=0.4602；P(X≤53|100,0.838) 应远小于 0.05 ──
    ck("二项对称点", round(binom_cdf_le(50, 100, 0.5), 4), 0.5398)
    ck("二项对称点-1", round(binom_cdf_le(49, 100, 0.5), 4), 0.4602)
    if not (0 <= binom_cdf_le(0, 100, 0.5) < 1e-30):
        bad.append("P(X≤0|100,0.5) 应≈0.5^100")
    ck("k=n 全概率", binom_cdf_le(100, 100, 0.838), 1.0)
    p_real = binom_cdf_le(53, 100, 0.838)
    if not p_real < 1e-8:
        bad.append(f"真实值 53/100 对 0.838 的尾部应 <1e-8，得 {p_real:.3g}")
    try:
        binom_cdf_le(101, 100, 0.5); bad.append("k>n 应抛错")
    except ValueError:
        pass
    # ── 重算门必须能抓篡改：翻一条 correct 就要现形 ──
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        items_p = os.path.join(td, "i.jsonl")
        rows = [{"correct": True, "how": "hash", "truncated": False}] * 53 + \
               [{"correct": False, "how": "hash", "truncated": False}] * 47
        with open(items_p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        # 夹具形状从真实 summary 抄全（L-ops-138 教训：缺键=夹具错，不是重算错）
        summ = {"n": 100, "n_correct": 53, "acc": 0.53,
                "wilson95": [0.4329, 0.6249], "gap_to_anchor_lo": -0.308,
                "n_unparsed": 0, "n_truncated": 0}
        good = recompute(items_p, summ)
        ck("干净数据重算过", good["ok"], True)
        rows[0] = {"correct": False, "how": "hash", "truncated": False}
        with open(items_p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        tam = recompute(items_p, summ)
        ck("篡改被重算抓到", tam["ok"], False)
        ck("篡改指认 n_correct", tam["diffs"].get("n_correct", (None, None))[1], 52)
        # summary 里没有 unparsed/truncated 字段时，重算多出的键也算 diff
        rows[0] = {"correct": True, "how": "unparsed", "truncated": True}
        with open(items_p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        tam2 = recompute(items_p, summ)
        ck("辅助字段缺失也算不一致", tam2["ok"], False)
    # ── 口径门：缺自声明/含越界词都要抓 ──
    ck("口径缺声明", caliber_in_claim("准确率 0.53 很好")["pass"], False)
    ck("口径越界词", caliber_in_claim("0.6B 复现了锚值")["pass"], False)
    ck("口径合格", caliber_in_claim(
        "0.6B 纯 prompt 与 7B 锚不同源，量级测量")["pass"], True)
    # ── scope 门复用：越界词必须抓 ──
    ck("scope 越界", gate_scope_discipline("该方法普遍解决了数学问题", "")["pass"], False)
    print(f"selftest: 失败 {len(bad)}")
    for b in bad:
        print("  FAIL", b)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    store = os.path.join(ROOT, "ai-researcher", "store")
    claim = (
        "迷你口径实测：Qwen3-0.6B 纯 prompt CoT 在 GSM8K test n=100"
        "（seed 20261003，CPU 贪心，截断计错）准确率 0.53，"
        "Wilson 95% CI [0.433, 0.625]；相对文献锚下界 0.838"
        "（MathCoder，7B 级微调+工具，与本实验不同源）差距 -0.308，"
        "精确二项检验 p<1e-8 且 CI 上界 0.625 仍低于锚下界——差距可区分。"
        "此为量级测量非受控比较：0.6B 纯 prompt 距前沿锚约 21~41 个百分点。"
        "unparsed=0，截断=5 计错。")
    measured_scope = ("Qwen3-0.6B 纯 prompt CoT；GSM8K test n=100 seed 20261003；"
                      "CPU 贪心 max_new_tokens=384；锚为文献固定点 0.838~0.907")
    rep = judge(claim, measured_scope,
                os.path.join(store, "w7_gsm8k_anchor_items.jsonl"),
                os.path.join(store, "w7_gsm8k_anchor_summary.json"))
    out = os.path.join(store, "w7_critic_verdict.json")
    json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("verdict:", rep["verdict"])
    for g, d in rep["gates"].items():
        print(f"  {g}: pass={d['pass']} {d.get('reason', '')[:80]}")
    print("wrote", out)
    return 0 if rep["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
