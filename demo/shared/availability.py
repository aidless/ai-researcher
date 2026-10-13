"""Availability accounting shared by every local collector in this demo tree.

One implementation on purpose. It started life inside run_sweetspot_amp.py as the
response to sweetspot-04, where 111 rows of 'ollama returned error-text (0 chars)'
were charged to capability and the run's best arm flipped. Collectors that need it
import it from here rather than copying the predicate -- a second copy of a
classifier is the defect this module exists to prevent, and this project has already
been bitten twice by two writable copies drifting apart.

THE RULE, in one sentence: a row is UNMEASURABLE when no usable answer arrived
(transport failure, empty response, absent model, timeout, grader blow-up); it is a
CAPABILITY FAILURE when an answer arrived and graded wrong -- including code that
raises and a reply with no code block. Never collapse the two into one rate.

Why the predicate is prefix-based and not substring: a substring rule excuses
`wrong value ['timeout']` (a wrong answer that happens to mention the task's own
vocabulary) as an availability event. That is the scorer bug of 2026-10-09 pointed
the other way, and laundering a wrong answer into "no answer" is worse than the
original misclassification because it silently raises the arm.

Use:
    from availability import arm_columns, outcome_of, unavailability_reason
    cols = arm_columns(rows)          # per arm
    print(cols["availability"], cols["measured_rate"], cols["acc_over_all_rows"])

Run the battery: python3 availability.py --selftest
"""

from __future__ import annotations

import json
import re
import sys

__all__ = ["unavailability_reason", "outcome_of", "arm_columns",
           "transport_row", "selftest", "replay_dir"]

_EXC_HEAD = re.compile(
    r"^([A-Za-z_]+(?:Error|Exception|Disconnected|Timeout|Interrupted))\b")

# Known transport/infra exception names, mapped to a specific label.
_UNAVAIL_EXCEPTIONS = {
    "httperror": "http_error",
    "timeouterror": "timeout",
    "readtimeout": "timeout",
    "connecttimeout": "timeout",
    "sockettimeout": "timeout",
    "urlerror": "connection_error",
    "connectionreseterror": "connection_error",
    "connectionabortederror": "connection_error",
    "connectionrefusederror": "connection_error",
    "connectionerror": "connection_error",
    "remotedisconnected": "connection_error",
    "brokenpipeerror": "connection_error",
    "oserror": "connection_error",
    "internalservererror": "http_error",
    "badgatewayerror": "http_error",
    "serviceunavailableerror": "http_error",
}


def unavailability_reason(why):
    """Availability label for a recorded reason, or None if an answer arrived."""
    s = str(why or "").strip()
    if not s:
        return None
    if s.upper().startswith("TRUNCATED"):
        return "truncated_at_cap"
    if s.startswith("grader_error"):
        return "grader_error"
    m = _EXC_HEAD.match(s)
    if not m:
        return None
    name = m.group(1).lower()
    if name in _UNAVAIL_EXCEPTIONS:
        return _UNAVAIL_EXCEPTIONS[name]
    if name == "runtimeerror":
        low = s.lower()
        # Order matters, and so does needle width. An earlier version tested
        # "chars" before "truncat", so "RuntimeError: truncated at num_predict=400
        # (528 chars)" came out empty_response -- right bucket (unmeasurable),
        # wrong reason, and those two diagnoses need different fixes: a budget
        # that is too small versus a model that said nothing. The guard's own
        # phrasing ("error-text") is the specific needle; a bare length report is
        # not evidence of emptiness.
        if "truncat" in low:
            return "truncated_at_cap"
        if "error-text" in low:
            return "empty_response"
        return "transport_error"
    # An unlisted exception name is still an exception: something blew up, rather
    # than an answer arriving and being wrong. Verified against the corpus on
    # 2026-10-09 before relying on it: of 2494 stored reasons, 206 begin with an
    # exception name and ALL 206 have passed=False, with shapes that are transport
    # or truncation ("truncated at num_predict=400", "HTTP Error 404"). Graded
    # wrong answers in this corpus read "candidate raised" / "wrong value 41" /
    # "expected None, got 0" and match no exception head, so this default cannot
    # launder a capability failure. A collector that records grading exceptions
    # without a `stage` field must set stage, which outranks this table entirely.
    return "transport_error"


def outcome_of(row):
    """pass | wrong | unavailable:<reason>. The recorded stage outranks the string.

    Rows written before this field existed fall back to the reason text, so replay
    of committed artifacts keeps working.
    """
    if row.get("passed") is True:
        return "pass"
    stage = row.get("stage")
    reason = unavailability_reason(row.get("why") or "")
    if stage in ("transport", "grading") and not reason:
        reason = "grader_error" if stage == "grading" else "transport_error"
    return f"unavailable:{reason}" if reason else "wrong"


def arm_columns(rows):
    """Three numbers, never one. See the module docstring for the rule."""
    total = len(rows)
    unavail = [r for r in rows if outcome_of(r).startswith("unavailable")]
    passed = [r for r in rows if outcome_of(r) == "pass"]
    measurable = total - len(unavail)
    reasons = {}
    for r in unavail:
        k = outcome_of(r).split(":", 1)[1]
        reasons[k] = reasons.get(k, 0) + 1
    return {
        "items": total,
        "unmeasurable": len(unavail),
        "availability": round(measurable / total, 4) if total else 0.0,
        # None, NOT 0.0: an arm with nothing measurable made no measurement.
        "measured_rate": (round(len(passed) / measurable, 4)
                          if measurable else None),
        "acc_over_all_rows": round(len(passed) / total, 4) if total else 0.0,
        "unmeasurable_by_reason": reasons,
    }


