#!/usr/bin/env python3
"""W9：NoMIRACL 多语相关性判定（迷你口径，预注册协议）。

## 预注册协议（跑批前钉死，修订必须入档理由+时间戳且不动计分）

- **任务**：NoMIRACL 相关性判定——给定 query 与 passage，判断该 passage 是否
  含回答 query 所需信息，输出 yes/no。这是提案 2312.11361v3 开放问题的前半
  （「判断任务非端到端」）；**不做端到端检索**（语料里直接给了正/负 passage），
  端到端半边保持开放，不得在结论里假装测了。
- **模型**：Qwen3-0.6B，bf16，CPU 贪心（do_sample=False），本地快照 glob 加载，
  max_new_tokens=16。**必须**走 apply_chat_template 且 enable_thinking=False——
  W6 实测裸补全下一 token top-5 全是 '\\n'（最高 22.75 分），0.6B 16 条全输出空串。
- **语言**：english / chinese / swahili（高/高/低资源，三种文字；数据已在
  data/nomiracl_cache/，hf-mirror 下载路径 W6 已验证）。
- **子集**：每语 relevant 子集抽 30 个 query（取其第一个 rel=1 passage），
  non_relevant 子集抽 30 个 query（其 passage 全部 rel=0，取第一个）。
  seed=20261003，先 sorted 再 sample（确定性，W7 纪律）。
- **指标**（每语各一格，分母=全部 n，unparsed 计为判官失败=错，W7 纪律）：
  - hallucination_rate = 判 yes 的比例（non_relevant 子集；全 rel=0 ⇒ 判 yes 即幻觉）
  - error_rate = 判 no 或无法解析的比例（relevant 子集；该 passage 是正例）
  - 每格 Wilson 95% CI（w6_significance 教训：n 小必须带区间）。
- **解析**：剥 `</think>` 前缀后取第一个完整词，yes/no 之外一律 None
  （'nonsense' 不得因以 n 开头判成 no——w6 selftest 反证钉过）。
- **锚**：store/w9_anchor_nomiracl.json（Llama-3-8B-Instruct / Mistral-7B-Instruct，
  论文 table 6 w/o SFT 列，均值与 table 3 核对一致）。**不同模型类别+不同 prompt
  协议 ⇒ 只做量级对照**；结论禁用「复现/达到/超过」。
- **判读语义**：跨语言是**独立样本**（不同 query），不做 McNemar；n=30/语很小，
  verdict=directional 仅当某指标某语言对的 Wilson 区间真正分离，否则
  report_numbers_only。
- **fail-closed**：store 状态机里 2312.11361v3 必须是「已批」才允许跑
  （gate_pass，rc=2）；语料/题目文件缺失即停，不猜。
- **断点续跑**：每题 append 到 store/w9_items.jsonl，重跑按 (lang,subset,i) 跳过
  已完成行（W8 教训：长跑必须可续）。

## 修订记录

- 2026-10-04 首版（跑批前；无结果数据，无需入档修订）。
- 2026-10-04T15:55+08:00 summarize 锚查表修复（**无结果数据期**：180 条 items 已
  采集、summary 因 KeyError 未产出，prompt/计分/抽样一字未动）。理由：锚 JSON
  语言键是 ISO 码 `en/zh/sw`（store/w9_anchor_nomiracl.json 实测内层键），代码用
  全名查表 KeyError('english')；契约键跟随产物真实形状（L-ops-158）。加
  LANG2CODE 映射，selftest 补第 7 组锚查表断言。
- 2026-10-04T16:00+08:00 锚单位修复（仍无结果数据：summary 将重算，items 不动）。
  锚 JSON 存论文原表**百分数**（19.2=19.2%，avg_check 同口径），我方 rate 是
  [0,1] 小数；直减出 anchor_gap=−18.3 垃圾值。修：查表后 /100；selftest 加
  第 8 组断言「锚值全 >1 ⇒ 百分数约定成立」（若未来重提取改存小数，selftest
  会拦住）。
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # 仓库根
PKG = os.path.join(ROOT, "ai-researcher", "src")
sys.path.insert(0, PKG)
CACHE = os.path.join(ROOT, "ai-researcher", "data", "nomiracl_cache")
OUT_ITEMS = os.path.join(ROOT, "ai-researcher", "store", "w9_items.jsonl")
OUT_SUMMARY = os.path.join(ROOT, "ai-researcher", "store", "w9_summary.json")
STATE_PATH = os.path.join(ROOT, "ai-researcher", "store", "proposals_state.json")
ARXIV_ID = "2312.11361v3"

LANGS = ("english", "chinese", "swahili")
# 锚 JSON（store/w9_anchor_nomiracl.json）语言键是 ISO 码；此处做全名→码映射
LANG2CODE = {"english": "en", "chinese": "zh", "swahili": "sw"}
N_PER_SUBSET = 30
SEED = 20261003
MAX_NEW_TOKENS = 16
MODEL_GLOB = os.path.expanduser(
    "~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/*")
PROMPT = ("You are given a question and a passage. Answer yes if the passage "
          "contains information that can help answer the question, otherwise "
          "answer no.\nQuestion: {q}\nPassage: {p}\nAnswer (yes or no):")


def gate_pass(state_path: str = STATE_PATH) -> None:
    """fail-closed：提案必须是「已批」。非已批 ⇒ SystemExit(2)。"""
    d = json.load(open(state_path, encoding="utf-8"))
    for e in d["entries"]:
        if e["arxiv_id"] == ARXIV_ID:
            if e["state"] != "已批":
                sys.stderr.write("gate_pass: %s 状态=%s，非「已批」禁止跑批\n"
                                 % (ARXIV_ID, e["state"]))
                sys.exit(2)
            return
    sys.stderr.write("gate_pass: 状态机里找不到 %s\n" % ARXIV_ID)
    sys.exit(2)


def parse_yes(txt: str):
    """W6 纪律：剥 think 标签 → 第一个完整词；非 yes/no ⇒ None。"""
    t = txt
    if "</think>" in t:
        t = t.rsplit("</think>", 1)[1]
    if "<think>" in t:
        t = t.rsplit("<think>", 1)[1]
    t = t.strip().strip(":*： \t")
    words = t.split()
    first = words[0].strip(".,:;!?\"'()").lower() if words else ""
    if first == "yes":
        return 1
    if first == "no":
        return 0
    return None


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def read_tsv(name: str) -> list[list[str]]:
    p = os.path.join(CACHE, name)
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    return [l.rstrip("\n").split("\t")
            for l in open(p, encoding="utf-8") if l.strip()]


def load_lang(lang: str) -> dict:
    """返回 {relevant: [(qid, query, docid, text)], non_relevant: [...]}。

    TREC 4 列 qrels：qid Q0 docid rel（3 列回退 qid docid rel）。
    """
    topics, qrels, corpus = {}, {}, {}
    for sub in ("relevant", "non_relevant"):
        # 缓存命名：{lang}_topics_{sub}.tsv / {lang}_qrels_{sub}.tsv（无 test. 中缀；
        # 首版曾写 _test. 前缀与实际文件名不符 → FileNotFoundError，已统一）
        for parts in read_tsv(f"{lang}_topics_{sub}.tsv"):
            topics.setdefault(sub, {})[parts[0]] = parts[1]
        for parts in read_tsv(f"{lang}_qrels_{sub}.tsv"):
            qid, docid, rel = ((parts[0], parts[2], parts[3]) if len(parts) == 4
                               else (parts[0], parts[1], parts[2]))
            qrels.setdefault(sub, {}).setdefault(qid, {})[docid] = int(rel)
    with gzip.open(os.path.join(CACHE, f"{lang}_corpus.jsonl.gz"),
                   "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                obj = json.loads(line)
                corpus[obj["docid"]] = obj.get("text", "")
    return {"topics": topics, "qrels": qrels, "corpus": corpus}


def pick_subset(lang_data: dict, subset: str, n: int, seed: int) -> list[dict]:
    """确定性抽样：候选按 (qid, docid) 排序后 sample。"""
    topics, qrels, corpus = (lang_data["topics"][subset],
                             lang_data["qrels"][subset], lang_data["corpus"])
    want_rel = 0 if subset == "non_relevant" else 1
    cands = []
    for qid in sorted(set(topics) & set(qrels)):
        docs = qrels[qid]
        if qid not in topics:
            continue
        for docid in sorted(docs):
            if docs[docid] == want_rel and docid in corpus:
                cands.append((qid, docid))
                break
    cands.sort()
    rng = random.Random(seed)
    picked = cands if n >= len(cands) else rng.sample(cands, n)
    picked.sort()
    return [{"qid": qid, "docid": docid, "query": topics[qid],
             "passage": corpus[docid][:4000]} for qid, docid in picked]


def load_model():
    snaps = glob.glob(MODEL_GLOB)
    if not snaps:
        raise FileNotFoundError("Qwen3-0.6B 快照不存在: " + MODEL_GLOB)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(snaps[0])
    mdl = AutoModelForCausalLM.from_pretrained(snaps[0], dtype=torch.bfloat16)
    mdl = mdl.to("cpu")
    mdl.eval()
    return tok, mdl


def build_inputs(tok, question: str, passage: str):
    raw = PROMPT.format(q=question, p=passage)
    try:
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        text = tok.apply_chat_template(
            [{"role": "user", "content": raw}],
            tokenize=False, add_generation_prompt=True)
    return tok(text, return_tensors="pt")


def existing_done() -> set:
    if not os.path.exists(OUT_ITEMS):
        return set()
    done = set()
    for l in open(OUT_ITEMS, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            done.add((r["lang"], r["subset"], r["i"]))
    return done


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    gate_pass()
    plan = []
    for lang in LANGS:
        ld = load_lang(lang)
        for subset in ("relevant", "non_relevant"):
            for i, s in enumerate(pick_subset(ld, subset, N_PER_SUBSET, SEED), 1):
                plan.append({"lang": lang, "subset": subset, "i": i,
                             "qid": s["qid"], "docid": s["docid"],
                             "query": s["query"], "passage": s["passage"]})
    done = existing_done()
    todo = [p for p in plan if (p["lang"], p["subset"], p["i"]) not in done]
    print(f"计划 {len(plan)} 条，已完成 {len(plan)-len(todo)}，待跑 {len(todo)}",
          flush=True)
    if not todo:
        print("全部已完成，直接汇总")
        return summarize()

    import torch
    t0 = time.time()
    tok, mdl = load_model()
    print(f"模型加载 {time.time()-t0:.1f}s", flush=True)
    with open(OUT_ITEMS, "a", encoding="utf-8") as fh:
        for p in todo:
            ids = build_inputs(tok, p["query"], p["passage"])
            t1 = time.time()
            with torch.no_grad():
                out = mdl.generate(**ids, max_new_tokens=MAX_NEW_TOKENS,
                                   do_sample=False)
            sec = round(time.time() - t1, 2)
            txt = tok.decode(out[0][-MAX_NEW_TOKENS:], skip_special_tokens=True)
            row = {**{k: p[k] for k in ("lang", "subset", "i", "qid", "docid")},
                   "n_prompt_tokens": int(ids["input_ids"].shape[1]),
                   "sec": sec, "pred": parse_yes(txt),
                   "raw_tail": txt.strip()[:80]}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[{p['lang']} {p['subset']} {p['i']}/{N_PER_SUBSET}] "
                  f"pred={row['pred']} {sec}s", flush=True)
    return summarize()


def summarize() -> int:
    rows = [json.loads(l) for l in open(OUT_ITEMS, encoding="utf-8") if l.strip()]
    summary = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "arxiv_id": ARXIV_ID, "n_per_subset": N_PER_SUBSET,
               "seed": SEED, "langs": list(LANGS),
               "cells": {}, "anchor_gap": {}}
    anchors = json.load(open(os.path.join(ROOT, "ai-researcher", "store",
                                          "w9_anchor_nomiracl.json"),
                             encoding="utf-8"))
    for lang in LANGS:
        for subset in ("relevant", "non_relevant"):
            rs = [r for r in rows if r["lang"] == lang and r["subset"] == subset]
            n = len(rs)
            if not n:
                continue
            if subset == "non_relevant":
                k = sum(1 for r in rs if r["pred"] == 1)
                cell = "hallucination_rate"
            else:
                k = sum(1 for r in rs if r["pred"] != 1)   # no 或 unparsed 都算错
                cell = "error_rate"
            lo, hi = wilson(k, n)
            summary["cells"][f"{lang}.{cell}"] = {
                "k": k, "n": n, "rate": round(k / n, 4),
                "wilson95": [round(lo, 4), round(hi, 4)],
                "n_unparsed": sum(1 for r in rs if r["pred"] is None),
                "sec_mean": round(statistics.mean([r["sec"] for r in rs]), 2)}
    # 锚差（量级对照）
    for key, cell in (("hallucination_rate_non_relevant", "hallucination_rate"),
                      ("error_rate_relevant", "error_rate")):
        for model in ("llama3_8b", "mistral_7b"):
            for lang in LANGS:
                mine = summary["cells"].get(f"{lang}.{cell}")
                if mine:
                    # 锚 JSON 是百分数（19.2 = 19.2%），我方 rate 是小数 ⇒ /100
                    summary["anchor_gap"][f"{lang}.{cell}.{model}"] = round(
                        mine["rate"] - anchors[key][model][LANG2CODE[lang]] / 100.0,
                        4)
    # verdict：directional 仅当某指标某语言对区间分离
    pairs = []
    for cell in ("hallucination_rate", "error_rate"):
        cs = [(l, summary["cells"][f"{l}.{cell}"]) for l in LANGS
              if f"{l}.{cell}" in summary["cells"]]
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                a, b = cs[i][1], cs[j][1]
                sep = a["wilson95"][1] < b["wilson95"][0] or \
                      b["wilson95"][1] < a["wilson95"][0]
                pairs.append({"cell": cell, "pair": f"{cs[i][0]}-{cs[j][0]}",
                              "separated": sep})
    summary["pairwise_separation"] = pairs
    summary["verdict"] = ("directional" if any(p["separated"] for p in pairs)
                          else "report_numbers_only")
    json.dump(summary, open(OUT_SUMMARY, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("verdict:", summary["verdict"])
    print("wrote", OUT_SUMMARY)
    return 0


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # 1. parse_yes：W6 真实形态
    ck("think 残留 yes", parse_yes("</think>\n\nyes"), 1)
    ck("带句号 No", parse_yes("No. The passage"), 0)
    ck("nonsense ⇒ None", parse_yes("nonsense"), None)
    ck("空串 ⇒ None", parse_yes(""), None)
    ck("完整 think 对", parse_yes("<think>a</think>\n\nno"), 0)

    # 2. Wilson 已知值（7/8）
    lo, hi = wilson(7, 8)
    ck("Wilson 7/8", (round(lo, 3), round(hi, 3)), (0.529, 0.978))

    # 3. 子集确定性：同 seed 同选；不同 seed 不同（大语料下大概率不同）
    ld = load_lang("english")
    a = pick_subset(ld, "relevant", 5, SEED)
    b = pick_subset(ld, "relevant", 5, SEED)
    c = pick_subset(ld, "relevant", 5, 999)
    ck("同 seed 确定性", [(x["qid"], x["docid"]) for x in a],
       [(x["qid"], x["docid"]) for x in b])
    ck("rel=1 过滤（relevant 子集全正例）",
       all(True for _ in a) and len(a) == 5, True)
    ck("不同 seed 不同（随机性存在）",
       [(x["qid"], x["docid"]) for x in a] != [(x["qid"], x["docid"]) for x in c],
       True)

    # 4. non_relevant 子集 rel 全 0
    nr = pick_subset(ld, "non_relevant", 5, SEED)
    ok = all(ld["qrels"]["non_relevant"][x["qid"]][x["docid"]] == 0 for x in nr)
    ck("non_relevant 全 rel=0", ok, True)

    # 5. 计分语义：non_relevant 判 yes=幻觉；relevant 判非 yes=错；unparsed 入分母
    rs = [{"pred": 1}, {"pred": 0}, {"pred": None}]
    k_h = sum(1 for r in rs if r["pred"] == 1)
    k_e = sum(1 for r in rs if r["pred"] != 1)
    ck("halluc 计分", (k_h, len(rs)), (1, 3))
    ck("error 计分（unparsed 计错）", (k_e, len(rs)), (2, 3))

    # 6. gate_pass：临时状态文件里非已批 ⇒ SystemExit(2)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"entries": [{"arxiv_id": ARXIV_ID, "state": "待批"}]}, fh)
        tmp = fh.name
    try:
        gate_pass(tmp)
        ck("gate_pass 拒绝非已批", "no-exit", "exit-2")
    except SystemExit as e:
        ck("gate_pass 拒绝非已批", e.code, 2)
    os.unlink(tmp)

    # 7. 锚查表契约：锚 JSON 语言键是 ISO 码（en/zh/sw），全名必须经 LANG2CODE
    fake_anchors = {"hallucination_rate_non_relevant": {
        "llama3_8b": {"en": 0.192, "zh": 0.644, "sw": 0.040}}}
    ck("锚查表（ISO 码）",
       fake_anchors["hallucination_rate_non_relevant"]["llama3_8b"][LANG2CODE["english"]],
       0.192)
    with open(os.path.join(ROOT, "ai-researcher", "store",
                           "w9_anchor_nomiracl.json"), encoding="utf-8") as fh:
        real = json.load(fh)
    ok = all(LANG2CODE[lang] in real[key][model]
             for key in ("hallucination_rate_non_relevant", "error_rate_relevant")
             for model in ("llama3_8b", "mistral_7b")
             for lang in LANGS)
    ck("真实锚 JSON 全部语言键可查", ok, True)

    # 8. 锚单位约定：全表值 >1 ⇒ 百分数（若改存小数此处必须拦住）
    vals = [v for key in ("hallucination_rate_non_relevant", "error_rate_relevant")
            for model in ("llama3_8b", "mistral_7b")
            for v in real[key][model].values()]
    ck("锚值全为百分数（>1）", all(v > 1 for v in vals), True)

    print(f"selftest: 失败 {len(bad)}")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())