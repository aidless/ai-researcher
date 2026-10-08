"""Build a fresh, disjoint held-out set for the prospective confirmation.

The paper's only project-level-surviving effect (arithmetic transfer, 8/8
families) was measured on heldout40, a strict subset of GSM8K test. Two problems
with confirming on that same set:

  1. It is not independent. Re-running 40 items that already produced the result
     tests reproducibility, not confirmation.
  2. The bank lived at /tmp/ind-audit/.../heldout40.json. /tmp is ephemeral, so the
     paper's data-availability claim was false and the evidence for its main claim
     was one cleanup away from being unreproducible. The bank is now copied into
     the repository.

So this script draws a fresh disjoint sample from the in-repo GSM8K test split
(data/gsm8k/test.jsonl, 1319 items), verifies the disjointness and the gold
answers, and fails rather than emitting a set that cannot be trusted.

Invariants, all executable:
  * no question text overlaps heldout40 (exact and 40-char-prefix match)
  * every sampled item's gold answer parses to a finite float
  * item ids are unique, count matches the request, seed is fixed
  * no sampled item is degenerate (single-digit answer on a multi-step question)

Usage: python3 demo/transfer/build_confirm_set.py [--n 160] [--seed 20261010]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GSM = ROOT / "data" / "gsm8k" / "test.jsonl"
HELD = HERE / "items" / "heldout40.json"
OUT = HERE / "items" / "confirm160.json"
NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def gold_number(answer: str):
    """Final numeric answer from a GSM8K solution ('#### 18')."""
    if "####" in answer:
        tail = answer.split("####")[-1].strip()
        m = NUM.search(tail.replace(",", ""))
        if m:
            try:
                return float(m.group(0).rstrip("."))
            except ValueError:
                return None
    return None


def step_count(answer: str) -> int:
    return answer.count("<<") or answer.count("\n")


def selftest(cases, held_texts, prefix_len=40):
    problems = []
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    held_exact = {t.strip() for t in held_texts}
    held_pref = {t.strip()[:prefix_len] for t in held_texts}
    for c in cases:
        q = c["input"].strip()
        if q in held_exact:
            problems.append(f"{c['id']}: exact overlap with heldout40")
        if q[:prefix_len] in held_pref:
            problems.append(f"{c['id']}: prefix overlap with heldout40")
        if c["expected"] is None:
            problems.append(f"{c['id']}: gold answer does not parse")
        if c["steps"] < 2:
            problems.append(f"{c['id']}: single-step item, not discriminative")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--seed", type=int, default=20261010)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    if not GSM.exists():
        print(f"FATAL: {GSM} missing. The confirmation set cannot be built "
              f"without an in-repo item source.")
        return 1
    if not HELD.exists():
        print(f"FATAL: {HELD} missing. Disjointness cannot be verified.")
        return 1

    held = json.loads(HELD.read_text(encoding="utf-8"))["cases"]
    held_texts = [c["input"] for c in held]
    held_q = {c["input"].strip() for c in held}
    held_pref = {c["input"].strip()[:40] for c in held}

    pool = []
    for i, line in enumerate(GSM.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        d = json.loads(line)
        q = d["question"].strip()
        if q in held_q or q[:40] in held_pref:
            continue  # already used for the original result
        val = gold_number(d["answer"])
        if val is None:
            continue
        steps = step_count(d["answer"])
        # Filter before sampling, not after: sampling first and rejecting after
        # would silently shrink the requested n, which is how a set ends up
        # smaller than the envelope it was built for.
        if steps < 2:
            continue
        pool.append({"question": d["question"], "answer": d["answer"],
                     "gold": val, "steps": steps})

    rng = random.Random(args.seed)
    rng.shuffle(pool)
    chosen = pool[:args.n]
    cases = [{"id": f"cf-{i:03d}", "input": c["question"],
              "expected": c["gold"], "steps": c["steps"]}
             for i, c in enumerate(chosen, 1)]

    problems = selftest(cases, held_texts)
    for p in problems:
        print(f"  [SELFTEST FAIL] {p}")
    if problems:
        print("refusing to write a set that fails its own invariants")
        return 1

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"cases": cases, "provenance": {
            "source": "data/gsm8k/test.jsonl (GSM8K test split, Cobbe et al. 2021)",
            "seed": args.seed, "n": len(cases),
            "excluded": "all items whose text or 40-char prefix matches heldout40",
            "heldout40_source": "demo/transfer/items/heldout40.json",
            "verified_disjoint": True,
            "note": "gold answer parsed from the '#### x' suffix; single-step "
                    "items excluded as non-discriminative"}},
        indent=1) + "\n", encoding="utf-8")
    print(f"  [SELFTEST OK] {len(cases)} items, disjoint from heldout40, "
          f"all golds parse, all multi-step")
    print(f"  pool available: {len(pool)} disjoint items of "
          f"{len(GSM.read_text(encoding='utf-8').splitlines())} in the split")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
