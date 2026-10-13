#!/usr/bin/env python3
"""W8 第二条闭环：Faithful-CoT 迷你口径——翻译→程序执行 vs 匹配 few-shot CoT（提案 2301.13379v3）。

预注册协议（2026-10-03，先钉死再跑，改动=新实验不覆盖本结果）：
  - 模型  Qwen3-0.6B 本地快照，bf16，CPU 贪心，chat template + enable_thinking=False
          （与 W7 完全同栈，逐字复用其加载/生成/抽取函数）
  - 数据  GSM8K test.jsonl，排序后 seed=20261003 抽 n=100——与 W7 **同一子集**；
          启动时断言 gold 序列与 w7_gsm8k_anchor_items.jsonl 逐位一致（配对校验）
  - 双臂  都用同一批 6 个 few-shot exemplar（**自编**：不来自任何 GSM8K 切片，
          零泄漏；selftest 逐个执行 exemplar 程序验证内部一致）：
            臂 F（faithful）：翻译成 Python 程序，沙箱执行出数
            臂 C（匹配 CoT）：同 6 题的文本推理 exemplar，"#### N" 格式
          匹配 shot 数 ⇒ F vs C 的配对差只差「程序执行 vs 文本推理」这一件事
  - 截断  max_new_tokens=384；截断=判错，单列计数
  - 抽取  臂 F：取**最后一个围栏程序**（行首 ``` 开/闭配对；末块未闭合
          到文末也算程序——2026-10-03 22:59 修订，n=1 仪器调试期，理由：
          模型常直接 EOS 不闭合围栏，原规则会整臂误判 unparsed；
          完全无围栏=unparsed 不变）；子进程
          [python, -I, -S] 执行，超时 20s=unparsed；从 stdout 抽最后一个数字
          臂 C：W7 原序（#### → \\boxed{} → 最后数字）
  - 计分  分母=全部 100；容差 1e-4（与 W7 相同）
  - 锚    Table 1（greedy，code-davinci-002）：Faithful CoT GSM8K=72.3，
          CoT 基线=63.3（来源 arxiv.org/html/2301.13379v3，2026-10-03 抓取）。
          本机 0.6B 与 code-davinci-002 不同源 ⇒ **量级测量**，非受控比较
  - 配对  McNemar 精确双侧：p = min(1, 2·P(X≤min(b,c) | Bin(n_d, 0.5)))；
          F vs C 为本项目第一次**双臂都是自己跑的**受控比较
  - 沙箱  生成的程序在本机子进程执行（-I -S 隔离 + 超时 + tmp 目录）；
          研究环境残留风险（磁盘写/无网络限制）如实披露，不做假声明

fail-closed：store 里该提案不是「已批」就拒绝运行；已跑/出结论拒绝重跑。
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "ai-researcher", "store")
DATA = os.path.join(ROOT, "ai-researcher", "data", "gsm8k")
TARGET_ID = "2301.13379v3"
SEED = 20261003
N = 100
MAX_NEW_TOKENS = 384
EXEC_TIMEOUT_S = 20
ANCHOR_F = 0.723   # Faithful CoT, greedy, code-davinci-002
ANCHOR_C = 0.633   # CoT baseline, greedy, code-davinci-002

# ── 6 个自编 exemplar（预注册原文；selftest 逐个执行程序验证内部一致）──────
EXEMPLARS = [
    {"q": "Maya buys 3 packs of stickers. Each pack has 12 stickers. She gives "
          "7 stickers to her friend. How many stickers does she have left?",
     "cot": "Maya starts with 3 packs of 12 stickers: 3 * 12 = 36 stickers.\n"
            "She gives away 7: 36 - 7 = 29.\n#### 29",
     "prog": "stickers = 3 * 12\nstickers = stickers - 7\nprint(stickers)"},
    {"q": "A train travels at 60 kilometers per hour for 2.5 hours. How many "
          "kilometers does it travel?",
     "cot": "Distance = speed * time: 60 * 2.5 = 150.\n#### 150",
     "prog": "speed = 60\ntime = 2.5\nprint(speed * time)"},
    {"q": "A jacket costs 80 dollars. The store adds a 15% sales tax. What is "
          "the total price in dollars?",
     "cot": "Tax = 15% of 80: 80 * 0.15 = 12.\nTotal = 80 + 12 = 92.\n#### 92",
     "prog": "price = 80\ntax = price * 0.15\nprint(price + tax)"},
    {"q": "A baker makes 250 cookies. He packs them into boxes of 8 cookies "
          "each. How many full boxes can he pack?",
     "cot": "250 / 8 = 31 with 2 cookies left over, so he can fully pack "
            "31 boxes.\n#### 31",
     "prog": "cookies = 250\nper_box = 8\nprint(cookies // per_box)"},
    {"q": "Liam has 45 marbles. Zoe has 12 fewer than twice as many marbles "
          "as Liam. How many marbles does Zoe have?",
     "cot": "Twice Liam's marbles: 2 * 45 = 90.\n12 fewer: 90 - 12 = 78.\n#### 78",
     "prog": "liam = 45\nzoe = 2 * liam - 12\nprint(zoe)"},
    {"q": "A faucet leaks 30 milliliters of water per hour. How many "
          "milliliters of water leak in 3 days?",
     "cot": "Hours in 3 days: 3 * 24 = 72.\nLeak: 30 * 72 = 2160.\n#### 2160",
     "prog": "per_hour = 30\nhours = 3 * 24\nprint(per_hour * hours)"},
]
assert len(EXEMPLARS) == 6

PROMPT_F = (
    "You translate grade school math problems into a short Python program that "
    "prints the numeric answer. Respond with ONE ```python code block and "
    "nothing else. The program must print only the final number.\n\n"
    + "\n\n".join(f"Problem: {e['q']}\n```python\n{e['prog']}\n```"
                  for e in EXEMPLARS)
    + "\n\nProblem: {q}"
)
PROMPT_C = (
    "Solve the grade school math problem. Reason step by step, then write the "
    "final numeric answer on the last line in the exact format:\n#### <number>\n\n"
    + "\n\n".join(f"Problem: {e['q']}\n{e['cot']}" for e in EXEMPLARS)
    + "\n\nProblem: {q}"
)

# ── 以下函数除 build_inputs 多收一个 prompt 模板外，逐字复用 W7 ─────────────
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_HASH = re.compile(r"####\s*(-?\d[\d,]*(?:\.\d+)?)")


def state_of(arxiv_id: str, path: str | None = None) -> str:
    p = path or os.path.join(STORE, "proposals_state.json")
    d = json.load(open(p, encoding="utf-8"))
    for e in d["entries"]:
        if e["arxiv_id"] == arxiv_id:
            return e["state"]
    raise KeyError(arxiv_id)


def gate_pass(state: str) -> bool:
    """批准门：只有「已批」可跑；终态/其他一律拒。"""
    return state == "已批"


def load_dataset() -> list[dict]:
    local = os.path.join(DATA, "test.jsonl")
    if not os.path.exists(local):
        raise FileNotFoundError(f"缺本地数据 {local}（网络下载留给显式步骤，脚本不静默下载）")
    return [json.loads(l) for l in open(local, encoding="utf-8") if l.strip()]


def pick_subset(items: list[dict], n: int = N, seed: int = SEED) -> list[dict]:
    ordered = sorted(items, key=lambda x: (x["question"], x["answer"]))
    import random
    rng = random.Random(seed)
    return sorted(rng.sample(ordered, n), key=lambda x: (x["question"], x["answer"]))


def parse_gold(ans_field: str):
    m = _HASH.search(ans_field)
    if not m:
        raise ValueError(f"gold 无 #### 标记：{ans_field[:60]!r}")
    return float(m.group(1).replace(",", ""))


def is_correct(pred, gold) -> bool:
    return pred is not None and gold is not None and abs(pred - gold) < 1e-4


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n <= 0 or not (0 <= k <= n):
        raise ValueError(f"wilson 非法输入 k={k} n={n}")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def strip_think(txt: str) -> str:
    t = txt
    if "</think>" in t:
        t = t.rsplit("</think>", 1)[1]
    if "<think>" in t:
        t = t.rsplit("<think>", 1)[1]
    return t


def extract_answer(txt: str):
    """臂 C 用：W7 原序抽取。"""
    t = strip_think(txt)
    m = _HASH.search(t)
    if m:
        try:
            return float(m.group(1).replace(",", "")), "hash"
        except ValueError:
            pass
    m = re.search(r"\\boxed\{([^{}]+)\}", t)
    if m:
        try:
            return float(m.group(1).strip().replace(",", "")), "boxed"
        except ValueError:
            pass
    nums = _NUM.findall(t)
    if nums:
        try:
            return float(nums[-1].replace(",", "")), "last_num"
        except ValueError:
            pass
    return None, "unparsed"


_FENCE_MARK = re.compile(r"^```(?:python|py)?[ \t]*$", re.MULTILINE)


def extract_code(txt: str) -> tuple[str | None, str]:
    """臂 F 用：取**最后一个**围栏程序（行首 ``` 标记配对：开/闭交替；
    末尾未闭合到文末也算程序）；无任何围栏=unparsed。"""
    t = strip_think(txt)
    marks = list(_FENCE_MARK.finditer(t))
    if not marks:
        return None, "unparsed"
    if len(marks) % 2 == 0:
        opn, close, how = marks[-2], marks[-1], "fence"
        code = t[opn.end():close.start()]
    else:
        opn, how = marks[-1], "fence_unclosed"
        code = t[opn.end():]
    code = code.split("```", 1)[0].strip()
    return (code if code else None), how


