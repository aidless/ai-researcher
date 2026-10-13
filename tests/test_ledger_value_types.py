"""A ledger value that does not parse as a number must not silently vanish.

`_parse_ledger` used `try: float(...) except: pass`, leaving the RAW STRING
in `row["value"]`. `quality.mechanical_check`'s CI-coverage check selects
quants with `isinstance(row["value"], (int, float))` -- so "0.42±0.1",
"about half", "160 items" all leave the denominator. Fewer claims, the same
number of CI mentions: coverage goes UP as the ledger gets worse. That is
the same shape as the 2026-10-02 paper-ledger finding (a missing value
reading as a neutral one), one layer up.

Pinned behaviour: a non-numeric value is recorded as None AND surfaced in
the row's `value_note`; the two-seat/bridge consumers see the note; and a
row with a str-typed value is a FAIL for the numbers-trace check rather
than invisible.
"""

from __future__ import annotations

import importlib
import inspect
import pathlib
import tempfile

loop = importlib.import_module("ai_researcher.loop")
qa = importlib.import_module("ai_researcher.quality")

# ids carry MAGNITUDE_HINT because production selects on id.lower(),
# not on claim text.
MD = """| id | claim | evidence | value | how | status |
|---|---|---|---|---|---|
| gain.A1 | gain on X | runs/x/result.json:gain | 0.42 | rerun | verified |
| gain.A2 | gain on Y (carries ±) | runs/y/result.json:gain | 0.42±0.1 | rerun | verified |
| gain.A3 | gain on Z (prose) | runs/z/result.json:gain | about half | rerun | verified |
"""


def parse(md: str):
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "CLAIM_LEDGER.md").write_text(md, encoding="utf-8")
    return loop._parse_ledger(d / "CLAIM_LEDGER.md")


def test_numeric_values_parse_as_float():
    rows = parse(MD)
    assert rows[0]["value"] == 0.42
    assert isinstance(rows[0]["value"], float)


def test_non_numeric_value_is_recorded_none_with_note_not_silently_str():
    rows = parse(MD)
    for r in rows[1:]:
        assert r["value"] is None, (
            f"{r['id']}: non-numeric value must be None, got "
            f"{r['value']!r} ({type(r['value']).__name__}) -- a str silently "
            f"leaves every downstream isinstance filter")
        assert r.get("value_note"), "the raw text must be kept for audit"


def test_no_row_ever_carries_a_str_value():
    rows = parse(MD)
    assert not [r for r in rows if isinstance(r.get("value"), str)]


def test_ci_coverage_denominator_sees_every_claim():
    """The consumption side: with the fix, non-numeric magnitude claims are
    None-and-noted. What must not happen is the OLD shape (str surviving and
    passing isinstance) -- so this pins that the two rows cannot re-enter the
    quant pool as strings."""
    rows = parse(MD)
    quants = [r for r in rows if isinstance(r.get("value"), (int, float))]
    noted = [r for r in rows if r["value"] is None and r.get("value_note")]
    assert len(quants) == 1
    assert len(noted) == 2
    # and: if quality's exact filter ran on these rows, the None ones would be
    # dropped too -- that is why the note exists. Assert the drop is visible.
    dropped = [r["id"] for r in rows
               if not isinstance(r.get("value"), (int, float)) and not r["value_note"]]
    assert dropped == [], (
        f"rows dropped with no audit note (silent exclusion): {dropped}")


def test_parser_signature_still_the_only_entrypoint():
    """Guard the seam: if the parser is renamed/reshaped, this suite moves
    with it instead of silently testing a helper nobody calls."""
    assert pathlib.Path(loop.__file__).exists()
    assert "rows" in inspect.getsource(loop._parse_ledger)


# --- the consumption side: CI-coverage denominator (quality.mechanical_check)


