"""Selection-robustness audit: the mistake I made, made impossible.

The balanced-reanalysis first reported a reversal on a top-3-per-modality subset.
Full enumeration over all 56 valid balanced subsets showed the pattern holds in
46 (82%) -- the reported subset was an unlucky 18% draw, and the two-seat
reviewers had flagged exactly this ("indistinguishable from noise or arbitrary
selection"). The error was procedural: the selection rule ("top-3 by mean
weight") used the data it was then tested on.

Rule from now on: any result that depends on a selection (subset, threshold,
seed, top-k) must be accompanied by the distribution over ALL valid selections,
computed automatically. A claim that holds in 82% of selections is reported as
"82% robust", not as "holds" or "reverses". A claim that holds in 18% is not
reported as a reversal either -- it is reported as selection-sensitive, with
the distribution attached.

This module implements that audit for the subset-selection case. The pattern
generalizes: threshold sweeps (cf. paper2's own threshold-robustness check over
gamma-cuts x CV-cuts) and seed sweeps are the same audit with a different
selection space.
"""
from __future__ import annotations

import itertools
import json


def audit_subsets(candidates: dict, metric_fn, select_fn, sizes=(3, 3)):
    """Enumerate every valid selection, apply metric_fn, report distribution.

    candidates: {group_name: [items]} e.g. {"text": [...8], "visual": [...3]}
    metric_fn: subset -> float (positive means the claimed direction holds)
    select_fn: subset -> bool, extra validity filter (default: all)
    sizes: how many to take from each group, in candidates order

    Returns {total, holds, reverses, p_holds, values, min, max, median}.
    """
    groups = list(candidates.keys())
    pools = [list(itertools.combinations(candidates[g], n))
             for g, n in zip(groups, sizes)]
    values = []
    for combo in itertools.product(*pools):
        subset = [x for part in combo for x in part]
        if not select_fn(subset):
            continue
        values.append(metric_fn(subset))
    holds = sum(1 for v in values if v > 0)
    values.sort()
    n = len(values)
    return {
        "total": n,
        "holds": holds,
        "reverses": n - holds,
        "p_holds": holds / n if n else 0.0,
        "min": values[0] if n else None,
        "max": values[-1] if n else None,
        "median": values[n // 2] if n else None,
    }


def verdict(report: dict, strong: float = 0.95, weak: float = 0.5) -> str:
    """Mechanical reading. Thresholds are defaults; preregister overrides."""
    p = report["p_holds"]
    if p >= strong:
        return "ROBUST"
    if p <= 1 - strong:
        return "REVERSED"
    if p >= weak:
        return "MOSTLY-HOLDS"
    return "SELECTION-SENSITIVE"
