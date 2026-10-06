"""Idea engine: limitations sections + failure-mode library -> ranked hypotheses.

A top-tier paper starts from a gap, not a method. This module mines the two
places where the account has already written its gaps down:

  1. Limitations / Future Work sections of its own manuscripts. Each "future
     work should ..." is a hypothesis the authors already believe is worth
     testing -- structured here with an explicit falsification criterion.
  2. The failure-mode library (references/failure-modes.md). Each FM's
     meta-lesson names a dimension along which current practice is wrong;
     "换稿件域就是新的误报来源" is itself a research program.

Every candidate is cost-tiered, because cost determines what "fully automatic"
can actually attempt unattended:
  T0 analysis-only  -- reanalysis of already-committed data. No new calls.
                      The machine can do all of it tonight.
  T1 local-compute  -- runs on this machine's ollama / GPU. Bounded, free.
  T2 api-budget     -- needs paid calls. Requires a human-approved spend.

Ranking is publishability x cheapness: a T0 that answers a stated limitation
outranks a T2 that needs a new dataset. The output is envelope drafts, not
prose -- each candidate maps directly onto envelope.py fields.

Usage:
    python -m ai_researcher.ideas mine <paper_dir>... --fm references/failure-modes.md
    python -m ai_researcher.ideas rank --out ideas_ranked.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# Manually curated from the account's own manuscripts. Each entry names the
# source line so the gap stays traceable. Machine extraction of Limitations
# sections is left as follow-up; hand curation is more reliable and these do
# not change often.
SEED_GAPS = [
    {"id": "mm-epc-bounded-metric",
     "source": "mm-epc/paper/mm_epc_paper.tex:175",
     "gap": "gamma is unbounded above; simplex geometry deflates it for high-PCI references",
     "hypothesis": "Jensen-Shannon divergence (or Hellinger / total variation) gives the same qualitative pattern (cross-model >> self-eval) with stable cross-condition comparisons",
     "falsifies": "JS divergence reverses the ordering (self-eval >= cross-model)",
     "tier": "T0",
     "needs": "committed weight vectors + PCI values from mm-epc evidence",
     "venue": "workshop or appendix extension"},
    {"id": "mm-epc-balanced-design",
     "source": "mm-epc/paper/mm_epc_paper.tex:491",
     "gap": "8 text-domain vs 3 visual-domain strategies biases weights toward text before any evaluator effect",
     "hypothesis": "reanalysis on a balanced 3+3 subset preserves the cross-model >> self-eval pattern with a cleaner modality estimate",
     "falsifies": "balanced subset erases the cross-model excess (pattern was an artifact of slot counts)",
     "tier": "T0",
     "needs": "committed per-strategy weights",
     "venue": "workshop or appendix extension"},
    {"id": "mm-epc-evaluator-diversity",
     "source": "mm-epc/paper/mm_epc_paper.tex:489",
     "gap": "findings specific to GPT-4o as evaluator; Claude/Gemini/Qwen-VL unknown",
     "hypothesis": "at least one other multimodal evaluator shows PCI magnification >= 2x over self-eval",
     "falsifies": "no tested evaluator exceeds 1.5x (collapse is GPT-4o-specific, not general)",
     "tier": "T2",
     "needs": "paid multimodal API calls, ~2000 per evaluator",
     "venue": "full paper if positive, workshop if mixed"},
    {"id": "gsm8k-cross-model-transfer",
     "source": "gsm8k round-2 established step-calc on qwen2.5:7b only",
     "gap": "policy effect may be model-specific; no cross-family evidence",
     "hypothesis": "step-calc shows positive gain on llama3.1:8b heldout40",
     "falsifies": "gain <= 0 on the second family (effect does not transfer)",
     "tier": "T1",
     "needs": "local ollama, 160 calls, ~25 min",
     "venue": "workshop replication or extension section"},
    {"id": "fm-detector-false-positive-rate",
     "source": "FM-30/FM-31 meta-lesson: detector false-positive rate decides its credibility",
     "gap": "no measured false-positive rate for any of the account's own checkers on held-out manuscripts",
     "hypothesis": "scan_number_consistency reports <= 1 false mismatch per 10 clean pages on manuscripts it has never seen",
     "falsifies": "> 3 false mismatches per 10 pages (the gate trains users to ignore it)",
     "tier": "T1",
     "needs": "2-3 clean manuscripts + local runs",
     "venue": "methods note, strengthens every paper that cites the checker"},
]


def rank(ideas: list) -> list:
    """Publishability x cheapness. T0 first, then T1, then T2. Stable order."""
    tier_rank = {"T0": 0, "T1": 1, "T2": 2}
    return sorted(ideas, key=lambda x: (tier_rank.get(x.get("tier", "T2"), 2), x["id"]))


def to_envelope(idea: dict, methods: str, rounds: int = 1) -> dict:
    """Draft an envelope skeleton from a ranked idea. Human fills methods."""
    return {
        "hypothesis": idea["hypothesis"],
        "methods": methods,
        "max_rounds": rounds,
        "max_cost_usd": 0.0 if idea["tier"] in ("T0", "T1") else 50.0,
        "max_wall_hours": 3.0,
        "kill_switch": [
            {"condition": "confirmed == true", "action": "STOP-EXTEND",
             "note": f"pattern holds: extend to full scale ({idea['venue']})"},
            {"condition": "confirmed == false", "action": "STOP-REFUTED",
             "note": f"falsified as stated: {idea['falsifies']}"},
        ],
        "required_artifacts": ["result.json"],
        "approved_by": "",
        "approved_at": "",
        "source_gap": idea["id"],
    }


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.ideas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--out", default="")
    e = sub.add_parser("envelope")
    e.add_argument("idea_id")
    e.add_argument("--methods", required=True)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "rank":
        ranked = rank(SEED_GAPS)
        doc = [{"rank": i + 1, **g} for i, g in enumerate(ranked)]
        if a.out:
            Path(a.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(doc, indent=1, ensure_ascii=False)[:2000])
    elif a.cmd == "envelope":
        idea = next(g for g in SEED_GAPS if g["id"] == a.idea_id)
        Path(a.out).write_text(
            json.dumps(to_envelope(idea, a.methods), indent=2, ensure_ascii=False) + "\n")
        print(f"envelope draft for {a.idea_id} -> {a.out} (needs human approval)")


if __name__ == "__main__":
    sys.exit(main())
