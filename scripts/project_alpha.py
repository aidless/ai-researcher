"""Project-level multiplicity: how much of this paper survives correction for 14 runs?

Every two-seat review has asked for power. None has asked the question that comes
next: the paper reports many arms, each analysed on its own, so the family-wise
error rate is not 0.05 per arm -- it is 0.05 per arm TIMES the number of arms. Only
transfer-01 ever corrected across anything (BH across two models). Across 14 runs
nothing was corrected at all.

This script recomputes each run's primary exact test from its per-item evidence
where that is possible, then applies Benjamini-Hochberg across the whole project.
Three outcomes matter and all three are reportable:

  * survives project-level BH  -- the claim is stronger than it looked
  * survives only within-run  -- the arm's own correction was enough
  * no test available          -- descriptive or underpowered; counted, not hidden

A run whose verdict was WITHDRAWN is excluded from the family and listed as such,
because correcting over a claim that has already been retracted would understate
the multiplicity that produced the retractions.

No p-value is taken on trust from a summary field. Where the artifact carries
per-item outcomes, the exact test is recomputed from them, so a run cannot report
significance its own item data does not support.
"""
from __future__ import annotations

import json
import pathlib
import sys
from math import comb

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def mcnemar_p(fixed: int, broke: int) -> float:
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def binom_p_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial against p0."""
    if n == 0:
        return 1.0
    probs = [comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in range(n + 1)]
    obs = probs[k]
    return min(1.0, sum(pr for pr in probs if pr <= obs * (1 + 1e-9)))


def benjamini_hochberg(items, alpha: float = 0.05):
    """items: [(label, p, run)]. Returns dict label -> (p_bh, survives, rank)."""
    ranked = sorted(items, key=lambda t: t[1])
    m = len(ranked)
    out, prev = {}, 1.0
    for i in range(m - 1, -1, -1):
        label, p, run = ranked[i]
        k = i + 1
        adj = min(prev, p * m / k)
        prev = adj
        out[label] = (round(adj, 6), adj <= alpha, k, run)
    return out


# --------------------------------------------------------------------------
# per-run primary endpoints, recomputed from per-item evidence
# --------------------------------------------------------------------------

def _paired_rows(run_dir: pathlib.Path):
    """Yield (model, policy_a, policy_b, [(passed_a, passed_b)]) from out_*.jsonl."""
    art = run_dir / "round-01" / "artifacts"
    by_model = {}
    for f in sorted(art.glob("out_*.jsonl")):
        stem = f.stem[len("out_"):]
        model, _, pol = stem.rpartition("_")
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        by_model.setdefault(model, {})[pol] = rows
    for model, pols in by_model.items():
        names = sorted(pols)
        if len(names) < 2:
            continue
        a, b = names[0], names[-1]
        yield model, a, b, list(zip(pols[a], pols[b]))


def primary_transfer(run_dir: pathlib.Path):
    """Paired direct-vs-step-calc arms: pooled McNemar over families."""
    fixed = broke = 0
    fams = 0
    for _m, _a, _b, pairs in _paired_rows(run_dir):
        fams += 1
        for x, y in pairs:
            pa = bool(x.get("passed"))
            pb = bool(y.get("passed"))
            if pb and not pa:
                fixed += 1
            if pa and not pb:
                broke += 1
    if fams == 0:
        return None
    return {"p": mcnemar_p(fixed, broke), "fixed": fixed, "broke": broke,
            "families": fams,
            "endpoint": "pooled paired McNemar, direct vs step-calc"}


def primary_embedded(run_dir: pathlib.Path):
    """Runs that store per-item outcomes inside result.json, not as out_*.jsonl.

    matrix-01 and transfer-01 -- the two strongest arms in the project -- keep
    their item data at models.<m>.policies.<policy>.detail[].passed. An extractor
    that only reads out_*.jsonl silently drops both, which is the same defect as
    the family it is meant to measure: the arms most likely to survive correction
    are the ones a parser fails to see. Found by noticing that a "0/5 survive"
    result omitted the run reporting p=1.9e-47.
    """
    res = run_dir / "round-01" / "artifacts" / "result.json"
    if not res.exists():
        return None
    d = json.loads(res.read_text(encoding="utf-8"))
    models = d.get("models")
    if not isinstance(models, dict) or not models:
        return None
    fixed = broke = fams = 0
    for mv in models.values():
        pols = (mv or {}).get("policies") or {}
        direct = pols.get("direct") or {}
        step = pols.get("step-calc") or pols.get("spec-first") or {}
        dd, sd = direct.get("detail"), step.get("detail")
        if not (isinstance(dd, list) and isinstance(sd, list) and dd and sd):
            continue
        fams += 1
        for x, y in zip(dd, sd):
            pa, pb = bool(x.get("passed")), bool(y.get("passed"))
            if pb and not pa:
                fixed += 1
            if pa and not pb:
                broke += 1
    if not fams:
        return None
    return {"p": mcnemar_p(fixed, broke), "fixed": fixed, "broke": broke,
            "families": fams,
            "endpoint": "pooled paired McNemar, direct vs treatment (item data in result.json)"}


def primary_seed_excess(run_dir: pathlib.Path):
    """Swarm arms: seed-level excesses against zero, exact sign test."""
    res = run_dir / "round-01" / "artifacts" / "result.json"
    if not res.exists():
        return None
    d = json.loads(res.read_text(encoding="utf-8"))
    exc = d.get("excesses")
    if not isinstance(exc, list) or not exc:
        return None
    pos = sum(1 for v in exc if isinstance(v, (int, float)) and v > 0)
    neg = sum(1 for v in exc if isinstance(v, (int, float)) and v < 0)
    k = max(pos, neg)
    return {"p": binom_p_two_sided(k, pos + neg, 0.5),
            "positive_seeds": f"{pos}/{len(exc)}",
            "endpoint": "seed-level sign test on excess over majority-vote baseline"}


def primary_binomial_count(run_dir: pathlib.Path, key: str, expect: str):
    res = run_dir / "round-01" / "artifacts" / "result.json"
    if not res.exists():
        return None
    d = json.loads(res.read_text(encoding="utf-8"))
    v = d.get(key)
    if not isinstance(v, dict):
        return None
    total, hit = v.get("total"), v.get("holds")
    if total is None and isinstance(d.get("pairs"), int):
        total, hit = d["pairs"], d.get("n_predictable")
    if not isinstance(total, int) or not isinstance(hit, int):
        return None
    return {"p": binom_p_two_sided(max(hit, total - hit), total, 0.5),
            f"{expect}": f"{hit}/{total}",
            "endpoint": f"exact binomial, {expect} against chance"}


def primary_escape(run_dir: pathlib.Path):
    res = run_dir / "round-01" / "artifacts" / "result.json"
    if not res.exists():
        return None
    d = json.loads(res.read_text(encoding="utf-8"))
    planted = d.get("planted")
    escaped = d.get("escaped")
    # `escaped` is a LIST of escaped-defect ids in some runs and a count in
    # others. Requiring an int silently dropped failclosed-01, whose result is
    # 5 planted / 0 escaped -- a computable exact binomial (p=0.031) that the
    # audit therefore could not see.
    if not isinstance(planted, int) or planted <= 0:
        return None
    n_esc = escaped if isinstance(escaped, int) else (
        len(escaped) if isinstance(escaped, list) else None)
    if n_esc is None:
        return None
    return {"p": binom_p_two_sided(max(planted - n_esc, n_esc), planted, 0.5),
            "escaped": f"{n_esc}/{planted}",
            "endpoint": "exact binomial, defects caught against chance (0.5)"}


def primary_pass_count(run_dir: pathlib.Path):
    """Single-arm hit counts: planted/caught, or passed out of n."""
    res = run_dir / "round-01" / "artifacts" / "result.json"
    if not res.exists():
        return None
    d = json.loads(res.read_text(encoding="utf-8"))
    if isinstance(d.get("planted"), int) and isinstance(d.get("caught"), int):
        n, k = d["planted"], d["caught"]
        return {"p": binom_p_two_sided(max(k, n - k), n, 0.5),
                "caught": f"{k}/{n}",
                "endpoint": "exact binomial, defects caught against chance (0.5)"}
    if isinstance(d.get("n"), int) and isinstance(d.get("passed"), int):
        n, k = d["n"], d["passed"]
        if not n:
            return None
        return {"p": binom_p_two_sided(max(k, n - k), n, 0.5),
                "passed": f"{k}/{n}",
                "endpoint": "exact binomial, single-arm hit count against chance"}
    return None


WITHDRAWN = {"lineage-01": "v3c regression withdrawn: infrastructure contamination, "
                           "recorded by amendment"}
# A run superseded by a clean re-run: the original stays on disk with its
# amendment, but the family uses the replacement. confirmation-8fam produced
# genuine measurements that were never signed (wall clock killed it before
# aggregation); confirmation-8fam-r2 repeated the identical design with a 20h
# wall clock and a properly signed bundle. Counting both would double-count one
# experiment.
SUPERSEDED = {"confirmation-8fam": "superseded by confirmation-8fam-r2: identical "
                                   "design, signed bundle, 7/8 with the same "
                                   "boundary family (qwen3:4b)"}
DESCRIPTIVE = {"breadth-01": "agreement rate and flip count are descriptive "
                             "quantities, not a hypothesis test"}


def collect(runs_dir: pathlib.Path):
    tests, notes, excluded, untested = [], [], [], []
    inflight = []
    for rd in sorted(runs_dir.glob("*")):
        if not rd.is_dir() or not (rd / "state.json").exists():
            continue
        name = rd.name
        state = json.loads((rd / "state.json").read_text(encoding="utf-8"))
        if state.get("status") == "RUNNING":
            # An in-flight run has partial item files. Counting it would put a
            # half-finished arm into the family and let its provisional p-value
            # correct the finished ones.
            inflight.append(name)
            notes.append((name, "still RUNNING: partial evidence, excluded from "
                                "the family and not a withdrawal"))
            continue
        if name in WITHDRAWN:
            excluded.append((name, WITHDRAWN[name]))
            continue
        if name in SUPERSEDED:
            notes.append((name, "SUPERSEDED: " + SUPERSEDED[name]))
            excluded.append((name, SUPERSEDED[name]))
            continue
        if name in DESCRIPTIVE:
            notes.append((name, DESCRIPTIVE[name]))
            continue
        got = None
        for fn in (primary_transfer, primary_embedded, primary_seed_excess):
            got = fn(rd)
            if got:
                break
        if not got:
            for key, label in (("robustness", "subsets holding order"),
                               ("p_holds", "predictable pairs")):
                got = primary_binomial_count(rd, key, label)
                if got:
                    break
        for fn2 in (primary_escape, primary_pass_count):
            if got:
                break
            got = fn2(rd)
        if got and got["p"] is not None:
            tests.append((f"{name}:primary", got["p"], name))
            notes.append((name, f"{got['endpoint']}; "
                                + ", ".join(f"{k}={v}" for k, v in got.items()
                                            if k not in ("p", "endpoint"))))
        else:
            res_p = rd / "round-01" / "artifacts" / "result.json"
            carries = False
            if res_p.exists():
                try:
                    dd = json.loads(res_p.read_text(encoding="utf-8"))
                    carries = any(k in dd for k in
                                  ("gain", "transfer_gain", "excesses", "slope_excess",
                                   "separation_gap", "cross_excess", "escape_rate",
                                   "pairwise_agreement", "any_sweet_spot"))
                except Exception:
                    carries = False
            notes.append((name, ("DIRECTIONAL CLAIM WITH NO RECOMPUTABLE TEST at this n "
                                 "-- counted as untested, not dropped"
                                 if carries else
                                 "no directional claim: descriptive only")))
            if carries:
                untested.append(name)
    return tests, notes, excluded, untested, inflight


def main() -> int:
    runs = ROOT / "demo/runs"
    tests, notes, excluded, untested, inflight = collect(runs)
    print(f"project-level multiplicity over {len(tests)} testable primary endpoints "
          f"(+{len(notes)} non-testable, {len(excluded)} withdrawn)\n")
    bh = benjamini_hochberg(tests)
    for label in sorted(bh, key=lambda k: bh[k][0]):
        p_bh, ok, rank, run = bh[label]
        print(f"  {run:16s} rank {rank:2d}  p_bh={p_bh:.2e}  "
              f"{'SURVIVES' if ok else 'does not survive'} project-level BH")
    # A surviving endpoint is not a supporting result. sweetspot-04's endpoint
    # survives at p_BH = 0.013 while pointing the OPPOSITE way from its own
    # preregistered hypothesis, so it is a refutation that happens to be
    # statistically distinguishable from zero. Reporting "N of M survive"
    # without the direction would let that read as a finding.
    dir_path = ROOT / "demo/papers/endpoint-direction.json"
    try:
        dirs = json.loads(dir_path.read_text(encoding="utf-8"))["endpoints"]
    except Exception:
        dirs = {}
    aligned = [k for k, v in bh.items()
               if v[1] and dirs.get(v[3], {}).get("direction") == "aligns"]
    contradicted = [k for k, v in bh.items()
                    if v[1] and dirs.get(v[3], {}).get("direction") == "contradicts"]
    unstated = [k for k, v in bh.items()
                if v[1] and dirs.get(v[3], {}).get("direction") == "unstated"]
    n_surv = sum(1 for v in bh.values() if v[1])
    print(f"\n  {n_surv}/{len(bh)} primary endpoints survive BH at 0.05 across the project")
    print(f"  of those, {len(aligned)} SUPPORT the claim they were preregistered for")
    if contradicted:
        print(f"  and {len(contradicted)} point the OPPOSITE way from their own "
              f"hypothesis (a refutation that happens to be resolvable): "
              f"{', '.join(k.split(':')[0] for k in contradicted)}")
    if unstated:
        print(f"  {len(unstated)} made no directional promise, so survival is "
              f"descriptive only: {', '.join(k.split(':')[0] for k in unstated)}")
    print("\n=== recomputed endpoint detail ===")
    for name, detail in notes:
        print(f"  {name:16s} {detail}")
    print(f"\n  UNTESTED but carrying a directional claim: {len(untested)} "
          f"({', '.join(untested) if untested else 'none'})")
    print("  These are NOT in the BH family. If any of them is cited as evidence,")
    print("  the family is understated and its p_bh values are optimistic.")
    print("\n=== excluded from the family ===")
    for name, why in excluded:
        print(f"  {name:16s} {why}")
    if inflight:
        print(f"  in flight (not withdrawals): {', '.join(inflight)}")
    out = {
        "family_size": len(bh),
        "surviving_supporting_claim": sorted(k.split(":")[0] for k in aligned),
        "surviving_contradicting_claim": sorted(k.split(":")[0] for k in contradicted),
        "surviving_direction_unstated": sorted(k.split(":")[0] for k in unstated),
        "directions": dirs,
        "alpha": 0.05,
        "surviving": sorted(k.split(":")[0] for k, v in bh.items() if v[1]),
        "endpoints": {k: {"p_bh": v[0], "survives": v[1], "rank": v[2], "run": v[3]}
                      for k, v in bh.items()},
        "non_testable": {n: d for n, d in notes},
        "withdrawn": {n: w for n, w in excluded},
        "in_flight": inflight,
        "untested_directional_claims": untested,
    }
    p = ROOT / "demo/papers/PROJECT-LEVEL-ALPHA.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    print(f"\nwrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
