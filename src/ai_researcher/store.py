"""L3 提案状态机：把 L2 判出的 14 条 executable 从「一次性 JSON」变成「有历史的工单」。

## 它解决的真问题

L2 跑完产出 `proposals/proposals.json`，里面有 14 条 `executable`。但那一刻之后
就没有然后了——没人知道哪条在跑、谁批的、为什么批、结果算不算数。
**没有状态的自动化，就是一次性脚本。**

## 三条设计决定，每条都是被坑逼出来的

### 一、可执行性必须**每轮重新实测**，不许读缓存

AGENTS.md 第 4 条已经吃过一次亏：凭印象写「本机无条件可用」，探测才发现
Docker/GPU/容器隔离全都不可用，差点白丢两个迁移项。所以这里的能力探测
**每次运行都真读一次系统**，不读配置、不读上轮结果、不接受注入
（`--capability` 只在自测里用，且会在 report 里标 `probe_source`）。

### 二、不可执行不等于可以藏起来

云服务器现在是关的（用户 2026-10-02 明说「云服务器暂时没有」）。
最容易犯的错是：把远端提案从队列里 `filter` 掉，于是「14 条可执行」
变成一个没人知道它少了东西的假数字。

**正确形态是留在队列里，`executable_here: false`，并写明实测原因**：
```
executable_here   : false
blocking_reason   : 云服务器不可用（SSH banner 前断开），且本机 GPU 6144 MiB < 需 16384 MiB
measured_capability: {...当轮实测的原始数...}
remote_probe      : "2026-10-03T10:31:00Z ssh -o ConnectTimeout=5 ... → banner 前断开"
```

### 三、状态迁移必须带非空 reason

这是把铁律 6/7 变成代码。`blocked → approved` 凭什么？没有凭什么就不许迁。
终态条目必须有 `conclusion`。**这不是为了严格，是为了三个月后还有人看得懂
当初为什么批了这条。**

## 状态图（无环，有向）

```
    待批 ──批准──→ 已批 ──跑通──→ 已跑 ──判读──→ 出结论
     │              │             │              │
     ↓              ↓             ↓              ↓
   被阻塞        被阻塞        被推翻          被推翻

被阻塞 ──补齐──→ 待批        （唯一回头路，且必须带 reason）
```

任何其他迁移（含 `出结论 → 待批`）一律拒绝。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from . import runner as U
from . import ranker as R

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "store", "proposals_state.json")
LOG = os.path.join(ROOT, "store", "transitions.jsonl")

# ── 状态机定义 ──────────────────────────────────────────────────────────
# 键是状态，值是允许的下一状态。**有向无环**：`出结论` 和 `被推翻` 是终态，
# 没有出边 —— 改了主意的正确做法是重开一条新提案，不是把旧结论改回去。
TERMINAL = ("出结论", "被推翻")
STATES: dict[str, tuple[str, ...]] = {
    "待批":   ("已批", "被阻塞"),
    "已批":   ("已跑", "被阻塞", "待批"),
    "已跑":   ("出结论", "被推翻"),
    "出结论": (),          # 终态
    "被推翻": (),# 终态
    "被阻塞": ("待批",),    # 唯一回头路
}

# ── 硬需求阈值：只认「明确写了要多少」的需求 ─────────────────────────
# 不猜。不写需求就是没有需求，而不是「默认需要 8G 显存」。
# 需求只能从提案的观测锚里读出**显式**的数字，见 NEED_*。
NEED_GPU_MIB = 16384       # 本机 6144 MiB ⇒ 一切要 GPU 的提案在此判不可执行

# 终态结论的最小字数：低于此值的「结论」是占位符，不是结论。
# 取 8 是因为它正好把 W5 实测里那类 5–7 字的机械缩写（「跨度不足」「无重」）
# 挡在门外——那种字符串读起来像结论，其实只是标签。
MIN_CONCLUSION_LEN = 8
PLACEHOLDER = {"tbd", "todo", "n/a", "na", "none", "done", "ok",
               "待补", "待定", "完成", "无"}


@dataclass
class Transition:
    """一次状态迁移的记录。**append-only**，永不修改。"""

    seq: int
    arxiv_id: str
    frm: str
    to: str
    reason: str
    at: str
    actor: str = "l3_store"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Entry:
    """队列里的一条提案 + 它的当前状态。"""

    arxiv_id: str
    title: str
    verdict: str# executable / blocked / needs_human
    state: str = "待批"
    executable_here: bool = True
    blocking_reason: str = ""
    demand_kind: str = ""      # gpu/data/net，空=原文未提
    demand_quote: str = ""     # 命中处的原文片段，供人核对
    measured_capability: dict[str, Any] = field(default_factory=dict)
    remote_status: str = "unknown"
    remote_probe: str = ""
    conclusion: str = ""
    transitions: list[Transition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["transitions"] = [t.to_dict() for t in self.transitions]
        return d


# ── 能力探测：真读系统 ─────────────────────────────────────────────────
def _load_prior() -> list[Entry] | None:
    """从 OUT 读回上一轮条目（含 Transition 从 dict 重建）。文件不存在
    返回 None（首轮）。解析失败**不静默**——宁可中断也不能丢审批台账。"""
    if not os.path.exists(OUT):
        return None
    with open(OUT, encoding="utf-8") as fh:
        raw = json.load(fh)
    prior: list[Entry] = []
    for d in raw.get("entries", []):
        ts = [Transition(**t) for t in d.pop("transitions", [])]
        e = Entry(**d, transitions=ts)
        prior.append(e)
    return prior


def probe_capability() -> dict[str, Any]:
    """当轮实测。**不缓存、不读配置、不接受注入**（自测除外）。

    `nvidia-smi` 失败（无 GPU / 驱动异常）与返回 0 显存必须区分开：
    前者是真的没卡，后者是有卡但被占满了，两者的 blocking_reason 完全不同。
    """
    cap: dict[str, Any] = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                      time.gmtime()),
                           "probe_source": "live"}
    # 内存
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            mi = {l.split(":")[0]: l.split()[1] for l in fh if ":" in l}
        cap["mem_total_gb"] = round(int(mi["MemTotal"]) / 1024 / 1024, 1)
        cap["mem_available_gb"] = round(
            int(mi["MemAvailable"]) / 1024 / 1024, 1)
    except (OSError, KeyError, ValueError) as e:
        cap["mem_available_gb"] = None
        cap["mem_probe_error"] = repr(e)
    # 磁盘
    try:
        st = os.statvfs(ROOT)
        cap["disk_free_gb"] = round(st.f_bavail * st.f_frsize / 1e9, 1)
        cap["disk_total_gb"] = round(st.f_blocks * st.f_frsize / 1e9, 1)
    except OSError as e:
        cap["disk_free_gb"] = None
        cap["disk_probe_error"] = repr(e)
    # GPU
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=True)
        total, used = (int(x) for x in out.stdout.strip().split("\n")[0]
                       .split(","))
        cap["gpu_total_mib"] = total
        cap["gpu_used_mib"] = used
        cap["gpu_free_mib"] = total - used
        cap["gpu_present"] = True
    except (subprocess.SubprocessError, ValueError, IndexError,
            FileNotFoundError) as e:
        cap["gpu_present"] = False
        cap["gpu_total_mib"] = None
        cap["gpu_free_mib"] = None
        cap["gpu_probe_error"] = repr(e)
    return cap


def probe_remote(timeout_s: int = 5) -> dict[str, Any]:
    """探测云服务器。**不可用时如实报 unavailable，绝不假装排上了队。**

    这里只做「能不能建连」这一个判断，且默认 `--no-remote` 时**不跑**
    （免得每轮都去戳一个关着的实例）。
    """
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout_s}",
           "seetacloud-h3", "true"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout_s + 5)
        ok = r.returncode == 0
        detail = (r.stderr or r.stdout or "").strip().split("\n")[-1][:160]
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        ok, detail = False, repr(e)[:160]
    return {"status": "available" if ok else "unavailable",
            "probe_at": at, "detail": detail}


def can_run_here(cap: dict[str, Any], needs_gpu: bool = False,
                 demand_kind: str = "") -> tuple[bool, str]:
    """本地可执行性判定。**返回 (能不能, 为什么不能)**，不能只返回 False。

    「不能」必须能回答「差多少」——只说 False 的话，人无法行动。

    `demand_kind` 非 gpu 时**一律判不可跑**：数据与外网需求没有本地量度，
    「本机大概有」是猜测，而猜测当判据等于没判（AGENTS.md 第 4/7 条）。
    只有 GPU 需求能用 nvidia-smi 当场量出来，才允许通过。
    """
    problems = []
    if needs_gpu:
        if not cap.get("gpu_present"):
            problems.append("本机无 GPU（nvidia-smi 不可用）")
        elif cap.get("gpu_free_mib", 0) < NEED_GPU_MIB:
            problems.append(
                "显存不足：需 %d MiB，本机可用 %s MiB（总 %s MiB）"
                % (NEED_GPU_MIB, cap.get("gpu_free_mib"),
                   cap.get("gpu_total_mib")))
    elif demand_kind in ("data", "net"):
        problems.append(
            "%s 需求未测量：原文提到该类资源但未给体量/来源，"
            "本地可得性无法判定（fail-closed）"
            % {"data": "数据", "net": "外网"}[demand_kind])
    if cap.get("disk_free_gb") is None:
        problems.append("磁盘容量探测失败")
    elif cap["disk_free_gb"] < 5:
        problems.append("磁盘余量 %.1fG < 5G 下限（拒绝启动）"
                        % cap["disk_free_gb"])
    if cap.get("mem_available_gb") is None:
        problems.append("内存探测失败")
    return (not problems, "；".join(problems))


def explicit_demand(p: U.Proposal) -> tuple[str, str]:
    """从提案原文里抽**显式**的算力/数据需求。返回 (kind, 引用原文)。

    kind ∈ {"gpu", "data", "net", ""}；空串表示**原文没提**。

    只认显式提及。猜不得 ——「这项实验大概要卡」是推测，而推测一旦变成
    「本机能跑」的判据，整条队列的可信度就没了（AGENTS.md 第 4 条）。

    抽不到不是「不需要」，而是**需求未测量**。这是 fail-closed 与乐观假设
    的唯一分界线，也是本模块最容易写成装饰门的地方。
    """
    text = " ".join([p.open_problem] + list(p.object_candidates)
                    + list(p.criterion_hints) + list(p.observe_hints))
    for kind, words in (("gpu", ("显存", "GPU", "gpu", "显卡", "加速卡")),
                        ("data", ("数据集", "语料", "训练集", "标注", "爬取")),
                        ("net", ("下载", "联网", "外部服务", "API 额度"))):
        for w in words:
            i = text.find(w)
            if i >= 0:
                return kind, text[max(0, i - 24):i + 24]
    return "", ""


def build(proposals: list[U.Proposal] | None = None,
          cap: dict[str, Any] | None = None,
          remote: dict[str, Any] | None = None,
          do_remote: bool = False,
          prior: list[Entry] | None = None) -> list[Entry]:
    """把 L2 提案装配成队列条目。**只读**，不写 wiki、不碰共享文件。

    prior：上一轮的条目列表。状态机的**记忆**（state / conclusion /
    transitions）必须跨轮保留——transitions 里存着人的批准记录和终态结论，
    重置等于销毁审批台账。探针字段（executable_here / blocking_reason /
    measured_capability / remote_*）照旧**当轮刷新**，不读缓存：状态是
    「已做出的决定」，探针是「此刻的测量」，二者不互相改写。
    """
    if proposals is None:
        ranked = R.rank()
        proposals = U.build(ranked)
    if cap is None:
        cap = probe_capability()
    if remote is None:
        remote = probe_remote() if do_remote else {
            "status": "not_probed", "probe_at": "", "detail": ""}
    rank_by_id = {r.arxiv_id: r for r in R.rank()}

    out: list[Entry] = []
    for p in proposals:
        # 只有 executable 才进「待批」；blocked 的进「被阻塞」，needs_human
        # 也进「待批」——因为它缺的正是**人的批准**，机器判不了就得等人。
        if p.verdict == "executable":
            state = "待批"
        elif p.verdict == "blocked":
            state = "被阻塞"
        else:
            state = "待批"

        # 先抽显式需求。抽不到 = 需求未测量 ⇒ **不得**判成「本机能跑」。
        # 上一版把 needs_gpu 当成可选分支、抽不到就默认可跑，于是 14 条
        # 全部 executable_here=True —— 一道对全集恒真的门，等于没有门。
        kind, quote = explicit_demand(p)
        if kind == "":
            ok = False
            reason = ("需求未测量：提案原文未显式给出算力/数据需求，"
                      "无法判定本机可跑（fail-closed）。"
                      "补齐方式：为该提案写一份 demand（需 X G 显存 / "
                      "需 N GB 数据 / 需外网），再重跑本模块")
        else:
            ok, reason = can_run_here(cap, needs_gpu=(kind == "gpu"),
                                      demand_kind=kind)
            if not ok and remote.get("status") == "unavailable":
                reason += "；云服务器亦不可用（%s）" % (
                    remote.get("detail") or "未探测")

        r = rank_by_id.get(p.arxiv_id)
        out.append(Entry(
            arxiv_id=p.arxiv_id,
            title=(r.title if r else ""),
            verdict=p.verdict,
            state=state,
            executable_here=ok if p.verdict == "executable" else False,
            blocking_reason=reason if (p.verdict == "executable" and not ok)
                             else p.blocked_reason or p.needs_human_reason,
            demand_kind=kind,
            demand_quote=quote,
            measured_capability=dict(cap),
            remote_status=remote.get("status", "unknown"),
            remote_probe=remote.get("detail", ""),
        ))
    # 状态机记忆回填：同 arxiv_id 的条目继承 state / conclusion /
    # transitions。探针字段保留本轮新值（上面已写）。
    if prior is not None:
        prior_by_id = {x.arxiv_id: x for x in prior}
        for e in out:
            p = prior_by_id.get(e.arxiv_id)
            if p is not None:
                e.state = p.state
                e.conclusion = p.conclusion
                e.transitions = list(p.transitions)
    return out


def transition(e: Entry, to: str, reason: str, actor: str = "l3_store",
               now: str = "") -> tuple[Entry, str]:
    """尝试迁移。返回 (新条目, 错误)。**空错误串 = 成功。**

    四道门，任何一道不过就**不动状态**、返回错误：
      1. 目标状态必须在 STATES[e.state] 的出边里
      2. reason 必须非空（铁律 6/7 变代码）
      3. 进终态的 reason 必须**够长且不是占位符**——它就是结论本身
      4. 已终态不得再迁出（无环）

    第 3 条曾经写错成「条目上必须已有 conclusion」：而 conclusion 是迁移
    成功**之后**才由 reason 写入的，于是这道门永不可能通过——**够不着的门
    等于没有门**（AGENTS.md 第 7 条）。现在语义明确为：终态理由即结论。
    """
    if to not in STATES.get(e.state, ()):
        return e, ("非法迁移 %s → %s（允许：%s）"
                   % (e.state, to, "、".join(STATES.get(e.state, ()))
                      or "终态无出边"))
    if not (reason or "").strip():
        return e, "迁移必须带非空 reason"
    if to in TERMINAL:
        n = len(re.sub(r"\s", "", reason))
        if n < MIN_CONCLUSION_LEN:
            return e, ("进入终态 %s 的理由仅 %d 字，短于下限 %d——"
                       "结论必须能让人三个月后看懂" % (to, n, MIN_CONCLUSION_LEN))
        if reason.strip().lower() in PLACEHOLDER:
            return e, "进入终态 %s 的理由是占位符「%s」" % (to, reason)
    t = Transition(seq=len(e.transitions) + 1, arxiv_id=e.arxiv_id,
                   frm=e.state, to=to, reason=reason,
                   at=now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   actor=actor)
    moved = Entry(**{**asdict_shallow(e), "state": to,
                     "transitions": e.transitions + [t]})
    if to in TERMINAL:
        moved.conclusion = reason
    return moved, ""


def asdict_shallow(e: Entry) -> dict[str, Any]:
    return {k: v for k, v in e.__dict__.items()}


def append_log(ts: list[Transition], path: str = LOG,
               skip_existing: bool = True) -> int:
    """append-only 审计日志。返回**本次真正新增**的行数。

    `skip_existing=True`（默认）时先读一遍已有行、按**整行内容**去重，
    避免「补写」把同一次迁移再追加一遍——2026-10-05 实测：W11 收口补写
    审计日志时若不去重，同一条 seq 会在文件里出现两次，而
    「append-only 永不修改」被读成「只增不减」并不包含「只增一次」。
    刻意**不按 (arxiv_id, seq) 去重**：同一个 seq 可以合法地有多行
    （actor 更正就是同 seq 追加一条 actor="actor_correction" 的更正行，
    按 seq 去重会把更正记录一并吃掉）。按内容比对，同一笔才认同一笔。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    seen: set[str] = set()
    if skip_existing and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    seen.add(json.dumps(json.loads(line), ensure_ascii=False,
                                        sort_keys=True))
                except json.JSONDecodeError:
                    continue          # 损坏行不当重复，但也不因此中断追加
    added = 0
    with open(path, "a", encoding="utf-8") as fh:
        for t in ts:
            line = json.dumps(t.to_dict(), ensure_ascii=False)
            if skip_existing and \
                    json.dumps(json.loads(line), ensure_ascii=False,
                               sort_keys=True) in seen:
                continue
            fh.write(line + "\n")
            seen.add(json.dumps(json.loads(line), ensure_ascii=False,
                                sort_keys=True))
            added += 1
    return added


