"""sweetspot-04: is the cap-1000 cliff real at an n that can resolve it?

sweetspot-03 measured accuracy across reasoning caps (150 / 400 / 1000) on 18
calibrated discriminative items and saw a flat-then-cliff shape in the code family
(0.833, 0.833, 0.333). Both seats refused it: n=6 per family, indistinguishable
from noise. The power pre-check added 2026-10-08 now requires n>=63 paired
observations for a 0.25 effect, so this arm runs the same comparison with enough
items to resolve it.

Two deliberate design choices:

1. Items come from the code-repair bank (run_coderepair.TESTS, 48 items across four
   bug classes), not a freshly invented set. That bank is already covered by an
   executable self-test -- every buggy source fails its own hidden tests, known-good
   implementations pass -- so the item validity argument does not have to be made
   twice, and three scorer bugs that would each have looked like a result cannot
   reappear here.
2. The only factor that varies is the reasoning budget (`num_predict`). Items,
   prompts, scorer, seed and models are fixed, so a cap effect cannot be
   confounded with item difficulty the way a fresh item bank could.

Statistic: exact binomial (McNemar) on the paired discordant items between cap 400
and cap 1000, per model and pooled. A "cliff" is confirmed only if the pooled test
resolves AND the direction is negative AND at least one model shows it -- a single
model moving is not a length effect, it is that model.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import re
import sys
from math import comb

def _repo_root(start: pathlib.Path) -> pathlib.Path:
    """Walk up to the directory that holds src/ai_researcher.

    Counting `parents[n]` is how this file failed twice: parents[1] put
    demo/coderepair at <root>/coderepair, and "fixing" it to parents[2] put the
    root one level above the repository. A marker directory cannot be miscounted.
    """
    d = start.resolve()
    for cand in [d, *d.parents]:
        if (cand / "src" / "ai_researcher").is_dir():
            return cand
    raise SystemExit(f"no repository root above {start} (no src/ai_researcher)")


HERE = pathlib.Path(__file__).resolve().parent
REPO = _repo_root(HERE)
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "demo" / "shared"))
sys.path.insert(0, str(REPO / "demo" / "coderepair"))

from run_coderepair import (  # noqa: E402
    TESTS, extract_code, resolve_models, run_tests,
    selftest as harness_selftest,
)

CAPS = [150, 400, 1000]
MODELS = ["qwen2.5:7b", "deepseek-r1:7b"]
PROMPT = ("Fix the bug. Reply with only the complete corrected function "
          "inside one ```python code block.")


def mcnemar(fixed: int, broke: int) -> float:
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


# ---------------------------------------------------------------------------
# Availability accounting lives in demo/shared/availability.py
# ---------------------------------------------------------------------------
# It began here, as the response to sweetspot-04 (111 rows of
# "ollama returned error-text (0 chars)" charged to capability, best arm flipped).
# It moved to shared/ so the other collectors import the SAME predicate instead of
# copying it -- a second writable copy of a classifier is the defect this module
# exists to prevent, and this project has already been bitten twice by two copies
# drifting. Before removing the local version the two were compared on every stored
# sweetspot-04 arm and on the adversarial cases: 6/6 arms identical, 0 classifier
# disagreements.
from availability import (arm_columns, outcome_of,            # noqa: E402
                          unavailability_reason,
                          selftest as availability_battery)


def grade_one(call_fn, model, item, cap):
    """Produce one row. Separate the two failure stages, on purpose.

    transport failure  -> no usable answer exists; the row cannot speak about
                          capability at all, so it is unmeasurable.
    anything graded    -> an answer arrived. Code that raises, and a reply with no
                          code block, are CAPABILITY failures and stay in the
                          accuracy denominator. Grading must not be able to launder
                          a wrong answer into an availability event.
    grading blew up    -> answer exists but is unjudgeable: unmeasurable, named.
    """
    user = f"```python\n{item['src']}```\n\n{PROMPT}"
    row = {"id": item["id"], "cls": item["cls"]}
    try:
        txt = call_fn(model, user, timeout=200, num_predict=cap)
    except Exception as e:  # noqa: BLE001 - transport, recorded as such
        msg = str(e)
        row.update(passed=False, stage="transport",
                   why=("TRUNCATED" if "truncated" in msg
                        else f"{type(e).__name__}: {msg}"[:70]))
        return row
    try:
        code = extract_code(txt)
        ok, why = run_tests(code, item["tests"])
    except Exception as e:  # noqa: BLE001 - grader error, not a model failure
        row.update(passed=False, stage="grading",
                   why=f"grader_error: {type(e).__name__}"[:70])
        return row
    row.update(passed=bool(ok), stage="graded", why=why)
    return row


def main():
    from ollama_guard import call
    seed = int(os.environ.get("EVO_SEED", "20261008"))
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    models = resolve_models(
        [m for m in os.environ.get("EVO_MODELS", "").split(",") if m] or MODELS)
    if not models:
        raise SystemExit("no requested models are installed; refusing to run")
    items = build_bank(seed)
    (out / "items.json").write_text(json.dumps(
        [{**{k: v for k, v in it.items() if k != "tests"},
          "n_tests": len(it["tests"])} for it in items], indent=1) + "\n")

    detail = {}
    for model in models:
        detail[model] = {}
        for cap in CAPS:
            rows, passed = [], 0
            for it in items:
                rows.append(grade_one(call, model, it, cap))
                passed += bool(rows[-1]["passed"])
            (out / f"out_{model.replace(':', '_')}_cap{cap}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            detail[model][cap] = rows
            col = arm_columns(rows)
            print(f"{model} cap={cap}: acc_all={col['acc_over_all_rows']:.4f} "
                  f"measured_rate={col['measured_rate']} "
                  f"availability={col['availability']:.3f} "
                  f"({col['items'] - col['unmeasurable']}/{col['items']} "
                  f"measurable)", flush=True)

    acc = {m: {c: round(sum(1 for r in detail[m][c] if r["passed"]) / len(items), 4)
               for c in CAPS} for m in models}
    trunc = {m: {c: sum(1 for r in detail[m][c] if r["why"] == "TRUNCATED")
                 for c in CAPS} for m in models}
    columns = {m: {str(c): arm_columns(detail[m][c]) for c in CAPS}
               for m in models}

    # cliff test: cap1000 worse than cap400, paired.
    #
    # The pairing is now restricted to items measurable under BOTH budgets. That is
    # not cosmetic: the sweep's independent variable (the cap) also determines
    # whether a row is measurable at all, so pairing over all items compares two
    # different subsets and lets the x-axis move the y-axis denominator. In
    # sweetspot-04 deepseek-r1 had 0/48 measurable at cap150 and 21/48 at cap1000,
    # so its published 0.000 -> 0.083 -> 0.271 rise was the growth of the measurable
    # set, not a budget effect. Dropped pairs are counted and printed, never hidden.
    per_model, pf, pb = {}, 0, 0
    for m in models:
        f_ = b_ = 0
        usable = []
        for a, b in zip(detail[m][400], detail[m][1000]):
            if unavailability_reason(a["why"]) or unavailability_reason(b["why"]):
                continue
            usable.append((a["id"], b["id"]))
            f_ += bool(b["passed"] and not a["passed"])
            b_ += bool(a["passed"] and not b["passed"])
        per_model[m] = {
            "cap400_fixed": f_, "cap1000_broke": b_,
            "p": round(mcnemar(f_, b_), 6),
            "delta": round(acc[m][1000] - acc[m][400], 4),
            "pairs_used": len(usable),
            "pairs_dropped_unmeasurable": len(items) - len(usable),
            "delta_measurable_only": (
                round(columns[m]["1000"]["measured_rate"]
                      - columns[m]["400"]["measured_rate"], 4)
                if columns[m]["400"]["measured_rate"] is not None
                and columns[m]["1000"]["measured_rate"] is not None else None),
        }
        pf += f_
        pb += b_
    pooled_p = mcnemar(pf, pb)
    negatives = sum(1 for m in models if acc[m][1000] < acc[m][400])
    cliff = bool(pooled_p < 0.05 and pb > pf and negatives >= 1
                 and all(v["delta"] < 0 for v in per_model.values()))
    res = {
        "domain": "code_repair_budget",
        "caps": CAPS, "n_items": len(items),
        "models_requested": MODELS, "models_measured": models,
        "acc": acc, "truncated": trunc, "per_model": per_model,
        "availability_columns": columns,
        "pooled": {"cap400_fixed": pf, "cap1000_broke": pb,
                   "mcnemar_p": round(pooled_p, 6),
                   "pairs_used": sum(v["pairs_used"] for v in per_model.values()),
                   "pairs_dropped_unmeasurable": sum(
                       v["pairs_dropped_unmeasurable"] for v in per_model.values())},
        "families_negative": f"{negatives}/{len(models)}",
        "cliff_confirmed": cliff,
        "confirmed": cliff,
        "note": ("`confirmed` is unchanged and still gates on acc over ALL rows, so "
                 "this run stays comparable with sweetspot-03/04 as registered. "
                 "availability_columns and delta_measurable_only are diagnostics, "
                 "NOT a second gate -- promoting them to the kill switch is the "
                 "owner's pre-registration decision, not a collector side effect."),
    }
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")

    print("\n=== availability / accuracy reported separately ===", flush=True)
    print(f"{'model':<18}{'cap':>6}{'items':>7}{'unmeas':>8}{'avail':>8}"
          f"{'acc_all':>9}{'measured_rate':>15}", flush=True)
    for m in models:
        for c in CAPS:
            col = columns[m][str(c)]
            mr = "n/a" if col["measured_rate"] is None else f"{col['measured_rate']:.4f}"
            print(f"{m:<18}{c:>6}{col['items']:>7}{col['unmeasurable']:>8}"
                  f"{col['availability']:>8.3f}{col['acc_over_all_rows']:>9.4f}"
                  f"{mr:>15}", flush=True)
    print(json.dumps({"acc": acc, "pooled_p": round(pooled_p, 6),
                      "cliff_confirmed": cliff}, ensure_ascii=False))



def availability_selftest() -> int:
    # the classifier table moved into the shared battery; it prints its own detail
    ok = availability_battery() == 0
    print("\n=== arm columns: the sweetspot-04 deepseek pattern ===")
    def arm(n_pass, n_unavail, n_wrong, cap):
        rows = ([{"id": f"p{i}", "passed": True, "why": "pass"}
                 for i in range(n_pass)]
                + [{"id": f"u{i}", "passed": False, "why":
                    'RuntimeError: ollama returned error-text (0 chars): ""'}
                   for i in range(n_unavail)]
                + [{"id": f"w{i}", "passed": False, "why": "wrong value 41"}
                   for i in range(n_wrong)])
        return arm_columns(rows)

    # cap150: every row unmeasurable
    a = arm(0, 48, 0, 150)
    checks = [
        ("cap150 availability == 0.0", a["availability"] == 0.0),
        ("cap150 measured_rate is None (NOT 0.000)", a["measured_rate"] is None),
        ("cap150 acc_over_all_rows == 0.0", a["acc_over_all_rows"] == 0.0),
    ]
    # cap1000: 13 pass, 27 unmeasurable, 8 wrong  -> the audited 0.271 / 0.619
    b = arm(13, 27, 8, 1000)
    checks += [
        ("cap1000 acc_all == 0.2708", b["acc_over_all_rows"] == 0.2708),
        ("cap1000 measured_rate == 0.619", b["measured_rate"] == 0.619),
        ("cap1000 availability == 0.4375", b["availability"] == 0.4375),
        ("cap1000 unmeasurable_by_reason counted",
         b["unmeasurable_by_reason"].get("empty_response") == 27),
    ]
    # a clean arm must be identical in all three columns
    c = arm(28, 0, 20, 400)
    checks += [
        ("clean arm availability == 1.0", c["availability"] == 1.0),
        ("clean arm measured_rate == acc_all",
         c["measured_rate"] == c["acc_over_all_rows"]),
    ]
    # the stage column must outrank the reason string, at the aggregate level too.
    # Built as 3 pass / 1 wrong / 1 unmeasurable so acc_all (3/5) and measured_rate
    # (3/4) DIFFER -- with 3 pass and 1 unmeasurable out of 4 they would coincide at
    # 0.75 and the check would prove nothing.
    stage_rows = [{"id": "s1", "passed": False, "stage": "transport",
                   "why": "ValueError: prompt build failed"},
                  {"id": "s2", "passed": False, "stage": "graded",
                   "why": "wrong value 41"}] + \
                 [{"id": f"q{i}", "passed": True, "stage": "graded",
                   "why": "pass"} for i in range(3)]
    sc = arm_columns(stage_rows)
    checks += [
        ("stage beats string: 1 of 5 unmeasurable", sc["unmeasurable"] == 1),
        ("stage beats string: measured_rate == 0.750 (3/4)",
         sc["measured_rate"] == 0.75),
        ("stage beats string: acc_all == 0.600 (3/5), so the two columns differ",
         sc["acc_over_all_rows"] == 0.6),
        ("the genuine wrong answer is NOT counted unmeasurable",
         sc["items"] - sc["unmeasurable"] == 4),
    ]
    for label, res in checks:
        print(f"  [{'ok' if res else 'FAIL'}] {label}")
        ok = ok and res
    if not any(r for _, r in checks[:1]):
        ok = False

    print("\n=== grade_one: stage separation on the production path ===")
    item = {"id": "g1", "cls": "off_by_one", "src": "def f():\n    return 1",
            "tests": [(((), ), 1)], "hinted": False}

    def raise_transport(model, user, timeout=None, num_predict=None):
        raise RuntimeError('ollama returned error-text (0 chars): ""')

    r = grade_one(raise_transport, "m", item, 400)
    good = (r["stage"] == "transport"
            and unavailability_reason(r["why"]) == "empty_response")
    print(f"  [{'ok' if good else 'FAIL'}] transport failure -> stage=transport, "
          f"why={r['why']!r}")
    ok = ok and good

    # The grading path needs the GRADER to fail, not the transport. An earlier
    # version of this fixture raised inside call_fn and then accepted either stage
    # value -- a vacuous assertion that proved nothing about grading.
    import sys as _sys
    this = _sys.modules[__name__]
    saved = (this.extract_code, this.run_tests)

    def boom(*a, **k):
        raise KeyError("tests are not callable")

    this.extract_code = boom
    try:
        rg = grade_one(lambda *a, **k: "```python\ndef f():\n    return 1\n```",
                       "m", item, 400)
    finally:
        this.extract_code, this.run_tests = saved
    grading_hit = rg["stage"] == "grading"
    print(f"  [{'ok' if grading_hit else 'FAIL'}] grader failure reaches the "
          f"grading stage: stage={rg['stage']} why={rg['why']!r}")
    ok = ok and grading_hit
    graded_unmeas = (outcome_of(rg) == "unavailable:grader_error")
    print(f"  [{'ok' if graded_unmeas else 'FAIL'}] unjudgeable answer is "
          f"unmeasurable, never a silent zero: outcome={outcome_of(rg)}")
    ok = ok and graded_unmeas

    # Stage must outrank the string: an unfamiliar transport exception name would
    # not be recognised by unavailability_reason, yet it is still no answer.
    def odd_transport(model, user, timeout=None, num_predict=None):
        raise ValueError("prompt build failed")

    ro = grade_one(odd_transport, "m", item, 400)
    stage_wins = (outcome_of(ro).startswith("unavailable:")
                  and unavailability_reason(ro["why"]) is None)
    print(f"  [{'ok' if stage_wins else 'FAIL'}] stage outranks the reason string "
          f"for an unlisted exception: outcome={outcome_of(ro)}")
    ok = ok and stage_wins

    def answer_wrong(model, user, timeout=None, num_predict=None):
        return "```python\ndef f():\n    return 99\n```"

    r3 = grade_one(answer_wrong, "m", item, 400)
    honest = (r3["stage"] == "graded" and r3["passed"] is False
              and outcome_of(r3) == "wrong")
    print(f"  [{'ok' if honest else 'FAIL'}] a wrong answer stays a capability "
          f"failure: why={r3['why']!r} outcome={outcome_of(r3)}")
    ok = ok and honest

    print("\nAVAILABILITY SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def replay_stored_run(run_dir: str) -> int:
    """Rebuild the columns from ALREADY STORED rows -- no model calls.

    This is the check that matters: the same functions main() uses must reproduce,
    from the committed out_*.jsonl, the numbers the audit derived by hand. If they
    disagree, one of the two is wrong and neither may be cited.
    """
    d = pathlib.Path(run_dir)
    files = sorted(d.glob("out_*.jsonl"))
    if not files:
        print(f"no out_*.jsonl under {d}")
        return 2
    print(f"=== replay of stored rows: {d}")
    print(f"{'arm':<26}{'items':>6}{'unmeas':>8}{'avail':>8}{'acc_all':>9}"
          f"{'measured':>10}")
    totals = {}
    for f in files:
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        col = arm_columns(rows)
        name = f.name[4:-6]
        totals[name] = col
        mr = "n/a" if col["measured_rate"] is None else f"{col['measured_rate']:.3f}"
        print(f"{name:<26}{col['items']:>6}{col['unmeasurable']:>8}"
              f"{col['availability']:>8.3f}{col['acc_over_all_rows']:>9.3f}"
              f"{mr:>10}")
    ds_un = sum(t["unmeasurable"] for k, t in totals.items()
                if k.startswith("deepseek"))
    print(f"\n  deepseek-r1 unmeasurable total: {ds_un}")
    agree = (totals.get("deepseek-r1_7b_cap150", {}).get("measured_rate") is None
             and totals.get("deepseek-r1_7b_cap1000", {}).get("measured_rate")
             == 0.619
             and ds_un == 111)
    print("  agrees with the hand audit (0.000 undefined, cap1000 0.619, 111 rows): "
          + ("YES" if agree else "NO -- investigate before citing either"))
    return 0 if agree else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        rc = harness_selftest()
        rc = availability_selftest() if rc == 0 else rc
        sys.exit(rc)
    if "--replay" in sys.argv:
        sys.exit(replay_stored_run(sys.argv[sys.argv.index("--replay") + 1]))
    main()
