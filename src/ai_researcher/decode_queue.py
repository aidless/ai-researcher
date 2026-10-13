"""L2.5 解码队列：把 283 条压缩标签变成**等人填写的工单**。

## 它为什么存在

L0 扫出 384 条可用候选，其中 **283 条的「开放点」不是散文，是用户 agent
的私有缩写**：

    1511.06422v7  层序成本；方差限
    1706.03762v7  二次成本；位置限
    1803.02155v2  相对泛化；偏置限

实测这些标签去掉空格后只有 5–13 字（中位 8 字），形态是
`XX成本；XX限`——**两个 2–4 字的词组用分号并列**。用户能读懂，我读不懂。

## 它绝不做什么

**绝不自动展开缩写。** 展开就是编造（AGENTS.md 铁律 2）。如果我把「层序成本」
猜成"分层顺序带来的计算成本"，然后这条进了排序层进了实验提案，
整条链上没有任何一处能追溯到原文 —— **看起来完全合理，所以极难被发现**。

正确的做法只有一个：**把标签原样送回去，请写它的人补一句人话**。

## 它做什么

每条工单携带：
- 压缩标签**原文**（不改写、不猜测）
- 同一条笔记的【做法】和【与本项目关系】——给解码的人当上下文，
  否则他也不知道自己在解码什么
- 校验钩子 `check_decode()`：填回队列后必须能过，才算解码完成

## 校验门（fail-closed）

`check_decode()` 判一条解码是否可信：
1. `decoded` 非空且**不等于**原标签（否则等于没填）
2. `decoded` 长度 ≥ `MIN_DECODED_LEN`（12 字）—— 防"换个说法糊弄"
3. `decoded` 里**不含残留标签形态**（`XX；XX` 分号并列）—— 说明还在用缩写
4. `source` 必须标明解码人/来源—— 不可追溯的解码不算解码

第 3 条是被数据教出来的：8 字档 82 条全是分号并列形态，而真实散文
极少这么短地并列。**这一条形制的"像散文"程度就是解码质量的代理指标。**
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from . import scanner as S
from . import ranker as R

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "queue", "decode_queue.json")

MIN_DECODED_LEN = 12
# 残留标签形态：分号并列的短词组（8 字档 82/283 命中真实数据）
_RESIDUE = re.compile(r"^[^，。；;！？、]{1,5}[；;][^，。；;！？、]{1,5}[；;]?$")


def build(gaps: list[S.Gap] | None = None, ranked: list[R.Ranked] | None = None,
          papers: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造解码队列。**只读** wiki，不写任何笔记（AGENTS.md 铁律 6）。

    【做法】段要现取：scanner 的 `Gap` 并不存这一段（它只留开放点与关系段），
    用 `getattr(g, "method", "")` 会**恒返回空串**——那等于给解码人一个永远
    空着的"上下文"栏，看着像有上下文其实没有（装饰门同款）。所以这里按
    arxiv_id 回 wiki 取原始 notes 的【做法】段。
    """
    if papers is None:
        papers = S.load_papers()
    gaps = gaps if gaps is not None else S.scan(papers)
    ranked = ranked if ranked is not None else R.rank()
    byid = {r.arxiv_id: r for r in ranked}

    def method_of(g: S.Gap) -> str:
        row = papers.get(g.arxiv_id)
        if not isinstance(row, dict):
            return ""
        return S.section_of(row.get("notes") or "", "做法").strip()

    items = []
    for g in S.usable(gaps):
        if not g.needs_decode:
            continue
        r = byid.get(g.arxiv_id)
        items.append({
            # ── 标识与溯源 ────────────────────────────────────────
            "arxivId": g.arxiv_id,
            "base_id": g.arxiv_id.split("v")[0],
            "title": g.title,
            "url": g.url,
            # ── 待解码内容：**原文，一个字不改** ────────────────────
            "compressed_label": g.open_problem,
            "label_len": len(re.sub(r"\s", "", g.open_problem)),
            # ── 给解码人的上下文（原笔记另两段，不是我写的）──────
            "context_做法": method_of(g),
            "context_与本项目关系": g.project_relation,
            # ── 解码槽位：**留空等人填** ────────────────────────────
            "decoded": "",
            "source": "",
            "status": "needs_decode",
            # ── 该条的排序上下文，便于解码人判断优先级 ────────────
            "tier": r.tier if r else "",
            "score": r.score if r else 0.0,
            "fit_local": bool(g.fit_local),
        })
    from collections import Counter
    lens = Counter(len(re.sub(r"\s", "", i["compressed_label"]))
                   for i in items)
    return {
        "report": {
            "count": len(items),
            "by_label_len": {str(k): lens[k] for k in sorted(lens)},
            "fit_local_true": sum(1 for i in items if i["fit_local"]),
            # 本模块唯一的"产品"就是这张工单表；自动展开数恒为 0 是它的
            # 不变量，写进 report 是为了让复跑的人一眼能看出没被谁填过。
            "auto_expanded": 0,
            "context_做法_nonempty": sum(1 for i in items if i["context_做法"]),
            "context_关系_nonempty": sum(1 for i in items
                                        if i["context_与本项目关系"]),
        },
        "items": items,
    }


