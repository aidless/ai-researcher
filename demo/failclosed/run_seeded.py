"""Seeded-defect escape rate: does the pre-submission pipeline catch planted bugs?

Takes the account's own gates (claim-ledger verifier, citation gate, number
scanner, mutation-control pattern) and measures them the way ICLR measured
hallucinated references: plant K known defects across copies of real
manuscript material, run the gates, count escapes. A pipeline that catches
100% is enforcement; anything under 80% is theater.

Defect classes (one each, deterministic):
  D1 hallucinated reference -- bib entry with no resolvable target
  D2 drifted number -- table value differs from evidence JSON by > tolerance
  D3 swallowed exit -- a gate step wrapped in `|| true`
  D4 unhedged inconclusive -- inconclusive claim stated as fact
  D5 stale manifest -- evidence file changed after manifest recorded

Writes artifacts/result.json {planted, caught, escape_rate, by_class}.
No model calls. Deterministic.
"""
import json
import os
import pathlib
import re
import shutil

DEFECTS = ["D1-hallucinated-ref", "D2-drifted-number", "D3-swallowed-exit",
           "D4-unhedged-inconclusive", "D5-stale-manifest"]


def check_d1_hallucinated_ref(work):
    """A bib entry / citation with no resolvable target must be flagged."""
    bib = (work / "refs.bib").read_text(encoding="utf-8", errors="ignore") \
        if (work / "refs.bib").exists() else ""
    # planted defect contains FAKEKEY2099 with no backing entry
    tex = (work / "main.tex").read_text(encoding="utf-8", errors="ignore") \
        if (work / "main.tex").exists() else ""
    cites = set(re.findall(r"\\cite\{([^}]+)\}", tex))
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    dangling = [c for cs in cites for c in cs.split(",") if c.strip() not in keys]
    return (len(dangling) == 0, f"dangling cites: {dangling[:3]}")


def check_d2_drifted_number(work):
    """Table value must match evidence JSON within tolerance."""
    try:
        ev = json.loads((work / "evidence.json").read_text(encoding="utf-8"))
        tex = (work / "main.tex").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return (False, "missing evidence files")
    for k, v in ev.items():
        if isinstance(v, (int, float)) and str(v) not in tex and f"{v:.2f}" not in tex:
            return (False, f"evidence {k}={v} absent from manuscript")
    return (True, "all evidence numbers present")


def check_d3_swallowed_exit(work):
    """No gate step may end in `|| true` / `|| echo` without a compensating check."""
    ymls = list(work.rglob("*.yml"))
    if not ymls:
        return (True, "no workflows to check")
    bad = []
    for f in ymls:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.search(r"\|\|\s*(true|echo)\b", line) and "negative" not in line.lower():
                bad.append(f"{f.name}:{i}")
    return (len(bad) == 0, f"swallowed exits: {bad[:3]}")


def check_d4_unhedged_inconclusive(work):
    """Inconclusive claims must carry hedge vocabulary."""
    p = work / "CLAIM_LEDGER.md"
    if not p.exists():
        return (True, "no ledger")
    HEDGE = ("hedge", "may be", "uncertain", "do not claim",
             "preliminary", "suggest")
    rows = [l for l in p.read_text(encoding="utf-8", errors="ignore").splitlines()
            if l.startswith("| C-")]
    # NOTE: "inconclusive" itself is NOT hedge vocabulary -- it is the status
    # token. Counting it would make every inconclusive row trivially "hedged",
    # which is exactly the failure this check exists to catch.
    bad = []
    for r in rows:
        parts = [x.strip() for x in r.strip("|").split("|")]
        if len(parts) < 6 or parts[5] != "inconclusive":
            continue
        body = " ".join(parts[1:5]).lower()
        if not any(h in body for h in HEDGE):
            bad.append(parts[0])
    return (len(bad) == 0, f"unhedged: {bad[:3]}")


