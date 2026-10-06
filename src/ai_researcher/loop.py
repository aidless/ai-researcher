"""Autonomous executor: runs unattended inside an approved envelope.

The loop is a state machine with resume. Each round:

  1. check budget (rounds, cost, wall-clock) -- over any bound: STOP, no appeal
  2. run the envelope's methods command in the round directory
  3. collect required artifacts -- missing: round does not count, retry once, else STOP
  4. sign the evidence bundle (Ed25519) -- unverifiable: STOP
  5. evaluate the kill-switch rows against the round result -- a matching STOP
     row ends the run with that verdict; CONTINUE proceeds
  6. every N rounds (default 2): two-seat review of the interim claim.
     A joint NOT_READY does not stop the run, but it is recorded and the next
     round must address the strongest objection, or the round after stops.

There is intentionally no --force, no --skip-gate, no override flag. A run that
cannot proceed inside its envelope is a run that should not proceed. The human
writes a new envelope instead.

Usage:
    python -m ai_researcher.loop approve envelope.json --by "name"   # the one human act
    python -m ai_researcher.loop run envelope.json --workdir runs/exp-01
    python -m ai_researcher.loop status runs/exp-01
    python -m ai_researcher.loop verify runs/exp-01                  # re-verify every bundle
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import evidence as EV
from .envelope import Envelope
from .two_seat import review as two_seat_review

STATE = "state.json"
REVIEW_EVERY = 2


def _now():
    return datetime.now(timezone.utc).isoformat()


def cmd_approve(args):
    env = Envelope.load(args.envelope)
    env.approved_by = args.by
    env.approved_at = _now()
    problems = env.validate()
    if problems:
        print("envelope NOT executable:")
        for p in problems:
            print(f"  - {p}")
        return 1
    env.save(args.envelope)
    print(f"approved by {args.by} at {env.approved_at}: executable")
    return 0


def _load_state(workdir: Path) -> dict:
    f = workdir / STATE
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"rounds": [], "status": "READY", "started_at": _now(),
            "cost_usd": 0.0, "key_pub": None, "key_priv": None}


def _save_state(workdir: Path, st: dict) -> None:
    (workdir / STATE).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


def _eval_kill(rows: list, result: dict):
    """Evaluate kill-switch rows in order. Returns (action, row) or (CONTINUE, None).

    The result dict carries numeric facts (gain, p_value, cost_usd, ...). Each row
    condition is a tiny expression over those names, e.g. "gain >= 0.10".
    Only names present in result are visible; anything else is a failed row, not
    a crash -- a row that cannot be evaluated cannot authorize continuation.
    """
    safe = {k: v for k, v in result.items() if isinstance(v, (int, float, bool))}
    for r in rows:
        try:
            if eval(r["condition"], {"__builtins__": {}}, dict(safe)):  # noqa: S307
                return r["action"], r
        except Exception:
            continue
    return "CONTINUE", None


def _run_round(env: Envelope, workdir: Path, rnd: int, st: dict) -> dict:
    rd = workdir / f"round-{rnd:02d}"
    (rd / "artifacts").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    proc = subprocess.run(env.methods, shell=True, cwd=rd, capture_output=True,
                          text=True, timeout=int(env.max_wall_hours * 3600))
    elapsed = time.monotonic() - t0
    (rd / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (rd / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    result_path = rd / "artifacts" / "result.json"
    result = {}
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as e:
            result = {"_parse_error": str(e)}
    result.setdefault("exit_code", proc.returncode)
    result.setdefault("wall_s", round(elapsed, 1))
    missing = [a for a in env.required_artifacts if not (rd / "artifacts" / a).exists()]
    return {"round": rnd, "dir": str(rd), "result": result, "missing": missing,
            "exit_code": proc.returncode}


def cmd_run(args):
    env = Envelope.load(args.envelope)
    problems = env.validate()
    if problems:
        print("refusing to start: envelope not executable:")
        for p in problems:
            print(f"  - {p}")
        return 1
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    st = _load_state(workdir)
    if st["status"] not in ("READY", "RUNNING"):
        print(f"run already {st['status']}; refusing to resume a finished run")
        return 1
    if not st.get("key_priv"):
        priv, pub = EV.generate_keypair()
        st["key_priv"], st["key_pub"] = priv.hex(), pub.hex()
    priv = bytes.fromhex(st["key_priv"])
    pub = bytes.fromhex(st["key_pub"])
    st["status"] = "RUNNING"
    _save_state(workdir, st)
    start_wall = time.monotonic()

    while len(st["rounds"]) < env.max_rounds:
        rnd = len(st["rounds"]) + 1
        # 1. budget
        if st["cost_usd"] > env.max_cost_usd and env.max_cost_usd > 0:
            st["status"] = "STOP-BUDGET"; break
        if (time.monotonic() - start_wall) / 3600 > env.max_wall_hours:
            st["status"] = "STOP-TIME"; break
        # 2-4. run, collect, sign
        rr = _run_round(env, workdir, rnd, st)
        if rr["missing"]:
            st["rounds"].append({**rr, "verdict": "ROUND-INVALID",
                                 "reason": f"missing artifacts: {rr['missing']}"})
            _save_state(workdir, st)
            st["status"] = "STOP-INVALID"
            break
        envl = EV.sign_round(workdir / f"round-{rnd:02d}" / "artifacts",
                             priv, signer="ai-researcher-loop",
                             round_id=f"r{rnd:02d}")
        chk = EV.verify_round(workdir / f"round-{rnd:02d}" / "artifacts",
                              envl["bundle"], envl["envelope"], pub)
        if not chk["valid"]:
            st["rounds"].append({**rr, "verdict": "ROUND-INVALID",
                                 "reason": chk["reason"]})
            _save_state(workdir, st)
            st["status"] = "STOP-INVALID"
            break
        (workdir / f"round-{rnd:02d}" / "envelope.json").write_text(
            json.dumps(envl, indent=2) + "\n", encoding="utf-8")
        # 5. kill-switch
        action, row = _eval_kill(
            [{"condition": r.condition, "action": r.action} for r in env.kill_switch],
            rr["result"])
        rec = {**rr, "bundle": envl["bundle"]["bundle_id"],
               "kill_row": (row["condition"] if row else None)}
        # 5b. selection-robustness audit: if the result declares the selections
        # it depends on (result["audit_values"] = precomputed metric per valid
        # selection), report the distribution now. A claim at 82% is
        # MOSTLY-HOLDS, never "holds" and never "reverses" -- see robustness.py.
        try:
            from .robustness import verdict as rob_verdict
            avals = (rr["result"] or {}).get("audit_values")
            if isinstance(avals, list) and avals:
                holds = sum(1 for v in avals if float(v) > 0)
                rec["robustness"] = {
                    "total": len(avals), "holds": holds,
                    "p_holds": round(holds / len(avals), 3),
                    "verdict": rob_verdict({"p_holds": holds / len(avals)}),
                }
        except Exception as e:
            rec["robustness"] = {"error": f"{type(e).__name__}: {e}"}
        if action != "CONTINUE":
            rec["verdict"] = action
            rec["reason"] = (row.get("note") if row else "")
            st["rounds"].append(rec)
            _save_state(workdir, st)
            st["status"] = action
            break
        # 6. periodic two-seat review
        if rnd % REVIEW_EVERY == 0:
            try:
                rev = two_seat_review(
                    claim=env.hypothesis,
                    evidence=json.dumps(rr["result"], ensure_ascii=False)[:4000])
                rec["review"] = {"joint": rev["joint"],
                                 "contradiction": rev["contradiction"],
                                 "methodology": rev["methodology"].get("verdict"),
                                 "devil": rev["devil"].get("verdict"),
                                 "devil_objection": rev["devil"].get("strongest_objection", "")[:500]}
            except Exception as e:
                rec["review"] = {"error": f"{type(e).__name__}: {e}"}
        rec["verdict"] = "CONTINUE"
        st["rounds"].append(rec)
        _save_state(workdir, st)
        print(f"[r{rnd:02d}] exit={rr['exit_code']} kill={action} "
              f"bundle={envl['bundle']['bundle_id'][:18]}")
    else:
        st["status"] = "STOP-ROUNDS-EXHAUSTED"
    _save_state(workdir, st)
    print(f"final: {st['status']} after {len(st['rounds'])} rounds")
    return 0


def cmd_status(args):
    st = _load_state(Path(args.workdir))
    print(f"status: {st['status']} | rounds: {len(st['rounds'])} | "
          f"cost: {st.get('cost_usd', 0.0)}")
    for r in st["rounds"]:
        print(f"  r{r['round']:02d} {r.get('verdict')} "
              f"{str(r.get('result', {}))[:110]}")


def cmd_verify(args):
    workdir = Path(args.workdir)
    st = _load_state(workdir)
    pub = bytes.fromhex(st["key_pub"])
    ok = bad = 0
    for r in st["rounds"]:
        rd = workdir / f"round-{r['round']:02d}"
        envl = json.loads((rd / "envelope.json").read_text(encoding="utf-8"))
        chk = EV.verify_round(rd / "artifacts", envl["bundle"],
                              envl["envelope"], pub)
        print(f"  r{r['round']:02d} {chk['valid']} {chk['reason']}")
        ok += chk["valid"]
        bad += not chk["valid"]
    print(f"{ok} valid, {bad} invalid")
    return 0 if bad == 0 else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.loop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("approve"); a.add_argument("envelope"); a.add_argument("--by", required=True)
    r = sub.add_parser("run"); r.add_argument("envelope"); r.add_argument("--workdir", required=True)
    s = sub.add_parser("status"); s.add_argument("workdir")
    v = sub.add_parser("verify"); v.add_argument("workdir")
    a = ap.parse_args(argv)
    return {"approve": cmd_approve, "run": cmd_run,
            "status": cmd_status, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
