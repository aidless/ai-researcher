"""P1 笔记归一化器 —— 把已有实质笔记改写成 P1 验收要求的【三段】格式。

## 它做什么

`research_wiki.json` 里 644 篇 lit1000 文献的笔记**有实质内容**，但用的是另一种
标记形式（`做法：` / `留下开口：` / `与C1-C3关系：`），而 P1 复算脚本
(`.agent-memory/ledger/count_p1_world_sota_20261001.py`) 只认方括号形式
（`【做法】` / `【开放点】` / `【与本项目关系】`），于是全部计 0。

本模块把前者**搬运**成后者。

## 它绝不做什么

本模块**不生成任何新内容**。它只做三件事：

1. 用正则从原笔记里**抽取**三段原文
2. 套上 `【】` 标记重新拼接
3. 在末尾追加一行格式归一的溯源戳

抽不出某一段 → 该篇进 `rejected`，原样不动。
**任何"根据标题猜一个做法"式的补全都是伪造成果，本模块禁止该路径。**

这直接对应 AGENTS.md 铁律 #1（数字可复算）与 #2（绝不编造）：
P1 计数从 393 跳到 1037 的每一个数字，都必须能回溯到某一篇原笔记的某段原文。

## 相关

- 复算真相源：`.agent-memory/ledger/count_p1_world_sota_20261001.py`
- 被改写的真值库：`~/.dsh/storages/research_wiki.json`（跨会话共享、无锁、铁律 #6）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# P1 验收要求的三段（判据真相源：count_p1_world_sota_20261001.py 的 SECTIONS）
SECTIONS = ("做法", "开放点", "与本项目关系")

# ── 严格格式：已合格，原样通过 ────────────────────────────────────────────
STRICT = tuple("【%s】" % s for s in SECTIONS)

# ── 宽松格式：三种历史写法，各自有独立的抽取正则 ────────────────────────────
# 每条正则捕获组 1 = 该段的原文。终止符优先取"下一段的开头标记"，
# 而不是贪婪吃到段末 —— 否则第二段会把第三段吞掉。
_PATTERNS: dict[str, re.Pattern[str]] = {
    "做法": re.compile(
        r"做法\s*[:：]\s*(.{10,400}?)"
        r"(?=(?:留下开口|开口|与C1|与本项目|关系)\s*[:：]|\n\s*T\d{2}-G\d{2}|$)",
        re.S,
    ),
    "开放点": re.compile(
        r"(?:留下开口|开口)\s*[:：]\s*(.{5,300}?)"
        r"(?=(?:与C1|与本项目|关系)\s*[:：]|\n\s*T\d{2}-G\d{2}|$)",
        re.S,
    ),
    "与本项目关系": re.compile(
        r"(?:与C1-C3关系|与C1-C3|与本项目关系|关系)\s*[:：]\s*(.{5,400}?)"
        r"(?=\n\s*T\d{2}-G\d{2}|$)",
        re.S,
    ),
}

# 每段最小有效长度：低于此值视为"抽到了标记但没抽到内容"，宁可拒收
MIN_SECTION_LEN = {"做法": 10, "开放点": 5, "与本项目关系": 15}

# 归一化戳：写进 notes 末尾，让"这行是机器加的"永远可辨认
STAMP = "【格式归一】{date} 由 ai-researcher/normalize_notes 从原文搬运（未新增论断）"


@dataclass
class Result:
    """单篇归一化结果。ok=False 时 `notes` 为 None，表示不改动。"""

    key: str
    title: str
    ok: bool
    notes: str | None = None
    missing: list[str] = field(default_factory=list)
    reason: str = ""


def already_strict(notes: str) -> bool:
    """三段方括号形式是否已齐备。"""
    return all(mark in notes for mark in STRICT)


def extract_sections(notes: str) -> tuple[dict[str, str], list[str]]:
    """从宽松格式笔记抽取三段。返回 (命中段, 缺失段名)。

    抽取是纯搬运：捕获组 1 就是原文字符串，本函数不改写一个字符。
    """
    found: dict[str, str] = {}
    missing: list[str] = []
    for name in SECTIONS:
        m = _PATTERNS[name].search(notes or "")
        if not m:
            missing.append(name)
            continue
        text = m.group(1).strip()
        # 抽到了标记但内容过短 —— 视为没抽到
        if len(text) < MIN_SECTION_LEN[name]:
            missing.append(name)
            continue
        found[name] = text
    return found, missing


def normalize_one(
    key: str,
    row: dict[str, Any],
    date: str,
) -> Result:
    """归一化单篇。已合格 → 原样返回 ok=True/notes=原样（幂等）。"""
    notes = row.get("notes") or ""
    title = str(row.get("title") or "")[:70]

    if already_strict(notes):
        return Result(key=key, title=title, ok=True, notes=notes,
                      reason="already_strict")

    found, missing = extract_sections(notes)
    if missing:
        return Result(key=key, title=title, ok=False, missing=missing,
                      reason="incomplete_source")

    # 保留原文主体在【】之前，便于人眼对照；方括号三段紧随其后。
    # 这样"机器加了哪一段"永远肉眼可辨，不构成对原文的静默覆盖。
    body = "".join("【%s】%s\n" % (n, found[n]) for n in SECTIONS)
    new_notes = "%s\n%s\n%s" % (notes.rstrip(), body.rstrip(), STAMP.format(date=date))
    return Result(key=key, title=title, ok=True, notes=new_notes,
                  missing=[], reason="normalized")


def classify(wiki: dict[str, Any], only_tag: str = "lit1000") -> dict[str, list[str]]:
    """把 papers 表按"可自动归一化 / 需人工"分桶。

    分桶判据与 normalize_one 完全同源 —— 不引入第二套标准。
    """
    papers = wiki.get("tables", {}).get("papers", {})
    buckets: dict[str, list[str]] = {
        "already_strict": [],   # 已是【】格式（含已计入 P1 的 393）
        "normalizable": [],     # 有实质内容，可机械搬运
        "needs_human": [],      # 抽不全，必须人读
    }
    for key, row in papers.items():
        tags = row.get("tags") or []
        notes = row.get("notes") or ""
        if already_strict(notes):
            buckets["already_strict"].append(key)
        elif only_tag in tags or any(
            t.startswith("world-sota-") for t in tags
        ):
            found, missing = extract_sections(notes)
            buckets["normalizable" if not missing else "needs_human"].append(key)
    return buckets