def transport_row(row_id, exc_or_none, extra=None):
    """Build the row a transport failure should produce, staged as such."""
    why = "TRUNCATED" if (exc_or_none and "truncated" in str(exc_or_none)) else (
        f"{type(exc_or_none).__name__}: {exc_or_none}"[:70] if exc_or_none
        else "transport_error")
    r = {"id": row_id, "passed": False, "stage": "transport", "why": why}
    r.update(extra or {})
    return r


CASES = [
    ('TRUNCATED', "truncated_at_cap", "the collector's own marker"),
    ('RuntimeError: ollama returned error-text (0 chars): ""',
     "empty_response", "the 111 sweetspot-04 rows"),
    ("HTTPError: HTTP Error 404: Not Found", "http_error",
     "absent model, the coderepair-01 shape"),
    ("TimeoutError: timed out", "timeout", "client ceiling"),
    ("URLError: <urlopen error [Errno 111]>", "connection_error", "socket level"),
    ("ConnectionRefusedError: [Errno 111] Connection refused",
     "connection_error", "MISSED on first shipping: ollama down, was -> None"),
    ("ReadTimeout: The read operation timed out", "timeout",
     "MISSED: requests-style name does not end in Error"),
    ("BrokenPipeError: [Errno 32] Broken pipe", "connection_error",
     "MISSED: server died mid-write"),
    ("RuntimeError: truncated at num_predict=400 (528 chars)",
     "truncated_at_cap", "the transfer-confirmation shape, 15 rows"),
    ("TypeError: unhashable", "transport_error",
     "unlisted exception name defaults to unmeasurable, corpus-verified safe"),
    ("grader_error: KeyError", "grader_error", "unjudgeable answer"),
    ("candidate raised", None, "code ran and raised => capability, must stay"),
    ("wrong value 41", None, "answered and wrong"),
    ("wrong value ['timeout']", None,
     "ANTI-LAUNDERING: mentions timeout, still capability"),
    ("expected None, got 0", None, "answered and wrong"),
    ("", None, "no reason recorded is not evidence of no answer"),
    ("pass", None, "the pass marker"),
]


def selftest() -> int:
    ok = True
    print("=== availability battery (shared) ===")
    for why, expect, note in CASES:
        got = unavailability_reason(why)
        if got != expect:
            ok = False
        print(f"  [{'ok' if got == expect else 'FAIL'}] {why!r:<52} -> {got!r}"
              f" (want {expect!r})  # {note}")

    rows = [{"id": "s1", "passed": False, "stage": "transport",
             "why": "ValueError: prompt build failed"},
            {"id": "s2", "passed": False, "stage": "graded", "why": "wrong value 41"}]
    rows += [{"id": f"q{i}", "passed": True, "stage": "graded", "why": "pass"}
             for i in range(3)]
    c = arm_columns(rows)
    # built so the two rates DIFFER (3/5 vs 3/4). Equal columns would prove nothing.
    for label, res in [
        ("stage beats string: 1 of 5 unmeasurable", c["unmeasurable"] == 1),
        ("measured_rate == 0.750 (3/4)", c["measured_rate"] == 0.75),
        ("acc_over_all_rows == 0.600 (3/5), so the columns differ",
         c["acc_over_all_rows"] == 0.6),
        ("a genuine wrong answer is not counted unmeasurable",
         c["items"] - c["unmeasurable"] == 4),
    ]:
        if not res:
            ok = False
        print(f"  [{'ok' if res else 'FAIL'}] {label}")

    empty = arm_columns([{"id": "z", "passed": False, "stage": "transport",
                          "why": 'RuntimeError: ollama returned error-text (0 chars)'}])
    res = (empty["availability"] == 0.0 and empty["measured_rate"] is None
           and empty["acc_over_all_rows"] == 0.0)
    if not res:
        ok = False
    print(f"  [{'ok' if res else 'FAIL'}] fully unmeasurable arm: rate is None, "
          "not 0.000")
    print("\nAVAILABILITY BATTERY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def replay_dir(artifacts, pattern="out_*.jsonl"):
    """Rebuild the columns from committed rows -- no model calls."""
    from pathlib import Path
    d = Path(artifacts)
    files = sorted(d.glob(pattern))
    if not files:
        print(f"no {pattern} under {d}")
        return None
    out = {}
    print(f"=== replay: {d}")
    for f in files:
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        col = arm_columns(rows)
        out[f.name] = col
        mr = "n/a" if col["measured_rate"] is None else f"{col['measured_rate']:.3f}"
        print(f"  {f.name[4:-6]:<26} items={col['items']:<4} "
              f"unmeas={col['unmeasurable']:<4} avail={col['availability']:.3f} "
              f"acc_all={col['acc_over_all_rows']:.3f} measured={mr}")
    return out


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--replay" in sys.argv:
        p = sys.argv[sys.argv.index("--replay") + 1]
        pat = sys.argv[sys.argv.index("--replay") + 2] \
            if len(sys.argv) > sys.argv.index("--replay") + 2 else "out_*.jsonl"
        sys.exit(0 if replay_dir(p, pat) is not None else 2)
    print(__doc__)
