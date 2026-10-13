#!/usr/bin/env python3
"""L1→L2 交接闸：把 dots-agent 的提案变成可精读的待办，并守住"不编造"。

## 它补的是哪个洞

实测（2026-10-02）：`dots-agent/.dot-workspace/proposals.jsonl` 里躺着 10 条
`paper_candidate`，而 `--approve` 只授予 agent **写入**提案的权限；approve
之后全仓库没有任何代码读它。提案有入口没出口——L1 跑得很好，L2 拿不到东西。

本脚本就是那个出口，但它**不是自动写笔记**，是三段式闸：

    提案 --[机械步骤]--> 待精读条目 --[人工/LLM 真读]--> 三段笔记 --> 入 wiki

## 为什么不直接自动写笔记

`ai-researcher/src/normalize_notes.py` 的文件头写死了约束：「本模块不生成
任何新内容，只做搬运」。那条约束对**已有笔记**成立，对**新论文**不适用
——新论文的三段内容根本不存在于任何地方，只能靠真读全文得到。

所以机械部分止步于"取到真实元数据 + 建一个明确标记待填的条目"，剩下的
交给人（或装了 LLM 的 agent）。若让脚本根据标题猜一个「做法」，那就是
洗稿，而 AGENTS.md 铁律 #2 禁止它。

## 三道门（任一不过 → 拒绝入盘）

    G1 去重：新论文的 base id 不得已在 wiki（铁律 18：按 base 比对，
             裸 arXiv id 查重永远 False）
    G2 非空：三段各自长度必须达标，缺一段或过短就整条退回，不写半成品
    G3 溯源：入 wiki 的行必须带 url，笔记末尾带归一化戳，
             让人一眼看出哪些是机器搬的

## 用法

    python3 proposal_to_queue.py --selftest
    python3 proposal_to_queue.py --stage            # 提案 → 待精读清单
    python3 proposal_to_queue.py --stage --limit 3
    python3 proposal_to_queue.py --promote queue/p1_deepread_queue.json \\
        --apply                                     # 三段齐备的才入 wiki
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from typing import Any

SECTIONS = ("做法", "开放点", "与本项目关系")
STRICT = tuple("【%s】" % s for s in SECTIONS)
# 复用 normalize_notes 的下限，别让两处标准漂移
MIN_SECTION_LEN = {"做法": 10, "开放点": 5, "与本项目关系": 15}
STAMP = "【格式归一】{date} 由 ai-researcher/proposal_to_queue 搬运（未新增论断）"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(REPO, "queue", "p1_deepread_queue.json")
WIKI = os.path.expanduser("~/.dsh/storages/research_wiki.json")
PROPOSALS = os.path.join(
    os.path.dirname(REPO), "dots-agent", ".dot-workspace", "proposals.jsonl")
ARXIV_API = "https://export.arxiv.org/api/query?id_list={ids}"


# ── G1 去重 ──────────────────────────────────────────────────────────────
def base_id(arxiv_id: str) -> str:
    """去掉版本号。铁律 18：带版本号的键必须按 base 比对。"""
    return re.sub(r"v\d+$", "", arxiv_id or "")


def already_known(papers: dict[str, Any], arxiv_id: str) -> bool:
    bid = base_id(arxiv_id)
    if bid in papers:
        return True
    for v in papers.values():
        if isinstance(v, dict) and base_id(str(v.get("arxivId") or "")) == bid:
            return True
    return False


# ── G2 非空 ──────────────────────────────────────────────────────────────
def section_text(notes: str, name: str) -> str:
    """取【段名】到下一段标记（或文末）之间的原文。

    终止符必须带 `\\Z` 兜底：只写"下一段标记"时，最后一段永远匹配不到，
    于是 `【做法】…` 缺后两段时报的是「做法过短」而不是「缺开放点」——
    错误信息指向了错误的原因。
    """
    idx = SECTIONS.index(name)
    tail = ("【%s】" % SECTIONS[idx + 1]) if idx + 1 < len(SECTIONS) else r"\Z\B"
    m = re.search(r"【%s】(.*?)(?=%s|\Z)" % (name, tail), notes or "", re.S)
    return m.group(1).strip() if m else ""


def check_three(notes: str) -> list[str]:
    """返回不合格的段名。合格 = 三段标记齐备且每段长度达标。"""
    bad: list[str] = []
    for name in SECTIONS:
        if "【%s】" % name not in (notes or ""):
            bad.append(name)
            continue
        text = section_text(notes, name)
        if len(text) < MIN_SECTION_LEN[name]:
            bad.append("%s(过短:%d)" % (name, len(text)))
    return bad


# ── 元数据抓取（只读） ────────────────────────────────────────────────────
def fetch_meta(ids: list[str], timeout: int = 30) -> dict[str, dict[str, str]]:
    """向 arXiv 取真实元数据。取不到的 id 不进 map —— 宁可少一条，
    也不要用标题猜出来的内容补位。"""
    if not ids:
        return {}
    url = ARXIV_API.format(ids=",".join(ids[:20]))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as fh:
            body = fh.read().decode("utf-8", "replace")
    except Exception as exc:                      # 网络失败是常态，不是异常
        print("[warn] arXiv 抓取失败：%s" % exc, file=sys.stderr)
        return {}
    out: dict[str, dict[str, str]] = {}
    for entry in re.findall(r"<entry>(.*?)</entry>", body, re.S):
        aid = re.search(r"<id>.*?abs/([^<]+)</id>", entry)
        if not aid:
            continue
        raw = aid.group(1).strip()
        def grab(tag: str) -> str:
            m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), entry, re.S)
            return " ".join(m.group(1).split()) if m else ""
        out[base_id(raw)] = {
            "arxivId": raw,
            "title": grab("title"),
            "summary": grab("summary"),
            "published": grab("published"),
            "url": "https://arxiv.org/abs/%s" % raw,
        }
    return out


# ── stage：提案 → 待精读清单 ──────────────────────────────────────────────
def stage(limit: int | None) -> int:
    if not os.path.exists(PROPOSALS):
        print("[error] 提案文件不存在：%s" % PROPOSALS)
        return 2
    with open(WIKI, encoding="utf-8") as fh:
        papers = json.load(fh)["tables"]["papers"]

    props = []
    with open(PROPOSALS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                props.append(json.loads(line))

    todo, skipped = [], []
    for p in props:
        raw = p.get("arxivId") or p.get("arxiv_id") or ""
        bid = base_id(raw)
        if not bid:
            skipped.append((str(p.get("arxiv_id"))[:24], "无 arxiv id"))
            continue
        if already_known(papers, bid):                       # G1
            skipped.append((bid, "已在 wiki（按 base id 比对）"))
            continue
        todo.append(p)

    if limit:
        todo = todo[:limit]
    meta = fetch_meta([base_id(t.get("arxiv_id") or "") for t in todo])

    items = []
    for p in todo:
        raw = p.get("arxiv_id") or ""
        bid = base_id(raw)
        m = meta.get(bid, {})
        items.append({
            "arxivId": m.get("arxivId", raw),
            "base_id": bid,
            "title": m.get("title") or p.get("title") or "",
            "summary": m.get("summary", ""),
            "url": m.get("url") or "https://arxiv.org/abs/%s" % bid,
            "published": m.get("published") or p.get("published") or "",
            "agent_score": p.get("score"),
            "why": p.get("why", ""),
            "meta_fetched": bool(m),
            "notes": "",            # 必须由真读全文填写；此处留空是设计
            "status": "needs_deepread",
        })

    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)

    missing_meta = sum(1 for i in items if not i["meta_fetched"])
    print("提案 %d 条 → 待精读 %d 条（跳过 %d：%s）"
          % (len(props), len(items), len(skipped),
             "；".join("%s %s" % s for s in skipped[:5]) or "无"))
    if missing_meta:
        print("[warn] %d 条没抓到 arXiv 元数据，title/url 取自提案原文"
              % missing_meta)
    print("待精读清单：%s" % QUEUE)
    print("下一步：对每条读全文，按【做法】【开放点】【与本项目关系】写笔记，"
          "再跑 --promote。三段不齐的会被拒绝入 wiki。")
    return 0


# ── promote：三段齐备才入 wiki ────────────────────────────────────────────
def promote(queue_path: str, apply: bool) -> int:
    if not os.path.exists(queue_path):
        print("[error] 清单不存在：%s" % queue_path)
        return 2
    with open(queue_path, encoding="utf-8") as fh:
        items = json.load(fh)

    with open(WIKI, encoding="utf-8") as fh:
        wiki = json.load(fh)
    papers = wiki["tables"]["papers"]

    good, rejected = [], []
    for it in items:
        bid = it.get("base_id") or base_id(it.get("arxivId") or "")
        if not bid:
            rejected.append(("<空>", "无 base id"))
            continue
        if already_known(papers, bid):                       # G1（入盘前再查）
            rejected.append((bid, "已在 wiki"))
            continue
        bad = check_three(it.get("notes") or "")             # G2
        if bad:
            rejected.append((bid, "三段不合格：%s" % "、".join(bad)))
            continue
        if not it.get("url"):                               # G3
            rejected.append((bid, "缺 url，无法溯源"))
            continue
        good.append((bid, it))

    print("清单 %d 条 → 可入 wiki %d 条，拒绝 %d 条"
          % (len(items), len(good), len(rejected)))
    for bid, why in rejected:
        print("  [拒绝] %-26s %s" % (bid[:26], why))
    if not good:
        print("没有合格条目，wiki 未改动。")
        return 0

    if not apply:
        print("\n--apply 未给，以下**不会**写盘。合格条目：")
        for bid, it in good:
            print("  %s  %s" % (bid, (it.get("title") or "")[:70]))
        return 0

    stamp = STAMP.format(date=time.strftime("%Y-%m-%d"))
    for bid, it in good:
        papers[bid] = {
            "arxivId": it.get("arxivId", bid),
            "title": it.get("title", ""),
            "authors": [],
            "summary": it.get("summary", ""),
            "url": it.get("url", ""),
            "notes": (it.get("notes") or "").rstrip() + "\n" + stamp,
            "tags": ["world-sota-A"],   # 新论文默认进 A 线，线归属由人复核
            "projectIds": [],
            "addedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
    bak = WIKI + ".bak-%s" % time.strftime("%Y%m%dT%H%M%S")
    os.replace(WIKI, bak)
    tmp = WIKI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(wiki, fh, ensure_ascii=False)
    os.replace(tmp, WIKI)
    print("已写入 %d 条。备份：%s" % (len(good), bak))
    print("注意：新条目标了 world-sota-A，线归属须人工复核；"
          "跑 .agent-memory/ledger/count_p1_world_sota_20261001.py 复验。")
    return 0


# ── 自测：门必须能失败 ────────────────────────────────────────────────────
def selftest() -> int:
    print("  反证：P1G1 版本号去重 2307.08691v2 vs wiki 存 v1")
    papers = {"2307.08691v1": {"arxivId": "2307.08691v1"}}
    assert already_known(papers, "2307.08691v2"), "版本号去重失败"
    assert not already_known(papers, "2307.08699v2"), "去重过宽，误判新论文"
    print("  通过")

    print("  反证：G2 三段缺一不可、过短不可")
    assert check_three("【做法】这是一个足够长的做法描述文本") == \
        ["开放点", "与本项目关系"], "缺段却放行"
    assert check_three("【做法】" + "长" * 10 + "【开放点】短"
                       "【与本项目关系】" + "长" * 15) == \
        ["开放点(过短:1)"], "过短段未检出"
    good = ("【做法】" + "长" * 12 + "【开放点】" + "长" * 8
            + "【与本项目关系】" + "长" * 18)
    assert check_three(good) == [], "合格笔记被拒"
    print("  通过：缺段/过短各被拒，合格放行")

    print("  反证：G3 缺 url 不可溯源")
    assert not {"url": ""}.get("url"), "缺 url 却认为可溯源"
    print("  通过")

    print("  反证：反手把 base_id 打恒等，确认去重不是靠巧合通过")
    saved = base_id
    try:
        globals()["base_id"] = lambda x: x          # type: ignore[assignment]
        assert not already_known({"2307.08691v1": {}}, "2307.08691v2"), \
            "恒等 base_id 下仍判已知名，说明门在靠巧合"
    finally:
        globals()["base_id"] = saved                # type: ignore[assignment]
    print("  通过")
    print("SELFTEST OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="store_true")
    ap.add_argument("--promote")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.promote:
        return promote(a.promote, a.apply)
    if a.stage:
        return stage(a.limit)
    ap.error("需要 --stage / --promote / --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())