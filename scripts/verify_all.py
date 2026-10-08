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
from ai_researcher.envelope import Envelope  # noqa: E402
from ai_researcher.loop import _parse_ledger  # noqa: E402
from ai_researcher.quality import mechanical_check  # noqa: E402

FAILS: list[str] = []
NOTES: list[str] = []


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_bundles(runs_dir: pathlib.Path) -> None:
    section("evidence bundles")
    ok = bad = 0
    invalid = []
    for rd in sorted(runs_dir.glob("*/round-*")):
        ep = rd / "envelope.json"
        if not ep.exists():
            continue
        state = json.loads((rd.parent / "state.json").read_text(encoding="utf-8"))
        if not state.get("key_pub"):
            continue
        envl = json.loads(ep.read_text(encoding="utf-8"))
        pub = bytes.fromhex(state["key_pub"])
        # sign_round returns {"bundle":..., "envelope":...}; verify_round wants the
        # inner envelope, which is where payload/signature live.
        signed = envl.get("envelope", envl)
        res = verify_round(rd / "artifacts", envl["bundle"], signed, pub)
        if res["valid"]:
            ok += 1
        else:
            bad += 1
            invalid.append((rd.parent.name, res["reason"]))
    print(f"  {ok} valid, {bad} invalid")
    for name, reason in invalid:
        line = f"{name}: {reason}"
        # A bundle invalid because a human edited a signed artifact is a
        # documented, intentional state in this repo (swarm-fd). It is reported
        # loudly and allowed only when an amendment explains it.
        amd = (runs_dir / name / "round-01" / "amendment.json")
        if amd.exists():
            NOTES.append(f"{line} -- documented by amendment, expected")
        else:
            FAILS.append(line)
    if bad:
        print("  invalid bundles listed above; those without an amendment FAIL")


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
    unbound = [r for r in recording if not any(r in b for b in bound)]
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
    check_unsigned_extras(ROOT / "demo/runs")
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
