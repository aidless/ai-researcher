#!/usr/bin/env python3
"""锚点作用域内的数字一致性扫描：补 research_ledger verify 的存在性盲区。

## 为什么需要它

2026-10-02 实测 `research_ledger(action=verify)` 与 `research_numbers`
的判据都是「台账里的值有没有在文档中出现」。改 1 处、漏改别处时，只要
还剩 1 处正确值就判 pass——实测把 FINAL_STATUS.md 的合计改成 1100 而
留下 4 处 1036，verdict 仍是 pass。它们挡得住「漏改」，挡不住
「改一处漏一处」，而后者恰是改稿最常见的死法。

## 判据：锚点作用域，不是数值邻近

第一版按「同一量级」比较（643 附近还有 644 就报冲突），结果对着真文档
就误报：FINAL_STATUS.md 里 `644 篇` 与 `643 篇` 是两个不同陈述
（"644 篇有实质内容" / "其中 643 篇被机械归一化"），`116e3d5` 与 `114`
更毫无关系。第二版改成"同行共现"，误报没了，但把反证也一起废了——
因为改稿漏改本来就不发生在同一行。

真正的判别信息在台账里：每条 entry 带一个 `anchor`（「P1 计入合计」
「待归线」「world-sota-A: 160」）。同一个量在不同句子里出现时，靠语义
锚点区分，而不是靠数值距离：

    带锚点的行  → 作用域内逐行核对，该行出现的量必须等于台账值
    无锚点的行  → 不归本条 entry 管（644 那行就不在 643 的作用域里）

锚点在文中找不到时降级为 `info` 而不是 error：锚点写的是复算程序的输出
格式（`world-sota-A: 160`），而 FINAL_STATUS 的表格用的是
`| A（…） | 160/500 |`，两者本就不该逐字对齐——这种情况要报"无法定位
作用域"，不能报"数字错了"。

## 用法

    python3 normalize_git_diff_numbers.py --ledger <ledger.json> --paper <doc> [更多…]
    python3 normalize_git_diff_numbers.py --selftest

退出码 0=无 error 1=有不一致 2=用法错。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# 裸整数。两道边界都是踩出来的：
#   - 前后不能是数字或小数点，否则 2210.02414 被拆成 2210；
#   - 也不能紧贴拉丁字母，否则锚点「P1 计入合计」里的 P1 会贡献一个 1、
#     commit 号 116e3d5 会贡献 116 —— 两者都成了"矛盾取值"的假来源。
#     只挡 [0-9A-Za-z.]，不挡中文：\w 在 str 模式下是 Unicode 的，
#     用 \w 会连带吃掉"其中643篇"这种中文紧贴的正常数字。
NUM = re.compile(r"(?<![0-9A-Za-z.§#])(\d{1,9})(?![0-9.])")
# 宽松版：允许数字紧贴拉丁字母。只用于**存在性**判据，不参与矛盾判。
# MISSION.md 第 353 行写 `A160+B119+C114`，值确实在那里，只是粘着线名；
# 若按严格版查就会误报"台账值一次都没出现"。粘着字母的 1 不会变成矛盾
# 取值（矛盾判仍走 NUM），所以放宽存在性不会把 P1 的 1 放进来。
NUM_LOOSE = re.compile(r"(\d{1,9})(?![0-9.])")
# 序数与章节引用不是度量值：`（见 §1）`、`第 2 节`、`表 3`、`图 4`。
# 不剔除的话 FINAL_STATUS.md 第 9 行会被当成"把这件事实写成 1"。
CITATION = re.compile(r"(?:§|第\s*|表\s*|图\s*|Fig\.?\s*|Table\s*|Eq\.?\s*)"
                      r"(\d{1,9})(?:\s*[节章部分条])?")
# x/y 里的整数是同一个比值的分子分母，不是两个待比较的量。
# `待归线 643；P2 100/100` 里 100 是 P2 的完成数，与 643 无关——
# 若不整段剔除，锚定行就会把它读成"把 643 写成 100"。分子分母都要丢，
# 因为 `1036/1000` 里的 1000 也是目标而不是"另一个真值"（见 ratio_target）。
RATIO = re.compile(r"\d{1,9}\s*/\s*\d{1,9}")


def window(value: int) -> int:
    """多接近才算"同一件事的另一种写法"。

    这个常数调错过两次，两次都失败：
      - 太宽（value*0.02）：643 旁边冒出 644（另一个事实）就误报；
      - 太窄（value*0.01）：抓得住笔误抓不住改稿——实测把 1036 改成
        1100（差 64，远超 ±10 的 1% 窗口）完全查不出来，而"改一处
        漏一处"恰恰是这个门存在的唯一理由。
    相对比例治不了这个：笔误和改稿的差值量级完全不同，且合法的相邻
    整数只差 1。所以真正的判别信息不在数值距离，而在**句法位置**——
    见 ratio_target()：同一句里两个数时，跟着分母/量词走的那个是目标，
    不是"另一个版本的真值"。
    """
    return max(1, round(value * 0.01))


def ratio_target(line: str, value: int) -> set[int]:
    """识别不该参与矛盾判定的数：`x/y` 的分母 y 与"目标 1000"式修饰。

    `| 1036/1000 |` 里 1000 是目标不是另一个真值；`P1 精读 1000 篇`
    里的 1000 同理。它们出现在锚定行里却不是矛盾，靠这条剔除。
    """
    drop: set[int] = set()
    for m in re.finditer(r"(\d{1,9})\s*/\s*(\d{1,9})", line):
        a, b = int(m.group(1)), int(m.group(2))
        if a == value:
            drop.add(b)          # 真值在前 → 后者是分母/目标
        elif b == value:
            drop.add(a)          # 真值在后 → 前者是分母/目标
        # 分子分母都不是真值时**不能**整段剔除：`1100/1000` 正是被改坏的
        # 分子，剔了就等于给篡改开门。别的量（如 P2 自己的 100/100）
        # 由 clause_of 的分句作用域排除，不该在这里动手。
    for m in re.finditer(r"(?:目标|计划|预期|设定|上限)\D{0,4}(\d{1,9})", line):
        drop.add(int(m.group(1)))
    return drop


def load_ledger(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def numbers_in(line: str) -> set[int]:
    """这一行里被当作"度量值"候选的整数。

    剔除三类非度量：紧贴拉丁字母的（P1、116e3d5、arXiv 2210.02414）
    与序数/引用标记（§1、第 2 节、表 3）。剩下的才参与矛盾判——
    它们的集合为空时更说明这行是散文，不是承载数字的记录。
    比值不在这里整段剔除：`1036/1000` 的真值 1036 必须留下，只有分母
    该丢（ratio_target 负责），整段删会把真值一起误杀。
    """
    s = CITATION.sub(" ", line)
    return {int(m.group(1)) for m in NUM.finditer(s)}


def numbers_present(line: str) -> set[int]:
    """宽松的数字集合，只用于"这个值在文中出现过没有"。"""
    s = CITATION.sub(" ", line)
    return {int(m.group(1)) for m in NUM_LOOSE.finditer(s)}


def is_data_line(line: str) -> bool:
    """这一行是"承载数字的记录行"吗。

    真值必须逐处核对的地方是表格行与键值行；散文句只在它自带数字时
    才算数。判据：
      - Markdown 表格行（含 `|`）
      - `键：值` / `键 = 值` 形式的短行
      - 带前置列表符且含数字的短行
    排除标题行与纯散文段——「待归线篇目**计入 P1 总数但不并入任何一条线**」
    讲的是口径不是数量，若计入覆盖统计就稳定误报。
    """
    s = line.strip()
    if not s or s.startswith("#") or s.startswith(">"):
        return False
    if "|" in s:
        return True
    if re.match(r"^[-*]\s+\S.*\d", s):
        return True
    if re.match(r"^\S[^，。；：]{0,24}\s*[:：=]\s*\S", s) and re.search(r"\d", s):
        return True
    return False


def clause_of(line: str, anchor: str) -> str | None:
    """取锚点所在**子句**。

    锚点的作用域不是整行，而是锚点自己所在的那个分句。同一行里常有
    多件事：`待归线 643；P2 100/100（已收官）` —— 锚点「待归线」该管
    的只有 `待归线 643`，`100/100` 是 P2 的完成数，与它无关。
    而 `- P1 精读 1000 篇：**1100/1000**` 里锚点与比值同属一个分句，
    1100 正是这条事实的改写版本，必须报出来。
    分句符：；;。，, 以及 Markdown 表格分隔符 |（表格行按格算）。
    """
    if anchor not in line:
        return None
    # 作用域不能是整行，也不能是整个分句——实测两种都会连累无辜：
    #   - 整行：`待归线 643；P2 100/100` 里的 100 被读成"把 643 写成 100"；
    #   - 整个分句：MISSION.md 的 `A160+B119+C114+待归线643` 是一整个
    #     分句，改 P1 合计（1036→1100）会被同时判成"C 线被写成 1100"。
    # 规则分两种：
    #   - 表格行：取锚点所在单元格及其左右邻居（`|` 相邻的取值才是
    #     这条事实的写法；按 | 全切开就永远看不到被改的值）。
    #   - 散文行：取锚点所在的**紧邻片段**，切分符用强分隔
    #     `；;。，,、|+（）()【】[]` 与连续空格，但**不切** `：`/`=`
    #     （`- P1 精读 1000 篇：**1036/1000**` 里冒号后的比值才是取值）。
    if "|" in line:
        cells = line.split("|")
        for i, cell in enumerate(cells):
            if anchor in cell:
                return "|".join(cells[max(0, i - 1):i + 2])
        return None
    for piece in re.split(r"[；;。，,、|+（）()【】\[\]]|\s{2,}", line):
        if anchor in piece:
            return piece
    return line


def anchors_of(entry: dict) -> list[str]:
    """一条 entry 的锚点可以是**同义词列表**。

    单个锚点串抓不到改稿漏改：`- P1 精读 1000 篇：**1100/1000**` 与
    `| **P1 计入合计** | **1036/1000** |` 说的是同一个事实，用的却是两套
    措辞（实测：锚点只有「P1 计入合计」时，改坏第 9 行完全查不出来）。
    真正的签名不是"锚点行少了真值"，而是**同一量级的事实被写成了两个
    不同的值**——所以锚点负责圈定"这件事在哪些分句被提到过"，
    圈子内的取值必须彼此一致。
    """
    raw = entry.get("anchor") or ""
    if isinstance(raw, str):
        raw = [raw]
    return [a for a in raw if a]


def scan(doc: str, ledger: dict) -> list[dict]:
    """每条 entry：圈出所有提到这件事的行，比较它们的取值是否一致。

    覆盖完整性只是辅助信号，主判据是**取值一致性**：
        圈内取值只有一种  → 一致
        圈内出现两种取值  → error（改稿漏改）
        一处都没有真值    → info（锚点写法对不上，没核对成）
    """
    with open(doc, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    findings: list[dict] = []
    for entry in ledger.get("entries", []):
        value = entry.get("value")
        anchors = anchors_of(entry)
        if not isinstance(value, int):
            continue

        anywhere = [i for i, ln in enumerate(lines, 1) if value in numbers_present(ln)]
        if not anywhere:
            findings.append({
                "level": "error", "key": entry["key"], "expected": value,
                "message": "台账值 %d 在文档中一次都没出现" % value,
            })
            continue

        if not anchors:
            findings.append({
                "level": "info", "key": entry["key"], "expected": value,
                "message": "该条没有锚点，无法判定作用域（%d 行出现，未核对）"
                           % len(anywhere),
            })
            continue

        scoped = [i for i, ln in enumerate(lines, 1)
                  if any(a in ln for a in anchors)]
        if not scoped:
            findings.append({
                "level": "info", "key": entry["key"], "expected": value,
                "message": "锚点 %s 不在文档中，无法定位作用域（%d 行出现，未核对）"
                           % ("/".join(anchors), len(anywhere)),
            })
            continue

        data = [i for i in scoped if is_data_line(lines[i - 1])] or scoped
        # 矛盾判据：锚点所在**分句**里出现了除真值之外的数，且它既不是
        # 分母/目标，也不是别的 entry 已认领的量。差额多大都算——改稿不会
        # 只差 1%，"1036→1100" 和 "643→644" 是同一种病；而 P2 自己的
        # 100/100 在另一个分句里，不会混进来。
        claimed: set[int] = {e["value"] for e in ledger.get("entries", [])
                             if isinstance(e.get("value"), int)}
        variants: dict[int, list[int]] = defaultdict(list)
        for i in data:
            line = lines[i - 1]
            text = " ".join(filter(None, (clause_of(line, a) for a in anchors)))
            drop = ratio_target(text, value) | claimed
            for got in numbers_in(text):
                if got != value and got not in drop:
                    variants[got].append(i)

        if variants:
            for got, where in sorted(variants.items()):
                findings.append({
                    "level": "error", "key": entry["key"], "expected": value,
                    "conflicting": got, "lines": sorted(where),
                    "message": "锚点 %s 圈定的行里，第 %s 行把这件事实写成 %d，"
                               "而台账是 %d —— 改稿漏改"
                               % ("/".join(anchors), ",".join(map(str, where)),
                                  got, value),
                })
        else:
            ok = [i for i in data if value in numbers_present(lines[i - 1])]
            if not ok:
                findings.append({
                    "level": "info", "key": entry["key"], "expected": value,
                    "message": "锚点 %s 圈定 %d 行却都未带真值 %d，未核对成"
                               "（值仍在第 %s 行出现）"
                               % ("/".join(anchors), len(data), value,
                                  ",".join(map(str, anywhere[:4]))),
                })
    return findings


def selftest() -> int:
    """门必须能失败：每条反证都要真能触发，否则脚本是装饰。"""
    tmp = "/tmp/_ncn_selftest.md"
    led = {"entries": [
        {"key": "p1.total", "value": 1036,
         "anchor": ["P1 计入合计", "P1 精读 1000 篇"]},
        {"key": "p1.pending_line", "value": 643, "anchor": "待归线"},
    ]}
    clean = ("| **P1 计入合计** | 1036/1000 | 103.6% |\n"
             "- P1 精读 1000 篇：**1036/1000 — 数量已超额**\n"
             "| **待归线（笔记合格但线未定）** | 643 | 新增 |\n"
             "另有 644 篇 lit1000 笔记早已写过实质内容，其中 643 篇被机械归一化。\n")

    # 反证 7 —— MISSION.md 的 `A160+B119+C114+待归线643` 整串：锚点用
    # 线名当同义词后，A/C 两家的分句跨度把 B119 的数字也圈了进来，
    # 于是改 P1 合计会同时被判成"B 线被写成 1100"。合取式（\u0026 是
    # 实际字符）要求锚点与取值靠得更近。
    compact = ("P1 = **1036**（A160+B119+C114+待归线643），与 FINAL_STATUS 一致。\n")
    led2 = {"entries": [
        {"key": "p1.total", "value": 1036, "anchor": ["P1 = "], "cooccur": ["1036"]},
        {"key": "p1.line_a", "value": 160, "anchor": ["A"], "cooccur": ["160"]},
        {"key": "p1.line_b", "value": 119, "anchor": ["B"], "cooccur": ["119"]},
        {"key": "p1.line_c", "value": 114, "anchor": ["C"], "cooccur": ["114"]},
    ]}
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(compact)
    got = scan(tmp, led2)
    assert got == [], "干净紧凑串不应报问题，却报了 %s" % got
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(compact.replace("P1 = **1036**", "P1 = **1100**"))
    got = scan(tmp, led2)
    assert any(f["level"] == "error" and f["key"] == "p1.total" for f in got), \
        "紧凑串里改合计未被抓到：%s" % got
    assert not any(f["key"] == "p1.line_c" for f in got), \
        "改合计却连累 C 线被误报：%s" % got
    print("  反证通过：紧凑串 A160+B119+C114 只按就近配对，不跨线误报")

    def run(text: str) -> list[dict]:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        return scan(tmp, led)

    base = run(clean)
    assert base == [], "干净文档不应报问题，却报了 %s" % base
    print("  通过：干净文档无问题（含 644/643 并列的合法句 + 同义锚点两处一致）")

    # 反证 1 —— 改稿漏改的真实现场：同义词两套措辞，结论段改了、表格行没改。
    # 这正是内置 verify 判 pass 的那个形态（sed 只改第 9 行）。
    got = run(clean.replace("- P1 精读 1000 篇：**1036/1000",
                            "- P1 精读 1000 篇：**1100/1000"))
    assert any(f["level"] == "error" and f["key"] == "p1.total" for f in got), \
        "反证「同义措辞一处改一处漏」未触发：%s" % got
    print("  反证通过：结论段改 1100 / 表格行仍 1036（同义锚点）")

    # 反证 1b —— 同一个锚点字面重复出现、只改一处。
    got = run(clean + "| **P1 计入合计** | 1100/1000 |\n")
    assert any(f["level"] == "error" and f["key"] == "p1.total" for f in got), \
        "反证「同锚点两处只改一处」未触发：%s" % got
    print("  反证通过：同锚点两处只改一处")

    # 反证 2 —— 台账值被整段删掉。
    got = run("| **待归线（笔记合格但线未定）** | 643 | 新增 |\n")
    assert any(f["level"] == "error" and f["key"] == "p1.total" for f in got), \
        "反证「值整段消失」未触发：%s" % got
    print("  反证通过：p1.total 整段消失")

    # 反证 3 —— 锚点缺失只降级 info，不得误报 error。
    got = run("| P1 合计 | 1036 | 待办 643 |\n")
    assert not any(f["level"] == "error" for f in got), "锚点缺失被误判成 error：%s" % got
    assert any(f["level"] == "info" for f in got), "锚点缺失应降级为 info：%s" % got
    print("  反证通过：锚点缺失降级 info，不误报")

    # 反证 4 —— 锚定行全部不带真值（锚点写法与文档对不上）同样降级 info。
    # 注意 1036 必须在别处出现，否则命中的是"值整段消失"那条 error，
    # 测的就不是锚点作用域了。
    got = run("| P1 计入合计 | 已超额 | 103.6% |\n| 待归线 | 643 |\n"
              "复算脚本输出 1036，与本表一致。\n")
    assert not any(f["level"] == "error" for f in got), \
        "锚定行无真值被误判成 error：%s" % got
    print("  反证通过：锚定行未带真值 → info 而非 error")

    # 反证 5 —— 锚定行疑似改错（643→644 且别处仍留着真值）必须报 error，
    # 而不是因为"值还在文中出现"就放过。
    got = run("| **P1 计入合计** | 1036/1000 |\n| **待归线（笔记合格但线未定）** | 644 |\n"
              "历史基线记 643。\n")
    assert any(f["level"] == "error" and f["key"] == "p1.pending_line" for f in got), \
        "锚定行疑似改错却没抓到：%s" % got
    print("  反证通过：锚定行 643 改成 644")

    # 反证 6 —— 差额过大的改写不该算矛盾（目标 1000 与实际 1036 同段出现）。
    got = run(clean + "| **P1 计入合计** | 1036/1000 |")
    assert not any(f["key"] == "p1.total" for f in got), \
        "把目标值 1000 当成矛盾：%s" % got
    print("  反证通过：目标 1000 与实际 1036 同段不算矛盾")

    os.remove(tmp)
    print("SELFTEST OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger")
    ap.add_argument("--paper", nargs="*", default=[])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.ledger or not args.paper:
        ap.error("需要 --ledger 与 --paper（或 --selftest）")

    ledger = load_ledger(args.ledger)
    findings: list[dict] = []
    for doc in args.paper:
        for f in scan(doc, ledger):
            f["document"] = os.path.basename(doc)
            findings.append(f)

    for f in findings:
        print("[%s] %s :: %s — %s" % (f["level"], f.get("document", ""),
                                      f["key"], f["message"]))
    errors = sum(1 for f in findings if f["level"] == "error")
    print("扫描 %d 个文档 / %d 条台账 → %d error, %d info"
          % (len(args.paper), len(ledger.get("entries", [])), errors,
             len(findings) - errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())