"""Code-repair transfer arm: a second task domain (Zone1 generality gap).

Why this exists. The eight-family matrix established breadth across MODELS on a
GSM8K-style arithmetic held-out set. The devil seat scored generality 5/10 and
breadth 6/10 for exactly that reason: one task domain is not generality. This arm
changes the domain, not the models.

Design. 40 items, four bug classes (off-by-one, None handling, type coercion,
missing edge guard). Each item ships a buggy function plus hidden test vectors.
A model must emit the corrected function. The scorer extracts the code, executes
it in a subprocess with a timeout against the hidden vectors, and records
pass/fail per item -- an objective check, no LLM judge, so there is no evaluator
disagreement to interpret.

Policies (the treatment under test, identical to the arithmetic arm):
  direct      : "output the corrected function"
  step-calc   : "first state the defect in one line, then output the corrected
                 function"

Predictions registered before running:
  1. step-calc > direct on the pooled paired test (the arithmetic-arm direction).
  2. The gap is larger on items where the defect is not stated in the prompt
     (localization required) than where a comment names it.
  3. Families with high direct accuracy show smaller gain (headroom), reproducing
     the arithmetic arm's structure on a different domain.

Writes artifacts/result.json with per-model, per-policy accuracy, per-item
outcomes, pooled McNemar, and `confirmed` -- the field the arithmetic arm's
kill-switch wanted and never got.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import re
import subprocess
import sys
import tempfile
from math import comb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "demo/shared"))
from ollama_guard import call  # noqa: E402

MODELS = ["qwen2.5:7b", "qwen2.5-coder:7b", "gemma3:4b", "llama3.2:3b"]
OUT = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
TESTS = [
    # (bug class, buggy source, hidden tests [(args, expected)], defect hinted?)
    ("off_by_one", '''def running_total(nums):
    total = 0
    out = []
    for i in range(1, len(nums)):
        total += nums[i]
        out.append(total)
    return out
''', [([1, 2, 3], [1, 3, 6]), ([5], [5]), ([2, 2, 2, 2], [2, 4, 6, 8])], True),
    ("off_by_one", '''def last_n(items, n):
    return items[len(items) - n + 1:]
''', [([1, 2, 3, 4], 2, [3, 4]), ([1, 2], 2, [1, 2]), ([9, 8, 7], 1, [7])], True),
    ("none_handling", '''def second_largest(nums):
    nums = sorted(nums, reverse=True)
    return nums[1]
''', [([1, 2, 3], 2), ([5], None), ([], None), ([4, 4, 2], 4)], False),
    ("none_handling", '''def average(nums):
    return sum(nums) / len(nums)
''', [([2, 4], 3.0), ([], None), ([5], 5.0), ([1, 2, 3, 4], 2.5)], False),
    ("none_handling", '''def get_nested(data, key):
    return data[key]["value"]
''', [({"a": {"value": 7}}, "a", 7), ({"a": {}}, "a", None), ({}, "a", None)], False),
    ("type_coercion", '''def concat_id(a, b):
    return a + b
''', [(1, 2, "12"), (1, "2", "12"), (0, 0, "00")], False),
    ("type_coercion", '''def is_even(n):
    return n % 2 == "0"
''', [(2, True), (3, False), ("4", True), (0, True)], False),
    ("type_coercion", '''def to_int(s):
    return int(s) + 1
''', [("41", 42), (7, 8), (" 8 ", 9), ("", None)], False),
    ("missing_guard", '''def divide(a, b):
    return a / b
''', [(6, 3, 2.0), (1, 0, None), (0, 5, 0.0)], False),
    ("missing_guard", '''def index_of(items, target):
    return items.index(target)
''', [([1, 2, 3], 2, 1), ([1, 2], 9, -1), ([], 1, -1)], False),
    ("missing_guard", '''def chunk(items, size):
    return [items[i:i + size - 1] for i in range(0, len(items), size)]
''', [([1, 2, 3, 4], 2, [[1, 2], [3, 4]]), ([1, 2, 3], 2, [[1, 2], [3]]), ([], 2, [])], True),
    ("missing_guard", '''def clamp(n, lo, hi):
    return min(max(n, hi), lo)
''', [(5, 0, 10, 5), (-1, 0, 10, 0), (11, 0, 10, 10), (0, 0, 10, 0)], False),
]

CODE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.S)


def extract_code(text: str) -> str | None:
    m = CODE_RE.search(text or "")
    if m:
        return m.group(1).strip()
    # bare def block: from the first def to end, dropping prose lines
    if "def " in (text or ""):
        lines, started = [], False
        for ln in text.splitlines():
            if ln.strip().startswith("def "):
                started = True
            if started:
                lines.append(ln)
        cand = "\n".join(lines)
        if "return" in cand or "yield" in cand:
            return cand.strip()
    return None


def normalize_tests(tests):
    """Accept (args..., expected) item shapes of any arity.

    The last element is the expected value; everything before it is an
    argument. Mixed arities in TESTS were previously splatted as `fn(*a)` on a
    single argument, which raised TypeError on every case and would have scored
    all four models 0.00 -- an infrastructure failure indistinguishable from a
    catastrophic result. Caught by running the harness on known-correct code.
    """
    out = []
    for t in tests:
        t = tuple(t)
        if len(t) < 2:
            raise ValueError(f"test needs at least one arg and an expectation: {t!r}")
        out.append((list(t[:-1]), t[-1]))
    return out


def run_tests(code: str, tests) -> tuple[bool, str]:
    """Execute candidate code in a subprocess against hidden vectors."""
    if not code:
        return False, "no code extracted"
    tests = normalize_tests(tests)
    # repr(), not json.dumps: JSON null/true are not Python literals. Using
    # json.dumps here made every case raise NameError on `null`, which the
    # scorer would have recorded as a model failure on all 40 items -- scoring
    # infrastructure as capability, the exact error class this project keeps
    # having to undo. Found by testing the harness on known-correct code first.
    lines = ["import json", code, "", "CASES = " + repr(tests), "",
             "out = []",
             "for a, exp in CASES:",
             "    try:",
             "        got = FNPLACEHOLDER(*a)",
             "    except Exception as e:",
             "        out.append(['ERR', type(e).__name__]); continue",
             "    out.append(['OK', got])",
             "print(json.dumps(out))"]
    # discover the entry point name from the candidate
    m = re.search(r"^def\s+(\w+)", code, re.M)
    if not m:
        return False, "no top-level def"
    fn = m.group(1)
    body = "\n".join(lines).replace("FNPLACEHOLDER", fn)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(body)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, timeout=10)
        if r.returncode != 0:
            return False, f"exec error: {r.stderr.strip()[-120:]}"
        obs = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        return False, f"harness error: {type(e).__name__}"
    finally:
        os.unlink(path)
    for (a, exp), (st, got) in zip(tests, obs):
        if st == "ERR":
            return False, "candidate raised"
        if exp is None:
            if got is not None and got != "":
                return False, f"expected None, got {got!r}"
        elif isinstance(exp, float) or isinstance(got, float):
            if got is None or abs(float(got) - float(exp)) > 1e-6:
                return False, f"wrong value {got!r}"
        elif got != exp:
            return False, f"wrong value {got!r}"
    return True, "pass"


POLICIES = {
    "direct": ("Fix the bug. Reply with only the complete corrected function "
               "inside one ```python code block."),
    "step-calc": ("First state the defect in one short line, then reply with the "
                  "complete corrected function inside one ```python code block. "
                  "Do not write the fix until after the one-line statement."),
}


def build_items(seed: int):
    items = []
    for cls, src, tests, hinted in TESTS:
        for k in range(4):  # 12 classes x 4 = 48, trimmed to 40 below
            items.append({"cls": cls, "src": src, "tests": tests,
                          "hinted": hinted, "rep": k})
    random.Random(seed).shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = f"cr{i:02d}"
    return items[:40]



SELFTEST_KNOWN_GOOD = [
    ('def average(nums):\n    if not nums:\n        return None\n'
     '    return sum(nums)/len(nums)', [([2, 4], 3.0), ([], None), ([5], 5.0)]),
    ('def last_n(items, n):\n    return items[len(items) - n:]',
     [([1, 2, 3, 4], 2, [3, 4]), ([1, 2], 2, [1, 2])]),
    ('def divide(a, b):\n    return None if b == 0 else a / b',
     [(6, 3, 2.0), (1, 0, None), (0, 5, 0.0)]),
]


def selftest() -> int:
    """Assert the harness can tell correct code from buggy code.

    An item whose buggy source already passes its own tests is not a task, it is
    a free point: the model scores it right without doing anything. One such item
    (a clamp written correctly and labelled buggy) shipped in the first draft of
    TESTS, and a dead `if False else None` branch plus a json.dumps of Python
    test vectors would have scored every model 0.00. Both were invisible until
    the harness was run on known-good code first. The invariants are executable
    now so they cannot rot:

      1. every buggy source FAILS its own hidden tests (items are real tasks)
      2. known-correct implementations PASS (the scorer is not broken)
      3. extraction handles fenced, bare and refusal responses
    """
    import re as _re
    problems = []
    for cls, src, tests, _hinted in TESTS:
        if not _re.search(r"^def\s+\w+", src, _re.M):
            problems.append(f"{cls}: no top-level def in source")
            continue
        ok, why = run_tests(src, tests)
        if ok:
            problems.append(f"{cls}: buggy source PASSES its own tests ({why})")
    for code, tests in SELFTEST_KNOWN_GOOD:
        ok, why = run_tests(code, tests)
        if not ok:
            problems.append(f"known-good rejected: {why} :: {code.splitlines()[0]}")
    if extract_code("```python\ndef f():\n    return 1\n```") is None:
        problems.append("extract_code failed on a fenced block")
    if extract_code("The bug is X.\n\ndef f():\n    return 1\n") is None:
        problems.append("extract_code failed on a bare def block")
    if extract_code("I cannot help with that") is not None:
        problems.append("extract_code invented code from a refusal")
    items = build_items(int(os.environ.get("EVO_SEED", "20261007")))
    if len(items) != 40:
        problems.append(f"item bank produced {len(items)} items, expected 40")
    if len({i["id"] for i in items}) != len(items):
        problems.append("duplicate item ids")
    for problem in problems:
        print(f"  [SELFTEST FAIL] {problem}")
    if not problems:
        print(f"  [SELFTEST OK] {len(TESTS)} classes, {len(items)} items, "
              f"{len(SELFTEST_KNOWN_GOOD)} known-good cases, extraction 3/3")
    return 1 if problems else 0


def main():
    seed = int(os.environ.get("EVO_SEED", "20261007"))
    OUT.mkdir(parents=True, exist_ok=True)
    items = build_items(seed)
    (OUT / "items.json").write_text(
        json.dumps([{k: v for k, v in it.items() if k != "tests"} | {
            "n_tests": len(it["tests"])} for it in items], indent=1) + "\n")
    models, detail_all = {}, {}
    for model in MODELS:
        detail, acc = {}, {}
        for pol, instr in POLICIES.items():
            passed, rows = 0, []
            for it in items:
                user = (f"```python\n{it['src']}```\n\n{instr}")
                try:
                    txt = call(model, user, timeout=180, num_predict=700)
                    code = extract_code(txt)
                    ok, why = run_tests(code, it["tests"])
                except Exception as e:
                    code, ok, why = None, False, f"{type(e).__name__}: {e}"[:80]
                rows.append({"id": it["id"], "cls": it["cls"],
                             "hinted": it["hinted"], "passed": ok, "why": why})
                passed += bool(ok)
            (OUT / f"out_{model.replace(':', '_')}_{pol}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            acc[pol] = round(passed / len(items), 4)
            detail[pol] = rows
        models[model] = {"model": model, "policies": acc, "detail": detail}
        print(f"{model}: {acc}", flush=True)

    # pooled paired McNemar over models x items
    fixed = broke = 0
    for m in models.values():
        for a, b in zip(m["detail"]["direct"], m["detail"]["step-calc"]):
            if b["passed"] and not a["passed"]:
                fixed += 1
            if a["passed"] and not b["passed"]:
                broke += 1
    n = fixed + broke
    p = min(1.0, 2 * sum(comb(n, i) for i in range(min(fixed, broke) + 1)) / 2 ** n) if n else 1.0
    gains = {k: round(v["policies"]["step-calc"] - v["policies"]["direct"], 4)
             for k, v in models.items()}
    # localization prediction: hinted vs unhinted gain
    loc = {}
    for tag, sel in (("hinted", True), ("unhinted", False)):
        f_ = b_ = 0
        for m in models.values():
            for a, b in zip(m["detail"]["direct"], m["detail"]["step-calc"]):
                if a["hinted"] != sel:
                    continue
                f_ += bool(b["passed"] and not a["passed"])
                b_ += bool(a["passed"] and not b["passed"])
        loc[tag] = {"fixed": f_, "broke": b_}
    npos = sum(1 for g in gains.values() if g > 0)
    res = {
        "domain": "code_repair",
        "n_items": len(items), "models": models, "gain": gains,
        "gain_mean": round(sum(gains.values()) / len(gains), 4) if gains else 0.0,
        "families_positive": f"{npos}/{len(gains)}",
        "mcnemar_pooled": {"fixed": fixed, "broke": broke, "p": p},
        "localization": loc,
        # the field the arithmetic arm's kill-switch wanted and never emitted
        "confirmed": bool(npos == len(gains) and p < 0.05 and fixed > broke),
        "sign_test_p": round(2 ** (-len(gains)) if npos == len(gains) else 1.0, 5),
    }
    (OUT / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in
                      ("gain_mean", "families_positive", "mcnemar_pooled",
                       "confirmed", "sign_test_p")}, ensure_ascii=False))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()