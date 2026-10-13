#!/usr/bin/env python3
"""W6 真门槛实测：NoMIRACL 单语一条真查询，Qwen3-4B CPU 要多久？

前面的 probe 只测了 8 token 的玩具 prompt（0.2 tok/s）。NoMIRACL 的真实任务是
「给定若干 passage，判断该 passage 是否能回答 query，输出 yes/no」——prompt 长得多，
输出只有 1 个 token。所以总时长由 prefill 主导，不能用玩具数字外推。

本脚本下真实数据、真模型、真 prompt，输出每查询秒数 → 整语种/18 语种的墙钟预算。
数据源走 hf-mirror（huggingface.co 本机当前超时，已实测）。
"""
from __future__ import annotations

import glob
import gzip
import io
import json
import os
import sys
import time
import urllib.request

MIRROR = "https://hf-mirror.com/datasets/miracl/nomiracl/resolve/main"
LANG = "english"
MODEL_GLOB = os.path.expanduser(
    "~/.cache/huggingface/hub/models--Qwen--Qwen3-4B/snapshots/*")

# NoMIRACL 的官方判定任务：只看该 passage 能否回答 query，输出 yes/no
PROMPT = (
    "You are given a question and a passage. Answer yes if the passage "
    "contains information that can help answer the question, otherwise answer no.\n"
    "Question: {q}\nPassage: {p}\nAnswer (yes or no):"
)


def fetch(path: str) -> bytes:
    url = f"{MIRROR}/{path}"
    # 镜像对无 UA 的 urllib 直发 403（curl 默认 UA 则 200）⇒ 必须带 UA
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def load_subset(subset: str):
    topics = {}
    for line in fetch(f"data/{LANG}/topics/test.{subset}.tsv").decode("utf-8").splitlines():
        if not line.strip():
            continue
        qid, _, q = line.partition("\t")
        topics[qid] = q
    qrels = {}
    for line in fetch(f"data/{LANG}/qrels/test.{subset}.tsv").decode("utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        qid, _, docid, rel = parts[0], parts[1], parts[2], parts[3]
        qrels.setdefault(qid, {})[docid] = int(rel)
    return topics, qrels


def main() -> int:
    n_probe = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rep = {"lang": LANG, "n_probe": n_probe, "probe_source": "live"}

    t0 = time.time()
    try:
        topics_rel, qrels_rel = load_subset("relevant")
        topics_non, qrels_non = load_subset("non_relevant")
    except Exception as exc:
        rep["data_error"] = repr(exc)[:300]
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 1
    rep["download_s"] = round(time.time() - t0, 1)
    rep["n_queries"] = {"relevant": len(topics_rel), "non_relevant": len(topics_non)}
    rep["n_judgements"] = {
        "relevant": sum(len(v) for v in qrels_rel.values()),
        "non_relevant": sum(len(v) for v in qrels_non.values()),
    }

    snaps = glob.glob(MODEL_GLOB)
    if not snaps:
        rep["model_error"] = "Qwen3-4B 快照不存在"
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 1

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(snaps[0])
    mdl = AutoModelForCausalLM.from_pretrained(snaps[0], dtype=torch.bfloat16)
    mdl = mdl.to("cpu")
    mdl.eval()

    # 取真查询 + 真 passage 文本太重，先用 qrels 里的 docid，
    # 但 prompt 必须含真 passage 才代表真实 prefill 长度 ⇒ 下 corpus。
    corpus = {}
    raw = gzip.decompress(fetch(f"data/{LANG}/corpus.jsonl.gz")).decode("utf-8")
    for line in raw.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        corpus[obj["docid"]] = obj["text"]
    rep["corpus_docs"] = len(corpus)
    rep["corpus_bytes_raw"] = len(raw)

    samples = []
    for subset, (topics, qrels) in (("relevant", (topics_rel, qrels_rel)),
                                    ("non_relevant", (topics_non, qrels_non))):
        for i, (qid, docs) in enumerate(qrels.items()):
            if i >= n_probe:
                break
            for docid, rel in list(docs.items())[:1]:
                if docid in corpus:
                    samples.append({"subset": subset, "qid": qid,
                                    "query": topics.get(qid, ""), "rel": rel,
                                    "passage": corpus[docid]})
    rep["n_samples_built"] = len(samples)

    timings = []
    for s in samples:
        prompt = PROMPT.format(q=s["query"], p=s["passage"][:4000])
        ids = tok(prompt, return_tensors="pt")
        t1 = time.time()
        with torch.no_grad():
            out = mdl.generate(**ids, max_new_tokens=1, do_sample=False)
        dt = time.time() - t1
        ans = tok.decode(out[0][-1], skip_special_tokens=True).strip()
        timings.append({"subset": s["subset"], "rel": s["rel"],
                        "prompt_tokens": int(ids["input_ids"].shape[1]),
                        "sec": round(dt, 2), "pred": ans[:20]})

    rep["timings"] = timings
    secs = [t["sec"] for t in timings]
    rep["per_query_s"] = {
        "mean": round(sum(secs) / len(secs), 2) if secs else None,
        "min": min(secs) if secs else None, "max": max(secs) if secs else None,
    }
    n_en = rep["n_judgements"]["relevant"] + rep["n_judgements"]["non_relevant"]
    if rep["per_query_s"]["mean"]:
        per_lang_h = n_en * rep["per_query_s"]["mean"] / 3600
        rep["budget"] = {
            "english_judgements": n_en,
            "english_hours": round(per_lang_h, 1),
            "all_18_langs_hours": round(per_lang_h * 18, 1),
        }
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())