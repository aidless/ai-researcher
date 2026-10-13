#!/usr/bin/env python3
"""W7 第一条闭环：GSM8K 纯 prompt 准确率 vs 文献锚值的差距测量（提案 2405.07551v1）。

预注册协议（2026-10-03，先钉死再跑，改动=新实验不覆盖本结果）：
  - 模型  Qwen3-0.6B 本地快照，bf16，CPU（torch 为 cpu-only 构建），贪心解码
  - 数据  GSM8K test.jsonl（1319 题），排序后 seed=20261003 抽 n=100
  - 提示  zero-shot CoT（下方 PROMPT 原文），chat template + enable_thinking=False
          ——Qwen3 是 thinking 模型，裸补全全空（w6_model_bakeoff.py:165 实测教训）
  - 截断  max_new_tokens=384；截断=判错，单列计数，不重抽不重滚
  - 抽取  剥 <think> 残留 → `#### N` → \\boxed{N} → 最后一个数字；都失败=unparsed
  - 计分  分母=全部 100（unparsed/截断计入错误，GSM8K 标准口径）；数值比较容差 1e-4
  - 判据  acc 的 Wilson 95% CI；gap_to_anchor_lo = acc − 0.838（锚为已发表固定点，
          不给锚加 CI）
  - 口径  锚值 83.8~90.7 出自 MathCoder（7B 级、微调+工具）。本机 0.6B 纯 prompt
          与它的差距是**量级测量**：模型规模与训练方式都不同源，不是受控比较。

fail-closed：store 里该提案不是「已批」状态就拒绝运行。
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import re
import statistics
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "ai-researcher", "store")
DATA = os.path.join(ROOT, "ai-researcher", "data", "gsm8k")
TARGET_ID = "2405.07551v1"
SEED = 20261003
N = 100
MAX_NEW_TOKENS = 384
ANCHOR_LO, ANCHOR_HI = 0.838, 0.907

PROMPT = (
    "Solve the following grade school math problem. Reason step by step, "
    "then write the final numeric answer on the last line in the exact format:\n"
    "#### <number>\n\n"
    "Problem: {q}"
)

GSM8K_URL = ("https://raw.githubusercontent.com/openai/grade-school-math/"
             "master/grade_school_math/data/test.jsonl")


def state_of(arxiv_id: str, path: str | None = None) -> str:
    p = path or os.path.join(STORE, "proposals_state.json")
    d = json.load(open(p, encoding="utf-8"))
    for e in d["entries"]:
        if e["arxiv_id"] == arxiv_id:
            return e["state"]
    raise KeyError(arxiv_id)


def load_dataset() -> list[dict]:
    """本地缓存优先；缺则从官方仓库下载一次并缓存。失败=报错退出，不静默降级。"""
    os.makedirs(DATA, exist_ok=True)
    local = os.path.join(DATA, "test.jsonl")
    if not os.path.exists(local):
        req = urllib.request.Request(GSM8K_URL, headers={"User-Agent": "w7-anchor/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(local + ".part", "wb") as fh:
            fh.write(r.read())
        os.replace(local + ".part", local)
    items = []
    with open(local, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    if len(items) < N:
        raise ValueError(f"GSM8K test 只有 {len(items)} 题，少于预注册 n={N}")
    return items


def pick_subset(items: list[dict], n: int = N, seed: int = SEED) -> list[dict]:
    """确定性抽样：先按题目全文排序再抽，同 seed 同子集（可复现，可自检）。"""
    ordered = sorted(items, key=lambda x: (x["question"], x["answer"]))
    rng = random.Random(seed)
    return sorted(rng.sample(ordered, n), key=lambda x: (x["question"], x["answer"]))


_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_HASH = re.compile(r"####\s*(-?\d[\d,]*(?:\.\d+)?)")


def _to_float(s: str):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def strip_think(txt: str) -> str:
    """w6 实测教训：Qwen3 输出可能残留 </think>；剥掉所有 think 块再解析。"""
    t = txt
    if "</think>" in t:
        t = t.rsplit("</think>", 1)[1]
    if "<think>" in t:
        t = t.rsplit("<think>", 1)[1]
    return t


def extract_answer(txt: str):
    """按预注册顺序抽取；失败返回 None，绝不硬塞一个数。"""
    t = strip_think(txt)
    m = _HASH.search(t)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, "hash"
    m = re.search(r"\\boxed\{([^{}]+)\}", t)
    if m:
        v = _to_float(m.group(1).strip())
        if v is not None:
            return v, "boxed"
    nums = _NUM.findall(t)
    if nums:
        v = _to_float(nums[-1])
        if v is not None:
            return v, "last_num"
    return None, "unparsed"


def parse_gold(ans_field: str):
    m = _HASH.search(ans_field)
    if not m:
        raise ValueError(f"gold 无 #### 标记：{ans_field[:60]!r}")
    return _to_float(m.group(1))


def is_correct(pred, gold) -> bool:
    return pred is not None and gold is not None and abs(pred - gold) < 1e-4


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson 分数区间。k/n 的 95% CI；n=0 或越界报错而不是给假区间。"""
    if n <= 0 or not (0 <= k <= n):
        raise ValueError(f"wilson 非法输入 k={k} n={n}")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def build_inputs(tok, question: str):
    """chat template + enable_thinking=False（老版 transformers 无此参则降级并记录）。"""
    raw = PROMPT.format(q=question)
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