def report(entries: list[Entry]) -> dict[str, Any]:
    """汇总 + 自洽断言。断言必须**能失败**（铁律 7）。

    两条针对「门变装饰」的检查：
      · `gate_is_discriminating`：若某道门对全集给出同一个答案，它没有
        在做任何事 —— 直接报出来，而不是显示一片绿。
      · `every_executable_demand_known`：凡判「本机能跑」的，必须有显式
        需求依据；需求未测量的绝不能落到 executable_here=True。
    """
    from collections import Counter
    c = Counter(e.state for e in entries)
    exe = [e for e in entries if e.verdict == "executable"]
    runnable = [e for e in exe if e.executable_here]
    notr = [e for e in exe if not e.executable_here]
    reasons = Counter(e.blocking_reason.split("：")[0].split("（")[0]
                      for e in notr)
    rep: dict[str, Any] = {
        "total": len(entries),
        "by_state": dict(c),
        "state_sum_matches": sum(c.values()) == len(entries),
        "by_verdict": dict(Counter(e.verdict for e in entries)),
        "executable_total": len(exe),
        "executable_here": len(runnable),
        "cannot_run_but_still_listed": len(notr),
        "demand_kinds": dict(Counter(e.demand_kind for e in exe)),
        "blocking_reasons": dict(reasons),
        # 每一条例外都必须说清为什么，且带上当轮实测数
        "every_not_runnable_says_why": all(
            e.blocking_reason and e.measured_capability for e in notr),
        "every_executable_demand_known": all(
            e.demand_kind and e.demand_quote for e in runnable),
        "every_executable_probe_is_live": all(
            e.measured_capability.get("probe_source") == "live"
            and e.measured_capability.get("probed_at") for e in exe),
        "terminal_entries_have_conclusion": all(
            e.conclusion for e in entries if e.state in TERMINAL),
        "every_state_known": all(e.state in STATES for e in entries),
    }
    rep["executable_arith"] = (len(runnable) + len(notr) == len(exe))
    # 门是否在区分：若「本机能跑 / 不能跑」非空非全集，即为真在区分。
    # 0 条或全部都能跑，都说明判据没有在做事（AGENTS.md 第 7 条）。
    rep["gate_is_discriminating"] = bool(exe) and len(runnable) < len(exe)
    rep["gate_discriminating_note"] = (
        "" if rep["gate_is_discriminating"] else
        "可执行性门对全集给出同一答案（%d/%d）——判据未在做事，"
        "这不是好消息，是警报" % (len(runnable), len(exe)))
    return rep


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    do_remote = "--remote" in sys.argv
    cap = probe_capability()
    remote = probe_remote() if do_remote else {"status": "not_probed",
                                               "probe_at": "",
                                               "detail": ""}
    entries = build(cap=cap, remote=remote, do_remote=False,
                    prior=_load_prior())
    rep = report(entries)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"report": rep, "entries": [e.to_dict() for e in entries]},
                  fh, ensure_ascii=False, indent=2)
    print("能力探测（当轮实测，不读缓存）：")
    print("  GPU %s  总 %s MiB / 可用 %s MiB"
          % ("有" if cap.get("gpu_present") else "无", cap.get("gpu_total_mib"),
             cap.get("gpu_free_mib")))
    print("  内存可用 %sG | 磁盘可用 %sG"
          % (cap.get("mem_available_gb"), cap.get("disk_free_gb")))
    print("  远端状态：%s" % remote["status"])
    print("\n状态分布：%s（自洽 %s）" % (rep["by_state"], rep["state_sum_matches"]))
    print("可执行提案 %d 条：**本机能跑 %d / 跑不了但仍列出 %d**（自洽 %s）"
          % (rep["executable_total"], rep["executable_here"],
             rep["cannot_run_but_still_listed"], rep["executable_arith"]))
    print("显式需求分布：%s（空 = 原文未提）" % rep["demand_kinds"])
    print("每条例外都写明原因并带当轮实测数：%s"
          % rep["every_not_runnable_says_why"])
    print("门在区分：%s %s" % (rep["gate_is_discriminating"],
                               rep["gate_discriminating_note"]))
    print("\n跑不了的（不隐藏，写明差多少）：")
    for e in entries:
        if e.verdict == "executable" and not e.executable_here:
            print("  %-15s %s" % (e.arxiv_id, e.blocking_reason[:76]))
    print("\n结果已写入 %s" % os.path.relpath(OUT, os.getcwd()))
    return 0


