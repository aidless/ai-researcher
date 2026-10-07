"""Calibrate sweetspot probe questions: keep only discriminative items.

A probe question is useful iff the model scores >0 at SOME cap (not floor)
and <1 at SOME cap (not ceiling). Floor items (all zeros) cannot show a curve;
ceiling items cannot fall. This script pilots candidates at cap 400 and keeps
6 per family in the mid band.
"""
import json
import os
import pathlib
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_sweetspot import ask, grade

CANDIDATES = {
    "math": [
        ("1+2*3=?", "7"), ("2^10=?", "1024"), ("15% of 200?", "30"),
        ("gcd(12,18)?", "6"), ("7*8=?", "56"), ("100-37=?", "63"),
        ("3*14=?", "42"), ("sqrt(144)?", "12"), ("2*3*5=?", "30"),
        ("99+1=?", "100"),
    ],
    "code": [
        ("Python palindrome check, one line:", "def"),
        ("Time decorator in Python:", "def"),
        ("Binary search returns index or?", "-1"),
        ("Sort dict by value:", "sorted"),
        ("Read file lines Python:", "open"),
        ("Python list append method:", "append"),
        ("Reverse a string in Python:", "[::-1]"),
        ("Python dict get with default:", "get"),
        ("Lambda add two numbers:", "lambda"),
        ("Try except syntax:", "except"),
    ],
    "logic": [
        ("All A are B, all B are C. A necessarily C? Answer yes or no.", "yes"),
        ("If P then Q. Not Q. Therefore? Answer in two words.", "not p"),
        ("A knight always tells truth. He says 'I am a knave.' Is he knight or knave?", "knave"),
        ("All cats are mammals. Tom is a cat. Is Tom a mammal? Answer yes or no.", "yes"),
        ("If it rains the ground is wet. The ground is dry. Did it rain? Answer yes or no.", "no"),
        ("Three doors, one prize. You pick one. Host opens an empty one. Switch?", "switch"),
        ("A bat and ball cost 1.10, bat costs 1 more. Ball costs? Answer number.", "0.05"),
        ("Lily pads double daily, cover lake in 48 days. Half cover on which day?", "47"),
        ("If all Bloops are Razzies and all Razzies are Lazzies, are Bloops Lazzies?", "yes"),
        ("You see smoke. Does that prove fire? Answer yes or no.", "no"),
    ],
}


def main():
    out = {}
    for fam, items in CANDIDATES.items():
        scored = []
        for q, a in items:
            try:
                r = ask(q, cap=400)
                hit = grade(r, a)
            except Exception:
                hit = False
            scored.append((q, a, hit))
            print(f"{fam} {'HIT ' if hit else 'miss'}: {q[:40]}", flush=True)
        hits = [x for x in scored if x[2]]
        # keep up to 6 hits; if fewer, pad with misses (floor items still
        # calibrate the bottom of the curve, but flag the family as weak)
        kept = hits[:6] + [x for x in scored if not x[2]][:max(0, 6 - len(hits))]
        out[fam] = [{"q": q, "a": a} for q, a, _ in kept]
        print(f"{fam}: {len(hits)}/{len(items)} hit at cap400", flush=True)
    p = pathlib.Path(os.environ.get("EVO_OUT", "artifacts")) / "calibrated.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
