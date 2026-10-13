#!/usr/bin/env python3
"""Reproduce PAPER/nli_adjudication.json (open-source NLI adjudication).

Usage:
  PYTHONPATH=/tmp/nli-pkgs python3 nli_adjudicate.py
Requires: torch (system), sentencepiece (/tmp/nli-pkgs, cp312 build),
cached model tals/albert-xlarge-vitaminc-mnli. CPU only (no GPU contention).
Writes nli_adjudication.json next to itself. Deterministic given the files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

HERE = Path(__file__).resolve().parent
SNAP = Path.home() / (".cache/huggingface/hub/models--tals--"
                      "albert-xlarge-vitaminc-mnli/snapshots/3082ba54344bd9ddada2be1c5e9b4131721d2a5d/")
CLEAN = Path("/home/liuzewen/F:\\deepseek/ai-researcher/demo/runs/lineage-01-clean/round-01/artifacts")
FAM = ["c021", "c022", "c023", "c024", "c025",
       "c026", "c027", "c028", "c029", "c030"]


def main() -> int:
    tok = AutoTokenizer.from_pretrained(str(SNAP), local_files_only=True)
    md = AutoModelForSequenceClassification.from_pretrained(
        str(SNAP), local_files_only=True).eval().to("cpu")
    ids = {int(v): k for k, v in md.config.label2id.items()}
    pb = {r["id"]: r for r in map(json.loads, open(CLEAN / "pred_v3b.jsonl"))}
    pc = {r["id"]: r for r in map(json.loads, open(CLEAN / "pred_v3c.jsonl"))}

    def nli(prem: str, hyp: str) -> dict:
        x = tok(prem, hyp, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            p = torch.softmax(md(**x).logits, dim=-1)[0]
        return {ids[i]: round(float(p[i]), 4) for i in range(len(p))}

    out = {"model": "tals/albert-xlarge-vitaminc-mnli (local snapshot 3082ba54)",
           "method": ("premise=v3b long answer, hypothesis=v3c short answer, "
                      "and reverse; CPU; truncation 512"),
           "pairs": {}}
    for i in FAM:
        out["pairs"][i] = {
            "long_to_short": nli(pb[i]["output"], pc[i]["output"]),
            "short_to_long": nli(pc[i]["output"], pb[i]["output"]),
            "v3c_len": len(pc[i]["output"]),
            "v3b_len": len(pb[i]["output"]),
        }
    (HERE / "nli_adjudication.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote nli_adjudication.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
