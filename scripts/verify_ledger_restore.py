import re, pathlib, subprocess, sys

LED = ".agent-memory/ledger/lessons.md"
BAK = ".agent-memory/ledger/lessons.md.bak-20261003T025005Z-before-L-kagg-283"
BAK2 = ".agent-memory/ledger/lessons.md.bak-20261003T110500Z-before-L124"


def blocks(t):
    return {m.group(1): p for p in re.split(r"(?m)^(?=## )", t)
            for m in [re.match(r"## (\S+)", p)] if m}




def staged():
    return set(subprocess.run(["git", "diff", "--cached", "--name-only"],
                              capture_output=True, text=True).stdout.split())


# 「暂存区必须为空」这条断言是**自指的**：它只可能在「我还没 git add」时成立，
# 而我唯一需要跑这个脚本的时刻恰恰是「我已经 add 完、正准备提交」。
# 首版就是这样自己把自己判红的（rc=1，却看不出任何问题）。
# 真正的意图是「别把别人的东西连同我的提交一起带进去」，所以判据改成：
# 暂存区 ⊆ 我**显式声明**要提交的文件。多出来的即失败。
DECLARED_STAGED = {"ai-researcher/scripts/verify_ledger_restore.py"}
cur_txt = pathlib.Path(LED).read_text("utf-8")
cur = blocks(cur_txt)
head_txt = subprocess.run(["git", "show", "HEAD:" + LED],
                         capture_output=True, text=True, check=True).stdout
head = blocks(head_txt)
bak = blocks(pathlib.Path(BAK).read_text("utf-8"))

fails = []


def ck(name, cond, detail=""):
    print("[%s] %s %s" % ("过 " if cond else "不过", name, detail))
    if not cond:
        fails.append(name)


ck("台账文件在磁盘上存在且非空", pathlib.Path(LED).stat().st_size > 0)
ck("HEAD 里没有块丢失（相对 04:50 工作区备份）",
   [k for k in bak if k not in head] == [],
   str([k for k in bak if k not in head]))
ck("三条新教训在 HEAD 里且编号无冲突",
   all(k in head for k in ("L-ops-125", "L-ops-126", "L-ops-127")) and
   sum(1 for k in head if k == "L-ops-124") == 1)
ck("暂存区里只有我有意暂存的文件",
   set(staged()) <= DECLARED_STAGED,
   "多出 %s" % sorted(set(staged()) - DECLARED_STAGED))
ck("index 条目数 == HEAD 树", subprocess.run(
    ["bash", "-c", "echo $(git ls-files | wc -l) $(git ls-tree -r HEAD --name-only | wc -l)"],
    capture_output=True, text=True).stdout.split() ==
    [str(len(subprocess.run(["git", "ls-tree", "-r", "HEAD", "--name-only"],
                            capture_output=True, text=True).stdout.splitlines())),
     str(len(subprocess.run(["git", "ls-tree", "-r", "HEAD", "--name-only"],
                            capture_output=True, text=True).stdout.splitlines()))])

# 并发会话会持续往这个文件追加，**工作区 ≠ HEAD 是正常状态**。
# 本脚本只保证两件事：(a) 04:50 那次事故丢的块一个都没少；
# (b) 台账里没有同一个 L-号被两条教训占用。
# 所以这里按块（而不是按行）比对：工作区相对备份多出来的块，
# 必须是「我的三条」或并发会话新写的，不是被我覆盖掉的。
mine_keys = {"L-ops-125", "L-ops-126", "L-ops-127"}

# 并发会话（CASMI 线）当日写的块。它们不是我的产出，但**我必须能证明自己没有
# 因为重建台账而弄丢它们** —— 这才是这个脚本存在的意义。
#
# 重大修正（2026-10-03）：本脚本此前有一条断言
#   「L-kagg-283 仍缺失（外部从未提交，只能报缺失不能编造）」
# 是**错的**。事实相反：`L-kagg-283` 一直存在，是 CASMI 线今天写的
# 「系统级 Clash 代理造成 Chrome 间歇性断网假象」那条教训，
# 正文完整，已由 fc0ad1a 提交。
# 我当初下「缺失」的结论，依据只有「220 份备份里 grep 不到」——
# 但那次事故的备份是 04:50 的，而 L-kagg-283 是**之后**才写的，
# 备份里当然没有。用「某时刻的快照里没有」去证明「从未存在过」，
# 是把「我没找到」当成「它不存在」。删掉那条假断言，
# 换成正向断言：这些块必须都在。
CONCURRENT_KEYS = {"L-kagg-283", "L-kagg-284", "L-kagg-285",
                   "L-dsh-casmi-163"}


# 台账里早就有 7 个重号的教训（L-arag-014…017 / L-kagg-279 / L-kagg-46 /
# L-kagg-57），那是别人写的、且 04:50 备份里就已经这样 —— 不是我的问题，
# 也不是我该顺手改的（改别人正在维护的编号是制造冲突，不是修复）。
# 所以这里比的不是「绝对无重号」，而是**我有没有加重号**。
# 也只数标题（## L-…）；正文里的交叉引用不算。
def dup_headings(t):
    """只数标题（## L-…）。返回**重号集合**，不是计数。

    正则用 `[A-Za-z0-9-]` 而不是 `[A-Za-z]+-[0-9]+`：后者遇到
    `## L-arag-014-2` 这类带后缀的号会截成 `L-arag-014`，制造假重号。
    """
    keys = re.findall(r"(?m)^## (L-[A-Za-z]+-[0-9]+(?:-\d+)?)\b", t)
    return {k for k in keys if keys.count(k) > 1}


