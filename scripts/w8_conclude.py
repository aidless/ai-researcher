#!/usr/bin/env python3
"""W8 收口驱动：判读通过后——状态机 已批→已跑→出结论 + writer 草稿。

设计约束（从本项目事故里学来的）：
  - 只在 w8_critic_verdict.json 存在且 verdict ∈ {pass, insufficient} 时才动
    状态机（verdict=fail ⇒ 不迁移，先修实验或修主张）。
  - 状态迁移用 ai_researcher.store.transition()（四道门原样生效），
    新对象回填列表 + report(entries) 重算（复刻「纯函数返回值没放回列表」
    事故的修法），整文件自洽落盘。
  - 草稿由 writer.draft() 生成：出结论之后才能起草；数字全部要在
    summary+verdict 数值池里，否则 writer 自己会拒。
  - 幂等安全：state 不是「已批」⇒ 拒绝（不自动续跑迁移），明说原因。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
import ai_researcher.store as st          # noqa: E402
import ai_researcher.writer as wr         # noqa: E402

TARGET_ID = "2301.13379v3"
ALLOWED_VERDICTS = ("pass", "insufficient")


def load_verdict(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺判读产物 {path}（先跑 w8_critic_check.py）")
    return json.load(open(path, encoding="utf-8"))


def flip_state(state_path: str, frm: str, to: str, reason: str,
               actor: str = "agent_w8_conclude",
               log_path: str | None = None) -> str:
    d = json.load(open(state_path, encoding="utf-8"))
    entries = _entries_of(state_path)
    hit = False
    for i, x in enumerate(entries):
        if x.arxiv_id != TARGET_ID:
            continue
        assert x.state == frm, f"状态是 {x.state}，期望 {frm}（非「已批」一律拒绝）"
        e, err = st.transition(x, to, reason, actor=actor)
        assert not err, f"迁移被状态机拒：{err}"
        entries[i] = e
        hit = True
    assert hit, f"{TARGET_ID} 不在 {state_path}"
    rep = st.report(entries)
    out = {"report": rep, "entries": [x.to_dict() for x in entries]}
    json.dump(out, open(state_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    # append-only 审计日志必须同步落笔。2026-10-05 实测：W11 迁移完
    # transitions.jsonl 只有 2 行（只有 w11_approve 那两跳），收口的
    # 已批→已跑→出结论 两跳**根本没进日志**——条目里有、日志里没有，
    # 于是「append-only 永不修改」的审计面漏了收口这一段。
    # 迁移已落盘，此时补写的是**已发生的事实**（带原始 at 时间戳），
    # 不是事后编造。
    if log_path:
        st.append_log([t for x in entries if x.arxiv_id == TARGET_ID
                       for t in x.transitions], log_path)
    return rep["by_state"]


def _entries_of(state_path: str) -> list:
    """从任意 state_path 重建 Entry 列表（Transition 从 dict 重建，不静默）。"""
    raw = json.load(open(state_path, encoding="utf-8"))
    out = []
    for d in raw.get("entries", []):
        d = dict(d)
        ts = [st.Transition(**t) for t in d.pop("transitions", [])]
        out.append(st.Entry(**d, transitions=ts))
    return out


def conclude(state_path: str, verdict_path: str, summary_path: str,
             items_path: str, drafts_dir: str | None = None) -> dict:
    try:
        verdict = load_verdict(verdict_path)
    except FileNotFoundError as e:
        return {"ok": False, "why": str(e)}
    v = verdict.get("verdict")
    if v not in ALLOWED_VERDICTS:
        return {"ok": False, "why": f"verdict={v} 不在 {ALLOWED_VERDICTS}——"
                                    "判读没过就不迁移状态机"}
    claim = verdict.get("claim", "")
    if len(claim) < 30:
        return {"ok": False, "why": "verdict.claim 缺失或过短——结论必须从判读器来"}

    rec = json.load(open(summary_path, encoding="utf-8")).get("report")
    by1 = flip_state(state_path, "已批", "已跑",
                     f"W8 双臂实验跑完：items={items_path}，判读 verdict={v}（"
                     "McNemar 配对检验 + 重算门 + scope/caliber 门见 w8_critic_verdict.json）")
    conclusion = claim
    by2 = flip_state(state_path, "已跑", "出结论", conclusion)
    draft_path, why = wr.draft(TARGET_ID, summary_path, verdict_path,
                               state_path=state_path, drafts_dir=drafts_dir)
    if draft_path is None:
        return {"ok": False, "why": f"出结论后草稿仍被拒：{why}", "by_state": by2}
    return {"ok": True, "verdict": v, "by_state_after_run": by1,
            "by_state_final": by2, "draft": draft_path,
            "claim": claim}


def selftest() -> int:
    bad = []
    ck = lambda name, got, want: bad.append(f"{name}: got {got!r} want {want!r}") \
        if got != want else None
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        # ── 夹具：store 里 2301.13379v3 已批 + 完整形状（L-ops-138 教训）──
        real = json.load(open(st.OUT, encoding="utf-8"))
        entry = None
        for x in real["entries"]:
            if x["arxiv_id"] == TARGET_ID:
                entry = dict(x)
        assert entry is not None
        entry["state"] = "已批"
        sp = os.path.join(td, "proposals_state.json")
        json.dump({"report": {"total": 1, "by_state": {"已批": 1}},
                   "entries": [entry]}, open(sp, "w", encoding="utf-8"),
                  ensure_ascii=False)

        summary = {"experiment": "w8", "protocol": {"n": 100, "seed": 20261003,
                                                    "anchors": {"faithful": 0.723, "cot": 0.633}},
                   "arm_f": {"n": 100, "n_correct": 72, "acc": 0.72,
                             "wilson95": [0.6222, 0.8014], "n_unparsed": 0,
                             "n_truncated": 3, "sec_mean": 90.0},
                   "arm_c": {"n": 100, "n_correct": 60, "acc": 0.6,
                             "wilson95": [0.5005, 0.692], "n_unparsed": 0,
                             "n_truncated": 1, "sec_mean": 80.0},
                   "paired_f_vs_c": {"b_f_right_c_wrong": 15, "c_f_wrong_c_right": 3,
                                     "n_discordant": 18, "p_exact_two_sided": 0.007538},
                   "gap_to_anchor": {"f_vs_0.723": -0.003, "c_vs_0.633": -0.033},
                   "wall_min": 31.0}
        summ_p = os.path.join(td, "s.json")
        json.dump(summary, open(summ_p, "w", encoding="utf-8"), ensure_ascii=False)
        claim = ("本实验迷你口径实测：Qwen3-0.6B 同源配对（同 n=100 GSM8K 子集），"
                 "程序执行臂 acc=0.72，"
                 "匹配 few-shot CoT 臂 acc=0.6，配对 McNemar 精确双侧 p=0.007538"
                 "（b=15, c=3），程序执行臂优于匹配 CoT 臂；对文献锚为量级测量："
                 "0.723 差 -0.003，0.633 差 -0.033。F 臂执行失败 0、截断 3；"
                 "C 臂无答案 0、截断 1。")
        verdict = {"verdict": "pass", "claim": claim,
                   "measured_scope": "0.6B 双臂 n=100 seed 20261003",
                   "gates": {"recomputable": {"pass": True},
                             "effect_vs_noise_paired": {"pass": True},
                             "scope_discipline": {"pass": True},
                             "caliber_in_claim": {"pass": True},
                             "mechanism_alignment": {"pass": None}}}
        vp = os.path.join(td, "v.json")
        json.dump(verdict, open(vp, "w", encoding="utf-8"), ensure_ascii=False)
        # writer.verify_numbers 需要 items 路径吗？不需要——draft 只读
        # summary/verdict/state。items_path 只是记录在迁移理由里。

        # ── verdict=fail ⇒ 拒绝迁移 ──
        vbad = dict(verdict, verdict="fail")
        vbp = os.path.join(td, "vbad.json")
        json.dump(vbad, open(vbp, "w", encoding="utf-8"), ensure_ascii=False)
        r = conclude(sp, vbp, summ_p, "items.jsonl", drafts_dir=td)
        ck("fail 拒绝", r["ok"], False)
        d = json.load(open(sp, encoding="utf-8"))
        ck("fail 后状态未动", d["entries"][0]["state"], "已批")

        # ── 缺判读产物 ⇒ 拒绝 ──
        r = conclude(sp, os.path.join(td, "不存在.json"), summ_p, "i", drafts_dir=td)
        ck("缺产物拒绝", r["ok"], False)

        # ── 状态不是已批 ⇒ 拒绝（幂等安全）──
        d["entries"][0]["state"] = "待批"
        json.dump(d, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
        try:
            r = conclude(sp, vp, summ_p, "i", drafts_dir=td)
            ck("非已批应抛错", "no_exception", "exception")
        except AssertionError:
            pass

        # ── 全绿：两段迁移 + 草稿落盘 ──
        d["entries"][0]["state"] = "已批"
        json.dump(d, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
        r = conclude(sp, vp, summ_p, "items.jsonl", drafts_dir=td)
        ck("全绿 ok", r["ok"], True)
        if r.get("ok"):
            d2 = json.load(open(sp, encoding="utf-8"))
            ck("终态出结论", d2["entries"][0]["state"], "出结论")
            ck("transitions 保留",
               len(d2["entries"][0].get("transitions", [])) >= 2, True)
            rep = d2["report"]
            ck("report 自洽", sum(rep["by_state"].values()) == rep["total"], True)
            txt = open(r["draft"], encoding="utf-8").read()
            ck("草稿页脚", "草稿状态：待批" in txt, True)
            ck("草稿主张在文", "acc=0.72" in txt, True)
            ck("状态可复跑拒绝", json.load(open(sp, encoding="utf-8"))["entries"][0]["state"],
               "出结论")

    print(f"selftest: 失败 {len(bad)}")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    store = os.path.join(ROOT, "ai-researcher", "store")
    r = conclude(st.OUT,
                 os.path.join(store, "w8_critic_verdict.json"),
                 os.path.join(store, "w8_faithful_cot_summary.json"),
                 os.path.join(store, "w8_faithful_cot_items.jsonl"))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
