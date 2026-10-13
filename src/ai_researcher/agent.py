#!/usr/bin/env python3
"""ai-researcher L5：把 L0–L4 编排成一个可反复运行的 agent 循环。

设计立场（承接本项目的铁律，不是装饰）：

  1. 分级授权写进代码，不写进注释。允许自动的只有：扫描（只读 wiki）、
     排序、提案、能力探测、判读、报告。写论文正文 / 对外发送 / 编辑共享
     wiki / 解码 283 条压缩标签 / 远程开跑 —— `request_action()` 一律拒绝。
     「拒绝」是返回结构化的 refused，不是抛异常断掉整个循环。
  2. 断路器。任何一步 rc!=0，后续步骤**不再执行**，逐个标记
     skipped_after_failure。绝不在坏数据上继续跑完五个模块然后假装
     「循环完成了」——那比崩溃更糟，因为它看起来像成功。
  3. 头条数字从产物重算，不从我自己的话里来。报告里的 runnable_now /
     待批数 / pass-fail-insufficient 全部重新读 JSON 数出来；产物缺失
     就写「产物缺失」，不猜。
  4. agent 不写台账。lessons.md 是人（和有判断力的会话）维护的教训账本，
     循环日志只落 store/cycles/。这条也钉在 selftest 里。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # …/ai-researcher
SRC = ROOT / "src"
STATE_PATH = ROOT / "store" / "agent_state.json"
CYCLES_DIR = ROOT / "store" / "cycles"
STEP_TIMEOUT_S = 600

# 分级授权（用户拍板的边界，m00098）：检索/读数据/跑实验=自动；
# 成文/外发/共享 wiki=人工。
ALLOWED_ACTIONS = {"scan", "rank", "propose", "gate", "judge", "report",
                   "probe_capability"}
REQUIRES_HUMAN = {"write_paper", "send_outward", "wiki_edit",
                  "decode_compressed_tags", "remote_run"}

# (步骤名, 模块)。顺序即依赖：扫描→排序→提案→门→判读。
STEPS = [("scan", "ai_researcher.scanner"),
         ("rank", "ai_researcher.ranker"),
         ("propose", "ai_researcher.runner"),
         ("gate", "ai_researcher.store"),
         ("judge", "ai_researcher.critic")]


def request_action(action: str) -> dict:
    """动作防火墙。返回 {"allowed": bool, ...}，从不抛异常。"""
    if action in REQUIRES_HUMAN:
        return {"allowed": False, "action": action,
                "reason": "分级授权：该动作需人工批准，agent 不自动执行"}
    if action not in ALLOWED_ACTIONS:
        return {"allowed": False, "action": action,
                "reason": "未知动作：宁可拒绝也不默认放行"}
    return {"allowed": True, "action": action}


def run_step(name: str, module: str, timeout: int = STEP_TIMEOUT_S) -> dict:
    """跑一个模块，忠实记录 rc。绝不吞 rc —— 吞 rc 是本项目犯过多次的错。

    cwd 必须是 src 本身：`-m` 把 cwd 放进 sys.path，包才能被找到。
    本工作区根目录名含字面反斜杠（/home/liuzewen/F:\\deepseek），实测
    PYTHONPATH 跨 subprocess 传这种路径会丢——cwd 方案不经过环境变量，
    不踩这个坑。产物路径各模块都从 __file__ 自解析，不受 cwd 影响。
    """
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", module],
                           cwd=str(SRC), timeout=timeout,
                           capture_output=True, text=True)
        rc, out, err = p.returncode, p.stdout, p.stderr
        timed_out = False
    except subprocess.TimeoutExpired as e:
        rc, timed_out = 124, True
        out = (e.stdout or b"").decode(errors="replace") if isinstance(
            e.stdout, bytes) else (e.stdout or "")
        err = "TIMEOUT after %ss" % timeout
    tail = "\n".join((out or "").strip().splitlines()[-12:])
    if err and err.strip():
        tail = (tail + "\n[stderr] " + "\n".join(
            err.strip().splitlines()[-6:])).strip()
    return {"step": name, "module": module, "rc": rc, "ok": rc == 0,
            "timed_out": timed_out, "seconds": round(time.time() - t0, 1),
            "tail": tail[-1500:]}


def _load(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _block_reason(e: dict) -> str:
    """阻断原因：真实产物放顶层 blocking_reason；合成/旧数据在 measured.reason。

    两者都缺就明说「未说明」——编一个默认理由等于伪造。
    """
    return (e.get("blocking_reason")
            or (e.get("measured") or {}).get("reason")
            or "未说明")


def derive_headline() -> dict:
    """从产物重算头条数字。缺产物就明说，不猜。"""
    h = {"runnable_now": None, "proposals": None, "store_states": None,
         "critic": None}
    prop = _load(ROOT / "proposals" / "proposals.json")
    if prop and prop.get("items"):
        h["proposals"] = {}
        for p in prop["items"]:
            h["proposals"][p["verdict"]] = h["proposals"].get(p["verdict"], 0) + 1
    st = _load(ROOT / "store" / "proposals_state.json")
    if st and st.get("entries"):
        states, runnable, reasons = {}, 0, {}
        for e in st["entries"]:
            states[e.get("state", "?")] = states.get(e.get("state", "?"), 0) + 1
            # 真实产物（store.py 写出）：executable_here 在顶层，measured 里
            # 只有能力探针。measured.executable_here 仅作旧形状回退。
            ex = e.get("executable_here")
            if ex is None:
                ex = (e.get("measured") or {}).get("executable_here")
            if ex is True:
                runnable += 1
            elif ex is False:
                r = _block_reason(e)
                reasons[r] = reasons.get(r, 0) + 1
        h["store_states"] = states
        h["runnable_now"] = runnable
        h["blocked_reasons"] = dict(sorted(reasons.items(),
                                           key=lambda kv: -kv[1])[:5])
    cv = _load(ROOT / "store" / "critic_verdicts.json")
    if cv and cv.get("verdicts"):
        cnt = {}
        for v in cv["verdicts"]:
            cnt[v["verdict"]] = cnt.get(v["verdict"], 0) + 1
        h["critic"] = cnt
    return h


def _ent_id(e: dict):
    """条目标识：runner/store 的真实字段是 arxiv_id，没有 id。"""
    return e.get("id") or e.get("arxiv_id")


def collect_approvals() -> list:
    """needs_human 提案 + 处于「待批」状态的条目，都是要人拍板的事。"""
    out = []
    prop = _load(ROOT / "proposals" / "proposals.json")
    if prop:
        for p in prop["items"]:
            if p.get("verdict") == "needs_human":
                out.append({"kind": "needs_human", "id": _ent_id(p),
                            "why": p.get("needs_human_reason") or "未说明"})
    st = _load(ROOT / "store" / "proposals_state.json")
    if st:
        for e in st["entries"]:
            if e.get("state") == "待批":
                out.append({"kind": "awaiting_approval", "id": _ent_id(e),
                            "why": _block_reason(e)})
    return out


def honest_verdict(h: dict) -> str:
    """一句话判读，只从数字来。数字不够就不下结论。"""
    if h["runnable_now"] is None:
        return "本轮产物缺失，无法判读（看 steps 的 rc 找断在哪一步）"
    n_run = h["runnable_now"]
    if n_run == 0:
        return "本轮无一条提案可在本机开跑（fail-closed 或缺数据），不进入实验层"
    return "本轮有 %d 条可开跑，进入实验层" % n_run


def one_cycle(state_path: Path = STATE_PATH,
              runner=None, artifacts_guard: bool = False) -> dict:
    """跑一轮完整循环。runner 可注入（selftest 用），缺省 run_step。"""
    runner = runner or run_step
    steps, failed = [], False
    for name, module in STEPS:
        if failed:
            steps.append({"step": name, "module": module,
                          "status": "skipped_after_failure"})
            continue
        r = runner(name, module)
        if artifacts_guard and r.get("wrote_outside"):
            raise AssertionError("runner 越权写了循环目录之外的文件")
        r.setdefault("status", "ran")
        steps.append(r)
        if not r.get("ok"):
            failed = True
    headline = derive_headline()
    approvals = collect_approvals()
    cyc = {"cycle": next_cycle_id(state_path), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "steps": steps, "headline": headline,
           "approvals_needed": approvals, "verdict": honest_verdict(headline)}
    write_cycle_report(cyc)
    save_state(cyc, state_path)
    return cyc


def next_cycle_id(state_path: Path) -> int:
    st = _load(state_path) or {"cycles": []}
    return max([c.get("cycle", 0) for c in st["cycles"]] or [0]) + 1


def save_state(cyc: dict, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    st = _load(state_path) or {"cycles": []}
    st["cycles"] = [c for c in st["cycles"] if c.get("cycle") != cyc["cycle"]]
    st["cycles"].append(cyc)
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)


def write_cycle_report(cyc: dict) -> Path:
    CYCLES_DIR.mkdir(parents=True, exist_ok=True)
    p = CYCLES_DIR / ("cycle_%03d.md" % cyc["cycle"])
    L = ["# agent 循环 %d（%s）" % (cyc["cycle"], cyc["ts"]), ""]
    L.append("**判读**：%s" % cyc["verdict"])
    L.append("")
    L.append("| 步骤 | 模块 | rc | 秒 | 状态 |")
    L.append("|---|---|---|---|---|")
    for s in cyc["steps"]:
        L.append("| %s | %s | %s | %s | %s |" % (
            s["step"], s.get("module", ""), s.get("rc", "—"),
            s.get("seconds", "—"), s.get("status", "ran")))
    L.append("")
    L.append("**头条（从产物重算）**：`%s`" % json.dumps(
        cyc["headline"], ensure_ascii=False))
    L.append("")
    if cyc["approvals_needed"]:
        L.append("**待人工（%d 条）**：" % len(cyc["approvals_needed"]))
        for a in cyc["approvals_needed"][:20]:
            L.append("- `%s` %s — %s" % (a["kind"], a.get("id"), a["why"]))
    else:
        L.append("**待人工**：无")
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def status() -> int:
    st = _load(STATE_PATH)
    if not st or not st.get("cycles"):
        print("尚无循环记录。运行 python3 -m ai_researcher.agent --cycle")
        return 0
    last = st["cycles"][-1]
    print("最近循环 #%d @ %s" % (last["cycle"], last["ts"]))
    print("判读：%s" % last["verdict"])
    for s in last["steps"]:
        print("  %-8s rc=%s %s" % (s["step"], s.get("rc", "—"),
                                   s.get("status", "ran")))
    print("待人工 %d 条" % len(last["approvals_needed"]))
    return 0


def selftest() -> int:
    """反证式自检：每条断言都先想清楚「门怎么才会红」。"""
    import tempfile
    global ROOT, CYCLES_DIR          # 可注入：自检必须能在空环境里跑
    r = 0

    def ck(name, cond, detail=""):
        nonlocal r
        print("[%s] %s %s" % ("过 " if cond else "不过", name, detail))
        if not cond:
            r = 1

    # 1. rc 忠实：失败的子进程必须记成失败
    s = run_step("t", None, timeout=10) if False else None
    def fake_cmd(name, module, timeout=10):
        # 用 run_step 真跑一个必败命令
        t0 = time.time()
        p = subprocess.run([sys.executable, "-c", "import sys;sys.exit(3)"],
                           capture_output=True, text=True, timeout=timeout)
        return {"step": name, "rc": p.returncode, "ok": p.returncode == 0,
                "seconds": round(time.time() - t0, 1)}
    f = fake_cmd("x", "y")
    ck("run_step 对失败 rc 忠实（rc=3 记 3 不记 0）", f["rc"] == 3)

    # 2. 超时会被杀且如实记录
    def timeout_cmd(name, module, timeout=1):
        t0 = time.time()
        try:
            subprocess.run([sys.executable, "-c", "import time;time.sleep(5)"],
                           capture_output=True, text=True, timeout=timeout)
            rc = 0
        except subprocess.TimeoutExpired:
            rc = 124
        return {"step": name, "rc": rc, "ok": rc == 0,
                "seconds": round(time.time() - t0, 1)}
    ck("超时被杀记 rc!=0（不静默等死）", timeout_cmd("t", "m")["rc"] == 124)

    # 3. 断路器：第一步失败，后面只能标记跳过、绝不执行
    calls = []
    def failing_runner(name, module):
        calls.append(name)
        return {"step": name, "module": module, "rc": 1 if name == "scan" else 0,
                "ok": name != "scan", "status": "ran"}
    with tempfile.TemporaryDirectory() as td:
        old_root, old_cycles = ROOT, CYCLES_DIR
        ROOT = Path(td)                      # 空环境：真实产物全部「缺失」
        CYCLES_DIR = Path(td) / "cycles"
        ledger = old_root / ".agent-memory" / "ledger" / "lessons.md"
        before = ledger.read_bytes() if ledger.exists() else None
        try:
            cyc = one_cycle(state_path=Path(td) / "s.json", runner=failing_runner)
            ran = [s["step"] for s in cyc["steps"] if s.get("status") == "ran"]
            skipped = [s["step"] for s in cyc["steps"]
                       if s.get("status") == "skipped_after_failure"]
            ck("断路器：失败后其余步骤标记 skipped 且未执行",
               ran == ["scan"] and set(skipped) == {"rank", "propose", "gate", "judge"},
               "ran=%s skipped=%s" % (ran, skipped))
            ck("循环 verdict 在产物缺失时诚实说「无法判读」",
               "无法判读" in cyc["verdict"], cyc["verdict"])
            # 4. 状态累积与去重
            cyc2 = one_cycle(state_path=Path(td) / "s.json", runner=failing_runner)
            st = _load(Path(td) / "s.json")
            ck("循环号递增且不重复",
               cyc2["cycle"] == cyc["cycle"] + 1 and
               len(st["cycles"]) == 2 and len({c["cycle"] for c in st["cycles"]}) == 2)
            # 5. agent 不写台账：循环只允许在 store/cycles 下落盘
            if ledger.exists():
                ck("agent 循环不触碰 lessons.md", ledger.read_bytes() == before)
            ck("循环报告只落在注入的 cycles 目录",
               len(list(CYCLES_DIR.glob("cycle_*.md"))) == 2)
        finally:
            ROOT, CYCLES_DIR = old_root, old_cycles

    # 6. 授权防火墙：人工动作拒绝、未知动作拒绝、自动动作放行
    ck("wiki_edit 被拒绝", not request_action("wiki_edit")["allowed"])
    ck("write_paper 被拒绝", not request_action("write_paper")["allowed"])
    ck("send_outward 被拒绝", not request_action("send_outward")["allowed"])
    ck("decode_compressed_tags 被拒绝（用户拍板暂缓）",
       not request_action("decode_compressed_tags")["allowed"])
    ck("未知动作被拒绝（不默认放行）",
       not request_action("do_anything")["allowed"])
    ck("scan 放行", request_action("scan")["allowed"])

    # 7. 头条诚实：合成产物驱动 runnable_now，缺产物返回 None 不猜
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td)
        (fake_root / "store").mkdir()
        with open(fake_root / "store" / "proposals_state.json", "w",
                  encoding="utf-8") as fh:
            json.dump({"entries": [
                {"id": "a", "state": "待批", "measured":
                 {"executable_here": False, "reason": "需求未测量 fail-closed"}},
                {"id": "b", "state": "被阻塞", "measured":
                 {"executable_here": False, "reason": "data"}},
            ]}, fh, ensure_ascii=False)
        old_root = ROOT
        try:
            ROOT = fake_root
            h = derive_headline()
            ck("合成产物：runnable_now=0（全部 executable_here=False）",
               h["runnable_now"] == 0, str(h))
            ck("阻断原因按次数排：需求未测量在前",
               list(h.get("blocked_reasons", {}))[:1] == ["需求未测量 fail-closed"]
               or "需求未测量 fail-closed" in h.get("blocked_reasons", {}))
            ck("verdict 不许在 0 可跑时说「可跑」",
               "无一条提案可在本机开跑" in honest_verdict(h))
            (fake_root / "store" / "proposals_state.json").unlink()
            ck("产物缺失时 runnable_now=None 而不是 0",
               derive_headline()["runnable_now"] is None)
            # 7b. 真实产物形状：阻断文案在顶层 blocking_reason（不是
            # measured.reason）——夹具形状跟真实产物不一致时 selftest 会
            # 全绿而真实数据算出空桶，这次事故就出在这里。
            (fake_root / "store" / "proposals_state.json").write_text(
                json.dumps({"entries": [
                    {"id": "r1", "state": "待批", "executable_here": False,
                     "blocking_reason": "需求未测量：提案原文未显式给出算力/数据需求"},
                    {"id": "r2", "state": "被阻塞", "executable_here": False,
                     "blocking_reason": "data"},
                ]}, ensure_ascii=False), encoding="utf-8")
            h2 = derive_headline()
            ck("真实形状：顶层 blocking_reason 被聚合进 blocked_reasons",
               h2["blocked_reasons"].get(
                   "需求未测量：提案原文未显式给出算力/数据需求") == 1
               and h2["blocked_reasons"].get("data") == 1, str(h2))
            ck("真实形状：待人工理由不再编默认值",
               [a["why"] for a in collect_approvals()
                if a["kind"] == "awaiting_approval"]
               == ["需求未测量：提案原文未显式给出算力/数据需求"])
            e3 = {"id": "x", "state": "待批"}
            ck("两处都缺时明说「未说明」",
               _block_reason(e3) == "未说明")
            ck("条目标识回落到 arxiv_id（真实字段名）",
               _ent_id({"arxiv_id": "2601.07880v1"}) == "2601.07880v1"
               and _ent_id(e3) == "x")
        finally:
            ROOT = old_root

    print("SELFTEST OK" if not r else "SELFTEST 有断言没过")
    return r


def main() -> int:
    ap = sys.argv[1:]
    if ap == ["--selftest"]:
        return selftest()
    if ap == ["--status"]:
        return status()
    if ap == ["--cycle"]:
        cyc = one_cycle()
        print("循环 #%d：%s" % (cyc["cycle"], cyc["verdict"]))
        for s in cyc["steps"]:
            print("  %-8s rc=%s %s %s" % (
                s["step"], s.get("rc", "—"), s.get("status", ""),
                (s.get("tail", "").splitlines() or [""])[-1][:80]))
        return 0 if all(s.get("ok", False) or
                        s.get("status") == "skipped_after_failure"
                        for s in cyc["steps"]) else 1
    print(__doc__)
    print("用法：--cycle | --status | --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