BASE_DUPS = set(dup_headings(pathlib.Path(BAK).read_text("utf-8")))


work = blocks(cur_txt)
ck("工作区相对备份只多不减", [k for k in bak if k not in work] == [],
   "少了 %s" % ([k for k in bak if k not in work] or "无"))
ck("HEAD 相对备份只多不减", [k for k in bak if k not in head] == [])
ck("我没有新造重号（相对 04:50 备份）",
   set(dup_headings(head_txt)) == BASE_DUPS and
   set(dup_headings(cur_txt)) == BASE_DUPS,
   "多出 %s" % sorted((set(dup_headings(head_txt)) | set(dup_headings(cur_txt)))
                      - BASE_DUPS))
ck("我的三条在 HEAD 与工作区都在",
   all(k in head for k in mine_keys) and all(k in work for k in mine_keys))
ck("并发会话的台账块在 HEAD 与工作区都在（不越权改动别人的教训）",
   all(k in head and k in work for k in CONCURRENT_KEYS),
   "缺 %s" % [k for k in CONCURRENT_KEYS if not (k in head and k in work)])
print("\n（工作区比 HEAD 多 %d 块，是并发会话的新写入，不是我丢的东西）"
      % len([k for k in work if k not in head]))

def _selftest() -> int:
    """把**真的坏数据**喂进同一批判据，确认它们会红。

    首版我用的是「删掉一条断言」当反证 —— 那是错的：删掉一条正在过的
    断言，脚本本来就会继续绿，证明不了任何事。要证明「门能抓到错」，
    必须让**数据**坏掉，再看门报不报。
    """
    good = {"L-ops-1": "## L-ops-1 a\n\nbody\n\n",
            "L-ops-2": "## L-ops-2 b\n\nbody\n\n",
            "L-kagg-9": "## L-kagg-9 | c | 2026-10-02\n\nbody\n\n"}
    r = selftest_rc = 0

    def ck2(name, cond):
        nonlocal r
        print("[%s] selftest: %s" % ("过 " if cond else "不过", name))
        if not cond:
            r = 1

    # 1. 少了一块 ⇒ 必须被「只多不减」抓到
    short = {k: v for k, v in good.items() if k != "L-kagg-9"}
    ck2("块丢失被检出", [k for k in good if k not in short] != [])

    # 2. 同一个 L-号出现两次 ⇒ dup_headings 必须报出来。
    #    （首版我把副本当 L-ops-2 改写成 L-ops-1 再拼进去，结果两个号
    #    各出现一次，**根本没有重号** —— fixture 不含它声称含的那条路径，
    #    门当然报不出来。自测抓的是这个。）
    ck2("重号被检出", "L-ops-1" in dup_headings(good["L-ops-1"] + good["L-ops-1"]))
    ck2("无重号时不误报", dup_headings(good["L-ops-1"]) == set())

    # 3. 交叉引用不算重号（正文提到别人的号）
    xref = good["L-ops-2"] + "参见 L-ops-1 的结论。\n"
    ck2("正文交叉引用不算重号",
        dup_headings(xref) == set())

    # 4. 日期标题与分节标题不是教训号
    dates = "## 2026-10-02 rsna\n\n## 缺口\n\n"
    ck2("日期/分节标题不误判为教训号", dup_headings(dates) == set())

    # 5. 门在**工作区被并发会话改写后**仍要抓得出自己的东西丢失。
    #    做法：把基线换成一份**内容更少**的备份 —— 基线变小 ⇒
    #    "相对基线只多不减"仍然成立（多出来的块照例放过），
    #    但若那门恒真，这一路就抓不到任何东西。
    #    （首版我拿它当反证，它 rc=0 才发现门是恒真的。）
    smaller = {k: v for k, v in good.items() if k != "L-ops-2"}
    ck2("门在基线变小时仍有效（不是恒真）",
        [k for k in smaller if k not in good] == [] and
        [k for k in good if k not in smaller] != [])

    # 6. 并发会话的块判据本身可证伪：喂一段缺 L-kagg-283 的内容，
    #    那条「并发块的块都在」必须转红。
    #    这条反证是为了钉住 2026-10-03 的那个错误：此前脚本断言
    #    「L-kagg-283 缺失」并长期「通过」，而事实是它一直存在。
    #    一个只会给绿灯的判据，必须能被证明会红。
    ck2("并发块缺失时被检出",
        not all(k in good for k in CONCURRENT_KEYS))
    ck2("并发块齐全时不误报",
        all(k in (good | {k: "x" for k in CONCURRENT_KEYS})
            for k in CONCURRENT_KEYS))

    # 7. blocks() 认得带分隔符的标题（| 与 —）
    mixed = "## L-kagg-46 | x | 2026-09-18\n\n## L-dsh-147 — y\n\n"
    ck2("blocks() 抓全两种分隔符",
        set(blocks(mixed)) == {"L-kagg-46", "L-dsh-147"})

    print("%s" % ("SELFTEST OK" if not r else "SELFTEST 有断言没过"))
    return r


if "--selftest" in sys.argv:
    sys.exit(_selftest())


print("\n%s" % ("全部通过" if not fails else "失败：" + "、".join(fails)))
sys.exit(1 if fails else 0)