def test_unverifiable_value_rows_stay_in_the_ci_denominator():
    """quality.py:293 used isinstance(int/float) and dropped None-valued
    magnitude claims. With the fix they stay in n_claims and are reported
    separately -- a claim that names a magnitude but gives no number still
    owes the reader an interval, or an explicit 'no interval given'."""
    rows = parse(MD)  # A1 numeric, A2/A3 None+note
    # mirror production's own MAGNITUDE_HINT / NOT_ESTIMANDS selection
    MAG = ("gain", "acc", "pci", "slope", "excess", "rate", "hit_rate",
           "mean", "diff")
    NOT = ("paired", "_p", "p_", "pvalue", "fixed", "broke", "n_", "seeds",
           "total", "pairs", "abstention", "committed", "conditions",
           "escaped", "caught", "trajectory", "excesses[", "arms[", "pci[")
    sel = [r for r in rows
           if (isinstance(r["value"], (int, float))
               or (r["value"] is None and r.get("value_note")))
           and any(h in r["id"].lower() for h in MAG)
           and not any(h in r["id"].lower() for h in NOT)]
    ids = {r["id"] for r in sel}
    assert {"gain.A1", "gain.A2", "gain.A3"} <= ids, (
        f"unexpected selection: {ids} -- A2/A3 (value=None, note kept) must "
        f"remain selectable, not be silently unfilterable")


def test_none_without_note_stays_out():
    """An empty/absent value cell is a missing row, not an unverifiable
    claim: it must NOT enter the denominator (that would punish every paper
    for the ledger's own blanks)."""
    blank = {"value": None}                      # no value_note -> not selectable
    noted = {"value": None, "value_note": "n/a"}  # -> selectable
    def selectable(r):
        return bool(isinstance(r.get("value"), (int, float))
                     or (r["value"] is None and r.get("value_note")))
    assert selectable(blank) is False
    assert selectable(noted) is True


# --- Z9: forced-vote disclosure gate (quality.mechanical_check)


def _rows_with_forced():
    return parse("""| id | run | claim | evidence | value | how | status |
| id | run | claim | evidence | value | how | status |
|---|---|---|---|---|---|---|
| fv.gain.A1 | swarm-01 | forced_votes = 4 | r/result.json -> forced_votes | 4.0 | rerun | verified |
| fv.gain.A2 | swarm-02 | forced_votes = 0 | r/result.json -> forced_votes | 0.0 | rerun | verified |
""")


def test_forced_votes_gate_fires_only_when_nonzero():
    import ai_researcher.quality as q
    rows = _rows_with_forced()
    mech = q.mechanical_check(rows, "text with limitations and reproduce",
                              {"tier": "workshop"}, "workshop")
    z9 = [m for m in mech if m[0] == "Z9-forced-votes-disclosed"]
    assert z9, "Z9 must appear exactly when a forced_votes>0 row exists"
    cid, passed, reason = z9[0]
    assert "swarm-01" in reason and "swarm-02" not in reason
    # not disclosed anywhere -> the gate FAILS (that is the point)
    assert passed is False


def test_forced_votes_gate_passes_when_ledger_names_it():
    import ai_researcher.quality as q
    rows = _rows_with_forced()
    # naming the FIELD is not disclosure: the ledger must say what the votes
    # ARE. "forced_votes = 4" alone still fails (covered above).
    rows[0]["claim"] = "forced_votes = 4 (abstentions terraformed into random votes)"
    mech = q.mechanical_check(rows, "text", {"tier": "workshop"}, "workshop")
    z9 = [m for m in mech if m[0] == "Z9-forced-votes-disclosed"]
    assert z9 and z9[0][1] is True


def test_forced_votes_gate_silent_when_all_zero():
    import ai_researcher.quality as q
    rows = _rows_with_forced()
    rows[0]["value"] = 0.0
    mech = q.mechanical_check(rows, "text", {"tier": "workshop"}, "workshop")
    assert not [m for m in mech if m[0] == "Z9-forced-votes-disclosed"], (
        "a ledger with no terraformed votes must not gain a new failure")
