"""Inter-evaluator agreement on real code diffs (breadth arm).

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
           "confirmed": (agree / tot < 0.8) if tot else False}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"agreement": res["pairwise_agreement"],
                      "flips": flips, "confirmed": res["confirmed"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