def last_number_from_stdout(out: str):
    nums = _NUM.findall(out)
    if not nums:
        return None
    try:
        return float(nums[-1].replace(",", ""))
    except ValueError:
        return None


def run_program(code: str, timeout_s: int = EXEC_TIMEOUT_S,
                python: str = sys.executable) -> tuple[str | None, str, int]:
    """沙箱执行生成的程序。-I -S 隔离 + 超时 + 一次性 tmp 目录。
    返回 (预测数或 None, how, 耗时 ms)。任何异常/超时=unparsed，绝不编数。"""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "gen.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        t0 = time.time()
        try:
            r = subprocess.run([python, "-I", "-S", path], capture_output=True,
                               text=True, timeout=timeout_s, cwd=td)
        except subprocess.TimeoutExpired:
            return None, "exec_timeout", int((time.time() - t0) * 1000)
        except OSError as e:
            return None, f"exec_error:{type(e).__name__}", int((time.time() - t0) * 1000)
        ms = int((time.time() - t0) * 1000)
        if r.returncode != 0:
            return None, "exec_error", ms
        pred = last_number_from_stdout(r.stdout)
        return pred, ("exec" if pred is not None else "no_number_in_stdout"), ms


def mcnemar_two_sided(b: int, c: int) -> float:
    """精确 McNemar：p = min(1, 2·P(X≤min(b,c) | Bin(b+c, .5)))。log 空间求和。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    logc = 0.0
    terms = []
    for i in range(0, k + 1):
        if i > 0:
            logc += math.log(n - i + 1) - math.log(i)
        terms.append(logc + i * math.log(0.5) + (n - i) * math.log(0.5))
    m = max(terms)
    tail = sum(math.exp(x - m) for x in terms) * math.exp(m)
    return min(1.0, 2.0 * tail)


def build_inputs(tok, template: str, question: str):
    raw = template.format(q=question)
    try:
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        flag = "enable_thinking=False"
    except TypeError:
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
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


def generate_one(mdl, tok, torch, template: str, question: str):
    ids, flag = build_inputs(tok, template, question)
    t1 = time.time()
    with torch.no_grad():
        out = mdl.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
    sec = round(time.time() - t1, 1)
    n_new = int(out.shape[1] - ids["input_ids"].shape[1])
    txt = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    return txt, n_new >= MAX_NEW_TOKENS, n_new, sec, flag


def pairing_check(subset: list[dict]) -> dict:
    """与 W7 配对校验：gold 序列逐位一致才算同一子集。"""
    w7_path = os.path.join(STORE, "w7_gsm8k_anchor_items.jsonl")
    w7_golds = [json.loads(l)["gold"] for l in open(w7_path, encoding="utf-8") if l.strip()]
    our_golds = [parse_gold(it["answer"]) for it in subset]
    same = len(w7_golds) == len(our_golds) and \
        all(abs(a - b) < 1e-9 for a, b in zip(w7_golds, our_golds))
    return {"matched": same, "n_w7": len(w7_golds), "n_ours": len(our_golds)}


def run() -> int:
    st = state_of(TARGET_ID)
    if not gate_pass(st):
        print(f"批准门拦截：{TARGET_ID} 状态={st}（需 已批）。拒绝运行。")
        return 2
    for suf in ("_summary.json",):
        p = os.path.join(STORE, "w8_faithful_cot" + suf)
        if os.path.exists(p):
            print(f"产物已存在 {p}——重跑需先归档/删除旧产物（预注册：不覆盖）。拒绝。")
            return 2

    f_path = os.path.join(STORE, "w8_f_items.jsonl")
    c_path = os.path.join(STORE, "w8_c_items.jsonl")
    done_f = {}
    if os.path.exists(f_path):
        for l in open(f_path, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                done_f[r["i"]] = r
    done_c = {}
    if os.path.exists(c_path):
        for l in open(c_path, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                done_c[r["i"]] = r
    if done_f or done_c:
        print(f"断点续跑：F 已有 {len(done_f)} 行，C 已有 {len(done_c)} 行", flush=True)

    t0 = time.time()
    subset = pick_subset(load_dataset())
    pc = pairing_check(subset)
    if not pc["matched"]:
        print(f"配对校验失败：与 W7 gold 序列不一致 {pc}。拒绝运行（不是同一子集）。")
        return 2

    tok, mdl, torch = load_model()
    flag = ""
    rows = []
    # ── 臂 F：翻译→执行 ──
    rows = []
    for i, it in enumerate(subset, 1):
        gold = parse_gold(it["answer"])
        if i in done_f:
            rows.append(done_f[i])
            continue
        txt, trunc, n_new, sec, flag = generate_one(mdl, tok, torch, PROMPT_F, it["question"])
        code, how = extract_code(txt)
        if code is None:
            pred, how2, ms = None, how, 0
        else:
            pred, how2, ms = run_program(code)
        ok = is_correct(pred, gold)
        row = {"i": i, "gold": gold,
               "f": {"pred": pred, "how": how2, "correct": ok,
                     "truncated": trunc, "n_new_tokens": n_new, "sec": sec,
                     "exec_ms": ms,
                     "code_tail": (code or "")[-160:],
                     "raw_tail": ("" if code is not None else txt.strip()[-160:])},
               "c": None}
        rows.append(row)
        with open(f_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if i % 10 == 0 or i == 1 or i == len(subset):
            acc = sum(1 for r in rows if r["f"]["correct"])
            print(f"[F {i}/{len(subset)}] acc={acc}/{len(rows)} last_sec={sec} "
                  f"how={how2} trunc={trunc}", flush=True)
    # ── 臂 C：匹配 few-shot CoT ──
    for i, it in enumerate(subset, 1):
        if i in done_c:
            rows[i - 1]["c"] = done_c[i]["c"]
            continue
        gold = rows[i - 1]["gold"]
        txt, trunc, n_new, sec, flag = generate_one(mdl, tok, torch, PROMPT_C, it["question"])
        pred, how = extract_answer(txt)
        c_res = {"pred": pred, "how": how, "correct": is_correct(pred, gold),
                 "truncated": trunc, "n_new_tokens": n_new, "sec": sec,
                 "raw_tail": txt.strip()[-120:]}
        rows[i - 1]["c"] = c_res
        with open(c_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"i": i, "gold": gold, "c": c_res},
                                ensure_ascii=False) + "\n")
        if i % 10 == 0 or i == 1 or i == len(subset):
            acc = sum(1 for r in rows if r["c"] and r["c"]["correct"])
            print(f"[C {i}/{len(subset)}] acc={acc}/{i} last_sec={sec}", flush=True)

    # ── 汇总（全行重扫，不靠循环内计数）──
    def arm_stat(key):
        got = [r[key] for r in rows]
        n = len(got)
        k = sum(1 for x in got if x and x["correct"])
        lo, hi = wilson(k, n)
        return {"n": n, "n_correct": k, "acc": round(k / n, 4),
                "wilson95": [round(lo, 4), round(hi, 4)],
                "n_unparsed": sum(1 for x in got if x and x["how"] in ("unparsed", "exec_timeout", "exec_error", "no_number_in_stdout")),
                "n_truncated": sum(1 for x in got if x and x["truncated"]),
                "sec_mean": round(statistics.mean([x["sec"] for x in got if x]), 1)}

    fs, cs = arm_stat("f"), arm_stat("c")
    b = sum(1 for r in rows if r["f"]["correct"] and not r["c"]["correct"])
    c = sum(1 for r in rows if not r["f"]["correct"] and r["c"]["correct"])
    p_fc = mcnemar_two_sided(b, c)
    gap_f = round(fs["acc"] - ANCHOR_F, 4)
    gap_c = round(cs["acc"] - ANCHOR_C, 4)
    summary = {
        "experiment": "w8_faithful_cot", "arxiv_id": TARGET_ID,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "device": "cpu",
        "protocol": {
            "model": "Qwen3-0.6B bf16 CPU greedy", "n": N, "seed": SEED,
            "max_new_tokens": MAX_NEW_TOKENS, "template_flag": flag,
            "arms": {"f": "翻译→Python 程序→沙箱执行（-I -S, 20s 超时）",
                     "c": "匹配 few-shot CoT（同 6 exemplar 题，#### 格式）"},
            "exemplars_source": "自编 6 题，不来自任何 GSM8K 切片（零泄漏）",
            "prompt_f": PROMPT_F, "prompt_c": PROMPT_C,
            "subset": "与 W7 同一子集：seed 20261003 排序抽样；gold 序列配对校验通过",
            "anchors": {"faithful": ANCHOR_F, "cot": ANCHOR_C,
                        "source": "arxiv.org/html/2301.13379v3 Table 1 (greedy, code-davinci-002)",
                        "caliber_note": "code-davinci-002 与 Qwen3-0.6B 不同源 ⇒ 量级测量非受控比较"},
        },
        "pairing_with_w7": pc,
        "arm_f": fs, "arm_c": cs,
        "paired_f_vs_c": {"b_f_right_c_wrong": b, "c_f_wrong_c_right": c,
                          "n_discordant": b + c, "p_exact_two_sided": round(p_fc, 6)},
        "gap_to_anchor": {"f_vs_0.723": gap_f, "c_vs_0.633": gap_c},
        "wall_min": round((time.time() - t0) / 60, 1),
    }
    items_path = os.path.join(STORE, "w8_faithful_cot_items.jsonl")
    with open(items_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = os.path.join(STORE, "w8_faithful_cot_summary.json")
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "protocol"},
                     ensure_ascii=False, indent=2))
    print("wrote", items_path, "and", out)
    return 0


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # ── exemplar 内部一致：真实执行每个程序，输出必须等于 CoT 的 #### 数 ──
    for i, e in enumerate(EXEMPLARS, 1):
        pred, how, _ = run_program(e["prog"], timeout_s=10)
        want = extract_answer(e["cot"])[0]
        ck(f"EX{i} 程序输出", pred, want)
        ck(f"EX{i} 程序 how", how, "exec")
        if not is_correct(pred, want):
            bad.append(f"EX{i} 程序与 CoT 不一致")

    # ── 围栏抽取：最后一个块；无围栏=unparsed；think 残留先剥 ──
    ck("围栏+py标记", extract_code("```python\nprint(1)\n```")[1], "fence")
    ck("双块取最后", extract_code("```\nprint(1)\n```\nmid\n```python\nprint(2)\n```")[0], "print(2)")
    ck("无围栏", extract_code("print(3)")[0], None)
    ck("无围栏how", extract_code("print(3)")[1], "unparsed")
    ck("think残留", extract_code("</think>\n```python\nprint(9)\n```")[0], "print(9)")
    # 修订后的抽取器（2026-10-03 22:59，n=1 仪器调试期，修订理由入档）：
    # 未闭合围栏（EOS 截断）也算程序；行首 ``` 标记开/闭配对；完全无围栏仍拒
    ck("未闭合围栏", extract_code("```python\nprint(7)"), ("print(7)", "fence_unclosed"))
    ck("闭合单块", extract_code("```python\nprint(9)\n```"), ("print(9)", "fence"))
    ck("末块未闭取胜", extract_code("```python\nprint(1)\n```\n```python\nprint(2)"),
       ("print(2)", "fence_unclosed"))
    ck("闭合块截到结束围栏", extract_code("```python\nprint(4)\n```extra"),
       ("print(4)", "fence_unclosed"))
    ck("裸```围栏", extract_code("```\nprint(1)\n```"), ("print(1)", "fence"))
    ck("真无围栏仍拒", extract_code("per_hour = 30\nprint(per_hour)"), (None, "unparsed"))

    # ── 沙箱执行：超时/报错/无数字都必须 unparsed 且不编数 ──
    p, how, _ = run_program("while True: pass", timeout_s=1)
    ck("死循环超时", (p, how), (None, "exec_timeout"))
    p, how, _ = run_program("1/0")
    ck("除零报错", (p, how), (None, "exec_error"))
    p, how, _ = run_program("print('hello')")
    ck("无数字输出", (p, how), (None, "no_number_in_stdout"))
    p, how, _ = run_program("print(1 +)")
    ck("语法错", (p, how), (None, "exec_error"))
    p, how, _ = run_program("print('42 17')")
    ck("stdout 末数", (p, how), (17.0, "exec"))
    p, how, _ = run_program("print(f\"{1234:,}\")")
    ck("stdout 千分位", p, 1234.0)

    # ── McNemar 已知值 ──
    ck("mcnemar 7/0", round(mcnemar_two_sided(7, 0), 6), 0.015625)
    ck("mcnemar 0/0", mcnemar_two_sided(0, 0), 1.0)
    ck("mcnemar 3/3 封顶", mcnemar_two_sided(3, 3), 1.0)
    ck("mcnemar 10/2", round(mcnemar_two_sided(10, 2), 6), 0.038574)

    # ── Wilson 教科书值（与 W7 同参）──
    lo, hi = wilson(50, 100)
    if abs(lo - 0.4038) > 1e-3 or abs(hi - 0.5962) > 1e-3:
        bad.append(f"wilson(50,100)=({lo:.4f},{hi:.4f}) 偏离教科书值")

    # ── 批准门 + 重跑门：假 store 证伪 ──
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "proposals_state.json")
        json.dump({"entries": [{"arxiv_id": TARGET_ID, "state": "待批"}]},
                  open(fake, "w", encoding="utf-8"))
        ck("假store读待批", state_of(TARGET_ID, path=fake), "待批")
    ck("门拒待批", gate_pass("待批"), False)
    ck("门放已批", gate_pass("已批"), True)
    ck("门拒已跑", gate_pass("已跑"), False)
    ck("门拒终态", gate_pass("出结论"), False)

    # ── 配对校验能抓坏 gold ──
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake_store = os.path.join(td, "store")
        os.makedirs(fake_store)
        src = os.path.join(STORE, "w7_gsm8k_anchor_items.jsonl")
        rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
        rows[0]["gold"] = rows[0]["gold"] + 100.0
        with open(os.path.join(fake_store, "w7_gsm8k_anchor_items.jsonl"), "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        # pairing_check 读固定 STORE 路径，这里直接验证逻辑分支
        items = load_dataset()
        subset = pick_subset(items)
        our = [parse_gold(x["answer"]) for x in subset]
        bad_gold = [r["gold"] for r in rows]
        ck("坏gold被抓", all(abs(a - b) < 1e-9 for a, b in zip(bad_gold, our)), False)
        good = [json.loads(l)["gold"] for l in open(src, encoding="utf-8") if l.strip()]
        ck("好gold通过", len(good) == len(our) and
           all(abs(a - b) < 1e-9 for a, b in zip(good, our)), True)

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
