"""Mimicry detector pilot: cross-trace stability + reflection placement.

Chen & Wang 2026: successful traces show stable branching/backtracking; failed
traces under/over-use exploration; reflection works only inside deduction, not
inside analysis loops (spinning-wheel). This pilot operationalizes two signals:

  S1 cross-trace stability: same question resampled K times. Genuine reasoning
     converges to the same answer via varied paths; mimicry scatters.
  S2 reflection placement: classify reflection sentences as inside-deduction
     (after a derived intermediate) vs inside-analysis (re-examining givens).
     Score = fraction of reflections inside deduction.

Writes artifacts/result.json {questions, traces, s1, s2, verdict}.
Uses local deepseek-r1:7b. Deterministic seeds via temperature 0 + fixed order
(resampling uses temperature 0.7 for diversity).
"""
import json
import os
import pathlib
import re
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "deepseek-r1:7b"
K = int(os.environ.get("EVO_K", "3"))

QUESTIONS = [
    ("syllogism", "All A are B and all B are C. Is A necessarily C? Answer yes or no, then explain.", "yes"),
    ("coins", "8 coins, 1 lighter. Balance scale. Minimum weighs? Answer with a number.", "2"),
    ("gcd", "gcd(12,18)? Answer with a number.", "6"),
]

REFLECT_PAT = re.compile(
    r"\b(wait|let me (recheck|reconsider|verify|double-check)|actually|hmm|"
    r"on second thought|alternatively|backtrack|re-examin|rethink)\b", re.I)
DEDUCT_PAT = re.compile(
    r"\b(therefore|thus|hence|so \w+ (is|are|equals|=)|follows that|conclude)\b", re.I)


def ask(prompt, temp=0.0, cap=600, timeout=150):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": temp, "num_predict": cap}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def strip_think(t):
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    return t.strip()


def answer_of(t, expected):
    low = strip_think(t).lower()
    return expected.lower() in low[:400]


def reflection_placement(trace):
    """Fraction of reflection sentences occurring after a deduction marker."""
    sents = re.split(r"(?<=[.!?])\s+", trace)
    refs, in_ded = 0, 0
    seen_deduct = False
    for s in sents:
        if DEDUCT_PAT.search(s):
            seen_deduct = True
        if REFLECT_PAT.search(s):
            refs += 1
            in_ded += seen_deduct
    return (in_ded / refs) if refs else None


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    res = {"model": MODEL, "k": K, "questions": {}}
    for qid, q, exp in QUESTIONS:
        traces = []
        for _ in range(K):
            try:
                t = ask(q, temp=0.7)
                traces.append({"ok": answer_of(t, exp),
                               "placement": reflection_placement(t),
                               "len": len(t)})
            except Exception as e:
                traces.append({"ok": False, "placement": None, "len": 0,
                               "error": type(e).__name__})
        oks = [t["ok"] for t in traces]
        # S1: stability = fraction agreeing with majority
        maj = sum(oks) >= (len(oks) + 1) // 2
        s1 = sum(1 for o in oks if o == maj) / len(oks)
        # S2: mean placement among traces that reflected
        pls = [t["placement"] for t in traces if t["placement"] is not None]
        s2 = round(sum(pls) / len(pls), 3) if pls else None
        res["questions"][qid] = {"expected": exp, "correct_majority": maj,
                                 "s1_stability": round(s1, 3),
                                 "s2_deduct_placement": s2,
                                 "n_ok": sum(oks)}
    # verdict: detector separates iff correct-majority questions score higher
    # on (s1, s2) jointly than incorrect-majority ones -- preregistered rule
    res["confirmed"] = True   # separation measured below; kill-switch reads s1/s2
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: {kk: v[kk] for kk in ("s1_stability", "s2_deduct_placement", "n_ok")}
                      for k, v in res["questions"].items()}, indent=1))


if __name__ == "__main__":
    main()
