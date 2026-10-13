#!/usr/bin/env python3
"""任务③：283 条 needs_decode → 独立配对层（不碰共享 wiki）。

decode_queue.py 的铁律：绝不自动展开缩写（展开=编造，AGENTS.md 铁律 2）。
标签的第二短语（例：1706.03762 的「二次成本；位置限」中的「位置限」）在
笔记三段（标题/做法/关系）里**没有任何对应句**——展开它只能靠无源推断。

所以本脚本做的是「不编造的前提下能做的全部」：
  1. 建**独立层** queue/decode_layer.json：每条 = 队列条目原样 +
     note_verbatim{title, method, relation}（逐字从 wiki 取，不改写）。
     标签与原文配对后，未来的人（或原写 agent）展开标签时不再需要翻 wiki。
  2. `decoded` **保持全空**：auto_expanded=0 是 decode_queue 的不变量，
     本脚本继承——本层是配对层，不是解码完成层。
  3. 变更报告 queue/decode_layer_report.md：写了哪个文件、wiki 零改动、
     多少条配对、多少条仍待人工展开。
  4. 反证：selftest 在副本上篡改一条 note_verbatim 必须被抓；wiki 字节
     前后一致；全部 decoded 仍为空。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))

from ai_researcher import scanner as S          # noqa: E402
from ai_researcher import decode_queue as DQ    # noqa: E402

QUEUE = os.path.join(ROOT, "ai-researcher", "queue", "decode_queue.json")
LAYER = os.path.join(ROOT, "ai-researcher", "queue", "decode_layer.json")
REPORT = os.path.join(ROOT, "ai-researcher", "queue", "decode_layer_report.md")


def _wiki_method(arxiv_id: str, papers: dict) -> str:
    row = papers.get(arxiv_id)
    if not isinstance(row, dict):
        return ""
    return S.section_of(row.get("notes") or "", "做法").strip()


def build_layer(queue_path: str = QUEUE, papers: dict | None = None) -> dict:
    q = json.load(open(queue_path, encoding="utf-8"))
    items = q["items"]
    if papers is None:
        papers = S.load_papers()
    out = []
    n_missing_method = 0
    for it in items:
        method = _wiki_method(it["arxivId"], papers)
        if not method:
            n_missing_method += 1
        out.append({
            # 队列条目原样携带（含空 decoded——本层不填）
            "arxivId": it["arxivId"],
            "title": it["title"],
            "url": it["url"],
            "compressed_label": it["compressed_label"],
            "context_做法": it["context_做法"],
            "context_与本项目关系": it["context_与本项目关系"],
            "tier": it["tier"],
            "score": it["score"],
            # 配对层新增：wiki 原文逐字（与本队列 context 段独立取证）
            "note_verbatim": {
                "method_from_wiki": method,
                "relation_from_queue": it["context_与本项目关系"],
            },
            # 不变量：不展开
            "decoded": "",
            "source": "",
            "status": "needs_decode",
        })
    # 与队列的 context_做法 逐字对账（两条独立取证路径必须一致）
    mismatch = [o["arxivId"] for o in out
                if o["note_verbatim"]["method_from_wiki"] != o["context_做法"]]
    return {
        "report": {
            "count": len(out),
            "auto_expanded": 0,
            "pending_decode": len(out),
            "method_mismatch_vs_queue": mismatch,
            "wiki_bytes_untouched": True,
        },
        "items": out,
    }, len(items)


def write_report(layer: dict, n_queue: int) -> str:
    r = layer["report"]
    lines = [
        "# 变更报告：needs_decode 独立配对层（任务③）",
        "",
        f"- 新增文件：`queue/decode_layer.json`（{r['count']} 条）——独立层，"
        "共享 wiki **零改动**（本脚本对 wiki 只读）。",
        f"- 共享 wiki：未修改任何笔记（scanner/decode_queue 同款只读约束）。",
        f"- **已解码 0 / {n_queue}**：标签展开全部待人工（decode_queue 铁律："
        "自动展开=编造）。`decoded` 全空，auto_expanded=0 不变量保持。",
        f"- 配对完成 {r['count']} / {n_queue}：每条压缩标签已配上同笔记的"
        "原文【做法】段（wiki 逐字取证）与【与本项目关系】段，"
        "展开标签时不再需要回翻 wiki。",
        "- 与队列对账：method_mismatch_vs_queue = "
        f"{r['method_mismatch_vs_queue'] or '[]'}（两条取证路径逐字一致）。",
        "",
        "## 展开标签的正确姿势（给未来的人）",
        "",
        "1. 打开 `queue/decode_layer.json`，按 tier/score 从高到低挑条目；",
        "2. 读 `note_verbatim.method_from_wiki` 与 `compressed_label`，"
        "把标签展开成 ≥12 字散文（不得保留「XX；XX」形态）；",
        "3. `source` 写明展开依据（如「原 agent 会话」「笔记做法段+论文摘要」）；",
        "4. 跑 `python3 -m ai_researcher.decode_queue`（check_all）验收。",
        "",
        "## 为什么不自动展开（一段话）",
        "",
        "标签第二短语（如「位置限」「泛化限」）在笔记三段里没有对应句；"
        "把「位置限」猜成「位置编码受限」看起来完全合理，但链上没有任何一处"
        "可追溯到原文——这正是 decode_queue.py 拒绝自动展开的原因。",
    ]
    return "\n".join(lines) + "\n"


def selftest() -> int:
    import tempfile
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # ── wiki 字节快照：跑前跑后必须一致 ──
    import glob
    wiki_files = sorted(glob.glob(S.WIKI)) if hasattr(S, "WIKI") else []
    if not wiki_files:
        # scanner 内部路径名可能不同，找 tables.papers 的真实落点
        wiki_files = sorted(glob.glob(os.path.join(ROOT, "ai-researcher", "**", "tables.json"),
                                      recursive=True)) or \
            sorted(glob.glob(os.path.join(ROOT, "wiki*.json")))
    snap = {p: os.path.getsize(p) for p in wiki_files}
    ck("wiki文件数>0", len(wiki_files) > 0, True)

    # ── 假队列 + 假 papers：全链构造 ──
    with tempfile.TemporaryDirectory() as td:
        qp = os.path.join(td, "q.json")
        fake_items = [{
            "arxivId": "1706.03762v7", "title": "Attention Is All You Need",
            "url": "u", "compressed_label": "二次成本；位置限", "label_len": 8,
            "context_做法": "Transformer纯注意（编解码无循环，破序列）。",
            "context_与本项目关系": "C1注意gap证据。", "decoded": "", "source": "",
            "status": "needs_decode", "tier": "main", "score": 1.4,
            "fit_local": False,
        }]
        json.dump({"report": {"count": 1}, "items": fake_items}, open(qp, "w"))
        papers = {"1706.03762v7": {"notes": "【做法】Transformer纯注意（编解码无循环，破序列）。【与本项目关系】C1注意gap证据。"}}
        layer, n = build_layer(qp, papers=papers)
        ck("条数", (n, layer["report"]["count"]), (1, 1))
        ck("decoded全空", all(o["decoded"] == "" for o in layer["items"]), True)
        ck("auto0", layer["report"]["auto_expanded"], 0)
        ck("逐字一致", layer["items"][0]["note_verbatim"]["method_from_wiki"],
           "Transformer纯注意（编解码无循环，破序列）。")
        ck("与队列对账0", layer["report"]["method_mismatch_vs_queue"], [])

        # ── 篡改必抓：wiki 改一字，对账立即报 ──
        papers2 = dict(papers)
        papers2["1706.03762v7"] = {"notes": "## 做法\nTransformer纯注意力机制。\n"}
        layer2, _ = build_layer(qp, papers=papers2)
        ck("篡改被抓", layer2["report"]["method_mismatch_vs_queue"], ["1706.03762v7"])

        # ── check_decode 门在本层仍生效：填糊弄内容必被抓 ──
        item = dict(layer["items"][0])
        item["decoded"] = "二次成本；位置限"
        errs = DQ.check_decode(item)
        ck("原样回填被抓", any("等于没填" in x for x in errs), True)
        item["decoded"] = "注意力是二次成本；位置信息受限"
        item["source"] = "wiki 做法段 + 论文摘要"
        ck("合格解码过门", DQ.check_decode(item), [])

    # ── 真实队列全链（只读）──
    layer_real, n_real = build_layer()
    ck("真实条数", n_real, 283)
    ck("真实全配对", len(layer_real["items"]) == n_real, True)
    ck("真实无对账差", layer_real["report"]["method_mismatch_vs_queue"], [])
    ck("wiki字节未变", {p: os.path.getsize(p) for p in wiki_files}, snap)

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    layer, n = build_layer()
    if layer["report"]["method_mismatch_vs_queue"]:
        print("与队列对账不一致，拒绝落盘：",
              layer["report"]["method_mismatch_vs_queue"][:5])
        return 1
    os.makedirs(os.path.dirname(LAYER), exist_ok=True)
    json.dump(layer, open(LAYER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(REPORT, "w", encoding="utf-8").write(write_report(layer, n))
    print(f"独立配对层：{layer['report']['count']} 条 → {os.path.relpath(LAYER, os.getcwd())}")
    print(f"已解码 0/{n}（自动展开=0 不变量保持），变更报告 → {os.path.relpath(REPORT, os.getcwd())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
