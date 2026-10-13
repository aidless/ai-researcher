#!/usr/bin/env python3
"""W6 可行性容量探测：不假设，只测。

问题：NoMIRACL 的两个指标（hallucination rate / error rate）都是**生成式**的，
需要真跑一个 LLM。本机 GPU 6GB（实测已用 3185 MiB），Qwen3-4B fp16 需 ~8GB。
所以真门槛不是显存而是「放得下吗、跑得动吗」。本脚本实测回答，不靠估算。

fail-closed：任何一步测不出来就报 UNKNOWN，绝不用估算值填坑。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

MODEL_DIR_GLOB = "~/.cache/huggingface/hub/models--Qwen--Qwen3-4B/snapshots/*"
VENV_PY = "/home/liuzewen/.venvs/w4-torch/bin/python"


def read_meminfo_gb() -> dict:
    out = {}
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable", "SwapTotal"):
                out[key] = round(int(rest.split()[0]) / 1024 / 1024, 2)
    return out


def read_gpu_mib() -> dict:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True)
        total, used = [int(x) for x in r.stdout.strip().split(",")]
        return {"present": True, "total_mib": total, "used_mib": used,
                "free_mib": total - used}
    except Exception as exc:                      # 探测失败 ≠ 显存为 0
        return {"present": False, "error": repr(exc)[:160]}


def model_files() -> dict:
    import glob
    snaps = glob.glob(os.path.expanduser(MODEL_DIR_GLOB))
    if not snaps:
        return {"found": False}
    snap = snaps[0]
    files = {}
    for name in os.listdir(snap):
        p = os.path.join(snap, name)
        if os.path.isfile(p):
            files[name] = os.path.getsize(p)
    idx = "model.safetensors.index.json"
    shards = sum(v for k, v in files.items() if k.endswith(".safetensors"))
    return {"found": True, "snapshot": snap, "n_files": len(files),
            "safetensors_bytes": shards,
            "has_index": idx in files, "has_tokenizer_json": "tokenizer.json" in files,
            "files": files}


def load_and_generate(device: str, max_new_tokens: int = 8) -> dict:
    """真加载真生成。返回耗时/峰值 RSS/首 token 文本。"""
    import glob
    import resource
    snaps = glob.glob(os.path.expanduser(MODEL_DIR_GLOB))
    if not snaps:
        return {"ok": False, "why": "快照目录不存在"}
    t0 = time.time()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        dtype = torch.bfloat16
        tok = AutoTokenizer.from_pretrained(snaps[0])
        # 不用 device_map：它会拖入 accelerate 依赖（本机未装），
        # 而单卡 .to(device) 足够，也少一个装不上的理由。
        mdl = AutoModelForCausalLM.from_pretrained(snaps[0], dtype=dtype)
        mdl = mdl.to(device)
        mdl.eval()
        t_load = time.time() - t0
        if device == "cuda":
            torch.cuda.synchronize()
        t1 = time.time()
        ids = tok("The capital of France is", return_tensors="pt").to(mdl.device)
        with torch.no_grad():
            out = mdl.generate(**ids, max_new_tokens=max_new_tokens,
                               do_sample=False)
        if device == "cuda":
            torch.cuda.synchronize()
        t_gen = time.time() - t1
        text = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, 2)
        res = {"ok": True, "device": device, "dtype": str(dtype),
               "load_s": round(t_load, 1), "gen_s": round(t_gen, 1),
               "gen_tok": max_new_tokens,
               "tok_per_s": round(max_new_tokens / t_gen, 2) if t_gen > 0 else None,
               "peak_rss_gb": peak, "generated": text.strip()[:120]}
        if device == "cuda":
            res["gpu_peak_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2)
        return res
    except Exception as exc:
        import traceback
        return {"ok": False, "device": device,
                "why": repr(exc)[:300],
                "last_line": traceback.format_exc().strip().splitlines()[-1][:300]}


def main() -> int:
    rep = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "probe_source": "live", "python": sys.executable}
    rep["mem"] = read_meminfo_gb()
    rep["gpu"] = read_gpu_mib()
    rep["model"] = model_files()

    want = sys.argv[1] if len(sys.argv) > 1 else "both"
    runs = {}
    if want in ("cpu", "both"):
        runs["cpu"] = load_and_generate("cpu")
    if want in ("cuda", "both") and rep["gpu"].get("present"):
        # 显存不够时也照样试，让失败本身成为证据
        runs["cuda"] = load_and_generate("cuda")
    elif want == "cuda":
        runs["cuda"] = {"ok": False, "why": "无 GPU，跳过（未测，不是不可用）"}
    rep["runs"] = runs

    # 结论只从实测值推，不含估算
    verdicts = []
    for dev, r in runs.items():
        if r.get("ok"):
            verdicts.append(f"{dev}: 可跑（load {r['load_s']}s / gen {r['gen_tok']} tok in {r['gen_s']}s = {r['tok_per_s']} tok/s）")
        else:
            verdicts.append(f"{dev}: 不可跑（{r.get('why', '?')[:120]}）")
    rep["verdict"] = verdicts

    print(json.dumps(rep, ensure_ascii=False, indent=2))
    ok = [d for d, r in runs.items() if r.get("ok")]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())