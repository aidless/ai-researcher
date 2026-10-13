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
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import evidence as EV
from . import keystore as KS
from .envelope import Envelope
from .two_seat import review as two_seat_review

STATE = "state.json"
REVIEW_EVERY = 2
# Bumped when the round record gained a review on terminal verdicts (the 5c placement).
# The gate requires a review record iff a run was produced by schema >= 2 -- a code
# marker, not a wall-clock date: seed6-01 started 2026-10-08T18:23Z and a date test for
# "2026-10-09" classified it as legacy, because local time was already 10-09 while the
# stamp is UTC. Do not date-gate this again.
LOOP_SCHEMA = 2


def should_review(rnd: int, max_rounds: int, every: int = REVIEW_EVERY) -> bool:
    """Does the two-seat review fire on this round?

    It used to be `rnd % REVIEW_EVERY == 0` alone, and every envelope on disk (14 of 15)
    sets max_rounds=1 -- so the periodic condition could never be satisfied and the
    judgment stage was structurally unreachable: 0 of 27 recorded rounds carry a review.
    A run that ends without ever being reviewed is exactly what this fixes: the last
    round is always reviewed, whatever the cadence says.
    """
    return rnd % every == 0 or rnd >= max_rounds


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
    """Atomic write: temp file + rename, so a crash mid-write cannot corrupt."""
    tmp = workdir / (STATE + ".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, workdir / STATE)


def _acquire_lock(workdir: Path):
    """Exclusive lock: two processes on one workdir corrupt state silently."""
    import os as _os
    lock = workdir / "run.lock"
    try:
        fd = _os.open(lock, _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
    except FileExistsError:
        try:
            pid = int(lock.read_text(encoding="utf-8").strip().split()[0])
            _os.kill(pid, 0)
            print(f"refusing: {lock} held by live pid {pid}")
            return None
        except (ValueError, ProcessLookupError, FileNotFoundError):
            print(f"stale lock {lock}, taking over")
            lock.unlink(missing_ok=True)
            return _acquire_lock(workdir)
    _os.write(fd, f"{_os.getpid()} {_now()}\n".encode())
    return fd


def _release_lock(fd, workdir: Path) -> None:
    import os as _os
    try:
        _os.close(fd)
    except Exception:
        pass
    (workdir / "run.lock").unlink(missing_ok=True)


def _eval_kill(rows: list, result: dict):
    """Evaluate kill-switch rows in order. Returns (action, row, unevaluable).

    The result dict carries numeric facts (gain, p_value, cost_usd, ...). Each row
    condition is a tiny expression over those names, e.g. "gain >= 0.10".
    Only names present in result are visible; anything else is a failed row, not
    a crash -- a row that cannot be evaluated cannot authorize continuation.

    A row that raises (NameError on a field the artifact never writes) is
    UNEVALUABLE, and an unevaluable row is returned to the caller instead of
    being silently skipped. matrix-01 (2026-10-07) shipped a kill-switch on
    `confirmed == True` while its script emitted no `confirmed` field: the
    exception was swallowed, no row fired, and the run concluded as
    STOP-ROUNDS-EXHAUSTED -- a preregistered decision rule that never ran,
    reported as a clean finish. Silent-skip made status a lie.
    """
    safe = {k: v for k, v in result.items() if isinstance(v, (int, float, bool))}
    unevaluable = []
    for r in rows:
        try:
            if eval(r["condition"], {"__builtins__": {}}, dict(safe)):  # noqa: S307
                return r["action"], r, unevaluable
        except Exception as e:
            unevaluable.append({"condition": r["condition"],
                                "error": f"{type(e).__name__}: {e}"})
            continue
    return "CONTINUE", None, unevaluable


def _run_round(env: Envelope, workdir: Path, rnd: int, st: dict) -> dict:
    rd = workdir / f"round-{rnd:02d}"
    (rd / "artifacts").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    # A wall-clock kill must not crash the loop: matrix-01 (2026-10-07) hit
    # subprocess.TimeoutExpired AFTER its script had already written a complete
    # artifacts/result.json, and the uncaught exception left state["status"] at
    # RUNNING forever -- an unsupervised run that can never conclude is worse
    # than a failed one, because status lies. Timeouts are now a recorded
    # round state (timed_out=True, exit_code=-1), not an exception.
    timed_out = False
    returncode = -1
    out, err = "", ""
    try:
        proc = subprocess.run(env.methods, shell=True, cwd=rd, capture_output=True,
                              text=True, timeout=int(env.max_wall_hours * 3600))
        out, err, returncode = proc.stdout or "", proc.stderr or "", proc.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        err = (err + f"\n[loop] wall-clock limit "
                      f"{env.max_wall_hours}h reached; process killed").strip()
    elapsed = time.monotonic() - t0
    (rd / "stdout.txt").write_text(out, encoding="utf-8")
    (rd / "stderr.txt").write_text(err, encoding="utf-8")
    result_path = rd / "artifacts" / "result.json"
    result = {}
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as e:
            result = {"_parse_error": str(e)}
    result.setdefault("exit_code", returncode)
    result.setdefault("wall_s", round(elapsed, 1))
    if timed_out:
        result["timed_out"] = True
    # Cost accrual: the methods command reports spend via result.json
    # "cost_usd" (LLM API meter) or a cost_usd.txt sidecar. Without either,
    # spend is unknown and the budget gate cannot protect: record that.
    cost = result.get("cost_usd")
    if cost is None:
        sidecar = rd / "artifacts" / "cost_usd.txt"
        if sidecar.exists():
            try:
                cost = float(sidecar.read_text(encoding="utf-8").strip())
            except Exception:
                cost = None
    result["cost_usd_known"] = cost is not None
    result["round_cost_usd"] = float(cost or 0.0)
    missing = [a for a in env.required_artifacts if not (rd / "artifacts" / a).exists()]
    return {"round": rnd, "dir": str(rd), "result": result, "missing": missing,
            "exit_code": returncode, "timed_out": timed_out}


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
    lock_fd = _acquire_lock(workdir)
    if lock_fd is None:
        return 1
    try:
        return _cmd_run_locked(args, workdir, lock_fd)
    finally:
        _release_lock(lock_fd, workdir)


def _cmd_run_locked(args, workdir: Path, lock_fd) -> int:
    env = Envelope.load(args.envelope)
    problems = env.validate()
    if problems:
        print("refusing to start: envelope not executable:")
        for p in problems:
            print(f"  - {p}")
        return 1
    st = _load_state(workdir)
    if st["status"] not in ("READY", "RUNNING"):
        print(f"run already {st['status']}; refusing to resume a finished run")
        return 1
    # Trust root (2026-10-09): rounds are signed by the pinned root key kept OUTSIDE
    # the run directory, and no private key is ever written into state.json again.
    # Before this, cmd_verify read the trust key from the same state.json that stored
    # the private key, so writing inside the run dir was enough to re-sign a doctored
    # bundle and have it print valid (demonstrated on a copy of coderepair-01).
    pub = KS.root_pub(KS.default_root_dir())
    if pub is None:
        print(f"refusing to start: no pinned root key at "
              f"{KS.default_root_dir() / KS.ROOT_PUB} -- run "
              f"`python -m ai_researcher.keystore init` first")
        return 1
    st["key_pub"] = pub.hex()
    st["key_priv"] = None          # never again: the run dir holds no signing power
    st["key_era"] = "root"
    st["loop_schema"] = LOOP_SCHEMA
    st["status"] = "RUNNING"
    _save_state(workdir, st)
    start_wall = time.monotonic()

    while len(st["rounds"]) < env.max_rounds:
        rnd = len(st["rounds"]) + 1
        # 1. budget. cost_usd accrues from each round's reported spend; rounds
        # that do not report spend leave cost_usd_known False and do NOT move
        # the meter -- unknown spend must never read as zero spend.
        if st["cost_usd"] > env.max_cost_usd and env.max_cost_usd > 0:
            st["status"] = "STOP-BUDGET"; break
        if (time.monotonic() - start_wall) / 3600 > env.max_wall_hours:
            st["status"] = "STOP-TIME"; break
        # 2-4. run, collect, sign
        rr = _run_round(env, workdir, rnd, st)

        # 1b. config binding. Signing proves the artifacts were not modified; it
        # says nothing about whether they are the artifacts the envelope declared.
        # breadth-02 (2026-10-08) ran the original 8 trivial diffs instead of the
        # declared 24 because the methods string never set the flag that selects
        # them, produced a signed bundle, and fired a kill-switch on the result.
        # An envelope may now declare `expect`, and the harness must record its
        # effective configuration in result.json under `_config`; a mismatch stops
        # the run instead of certifying the wrong experiment.
        exp = getattr(env, "expect", None)
        if exp:
            rp = workdir / f"round-{rnd:02d}" / "artifacts" / "result.json"
            try:
                got = (json.loads(rp.read_text(encoding="utf-8"))
                       .get("_config") or {})
            except Exception as e:
                st["status"] = "STOP-CONFIG-UNBOUND"
                st["notes"] = (f"envelope declares expect={sorted(exp)} but "
                               f"result.json carries no readable _config ({e})")
                _save_state(workdir, st)
                break
            bad = {k: (exp[k], got.get(k)) for k in exp if got.get(k) != exp[k]}
            if bad:
                st["status"] = "STOP-CONFIG-MISMATCH"
                st["notes"] = ("harness ran a different experiment than the "
                               "envelope declared (key: declared, actual): "
                               + "; ".join(f"{k}={v}" for k, v in bad.items()))
                _save_state(workdir, st)
                print(f"config mismatch: {st['notes']}")
                break
        # 1c. An artifact that disclaims its own measurement cannot produce a
        # verdict. breadth-02 (2026-10-08, second attempt) ran the declared 24
        # diffs and set measurable=False because 34.7% of judgments were
        # unparseable -- then a kill-switch row fired on the unusable comparison
        # and the run was filed STOP-EXTEND. A harness saying "this cannot support
        # the claim" must stop the loop, unless a kill row explicitly addresses
        # the measurability flag.
        _probe = {}
        _rp0 = workdir / f"round-{rnd:02d}" / "artifacts" / "result.json"
        if _rp0.exists():
            try:
                _probe = json.loads(_rp0.read_text(encoding="utf-8"))
            except Exception:
                _probe = {}
        if _probe.get("measurable") is False:
            rows_txt = " ".join(
                f"{r.condition} {r.action} {r.note}".lower()
                for r in env.kill_switch)
            if "measurable" not in rows_txt and "abstention" not in rows_txt:
                st["status"] = "STOP-UNMEASURABLE"
                st["notes"] = (
                    f"artifact declares measurable=False "
                    f"(abstention_rate={_probe.get('abstention_rate')}); no "
                    f"kill-switch row addresses measurability, so no decision may "
                    f"be taken from it")
                _save_state(workdir, st)
                print(f"unmeasurable artifact: {st['notes']}")
                break
        if rr["missing"]:
            st["rounds"].append({**rr, "verdict": "ROUND-INVALID",
                                 "reason": f"missing artifacts: {rr['missing']}"})
            _save_state(workdir, st)
            st["status"] = "STOP-INVALID"
            break
        envl = KS.sign_with_root(workdir / f"round-{rnd:02d}" / "artifacts",
                                 signer="ai-researcher-loop", round_id=f"r{rnd:02d}")
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
        # Record the bundle outside the run tree. A bundle that is signed but absent
        # from the registry does not verify (tests/test_trust_root.py T5).
        KS.register(envl, run_name=workdir.name)
        # 5. kill-switch (notes pass through: a verdict without its reason
        # is unactionable, and the earlier dict comprehension dropped them)
        action, row, uneval = _eval_kill(
            [{"condition": r.condition, "action": r.action, "note": r.note}
             for r in env.kill_switch],
            rr["result"])
        # fail-closed: a preregistered rule that cannot be evaluated cannot be
        # reported as "nothing fired". Either a row decides, or the run stops
        # as STOP-KILL-UNEVALUABLE and names the rows that never ran.
        if uneval and action == "CONTINUE":
            action = "STOP-KILL-UNEVALUABLE"
            row = {"condition": "; ".join(u["condition"] for u in uneval),
                   "action": "STOP-KILL-UNEVALUABLE",
                   "note": ("kill-switch rows unevaluable against this artifact: "
                            + "; ".join(f"{u['condition']} ({u['error']})"
                                        for u in uneval)
                            + " -- preregistered decision rule did not run")}
        rec = {**rr, "bundle": envl["bundle"]["bundle_id"],
               "kill_row": (row["condition"] if row else None)}
        # A completed-but-killed round is still signed evidence; if no
        # kill-switch row claimed it, the wall clock is the reason and the run
        # must terminate as STOP-TIME rather than pretend it may continue.
        if rr.get("timed_out") and action == "CONTINUE":
            action = "STOP-TIME"
            row = {"condition": f"wall_s >= {int(env.max_wall_hours * 3600)}",
                   "note": "wall-clock limit reached; artifacts preserved and signed",
                   "action": "STOP-TIME"}
        # cost accrues here, once per counted round, from the round's own report
        st["cost_usd"] = round(st.get("cost_usd", 0.0)
                               + float(rr["result"].get("round_cost_usd", 0.0)), 6)
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
        # 5c. two-seat review, BEFORE the verdict is written. Placement matters and was
        # a bug: this stage used to sit after the terminal branch's `break`, so a run that
        # refuted on its first round (seed6-01, 2026-10-09 -- the very run that found it)
        # reached a final verdict with review=None. A refutation is exactly the result that
        # needs an independent read on it, so the review runs regardless of the action and
        # the last round is always reviewed (should_review), whatever the cadence says.
        if should_review(rnd, env.max_rounds):
            try:
                rev = two_seat_review(
                    claim=env.hypothesis,
                    evidence=json.dumps(rr["result"], ensure_ascii=False)[:4000])
                rec["review"] = {"joint": rev["joint"],
                                 "contradiction": rev["contradiction"],
                                 "methodology": rev["methodology"].get("verdict"),
                                 "devil": rev["devil"].get("verdict"),
                                 "devil_objection": rev["devil"].get("strongest_objection", "")[:500],
                                 # which instrument produced this score. A review without a
                                 # model id is unreadable later: same-family and different-
                                 # family reviews look identical otherwise, and the whole
                                 # point of the two seats is cross-family independence.
                                 "reviewer": rev.get("reviewer")}
            except Exception as e:
                rec["review"] = {"error": f"{type(e).__name__}: {e}"}
        if action != "CONTINUE":
            rec["verdict"] = action
            rec["reason"] = (row.get("note") if row else "")
            st["rounds"].append(rec)
            _save_state(workdir, st)
            st["status"] = action
            break
        # 6. (review already ran at 5c, before the verdict -- see the placement note)
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
    """Re-verify every bundle in a run against the PINNED trust root, never against a
    key stored inside the run directory (that was the laundering path until 2026-10-09).

    A round may verify under the root key (registered, authoritative) or under a key
    pinned in keys/legacy_pubkeys.jsonl (pre-trust-root history). Legacy verdicts are
    labelled as non-authoritative in the reason string: their signing key sat in the
    run's own state.json, so they prove the files were not edited after signing and
    nothing more.
    """
    workdir = Path(args.workdir)
    res = KS.verify_run(workdir)
    ok = bad = legacy = 0
    for r in res["rounds"]:
        print(f"  {r['round']} {r['valid']} {r['reason']}")
        ok += r["valid"]
        bad += not r["valid"]
        legacy += bool(r["valid"] and "legacy era" in r["reason"])
    print(f"{ok} valid, {bad} invalid"
          + (f"  ({legacy} of them legacy-era, non-authoritative)" if legacy else ""))
    if not res["rounds"]:
        print(f"nothing signed under {workdir}: no state.json rounds and no round-*/envelope.json")
    return 0 if bad == 0 else 1


def cmd_publish(args):
    """Publication gate: a run is submittable to a tier only if BOTH halves pass.

    Mechanical half runs locally (no model). Judgment half scores both seats
    against the tier rubric. Either half failing -> NOT-SUBMITTABLE, with the
    failing checks named. There is no override flag: fix the paper, not the gate.
    """
    from .quality import gate_report, JUDGMENT, TIERS
    from .two_seat import review_rubric
    if args.tier not in TIERS:
        print(f"unknown tier {args.tier!r}; choose from {', '.join(TIERS)}")
        return 1
    workdir = Path(args.workdir)
    st = _load_state(workdir)
    if not st.get("rounds"):
        print(f"no rounds in {workdir}: nothing to judge yet (run first)")
        return 1
    paper = Path(args.paper)
    # Which artifact is under review?  Until 2026-10-07 this read
    # <paper>/DRAFT_SEED.md and nothing else.  Every "zone1 17/17 PASS" printed
    # before then was measured against a per-run draft seed, never against the
    # manuscript -- the gate was validating a scaffold and reporting it as a
    # paper verdict.  Resolution order is now explicit and printed:
    #   --manuscript file  >  <paper>/SYNTHESIS.md  >  <paper>/DRAFT_SEED.md
    # and an absent source is refused rather than silently gated on "".
    src = None
    if getattr(args, "manuscript", None):
        src = Path(args.manuscript)
        if not src.exists():
            print(f"refusing to publish: --manuscript not found: {src}")
            return 1
    elif (paper / "SYNTHESIS.md").exists():
        src = paper / "SYNTHESIS.md"
    elif (paper / "DRAFT_SEED.md").exists():
        src = paper / "DRAFT_SEED.md"
    if src is None:
        print(f"refusing to publish: no manuscript in {paper} "
              f"(need SYNTHESIS.md or DRAFT_SEED.md, or pass --manuscript). "
              f"Gating on an empty string would report FAILs that describe the "
              f"missing file, not the paper.")
        return 1
    draft = src.read_text(encoding="utf-8")
    if not draft.strip():
        print(f"refusing to publish: {src} is empty")
        return 1
    print(f"reviewing artifact: {src} ({len(draft)} chars)")
    ledger_path = paper / "CLAIM_LEDGER.md"
    rows = _parse_ledger(ledger_path) if ledger_path.exists() else []
    if not rows:
        print(f"note: no CLAIM_LEDGER.md in {paper}; evidence-linked claim "
              f"checks will be reported as unverifiable rather than passed")
    dims = JUDGMENT[args.tier]
    try:
        scores = review_rubric(
            draft, json.dumps(st["rounds"][-1].get("result", {}))[:3000],
            args.tier, dims)
        seat_scores = {"methodology": scores["methodology"],
                       "devil": scores["devil"]}
    except Exception as e:
        print(f"judgment half unavailable ({type(e).__name__}: {e}); "
              f"mechanical half still runs")
        seat_scores = {}
    # A verdict that does not name the artifact it judged is not auditable:
    # the 2026-10-07 scorecard claimed "mechanical 17/17 PASS" with no record of
    # which text was read, which is how a scaffold got reported as a paper.
    rep = gate_report(args.tier, rows, draft, seat_scores,
                      {"workdir": str(workdir),
                       "manuscript": str(src),
                       "manuscript_chars": len(draft),
                       "ledger": str(ledger_path) if ledger_path.exists() else None,
                       "ledger_rows": len(rows),
                       "runs_in_ledger": sorted({r.get("run", "?") for r in rows})})
    print(f"tier={rep['tier']} verdict={rep['verdict']} bar={rep['bar']}")
    for m in rep["mechanical"]:
        print(f"  [{'PASS' if m['pass'] else 'FAIL'}] {m['id']}: {m['reason']}")
    print(f"  judgment means: {rep['judgment_means']} (need >= {rep['bar']} both seats)")
    (workdir / f"publish-{args.tier}.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if rep["verdict"] == "PASS" else 1


def _parse_ledger(path: Path) -> list:
    """Parse a CLAIM_LEDGER.md table into {id, value, status, evidence, how}.

    Header-driven with English and Chinese aliases. The historical hardcoded
    `| C-` prefix silently returned zero rows for any ledger whose first column
    was not a C-numbered id -- and a ledger that parses to nothing makes every
    evidence-linked gate check unverifiable while still reporting PASS (fifth
    instance of the shape that has bitten this project: a missing value reading
    as a neutral one). bridge writes Chinese headers, so English-only matching
    would have reproduced the same silence.

        id | claim | evidence | value | how | status | run
        ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 | 源运行

    Columns are located by name, so ledgers may carry extra columns (e.g. `run`)
    in any order. With no recognizable header the positional layout is used.
    """
    alias = {
        "id": ("id", "编号"),
        "run": ("run", "源运行", "运行"),
        "claim": ("claim", "声明", "声明（章节）", "声明(章节)"),
        "evidence": ("evidence", "证据", "证据文件", "证据文件+字段"),
        "value": ("value", "数值"),
        "how": ("how", "如何验证", "验证"),
        "status": ("status", "状态"),
    }

    def norm(c: str) -> str:
        return "".join(ch for ch in c.lower() if ch.isalnum())

    def match(low: list) -> dict:
        found = {}
        for field, names in alias.items():
            for i, cell in enumerate(low):
                n = norm(cell)
                if n and any(n == norm(a) or norm(a) in n for a in names):
                    found.setdefault(field, i)
                    break
        return found

    header, rows = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        parts = [c.strip() for c in s.strip("|").split("|")]
        if parts and all(set(c) <= set("-: ") for c in parts if c):
            continue  # separator row
        m = match([c.lower() for c in parts])
        if "id" in m and ("claim" in m or "value" in m):
            header = m
            continue
        if not header:
            if len(parts) < 6:
                continue
            header = {"id": 0, "claim": 1, "evidence": 2,
                      "value": 3, "how": 4, "status": 5}
        if len(parts) < 6:
            continue

        def cell(name, fallback=""):
            i = header.get(name, fallback)
            return parts[i] if isinstance(i, int) and 0 <= i < len(parts) else ""

        cid = cell("id")
        if not cid or norm(cid) in ("id", "编号"):
            continue
        val = cell("value")
        note = None
        try:
            val = float(val.split()[0].rstrip(":："))
        except Exception:
            # A value that does not parse must become None WITH ITS RAW TEXT
            # kept (value_note), not stay a str. Downstream filters use
            # isinstance(row["value"], (int, float)); a surviving str leaves
            # every such filter silently, and the CI-coverage denominator
            # shrinks as the ledger gets worse -- the 2026-10-02
            # "missing value reads as neutral" shape, one layer up.
            if val.strip():
                note = val
            val = None
        row = {"id": cid, "claim": cell("claim"), "evidence": cell("evidence"),
               "value": val, "how": cell("how"), "status": cell("status")}
        if note:
            row["value_note"] = note
        if cell("run"):
            row["run"] = cell("run")
        rows.append(row)
    return rows


def cmd_amend(args):
    """Append a correction note to a round WITHOUT touching signed artifacts.

    Directly editing artifacts/result.json breaks the bundle signature (learned
    the hard way: a threshold recomputation edited the signed file and voided
    the chain). Amend instead writes a separate amendment.json alongside,
    recording what was corrected, why, and whether the correction was knowable
    without seeing the data. Bridge reads amendments and surfaces them.
    """
    import shutil
    workdir = Path(args.workdir)
    st = _load_state(workdir)
    rnd = int(args.round)
    rd = workdir / f"round-{rnd:02d}"
    if not rd.exists():
        print(f"no such round: {rd}")
        return 1
    note = {"amended_at": _now(), "correction": args.note,
            "knowable_without_data": args.apriori}
    (rd / "amendment.json").write_text(
        json.dumps(note, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"amendment recorded on round-{rnd:02d} (artifacts untouched, bundle intact)")
    return 0


def cmd_finalize(args):
    """Complete bookkeeping for a round whose artifacts already exist on disk.

    matrix-01 (2026-10-07) wrote a complete artifacts/result.json and was then
    killed by the wall clock before the loop could sign it, evaluate the
    kill-switch, or set a terminal status. The data was real; only the
    bookkeeping was missing. Re-running `run` would refuse (artifacts present,
    budget and time already spent) and hand-editing state.json would forge the
    audit trail. This command signs the untouched artifacts, evaluates the
    envelope's kill-switch against them, and appends the round to state.

    It never touches artifact bytes and never invents a verdict: no envelope
    kill-switch row firing means CONTINUE -> STOP-ROUNDS-EXHAUSTED, and a
    missing or unparseable result.json is refused.
    """
    workdir = Path(args.workdir)
    env = Envelope.load(args.envelope)
    problems = env.validate()
    if problems:
        print("refusing to finalize: envelope not executable:")
        for p in problems:
            print(f"  - {p}")
        return 1
    if _load_state(workdir)["status"] not in ("READY", "RUNNING"):
        print("run already concluded; nothing to finalize")
        return 1
    lock_fd = _acquire_lock(workdir)
    if lock_fd is None:
        return 1
    try:
        st = _load_state(workdir)
        pub = KS.root_pub(KS.default_root_dir())
        if pub is None:
            print("refusing to finalize: no pinned root key at "
                  f"{KS.default_root_dir() / KS.ROOT_PUB} -- run "
                  "`python -m ai_researcher.keystore init` first")
            return 1
        st["key_pub"] = pub.hex()
        st["key_priv"] = None
        rnd = len(st["rounds"]) + 1
        rd = workdir / f"round-{rnd:02d}"
        result_path = rd / "artifacts" / "result.json"
        if not result_path.exists():
            print(f"refusing to finalize: no artifacts at {result_path}")
            return 1
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"refusing to finalize: result.json unparseable ({e})")
            return 1
        missing = [a for a in env.required_artifacts
                   if not (rd / "artifacts" / a).exists()]
        if missing:
            print(f"refusing to finalize: missing artifacts {missing}")
            return 1
        result.setdefault("finalized_from_disk", True)
        envl = KS.sign_with_root(rd / "artifacts", round_id=f"r{rnd:02d}")
        chk = EV.verify_round(rd / "artifacts", envl["bundle"], envl["envelope"], pub)
        if not chk["valid"]:
            print(f"refusing to finalize: verification failed ({chk['reason']})")
            return 1
        (rd / "envelope.json").write_text(json.dumps(envl, indent=2) + "\n",
                                          encoding="utf-8")
        KS.register(envl, run_name=workdir.name)
        action, row, uneval = _eval_kill(
            [{"condition": r.condition, "action": r.action, "note": r.note}
             for r in env.kill_switch], result)
        if uneval and action == "CONTINUE":
            action = "STOP-KILL-UNEVALUABLE"
            row = {"condition": "; ".join(u["condition"] for u in uneval),
                   "action": "STOP-KILL-UNEVALUABLE",
                   "note": ("kill-switch rows unevaluable against this artifact: "
                            + "; ".join(f"{u['condition']} ({u['error']})"
                                        for u in uneval)
                            + " -- preregistered decision rule did not run")}
        if action == "CONTINUE":
            action = "STOP-ROUNDS-EXHAUSTED"
        rec = {"round": rnd, "dir": str(rd), "result": result, "missing": [],
               "exit_code": result.get("exit_code", -1), "timed_out": False,
               "finalized": True,
               "bundle": envl["bundle"]["bundle_id"],
               "kill_row": (row["condition"] if row else None),
               "verdict": action,
               "reason": (row.get("note") if row else
                          "artifacts signed after wall-clock kill; no kill row fired")}
        st["cost_usd"] = round(st.get("cost_usd", 0.0)
                               + float(result.get("round_cost_usd", 0.0)), 6)
        st["rounds"].append(rec)
        st["status"] = action
        _save_state(workdir, st)
        print(f"finalized round-{rnd:02d}: {action} "
              f"bundle={envl['bundle']['bundle_id'][:18]}")
        return 0
    finally:
        _release_lock(lock_fd, workdir)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.loop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("approve"); a.add_argument("envelope"); a.add_argument("--by", required=True)
    r = sub.add_parser("run"); r.add_argument("envelope"); r.add_argument("--workdir", required=True)
    s = sub.add_parser("status"); s.add_argument("workdir")
    v = sub.add_parser("verify"); v.add_argument("workdir")
    p = sub.add_parser("publish"); p.add_argument("workdir"); p.add_argument("--tier", required=True)
    p.add_argument("--paper", required=True); p.add_argument("--manuscript", default=None)
    fi = sub.add_parser("finalize")
    fi.add_argument("envelope"); fi.add_argument("--workdir", required=True)
    am = sub.add_parser("amend"); am.add_argument("workdir"); am.add_argument("--round", required=True); am.add_argument("--note", required=True); am.add_argument("--apriori", default="no")
    a = ap.parse_args(argv)
    return {"approve": cmd_approve, "run": cmd_run,
            "status": cmd_status, "verify": cmd_verify,
            "publish": cmd_publish, "amend": cmd_amend,
            "finalize": cmd_finalize}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