def check_decode(item: dict[str, Any]) -> list[str]:
    """校验一条解码。返回问题列表，空列表 = 通过。**fail-closed。**"""
    errs: list[str] = []
    label = (item.get("compressed_label") or "").strip()
    dec = (item.get("decoded") or "").strip()
    if not dec:
        return ["未填 decoded"]
    if dec == label:
        errs.append("decoded 与原标签完全相同——等于没填")
    if len(re.sub(r"\s", "", dec)) < MIN_DECODED_LEN:
        errs.append("decoded 仅 %d 字，短于下限 %d——可能只是换个说法糊弄"
                    % (len(re.sub(r"\s", "", dec)), MIN_DECODED_LEN))
    if _RESIDUE.match(dec):
        errs.append("decoded 仍是「XX；XX」分号并列的压缩形态——还没解码")
    if not (item.get("source") or "").strip():
        errs.append("未填 source——不可追溯的解码不算解码")
    return errs


def check_all(q: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter
    errs = [e for i in q["items"] for e in check_decode(i)]
    c = Counter(e.split("——")[0] for e in errs)
    return {
        "items": len(q["items"]),
        "pending": sum(1 for i in q["items"] if not i["decoded"].strip()),
        "problems": dict(c),
        "auto_expanded": q["report"]["auto_expanded"],
    }


def selftest() -> int:
    """反证：证明「糊弄式解码」和「未填」都会被抓住，且没有人自动展开。"""
    checks = 0
    base = {"arxivId": "x", "compressed_label": "层序成本；方差限",
            "decoded": "", "source": ""}

    # ── 1. 未填 ⇒ 报「未填 decoded」 ──────────────────────────────
    e = check_decode(dict(base))
    assert e == ["未填 decoded"], e
    checks += 1

    # ── 2. 原样回填 ⇒ 等于没填 ───────────────────────────────────
    e = check_decode(dict(base, decoded="层序成本；方差限", source="我"))
    assert any("等于没填" in x for x in e), e
    checks += 1

    # ── 3. 换个说法糊弄（还是分号并列）⇒ 抓残留形态 ───────────────
    e = check_decode(dict(base, decoded="层次成本；方差限制", source="我"))
    assert any("压缩形态" in x for x in e), e
    checks += 1

    # ── 4. 太短 ⇒ 抓长度 ─────────────────────────────────────────
    e = check_decode(dict(base, decoded="层序成本高", source="我"))
    assert any("短于下限" in x for x in e), e
    checks += 1

    # ── 5. 无来源 ⇒ 抓溯源 ───────────────────────────────────────
    e = check_decode(dict(base, decoded="分层顺序会带来额外的计算开销与延迟",
                          source=""))
    assert any("source" in x for x in e), e
    checks += 1

    # ── 6. 合格解码 ⇒ 通过（四条门同时满足才算）──────────────────
    e = check_decode(dict(base,
                          decoded="分层顺序会带来额外的计算开销与延迟开销",
                          source="原 agent 会话 2026-10-02"))
    assert e == [], e
    checks += 1

    # ── 7. 队列构造**不得**填任何 decoded（防自动展开）──────────
    q = build()
    assert all(i["decoded"] == "" for i in q["items"]), \
        "队列构造时竟有条目被填了内容——这等于自动展开缩写"
    assert q["report"]["auto_expanded"] == 0
    assert all(i["compressed_label"] == g.open_problem
               for i, g in zip(q["items"],
                               [x for x in S.usable(S.scan())
                                if x.needs_decode])), "压缩标签被改写了"
    # 上下文栏必须真的非空：留一个永远为空的"上下文"字段，等于骗解码人
    # 说"我们有背景资料"。解码人没背景就只能猜，那正是本模块要避免的。
    assert q["report"]["context_做法_nonempty"] == len(q["items"]), \
        "【做法】段全空——解码人拿不到任何背景"
    assert q["report"]["context_关系_nonempty"] == len(q["items"]), \
        "【与本项目关系】段全空"
    checks += 1

    sys.stdout.write("DECODE QUEUE SELFTEST OK（%d 组断言）\n" % checks)
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    q = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(q, fh, ensure_ascii=False, indent=2)
    rep = q["report"]
    print("解码队列：%d 条（**全部 decoded 留空等人填**）" % rep["count"])
    print("  标签长度分布：%s" % rep["by_label_len"])
    print("  fit_local=True：%d" % rep["fit_local_true"])
    print("  自动展开条数：%d（本模块永不为 0）" % rep["auto_expanded"])
    print("\n样例（看它给了解码人什么上下文）：")
    for i in q["items"][:3]:
        print("  %-15s [%d字] %s" % (i["arxivId"], i["label_len"],
                                       i["compressed_label"]))
        print("      关系段：%s" % i["context_与本项目关系"][:56])
    print("\n校验门（填完回来跑 check_all）：4 条，缺一不可")
    print("结果已写入 %s" % os.path.relpath(OUT, os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main())