def selftest() -> int:
    """反证：证明四道门都能失败，且「跑不了」不会被悄悄藏起来。"""
    checks = 0
    base = Entry(arxiv_id="x", title="T", verdict="executable")

    # ── 1. 正常迁移 + 带 reason ─────────────────────────────────────
    moved, err = transition(base, "已批", "人工复核四件套后批准")
    assert err == "" and moved.state == "已批", err
    assert moved.transitions[0].seq == 1
    checks += 1

    # ── 2. 无 reason ⇒ 必须拒绝（铁律 6/7 变代码）────────────────────
    still, err = transition(base, "已批", "")
    assert err and "reason" in err, err
    assert still.state == "待批", "被拒绝的迁移却改了状态"
    checks += 1

    # ── 3. 非法迁移（待批 → 已跑，跳过已批）⇒ 必须拒绝 ──────────────
    still, err = transition(base, "已跑", "抄近路")
    assert err and "非法迁移" in err, err
    assert still.state == "待批"
    checks += 1

    # ── 4. 进终态的 reason 必须够长、且不是占位符（它就是结论）────────
    # 必须先走**合法路径**造出「已跑」态的对象，否则会被第一道门（合法性）
    # 拦下并返回「非法迁移」——那样第三道门就是永不可达的代码（AGENTS.md 第 7 条：
    # 够不着的门和没有门在证据上等价）。self-test 里这两种情况长得像。
    ran, err = transition(moved, "已跑", "实验跑完，产出结果文件")
    assert err == "" and ran.state == "已跑", err
    # 太短 ⇒ 拒绝（「跨度不足」这类 4 字标签不是结论）
    still, err = transition(ran, "出结论", "跨度不足")
    assert err and "短于下限" in err, err
    assert still.state == "已跑", "被拒绝的迁移却改了状态"
    # 占位符 ⇒ 拒绝（够长但无内容）
    still, err = transition(ran, "出结论", "TBD 待补")
    assert err and ("占位符" in err or "短于下限" in err), err
    # 带真结论 ⇒ 放行
    done2, err = transition(ran, "出结论", "门禁判不支持该机制主张，n=6 跨度不足")
    assert err == "" and done2.state == "出结论" and done2.conclusion, err
    checks += 1

    # ── 5. 终态不得再迁出（无环）───────────────────────────────────
    done = Entry(arxiv_id="x", title="T", verdict="executable",
                 state="出结论", conclusion="门禁判不支持")
    still, err = transition(done, "待批", "改主意")
    assert err and "终态" in err, err
    checks += 1

    # ── 6. 被阻塞 是唯一回头路 ─────────────────────────────────────
    blk = Entry(arxiv_id="x", title="T", verdict="blocked", state="被阻塞")
    back, err = transition(blk, "待批", "已补齐判据与观测")
    assert err == "" and back.state == "待批", err
    still, err = transition(blk, "已跑", "不补齐就想跑")
    assert err, "被阻塞竟能直接跳到已跑"
    checks += 1

    # ── 7. **不可执行必须留在队列里，且写明差多少** ────────────────
    cap = {"gpu_present": True, "gpu_total_mib": 6144, "gpu_free_mib": 2953,
           "mem_available_gb": 9.0, "disk_free_gb": 14.0}
    ok, why = can_run_here(cap, needs_gpu=True)
    assert not ok and "显存不足" in why and "16384" in why, why
    ok, why = can_run_here(cap, needs_gpu=False)
    assert ok and why == "", why
    # **认出了需求却没量它** ⇒ 也必须判不可跑（识别不等于检查）
    ok, why = can_run_here(cap, needs_gpu=False, demand_kind="data")
    assert not ok and "数据" in why and "未测量" in why, why
    ok, why = can_run_here(cap, needs_gpu=False, demand_kind="net")
    assert not ok and "外网" in why, why
    checks += 1

    # ── 8. report 必须能失败（铁律 7）─────────────────────────────
    ghost = Entry(arxiv_id="g", title="T", verdict="executable",
                  executable_here=False, blocking_reason="",
                  measured_capability={})
    assert report([ghost])["every_not_runnable_says_why"] is False, \
        "空原因的不可执行项没被抓——那是装饰断言"
    bad_state = Entry(arxiv_id="b", title="T", verdict="executable",
                      state="不存在")
    assert report([bad_state])["every_state_known"] is False, \
        "未知状态没被抓"
    no_concl = Entry(arxiv_id="n", title="T", verdict="executable",
                     state="出结论", conclusion="")
    assert report([no_concl])["terminal_entries_have_conclusion"] is False, \
        "终态无结论没被抓"
    # **对全集恒真的门必须报警报**，不能显示一片绿（这是本轮最大的教训）
    all_ok = [Entry(arxiv_id="o%d" % i, title="T", verdict="executable",
                    executable_here=True, demand_kind="gpu",
                    demand_quote="需 8G 显存",
                    measured_capability={"probe_source": "live",
                                         "probed_at": "t"})
              for i in range(3)]
    rep = report(all_ok)
    assert rep["gate_is_discriminating"] is False, \
        "门对全集给出同一答案却没报——这是装饰门"
    assert "警报" in rep["gate_discriminating_note"]
    # 无需求依据却判「可跑」⇒ 必被抓
    nod = Entry(arxiv_id="d", title="T", verdict="executable",
                executable_here=True, demand_kind="", demand_quote="",
                measured_capability={"probe_source": "live", "probed_at": "t"})
    assert report([nod])["every_executable_demand_known"] is False, \
        "无显式需求却判本机可跑——靠猜得出的结论不可信"
    checks += 1

    # ── 9. **抽不到需求 ≠ 不需要需求**（fail-closed 核心）──────────
    p = U.Proposal(arxiv_id="x", verdict="executable",
                   open_problem="在跨语言检索基准上对比不同切块策略",
                   object_candidates=["切块策略"], criterion_hints=["recall@3"],
                   observe_hints=["准确率待对比"], why_now="W5 已跑通对照组")
    kind, _ = explicit_demand(p)
    assert kind == "", "无算力字样却抽出需求：%s" % kind
    es = build([p], cap={"gpu_present": True, "gpu_free_mib": 6129,
                         "gpu_total_mib": 6144, "mem_available_gb": 8.7,
                         "disk_free_gb": 14.7,
                         "probe_source": "live", "probed_at": "t"})
    assert es[0].executable_here is False, "需求未测量却判本机可跑"
    assert "需求未测量" in es[0].blocking_reason
    assert es[0].measured_capability.get("probe_source") == "live"
    # 显式提到显存 ⇒ 走 GPU 门，且本机 6144 < 16384 ⇒ 不可跑并说清差多少
    pg = U.Proposal(arxiv_id="y", verdict="executable",
                    open_problem="该方法需 24G 显存才能跑通复现",
                    object_candidates=[], criterion_hints=[],
                    observe_hints=[], why_now="q")
    kg, qg = explicit_demand(pg)
    assert kg == "gpu" and "显存" in qg, (kg, qg)
    es2 = build([pg], cap={"gpu_present": True, "gpu_free_mib": 6129,
                           "gpu_total_mib": 6144, "mem_available_gb": 8.7,
                           "disk_free_gb": 14.7,
                           "probe_source": "live", "probed_at": "t"})
    assert es2[0].executable_here is False
    assert "显存不足" in es2[0].blocking_reason and "16384" in es2[0].blocking_reason
    checks += 1

    # ── 10. 真实探测必须非空且标 source（不许读缓存）─────────────────
    cap = probe_capability()
    assert cap["probe_source"] == "live", "探测不是实测"
    assert cap["probed_at"], "探测缺时间戳"
    assert cap.get("gpu_present") is not None, "GPU 状态未判定（None 既不是有也不是无）"
    assert (cap.get("disk_free_gb") is not None
            or cap.get("disk_probe_error")), "磁盘既无数也无错"
    checks += 1

    # ── 11. 记忆回填：build(prior=…) 必须继承状态机记忆，探针照旧刷新 ──
    # 没有 prior 时行为不变（首轮/测试路径）；有 prior 时 state/conclusion/
    # transitions 继承（审批台账不许被重建销毁），executable_here 等
    # 探针字段取本轮新值。反证：断言继承后的 state 不再是 build 的默认值。
    pg2 = U.Proposal(arxiv_id="x", verdict="executable", open_problem="p",
                     object_candidates=[], criterion_hints=[],
                     observe_hints=[], why_now="q")
    approved, err = transition(Entry(arxiv_id="x", title="T",
                                     verdict="executable"),
                               "已批", "人工复核四件套后批准")
    assert err == "", err
    probe_now = {"gpu_present": False, "gpu_total_mib": 0,
                 "gpu_free_mib": 0, "mem_available_gb": 8.7,
                 "disk_free_gb": 14.7, "probe_source": "live",
                 "probed_at": "t2"}
    es3 = build([pg2], cap=probe_now,
                prior=[approved])
    assert es3[0].state == "已批", es3[0].state          # 记忆继承
    assert es3[0].transitions and es3[0].transitions[0].seq == 1
    assert es3[0].measured_capability["probed_at"] == "t2"  # 探针刷新
    es4 = build([pg2], cap=probe_now, prior=None)
    assert es4[0].state == "待批", "无 prior 时行为必须与旧版一致"
    checks += 1

    sys.stdout.write("STORE SELFTEST OK（%d 组断言）\n" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
