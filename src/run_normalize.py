#!/usr/bin/env python3
"""P1 笔记归一化执行器。

用法::

    python3 run_normalize.py --dry-run              # 只报告，不写盘（默认）
    python3 run_normalize.py --limit 10             # 先小批量试写
    python3 run_normalize.py --apply                # 全量写入

写入真值库（`~/.dsh/storages/research_wiki.json`）前必做三件事，
对应 AGENTS.md 铁律 #6（共享文件无锁、跨会话竞态）：

1. **重新读最新态** —— 不复用任何缓存副本，避免覆盖别人刚写的行
2. **留 `.bak-<时间戳>` 备份** —— 可一键回滚
3. **写后复验** —— `count_p1` 计数不得下降，且新增篇目三段齐备

退出码即门禁（AGENTS.md 铁律 #7）：任何一步违反 → exit≠0。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from normalize_notes import classify, normalize_one  # noqa: E402

WIKI = os.path.expanduser("~/.dsh/storages/research_wiki.json")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(REPO, "reports")
RECUR = os.path.join(
    os.path.dirname(REPO), ".agent-memory", "ledger",
    "count_p1_world_sota_20261001.py",
)


def load_wiki() -> dict[str, Any]:
    with open(WIKI, encoding="utf-8") as fh:
        return json.load(fh)


def run_recount() -> tuple[bool, str]:
    """跑官方复算脚本。返回 (是否通过, 输出)。"""
    if not os.path.exists(RECUR):
        return False, "复算脚本缺失: %s" % RECUR
    proc = subprocess.run(
        [sys.executable, RECUR], capture_output=True, text=True,
        cwd=os.path.dirname(RECUR),
        env={**os.environ, "PYTHONPATH": os.path.dirname(RECUR)},
        timeout=300,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def parse_p1(output: str) -> dict[str, int]:
    """从复算输出里抠出 P1 计数。

    注意：输出用**全角冒号** `：`（`P1 计入            : 393`），不是半角。
    这里只匹配半角会让基线静默变成 0 —— 而基线 0 与「写后计数不降」这道
    门禁组合起来会永远通过，等于没有门。
    """
    out: dict[str, int] = {"total": -1, "A": -1, "B": -1, "C": -1}
    for raw in output.splitlines():
        line = raw.replace("：", ":").strip()
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label, value = label.strip(), value.strip()
        if not value.isdigit():
            continue
        n = int(value)
        if label == "P1 计入":
            out["total"] = n
        elif label.startswith("world-sota-A"):
            out["A"] = n
        elif label.startswith("world-sota-B"):
            out["B"] = n
        elif label.startswith("world-sota-C"):
            out["C"] = n
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 笔记归一化执行器")
    ap.add_argument("--apply", action="store_true", help="真正写盘（默认 dry-run）")
    ap.add_argument("--dry-run", action="store_true",
                    help="显式声明只报告不写盘（与默认行为相同，存在是为了让"
                         "文档里的 --dry-run 真能跑 —— 文档与实现脱节本身就是一种缺陷）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 篇（0=全部）")
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"), help="归一戳日期")
    args = ap.parse_args()

    # ── 门 1：复算基线 ────────────────────────────────────────────────
    ok, out = run_recount()
    if not ok:
        print("门1 失败：基线复算未通过（P1 数字本来就不可信，拒绝在其上动手）")
        print(out[-800:])
        return 2
    before = parse_p1(out)
    if before["total"] < 0:
        print("门1 失败：复算输出解析不出 P1 计数（格式变了？拒绝盲写）")
        print(out[-800:])
        return 2
    print("门1 通过 · 基线 P1 = %d (A%d/B%d/C%d)" % (
        before["total"], before["A"], before["B"], before["C"]))

    # ── 门 2：分桶 ────────────────────────────────────────────────────
    wiki = load_wiki()
    buckets = classify(wiki)
    print("门2 分桶 · 已合格 %d · 可自动归一 %d · 需人工 %d" % (
        len(buckets["already_strict"]),
        len(buckets["normalizable"]),
        len(buckets["needs_human"]),
    ))

    # ── 门 3：逐篇归一，抽不全一律拒收 ─────────────────────────────────
    papers = wiki["tables"]["papers"]
    targets = buckets["normalizable"]
    if args.limit:
        targets = targets[: args.limit]
    results = [normalize_one(k, papers[k], args.date) for k in targets]
    good = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    print("门3 逐篇 · 成功 %d · 拒收 %d" % (len(good), len(bad)))

    needs_human = [(k, papers[k].get("notes") or "") for k in buckets["needs_human"]]
    print("       需人工合计 %d 篇（不计入本次）" % len(needs_human))

    report: dict[str, Any] = {
        "date": args.date,
        "mode": "apply" if args.apply else "dry-run",
        "before_p1": before,
        "buckets": {k: len(v) for k, v in buckets.items()},
        "normalized": len(good),
        "rejected": [{"key": r.key, "missing": r.missing} for r in bad],
        "needs_human_keys": [k for k, _ in needs_human],
    }

    if not args.apply:
        os.makedirs(REPORTS, exist_ok=True)
        path = os.path.join(REPORTS, "normalize_dryrun_%s.json" % args.date)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        expected = before["total"] + len(good)
        print("\n[DRY-RUN] 未写盘。预期写后 P1：%d → %d (+%d)" % (
            before["total"], expected, len(good)))
        print("[DRY-RUN] 报告：%s" % path)
        if bad:
            print("[DRY-RUN] 拒收样本（需人工）：")
            for r in bad[:5]:
                print("   %s  缺段=%s  %s" % (r.key, r.missing, r.title))
        return 0

    # ── 门 4：写前重新读最新态 + 备份 ──────────────────────────────────
    fresh = load_wiki()  # 铁律 #6：不复用内存里的旧副本
    bak = "%s.bak-normalize-%s" % (WIKI, time.strftime("%Y%m%dT%H%M%S"))
    shutil.copy2(WIKI, bak)
    print("门4 备份 → %s" % bak)

    fp = fresh["tables"]["papers"]
    written = 0
    untagged: list[str] = []
    for r in good:
        if r.key in fp:
            fp[r.key]["notes"] = r.notes
            tags = fp[r.key].setdefault("tags", [])
            if not any(t.startswith("world-sota-") for t in tags):
                # 不擅自归线。P1 的 line 字段表示"属于哪条研究线"，
                # 那是人的判断（MISSION.md 锁定字段）；机器猜一个 A 上去
                # 会让复算输出 A803/B119/C114 —— 一个假的分布。
                # 这里只记下"待归线"清单，由人分配。
                tags.append("p1-pending-line")
                untagged.append(r.key)
            written += 1

    tmp = WIKI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(fresh, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, WIKI)
    print("       写入 %d 篇" % written)

    # ── 门 5：写后复验，计数不得下降 ───────────────────────────────────
    ok2, out2 = run_recount()
    after = parse_p1(out2)
    if not ok2:
        print("门5 失败：写后复算未通过，回滚")
        shutil.copy2(bak, WIKI)
        return 3
    if after["total"] < before["total"]:
        print("门5 失败：P1 计数下降 %d → %d，回滚" % (before["total"], after["total"]))
        shutil.copy2(bak, WIKI)
        return 3
    print("门5 通过 · P1 %d → %d (+%d)" % (
        before["total"], after["total"], after["total"] - before["total"]))
    print("       A%d→%d  B%d→%d  C%d→%d" % (
        before["A"], after["A"], before["B"], after["B"],
        before["C"], after["C"]))

    report["after_p1"] = after
    report["backup"] = bak
    report["pending_line_assignment"] = untagged
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, "normalize_apply_%s.json" % args.date)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("\n[APPLIED] 报告：%s\n[APPLIED] 回滚命令：cp %s %s" % (path, bak, WIKI))
    return 0


if __name__ == "__main__":
    sys.exit(main())