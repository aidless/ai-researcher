"""breadth-02: inter-evaluator agreement on a larger, harder diff set.

TTRL toys and GSM8K items do not deploy. Code review does: teams already route
diffs through LLM reviewers, and the reviewer model is usually chosen by price
or habit, not evidence. If three competent local evaluators disagree
substantially on the SAME real diffs, evaluator dependence is a deployment fact,
not a lab artifact.

Design: 8 real-world-style diffs (bugfix, perf, refactor, security-sensitive,
docs-only, test-only, dependency bump, API change), 3 evaluator families
(qwen2.5:7b, llama3.1:8b, deepseek-r1:7b). Each evaluator rates each diff
APPROVE/REQUEST_CHANGES with a one-line reason. Metric: Fleiss-style pairwise
agreement + cases where the majority flips by evaluator (ship/no-ship
disagreements -- the ones that would change a deployment).

Writes artifacts/result.json {diffs, votes, agreement, flip_cases, verdict}.
~24 local calls. Deterministic seed.
"""
import json
import os
import pathlib
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
EVALUATORS = ["qwen2.5:7b", "llama3.1:8b", "deepseek-r1:7b"]

# breadth-02 additions: 16 harder diffs (multi-hunk, subtle semantics,
# performance-with-tradeoffs, security-relevant, API/typing changes). breadth-01's
# eight diffs were mostly single-line and easy, which is the most likely reason it
# saw disagreement without any decision flip: trivial diffs have one defensible
# verdict, so evaluators can differ in reasoning and agree in outcome.
DIFFS_EXTRA = [
    ("perf-tradeoff",
     "--- a/parser.py\n+++ b/parser.py\n@@\n-    for line in lines:\n-        out.append(parse(line))\n+    out = [parse(l) for l in lines]\n+    # now streaming is lost",
     "list comprehension loses streaming"),
    ("subtle-semantics",
     "--- a/dict_get.py\n+++ b/dict_get.py\n@@\n def get(d, k, default=None):\n-    return d.get(k, default) or default",
     "falsy values collapse to default"),
    ("multi-hunk",
     "--- a/api.py\n+++ b/api.py\n@@\n-def f(a, b):\n-    return a / b\n+def f(a, b):\n+    if b == 0:\n+        raise ValueError('div0')\n+    return a / b\n@@ def g(x):\n-    return x\n+    return x * 2",
     "guard added plus unrelated behaviour change"),
    ("typing-tightening",
     "--- a/client.py\n+++ b/client.py\n@@\n-def get(url, retries=3):\n+def get(url: str, *, retries: int = 3) -> dict:\n     return fetch(url, retries)",
     "callers passing positionally now break"),
    ("security-order",
     "--- a/auth.py\n+++ b/auth.py\n@@\n def check(user, admin):\n-    return user.is_admin or admin.is_admin\n+    return user.is_admin and admin.is_admin",
     "or to and narrows access"),
    ("cache-invalidation",
     "--- a/store.py\n+++ b/store.py\n@@\n def put(k, v):\n     db[k] = v\n+    # cache not invalidated",
     "stale cache reads"),
    ("silent-truncation",
     "--- a/text.py\n+++ b/text.py\n@@\n def first_line(s, n=80):\n-    return s.split('\\n')[0]",
     "long first lines silently truncated at call sites"),
    ("regex-catastrophic",
     "--- a/match.py\n+++ b/match.py\n@@\n def is_num(s):\n-    return bool(re.match('(\\d+)+$', s))",
     "catastrophic backtracking"),
    ("float-equality",
     "--- a/money.py\n+++ b/money.py\n@@\n-    return round(a + b, 2) == expected\n+    return abs(a + b - expected) < 0.01",
     "float compare to money"),
    ("lock-order",
     "--- a/db.py\n+++ b/db.py\n@@\n def tx(a, b):\n+    a.lock()\n     with db.transaction():\n-        b.lock()\n+        pass",
     "lock acquired outside transaction"),
    ("json-nan",
     "--- a/api.py\n+++ b/api.py\n@@\n-    return json.dumps({'x': float('nan')})",
     "NaN is not valid JSON"),
    ("copy-vs-deepcopy",
     "--- a/state.py\n+++ b/state.py\n@@\n-    self.snapshot = other.dict",
     "shallow copy of nested state"),
    ("timezone",
     "--- a/sched.py\n+++ b/sched.py\n@@\n-    return datetime.utcnow() + timedelta(days=1)",
     "naive datetime"),
    ("retry-storm",
     "--- a/net.py\n+++ b/net.py\n@@\n def get(url):\n     for _ in range(5):\n         try:\n             return fetch(url)\n         except:\n             pass",
     "bare except swallows non-retryable errors"),
    ("off-by-one-guard",
     "--- a/range.py\n+++ b/range.py\n@@\n-    return [i for i in range(n)]\n+    return [i for i in range(n) if i % 2 == 0]",
     "silently filters odd values"),
    ("doc-only-semantics",
     "--- a/core.py\n+++ b/core.py\n@@\n def pay(amount):\n     # amount is in cents\n     return amount",
     "doc says cents, callers pass dollars"),
]

