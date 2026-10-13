#!/usr/bin/env python3
"""W6 选型闸：同一个真实 NoMIRACL 判定任务，不同模型各跑同几条，比速度与准确率。

前一轮 probe_w6_nomiracl_rate.py 只测了 Qwen3-4B：54.45 s/judgement ⇒ 英文全量 13.7 天、
18 语 246 天，纯 CPU 下不可行。但 246 天是「拿 4B 模型跑 18 语全量」这一种选择的代价，
不是任务的代价。选型（更小模型 / 少采样 / 换指标口径）都是自由的，必须实测比。

本脚本：
  1. 从本地 cache 读真 topics/qrels/corpus（不重下）；
  2. 对每个候选模型跑**同一批**真实 judgement（同一 qid+docid，配对比较）；
  3. 同时报延迟与在配对样本上的准确率 —— 小模型快但答错，快是没用的；
  4. 落盘 JSON，供 critic.py 的重算门消费。

fail-closed：模型加载失败 → 该模型不参与比较，记失败原因，不静默跳过。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import statistics
import sys
import time

CACHE = os.path.join(os.getcwd(), "ai-researcher/data/nomiracl_cache")
LANG = "english"

# NoMIRACL 官方判定任务（与官方 prompts 语义一致）
PROMPT = (
    "You are given a question and a passage. Answer yes if the passage "
    "contains information that can help answer the question, otherwise answer no.\n"
    "Question: {q}\nPassage: {p}\nAnswer (yes or no):"
)

MODELS = {
    "qwen3-4b": os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-4B/snapshots/*"),
    "qwen3-1.7b": os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-1.7B/snapshots/*"),
    "qwen3-0.6b": os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/*"),
}


def _rd(name):
    with open(os.path.join(CACHE, name), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                yield line


def load_split(subset: str):
    topics = {}
    for line in _rd(f"{LANG}_topics_{subset}.tsv"):
        qid, _, q = line.partition("\t")
        topics[qid] = q
    qrels = {}
    for line in _rd(f"{LANG}_qrels_{subset}.tsv"):
        p = line.split("\t")
        if len(p) == 4:
            qid, docid, rel = p[0], p[2], p[3]
        elif len(p) == 3:
            qid, docid, rel = p[0], p[1], p[2]
        else:
            continue
        qrels.setdefault(qid, {})[docid] = int(rel)
    return topics, qrels


def load_corpus() -> dict:
    import gzip
    corpus = {}
    with gzip.open(os.path.join(CACHE, f"{LANG}_corpus.jsonl.gz"),
                   "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            corpus[obj["docid"]] = obj.get("text", "")
    return corpus


def build_samples(n: int, seed: int = 20261003):
    """配对样本：从 relevant 子集取含正例的查询，每查询 1 正 + 1 负。

    只用 relevant 子集是因为 non_relevant 子集**全是 rel=0**（实测 3420 条 judgement
    无一 rel1），单独用它只能测 error rate，测不到 hallucination rate 的正负对比。
    """
    topics, qrels = load_split("relevant")
    corpus = load_corpus()
    rng = random.Random(seed)
    cands = []
    for qid, docs in qrels.items():
        if qid not in topics:
            continue
        pos = [d for d, r in docs.items() if r == 1 and d in corpus]
        neg = [d for d, r in docs.items() if r == 0 and d in corpus]
        if pos and neg:
            cands.append((qid, pos, neg))
    cands.sort()                      # 确定性：先排序再抽样
    picked = cands if n >= len(cands) else rng.sample(cands, n)
    picked.sort()
    samples = []
    for qid, pos, neg in picked:
        for rel, pool in ((1, pos), (0, neg)):
            docid = pool[0]
            samples.append({"qid": qid, "rel": rel, "docid": docid,
                            "query": topics[qid],
                            "passage": corpus[docid][:4000]})
    return samples, len(cands)


def load_model(key: str):
    snaps = glob.glob(MODELS[key])
    if not snaps:
        return None, f"快照不存在：{MODELS[key]}"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    try:
        tok = AutoTokenizer.from_pretrained(snaps[0])
        mdl = AutoModelForCausalLM.from_pretrained(snaps[0],
                                                  dtype=torch.bfloat16)
        mdl = mdl.to("cpu")
        mdl.eval()
        return (tok, mdl), None
    except Exception as exc:
        return None, repr(exc)[:200]


def parse_yes(txt: str):
    """从生成文本里取答案。

    实测教训（2026-10-03 第二轮）：只看生成窗口的**开头**会把 thinking 模型的答案
    判成「无法解析」。Qwen3 即使 enable_thinking=False，模板末尾仍带 `</think>\n\n`，
    答案在它**之后**。首版按「取末尾 4 token + startswith 判定」实现，结果 0.6B
    16 条里 15 条 `raw='</think>\n\nyes'` 全被判 None ⇒ acc 只剩 1/1=1.0，
    一个假信号；而 1.7B acc=0.444 是 9 条样本上的值，与 4B 的 15 条不可比。

    正确做法：先剥掉 `<think>...</think>` 前缀（可能有多段、可能有开标签残留），
    再判定 yes/no，并且**只判第一个词**。
    """
    t = txt
    # 去掉所有闭合 think 标签之前的内容
    if "</think>" in t:
        t = t.rsplit("</think>", 1)[1]
    # 去掉可能存在的开标签（模型自行开启 thinking）
    if "<think>" in t:
        t = t.rsplit("<think>", 1)[1]
    t = t.strip().strip(":*： 	")
    low = t.lower()
    words = low.split()
    first = words[0].strip(".,:;!?\"'()") if words else ""
    if first == "yes":
        return 1
    if first == "no":
        return 0
    # 找不到明确 yes/no → 无法判定，单列，绝不塞 0/1 充数
    return None


def build_inputs(tok, question: str, passage: str):
    """必须走 chat template 且关掉 thinking。

    实测教训（2026-10-03）：Qwen3 系列是 **thinking 模型**。裸补全时
    下一 token 的 top-5 全是 '\\n' / '?\\n'（Qwen3-0.6B 实测最高 22.75 分），
    因为模型要先把答案写进 <think> 块；实测 0.6B 16 条 judgement **全部输出空串**，
    而同一条加 chat template + enable_thinking=False 后 5.8 秒就吐出 'yes'。
    也就是说：不套 template 测出来的「小模型答不出」是**测量方法的错**，
    不是模型能力的差异 —— 拿它去选型会选出一个根本没被测过的模型。
    """
    raw = PROMPT.format(q=question, p=passage)
    try:
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        # 老版本 transformers 没有 enable_thinking 参数；记录降级，不静默改变协议
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
            tokenize=False, add_generation_prompt=True)
    return tok(text, return_tensors="pt")


def run_model(key: str, samples: list, max_new_tokens: int = 16) -> dict:
    t0 = time.time()
    loaded, err = load_model(key)
    if err:
        return {"model": key, "ok": False, "why": err}
    tok, mdl = loaded
    import torch
    t_load = time.time() - t0
    rows = []
    for s in samples:
        ids = build_inputs(tok, s["query"], s["passage"])
        t1 = time.time()
        with torch.no_grad():
            out = mdl.generate(**ids, max_new_tokens=max_new_tokens,
                               do_sample=False)
        dt = time.time() - t1
        txt = tok.decode(out[0][-max_new_tokens:], skip_special_tokens=True)
        rows.append({**{k: s[k] for k in ("qid", "rel", "docid")},
                     "prompt_tokens": int(ids["input_ids"].shape[1]),
                     "sec": round(dt, 2), "pred": parse_yes(txt),
                     "raw": txt.strip()[:80]})
    secs = [r["sec"] for r in rows]
    judged = [r for r in rows if r["pred"] is not None]
    n_unparsed = len(rows) - len(judged)
    acc = (sum(1 for r in judged if r["pred"] == r["rel"]) / len(judged)
           if judged else None)
    # 两个子指标（NoMIRACL 原定义）：非相关子集=hallucination，这里用 rel=0 样本近似
    neg = [r for r in judged if r["rel"] == 0]
    pos = [r for r in judged if r["rel"] == 1]
    return {
        "model": key, "ok": True, "load_s": round(t_load, 1),
        "n": len(rows), "n_judged": len(judged), "n_unparsed": n_unparsed,
        "sec_mean": round(statistics.mean(secs), 2),
        "sec_min": round(min(secs), 2), "sec_max": round(max(secs), 2),
        "acc": round(acc, 4) if acc is not None else None,
        "hallucination_rate_on_neg": (
            round(sum(1 for r in neg if r["pred"] == 1) / len(neg), 4)
            if neg else None),
        "miss_rate_on_pos": (
            round(sum(1 for r in pos if r["pred"] == 0) / len(pos), 4)
            if pos else None),
        "speedup_vs_first": None, "rows": rows,
    }


def selftest() -> int:
    """解析器必须能被证伪。判据：喂进真实见过的形态，错答必须暴露。

    反证设计的关键：不能只测「对的样子」，必须测「实际观测到的坏样子」。
    本轮真实踩到两种：thinking 标签残留（'</think>\\n\\nyes'）与
    带句号的答案（'Yes.' / 'No. The passage'）。
    """
    cases = [
        # (输入, 期望, 说明)
        ("</think>\n\nyes", 1, "thinking 标签残留在前（0.6B 实测形态）"),
        ("</think>\n\nYes", 1, "大写 + think 残留"),
        ("Yes.", 1, "带句号（4B 实测形态）"),
        ("No. The passage", 0, "否定答案后跟解释（4B 实测形态）"),
        ("no\n\nThe passage", 0, "小写换行后接解释（1.7B 实测形态）"),
        ("<think>\nlet me see</think>\n\nno", 0, "完整 think 对"),
        ("<think>a</think><think>b</think>\n\nyes", 1, "多段 think，取最后一段之后"),
        ("  \n\n: Yes :", 1, "前后噪声与冒号"),
        ("maybe", None, "不含 yes/no ⇒ 必须 None，绝不塞 0/1"),
        ("", None, "空串 ⇒ None"),
        ("nonsense", None, "无关串 ⇒ None（不能因为含字母 n 就判 no）"),
        ("knowledge", None, "含字母 n 但不是答案 ⇒ None（不能 startswith('n') 裸判）"),
    ]
    bad = []
    for text, want, why in cases:
        got = parse_yes(text)
        if got != want:
            bad.append(f"{why}: parse_yes({text!r}) = {got}，期望 {want}")
    # 计数门：不可判定的不能悄悄变成 0/1
    for text in ("maybe", "", "knowledge"):
        if parse_yes(text) in (0, 1):
            bad.append(f"不可判定被塞进 0/1：{text!r}")
    print(f"selftest: {len(cases) - len(bad)}/{len(cases)} 通过")
    for b in bad:
        print("  FAIL", b)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=8, help="配对查询数（每查询 1 正 1 负）")
    ap.add_argument("--models", default="qwen3-0.6b,qwen3-1.7b,qwen3-4b")
    ap.add_argument("--out", default="ai-researcher/store/w6_model_bakeoff.json")
    args = ap.parse_args()

    samples, n_cands = build_samples(args.n)
    rep = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "probe_source": "live", "lang": LANG,
           "n_query_paired": args.n, "n_candidates_usable": n_cands,
           "n_judgements": len(samples), "prompt_template": PROMPT,
           "results": []}

    base = None
    for key in args.models.split(","):
        r = run_model(key, samples)
        rep["results"].append(r)
        print(f"[{key}] ok={r.get('ok')} "
              f"acc={r.get('acc')} mean_s={r.get('sec_mean')} "
              f"why={str(r.get('why'))[:90]}", flush=True)
        if r.get("ok") and base is None:
            base = r["sec_mean"]

    for r in rep["results"]:
        if r.get("ok") and base:
            r["speedup_vs_first"] = round(base / r["sec_mean"], 2)

    # 选型结论只从实测值推；全灭则诚实报不可行
    ok = [r for r in rep["results"] if r.get("ok")]
    if ok:
        fastest = min(ok, key=lambda r: r["sec_mean"])
        best_acc = max(ok, key=lambda r: (r["acc"] if r["acc"] is not None else -1))
        rep["verdict"] = {
            "fastest": fastest["model"],
            "fastest_sec": fastest["sec_mean"],
            "best_acc": best_acc["model"], "best_acc_value": best_acc["acc"],
            "english_full_days_at_fastest": round(
                21661 * fastest["sec_mean"] / 86400, 2),
            "note": "秒数按 n_judgements 线性外推，仅为量级判断，非承诺",
        }
    else:
        rep["verdict"] = {"all_models_failed": True}

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)
    print(json.dumps(rep.get("verdict", {}), ensure_ascii=False, indent=2))
    print("wrote", args.out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())