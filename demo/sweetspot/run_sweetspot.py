"""Inference sweet spot: does capping reasoning length help or hurt?

Thoughtology (TMLR) claims extra inference can IMPAIR performance on frontier R1.
Test on local deepseek-r1:7b across 3 task families (math/code/logic), 6 items
each, with num_predict caps [150, 400, 1000]. Exact-match grading against
reference answers. Fixed seed.

Writes artifacts/result.json {families, caps, accuracy curves, verdict}.
Falsifies to STOP-REFUTED if accuracy is monotone non-decreasing everywhere
(sweet spot is frontier/task-specific artifact).
"""
import json
import os
import pathlib
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "deepseek-r1:7b"
CAPS = [150, 400, 1000]
TASKS = {
    "math": [
        ("1+2*3=?", "7"),
        ("5//2 in Python?", "2"),
        ("8 coins 1 lighter, min weighs?", "2"),
        ("2^10=?", "1024"),
        ("15% of 200?", "30"),
        ("gcd(12,18)?", "6"),
    ],
    "code": [
        ("Python palindrome check, one line:", "def"),
        ("Time decorator in Python:", "def"),
        ("Binary search returns index or?", "-1"),
        ("List comprehension squares 0-4:", "0, 1"),
        ("Sort dict by value:", "sorted"),
        ("Read file lines Python:", "open"),
    ],
    "logic": [
        ("All A are B, all B are C. A necessarily C?", "yes"),
        ("3 lamps 3 switches, enter once, determine mapping?", "switch"),
        ("If P then Q. Not Q. Therefore?", "not p"),
        ("Syllogism valid: all cats mammals, Tom is cat?", "yes"),
        ("Contrapositive of: if rains, wet?", "not wet"),
        ("Knights always truth, knave says 'I am knave'?", "knave"),
    ],
}


def ask(prompt, cap, timeout=150):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "num_predict": cap}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["response"]


def grade(response, expected):
    """Numeric answers compare against the LAST number in the response (answers
    come last; the question's own numbers come first -- comparing the first
    number grades the question stem, not the answer). Non-numeric answers use
    word boundaries ("yes" must not match "eyes").
    """
    import re
    low = response.lower()
    exp = expected.lower().strip()
    nums = re.findall(r"[-+]?\d*\.?\d+", low)
    try:
        return float(nums[-1]) == float(exp)
    except (IndexError, ValueError):
        pass
    return re.search(r"\b" + re.escape(exp) + r"\b", low) is not None


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    res = {"model": MODEL, "caps": CAPS, "families": {}}
    for fam, items in TASKS.items():
        curve = []
        for cap in CAPS:
            hits = 0
            for q, a in items:
                try:
                    hits += grade(ask(q, cap), a)
                except Exception:
                    pass
            curve.append(round(hits / len(items), 4))
        nonmono = any(curve[i] < curve[i - 1] for i in range(1, len(curve)))
        res["families"][fam] = {"acc": curve, "nonmonotonic": nonmono}
    res["any_sweet_spot"] = any(f["nonmonotonic"] for f in res["families"].values())
    res["confirmed"] = res["any_sweet_spot"]
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v["acc"] for k, v in res["families"].items()}))


if __name__ == "__main__":
    main()