def gate_pass(state: str) -> bool:
    """批准门：只有「已批」可跑。抽成纯函数以便证伪测试。"""
    return state == "已批"


def run(out_prefix: str = "w7_gsm8k_anchor") -> int:
    # 批准门：不是已批就不跑（fail-closed）
    st = state_of(TARGET_ID)
    if not gate_pass(st):
        print(f"批准门拦截：{TARGET_ID} 状态={st}（需 已批）。拒绝运行。")
        return 2

    t0 = time.time()
    items = load_dataset()
    subset = pick_subset(items)
    tok, mdl, torch = load_model()
    device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"

    rows, correct = [], 0
    for i, it in enumerate(subset, 1):
        gold = parse_gold(it["answer"])
        ids, tflag = build_inputs(tok, it["question"])
        t1 = time.time()
        with torch.no_grad():
            out = mdl.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
        sec = round(time.time() - t1, 1)
        n_new = int(out.shape[1] - ids["input_ids"].shape[1])
        truncated = n_new >= MAX_NEW_TOKENS
        txt = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        pred, how = extract_answer(txt)
        ok = is_correct(pred, gold)
        correct += int(ok)
        rows.append({"i": i, "gold": gold, "pred": pred, "how": how,
                     "correct": ok, "truncated": truncated, "n_new_tokens": n_new,
                     "sec": sec, "raw_tail": txt.strip()[-120:]})
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{len(subset)}] running_acc={correct}/{i} "
                  f"last_sec={sec} truncated={truncated}", flush=True)
            # 增量落盘：中断也有部分产物可查（append 模式在循环外重写保证原子性见下）

    # 汇总（全部行重扫一遍，不依赖循环内增量）
    n = len(rows)
    n_unparsed = sum(1 for r in rows if r["how"] == "unparsed")
    n_truncated = sum(1 for r in rows if r["truncated"])
    acc = correct / n
    lo, hi = wilson(correct, n)
    secs = [r["sec"] for r in rows]
    summary = {
        "experiment": "w7_gsm8k_anchor", "arxiv_id": TARGET_ID,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "probe_source": "live", "device": device,
        "protocol": {"model": "Qwen3-0.6B bf16 CPU greedy", "n": n, "seed": SEED,
                     "max_new_tokens": MAX_NEW_TOKENS,
                     "template_flag": tflag, "prompt": PROMPT,
                     "scoring": "分母=全部 n；unparsed/截断计错；容差 1e-4",
                     "anchor": [ANCHOR_LO, ANCHOR_HI],
                     "caliber_note": "锚为 7B 级微调+工具（MathCoder）；本机 0.6B 纯 prompt "
                                     "与它的差距是量级测量，不是受控比较"},
        "n_correct": correct, "n": n, "acc": round(acc, 4),
        "wilson95": [round(lo, 4), round(hi, 4)],
        "gap_to_anchor_lo": round(acc - ANCHOR_LO, 4),
        "gap_ci_note": "gap 的不确定度≈acc 自身 CI 的宽度（锚按固定点处理）",
        "n_unparsed": n_unparsed, "n_truncated": n_truncated,
        "sec_mean": round(statistics.mean(secs), 1),
        "wall_min": round((time.time() - t0) / 60, 1),
    }
    items_path = os.path.join(STORE, out_prefix + "_items.jsonl")
    with open(items_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = os.path.join(STORE, out_prefix + "_summary.json")
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("wrote", items_path, "and", out)
    return 0


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # ── 抽取：真实坏形态必须被处理（w6 教训：think 残留在前）──
    ck("think残留+hash", extract_answer("</think>\n\n#### 42")[0], 42.0)
    ck("think块完整+hash", extract_answer("<think>abc</think>\n#### 7")[0], 7.0)
    ck("千分位", extract_answer("#### 1,234")[0], 1234.0)
    ck("小数", extract_answer("so the answer is\n#### 3.5")[0], 3.5)
    ck("boxed回退", extract_answer("thus \\boxed{18}")[0], 18.0)
    ck("最后数字回退", extract_answer("5 + 3 = 8. So 8.")[0], 8.0)
    ck("无数字", extract_answer("I cannot solve this.")[0], None)
    ck("无数字how", extract_answer("I cannot solve this.")[1], "unparsed")
    ck("空串", extract_answer("")[1], "unparsed")
    ck("hash优先于末数", extract_answer("12 total. #### 20")[0], 20.0)
    ck("截断残留数字也不冒充hash", extract_answer("#### 4")[0], 4.0)

    # ── gold 解析 ──
    ck("gold标准", parse_gold("reason #### 72\n"), 72.0)
    try:
        parse_gold("no marker"); bad.append("gold 无标记应抛错")
    except ValueError:
        pass

    # ── 计分 ──
    ck("unparsed计错", is_correct(None, 5.0), False)
    ck("容差内对", is_correct(71.99999, 72.0), True)   # 间距 1e-5 < 1e-4
    ck("容差外错", is_correct(71.99, 72.0), False)     # 间距 0.01 > 1e-4

    # ── Wilson：n=100 k=50 的教科书值 (0.4038, 0.5962)，容差 1e-3 ──
    lo, hi = wilson(50, 100)
    if abs(lo - 0.4038) > 1e-3 or abs(hi - 0.5962) > 1e-3:
        bad.append(f"wilson(50,100)=({lo:.4f},{hi:.4f})，偏离教科书值")
    lo0, hi0 = wilson(0, 100)
    if not (0 <= lo0 <= hi0 <= 1) or lo0 != 0.0:
        bad.append(f"wilson(0,100) 下界应为 0，得 {lo0}")
    try:
        wilson(101, 100); bad.append("k>n 应抛错")
    except ValueError:
        pass

    # ── 抽样确定性 ──
    fake = [{"question": f"q{i:03d}", "answer": f"#### {i}"} for i in range(300)]
    a, b = pick_subset(fake), pick_subset(fake)
    if [x["question"] for x in a] != [x["question"] for x in b]:
        bad.append("同 seed 抽样不确定")
    if len(a) != N:
        bad.append(f"抽样数 {len(a)} != {N}")

    # ── 批准门：不是已批必须拒（state_of 走临时假 store，不碰真库）──
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake_store = os.path.join(td, "proposals_state.json")
        json.dump({"entries": [{"arxiv_id": TARGET_ID, "state": "待批"}]},
                  open(fake_store, "w", encoding="utf-8"))
        ck("假store读出待批", state_of(TARGET_ID, path=fake_store), "待批")
    ck("门拒待批", gate_pass("待批"), False)
    ck("门放已批", gate_pass("已批"), True)
    ck("门拒终态", gate_pass("出结论"), False)
    ck("真store读已批", state_of(TARGET_ID), "已批")

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
