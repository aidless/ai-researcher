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
# Above this share of unparseable judgments, the comparator cannot support a
# decision-level claim and the arm reports measurable=False.
MAX_ABSTENTION = 0.2
# deepseek-r1:7b was replaced after measurement, not preference. It abstained on
# 24 of 24 diffs across two runs. Cause, measured directly rather than guessed:
# at num_predict=150 the reply is EMPTY, at 400 still empty, at 1200 it finally
# emits 2806 characters containing the verdict and still reports
# done_reason=length. It reasons at length regardless of an explicit
# "state the verdict first" instruction. Under a 72-judgment arm that is not an
# affordable evaluator, and "the reasoning model abstains" was never the finding.
EVALUATORS = ["qwen2.5:7b", "llama3.1:8b", "gemma3:4b"]

# Preflight: an evaluator that cannot return a parseable verdict within budget is
# excluded BEFORE the arm runs and recorded in _config. breadth-01 and the first
# breadth-02 both spent a third of their judgments producing nothing measurable
# and the number only surfaced at the end, where it invalidated the arm. The
# general lesson is the same one the config binding exists for: a precondition
# that can be checked up front should be, and a silently unusable component
# should not be allowed to reach the statistics.
PREFLIGHT_PROBE = "```python\ndef f(x):\n    return x[1:]\n```"


def preflight(evaluators, budget=400):
    ok, dropped = [], {}
    for ev in evaluators:
        try:
            v = judge(ev, "preflight", PREFLIGHT_PROBE, num_predict=budget)
        except Exception as e:
            v = None
            dropped[ev] = f"{type(e).__name__}: {str(e)[:70]}"
        if v:
            ok.append(ev)
        else:
            dropped[ev] = dropped.get(ev, "unparseable verdict at "
                                      f"num_predict={budget}")
    return ok, dropped

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


def _verdict(text: str):
    """Verdict or None. Extracted so it can be unit-tested without a model."""
    t = (text or "").strip().upper()
    head = "\n".join((text or "").strip().splitlines()[:4])
    if not (("APPROVE" in head.upper()) or ("REQUEST" in head.upper())):
        # verdict-first prompting usually puts it in the first line; if a reasoning
        # model still front-loads analysis, search the whole reply rather than
        # discarding a judgement that is present but late.
        head = (text or "").strip()
    norm = head.upper().replace(" ", "_").replace("-", "_")
    has_req = "REQUEST_CHANGES" in norm
    has_app = "APPROVE" in norm
    if has_req and not has_app:
        return "REQUEST_CHANGES"
    if has_app and not has_req:
        return "APPROVE"
    first = head.split("\n")[0].strip().upper() if head else ""
    if first.startswith("APPROVE"):
        return "APPROVE"
    if first.startswith("REQUEST"):
        return "REQUEST_CHANGES"
    return None


# Diagnosis, 2026-10-08: deepseek-r1:7b abstained on all 24 diffs. The cause is
# NOT the parser (widening it was still correct -- a model prefixing prose would
# have been missed -- but it was not this). Measured directly: at num_predict=150
# the response is EMPTY, and at 500 it is TRUNCATED after 798 characters of
# reasoning. The model spends its whole budget thinking and never reaches a
# verdict. So the abstention rate was measuring a reasoning model's budget
# behaviour, not its judgement.
#
# The fix is to make the verdict the first token rather than to spend more budget
# hoping it appears: a reasoning model that is told to state its verdict before
# explaining emits it immediately, and the reasoning that follows cannot swallow
# it. A larger budget is kept as a backstop.
PROMPT = ("Reply with exactly one line: APPROVE or REQUEST_CHANGES, followed by a "
          "colon and one sentence of reason.\n"
          "State the verdict word FIRST, before any analysis. Do not reason before "
          "answering.\n\n"
          "Code review this diff ({diff_id}):\n{patch}")


def judge(model, diff_id, patch, timeout=200, num_predict=400):
    body = json.dumps({
        "model": model,
        "prompt": PROMPT.format(diff_id=diff_id, patch=patch),
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.loads(r.read().decode())["response"]
    t = text.strip().upper()
    return _verdict(text)


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    # Breadth-02 ran the ORIGINAL eight trivial diffs because nothing set
    # EVO_BREADTH2, produced a signed bundle, and fired a kill-switch on it. So the
    # arm is now selected by an explicit required flag rather than an opt-in env
    # var, and the effective configuration is written into result.json for the
    # loop's config-binding check to verify against the envelope's `expect`.
    if os.environ.get("EVO_BREADTH2") != "1":
        raise SystemExit("refusing to run: EVO_BREADTH2=1 is required. Without it "
                         "this script silently runs the original 8-diff set, which "
                         "is how a signed bundle came to certify the wrong "
                         "experiment.")
    DIFFS.extend(DIFFS_EXTRA)
    evaluators, dropped = preflight(EVALUATORS)
    if dropped:
        print(f"[preflight] evaluators excluded before measurement: {dropped}")
    if len(evaluators) < 2:
        raise SystemExit(f"only {len(evaluators)} evaluator(s) returned a "
                         f"parseable verdict; refusing to run an arm whose "
                         f"agreement statistic needs at least two")
    votes, abst = {}, 0
    for did, patch, _ in DIFFS:
        votes[did] = {}
        for ev in evaluators:
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
    usable = sum(1 for v in votes.values() for x in v.values() if x)
    total_judgements = len(DIFFS) * len(evaluators)
    abstention_rate = round(1 - usable / total_judgements, 3) if total_judgements else 1.0
    # A comparator where a third of judgments cannot be parsed cannot support a
    # claim about decision flips. breadth-02 reported flip_cases=0 with 9 of 24
    # judgments unusable, which reads as "no flips" when it means "not measurable".
    measurable = abstention_rate <= MAX_ABSTENTION
    res = {"n_diffs": len(DIFFS), "evaluators": evaluators,
           "evaluators_dropped_by_preflight": dropped,
           "_config": {"n_diffs": len(DIFFS), "evaluators": len(evaluators),
                       "abstention_rate": abstention_rate},
           "abstention_rate": abstention_rate,
           "measurable": measurable,
           "votes": votes, "abstentions": abst,
           "pairwise_agreement": round(agree / tot, 3) if tot else None,
           "flip_cases": flips,
           # confirmed also requires the comparator to be usable
           "confirmed": bool(tot) and (agree / tot < 0.8) and measurable,
           # breadth-02 additions used by the kill-switch
           "flip_confirmed": (flips >= 1) and measurable}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"agreement": res["pairwise_agreement"],
                      "flips": flips, "confirmed": res["confirmed"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
