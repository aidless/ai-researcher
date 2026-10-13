#!/usr/bin/env python3
"""把 2107.03374v2 从「被阻塞」迁到「已批」——两跳，走状态机不手改。

## 为什么是这条提案（自主决策的依据，见 store/w10_criteria.json）

41 条被阻塞提案经 w10_criteria_fill.py 回原论文核对后 22 条 measurable。
在其中，本机**真能跑通端到端闭环**的只有这一条：

  · 数据可得且已实测：HumanEval.jsonl.gz 从
    raw.githubusercontent.com/openai/human-eval/master/data/ 实测 206/200，
    44,877 字节，解出 164 条、字段 {task_id, prompt, entry_point, test,
    canonical_solution}（2026-10-04 23:44 实测，非凭记忆）
  · 判据明确且逐字可追：2107.03374v2 Table 1（2026-10-04 23:46 抓
    arxiv.org/html/2107.03374v2 提取）pass@1 锚 GPT-J 6B 11.62%、
    Codex-12B 28.81%、GPT-Neo 2.7B 6.41%；文中另有 Codex 复现段
    "GPT-3 solves 0% and GPT-J solves 11.4%"（自洽交叉核对）
  · 指标可算：pass@1 = 一题一采样过全部单元测试；判据函数 check(candidate)
    在数据里逐条给出；本机 CPU 子进程可执行（与 W8 同一沙箱路径）
  · 与已有线不重复：W7/W8 是自然语言算术（GSM8K），W9 是相关性判官；
    这是第一条**代码生成 + 单元测试执行**的闭环

## 为什么必须两跳

STATES 状态图（store.py:75）里 `被阻塞` 的**唯一出边是「待批」**，没有直达
「已批」的边。手改 JSON 会绕过状态机，等于把门变装饰。所以：
  被阻塞 ──补齐判据+数据可达（带证据）──→ 待批 ──本机可跑（带证据）──→ 已批

## 它绝不做什么

1. 不改判据/观测/对象以外的任何字段；blocking_reason 留在条目上作为历史
2. 不改 verdict（仍 blocked）——verdict 是「需求是否可执行」的测量结论，
   批的是「这条实验值得跑」，两者不是一回事
3. 不碰其他 40 条提案
4. 不自动跑批：已批之后仍需人工/agent 显式运行 w11 脚本

## 用法

    python3 scripts/w11_approve_humaneval.py --selftest
    python3 scripts/w11_approve_humaneval.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "ai-researcher", "store")
STATE_PATH = os.path.join(STORE, "proposals_state.json")
TARGET_ID = "2107.03374v2"

# 第一跳：补齐判据（逐字可追的锚 + 实测数据可达）
REASON_FILL = (
    "判据回填（2026-10-04，回原论文核对）：2107.03374v2 Table 1（抓 "
    "arxiv.org/html/2107.03374v2，正文 Table 1 段逐字提取）给出 HumanEval "
    "pass@1 锚——GPT-J 6B 11.62%、Codex-12B 28.81%、GPT-Neo 2.7B 6.41%、"
    "GPT-Neo 125M 0.75%，共 164 题、平均每题 7.7 个单元测试；摘要段"
    "「GPT-3 solves 0% and GPT-J solves 11.4%」与表内 11.62 自洽。"
    "判据可算：一题一采样、候选程序须通过数据自带 check(candidate) 的"
    "全部单元测试，pass@1 = 通过题数 / 164。数据实测可达："
    "raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz "
    "HTTP 206、44,877 字节，gunzip 后 164 行，字段 task_id/prompt/entry_point/"
    "test/canonical_solution 齐备（2026-10-04 23:44 实测）。"
    "本条从此不再是「缺判据/缺观测/缺对象」。")

# 第二跳：本机可跑（能力测量 + 执行路径已验证）
REASON_APPROVE = (
    "本机可跑（2026-10-04 测量）：Qwen3-0.6B 本地快照在 "
    "~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/w6probe/，"
    "W7/W8/W9 三条闭环已逐字复用该栈（bf16 + CPU 贪心 + chat template + "
    "enable_thinking=False）跑通；候选程序用 W8 同一条沙箱路径 "
    "[python, -I, -S, tmpfile] 子进程执行并设超时，无需 GPU。"
    "口径钉死：pass@1（每题单采样、贪心），164 题全量，分母=164，"
    "与 Codex 表 1 的 k=1 列同口径；模型/来源不同 ⇒ 差距是**量级测量**"
    "非受控比较。批准执行 W11 闭环，产物须含逐题落盘与独立重算。")

BACKUP_SUFFIX = ".bak-before-w11-approve"

# store.report() 的自洽断言键。**逐条列全**——用 .get() 逐个探，
# 探不到就是 None，而 None 不是「通过」。旧写法回一个
# rep.get("integrity_ok")，而 report() 从不产这个键，于是迁移脚本
# 永远报 report_self_ok: null，没人看出它其实什么都没验。
GATE_KEYS = (
    "state_sum_matches", "every_state_known", "every_not_runnable_says_why",
    "every_executable_demand_known", "every_executable_probe_is_live",
    "terminal_entries_have_conclusion", "executable_arith",
    "gate_is_discriminating",
)


def load(path: str = STATE_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_entry(d: dict, aid: str = TARGET_ID) -> dict:
    for e in d["entries"]:
        if e["arxiv_id"] == aid:
            return e
    raise KeyError(f"状态机里找不到 {aid}")


def _mk_entry(d: dict, e: dict) -> "object":
    """把 JSON 条目还原成 store.Entry（含 transitions）。"""
    sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
    from ai_researcher import store as st
    return st.Entry(**{k: v for k, v in e.items() if k != "transitions"},
                    transitions=[st.Transition(**t) for t in e.get("transitions", [])])


def _dump_entry(entry: "object") -> dict:
    sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
    from ai_researcher import store as st
    d = st.asdict_shallow(entry)
    d["transitions"] = [t.to_dict() for t in entry.transitions]
    return d


def approve(dry_run: bool = False, state_path: str = STATE_PATH) -> dict:
    sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
    from ai_researcher import store as st
    d = load(state_path)
    e = find_entry(d)
    if e["state"] == "已批":
        return {"changed": False, "why": "已是已批，幂等"}
    steps = []
    cur = _mk_entry(d, e)
    if cur.state == "被阻塞":
        cur, err = st.transition(cur, "待批", REASON_FILL, actor="l5_agent",
                                 now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        if err:
            return {"changed": False, "why": f"第一跳失败：{err}"}
        steps.append(("被阻塞", "待批"))
    if cur.state == "待批":
        cur, err = st.transition(cur, "已批", REASON_APPROVE, actor="l5_agent",
                                 now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        if err:
            return {"changed": False, "why": f"第二跳失败：{err}"}
        steps.append(("待批", "已批"))
    if cur.state != "已批":
        return {"changed": False, "why": f"迁移后状态异常：{cur.state}"}
    if dry_run:
        return {"changed": False, "why": "dry-run：未落盘", "steps": steps,
                "final": cur.state}
    if not os.path.exists(state_path + BACKUP_SUFFIX):
        with open(state_path + BACKUP_SUFFIX, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
    for i, entry in enumerate(d["entries"]):
        if entry["arxiv_id"] == TARGET_ID:
            d["entries"][i] = _dump_entry(cur)
            break
    rep = st.report([_mk_entry(d, x) for x in d["entries"]])
    d["report"] = rep
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
    st.append_log(cur.transitions, os.path.join(STORE, "transitions.jsonl"))
    # 自洽断言必须**逐条**回报，而不是回一个不存在的键：store.report()
    # 从不产出 integrity_ok，读 .get("integrity_ok") 只会静默拿到 None
    # ——「空值不是通过」（曾真这么写过一次）。
    gates = {k: rep[k] for k in GATE_KEYS}
    return {"changed": True, "steps": steps, "final": cur.state,
            "report_gates": gates,
            "report_all_gates_ok": all(gates.values())}


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # 状态图约束：被阻塞 不能直达 已批（否则两跳设计无意义）
    sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
    from ai_researcher import store as st
    ck("被阻塞无直达已批的边", "已批" in st.STATES.get("被阻塞", ()), False)
    ck("被阻塞唯一出边是待批", list(st.STATES["被阻塞"]), ["待批"])

    # 迁移必须 fail-closed：跳级被拒
    blk = st.Entry(arxiv_id="x", title="T", verdict="blocked", state="被阻塞")
    _, err = st.transition(blk, "已批", REASON_APPROVE, actor="test")
    ck("被阻塞直达已批被拒", bool(err), True)

    # 两跳能走通。conclusion **只在终态写入**（store.transition 里
    # `if to in TERMINAL: moved.conclusion = reason`），已批不是终态，
    # 所以这里必须为空——曾把断言写成「结论即第二跳理由」而恒假。
    ck("已批不是终态", "已批" in st.TERMINAL, False)
    cur, err = st.transition(blk, "待批", REASON_FILL, actor="test")
    ck("第一跳成功", err, "")
    ck("第一跳后状态", cur.state, "待批")
    cur, err = st.transition(cur, "已批", REASON_APPROVE, actor="test")
    ck("第二跳成功", err, "")
    ck("第二跳后状态", cur.state, "已批")
    ck("非终态不写 conclusion", cur.conclusion, "")
    ck("两条迁移留痕", len(cur.transitions), 2)

    # 反证：只有进终态才写 conclusion（同一 reason，非终态空、终态非空）
    ran, err = st.transition(cur, "已跑", "已跑：本机 164 题 pass@1 全部跑完", actor="test")
    ck("已批→已跑成功", err, "")
    ck("已跑仍不写 conclusion", ran.conclusion, "")
    concl_reason = "结论：pass@1 全量跑完，0.6B 在本机量级低于表中最小锚"
    done, err = st.transition(ran, "出结论", concl_reason, actor="test")
    ck("已跑→出结论成功", err, "")
    ck("终态才写 conclusion", done.conclusion, concl_reason)
    ck("终态无出边", list(st.STATES["出结论"]), [])
    _, err = st.transition(done, "已跑", "试图改主意", actor="test")
    ck("终态不可迁出", bool(err), True)
    # 反证：终态理由太短必须被拒（够不着的门等于没门）
    short = st.Entry(arxiv_id="y", title="T", verdict="blocked", state="已跑")
    _, err = st.transition(short, "出结论", "无差异", actor="test")
    ck("终态短理由被拒", bool(err), True)

    # 幂等：已批再批不报错不重复迁移
    cur2, err2 = st.transition(cur, "已批", REASON_APPROVE, actor="test")
    ck("已批再批被拒（无自环）", bool(err2), True)

    # dry-run 不落盘。**对备份文件**跑，而不是当前库——当前库已经迁移到
    # 已批 了，拿它测 dry-run 只会测出「幂等」，测不到 dry-run 那条路。
    pre = STATE_PATH + BACKUP_SUFFIX
    if os.path.exists(pre):
        before = os.path.getmtime(pre)
        r = approve(dry_run=True, state_path=pre)
        ck("dry-run 不落盘", os.path.getmtime(pre), before)
        ck("dry-run 报未落盘", r.get("why"), "dry-run：未落盘")
        ck("dry-run 仍算出两跳", [s[1] for s in r.get("steps", [])], ["待批", "已批"])
        ck("dry-run 不改 changed", r.get("changed"), False)
        ck("备份里仍是迁移前状态", find_entry(load(pre))["state"], "被阻塞")
    else:
        ck("迁移前备份存在", pre, "存在")

    # GATE_KEYS 必须**真实存在于** store.report() 的输出里。旧代码回
    # rep.get("integrity_ok")——report() 从不产这个键，于是永远得到 None，
    # 而 None 在「全为真才算过」的聚合里等同「没验」。这里把键集合钉死。
    d = load()
    rep_real = st.report([_mk_entry(d, x) for x in d["entries"]])
    ck("GATE_KEYS 全是 report() 的布尔键",
       sorted(GATE_KEYS),
       sorted(k for k, v in rep_real.items() if isinstance(v, bool)))
    ck("现库全部门通过", all(rep_real[k] for k in GATE_KEYS), True)

    # 反证：注入一条「终态但无结论」的条目，`terminal_entries_have_conclusion`
    # 必须翻成 False —— 否则这道门是装饰。
    broken = _mk_entry(d, find_entry(d))
    broken.state = "出结论"
    broken.conclusion = ""
    rep_bad = st.report([broken])
    ck("注入违规后该门翻假", rep_bad["terminal_entries_have_conclusion"], False)

    # 目标条目在状态机里，且状态已知
    e = find_entry(d)
    ck("目标存在", e["arxiv_id"], TARGET_ID)
    ck("目标状态已知", e["state"] in st.STATES, True)
    # 迁移幂等：已批再跑一次不重复迁移、不报错
    if e["state"] == "已批":
        again = approve()
        ck("再跑一次是幂等的", again.get("why"), "已是已批，幂等")

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    r = approve(dry_run="--dry-run" in sys.argv)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("changed") or r.get("why") == "已是已批，幂等" else 1


if __name__ == "__main__":
    sys.exit(main())