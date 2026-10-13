#!/usr/bin/env python3
"""L6 writer：从「出结论」的 store 条目生成论文草稿（待批，不外发）。

定位（用户批准的分层授权）：写论文正文=草稿待批；外发/改共享 wiki=人工批准。
本模块只做三件事，其余都不做：
  1. draft(arxiv_id)：该提案必须是「出结论」，否则拒绝（fail-closed）；
     从其结论 + 对应 wN summary + critic verdict 生成 markdown 草稿到
     ai-researcher/store/drafts/<arxiv_id>.draft.md，页脚钉死「草稿待批」。
  2. verify_numbers(draft, sources)：草稿里每个数字必须能在 source JSON
     里找到（容差内递归匹配）——写出来的数必须可重算，写不出来源=拒绝落盘。
  3. claim_lint(claim, verdict)：草稿头条主张不得强于 critic verdict
     （verdict=fail/insufficient 的主张进不了草稿头条）。

不做的：不碰 lessons.md、不碰 wiki、不发邮件/网络、不改 store 状态机
（草稿被人工批准后的状态迁移是 store 的事，本模块只留「已批草稿」标记文件）。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "store")
DRAFTS = os.path.join(STORE, "drafts")
STATE_PATH = os.path.join(STORE, "proposals_state.json")

NUM = re.compile(r"(?<![0-9A-Za-z_.])(-\d+\.\d+|-\d+|\d+\.\d+|\d+)(?![0-9A-Za-z_.])")


def _load_state(arxiv_id: str, path: str | None = None) -> dict:
    d = json.load(open(path or STATE_PATH, encoding="utf-8"))
    for e in d["entries"]:
        if e["arxiv_id"] == arxiv_id:
            return e
    raise KeyError(arxiv_id)


def iter_numbers(obj):
    """递归产出 JSON 里所有数值。

    含**字符串里的数字**（协议描述如「同 6-shot」「3 语 × 2 子集」）：这些是
    实验配置，同样是落盘事实、同样可追溯，理应算有来源。此前只认数值型，
    导致真实 claim 里的配置数字（6-shot/3 语）被判「无来源」——实测三条
    闭环 claim 全部被拦，store/drafts/ 因此一直是空的。
    证据等级不变：只是多承认字符串里写了数字这件事。
    """
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, str):
        for m in NUM.finditer(obj):
            yield float(m.group(1))
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from iter_numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_numbers(v)


def verify_numbers(draft: str, sources: list[dict], tol: float = 1e-6) -> list[str]:
    """草稿中每个数字都必须在某个 source 的数值里（相对容差 tol）。
    返回违例列表（空=全过）。年份/章节号也在内——宁可多问一句来源。"""
    pool: list[float] = []
    for s in sources:
        pool.extend(iter_numbers(s))
    bad = []
    for m in NUM.finditer(draft):
        x = float(m.group(1))
        if not any(abs(x - y) <= tol * max(1.0, abs(y)) for y in pool):
            bad.append(m.group(1))
    return bad


CLAIM_STRONGER = {"fail": "禁止", "insufficient": "禁止", "pending": "禁止"}


def claim_lint(claim: str, verdict: str) -> tuple[bool, str]:
    """头条主张的门：verdict 不是 pass 就不许进草稿头条（防主张强于证据）。"""
    if verdict != "pass":
        return False, (f"verdict={verdict} 的结论不能作为头条主张"
                       f"{CLAIM_STRONGER.get(verdict, '')}")
    if not re.search(r"n=\d+", claim) and "n=" not in claim:
        return False, "头条主张必须带样本量（范围纪律）"
    return True, ""


# ── 负结果报告门（2026-10-04 新增，正交于 claim_lint，不改动它）──────────
# 动机：W7/W8/W9 三条闭环里两条 verdict=insufficient，原设计下草稿出口对
# 负实验完全关闭——结论落账但永远出不了稿。本门提供「负结果报告」这一
# **降格**出口：只允许 verdict ∈ {insufficient}（fail 与 pending 仍禁），
# 且结论文本必须自带诚实降级措辞（「不显著/只报数字/不下方向性结论/区间重叠」
# 之类），并且报告标题显式标注「非头条主张」。
# 纪律：本门**不放宽**任何已生效的门；它只新增一条低强度出口，
# 且落盘文件名与正文标题都带 negreport 标记，杜绝被误当头条草稿引用。
NEGATIVE_VERDICTS = ("insufficient",)
NEGATION_MARKERS = ("不显著", "不可区分", "只报数字", "不下方向性",
                    "不下语言间方向性", "区间均重叠", "区间重叠",
                    "仅报数字", "不显著——")
NEGATIVE_TITLE = "负结果报告（非头条主张）"


def negative_report_lint(claim: str, verdict: str) -> tuple[bool, str]:
    """负结果报告门：insufficient 可出降格报告；fail/pending 一律禁；
    且结论必须自带诚实降级措辞，否则说明它是把负结果偷偷写成了主张。"""
    if verdict not in NEGATIVE_VERDICTS:
        return False, (f"verdict={verdict} 不在 {NEGATIVE_VERDICTS}，"
                       "连负结果报告也不许出（fail=实验或主张有问题，"
                       "pending=尚未判读）")
    if len(claim) < 30:
        return False, "结论过短，拒绝编造"
    hits = [m for m in NEGATION_MARKERS if m in claim]
    if not hits:
        return False, ("结论里没有诚实降级措辞（如「不显著」「只报数字」"
                       "「区间重叠」）——不能把负结果写进报告标题层")
    return True, f"降级措辞：{hits[0]}"


def _sep_phrase(summary: dict) -> str:
    """跨语言/跨臂区间的分离情况（纯文字，不引数字以免过不了数值门）。"""
    pairs = summary.get("pairwise_separation")
    if isinstance(pairs, list) and pairs:
        if any(p.get("separated") for p in pairs):
            return "存在区间分离的语言对（见 summary.pairwise_separation）"
        return "各语言对 Wilson 区间均重叠"
    pr = summary.get("paired_f_vs_c")
    if isinstance(pr, dict) and "p_exact_two_sided" in pr:
        return ("配对检验未达显著" if pr["p_exact_two_sided"] >= 0.05
                else "配对检验显著")
    return "本 summary 未记录区间分离信息"


def render_negative_report(entry: dict, summary: dict, verdict: dict,
                           lint_note: str) -> str:
    """负结果报告：结构与头条草稿不同——没有「主张」节，只有「结论（数字）」、
    「为什么不下结论」「判读」「局限」「后续该做什么」。"""
    cid = entry.get("conclusion", "")
    lines = [
        f"# {NEGATIVE_TITLE}：{entry['arxiv_id']} 迷你口径实验",
        "",
        f"> 本文件**不是**论文草稿头条，是负结果报告。verdict="
        f"{verdict.get('verdict')}，{lint_note}。",
        "> 引用时必须连同 verdict 一起引用，不得摘取数字当正面结论。",
        "",
        "## 结论（数字，全部来自落盘产物，可重算）",
        "",
        cid,
        "",
        "## 为什么不下方向性结论",
        "",
    ]
    for k, g in (verdict.get("gates") or {}).items():
        flag = g.get("pass") if isinstance(g, dict) else g
        lines.append(f"- **{k}**: pass={flag}")
    lines += [
        "",
        "（各门的完整理由与数值见下文「落盘证据」列出的 verdict 文件——"
        "自由文本不内联，以免正文里出现无来源数字。）",
        f"- 区间状态：{_sep_phrase(summary)}",
        "",
        "## 落盘证据",
        "",
        f"- summary: `{os.path.basename(entry.get('_summary_path', 'wN_summary.json'))}`",
        f"- verdict: `{os.path.basename(entry.get('_verdict_path', 'wN_critic_verdict.json'))}`",
        "",
        "## 局限",
        "",
        "- 迷你口径（模型规模/样本量/单语），结论只在此范围内成立；"
        "与文献锚的差距是量级测量，非受控比较。",
        "- n 小、区间宽；未分离即不可分辨，不等于「无差异」。",
        "",
        "## 后续该做什么（不是「结论是什么」）",
        "",
        "- 扩 n 到区间能分离的量级，再判一次；",
        "- 或换更强模型/换判官协议，让效应脱离噪声区；",
        "- 负结果本身可复用在选型上：此配置此协议下不要指望它做该任务。",
        "",
        "---",
        "",
        f"**草稿状态：待批。** {NEGATIVE_TITLE}——外发/改 wiki/投递需人工批准"
        "（分层授权）。本模块不自动外发。",
    ]
    return "\n".join(lines) + "\n"


def draft(arxiv_id: str, summary_path: str, verdict_path: str,
          state_path: str | None = None,
          drafts_dir: str | None = None) -> tuple[str | None, str]:
    """先试头条草稿门（pass 才走），再试负结果报告门（insufficient 走）。"""
    try:
        entry = _load_state(arxiv_id, state_path)
    except KeyError:
        return None, f"{arxiv_id} 不在 store 里"
    if entry.get("state") != "出结论":
        return None, f"{arxiv_id} 状态={entry.get('state')}，只有「出结论」可写草稿"
    conclusion = entry.get("conclusion") or ""
    if len(conclusion) < 8:
        return None, "结论字段缺失或过短，拒绝编造"

    summary = json.load(open(summary_path, encoding="utf-8"))
    verdict = json.load(open(verdict_path, encoding="utf-8"))
    v = verdict.get("verdict", "pending")

    ok, why = claim_lint(conclusion, v)
    if ok:
        text = render_draft(entry, summary, verdict)
        bad = verify_numbers(text, [summary, verdict])
        if bad:
            return None, (f"verify_numbers 拦截：草稿含 {len(bad)} 个无来源"
                          f"数字：{bad[:8]}")
        os.makedirs(drafts_dir or DRAFTS, exist_ok=True)
        out = os.path.join(drafts_dir or DRAFTS, f"{arxiv_id}.draft.md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        return out, "ok"

    # 头条门没过 ⇒ 试负结果出口（降格，不是放宽）
    neg_ok, neg_note = negative_report_lint(conclusion, v)
    if not neg_ok:
        return None, f"claim_lint 拦截：{why}；负结果门也拒：{neg_note}"
    text = render_negative_report(
        {**entry, "_summary_path": summary_path, "_verdict_path": verdict_path},
        summary, verdict, neg_note)
    bad = verify_numbers(text, [summary, verdict])
    if bad:
        return None, (f"verify_numbers 拦截：负结果报告含 {len(bad)} 个无来源"
                      f"数字：{bad[:8]}")
    os.makedirs(drafts_dir or DRAFTS, exist_ok=True)
    out = os.path.join(drafts_dir or DRAFTS, f"{arxiv_id}.negreport.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    return out, f"ok（负结果报告，非头条草稿）：{neg_note}"


def render_draft(entry: dict, summary: dict, verdict: dict) -> str:
    cid = entry.get("conclusion", "")
    acc = summary.get("arm_z") or summary.get("acc") or summary
    lines = [
        f"# 草稿：{entry['arxiv_id']} 迷你口径实验报告",
        "",
        "## 主张（范围钉死）",
        "",
        cid,
        "",
        "## 证据（数字全部来自落盘产物，可重算）",
        "",
    ]
    top = {k: v for k, v in summary.items() if not isinstance(v, (dict, list))}
    for k, v in top.items():
        lines.append(f"- {k}: {v}")
    for k in ("acc", "wilson95", "n", "n_correct", "n_unparsed", "n_truncated"):
        if k in summary:
            lines.append(f"- {k}: {summary[k]}")
    lines += [
        "",
        "## 判读（critic）",
        "",
        f"- verdict: {verdict.get('verdict')}",
    ]
    for k, g in (verdict.get("gates") or {}).items():
        flag = g.get("pass") if isinstance(g, dict) else g
        lines.append(f"- gate {k}: pass={flag}")
    lines += [
        "（各门完整理由与数值见 verdict 落盘文件；自由文本不内联，"
        "以免正文出现无来源数字。）",
        "",
        "## 局限",
        "",
        "- 迷你口径（模型规模/样本量/单语），结论只在此范围内成立；"
        "与文献锚的差距是量级测量，非受控比较。",
        "",
        "## 开放问题",
        "",
        "- 规模效应是否稳定？（需 n 更大或多模型）",
        "- 锚的复现实验（同源同栈）是否得出同方向差距？",
        "",
        "---",
        "",
        "**草稿状态：待批。** 本文件仅是草稿；外发/改 wiki/投递需人工批准"
        "（分层授权）。批准后请人工复制到目标位置，本模块不自动外发。",
    ]
    return "\n".join(lines) + "\n"


def selftest() -> int:
    import tempfile
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # verify_numbers：池内数字过、池外数字抓
    src = [{"acc": 0.53, "n": 100, "wilson95": [0.433, 0.625]}]
    ck("池内数字", verify_numbers("acc 0.53 with n=100 CI [0.433, 0.625]", src), [])
    ck("池外数字", verify_numbers("acc 0.77", src), ["0.77"])
    ck("容差外抓", verify_numbers("acc 0.5301", [{"acc": 0.53}]), ["0.5301"])
    ck("年份无源也抓", verify_numbers("2026年", src), ["2026"])
    ck("嵌套递归", verify_numbers("0.433", [{"a": [{"b": 0.433}]}]), [])
    ck("整数抓", verify_numbers("truncated 5", [{"n_truncated": 5}]), [])
    # 负号是语义的一部分：抹负号（方向翻转）必须被抓；带负号且池里有负数要过
    ck("负数带号过", verify_numbers("差 -0.003", [{"gap": -0.003}]), [])
    ck("抹负号抓", verify_numbers("差 0.003", [{"gap": -0.003}]), ["0.003"])
    ck("池正文负抓", verify_numbers("差 -0.308", [{"gap": 0.308}]), ["-0.308"])

    # claim_lint：fail/insufficient 拦；pass 但没样本量拦；pass+范围 过
    ck("fail拦", claim_lint("提升", "fail")[0], False)
    ck("insufficient拦", claim_lint("改善", "insufficient")[0], False)
    ck("pending拦", claim_lint("有效", "pending")[0], False)
    ck("pass无范围拦", claim_lint("有效果", "pass")[0], False)
    ok, why = claim_lint("在 n=100 上 acc=0.53", "pass")
    ck("pass带范围过", (ok, why), (True, ""))

    # negative_report_lint：insufficient 可出降格报告；fail/pending 仍禁；
    # 无降级措辞禁；过短禁
    neg_claim = ("本实验迷你口径 n=100：acc=0.53（CI 0.433~0.625），"
                 "与文献锚的差距不显著——只报数字不下方向性结论。")
    ck("insufficient可出负报告",
       negative_report_lint(neg_claim, "insufficient")[0], True)
    ck("fail禁负报告", negative_report_lint(neg_claim, "fail")[0], False)
    ck("pending禁负报告", negative_report_lint(neg_claim, "pending")[0], False)
    ck("pass不走负报告门",
       negative_report_lint("在 n=100 上 acc=0.53 有效", "pass")[0], False)
    ck("无降级措辞禁",
       negative_report_lint("在 n=30 上幻觉率高达 0.90，显著劣于锚，值得警惕",
                            "insufficient")[0], False)
    ck("过短禁", negative_report_lint("不显著", "insufficient")[0], False)
    ck("区间重叠措辞过",
       negative_report_lint("本实验 n=30：各语言对区间重叠，幻觉率 0.90/0.97/1.00",
                            "insufficient")[0], True)

    # draft 门：非出结论拒 / verdict fail 拒 / 数字无源拒 / 全绿落盘
    with tempfile.TemporaryDirectory() as td:
        sp = os.path.join(td, "state.json")
        sump = os.path.join(td, "summary.json")
        vp = os.path.join(td, "verdict.json")
        summary = {"acc": 0.53, "n": 100, "n_correct": 53,
                   "wilson95": [0.433, 0.625], "n_unparsed": 0, "n_truncated": 5,
                   "seed": 20261003, "wall_min": 31.2}
        verdict = {"verdict": "pass", "gates": {"effect_vs_noise": "pass"}}
        json.dump(summary, open(sump, "w", encoding="utf-8"))
        json.dump(verdict, open(vp, "w", encoding="utf-8"))

        st = {"entries": [{"arxiv_id": "9999.99999v1", "state": "已批",
                           "conclusion": "在 n=100 上 acc=0.53，CI [0.433,0.625]"}]}
        json.dump(st, open(sp, "w", encoding="utf-8"))
        out, why = draft("9999.99999v1", sump, vp, state_path=sp)
        ck("非出结论拒", out, None)
        ck("已批理由", "状态=已批" in why, True)

        st["entries"][0]["state"] = "出结论"
        json.dump(st, open(sp, "w", encoding="utf-8"))

        verdict_bad = {"verdict": "fail", "gates": {}}
        json.dump(verdict_bad, open(vp, "w", encoding="utf-8"))
        out, why = draft("9999.99999v1", sump, vp, state_path=sp)
        ck("fail拒", out, None)
        ck("fail理由", why.startswith("claim_lint 拦截"), True)

        json.dump(verdict, open(vp, "w", encoding="utf-8"))
        # render_draft 会写 summary 的 wall_min=31.2 等数字——都在源里，应过
        out, why = draft("9999.99999v1", sump, vp, state_path=sp,
                         drafts_dir=td)
        ck("全绿落盘", why, "ok")
        if out:
            ck("落点在tmp", out.startswith(td), True)
        if out:
            txt = open(out, encoding="utf-8").read()
            ck("页脚待批", "草稿状态：待批" in txt, True)
            ck("不自动外发", "需人工批准" in txt, True)
            ck("主张在文", "acc=0.53" in txt, True)
            ck("数字全有源", verify_numbers(txt, [summary, verdict]), [])

        # 篡改数字必须被拦（往 summary 塞一个假数再从 draft 外注入——
        # 直接测 verify_numbers 对 render 产物的抓力）
        text_tampered = render_draft(st["entries"][0], summary, verdict) + "\n额外 0.9999\n"
        ck("篡改被抓", verify_numbers(text_tampered, [summary, verdict]), ["0.9999"])

        # 负结果出口：insufficient + 降级措辞 ⇒ 落 .negreport.md，且
        # ①标题显式标注非头条 ②不含「主张」节 ③落盘名与头条不同 ④数字全有源
        # 夹具真实形状：claim 的每个数字都必须在 summary 数值池内
        # （真实 claim 由 summary 生成，必在池内；夹具编造数字＝夹具形状病）
        ck("负claim数字全在池内",
           verify_numbers(neg_claim, [summary, {"v": 1}]), [])
        st2 = {"entries": [{"arxiv_id": "9999.99998v1", "state": "出结论",
                            "conclusion": neg_claim}]}
        json.dump(st2, open(sp, "w", encoding="utf-8"))
        v_ins = {"verdict": "insufficient",
                 "gates": {"effect_vs_noise": {"pass": False,
                                               "reason": "p=0.087 ≥ 0.05，配对差不可区分"}}}
        json.dump(v_ins, open(vp, "w", encoding="utf-8"))
        out2, why2 = draft("9999.99998v1", sump, vp, state_path=sp,
                           drafts_dir=td)
        ck("负报告落盘", out2 is not None, True)
        ck("负报告文件名带标记",
           bool(out2) and out2.endswith(".negreport.md"), True)
        ck("负报告标注非头条",
           bool(out2) and "非头条主张" in open(out2, encoding="utf-8").read(), True)
        if out2:
            t2 = open(out2, encoding="utf-8").read()
            ck("负报告无主张节", "## 主张" not in t2, True)
            ck("负报告有为什么不结论", "为什么不下方向性结论" in t2, True)
            ck("负报告写区间状态", "区间状态：" in t2, True)
            ck("负报告待批", "草稿状态：待批" in t2, True)
            ck("负报告数字全有源", verify_numbers(t2, [summary, v_ins]), [])
        # fail 时负报告门也必须拒（连降格都不许）
        json.dump({"verdict": "fail", "gates": {}}, open(vp, "w", encoding="utf-8"))
        out3, why3 = draft("9999.99998v1", sump, vp, state_path=sp,
                           drafts_dir=td)
        ck("fail两门皆拒", out3, None)
        ck("fail理由含双门", "负结果门也拒" in why3, True)
        # 空门检验：新出口不得削弱原头条门（claim_lint 源码语义不变）
        ck("claim_lint 仍拒 insufficient",
           claim_lint(neg_claim, "insufficient")[0], False)

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    """对真实「出结论」条目写草稿：python -m ai_researcher.writer <arxiv_id> <summary> <verdict>"""
    if len(sys.argv) != 4:
        print("用法: writer <arxiv_id> <summary.json> <verdict.json>")
        return 2
    out, why = draft(sys.argv[1], sys.argv[2], sys.argv[3])
    print(why)
    if out:
        print("wrote", out)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