def check_d5_stale_manifest(work):
    """Every file listed in the manifest must hash-match."""
    import hashlib
    p = work / "manifest.json"
    if not p.exists():
        return (True, "no manifest")
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return (False, "manifest unparsable")
    for rel, h in m.get("files", {}).items():
        f = work / rel
        if not f.exists():
            return (False, f"manifest lists missing file {rel}")
        if hashlib.sha256(f.read_bytes()).hexdigest() != h:
            return (False, f"stale hash for {rel}")
    return (True, "manifest fresh")


CHECKS = {"D1-hallucinated-ref": check_d1_hallucinated_ref,
          "D2-drifted-number": check_d2_drifted_number,
          "D3-swallowed-exit": check_d3_swallowed_exit,
          "D4-unhedged-inconclusive": check_d4_unhedged_inconclusive,
          "D5-stale-manifest": check_d5_stale_manifest}


def build_fixture(base: pathlib.Path, defect: str):
    """Copy the fixture manuscript, then plant exactly one defect."""
    work = base / "case"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(base / "clean", work)
    if defect == "D1-hallucinated-ref":
        t = work / "main.tex"
        s = t.read_text(encoding="utf-8")
        s = s.replace(r"\cite{real2024}", r"\cite{real2024,FAKEKEY2099}")
        t.write_text(s, encoding="utf-8")
    elif defect == "D2-drifted-number":
        t = work / "main.tex"
        s = t.read_text(encoding="utf-8")
        s = s.replace("0.75", "0.95")
        t.write_text(s, encoding="utf-8")
    elif defect == "D3-swallowed-exit":
        (work / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (work / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n  test:\n    steps:\n      - run: pytest || true\n", encoding="utf-8")
    elif defect == "D4-unhedged-inconclusive":
        t = work / "CLAIM_LEDGER.md"
        s = t.read_text(encoding="utf-8")
        # turn the verified claim into an inconclusive one stated as fact:
        # status flips, value stays asserted, no hedge vocabulary anywhere
        s = s.replace("| verified |", "| inconclusive |")
        s = re.sub(r"hedge[^|\n]*", "", s)
        t.write_text(s, encoding="utf-8")
    elif defect == "D5-stale-manifest":
        (work / "evidence.json").write_text('{"gain": 0.99}', encoding="utf-8")
    return work


def build_clean(base: pathlib.Path):
    c = base / "clean"
    if c.exists():
        shutil.rmtree(c)
    c.mkdir(parents=True)
    (c / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nGain 0.75~\\cite{real2024}.\n"
        "\\bibliography{refs}\n\\end{document}\n", encoding="utf-8")
    (c / "refs.bib").write_text(
        "@article{real2024,\n  title={Real},\n  author={A},\n  year={2024}\n}\n",
        encoding="utf-8")
    (c / "evidence.json").write_text('{"gain": 0.75}', encoding="utf-8")
    import hashlib
    m = {"files": {"evidence.json": hashlib.sha256(
        (c / "evidence.json").read_bytes()).hexdigest()}}
    (c / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    (c / "CLAIM_LEDGER.md").write_text(
        "# CLAIM_LEDGER\n\n| ID | 声明 | 证据 | 数值 | 如何验证 | 状态 |\n"
        "| C-gain | gain 0.75 | evidence.json -> gain | 0.75 | recompute | verified |\n",
        encoding="utf-8")
    return c


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    base = out / "work"
    build_clean(base)
    # control: clean fixture must pass everything
    control = {k: fn(base / "clean")[0] for k, fn in CHECKS.items()}
    assert all(control.values()), f"clean fixture fails: {control}"
    caught, missed = [], []
    for d in DEFECTS:
        work = build_fixture(base, d)
        ok, reason = CHECKS[d](work)
        (caught if not ok else missed).append(d)
        print(f"{d}: {'CAUGHT' if not ok else 'ESCAPED'} ({reason[:60]})")
    res = {"planted": len(DEFECTS), "caught": len(caught),
           "escape_rate": round(len(missed) / len(DEFECTS), 3),
           "escaped": missed, "confirmed": len(missed) == 0,
           "control_clean_pass": True}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"escape_rate": res["escape_rate"],
                      "confirmed": res["confirmed"]}))
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
