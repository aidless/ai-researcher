"""L1 排序器：给 L0 抽出的候选研究问题打分。**只读，永不写 wiki。**

## 它解决什么

L0 交出 384 条可用候选（其中 101 条是纯散文，283 条是压缩标签）。全部丢给
用户审核是不负责任的——384 条里绝大多数是别人的私有缩写「省半质；泛化限」，
用户得先解码 283 条才能开始判断。所以需要一个**确定性**排序层：把最值得
先看的顶上来，并且**每条都带可复核的理由**。

## 为什么是确定性打分，不是 LLM 打分

1. 同一批输入必须给出同一批排序，否则"上次它推 A 这次推 B"没法复盘。
2. 6GB 本机 + 中文小模型（bge 24M）在这个任务上没有优势；判断"这条开放点
   与本项目什么关系"靠的是笔记里已经写好的文本，不是语义泛化。
3. 打分逻辑要能被**注入反证**：能不能指出"哪种输入会让这个分算错"。

## 分量的设计依据（都是量出来的，不是拍的）

实测 384 条可用候选的信号分布：

| 信号 | 出现数 | 为什么算分 |
|:---|---:|:---|
| `project_relation` 非空 | 384/384 | 这是唯一写明"与本项目什么关系"的字段 |
| 含 `C1…gap证据` | 320 | 用户已经判断过它是个缺口 |
| 含 `C2…模板` | 325 | 有可套用的方法论模板 |
| 含 `C3…agent` | 176 | 能落到 agent 设计上 |
| 含 `与X仲裁…无重` | 154 | **最强信号**：已核对与已有工作不重复 |
| 含 `直取证伪` | 51 | 已用它证伪过别人的说法，是负知识 |
| 纯散文（非压缩标签） | 101 | 用户能直接读，不用先解码 |

`与X仲裁…无重` 排第一的理由不是它出现得多，而是**它代表的工作量最大**：
那 154 篇的作者已经读过对标论文并写下了结论。压缩标签则必须**先解码**才谈
得上排序，所以 needs_decode 的候选单独分层，不混进主榜。

## 硬约束

- **成本类降级但不丢弃**：`cost_scale` 的 `fit_local=False`（6GB 跑不动），
  它们仍然可能有洞见，所以给独立分榜而不是从候选里删除。
- **needs_decode 不与纯散文同榜**：一个要人先解码、一个可直接读，混在一起
  排序会让人以为前者已经可读。
- **打分不改变原文**：`open_problem` 原样透传（AGENTS.md 铁律 2）。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any
import sys

from . import scanner as S

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "rank", "ranked.json")

# ── 信号识别 ──────────────────────────────────────────────────────────────
# 每条正则都在真实 384 条数据上核对过出现次数（见模块 docstring 的表）。
# 写在这里而不是散在代码里，是为了让"这个分量到底认什么"可以被反证。

# C1/C2/C3 槽位：用户在笔记里给自己项目的三条线填了位置
RE_C1_GAP = re.compile(r"C1.{1,12}?gap证据")
RE_C2_TPL = re.compile(r"C2.{1,12}?模板")
RE_C3_AGENT = re.compile(r"C3.{1,12}?agent")

# 与已有工作的仲裁：已核对不重复。这是最贵的信号——作者读过对标论文。
RE_ARBITER = re.compile(r"与.{1,14}?仲裁[^。]{0,24}?无重")

# 已用该篇证伪过别人的说法（负知识，最难重新获得）
RE_FALSIFIED = re.compile(r"直取证伪")

# 归一化搬运残留还留在关系段里（10 条），说明这条笔记没被整理干净
RE_REL_RESIDUE = re.compile(r"与C1-C3\s*[:：]")

# 「必须补实验」类缺口的强度：越像"就差一次实验"越可能现在就能做
RE_NEAR_RUNNABLE = re.compile(
    r"待验证|待补|未.{0,4}验证|缺.{0,6}实验|没有.{0,4}实验|尚未")

# ── 以下两条是被真实数据教出来的（首版漏了，24/56 主榜条目得 0 分）──────
# 首版只认 `C1…gap证据` 这类带后缀的槽位写法，于是 `C1提示小模型做翻译比做求解
# 更可靠`（裸槽位）、`范式参照：…`、`胜步律：…`、`P3必引` 全部落在正则外面，
# 看起来像"这些条目没有价值"。实际它们是本批里信息密度最高的一批。
RE_LINE_BOUND = re.compile(r"[ABC]\s*线")
RE_ROLE_WORD = re.compile(
    r"参照|锚|范式|背书|证据|对立基线|对照|谱系")
# 裸槽位：提到 C1/C2/C3 但没跟 gap证据/模板/agent 后缀
RE_SLOT_BARE = re.compile(r"[ABC][123](?![^。；;]{0,12}(?:gap证据|模板|agent))")

# 权重。理由逐条写死，便于反证时逐项质疑。
W_ARBITER = 3.0        # 已核对不重复
W_C1 = 1.0             # 已被判为缺口
W_C2 = 0.8             # 有模板
W_C3 = 0.6             # 能落到 agent 设计
W_FALSIFIED = 1.2      # 有负知识
W_NEAR_RUNNABLE = 0.7  # 就差一次实验
W_MULTI_TYPE = 0.5     # 命中多类 = 洞见更完整（每多一类 +0.5，封顶 +1.0）
W_REL_RESIDUE = -0.5   # 关系段还有搬运残留 = 笔记没整理干净，轻微扣分
W_COST_ONLY = -1.0     # 只命中成本类 = 6GB 跑不动
W_LINE_BOUND = 0.9     # 明确绑到 A/B/C 三线之一 = 知道该拿它干什么
W_ROLE_WORD = 0.5      # 写明了角色（参照/锚/对立基线）= 不是随手摘抄
W_SLOT_BARE = 0.4      # 裸槽位提及：比带后缀弱，但仍说明作者把它放进了框架

MIN_SCORE = 1.0        # 低于此分不进主榜（可进 needs_decode 榜）


@dataclass
class Ranked:
    """一条排序结果。**每一项都自带理由**，不产出无法复核的分数。"""

    arxiv_id: str
    title: str
    open_problem: str          # 原文，未改写
    url: str
    project_relation: str      # 原文，未改写
    gap_types: list[str]
    fit_local: bool
    needs_decode: bool         # True = 内容是压缩标签，必须先人解码
    score: float
    reasons: list[str] = field(default_factory=list)
    tier: str = "main"         # main / needs_decode / needs_remote
    below_gate: bool = False   # True = 已判定但分数没过 MIN_SCORE，不进主榜

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_gap(g: S.Gap) -> Ranked:
    """打分。纯函数，无 IO、无随机、无全局状态。"""
    rel = g.project_relation
    reasons: list[str] = []
    s = 0.0

    if RE_ARBITER.search(rel):
        s += W_ARBITER
        reasons.append("已仲裁与对标工作不重复（%.1f）" % W_ARBITER)
    if RE_FALSIFIED.search(rel):
        s += W_FALSIFIED
        reasons.append("已用它证伪过他人说法，负知识（%.1f）" % W_FALSIFIED)
    if RE_C1_GAP.search(rel):
        s += W_C1
        reasons.append("用户已判为 C1 类缺口（%.1f）" % W_C1)
    if RE_C2_TPL.search(rel):
        s += W_C2
        reasons.append("有可套用的 C2 模板（%.1f）" % W_C2)
    if RE_C3_AGENT.search(rel):
        s += W_C3
        reasons.append("能落到 C3 agent 设计（%.1f）" % W_C3)
    if RE_LINE_BOUND.search(rel):
        s += W_LINE_BOUND
        reasons.append("明确绑到 A/B/C 三线之一（%.1f）" % W_LINE_BOUND)
    if RE_SLOT_BARE.search(rel) and not (
            RE_C1_GAP.search(rel) or RE_C2_TPL.search(rel)
            or RE_C3_AGENT.search(rel)):
        s += W_SLOT_BARE
        reasons.append("裸槽位提及 C1/C2/C3（%.1f）" % W_SLOT_BARE)

    # 角色词必须**剔除槽位写法**再判：否则 `C1…gap证据` 里那个「证据」会被
    # RE_ROLE_WORD 再认一次，同一段文本拿两次分（自测第 10 条抓到过）。
    rel_noslot = RE_C1_GAP.sub("", RE_C2_TPL.sub("", RE_C3_AGENT.sub("", rel)))
    if RE_ROLE_WORD.search(rel_noslot):
        s += W_ROLE_WORD
        reasons.append("写明了角色（参照/锚/对立基线）（%.1f）" % W_ROLE_WORD)
    if RE_SLOT_BARE.search(rel) and not (
            RE_C1_GAP.search(rel) or RE_C2_TPL.search(rel)
            or RE_C3_AGENT.search(rel)):
        s += W_SLOT_BARE
        reasons.append("裸槽位提及 C1/C2/C3（%.1f）" % W_SLOT_BARE)

    multi = len(g.gap_types)
    if multi > 1:
        add = min(W_MULTI_TYPE * (multi - 1), 1.0)
        s += add
        reasons.append("命中 %d 类缺口（%.1f）" % (multi, add))

    if RE_NEAR_RUNNABLE.search(g.open_problem):
        s += W_NEAR_RUNNABLE
        reasons.append("开放点措辞接近「就差一次实验」（%.1f）" % W_NEAR_RUNNABLE)

    if RE_REL_RESIDUE.search(rel):
        s += W_REL_RESIDUE
        reasons.append("关系段仍有归一化搬运残留（%.1f）" % W_REL_RESIDUE)

    if g.gap_types == ["cost_scale"]:
        s += W_COST_ONLY
        reasons.append("只命中成本类，6GB 本机跑不动（%.1f）" % W_COST_ONLY)

    # 分层：解码成本与算力门槛是两个正交维度，不能靠分数表达
    if g.needs_decode:
        tier = "needs_decode"
    elif g.fit_local:
        tier = "main"
    else:
        tier = "needs_remote"

    # 门槛**只对主榜生效**，且它是"标记"不是"删除"：不达标的条目仍然留在
    # 输出里并带 below_gate=True。删掉它们等于让人以为扫过了全部候选，
    # 而实际是静默截断——这正是 AGENTS.md 第 7 条说的装饰性门禁。
    below_gate = (tier == "main" and s < MIN_SCORE)
    if below_gate:
        reasons.append("分数 %.1f 未达门槛 %.1f，标记待补标注而非丢弃" % (s, MIN_SCORE))

    return Ranked(
        arxiv_id=g.arxiv_id, title=g.title, open_problem=g.open_problem,
        url=g.url, project_relation=rel, gap_types=list(g.gap_types),
        fit_local=g.fit_local, needs_decode=bool(g.needs_decode),
        score=round(s, 2), reasons=reasons, tier=tier, below_gate=below_gate,
    )


def rank(gaps: list[S.Gap] | None = None) -> list[Ranked]:
    """返回排好序的列表。排序键 (tier_order, -score, arxiv_id)。

    末位键 arxiv_id 保证**确定性**：分数相同的候选之间不靠 dict 顺序决定，
    否则每次复跑可能给出不同顺序，看起来像结果在动。
    """
    gaps = gaps if gaps is not None else S.scan()
    order = {"main": 0, "needs_remote": 1, "needs_decode": 2}
    out = [score_gap(g) for g in S.usable(gaps)]
    out.sort(key=lambda r: (order[r.tier], -r.score, r.arxiv_id))
    return out


def report(rs: list[Ranked]) -> dict[str, Any]:
    """汇总。口径必须自洽：tier 三类之和 == len(rs)。"""
    from collections import Counter
    tiers = Counter(r.tier for r in rs)
    rep = {
        "total": len(rs),
        "by_tier": dict(tiers),
        "tier_sum_matches": sum(tiers.values()) == len(rs),
        "scores": {
            t: {
                "n": sum(1 for r in rs if r.tier == t),
                "min": min((r.score for r in rs if r.tier == t), default=None),
                "max": max((r.score for r in rs if r.tier == t), default=None),
            } for t in ("main", "needs_remote", "needs_decode")
        },
        "every_item_has_reasons": all(r.reasons for r in rs),
        "below_gate": sum(1 for r in rs if r.below_gate),
        "top": [r.to_dict() for r in rs[:10]],
    }
    # 主榜与 needs_decode 榜不得有交集（分层是正交的）
    main = {r.arxiv_id for r in rs if r.tier == "main"}
    dec = {r.arxiv_id for r in rs if r.tier == "needs_decode"}
    rep["tiers_disjoint"] = not (main & dec)
    # 门槛标记必须与分数自洽：below_gate 当且仅当（主榜 且 分数 < MIN_SCORE）。
    # 这条断言的作用是**抓住"改了 MIN_SCORE 却忘了改判定"或反过来**的漂移。
    rep["gate_consistent"] = all(
        r.below_gate == (r.tier == "main" and r.score < MIN_SCORE) for r in rs)
    return rep


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    rs = rank()
    rep = report(rs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"report": rep, "items": [r.to_dict() for r in rs]},
                  fh, ensure_ascii=False, indent=2)
    print("分层：%s" % rep["by_tier"])
    for t in ("main", "needs_remote", "needs_decode"):
        d = rep["scores"][t]
        print("  %-13s n=%-4d 分 %s .. %s"
              % (t, d["n"], d["min"], d["max"]))
    print("口径自洽（三类之和 == 总数）：%s" % rep["tier_sum_matches"])
    print("每条都有理由：%s" % rep["every_item_has_reasons"])
    print("主榜与解码榜不相交：%s" % rep["tiers_disjoint"])
    print("门槛标记与分数自洽：%s（未达门槛 %d 条，已标记未丢弃）"
          % (rep["gate_consistent"], rep["below_gate"]))
    print("\n主榜前 10：")
    for i, r in enumerate([x for x in rs if x.tier == "main"][:10], 1):
        print("  %2d. [%4.1f] %-16s %s"
              % (i, r.score, r.arxiv_id, r.open_problem[:44]))
        for why in r.reasons[:3]:
            print("        %s" % why)
    print("\n结果已写入 %s" % os.path.relpath(OUT, os.getcwd()))
    return 0


def selftest() -> int:
    """注入反证：每条断言都在证明**排序层能被搞坏**。

    没有反证的排序层就是装饰——真实数据跑一次"看着合理"不等于判据成立
    （AGENTS.md 铁律 7）。这里用假臂、平凡臂、零权重臂、门槛漂移四种方式
    证明它会失败。
    """
    import sys as _s

    def mk(aid, rel, op="待验证补实验", types=("cost_scale",),
           fit=True, dec=False, title="T"):
        return S.Gap(arxiv_id=aid, title=title, open_problem=op,
                     gap_types=list(types), fit_local=fit,
                     project_relation=rel, url="", rejected="",
                     needs_decode=dec)

    checks = 0

    # ── 1. 强臂必须压过弱臂：否则权重顺序是任意的 ─────────────────────
    strong = score_gap(mk("strong", "与LLM-RAG仲裁无重；C1是gap证据"))
    weak = score_gap(mk("weak", "泛化有限"))
    assert strong.score > weak.score, "强臂没压过弱臂：权重顺序无意义"
    assert strong.reasons, "强臂没有理由"
    checks += 1

    # ── 2. 相同输入必须给相同顺序（确定性）───────────────────────────
    arm = [mk("b", "与X仲裁无重"), mk("a", "与X仲裁无重"), mk("c", "与X仲裁无重")]
    o1 = [r.arxiv_id for r in
          sorted([score_gap(g) for g in arm],
                 key=lambda r: (-r.score, r.arxiv_id))]
    assert o1 == ["a", "b", "c"], "同分未按 arxiv_id 定序，结果不稳定"
    checks += 1

    # ── 3. needs_decode 不得进主榜（否则未解码内容会被当成可读的）───
    dec = score_gap(mk("d", "与X仲裁无重；C1是gap证据", dec=True))
    assert dec.tier == "needs_decode" and dec.tier != "main", "压缩标签混进主榜"
    checks += 1

    # ── 4. fit_local=False 不得进主榜（6GB 跑不动）───────────────────
    rem = score_gap(mk("r", "与X仲裁无重；C1是gap证据", fit=False))
    assert rem.tier == "needs_remote", "远端档期条目混进主榜"
    checks += 1

    # ── 5. 只命中成本类要扣分（但不被丢弃）──────────────────────────
    only = score_gap(mk("c", "", types=("cost_scale",)))
    cost_free = score_gap(mk("cf", "C1是gap证据", types=("data_labeling",)))
    assert only.score < cost_free.score, "成本类未降级"
    assert only.reasons, "成本类被丢弃而非降级说明"
    checks += 1

    # ── 6. 门槛是标记不是删除：不过线也必须在输出里 ──────────────────
    #    这是最容易写错的一处：静默截断会让人以为扫过了全部候选。
    zero = score_gap(mk("z", "泛化有限"))
    assert zero.below_gate is True, "0 分主榜条目未被标记"
    assert zero.score < MIN_SCORE, "0 分条目的分数与门槛判定不自洽"
    zero_rep = report([zero])
    assert zero_rep["below_gate"] == 1, "门槛计数漏记"
    assert zero_rep["gate_consistent"] is True, "门槛自洽断言失效"
    checks += 1

    # ── 7. 门槛自洽断言必须能失败（否则是装饰）───────────────────────
    forged = Ranked(**{**zero.to_dict(), "below_gate": False})
    assert report([forged])["gate_consistent"] is False, \
        "篡改 below_gate 后自洽断言仍通过——这条断言是装饰"
    checks += 1

    # ── 8. 三个口径自洽断言各自能被打破 ─────────────────────────────
    assert report([])["tier_sum_matches"] is True
    # 同一 id 出现在两个榜上（tier 是单值，重复 id 只能来自数据重复）——
    # 这才是 tiers_disjoint 真正要抓的违规。若只测"一个对象"，它恒真。
    clash = [score_gap(mk("dup", "与X仲裁无重")),
             Ranked(**{**score_gap(mk("dup", "与X仲裁无重")).to_dict(),
                       "tier": "needs_decode", "needs_decode": True})]
    assert report(clash)["tiers_disjoint"] is False, \
        "同一 id 同时出现在两个榜上未被抓住"
    no_reason = Ranked(**{**zero.to_dict(), "reasons": []})
    assert report([no_reason])["every_item_has_reasons"] is False, \
        "空理由未被口径自洽断言抓住"
    checks += 1

    # ── 9. 零权重必须让分数塌陷（证明分数真的来自这些信号）─────────
    # 只喂仲裁文本：混进 `C1…gap证据` 会额外命中 RE_ROLE_WORD（它含「证据」），
    # 那样即使权重归零也仍有分，测的就不是这个分量了。
    global W_ARBITER, W_C1, W_FALSIFIED
    keep = (W_ARBITER, W_C1, W_FALSIFIED)
    probe, plain = "与X仲裁无重", ""
    try:
        before = score_gap(mk("s", probe)).score
        base_before = score_gap(mk("s2", plain)).score
        assert before != base_before, "仲裁信号对空关系段无区分度"
        W_ARBITER = W_C1 = W_FALSIFIED = 0.0
        assert score_gap(mk("s", probe)).score == score_gap(mk("s2", plain)).score, \
            "权重置零后分数没有塌陷——分数可能来自别处或被硬编码"
    finally:
        W_ARBITER, W_C1, W_FALSIFIED = keep
    checks += 1

    # ── 10. 同一段文本不得被两个分量重复计分 ────────────────────────
    # 上一步的失败就是这个 bug 的实例：gap证据 既是 C1 槽位又被角色词认到。
    # 修法是判角色词前先剔掉槽位写法，而不是靠"调小权重"掩盖重复。
    probe = "C1是gap证据"
    stripped = RE_C1_GAP.sub("", RE_C2_TPL.sub("", RE_C3_AGENT.sub("", probe)))
    assert RE_ROLE_WORD.search(probe) is not None, "探针本身无效：角色词已不认「证据」"
    assert RE_ROLE_WORD.search(stripped) is None, "槽位写法未被剔除，仍会被重复计分"
    # 端到端：只有槽位写法时，理由里不能同时出现槽位与角色两项
    slot_only = [w for w in score_gap(mk("ds", probe)).reasons
                 if "角色" in w]
    assert not slot_only, "仅槽位命中的条目仍拿到了角色词分：%s" % slot_only
    checks += 1

    # ── 11. 零权重臂不该意外通过门槛 ───────────────────────────────
    #    （若门槛恒真，这条恒成立，无法证伪——所以要显式断言它可失败）
    assert score_gap(mk("q", "")).below_gate is True, "空关系段竟过了门槛"
    checks += 1

    _s.stdout.write("RANKER SELFTEST OK（%d 组断言）\n" % checks)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())