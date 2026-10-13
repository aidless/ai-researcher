"""L2 提案器：把 L1 排好序的开放点变成**可机械执行的验证提案**。

## 它和 L1/L0 的分工

    L0 scanner  从笔记抽出「开放点」原文（不判断能不能验证）
    L1 ranker   判断哪条值得先看（打分 + 分层）
    L2 runner   判断这条**能不能被写成可执行的验证方案**，写不出来就说写不出来

## 它绝不做什么

- **不写 wiki，不改笔记，不改 L1 输出。**
- **不发明实验设计**。提案的每一句都必须能从笔记里已有的内容推出。
- **不用通用模板凑数**。这是本模块的核心纪律，见下。

## 为什么"写不出来"是一等公民

一个自然的做法是：给每条开放点套一个"跑 X 实验、看 Y 指标"的模板，
输出 56 条看起来整齐的提案。这个做法是**错的**，而且错得很隐蔽：

    模板会替你做决定，而那些决定正是最不该被机器替你做的。

比如「verifier分布外泛化待验」——套模板会产出"构造分布外集、测泛化落差"，
看着完全合理。但"分布外"到底指哪种分布（原论文的语言域？时间域？
对抗构造的域？）**只有读过原论文的人知道**。模板替你选了"语言域"，
方案就变成洗稿，且**看起来比"写不出来"专业得多**。

所以 L2 的判定是三值的：

    executable  能推出可执行方案（对象、观测、判据都指得出具体东西）
    blocked     笔记里缺少必要信息，写不出方案——**这是合法结果**，不是失败
    needs_human 涉及取舍/伦理/授权，必须人拍

实测（2026-10-02，主榜 56 条）：executable 14 / blocked 41 / needs_human 1。
**blocked 占多数（41/56），这是正确的**——它精确指出"这 41 条需要先回原论文
补信息"，而不是拿模板糊过去。

（第一版这里写的是「12 / 39 / 5」，那是我**事前估的、没跑就写上去的**，
实测是 14 / 41 / 1。差异本身抓到了一个真 bug：观测门把槽位标签 `C1` 里的
数字当成观测量，导致 15 条误判为可执行。见下面 OBSERVE 处的说明。
**门的设计文档里写预测值、代码里跑实测值，两者不一致时以实测为准并改文档**
——否则下一个人会拿那个假数字当基线。）

## 提案的四个必备件（缺一不可 ⇒ blocked）

    object     被检验的对象是什么（必须是可指认的量/集合/关系）
    observe    观测什么（必须是能算出来的数，不是"看看好不好"）
    criterion  什么算通过（必须是可机械判定的阈值/比较/不变量）
    why_now    为什么现在能做（来自 notes，不是来自我的想象）

这四件都从**笔记原文**里抽，抽不到就 blocked。`extract_proposal()` 返回
`blocked_reason` 指明缺哪一件——这是给读者的行动指令，不是错误码。
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

from . import scanner as S
from . import ranker as R

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "proposals", "proposals.json")

VERDICTS = ("executable", "blocked", "needs_human")


# ── 可指认对象：从开放点里认「测什么」 ───────────────────────────────────
# 每个类型给一组"锚词"。锚词的作用不是猜语义，而是**证明笔记里确实提到了
# 那个可指认的东西**——没提到就不能假装它是对象。

# 对象锚：可指认的量/集合
ANCHORS: dict[str, list[str]] = {
    "评测集/基准": ["评测", "基准", "benchmark", "榜单", "leaderboard",
                 "测试集", "数据集", "BFCL", "SWEBench", "WebArena",
                 "GSM8K", "MMLU", "arena"],
    "覆盖范围（语种/任务/域）": ["覆盖", "跨语言", "语种", "双语", "七语言",
                        "四语言", "18语", "多语", "跨域", "任务面", "域"],
    "模型/权重": ["模型", "权重", "小模型", "大模型", "1B", "7B", "开源权重",
                "闭源", "API"],
    "代码仓库/制品": ["仓库", "开源", "代码", "artifact", "复现", "库", "权重"],
    "数据标注": ["标注", "标注成本", "标注员", "指令数据", "训练数据"],
    "成本/延迟/算力": ["成本", "延迟", "开销", "显存", "预算", "吞吐", "亿token"],
    "攻击者/防御/安全": ["攻击", "防御", "安全", "红队", "对抗", "越狱", "jailbreak"],
    "检索/排序/召回": ["检索", "召回", "排序", "重排", "BM25", "chunk", "切块"],
    "代理/工具调用链": ["agent", "代理", "工具调用", "工具描述", "多轮", "重放"],
    "推理/自进化/RL": ["推理", "自进化", "RL", "强化学习", "PRM", "奖励"],
    "翻译/跨语言迁移": ["翻译", "中英", "跨语言", "迁移"],
    "数学/符号求解": ["求解器", "符号", "数学", "PAL", "定理"],
}

# 判据锚：什么算通过
CRITERIA: list[str] = [
    r"待验", r"待补", r"待测", r"外泛化", r"跨语言", r"覆盖", r"对比", r"比较",
    r"差距", r"落[后差]", r"一致[性]", r"重现", r"复现", r"不[降升]", r"持平",
    r"显著", r"提升", r"下降", r"波动", r"收敛", r"超[出低]于", r"比率",
]

# 观测锚：能算出来的数。
#
# **这里踩过一个真坑**：第一版把 `\d`（任意数字）当观测证据，于是
# `C1多语issue解决gap证据` 里那个 `1` 就让整条通过了「有可算的数」这道门。
# 槽位标签 C1/C2/C3 是纯记账符号，不承载任何测量——但机器分不出「C1 的 1」
# 和「覆盖 1 种语言」的 1。**符号本身没有语义，`\d` 却在替它背书。**
#
# 修法：不再接受裸 `\d`，只接受**带计量单位或量词形态**的数字
# （「七语言」走中文数词+量词表，「0.1M」走数字+单位）。纯槽位标签因此
# 不再能满足观测门。这条判据有反证守着：喂纯槽位文本必须判 blocked。
OBSERVE: list[str] = [
    r"[零一二三四五六七八九十百千万两]{1,3}(?:语|语言|任务|域|篇|题|组|类|条|轮|步|次)",
    r"\d+(?:\.\d+)?\s*(?:%|％|倍|万|亿|千|百|个|条|题|篇|语|任务|轮|次|步|类|组|M|K)",
    r"准确率", r"召回", r"MRR", r"nDCG", r"F1", r"pass@", r"精确率",
    r"成功率", r"开销", r"延迟", r"成本", r"占比", r"规模", r"token", r"题量",
    r"语言数", r"任务数", r"覆盖数", r"覆盖限", r"窄", r"有限",
]



@dataclass
class Proposal:
    """一条验证提案。**被阻塞时也要产出对象**，否则调用方无从下手。"""

    arxiv_id: str
    verdict: str                  # executable / blocked / needs_human
    open_problem: str             # L0 原文，未改写
    gap_types: list[str] = field(default_factory=list)
    object_candidates: list[str] = field(default_factory=list)
    criterion_hints: list[str] = field(default_factory=list)
    observe_hints: list[str] = field(default_factory=list)
    why_now: str = ""             # 只能来自 notes
    blocked_reason: str = ""      # 指明缺哪一件（可行动指令）
    needs_human_reason: str = ""
    score: float = 0.0            # 来自 L1，仅用于排序

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _anchors_in(text: str, table: dict[str, list[str]]) -> list[str]:
    hit = []
    for name, words in table.items():
        for w in words:
            if w.lower() in text.lower():
                hit.append(name)
                break
    return hit


def _hits(text: str, pats: list[str]) -> list[str]:
    out = []
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            out.append(m.group(0))
    return out


def extract_proposal(r: R.Ranked) -> Proposal:
    """把一条排序结果转成提案。纯函数，无 IO。

    判据顺序是刻意的：**先看有没有对象**，再看有没有判据与观测，最后才谈
    为什么现在能做。反过来写会把「笔记写得很兴奋」误判成「可执行」。
    """
    op = r.open_problem
    rel = r.project_relation
    full = op + "\n" + rel

    objs = _anchors_in(full, ANCHORS)
    crit = _hits(full, CRITERIA)
    obs = _hits(full, OBSERVE)

    missing = []
    if not objs:
        missing.append("对象（笔记里找不到任何可指认的评测集/模型/数据集/机制）")
    if not crit:
        missing.append("判据（找不到任何可判定的比较、阈值或不变量）")
    if not obs:
        missing.append("观测（找不到任何可算出来的数）")

    # needs_human：涉及授权/伦理/生产数据的，只能人拍
    if re.search(r"生产数据|不可公开|合规|伦理|授权|用户数据|合规审查", full):
        return Proposal(
            arxiv_id=r.arxiv_id, verdict="needs_human",
            open_problem=op, gap_types=list(r.gap_types),
            object_candidates=objs, criterion_hints=crit,
            observe_hints=obs, why_now=rel[:120],
            needs_human_reason="涉及生产数据/授权/合规，必须人拍后才能定实验",
            score=r.score,
        )

    if missing:
        return Proposal(
            arxiv_id=r.arxiv_id, verdict="blocked",
            open_problem=op, gap_types=list(r.gap_types),
            object_candidates=objs, criterion_hints=crit,
            observe_hints=obs, why_now=rel[:120],
            blocked_reason="缺" + "；缺".join(missing)
                          + "——需回原论文补齐后才能定实验",
            score=r.score,
        )

    return Proposal(
        arxiv_id=r.arxiv_id, verdict="executable",
        open_problem=op, gap_types=list(r.gap_types),
        object_candidates=objs, criterion_hints=crit,
        observe_hints=obs, why_now=rel[:200], score=r.score,
    )


def build(ranked: list[R.Ranked] | None = None, limit: int | None = None
          ) -> list[Proposal]:
    ranked = ranked if ranked is not None else R.rank()
    out = [extract_proposal(r) for r in ranked if r.tier == "main"]
    if limit:
        out = out[:limit]
    return out


def report(ps: list[Proposal], ranked: list[R.Ranked] | None = None
           ) -> dict[str, Any]:
    """汇总。

    `ranked` 是**可选的对照源**。给了才算 `no_invented_text`，不给就报 None
    而不是 True —— 凭空断言「没改写原文」比不报更危险（AGENTS.md 第 7 条：
    永远"通过"的门等于没有门）。
    """
    from collections import Counter
    c = Counter(p.verdict for p in ps)
    rep: dict[str, Any] = {
        "total": len(ps),
        "by_verdict": {v: c.get(v, 0) for v in VERDICTS},
        "verdict_sum_matches": sum(c.values()) == len(ps),
        "every_executable_has_four_parts": all(
            p.object_candidates and p.criterion_hints
            and p.observe_hints and p.why_now
            for p in ps if p.verdict == "executable"),
        "every_blocked_says_what_is_missing": all(
            p.blocked_reason for p in ps if p.verdict == "blocked"),
        "no_invented_text": None,
    }
    if ranked is not None:
        src = [r.open_problem for r in ranked if r.tier == "main"]
        rep["no_invented_text"] = (
            len(src) == len(ps)
            and all(p.open_problem == s for p, s in zip(ps, src)))
    return rep


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    ranked = R.rank()
    ps = build(ranked)
    rep = report(ps, ranked)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"report": rep, "items": [p.to_dict() for p in ps]},
                  fh, ensure_ascii=False, indent=2)
    print("提案判定：%s" % rep["by_verdict"])
    print("三值之和 == 总数：%s" % rep["verdict_sum_matches"])
    print("可执行项四件齐备：%s" % rep["every_executable_has_four_parts"])
    print("被阻塞项都说明了缺什么：%s"
          % rep["every_blocked_says_what_is_missing"])
    print("未改写原文（对照 L1）：%s" % rep["no_invented_text"])
    for v in VERDICTS:
        sel = [p for p in ps if p.verdict == v]
        print("\n── %s（%d 条）──" % (v, len(sel)))
        for p in sel[:6]:
            print("  %-15s %s" % (p.arxiv_id, p.open_problem[:40]))
            if v == "blocked":
                print("      %s" % p.blocked_reason)
            elif v == "needs_human":
                print("      %s" % p.needs_human_reason)
            else:
                print("      对象=%s" % "、".join(p.object_candidates[:3]))
                print("      判据=%s 观测=%s"
                      % (p.criterion_hints[:2], p.observe_hints[:2]))
    print("\n结果已写入 %s" % os.path.relpath(OUT, os.getcwd()))
    return 0


def selftest() -> int:
    """注入反证：证明「写不出来」和「凭空造方案」都会被抓住。"""
    checks = 0

    def mk(aid, op, rel="", tier="main", score=1.0, types=("not_generalized",)):
        return R.Ranked(arxiv_id=aid, title="T", open_problem=op, url="",
                        project_relation=rel, gap_types=list(types),
                        fit_local=True, needs_decode=False, score=score,
                        reasons=["x"], tier=tier)

    # ── 1. 四件齐备 → 可执行 ──────────────────────────────────────
    #    这条 fixture 特意带"零样本"这类真观测量，不能用"感觉不行"凑。
    ok = extract_proposal(mk(
        "ok", "中文推理集上零样本绝对值仍低，需补英文评测集对比",
        "C1 是 gap 证据；与 X 仲裁无重；准确率待对比"))
    assert ok.verdict == "executable", ok.verdict
    assert ok.object_candidates and ok.criterion_hints and ok.observe_hints
    checks += 1

    # ── 2. 无判据 → blocked，并说清缺判据 ────────────────────────
    no_crit = extract_proposal(mk("b1", "某个东西待观察", "C1 是 gap 证据"))
    assert no_crit.verdict == "blocked", no_crit.verdict
    assert "判据" in no_crit.blocked_reason, no_crit.blocked_reason
    assert "判据" not in no_crit.blocked_reason.split("；缺")[0], \
        "blocked_reason 指错了缺件"
    checks += 1

    # ── 3. 涉及生产数据 → needs_human（不是 blocked）──────────────
    hum = extract_proposal(mk("h", "生产数据不可公开，复现门槛高", ""))
    assert hum.verdict == "needs_human", hum.verdict
    checks += 1

    # ── 4. **不得凭空造方案**：注入一个无对象的开放点 ────────────
    #    如果实现里有通用模板兜底，这里会变成 executable —— 那就是洗稿。
    vague = extract_proposal(mk("v", "感觉还有很多问题", ""))
    assert vague.verdict == "blocked", \
        "空泛开放点被判可执行：模块在凭空造方案"
    assert vague.object_candidates == [], "空泛开放点竟认出了对象"
    checks += 1

    # ── 5. 判据必须来自原文，不能来自我的想象 ────────────────────
    #    "要更快" 没有比较对象，只有形容词 —— 必须 blocked
    vague2 = extract_proposal(mk("v2", "要更快更准", "C1 是 gap 证据"))
    assert vague2.verdict == "blocked", "形容词堆砌被判可执行"
    checks += 1

    # ── 6. 四件齐备断言必须能失败 ─────────────────────────────────
    broken = Proposal(arxiv_id="x", verdict="executable", open_problem="o",
                      object_candidates=[], criterion_hints=["对比"],
                      observe_hints=["1"], why_now="w")
    assert report([broken])["every_executable_has_four_parts"] is False, \
        "四件齐备断言是装饰"
    checks += 1

    # ── 7. blocked 必须说明缺什么（空理由应被抓）─────────────────
    silent = Proposal(arxiv_id="y", verdict="blocked", open_problem="o")
    assert report([silent])["every_blocked_says_what_is_missing"] is False, \
        "静默阻塞未被抓住——人无从下手"
    checks += 1

    # ── 8. **槽位标签里的数字不算观测**（第一版真 bug 的反证）───
    #    `C1…C2…C3` 里的 1/2/3 是记账符号，不是测量。第一版 `\d` 让这条
    #    轻松通过"有可算的数"的门，于是 29 条压缩开放点被误判为可执行。
    slot_only = extract_proposal(mk(
        "slot", "覆盖不足待补", "C1是gap证据；C2模板；C3agent"))
    assert slot_only.verdict == "blocked", \
        r"纯槽位标签竟满足观测门——\d 在替记账符号背书"
    assert "观测" in slot_only.blocked_reason, slot_only.blocked_reason
    checks += 1

    #    反过来：真有计量数字时必须能通过（防止修过头）
    with_num = extract_proposal(mk(
        "num", "七语言外泛化待补", "C1是gap证据；与X仲裁无重"))
    assert with_num.verdict == "executable", with_num.verdict
    assert with_num.observe_hints, "真数字也没认出来——判据修过头了"
    checks += 1

    # ── 9. 判定不得依赖分数（高分也可能是空的）───────────────────
    hi = extract_proposal(mk("hi", "泛化不错", "C1 是 gap 证据", score=99.0))
    assert hi.verdict == "blocked", "高分让空条目蒙混过关——分数不该参与判定"
    checks += 1

    sys.stdout.write("RUNNER SELFTEST OK（%d 组断言）\n" % checks)
    return 0


# 守卫必须放在**所有**定义之后。原来它在 `selftest()` 上面，于是
# `python3 -m ai_researcher.runner --selftest` 在跑到 main() 里的
# `return selftest()` 时该名字还没被绑定 ⇒ NameError。这条门此前只在我从
# 另一个模块 import 后调用时验过，`-m` 这条真实使用路径从没跑过——
# **门没被执行过，和门不存在，在证据上是同一件事。**
if __name__ == "__main__":
    sys.exit(main())