DIFFS = [
    ("bugfix-offbyone",
     "--- a/paginate.py\n+++ b/paginate.py\n@@\n-    for i in range(1, pages):\n+    for i in range(0, pages):\n     fetch(page[i])",
     "off-by-one fix"),
    ("perf-nplus1",
     "--- a/users.py\n+++ b/users.py\n@@\n-    for u in users:\n-        u.profile = db.get(u.id)\n+    profiles = db.batch_get([u.id for u in users])",
     "N+1 query fix"),
    ("refactor-rename",
     "--- a/util.py\n+++ b/util.py\n@@\n-def calc(x):\n+def compute_total(items):",
     "rename only"),
    ("security-eval",
     "--- a/render.py\n+++ b/render.py\n@@\n-    return eval(user_input)\n+    return ast.literal_eval(user_input)",
     "eval to literal_eval"),
    ("docs-typo",
     "--- a/README.md\n+++ b/README.md\n@@\n-Recieve requests\n+Receive requests",
     "typo only"),
    ("test-only",
     "--- a/test_api.py\n+++ b/test_api.py\n@@\n+def test_timeout():\n+    assert call(timeout=1)",
     "new test"),
    ("dep-bump",
     "--- a/requirements.txt\n+++ b/requirements.txt\n@@\n-requests==2.28\n+requests==2.32",
     "dependency bump"),
    ("api-change",
     "--- a/client.py\n+++ b/client.py\n@@\n-def get(url, timeout=5):\n+def get(url, *, timeout=5, retries=3):",
     "keyword-only breaking change"),
]


def judge(model, diff_id, patch, timeout=150):
    body = json.dumps({
        "model": model,
        "prompt": (f"Code review this diff ({diff_id}):\n{patch}\n\n"
                   f"Reply with exactly one line: APPROVE or REQUEST_CHANGES, "
                   f"followed by a colon and one sentence of reason."),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 150}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = json.loads(r.read().decode())["response"].strip().upper()
    if t.startswith("APPROVE"):
        return "APPROVE"
    if "REQUEST_CHANGES" in t[:40] or t.startswith("REQUEST"):
        return "REQUEST_CHANGES"
    return None


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    if os.environ.get("EVO_BREADTH2"):
        DIFFS.extend(DIFFS_EXTRA)
    votes, abst = {}, 0
    for did, patch, _ in DIFFS:
        votes[did] = {}
        for ev in EVALUATORS:
            try:
                v = judge(ev, did, patch)
            except Exception:
                v = None
            votes[did][ev] = v
            if v is None:
                abst += 1
    # pairwise agreement + flip cases (majority differs by evaluator subset)
    import itertools
    agree = tot = 0
    for did in votes:
        vs = [votes[did][e] for e in EVALUATORS if votes[did][e]]
        for a, b in itertools.combinations(vs, 2):
            tot += 1
            agree += (a == b)
    # flip: would dropping one evaluator change the majority?
    flips = 0
    for did in votes:
        vs = [votes[did][e] for e in EVALUATORS if votes[did][e]]
        if len(vs) < 3:
            continue
        full = sum(1 for v in vs if v == "APPROVE") > len(vs) / 2
        for drop in range(len(vs)):
            rest = vs[:drop] + vs[drop + 1:]
            if (sum(1 for v in rest if v == "APPROVE") > len(rest) / 2) != full:
                flips += 1
                break
    res = {"n_diffs": len(DIFFS), "evaluators": EVALUATORS,
           "votes": votes, "abstentions": abst,
           "pairwise_agreement": round(agree / tot, 3) if tot else None,
           "flip_cases": flips,
           "confirmed": (agree / tot < 0.8) if tot else False,
           # breadth-02 additions used by the kill-switch
           "flip_confirmed": flips >= 1}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"agreement": res["pairwise_agreement"],
                      "flips": flips, "confirmed": res["confirmed"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
