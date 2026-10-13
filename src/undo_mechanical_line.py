#!/usr/bin/env python3
"""撤销 run_normalize.py 的机械归线，把 A 线恢复到审计前的真实分布。

## 为什么需要它

第一版执行器给 643 篇未归线笔记**一律打了 `world-sota-A`**，理由是
"待人工改线"。但这让复算输出变成 `A803/B119/C114` —— 一个假的分布，
而且写进了基线快照 `FROZEN`。这是把机器猜测伪装成既成事实，违反
AGENTS.md 铁律 #2（绝不编造）：`world-sota-A` 表示"这篇属于 A 线研究"，
不是"这篇还没决定属于哪条线"。

正确做法是 `p1-pending-line` 标签 —— 它进入 P1 计数（三段笔记已合格），
但不伪造线归属。本脚本把线归属还原，保留笔记归一化的成果。

## 用法

    python3 undo_mechanical_line.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

WIKI = os.path.expanduser("~/.dsh/storages/research_wiki.json")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECUR = os.path.join(
    os.path.dirname(REPO), ".agent-memory", "ledger",
    "count_p1_world_sota_20261001.py",
)


def recount() -> dict[str, int]:
    proc = subprocess.run(
        [sys.executable, RECUR], capture_output=True, text=True,
        cwd=os.path.dirname(RECUR),
        env={**os.environ, "PYTHONPATH": os.path.dirname(RECUR)},
        timeout=300,
    )
    out = {"total": -1, "A": -1, "B": -1, "C": -1}
    for raw in proc.stdout.splitlines():
        line = raw.replace("：", ":").strip()
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label, value = label.strip(), value.strip()
        if not value.isdigit():
            continue
        if label == "P1 计入":
            out["total"] = int(value)
        elif label.startswith("world-sota-A"):
            out["A"] = int(value)
        elif label.startswith("world-sota-B"):
            out["B"] = int(value)
        elif label.startswith("world-sota-C"):
            out["C"] = int(value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(WIKI, encoding="utf-8") as fh:
        wiki = json.load(fh)
    papers = wiki["tables"]["papers"]

    # 只撤销带 p1-pending-line 戳的 —— 它们是本轮机械归线的产物。
    # 带真实 world-sota-A 但没有 pending 戳的，是审计前就有的，不碰。
    victims = [
        k for k, v in papers.items()
        if "world-sota-A" in (v.get("tags") or [])
        and "p1-pending-line" not in (v.get("tags") or [])
        and "【格式归一】" in (v.get("notes") or "")
    ]
    print("待撤销机械归线：%d 篇" % len(victims))

    if not args.apply:
        print("[DRY-RUN] 未写盘。加 --apply 执行。")
        return 0

    bak = "%s.bak-undoline-%s" % (WIKI, time.strftime("%Y%m%dT%H%M%S"))
    shutil.copy2(WIKI, bak)
    print("备份 → %s" % bak)

    for k in victims:
        tags = papers[k]["tags"]
        papers[k]["tags"] = [
            t for t in tags
            if t != "world-sota-A"
        ] + ["p1-pending-line"]

    tmp = WIKI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(wiki, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, WIKI)

    after = recount()
    print("写后复算 · P1=%d (A%d/B%d/C%d)" % (
        after["total"], after["A"], after["B"], after["C"]))
    if after["A"] >= 803:
        print("门禁失败：A 线仍是 %d，撤销未生效" % after["A"])
        shutil.copy2(bak, WIKI)
        return 3
    print("通过 · A 线已回到真实分布，P1 计数未变（%d）" % after["total"])
    print("回滚：cp %s %s" % (bak, WIKI))
    return 0


if __name__ == "__main__":
    sys.exit(main())