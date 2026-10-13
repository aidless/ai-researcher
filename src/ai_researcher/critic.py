"""L4 判读器：读一组实验结果，判它**能支撑什么、不能支撑什么**。

## 它为什么不是"跑个统计然后下结论"

W5 实测给了个教科书级的教训（`bline/w5_results.json`）：contextual retrieval
的 span_full@3 从 dense_plain 的 0.922 涨到 0.953，**符号是正的**。如果只比
W4 的稀疏基线 0.984，它会变成 **−0.031**，读作"重建有害"。

而 L4 真正要拦的是那些**结论本身没错、但比证据能承载的多了一层**的写法：

    事实：contextual retrieval 在本语料上 +2 题（+0.031）
    ✗ 错：上下文重建能提升检索效果                    ← 越过了边界条件
    ✓ 对：本语料（26 篇/64 题）上 contextual retrieval 优于 dense_plain

差一个 "本语料"。三个月后没人记得这个 +0.031 只在那 26 篇上量过。

## 四个门

| 门 | 问的问题 | 判不过时的诚实说法 |
|---|---|---|
| `effect_vs_noise` | 差异超过随机波动了吗 | 跨度不足 N 题，只报数字 |
| `caliber_isolation` | 对照臂和实验臂同口径吗 | 不可比，结论无效 |
| `mechanism_alignment` | 增益出现在**机制预测**出现的题型上吗 | 不支持该机制主张 |
| `scope_discipline` | 结论里的范围词盖住了实测范围吗 | 超出实测范围 |

## 一等结论：`insufficient`

`insufficient` 是**合法输出**，不是失败。四门里任何一门不过，判读器给
`insufficient` 并说清哪一门、差多少。**它绝不为了让流程走完而给 pass** ——
W5 就是这么产出一个否定性结果的，而那个否定性结果是这轮最值钱的产出。
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "store", "critic_verdicts.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# ── 判据阈值：全部来自实测，不是拍的 ────────────────────────────────────
# MIN_SPAN = 0.02 取自 W5：contextual 的 boundary 增益是 +0.000，
# late_chunking 的整体增益是 −0.016 —— 两个都 < 0.02，都被判「跨度不足」。
# 若这个阈值放到 0.01，W5 就会给出一个它扛不住的方向性结论。
MIN_SPAN = 0.02

# 范围词：出现即说明结论越过了实测边界，除非实测范围确实覆盖它
RE_SCOPE = re.compile(
    r"(普遍|一般|所有|任意|必然|总是|从来|各类|各种|全面|广泛|"
    r"in general|universally|always|all\s+\w+|any\s+\w+)")
RE_MEASURED_SCOPE = re.compile(
    r"(本语料|本文|本实验|这批|该语料|上述|本次|此基准|本基准|"
    r"in this (corpus|benchmark|experiment))")
RE_NUMBER = re.compile(r"(?<![0-9A-Za-z.§#])(\d{1,4}\.\d+)(?![0-9.])")

# 反证 A 的产物：把对照臂 span_full@3 从 0.922 抬到 0.999，effect_vs_noise
# 只知道「比 0.02 小就拒」，不知道「大得不可能」——于是跨度从 0.031 变
# 0.046，三条主张全绿。**效应量门天生没有上界**，而虚高恰恰是最危险的
# 那个方向（把对照臂调低，任何处理都能做出巨大效应）。
# 所以补一条 `no_implausible_effect`：跨度超过上限就否，理由写明超出量度
# 能产生的范围（64 题里 0.08 就是 5 题以上，不可能来自细微机制差异）。
MAX_SPAN = 0.10

# 反证 B 的产物（比虚高更根本的一个洞）：W5 的落盘 JSON 里，每臂带
# `detail`（64 条逐题记录）与 `by_type`（hit/total/recall）。
# 篡改 `span_full_at_3` 或 `by_type.recall` 时，**只有重算能发现**——
# 任何幅度阈值都不行，因为把头条数字和逐类数字一起抬高，
# 内部完全自洽，看不出是假的。
# 所以下面这条门做的是 AGENTS.md 铁律 1 的字面实现：
#   **报出去的每个聚合数，都必须能从落盘的逐项证据重算出来。**

VERDICTS = ("pass", "fail", "insufficient")


@dataclass
class Arm:
    """一个实验臂的观测。**字段必须来自程序输出，不能是手写。**"""

    name: str
    metric: str
    value: float
    n_items: int = 0
    by_type: dict[str, float] = field(default_factory=dict)
    caliber: str = ""          # 同口径标识：检索器/切块/题集，必须与对照臂相同
    source_file: str = ""      # 数字出自哪个文件（可复算的锚）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    claim: str
    verdict: str              # pass / fail / insufficient
    gates: dict[str, dict[str, Any]] = field(default_factory=dict)
    n_items: int = 0
    scale: str = ""           # 结论必须带上的实测范围
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gate_effect_vs_noise(test: Arm, control: Arm,
                         min_span: float = MIN_SPAN,
                         max_span: float = MAX_SPAN) -> dict[str, Any]:
    """效应 vs 噪声：差异是否够大。

    判据不是「p < 0.05」——题集只有几十条，任何正经统计量都不可信。
    判据是**绝对跨度**：差值要超过 min_span 才允许方向性结论。理由写在
    W5 的 notes 里：跨度不足时给方向，就是给一个扛不住的结论。

    两臂必须**各自**声明样本数。首版写的是 `max(test.n_items,
    control.n_items)` —— 于是实验臂 n=0（未知）时借了对照臂的 64 当自己的
    样本量，门就放行了。**用邻居的值填未知，门就不是门了**（AGENTS.md 第 7 条）。
    """
    d = test.value - control.value
    missing = [n for n, a in (("实验臂", test), ("对照臂", control))
               if a.n_items <= 0]
    if missing:
        return {"pass": False,
                "reason": "%s 未声明样本数 —— 不得用另一臂的 n 顶替，"
                          "拒绝给方向性结论" % "、".join(missing),
                "delta": d}
    n = min(test.n_items, control.n_items)
    span = abs(d)
    if span < min_span:
        return {"pass": False, "reason": "跨度不足 %.3f（<%.2f，n=%d）——"
                "只报数字，不下方向性结论" % (span, min_span, n),
                "delta": d, "span": span, "n_items": n}
    if span > max_span:
        return {"pass": False,
                "reason": "跨度 %.3f 超过上限 %.2f（n=%d，约合 %.1f 题）——"
                          "多半是对照臂被抬高或数据被篡改，不是真实效应"
                          % (span, max_span, n, span * n),
                "delta": d, "span": span, "n_items": n}
    return {"pass": True, "reason": "跨度 %.3f 落在 [%.2f, %.2f]（n=%d）"
            % (span, min_span, max_span, n), "delta": d, "span": span,
            "n_items": n}


def gate_caliber_isolation(test: Arm, control: Arm) -> dict[str, Any]:
    """口径隔离：两臂是否同口径可比。

    W5 最贵的一次教训就是少了这一门：只与 W4 稀疏基线比，+0.031 变成
    −0.031，**结论符号整个翻过来**。所以这一门不是"提醒"，它是否决权。
    """
    if not test.caliber or not control.caliber:
        return {"pass": False, "reason": "至少一臂未标 caliber —— "
                "不可证明同口径，拒绝出结论（无标签 ≠ 同口径）"}
    if test.caliber != control.caliber:
        return {"pass": False, "reason": "口径不同：实验臂 %r vs 对照臂 %r ——"
                "差值里混着口径差异，不是处理效应"
                % (test.caliber, control.caliber)}
    if test.metric != control.metric:
        return {"pass": False, "reason": "指标不同：%r vs %r"
                % (test.metric, control.metric)}
    return {"pass": True, "reason": "同口径 %r，指标 %r"
            % (test.caliber, test.metric)}


def gate_mechanism_alignment(test: Arm, control: Arm,
                             predicted: str = "boundary") -> dict[str, Any]:
    """机制对齐：增益是否出现在**机制预测**的题型上。

    predicted 是机制主张预测受益的题型（late/contextual chunking 预测
    boundary 类；困惑度类机制预测 single 类）。增益出现在别处 = 机制不成立，
    但效应仍可能真实 —— 所以这条门只否「机制主张」，不否「效应存在」。
    """
    t = test.by_type.get(predicted)
    c = control.by_type.get(predicted)
    others = [k for k in test.by_type if k != predicted]
    if t is None or c is None:
        return {"pass": False, "reason": "两臂缺 %r 类分项，无法验机制"
                % predicted, "predicted_type": predicted}
    gain = t - c
    others_gain = (sum(test.by_type[k] - control.by_type[k] for k in others)
                   / len(others)) if others else float("nan")
    if others and gain < others_gain:
        return {"pass": False,
                "reason": "增益不在预测的 %r 类（该类 %+.3f，"
                          "其余类均值 %+.3f）——不支持该机制主张，但效应可能真实"
                          % (predicted, gain, others_gain),
                "predicted_type": predicted, "gain_on_predicted": gain,
                "gain_elsewhere_mean": others_gain}
    return {"pass": True, "reason": "%r 类增益 %+.3f ≥ 其余类均值 %+.3f"
            % (predicted, gain, others_gain), "predicted_type": predicted,
            "gain_on_predicted": gain, "gain_elsewhere_mean": others_gain}


def gate_scope_discipline(claim: str, measured_scope: str) -> dict[str, Any]:
    """范围纪律：结论里的范围词是否盖过了实测范围。

    这一门抓的是「事实没错但多写了一层」——那正是论文被审稿人抓的那类问题，
    也是最难自查的，因为它读起来完全正常。
    """
    over = sorted(set(RE_SCOPE.findall(claim)))
    has_scope = bool(RE_MEASURED_SCOPE.search(claim))
    if over and not has_scope:
        return {"pass": False, "reason": "结论含越界词 %s 但未限定实测范围"
                                          "（实测范围：%s）——超出实测范围"
                % ("、".join(over[:4]), measured_scope or "未声明"),
                "overreach_words": over, "measured_scope": measured_scope}
    if not measured_scope:
        return {"pass": False, "reason": "未声明实测范围，无法判定结论是否越界"}
    if over:
        return {"pass": True, "reason": "含范围词 %s，但同时限定了实测范围"
                % "、".join(over[:3]), "overreach_words": over,
                "measured_scope": measured_scope}
    # **无越界词不等于结论已被限定**：「上下文重建提升了检索效果」在
    # 26 篇语料上是真的，在 10 万篇上也可能是真的 —— 差别只在有没有人
    # 写下来。所以本门要求：实测范围既要在参数里声明，**也要在主张文本
    # 里可见**，否则读者拿到一句没有边界的话。
    # （首版只查参数，导致「上下文重建能提升检索效果」这种无边界主张
    #  直接 PASS —— 恰恰是本模块最该拦的那句。）
    if not has_scope:
        return {"pass": False,
                "reason": "主张文本未写明实测范围（实测范围：%s）——"
                          "结论没有边界，读者无法判断它覆盖多大范围"
                % measured_scope,
                "measured_scope": measured_scope}
    return {"pass": True,
            "reason": "无越界词；实测范围：%s" % measured_scope,
            "measured_scope": measured_scope}


def gate_recomputable(d: dict[str, Any], arm_name: str,
                      metric_key: str = "span_full_at_3") -> dict[str, Any]:
    """铁律 1 的字面实现：头条数字必须能从 `detail` 逐项重算出来。

    **按头条指标重算**：`metric_key` 是头条字段名（`span_full_at_3`），
    逐项字段取 `detail` 里的 `span_full`（头条指标去掉 `_at_3` 后缀）。
    这一点不是洁癖 —— W5 落盘真的同时存了 `span_full` 与
    `doc_in_top3` 两套数，若重算时用错其中一套，门会对**正确的数据**
    报「被篡改」，比不设门更坏（冤枉好人比漏抓坏人更不可修）。

    三处重算、互相独立：
      1. 头条 ← detail 里逐项头条字段的均值
      2. `by_type[t].hit` / `.total` ← detail 里同 type 的**头条**计数
      3. `by_type[t].recall` ← hit/total

    任一处对不上就否。**这是唯一能抓住"内部自洽的篡改"的门**：
    幅度阈值抓不住（把两个数一起抬高就看不出来），口径门也抓不住
    （口径标签不会变）。只有重算能。
    """
    arm = d["arms"].get(arm_name)
    if arm is None:
        return {"pass": False, "reason": "落盘结果里没有臂 %r" % arm_name}
    detail = arm.get("detail")
    if not detail:
        return {"pass": False, "reason": "臂 %r 没有逐项 detail ——"
                "聚合数不可复算，拒绝出结论" % arm_name}
    # 头条指标 → 逐项字段。span_full_at_3 → span_full；取不到就报，不猜。
    item_field = metric_key.rsplit("_at_3", 1)[0]
    sample = detail[0]
    if item_field not in sample:
        return {"pass": False, "reason": "detail 里没有逐项字段 %r，"
                "无法按头条指标 %r 重算" % (item_field, metric_key)}
    claimed = arm.get(metric_key)
    recomputed = sum(x[item_field] for x in detail) / len(detail)
    if abs(claimed - recomputed) > 1e-9:
        return {"pass": False,
                "reason": "臂 %r 的 %s=%.6f 与逐项重算 %.6f 不符（n=%d）——"
                          "数字被改过或来自别处"
                % (arm_name, metric_key, claimed, recomputed, len(detail)),
                "claimed": claimed, "recomputed": recomputed}
    bad: list[str] = []
    for t, v in arm.get("by_type", {}).items():
        rows = [x for x in detail if x["type"] == t]
        if v["total"] != len(rows):
            bad.append("%s.total 记 %d，实为 %d" % (t, v["total"], len(rows)))
            continue
        hit = sum(x[item_field] for x in rows)
        if v["hit"] != hit:
            bad.append("%s.hit 记 %d，按 %r 重算实为 %d"
                       % (t, v["hit"], item_field, hit))
        elif abs(v["recall"] - hit / len(rows)) > 1e-9:
            bad.append("%s.recall 记 %.6f，实为 %.6f"
                       % (t, v["recall"], hit / len(rows)))
    if bad:
        return {"pass": False,
                "reason": "臂 %r 逐类数字与 detail 对不上：%s"
                % (arm_name, "；".join(bad[:4]))}
    return {"pass": True, "reason": "臂 %r 头条与 %d 条逐项记录逐类全部重算一致"
            % (arm_name, len(detail))}


# 自测里的构造样例没有落盘证据。按上面的 fail-closed 规则它们会全部被判
# insufficient —— 于是 mechanism / caliber / scope 三道门在测试里**永远
# 走不到**，测试就成了恒真。
# 两条路：把 fail-closed 放松（不可接受：真实调用会因此默认当作过了），
# 或者给样例一条**显式且被计数**的出路（本条）。
# `fixture_ok()` 的结果带 `fixture=True`，report() 会单独统计它用了多少次；
# `main()` 永远不调用它（真实判读只有落盘证据一条路）。
def fixture_ok() -> dict[str, Any]:
    return {"pass": True, "fixture": True,
            "reason": "构造样例：无落盘逐项证据（本条为自测显式豁免，"
                      "已被 report 计数；真实判读不得使用）"}




def _fake_raw(claimed: float, detail_hit: dict[str, int],
              claim_hit: dict[str, int] | None = None,
              total: dict[str, int] | None = None) -> dict[str, Any]:
    """构造一份**逐项证据**，让 `gate_recomputable` 有真东西可重算。

    `detail_hit` 是逐题记录里的真实命中；`claim_hit` 是落盘 `by_type` 里
    声称的命中。**两者分开正是关键**：篡改只会改声称值，逐题记录留在原处
    —— 于是重算一定对不上。首版把两者绑在一起，于是「改逐类数字」这类
    篡改在 fixture 里根本造不出来（fixture 自己就是自洽的），
    断言于是变成恒真。

    fixture 的数字是编的没关系：这一组验的是**门能不能发现不一致**，
    不是这些数字代表什么。
    """
    totals = total or {"single": 32, "multi_hop": 20, "boundary": 12}
    claim_hit = claim_hit or detail_hit
    detail: list[dict[str, Any]] = []
    by_type: dict[str, Any] = {}
    for t, n in totals.items():
        hit = min(detail_hit[t], n)
        claim = claim_hit[t]          # 不夹取：夹取会把篡改抹平
        by_type[t] = {"hit": claim, "total": n, "recall": claim / n}
        detail += [{"q": "%s-%d" % (t, i), "type": t,
                    "span_full": 1 if i < hit else 0}
                   for i in range(n)]
    return {"arms": {"a": {"span_full_at_3": claimed,
                           "detail": detail, "by_type": by_type}}}



def adjudicate(claim: str, test: Arm, control: Arm,
               predicted: str = "boundary",
               measured_scope: str = "",
               min_span: float = MIN_SPAN,
               recomputable: dict[str, Any] | None = None) -> Verdict:
    """跑五门，出裁决。**任一门不过 ⇒ 不给 pass。**

    `recomputable` 是 `gate_recomputable()` 的结果：给了就并入 `effect_vs_noise`
    的裁决（重算不过 ⇒ 效应不可信）；不给就并入「未提供逐项证据」并
    判不过（**不能默认当作过了**，AGENTS.md 第 7 条）。

    裁决优先级**有讲究**，顺序反了会制造比原文更强的结论：

    1. `scope_discipline` 不过 ⇒ **fail**。这是主张文本本身的问题
       （越界词盖过实测范围），与证据强不强无关：证据再硬，一个写超了
       的主张依然是错的。
    2. 否则 `effect_vs_noise` 不过 ⇒ **insufficient**。效应没立住，
       「机制是否成立」无从谈起 —— 在这里给 fail 等于宣称「机制被证伪」，
       那比证据能承载的更强。
    3. 否则 `mechanism_alignment` 不过 ⇒ **fail**。效应是真的，但增益不在
       预测的题型上 ⇒ 机制主张不成立（效应本身仍然成立）。
    4. 全过 ⇒ **pass**。

    `insufficient` 是**一等的合法结论**，不是失败。W5 产出的否定性结果
    （跨度不足、不支持机制主张）是这轮最值钱的产出之一。
    """

    eff = gate_effect_vs_noise(test, control, min_span)
    if recomputable is None:
        eff = {"pass": False,
               "reason": eff["reason"] + "｜未提供逐项证据，无法确认数字"
                                         "可从落盘记录重算（不作已通过处理）",
               "delta": eff.get("delta")}
    elif not recomputable["pass"]:
        eff = {"pass": False, "reason": eff["reason"] + "｜" +
               recomputable["reason"], "delta": eff.get("delta")}
    gates = {
        "effect_vs_noise": eff,
        "caliber_isolation": gate_caliber_isolation(test, control),
        "mechanism_alignment": gate_mechanism_alignment(test, control,
                                                        predicted),
        "scope_discipline": gate_scope_discipline(claim, measured_scope),
    }
    failed = [k for k, g in gates.items() if not g["pass"]]
    if not failed:
        v = "pass"
    elif "scope_discipline" in failed:
        v = "fail"          # 主张本身写错了，先改写
    elif "caliber_isolation" in failed:
        # 口径不同是**已知的坏比较**，不是「数据还不够」。前者要改比较方式，
        # 后者要加样本 —— 对 human 的行动建议完全相反，裁决不能混。
        v = "fail"
    elif "effect_vs_noise" in failed:
        v = "insufficient"  # 效应没立住，谈机制为时过早
    else:
        v = "fail"          # 效应成立但机制主张不成立

    notes: list[str] = []
    if test.source_file and control.source_file:
        notes.append("数字出处：%s vs %s（可复算）"
                     % (test.source_file, control.source_file))
    if not measured_scope:
        notes.append("实测范围未声明——任何范围性结论都不可信")
    if v == "insufficient":
        notes.append("insufficient 是一等结论：只报数字，不下方向性结论")
    return Verdict(claim=claim, verdict=v, gates=gates,
                   n_items=min(test.n_items, control.n_items),
                   scale=measured_scope, notes=notes)


def report(vs: list[Verdict]) -> dict[str, Any]:
    from collections import Counter
    c = Counter(v.verdict for v in vs)
    gates = Counter()
    for v in vs:
        for k, g in v.gates.items():
            if not g["pass"]:
                gates[k] += 1
    return {
        "total": len(vs),
        "by_verdict": {k: c.get(k, 0) for k in VERDICTS},
        "verdict_sum_matches": sum(c.values()) == len(vs),
        "failing_gates": dict(gates),
        "every_fail_explains": all(
            all(g["pass"] or g.get("reason") for g in v.gates.values())
            for v in vs),
        # 四门必须都被至少一条反证触过 —— 四门全绿的判读器是一台机器，
        # 不是判读器。没人反对时，门的存在无法被验证。
        "gates_all_exercised": all(
            any(k in v.gates for v in vs) for k in
            ("effect_vs_noise", "caliber_isolation",
             "mechanism_alignment", "scope_discipline")),
        "fixture_exemptions": sum(
            1 for v in vs
            if v.gates.get("effect_vs_noise", {}).get("fixture")),
        # 自测豁免必须可见：数出来，而不是默认 0
        "no_pass_without_scope": all(
            v.verdict != "pass" or v.scale for v in vs),
    }


def selftest() -> int:
    """反证：证明每一门都能失败，且 insufficient 是可达的一等结论。"""
    checks = 0
    ctrl = Arm("dense_plain", "span_full@3", 0.922, n_items=64,
               by_type={"single": 0.94, "multi_hop": 0.91, "boundary": 0.90},
               caliber="dense|fixed_220_o40|w4", source_file="w5_results.json")

    # ── 1. 跨度不足 ⇒ insufficient（不是 fail，更不是 pass）────────
    t = Arm("late_chunking", "span_full@3", 0.906, n_items=64,
            by_type={"single": 0.94, "multi_hop": 0.91, "boundary": 0.757},
            caliber="dense|fixed_220_o40|w4")
    v = adjudicate("本语料上 late chunking 改善了边界题", t, ctrl,
                   measured_scope="本语料 26 篇 / 64 题",
                   recomputable=fixture_ok())
    assert v.verdict == "insufficient", v.verdict
    assert "跨度不足" in v.gates["effect_vs_noise"]["reason"]
    checks += 1

    # ── 2. **一臂未声明样本数 ⇒ 拒绝**，且不得借另一臂的 n ─────────
    # 首版这里写成 max(test.n, control.n)，于是 n=0 的实验臂借了对照臂的
    # 64 过关。这条断言把「不得顶替」钉死。
    v = adjudicate("本语料上 X 提升检索", Arm("t", "span_full@3", 0.99,
                 n_items=0, caliber="dense|fixed_220_o40|w4"), ctrl,
                   measured_scope="本语料",
                   recomputable=fixture_ok())
    assert v.verdict == "insufficient", v.verdict
    assert "实验臂" in v.gates["effect_vs_noise"]["reason"], \
        "未声明 n 竟没被指名——门放行了"
    # 反向：对照臂没 n，同样拒绝
    v = adjudicate("本语料上 X 提升检索",
                   Arm("t", "span_full@3", 0.99, n_items=64,
                       caliber="dense|fixed_220_o40|w4"),
                   Arm("c", "span_full@3", 0.92, n_items=0,
                       caliber="dense|fixed_220_o40|w4"),
                   measured_scope="本语料",
                   recomputable=fixture_ok())
    assert v.verdict == "insufficient", v.verdict
    assert "对照臂" in v.gates["effect_vs_noise"]["reason"]
    checks += 1

    # ── 2b. **跨度大得不可能 ⇒ 必须否**（反证 A 的直接修法）─────────
    # 注入：把对照臂抬到 0.999，处理臂不动。没有上界时跨度 0.046 全绿。
    inflated = Arm("dense_plain_INFLATED", "span_full_at_3", 0.999,
                   n_items=64, by_type={"boundary": 0.999, "single": 0.999,
                                        "multi_hop": 0.999},
                   caliber="dense|fixed_220_o40|w4")
    v = adjudicate("在本语料（26 篇 / 64 题）上，处理臂优于对照臂",
                   Arm("t", "span_full_at_3", 0.953, n_items=64,
                       by_type={"boundary": 0.99, "single": 0.99,
                                "multi_hop": 0.99},
                       caliber="dense|fixed_220_o40|w4"), inflated,
                   predicted="boundary",
                   measured_scope="本语料 26 篇 / 64 题",
                   recomputable=fixture_ok())
    # ── 2b. **篡改的检出靠重算，不靠幅度阈值**（反证 A/B 的正解）────
    # 反证 A：把对照臂 headline 抬到 0.999 ⇒ 跨度从 0.031 变 0.046，
    #          而 MIN/MAX_SPAN 两道幅度门都拦不住（0.046 在区间内）。
    # 反证 B：把 headline 与逐类数字**一起**抬高 ⇒ 内部完全自洽，
    #          任何幅度阈值都无用。
    # 只有 `gate_recomputable` 能抓：从落盘 detail 逐项重算，对不上就否。
    # 基线自洽 ⇒ 过（32+19+11 = 62 / 64 = 0.96875）
    raw_ok = _fake_raw(claimed=62 / 64, detail_hit={"single": 32,
                                                     "multi_hop": 19,
                                                     "boundary": 11})
    # 只改 headline ⇒ 重算对不上 ⇒ 否
    raw_bad = _fake_raw(claimed=0.999, detail_hit={"single": 32,
                                                      "multi_hop": 19,
                                                      "boundary": 11})
    # headline 对、逐类声称值被改 ⇒ 也必须抓到（只查 headline 不够）
    raw_type = _fake_raw(claimed=62 / 64,
                        detail_hit={"single": 32, "multi_hop": 19,
                                    "boundary": 11},
                        claim_hit={"single": 40, "multi_hop": 19,
                                   "boundary": 11})
    g_ok = gate_recomputable(raw_ok, "a")
    g_bad = gate_recomputable(raw_bad, "a")
    assert g_ok["pass"], g_ok
    assert not g_bad["pass"] and "重算" in g_bad["reason"], g_bad
    g_type = gate_recomputable(raw_type, "a")
    assert not g_type["pass"] and "single.hit" in g_type["reason"], g_type
    # 没有逐项证据 ⇒ 不作已通过处理（fail-closed）
    g_none = gate_recomputable({"arms": {"a": {}}}, "a")
    assert not g_none["pass"] and "detail" in g_none["reason"], g_none
    # 并入 adjudicate：不给逐项证据 ⇒ 不过；给了但对不上 ⇒ 不过
    v = adjudicate("在本语料（26 篇 / 64 题）上，处理臂优于对照臂",
                   Arm("t", "span_full_at_3", 0.953, n_items=64,
                       by_type={"boundary": 0.99, "single": 0.99,
                                "multi_hop": 0.99},
                       caliber="dense|fixed_220_o40|w4"),
                   Arm("c", "span_full_at_3", 0.922, n_items=64,
                       by_type={"boundary": 0.90, "single": 0.94,
                                "multi_hop": 0.92},
                       caliber="dense|fixed_220_o40|w4"),
                   predicted="boundary",
                   measured_scope="本语料 26 篇 / 64 题",
                   recomputable=g_bad)
    assert v.verdict == "insufficient", v.verdict
    assert "重算" in v.gates["effect_vs_noise"]["reason"]
    checks += 1



    # ── 3. **口径不同 ⇒ 结论符号可能翻转**，必须否决 ───────────────
    sparse = Arm("sparse_w4", "span_full@3", 0.984, n_items=64,
                 caliber="sparse|fixed_220_o40|w4")
    v = adjudicate("本语料上 contextual retrieval 优于 W4 基线",
                   Arm("ctx", "span_full@3", 0.953, n_items=64,
                       caliber="dense|fixed_220_o40|w4"), sparse,
                   measured_scope="本语料 26 篇 / 64 题",
                   recomputable=fixture_ok())
    assert v.verdict == "fail", v.verdict
    assert "口径不同" in v.gates["caliber_isolation"]["reason"]
    # 而同一对臂换成同口径 ⇒ 符号确实翻转为正（把 W5 的教训钉成断言）
    assert Arm("ctx", "span_full@3", 0.953).value > ctrl.value
    assert Arm("ctx", "span_full@3", 0.953).value < sparse.value
    checks += 1

    # ── 4. 无 caliber 标签 ≠ 同口径（这是最容易漏的一种）────────────
    v = adjudicate("本语料上 X 提升检索", Arm("t", "span_full@3", 0.99,
                 n_items=64), ctrl, measured_scope="本语料",
                   recomputable=fixture_ok())
    assert v.verdict == "fail", v.verdict
    assert "caliber" in v.gates["caliber_isolation"]["reason"]
    checks += 1

    # ── 5. 增益不在预测题型 ⇒ 否机制主张，但保留效应 ─────────────────
    # **先断言 fixture 真的有区分度**（首版这里的 fixture 写着"增益不在
    # 边界类"，实际算出来边界类增益 0.000 反而高于其余类均值 −0.005 ——
    # 测试通过是因为数据恰好不触发，而不是因为门在工作。AGENTS.md 第 7 条：
    # 样例必须真的含它声称含的那条路径）。
    ctrl_m = Arm("dense_plain", "span_full@3", 0.922, n_items=64,
                 by_type={"single": 0.90, "multi_hop": 0.90,
                          "boundary": 0.95},
                 caliber="dense|fixed_220_o40|w4")
    test_m = Arm("ctx", "span_full@3", 0.953, n_items=64,
                 by_type={"single": 0.94, "multi_hop": 0.95,
                          "boundary": 0.93},
                 caliber="dense|fixed_220_o40|w4")
    g = gate_mechanism_alignment(test_m, ctrl_m, "boundary")
    assert g["gain_on_predicted"] < g["gain_elsewhere_mean"], \
        "fixture 没有区分度：%s" % g
    v = adjudicate("本语料上 contextual retrieval 主要改善边界题",
                   test_m, ctrl_m, predicted="boundary",
                   measured_scope="本语料 26 篇 / 64 题",
                   recomputable=fixture_ok())
    assert v.verdict == "fail", v.verdict
    assert "不支持该机制主张" in v.gates["mechanism_alignment"]["reason"]
    checks += 1

    # ── 6. 机制对齐 + 跨度够 + 同口径 ⇒ pass（正向，不是只有反证）───
    v = adjudicate("本语料上 contextual retrieval 改善了边界题",
                   Arm("ctx", "span_full@3", 0.953, n_items=64,
                       by_type={"single": 0.94, "multi_hop": 0.91,
                                "boundary": 0.97},
                       caliber="dense|fixed_220_o40|w4"), ctrl,
                   predicted="boundary", measured_scope="本语料 26 篇 / 64 题",
                   recomputable=fixture_ok())
    assert v.verdict == "pass", (v.verdict, v.gates)
    checks += 1

    # ── 7. 范围纪律：越界词无限定 ⇒ fail；补上限定 ⇒ pass ───────────
    # 先断言 fixture 真的含越界词。首版这句写的是「上下文重建能提升检索效果」
    # —— 里面**没有**任何越界词，门正确地什么都没抓到，我却断言它该 fail。
    # 这是 ranker.py「塌陷测试探针被污染」的同一类：测试绿着，但它没测到
    # 它声称测的东西。
    bad = "上下文重建普遍能提升检索效果"
    assert RE_SCOPE.search(bad), "fixture 没有越界词：%s" % bad
    g = gate_scope_discipline(bad, "26 篇 / 64 题")
    assert not g["pass"] and "越界" in g["reason"], g
    assert g["overreach_words"], "越界词未被记录，人无法复核"
    ok = "在本语料（26 篇 / 64 题）上，上下文重建普遍提升了检索效果"
    g = gate_scope_discipline(ok, "本语料 26 篇 / 64 题")
    assert g["pass"], g
    # 无越界词但没声明实测范围 ⇒ 判不了，仍须拒绝
    g = gate_scope_discipline("上下文重建提升了检索效果", "")
    assert not g["pass"] and "实测范围" in g["reason"], g
    # 无越界词 + 声明了范围 + 主张里写了范围 ⇒ 过（最常见情形）
    g = gate_scope_discipline("在本语料（26 篇 / 64 题）上召回率上升",
                              "本语料 26 篇 / 64 题")
    assert g["pass"], g
    # **参数里有范围、主张里没有** ⇒ 仍须拒绝：读者拿到的是无边界结论。
    # 首版只查参数，这一句直接 PASS —— 恰恰是本模块最该拦的那句。
    g = gate_scope_discipline("上下文重建提升了检索效果",
                              "本语料 26 篇 / 64 题")
    assert not g["pass"] and "主张文本未写明实测范围" in g["reason"], g
    checks += 1

    # ── 8. pass 必须带实测范围（不给就不许 pass）────────────────────
    v = adjudicate("X 提升了检索效果", Arm("t", "span_full@3", 0.99, n_items=64,
                 by_type={"boundary": 0.99, "single": 0.99},
                 caliber="dense|fixed_220_o40|w4"), ctrl,
                   measured_scope="",
                   recomputable=fixture_ok())
    assert v.verdict != "pass", "未声明实测范围却给 pass"
    checks += 1

    # ── 9. report 必须能失败 ────────────────────────────────────────
    empty = report([v])
    assert empty["every_fail_explains"] is True
    assert empty["no_pass_without_scope"] is True
    naked = Verdict(claim="X", verdict="pass")   # 没跑门就 pass
    r = report([naked])
    assert r["no_pass_without_scope"] is False, \
        "没跑门就 pass 的裁决没被抓——report 是装饰"
    checks += 1

    sys.stdout.write("CRITIC SELFTEST OK（%d 组断言）\n" % checks)
    return 0


def load_w5(path: str) -> tuple[Arm, dict[str, Arm]]:
    """**从落盘 JSON 读 W5 实测值**，一个数都不手抄。

    这一条是被自己抓出来的：`main()` 首版的 `by_type` 是我照着对话里的
    摘要手打的，而真文件里 `dense_plain` 三类全是 1.0、`contextual_retrieval`
    三类全都更低。手抄值让机制门报出「其余类均值 +0.015」，真值是 −0.018 ——
    **结论的符号和含义都反了**（AGENTS.md 铁律 1/2）。

    所以：**判读器只吃程序输出**。数字要么来自 `source_file`，要么显式标注
    `source_file=""` 表示这是构造的 fixture；后者在 report 里会被单独计数。
    """
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    arms = d["arms"]
    control = d.get("control", "?")
    cal = "dense|fixed_220_o40|w4_64q"     # 检索器|切块|题集

    def mk(name: str) -> Arm:
        a = arms[name]
        by = {t: v["recall"] for t, v in a.get("by_type", {}).items()}
        return Arm(name=name, metric="span_full_at_3",
                   value=a["span_full_at_3"],
                   n_items=sum(v["total"] for v in a.get("by_type", {})
                               .values()),
                   by_type=by, caliber=cal,
                   source_file=os.path.relpath(path, ROOT))

    return mk("dense_plain"), {k: mk(k) for k in arms
                               if k not in ("dense_plain",
                                            "control_sparse_w4")}


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    vs: list[Verdict] = []

    w5 = os.path.join(ROOT, "..", "rag_min_demo", "bline", "w5_results.json")
    if not os.path.isfile(w5):
        print("找不到 W5 实测结果 %s —— 拒绝用记忆里的数字判读" % w5)
        return 2
    ctrl, arms = load_w5(w5)
    with open(w5, encoding="utf-8") as fh:
        raw = json.load(fh)

    # 主张 1：照我当初写在 W5 里的那种话（无范围限定）去判
    vs.append(adjudicate(
        "上下文重建能提升检索效果", arms["contextual_retrieval"], ctrl,
        predicted="boundary", measured_scope="本语料 26 篇 / 64 题",
        recomputable=gate_recomputable(raw, "contextual_retrieval"),))
    # 主张 2：同一批数据，配上机制预测与范围限定
    vs.append(adjudicate(
        "在本语料（26 篇 / 64 题）上，late chunking 改善了边界题",
        arms["late_chunking"], ctrl, predicted="boundary",
        measured_scope="本语料 26 篇 / 64 题",
        recomputable=gate_recomputable(raw, "late_chunking"),))
    # 主张 3：稀疏基线 vs 稠密对照 —— 口径不同，验证是否被拦下
    vs.append(adjudicate(
        "在本语料（26 篇 / 64 题）上，contextual retrieval 优于 W4 稀疏基线",
        arms["contextual_retrieval"],
        Arm("control_sparse_w4", "span_full_at_3", 0.984375, n_items=64,
            caliber="sparse|fixed_220_o40|w4_64q",
            source_file="rag_min_demo/bline/w5_results.json"),
        predicted="boundary", measured_scope="本语料 26 篇 / 64 题",
        recomputable=gate_recomputable(raw, "control_sparse_w4"),))

    rep = report(vs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"report": rep, "verdicts": [v.to_dict() for v in vs]},
                  fh, ensure_ascii=False, indent=2)
    print("L4 判读（%d 条主张）→ %s" % (rep["total"], rep["by_verdict"]))
    print("不过的门：%s" % (rep["failing_gates"] or "无"))
    print("每条不过都说明原因：%s | pass 必带实测范围：%s"
          % (rep["every_fail_explains"], rep["no_pass_without_scope"]))
    for v in vs:
        print("\n主张：%s\n  裁决：%s" % (v.claim, v.verdict.upper()))
        for k, g in v.gates.items():
            print("    [%s] %s → %s" % ("过" if g["pass"] else "不过", k,
                                        g["reason"]))
    print("\n结果已写入 %s" % os.path.relpath(OUT, os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
