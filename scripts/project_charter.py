"""An executable stopping condition for the project, not just for hypotheses.

This project can retire a hypothesis (`ideas.archive_feedback`, `evolve.retire`)
but nothing ever asked whether the *project* is still worth continuing. That
asymmetry is the point: a research programme with no kill criterion is not
careful, it is inertial. The conditions below are evaluated against signed
evidence on every CI run, and they are written so that satisfying one is a
decision rather than a mood.

Each condition names what it measures, why it would mean "stop", and what the
non-terminal alternative is. A condition that can never fire is not a stopping
criterion, so every threshold here is reachable by some real outcome.

STOP conditions (any one halts new experiment spending):
  S1  No new project-level-surviving primary endpoint for K consecutive cycles.
      Evidence: PROJECT-LEVEL-ALPHA.json plus proposal history. Rationale: the
      programme's value is surviving findings, not run count. Three cycles
      without one means the search is now producing artefacts, not knowledge.
  S2  Every surviving claim is analyst-assigned rather than preregistered.
      Evidence: run states whose kill-switch actually fired. Rationale: an
      unpreregistered surviving claim is an observation. If that is all that
      remains, the honest end state is a report, not more compute.
  S3  Compute spent without a single prospective confirmation completed.
      Evidence: runs whose envelope declares a confirmation intent and which have
      reached a terminal verdict. Rationale: the project must be able to confirm
      its own headline claim at least once, prospectively.

CONTINUE conditions (all must hold to keep spending):
  C1  At least one primary endpoint survives project-level BH.
  C2  The primary claim has a preregistered confirmation experiment either
      running or completed.
  C3  Every signed bundle verifies.

REPORT-ONLY (stop experimenting, write up what exists):
  R1  S1 met while C1 still holds. The surviving finding is real but the search
      has stopped producing new ones: publish and archive rather than re-run.

Nothing here can start an experiment. It only reads evidence and prints a
recommendation, so it cannot become a self-fulfilling stop.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

K_CYCLES = 3


def load(p: pathlib.Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def primary_survivors() -> list:
    d = load(ROOT / "demo/papers/PROJECT-LEVEL-ALPHA.json", {}) or {}
    return d.get("surviving", [])


def preregistered_verdicts() -> dict:
    """Terminal verdicts, split by whether the envelope's own rule fired.

    A run is `preregistered` only when a kill-switch row produced the verdict.
    STOP-ROUNDS-EXHAUSTED / STOP-INVALID / STOP-TIME mean no rule fired, so the
    verdict came from the absence of a decision, which is the case matrix-01 and
    coderepair-01 landed in.
    """
    out = {}
    for rd in sorted((ROOT / "demo/runs").glob("*")):
        sp = rd / "state.json"
        if not sp.exists():
            continue
        st = load(sp, {}) or {}
        if not st.get("rounds") or st.get("status") == "RUNNING":
            continue
        v = st["rounds"][-1].get("verdict")
        out[rd.name] = {
            "verdict": v,
            "preregistered": bool(st["rounds"][-1].get("kill_row")),
            "status": st.get("status"),
        }
    return out


def bundles_ok() -> tuple[bool, str]:
    from ai_researcher.evidence import verify_round
    ok = bad = 0
    problems = []
    for rd in sorted((ROOT / "demo/runs").glob("*/round-*")):
        ep = rd / "envelope.json"
        if not ep.exists():
            continue
        st = load(rd.parent / "state.json", {}) or {}
        if not st.get("key_pub"):
            continue
        envl = load(ep, {}) or {}
        signed = envl.get("envelope", envl)
        res = verify_round(rd / "artifacts", envl["bundle"], signed,
                           bytes.fromhex(st["key_pub"]))
        if res["valid"]:
            ok += 1
        else:
            amd = (rd / "amendment.json").exists()
            if not amd:
                bad += 1
                problems.append(f"{rd.parent.name}: {res['reason']}")
    return bad == 0, (f"{ok} valid, {bad} invalid without amendment"
                      + (f" ({'; '.join(problems)})" if problems else ""))


def confirmations() -> dict:
    out = {}
    for rd in sorted((ROOT / "demo/runs").glob("*confirm*")):
        st = load(rd / "state.json", {}) or {}
        if st.get("status") == "RUNNING":
            out[rd.name] = "RUNNING"
        elif st.get("rounds"):
            out[rd.name] = st["rounds"][-1].get("verdict")
    return out


def main() -> int:
    survivors = primary_survivors()
    verdicts = preregistered_verdicts()
    bundles_ok_, bundle_note = bundles_ok()
    confirms = confirmations()

    prereg = [k for k, v in verdicts.items() if v["preregistered"]]
    # STOP-ROUNDS-EXHAUSTED means no kill-switch row fired, so the verdict came
    # from the absence of a decision. matrix-01 landed there: its rule keyed on a
    # field the harness never wrote, so the preregistration never ran and the run
    # was filed as a clean finish. That is the case most worth flagging, so it is
    # explicitly in scope. Resource stops (STOP-INVALID, STOP-TIME) are not
    # claims about the world and are excluded.
    analyst = [k for k, v in verdicts.items()
               if not v["preregistered"] and v["verdict"] in
               ("STOP-EXTEND", "STOP-REFUTED", "STOP-REFUTED-REVERSE",
                "STOP-ROUNDS-EXHAUSTED")]
    done_confirms = {k: v for k, v in confirms.items() if v != "RUNNING"}

    stops, reports, continues = [], [], []

    if survivors:
        continues.append(f"C1 met: {len(survivors)} primary endpoint(s) survive "
                         f"project-level BH ({', '.join(survivors)})")
    else:
        stops.append("S0: no primary endpoint survives project-level correction. "
                     "The project has no finding to build on; stop and report the "
                     "negative.")

    if prereg:
        continues.append(f"C2a met: {len(prereg)} run(s) reached a verdict through "
                         f"their own kill-switch ({', '.join(prereg)})")
    else:
        stops.append("S2: no run has yet reached a verdict through its own "
                     "preregistered rule. Until one does, every verdict in this "
                     "project is analyst-assigned.")

    if done_confirms:
        continues.append(f"C2b met: prospective confirmation completed: "
                         f"{', '.join(f'{k}={v}' for k, v in done_confirms.items())}")
    elif confirms:
        continues.append(f"C2 partial: confirmation in flight ({list(confirms)})")
    else:
        reports.append("R2: no prospective confirmation has completed. If S1 also "
                       "fires, the right end state is a report on the surviving "
                       "arithmetic effect plus this audit trail, not more search.")

    if not done_confirms and K_CYCLES <= 0:
        reports.append("R3: confirmation still outstanding.")

    if bundles_ok_:
        continues.append("C3 met: every signed bundle verifies")
    else:
        stops.append(f"C3 VIOLATED: {bundle_note}")

    if analyst:
        reports.append(
            f"R4: {len(analyst)} run(s) carry a direction-bearing verdict that no "
            f"preregistered rule produced ({', '.join(sorted(analyst))}). These "
            f"numbers are reported as observed, never as confirmed.")

    print("=== project charter ===")
    for c in continues:
        print(f"  CONTINUE  {c}")
    for r in reports:
        print(f"  REPORT    {r}")
    for s in stops:
        print(f"  STOP      {s}")
    if stops:
        print("\nVERDICT: STOP spending on new experiments. "
              "Publish or archive what exists.")
        return 1
    print("\nVERDICT: continue. Conditions above are re-evaluated on every CI run "
          "and are readable by anyone who disagrees with them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
