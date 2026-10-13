#!/usr/bin/env python3
"""W11 第三条闭环：HumanEval pass@1 代码生成（提案 2107.03374v2 Evaluating LLMs Trained on Code）。

预注册协议（2026-10-05，先钉死再跑；改动 = 新实验，不覆盖本结果）：
  - 提案  2107.03374v2 / 被回填判据（w10）+ 本机可跑（w11_approve）→ 状态必须「已批」
  - 数据  openai/human-eval 的 data/HumanEval.jsonl.gz，**实测**（2026-10-05 10:2x）：
          HTTP 200、44,877 字节、gunzip 后 164 行；字段 task_id/prompt/entry_point/
          test/canonical_solution 齐备。脚本不静默下载，缺文件即拒。
          仪器自检：canonical_solution 在自己的 check() 下必须过（先跑 8 题实测）
  - 模型  Qwen3-0.6B 本地快照，bf16 + CPU 贪心 + chat template +
          enable_thinking=False（与 W7/W8/W9 同栈，逐字复用其加载/生成写法）
  - 口径  pass@1：每题**单采样**（greedy），分母=164 全量（无抽样）
  - 判对  候选程序 `prompt + 生成代码` 后接数据自带 `test`，
          再 `check(entry_point)`；子进程 [python,-I,-S] 执行，超时 20s
          ⇒ 通过=pass，超时/报错/未产出代码=fail（**不区分原因地计入分母**，
          但原因分布单独落盘，因为「跑不动」和「写错了」是两种失败）
  - 抽取  最后一个 ``` 围栏块（与 W8 extract_code 同规则，含未闭合围栏）；
          无围栏=unparsed 判 fail
  - 落盘  逐题 append 到 w11_items.jsonl（每行 flush），可断点续跑；
          汇总时全行重扫，不靠循环内计数（防计数漂移）
  - 锚    Codex 论文 Table 1 pass@1（https://arxiv.org/html/2107.03374v2，2026-10-04 抓取）：
          GPT-Neo 125M 0.75 / 1.3B 4.79 / 2.7B 6.41、GPT-J 6B 11.62、
          TabNine 2.58、Codex-12M 2.00 / 25M 3.21 / 42M 5.06 / 85M 8.22 /
          300M 13.17 / 679M 16.22 / 2.5B 21.36 / 12B 28.81
  - 口径警告  表 1 的 k=1 列与本协议同口径（单采样）；但模型/来源不同
          ⇒ 差距是**量级测量**，不是受控比较。不做显著性声明。

fail-closed：store 里该提案不是「已批」就拒绝运行；产物已存在拒绝覆盖。
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "ai-researcher", "store")
DATA = os.path.join(ROOT, "ai-researcher", "data", "humaneval", "HumanEval.jsonl")
TARGET_ID = "2107.03374v2"
MAX_NEW_TOKENS = 512
EXEC_TIMEOUT_S = 20
N_TASKS = 164

# Codex 论文 Table 1（pass@1 %，greedy / temperature=0），逐字抄录
ANCHORS = {
    "GPT-Neo 125M": 0.75, "GPT-Neo 1.3B": 4.79, "GPT-Neo 2.7B": 6.41,
    "GPT-J 6B": 11.62, "TabFive 2.58": 2.58,
    "Codex-12M": 2.00, "Codex-25M": 3.21, "Codex-42M": 5.06,
    "Codex-85M": 8.22, "Codex-300M": 13.17, "Codex-679M": 16.22,
    "Codex-2.5B": 21.36, "Codex-12B": 28.81,
}

PROMPT = ("Complete the following Python function. Reply with ONLY one code "
          "block containing the complete function implementation "
          "(including the signature).\n\n```python\n{prompt}```")


def state_of(arxiv_id: str = TARGET_ID,
             path: str | None = None) -> str:
    p = path or os.path.join(STORE, "proposals_state.json")
    d = json.load(open(p, encoding="utf-8"))
    for e in d["entries"]:
        if e["arxiv_id"] == arxiv_id:
            return e["state"]
    raise KeyError(arxiv_id)


def gate_pass(state: str) -> bool:
    return state == "已批"


def load_tasks() -> list[dict]:
    if not os.path.exists(DATA):
        raise FileNotFoundError(
            f"缺本地数据 {DATA}（HumanEval 需显式下载，脚本不静默联网）")
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
    if len(rows) != N_TASKS:
        raise ValueError(f"题数 {len(rows)} != 预注册的 {N_TASKS}，拒跑")
    return rows


_FENCE = re.compile(r"^```(?:python|py)?[ \t]*$", re.MULTILINE)


def extract_code(t: str) -> tuple[str | None, str]:
    """取**最后一个** ``` 围栏块（行首 ```python / ``` / ```py 标记配对，
    开闭交替）；末尾未闭合到文末也算程序（模型常直接 EOS）；完全无围栏
    = unparsed。规则与 W8 extract_code 逐字一致（含 think 块先剥）。
    ⚠️ 2026-10-05 修正：初版用 `^\\s*``` ` 会把 ```python 的语言标记
    一起切进代码里（'python\\ndef f(): pass' 是 SyntaxError），
    门立刻抓到——抽取器的第一个自检断言就是它。
    """
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    marks = list(_FENCE.finditer(t))
    if not marks:
        return None, "unparsed"
    if len(marks) % 2 == 0:
        code = t[marks[-2].end():marks[-1].start()]
        how = "fence"
    else:
        code = t[marks[-1].end():]
        how = "fence_unclosed"
    code = code.split("```", 1)[0].strip()
    return (code if code else None), how


def check_task(task: dict, code: str,
               timeout_s: int = EXEC_TIMEOUT_S,
               python: str = sys.executable) -> tuple[bool, str, str, int]:
    """跑数据自带 check()。返回 (passed, how, stderr 尾, ms)。
    任何异常/超时 ⇒ (False, ...) —— 绝不让未验证的候选算通过。"""
    src = task["prompt"] + code + "\n\n" + task["test"] + \
        f"\n\ncheck({task['entry_point']})\n"
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "cand.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        t0 = time.time()
        try:
            r = subprocess.run([python, "-I", "-S", path], capture_output=True,
                               text=True, timeout=timeout_s, cwd=td)
        except subprocess.TimeoutExpired:
            return False, "exec_timeout", "", int((time.time() - t0) * 1000)
        except OSError as e:
            return False, f"exec_error:{type(e).__name__}", "", \
                int((time.time() - t0) * 1000)
        ms = int((time.time() - t0) * 1000)
    if r.returncode == 0:
        return True, "pass", "", ms
    tail = (r.stderr or "").strip().splitlines()
    return False, "assert_or_error", (tail[-1][:160] if tail else ""), ms


def build_inputs(tok, prompt_text: str):
    try:
        text = tok.apply_chat_template(
            [{"role": "user", "content": prompt_text}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        flag = "enable_thinking=False"
    except TypeError:
        text = tok.apply_chat_template(
            [{"role": "user", "content": prompt_text}],
            tokenize=False, add_generation_prompt=True)
        flag = "template_no_flag"
    return tok(text, return_tensors="pt"), flag


def load_model():
    snaps = glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/*"))
    if not snaps:
        raise FileNotFoundError("Qwen3-0.6B 本地快照不存在")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(snaps[0])
    mdl = AutoModelForCausalLM.from_pretrained(snaps[0], dtype=torch.bfloat16).to("cpu")
    mdl.eval()
    return tok, mdl, torch


def generate_one(mdl, tok, torch, prompt_text: str):
    ids, flag = build_inputs(tok, prompt_text)
    t1 = time.time()
    with torch.no_grad():
        out = mdl.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
    sec = round(time.time() - t1, 1)
    n_new = int(out.shape[1] - ids["input_ids"].shape[1])
    txt = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    return txt, n_new >= MAX_NEW_TOKENS, n_new, sec, flag


# ── 汇总：全量重扫（不是靠循环内计数）──
def summarize(rows: list[dict], scanned: list[dict], flag: str,
              wall_min: float) -> dict:
    """从落盘的逐题记录算 summary。**唯一的数字来源是 scanned**，
    调用方不得传任何自己算的数进来。"""
    n = len(scanned)
    if n != N_TASKS:
        raise ValueError(f"分母 {n} != 预注册 {N_TASKS}")
    k = sum(1 for r in scanned if r["passed"])
    fail_reasons: dict[str, int] = {}
    for r in scanned:
        if not r["passed"]:
            key = r["check"]
            fail_reasons[key] = fail_reasons.get(key, 0) + 1
    lo, hi = wilson(k, n)
    return {
        "experiment": "w11_humaneval_pass1", "arxiv_id": TARGET_ID,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "device": "cpu",
        "protocol": {
            "model": "Qwen3-0.6B bf16 CPU greedy",
            "n_tasks": n, "denominator": "全部 164 题（无抽样）",
            "max_new_tokens": MAX_NEW_TOKENS, "template_flag": flag,
            "metric": "pass@1（每题单采样贪心）",
            "judge": "prompt+候选代码 后接数据自带 check(entry_point)，"
                     "子进程 [python,-I,-S]，超时 20s；超时/报错/无代码均判 fail",
            "dataset": "openai/human-eval data/HumanEval.jsonl.gz（164 行实测）",
            "anchors": ANCHORS,
            "anchor_source": "https://arxiv.org/html/2107.03374v2 Table 1（2026-10-04 抓取）",
            "caliber_note": "表 1 的 k=1 列与本协议同为单采样；但模型/来源不同 ⇒ "
                            "量级测量，非受控比较；不做显著性声明",
        },
        "pass_at_1": round(k / n, 4),
        "wilson95": [round(lo, 4), round(hi, 4)],
        "n_pass": k, "n_tasks": n,
        "fail_reasons": fail_reasons,
        "n_truncated": sum(1 for r in scanned if r["truncated"]),
        "n_unparsed": sum(1 for r in scanned if r["extract"] == "unparsed"),
        "sec_mean": round(statistics.mean([r["sec"] for r in scanned]), 1),
        "gap_to_anchor": {
            "vs_Codex-12M_2.00": round(k / n - 0.0200, 4),
            "vs_GPT-Neo-125M_0.75": round(k / n - 0.0075, 4),
            "vs_GPT-J-6B_11.62": round(k / n - 0.1162, 4),
        },
        "wall_min": wall_min,
    }


def resummarize() -> int:
    """从已落盘的 items 重算 summary，**不重跑模型**。

    为什么需要它（2026-10-05 实测事故）：`wilson95` 字段是跑批**开始之后**
    才补进 summarize 逻辑的，那一轮 summary 因此缺这个键，判读器的重算门
    立刻抓到 `summary.wilson95 = null` ⇒ verdict=fail。正确修法是**重算**
    summary（数字仍然全部来自 items），不是手填一个 wilson95 进去。
    旧 summary 先备份，产物保留可追溯。
    """
    rows = load_tasks()
    out_path = os.path.join(STORE, "w11_humaneval_items.jsonl")
    summ_path = os.path.join(STORE, "w11_humaneval_summary.json")
    allrows: dict[str, dict] = {}
    for l in open(out_path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        allrows[r["task_id"]] = r
    missing = [t["task_id"] for t in rows if t["task_id"] not in allrows]
    if missing:
        print(f"分母不完整：缺 {len(missing)} 题，拒绝重算")
        return 2
    scanned = [allrows[t["task_id"]] for t in rows]
    old = {}
    if os.path.exists(summ_path):
        old = json.load(open(summ_path, encoding="utf-8"))
        with open(summ_path + ".bak-before-resummarize", "w", encoding="utf-8") as fh:
            json.dump(old, fh, ensure_ascii=False, indent=2)
    flag = old.get("protocol", {}).get("template_flag", "")
    wall = old.get("wall_min", 0.0)
    summary = summarize(rows, scanned, flag, wall)
    summary["resummarized"] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "why": "跑批开始后才把 wilson95 补进 summarize，旧 summary 缺该键；"
               "从 items 重算而非手填",
        "old_summary_sha_like": {kk: old.get(kk) for kk in
                                 ("pass_at_1", "wilson95", "n_pass", "n_tasks",
                                  "fail_reasons", "n_truncated", "n_unparsed",
                                  "sec_mean")},
        "old_backup": os.path.basename(summ_path + ".bak-before-resummarize"),
    }
    # 不变量：除新增字段外，所有数字必须与旧 summary 一致（重算不是改数）
    drift = {kk: (summary.get(kk), old.get(kk)) for kk in
             ("pass_at_1", "n_pass", "n_tasks", "fail_reasons",
              "n_truncated", "n_unparsed", "sec_mean")
             if old and summary.get(kk) != old.get(kk)}
    if drift:
        print(f"重算与旧 summary 不一致，拒绝落盘：{drift}")
        return 2
    json.dump(summary, open(summ_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("protocol", "resummarized")},
                     ensure_ascii=False, indent=2))
    print("（旧 summary 已备份为 " + os.path.basename(summ_path) +
           ".bak-before-resummarize）")
    return 0


def run() -> int:
    st = state_of(TARGET_ID)
    if not gate_pass(st):
        print(f"批准门拦截：{TARGET_ID} 状态={st}（需 已批）。拒绝运行。")
        return 2
    out_path = os.path.join(STORE, "w11_humaneval_items.jsonl")
    summ_path = os.path.join(STORE, "w11_humaneval_summary.json")
    if os.path.exists(summ_path):
        print(f"汇总已存在 {summ_path}——重跑需先归档（预注册：不覆盖）。拒绝。")
        return 2

    rows = load_tasks()
    done: dict[str, dict] = {}
    n_corrupt = 0
    if os.path.exists(out_path):
        for l in open(out_path, encoding="utf-8"):
            if not l.strip():
                continue
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                # 进程在写一半时被回收 ⇒ 尾行可能是半截 JSON。容错跳过，
                # 但必须报出来：漏掉的题由下面的分母完整性门抓住（fail-closed）。
                n_corrupt += 1
                continue
            done[r["task_id"]] = r
        print(f"断点续跑：已有 {len(done)} 题（损坏行 {n_corrupt}）", flush=True)

    tok, mdl, torch = load_model()
    flag = ""
    t0 = time.time()
    results: list[dict] = []
    for i, task in enumerate(rows, 1):
        tid = task["task_id"]
        if tid in done:
            results.append(done[tid])
            continue
        user = PROMPT.format(prompt=task["prompt"])
        txt, trunc, n_new, sec, flag = generate_one(mdl, tok, torch, user)
        code, how = extract_code(txt)
        if code is None:
            passed, chk, err, ms = False, "no_code", "", 0
        else:
            passed, chk, err, ms = check_task(task, code)
        row = {"task_id": tid, "entry_point": task["entry_point"],
               "passed": passed, "extract": how, "check": chk,
               "err_tail": err, "truncated": trunc, "n_new_tokens": n_new,
               "sec": sec, "exec_ms": ms,
               "code": (code or "")[:4000],
               "raw_tail": ("" if code is not None else txt.strip()[-200:])}
        results.append(row)
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        if i % 5 == 0 or i == 1 or i == len(rows):
            k = sum(1 for r in results if r["passed"])
            print(f"[{i}/{len(rows)}] pass={k}/{len(results)} "
                  f"last_sec={sec} chk={chk} trunc={trunc}", flush=True)

    # ── 汇总：全量重扫（不是靠循环内计数）──
    allrows: dict[str, dict] = {}
    for l in open(out_path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        allrows[r["task_id"]] = r
    missing = [t["task_id"] for t in rows if t["task_id"] not in allrows]
    if missing:
        # 分母完整性门：分母必须=164。少题却照样算 pass@1 会把
        # 「只跑了容易的」伪装成「跑完了」——这是能骗过所有下游门的一类错。
        print(f"分母不完整：缺 {len(missing)} 题（{missing[:5]}），拒绝汇总")
        return 2
    scanned = [allrows[t["task_id"]] for t in rows]
    n = len(scanned)
    if n != N_TASKS:
        print(f"分母 {n} != 预注册 {N_TASKS}，拒绝汇总")
        return 2
    summary = summarize(rows, scanned, flag,
                        round((time.time() - t0) / 60, 1))
    json.dump(summary, open(summ_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({kk: v for kk, v in summary.items() if kk != "protocol"},
                     ensure_ascii=False, indent=2))
    print("wrote", out_path, "and", summ_path)
    return 0


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    ck("批准门放 已批", gate_pass("已批"), True)
    for s in ("已跑", "出结论", "待批", "被阻塞", "被推翻"):
        ck(f"批准门拦 {s}", gate_pass(s), False)

    # 抽取规则
    ck("围栏", extract_code("```python\ndef f(): pass\n```")[0], "def f(): pass")
    ck("双块取最后", extract_code("```\na=1\n```\n```python\na=2\n```")[0], "a=2")
    ck("未闭合围栏", extract_code("```python\ndef g(): pass"),
       ("def g(): pass", "fence_unclosed"))
    ck("无围栏", extract_code("def h(): pass"), (None, "unparsed"))

    # 判对器：必须能失败——错的代码必须判 fail（门不是装饰）
    tasks = load_tasks()
    t0 = tasks[0]
    ck("题目数", len(tasks), N_TASKS)
    passed, how, err, _ = check_task(t0, "\n    pass")
    ck("空实现判 fail", passed, False)
    passed, how, err, _ = check_task(t0, "\n    raise ValueError('x')")
    ck("抛异常判 fail", passed, False)
    passed, how, err, _ = check_task(t0, "\n    while True: pass", timeout_s=3)
    ck("死循环判 fail(超时)", (passed, how), (False, "exec_timeout"))
    ck("超时非 0", err, "")

    # 仪器自检：canonical_solution 必须过自己的 check()——judge 没有集体失灵
    n_can = 5
    for task in tasks[:n_can]:
        p, how, err, _ = check_task(task, task["canonical_solution"])
        ck(f"canonical {task['task_id']} 应通过", p, True)

    # summarize：分母不足必须抛（不许静默出一个「算完了」的 summary）
    try:
        summarize(tasks, [{"task_id": "x", "passed": True, "check": "pass",
                           "sec": 1.0, "truncated": False,
                           "extract": "fence"}], "", 0.0)
        ck("分母不足 summarize 抛错", "没抛", "抛 ValueError")
    except ValueError:
        ck("分母不足 summarize 抛错", "抛了", "抛了")
    # summarize 的数字必须全部来自 scanned（Wilson 教科书值夹具 7/8 缩放到 164）
    fake = []
    for i in range(N_TASKS):
        fake.append({"task_id": f"t{i}", "passed": i < 7, "sec": 1.0,
                     "truncated": False, "extract": "fence",
                     "check": "pass" if i < 7 else "assert_or_error"})
    s = summarize(tasks, fake, "flag", 1.0)
    ck("7/164 pass", (s["n_pass"], s["n_tasks"]), (7, N_TASKS))
    ck("pass@1 7/164", s["pass_at_1"], round(7 / 164, 4))
    lo8, hi8 = wilson(7, 8)
    ck("Wilson 7/8", (round(lo8, 3), round(hi8, 3)), (0.529, 0.978))
    ck("失败分布", s["fail_reasons"], {"assert_or_error": N_TASKS - 7})
    ck("锚差=我方−Codex-12M", s["gap_to_anchor"]["vs_Codex-12M_2.00"],
       round(7 / 164 - 0.02, 4))

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--resummarize" in sys.argv:
        sys.exit(resummarize())
    sys.exit(run())