"""Evidence-integrity and gate sweep, exit non-zero on any failure.

Every bundle in this project had been verified by hand, on demand, by one person
who remembered to. That is not a control: it is a habit, and habits do not survive
a deadline. Two bundles were found invalid during a manual sweep -- one
hand-edited, one with an unsigned file written into the signed directory -- and
neither was noticed at the time it happened.

This script is the control. It runs on every push:

  1. every round bundle verifies (Ed25519 signature + SHA-256 manifest)
  2. no signed artifacts directory contains files outside its manifest
  3. the consolidated claim ledger parses to a non-zero number of claims
  4. every envelope on disk still validates (no regression in the contract)
  5. the mechanical half of the venue gate runs against the real manuscript
  6. the proposal loop still runs

The judgment half of the gate needs a review API key and is therefore NOT run
here: a CI job that silently degrades to "mechanical only" while reporting green
is the same failure mode this project keeps paying for. When no key is present
the script says so in its output and reports the judgment half as SKIPPED, which
is visible rather than assumed.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]  # scripts/ -> repo root
sys.path.insert(0, str(ROOT / "src"))

from ai_researcher.evidence import verify_round  # noqa: E402
from ai_researcher import keystore as KS  # noqa: E402
from ai_researcher.envelope import Envelope  # noqa: E402
from ai_researcher.loop import _parse_ledger  # noqa: E402
from ai_researcher.quality import mechanical_check  # noqa: E402

FAILS: list[str] = []
NOTES: list[str] = []


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# Runs superseded by a clean re-run: the original stays on disk with its amendment,
# but its failures are expected-and-documented rather than actionable. Without this,
# two FAILs on confirmation-8fam would stay lit forever -- not because anything is
# newly wrong, but because a superseded round will never be re-signed. A permanent
# red that cannot clear trains people to ignore red.
SUPERSEDED_RUNS = {
    "confirmation-8fam": "superseded by confirmation-8fam-r2 (identical design, "
                          "signed bundle, same boundary family)",
}


def check_bundles(runs_dir: pathlib.Path) -> None:
    section("evidence bundles")
    # Trust comes from keys/ pinned OUTSIDE every run directory (2026-10-09). Before
    # this, this sweep took the pubkey from the run's own state.json -- the same file
    # that stored the private key -- so tampering an artifact and re-signing it in place
    # printed "valid" here too. The denominator is now the round list in state.json,
    # which also closes the old gap where deleting envelope.json made a round simply
    # not appear (an absent signature is a failure, not a skip).
    ok = bad = legacy = missing = 0
    invalid = []
    for st_file in sorted(runs_dir.glob("*/state.json")):
        run = st_file.parent
        state = json.loads(st_file.read_text(encoding="utf-8"))
        declared = len(state.get("rounds", []))
        if declared == 0:
            continue
        if KS.root_pub(KS.default_root_dir()) is None:
            FAILS.append(f"{run.name}: no pinned trust root at "
                         f"{KS.default_root_dir() / KS.ROOT_PUB} -- this is NOT_VERIFIABLE, "
                         f"not a pass")
            continue
        res = KS.verify_run(run)
        seen = len(res["rounds"])
        if seen < declared:
            missing += declared - seen
            invalid.append((run.name, None,
                            f"state.json declares {declared} round(s) but only {seen} carry "
                            f"an envelope.json -- a deleted signature is not a verified round"))
        for r in res["rounds"]:
            if r["valid"]:
                ok += 1
                if "legacy era" in r["reason"]:
                    legacy += 1
            else:
                bad += 1
                invalid.append((run.name, r["round"], r["reason"]))
    print(f"  {ok} valid, {bad} invalid, {missing} signature-file missing")
    if legacy:
        NOTES.append(f"{legacy}/{ok} valid bundles are legacy-era (pre-trust-root keys "
                     f"pinned in {KS.LEGACY}). They prove the files were not edited after "
                     f"signing; they do NOT prove a human approved the run -- green here is "
                     f"not authorship")
    for name, rdir, reason in invalid:
        line = f"{name}: {reason}"
        if name in SUPERSEDED_RUNS:
            NOTES.append(f"{line} -- SUPERSEDED: {SUPERSEDED_RUNS[name]}")
            continue
        # An amendment excuses exactly one thing: the artifacts directory changed after
        # signing (swarm-fd -- a human edited a signed result.json, the chain broke, and
        # the ledger says so). It was unconditional before 2026-10-09, which a fixture
        # proved: with ANY amendment file present, a deleted envelope and a
        # tamper-then-re-sign both printed "no failures" and exited 0. A signature
        # failure, a missing signature file, or a run-dir key rewrite is never
        # "documented state" -- those FAIL. The lookup follows the round that actually
        # failed (it used to be hardcoded round-01, so a round-02 break found the wrong
        # round's paperwork). Known limit, not yet closed: this checks that the round
        # carries an amendment, not that the amendment text describes this edit.
        amd = (runs_dir / name / (rdir or "round-??") / "amendment.json")
        if rdir is not None and amd.exists() and "hash mismatch" in reason:
            NOTES.append(f"{line} -- documented by amendment, expected")
        else:
            FAILS.append(line)
    if bad or missing:
        print("  invalid/missing bundles listed above; those without an amendment FAIL")


REVIEW_FIX_DATE = "2026-10-09"  # superseded: the criterion below is loop_schema, not a date
SCHEMA_REQUIRES_REVIEW = 2      # loop.LOOP_SCHEMA from which a review record is mandatory


def check_signing_power(runs_dir: pathlib.Path) -> None:
    """Invariant: no run directory holds signing power.

    loop.py nulls `key_priv` before it ever saves state, but that is a *writer*
    guarantee -- it says nothing about files that arrive by another route (an
    older checkout, a hand-built state.json, a resumed copy). The trust root only
    means something if the audited object cannot also be the signer, so the
    invariant is checked on the bytes, not asserted from the code path.
    """
    section("no run dir holds a signing key")
    pinned = set()
    pinf = ROOT / "demo" / "legacy_unreviewed.txt"
    rk = ROOT / "demo" / "evidence" / "line_registry.jsonl"
    if rk.exists():
        for line in rk.read_text(encoding="utf-8").splitlines():
            try:
                pinned.add(str(json.loads(line).get("key_pub") or ""))
            except Exception:
                continue
    legacy = ROOT / "src" / "ai_researcher" / "legacy_pubkeys.jsonl"
    if legacy.exists():
        for line in legacy.read_text(encoding="utf-8").splitlines():
            try:
                pinned.add(str(json.loads(line).get("key_pub") or ""))
            except Exception:
                continue
    offenders = 0
    for st_file in sorted(runs_dir.glob("*/state.json")):
        try:
            st = json.loads(st_file.read_text(encoding="utf-8"))
        except Exception as e:                       # unreadable state is not "clean"
            FAILS.append(f"{st_file.parent.name}: state.json unparseable ({e}) -- "
                         "signing-power check cannot run")
            continue
        priv = st.get("key_priv")
        if priv in (None, "", 0):
            continue
        offenders += 1
        pub = str(st.get("key_pub") or "")
        where = "在注册表/固定表里" if pub in pinned else "不在任何固定表里（任何人都能拿它对任意产物重新签名后再覆盖 key_pub）"
        FAILS.append(
            f"{st_file.parent.name}: state.json 里带着可用私钥 key_priv={str(priv)[:12]}… "
            f"（{where}；status={st.get('status')} loop_schema={st.get('loop_schema')}）"
            " -- 被审对象自己持有签名权力，信任根等于没有")
    if not offenders:
        print(f"  ok: {len(list(runs_dir.glob('*/state.json')))} 份 state.json 无一持有私钥")
    else:
        print(f"  {offenders} 份 state.json 持有私钥")


def check_review_coverage(runs_dir: pathlib.Path) -> None:
    section("judgment stage reachability")
    # Two fixes live here and the second one is about this check itself.
    # (a) The cadence trigger (rnd % 2 == 0) could never fire for envelopes with
    #     max_rounds=1 -- 0 of 27 historical rounds carried a review.
    # (b) The review stage then sat AFTER the terminal branch's break, so seed6-01 --
    #     the first run of the repaired loop, STOP-REFUTED at n=6 -- reached a final
    #     verdict with review=None, and this check did not flag it, because it compared
    #     started_at against "2026-10-09" while the stamp is UTC (18:23Z on the 8th) and
    #     the local clock already read the 9th. A date-gate that mis-fires on its own
    #     first case is not a gate. The criterion is now the code marker loop_schema.
    reviewed = errored = exempt = pre_schema = 0
    exempt_names = set()
    exf = ROOT / "demo" / "legacy_unreviewed.txt"
    if exf.exists():
        # the file is "name<TAB>reason"; taking the whole line was my first attempt and it
        # made the exemption silently never match (the gate then FAILED on the run the
        # exemption was written for -- a broken allowlist is loud only because a fixture
        # made it loud)
        exempt_names = {l.split("\t")[0].strip() for l in
                        exf.read_text(encoding="utf-8").splitlines()
                        if l.strip() and not l.startswith("#")}
    for st_file in sorted(runs_dir.glob("*/state.json")):
        state = json.loads(st_file.read_text(encoding="utf-8"))
        rounds = state.get("rounds", [])
        if not rounds:
            continue
        with_review = [r for r in rounds if isinstance(r.get("review"), dict)]
        schema = int(state.get("loop_schema", 1) or 1)
        # key_era == "root" is the other handle on "produced by the repaired code": it was
        # written by cmd_run from the trust-root commit onward, and seed6-01 carries it
        # while predating the loop_schema field. Either marker triggers the requirement.
        post_fix = schema >= SCHEMA_REQUIRES_REVIEW or state.get("key_era") == "root"
        name = st_file.parent.name
        if with_review:
            reviewed += 1
            if any("error" in r["review"] for r in with_review):
                errored += 1
        elif post_fix:
            if name in exempt_names:
                exempt += 1
            else:
                why = (f"loop_schema={schema}" if schema >= SCHEMA_REQUIRES_REVIEW
                       else "key_era=root (post-trust-root, schema field absent)")
                FAILS.append(f"{name}: {why} marks this run as produced by the repaired "
                             f"loop, which requires a review record on the terminal round; "
                             f"none exists -- the judgment stage is unreachable again")
        else:
            pre_schema += 1
    if exempt:
        NOTES.append(f"{exempt} schema>=2 run(s) carry no review but are listed in "
                     f"demo/legacy_unreviewed.txt (created before the 5c placement fix)")
    NOTES.append(f"{reviewed} run(s) carry a review record"
                 + (f", {errored} of which record an error in the reviewer call "
                    f"(an attempted review with no review key is NOT a review)" if errored else "")
                 + f"; {pre_schema} pre-schema-{SCHEMA_REQUIRES_REVIEW} run(s) have none, "
                 f"which is the structural gap that was fixed, not a new defect")


def check_unsigned_extras(runs_dir: pathlib.Path) -> None:
    section("unsigned files inside signed artifact directories")
    found = 0
    for rd in sorted(runs_dir.glob("*/round-*")):
        ep = rd / "envelope.json"
        if not ep.exists():
            continue
        man = json.loads(ep.read_text(encoding="utf-8")).get(
            "bundle", {}).get("manifest", {}).get("files", {})
        ad = rd / "artifacts"
        if not ad.is_dir():
            continue
        for f in sorted(ad.iterdir()):
            if f.is_file() and f.name not in man:
                found += 1
                FAILS.append(f"{rd.parent.name}: unsigned {f.name} inside signed "
                             f"artifacts/ (derived analysis belongs outside)")
    print(f"  {found} found")


def check_ledger(path: pathlib.Path) -> None:
    section("consolidated claim ledger")
    if not path.exists():
        FAILS.append(f"missing consolidated ledger: {path}")
        print("  MISSING")
        return
    rows = _parse_ledger(path)
    runs = {r.get("run") for r in rows if r.get("run")}
    print(f"  {len(rows)} claims from {len(runs)} runs")
    if len(rows) == 0:
        FAILS.append("consolidated ledger parsed to zero claims: the parser and "
                     "the writer disagree, which silently passes evidence checks")


def check_envelopes() -> None:
    section("envelopes still satisfy the contract")
    legacy_p = ROOT / "demo/legacy_envelopes.txt"
    legacy = set()
    if legacy_p.exists():
        legacy = {ln.strip() for ln in legacy_p.read_text(
            encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")}
    n = new_bad = legacy_bad = 0
    for p in sorted(ROOT.glob("demo/**/*.json")):
        # Preregistration envelopes only. Signed round envelopes and the copies
        # bridge writes under demo/papers/*/evidence/ have no hypothesis field --
        # treating those as preregistrations produced 30 phantom failures.
        name = p.name
        if not (name.startswith("envelope") or name.endswith("_env.json")):
            continue
        rel = str(p.relative_to(ROOT))
        if "round-" in rel or "/evidence/" in rel:
            continue
        try:
            env = Envelope.load(p)
        except Exception as e:
            new_bad += 1
            FAILS.append(f"{rel}: unloadable ({type(e).__name__}: {e})")
            continue
        n += 1
        problems = env.validate()
        # seed=0 / unapproved are legitimate drafts.
        hard = [x for x in problems
                if not x.startswith("not approved") and not x.startswith("seed is 0")]
        if hard:
            if rel in legacy:
                legacy_bad += 1
                NOTES.append(f"{rel}: pre-dates the power gate ({hard[0]}); "
                             f"cannot be re-approved, listed in legacy_envelopes.txt")
            else:
                new_bad += 1
                FAILS.append(f"{rel}: {hard[0]}")
    print(f"  {n} preregistration envelopes checked; {new_bad} new violations, "
          f"{legacy_bad} legacy (noted, not failed)")
    if legacy_bad:
        print(f"  {legacy_bad} envelope(s) can no longer pass `loop approve`. "
              f"Raise n or promise a larger effect before reusing them.")


def check_mechanical_gate(tier: str = "zone1") -> None:
    section(f"{tier} mechanical gate (real manuscript)")
    from ai_researcher.quality import BAR
    draft_p = ROOT / "demo/papers/SYNTHESIS.md"
    ledger_p = ROOT / "demo/papers/CLAIM_LEDGER.md"
    if not draft_p.exists():
        FAILS.append(f"missing manuscript: {draft_p}")
        print("  MISSING")
        return
    draft = draft_p.read_text(encoding="utf-8")
    rows = _parse_ledger(ledger_p) if ledger_p.exists() else []
    mech = mechanical_check(rows, draft, {"workdir": "ci",
                                           "manuscript": str(draft_p)}, tier)
    npass = sum(1 for _, p, _ in mech if p)
    for cid, ok, reason in mech:
        if not ok:
            print(f"  [FAIL] {cid}: {reason}")
    print(f"  {npass}/{len(mech)} mechanical checks pass")
    # A failing mechanical check is a real finding about the manuscript and is
    # reported, but it is not a CI failure: the manuscript is expected to be
    # mid-revision and Z15 correctly fails while references are quarantined.
    # CI's job here is that the gate RAN and said so.
    NOTES.append(f"mechanical gate {npass}/{len(mech)}; failures are reported above")


def check_judgment_available() -> None:
    section("judgment half availability")
    have = any(os.environ.get(k) for k in
               ("SILICONFLOW_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"))
    if have:
        print("  review key present: judgment half could run locally")
        NOTES.append("review key present in CI environment")
    else:
        print("  SKIPPED: no review API key in this environment.")
        print("  The judgment half was NOT run. A green mechanical result here")
        print("  does not mean the paper passed review.")
        NOTES.append("judgment half SKIPPED in CI (no review key) -- do not read "
                     "green as a venue verdict")


def check_binding_coverage() -> None:
    """A harness that records _config must have its envelope declare `expect`.

    The binding is what stopped breadth-02 from certifying the wrong experiment,
    and `loop approve` silently deleted both `expect` and `power.endpoint` for a
    while because to_dict did not carry them -- so the binding vanished while
    everything still looked approved. An unbound harness that records its config
    is reported here rather than discovered when it matters.
    """
    section("config-binding coverage")
    recording, bound, unbound = [], [], []
    for art in sorted((ROOT / "demo/runs").glob("*/round-01/artifacts/result.json")):
        try:
            cfg = json.loads(art.read_text(encoding="utf-8")).get("_config")
        except Exception:
            continue
        if cfg:
            recording.append(art.parts[-4])
    envs = sorted(ROOT.glob("demo/**/*.json"))
    for e in envs:
        name = e.name
        if not (name.startswith("envelope") or name.endswith("_env.json")):
            continue
        rel = str(e.relative_to(ROOT))
        if "round-" in rel or "/evidence/" in rel:
            continue
        try:
            d = json.loads(e.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d.get("expect"), dict) and d["expect"]:
            bound.append(rel)
    # An envelope that declares a config binding must still declare it after a
    # save/load round trip. This is tested as a property of the serializer rather
    # than by trusting the file: `loop approve` rewrites envelopes through
    # to_dict, and to_dict once omitted `expect` and `power.endpoint`, so a
    # binding could vanish while the file still read "approved". An earlier version
    # of this check tried to flag it with a marker field on the envelope -- which
    # then failed the same round trip it was meant to police.
    import tempfile
    for e in envs:
        try:
            env = Envelope.load(str(e))
        except Exception:
            continue
        if not getattr(env, "expect", None):
            continue
        with tempfile.TemporaryDirectory() as td:
            rt = pathlib.Path(td) / "rt.json"
            env.save(rt)
            back = Envelope.load(str(rt))
            if getattr(back, "expect", None) != env.expect:
                FAILS.append(f"{e.relative_to(ROOT)}: expect does not survive a "
                             f"save/load round trip; the binding is inert after "
                             f"`loop approve`")
        if not (getattr(env.power, "endpoint", "") or "").strip():
            NOTES.append(f"{e.relative_to(ROOT)}: power.endpoint is empty, so the "
                         f"power gate will treat it as a paired-proportion "
                         f"endpoint")
    # A harness that records _config must be bound by SOME envelope. Matching by
    # run directory name alone reported a false "unbound" for breadth-02, whose
    # envelope lives at demo/breadth/ and whose run is demo/runs/breadth-02 -- so
    # the note was noise that would have taught a reader to ignore the check.
    unbound = []
    for r in recording:
        if not any(r in b or r.replace("-02", "") in b or r.split("-")[0] in b
                   for b in bound):
            unbound.append(r)
    print(f"  harnesses recording _config: {len(recording)} ({', '.join(recording) or 'none'})")
    print(f"  envelopes declaring expect: {len(bound)}")
    for r in unbound:
        NOTES.append(f"{r} records _config but its envelope declares no expect, "
                     f"so nothing binds the run to the declared design")
    if not recording:
        NOTES.append("no harness records _config yet: config binding is inert")


def check_figures() -> None:
    """Figure captions must quote numbers that still match their data.

    A caption is prose, so it goes stale silently when a bundle is amended or the
    multiplicity audit is re-run, and a figure whose caption disagrees with its own
    data is worse than no figure because it is checked by eye and believed.
    """
    section("figure / caption consistency")
    script = ROOT / "demo/papers/figures/check_consistency.py"
    if not script.exists():
        NOTES.append("no figure consistency checker present")
        print("  no checker")
        return
    import subprocess
    r = subprocess.run([sys.executable, str(script)], capture_output=True,
                       text=True, cwd=str(ROOT),
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-6:]
    for ln in tail:
        print(f"  {ln}")
    if r.returncode != 0:
        FAILS.append("figure caption disagrees with its data; see "
                     "demo/papers/figures/figure_check.md")


def check_proposals() -> None:
    section("self-evolution proposal loop")
    from ai_researcher.evolve import propose_next
    props = propose_next(ROOT / "demo/runs",
                         ROOT / "demo/papers/CLAIM_LEDGER.md", limit=10)
    print(f"  {len(props)} proposals derived from finished runs")
    for p in props:
        flag = "BLOCKED" if p.blocked else "ready"
        print(f"    [{flag}] {p.kind:16s} {p.source_run}")
    if not props:
        FAILS.append("proposal loop produced nothing: a finished-run corpus "
                     "should always yield at least a retire or escalation")


def main() -> int:
    print(f"ai-researcher integrity sweep: {ROOT}")
    check_bundles(ROOT / "demo/runs")
    check_signing_power(ROOT / "demo/runs")
    check_unsigned_extras(ROOT / "demo/runs")
    check_review_coverage(ROOT / "demo/runs")
    check_ledger(ROOT / "demo/papers/CLAIM_LEDGER.md")
    check_envelopes()
    check_mechanical_gate()
    check_judgment_available()
    check_figures()
    check_binding_coverage()
    check_proposals()
    print("\n=== summary ===")
    for n in NOTES:
        print(f"  note: {n}")
    if FAILS:
        for f in FAILS:
            print(f"  FAIL: {f}")
        print(f"\n{len(FAILS)} failure(s)")
        return 1
    print("\nno failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
