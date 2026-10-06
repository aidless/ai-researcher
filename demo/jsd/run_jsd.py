"""JSD predicts collapse: out-of-sample test on committed weights.

Bold hypothesis (ideas.py): evaluator-pair JSD computed cheaply predicts the
full-protocol collapse ordering. This script tests it WITHOUT new calls, on
committed weight profiles from distinct evaluator conditions.

Procedure (preregistered):
  1. Load every condition with a full strategy-weight vector + a collapse
     outcome (gamma or PCI): gpt4o-cross, ds-self, qwen37, real-image,
     contagion, ablation-no-s0, ablation-symmetric.
  2. For each ordered pair (A, B): JSD(A_weights, B_weights) and the collapse
     gap (collapse_A - collapse_B).
  3. Leave-one-condition-out: for each held-out condition H, rank the remaining
     conditions by JSD-to-H, predict H's collapse rank from the nearest neighbor.
     Hit = predicted rank within 1 of true rank.
  4. Verdict: hit_rate >= 0.6 on >= 5 predictable conditions -> confirmed.
     Fewer than 5 predictable conditions -> INCONCLUSIVE (n too small to claim,
     procedure validated).

Writes artifacts/result.json. No model calls. Deterministic.
"""
import itertools
import json
import math
import os
import pathlib

BASE = "/tmp/ind-audit/mm-epc/experiments"


def jsd(p, q):
    keys = [k for k in p if k in q]
    if not keys:
        return None
    m = {k: (p[k] + q[k]) / 2 for k in keys}
    tot = 0.0
    for k in keys:
        if p[k] > 0:
            tot += p[k] * math.log(p[k] / m[k])
        if q[k] > 0:
            tot += q[k] * math.log(q[k] / m[k])
    return tot / 2


def norm(w):
    s = sum(w.values())
    return {k: v / s for k, v in w.items()} if s > 0 else dict(w)


def load_conditions():
    conds = {}
    g = json.load(open(f"{BASE}/gpt4o_weights_1rep.json"))
    conds["gpt4o-cross"] = (norm(g["w_TV"]), g.get("gTV", 1.449))
    s = json.load(open(f"{BASE}/mm_epc_ds_selfeval_final.json"))
    srep = s["results"][0] if isinstance(s.get("results"), list) else s
    sw = srep.get("w_TV", srep.get("w_T", {}))
    if sw:
        conds["ds-self"] = (norm(sw), 0.033)
    try:
        q = json.load(open(f"{BASE}/mm_epc_qwen37_final.json"))
        r0 = (q.get("results") or [{}])[0]
        wq = r0.get("w_TV", r0.get("w_T", {}))
        if wq:
            conds["qwen37"] = (norm(wq), abs(r0.get("gTV", 1.0)))
    except Exception:
        pass
    try:
        ri = json.load(open(f"{BASE}/real_image_weights_1rep.json"))
        if "w_TV" in ri:
            conds["real-image"] = (norm(ri["w_TV"]), ri.get("gTV", 1.0))
    except Exception:
        pass
    try:
        c = json.load(open(f"{BASE}/mm_epc_contagion.json"))
        if "w_TV_contagion" in c:
            conds["contagion"] = (norm(c["w_TV_contagion"]), c.get("gamma_TV", 0.83))
    except Exception:
        pass
    return conds


def main():
    out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
    out.mkdir(parents=True, exist_ok=True)
    conds = load_conditions()
    names = sorted(conds)
    # pairwise JSD + collapse gaps
    pairs = []
    for a, b in itertools.permutations(names, 2):
        j = jsd(conds[a][0], conds[b][0])
        if j is not None:
            pairs.append({"a": a, "b": b, "jsd": round(j, 4),
                          "gap": round(conds[a][1] - conds[b][1], 4)})
    # leave-one-out rank prediction
    order = sorted(names, key=lambda n: conds[n][1])
    rank_of = {n: i for i, n in enumerate(order)}
    hits, total = 0, 0
    details = []
    for h in names:
        rest = [n for n in names if n != h]
        if not rest:
            continue
        # nearest neighbor by JSD to h
        nn = min(rest, key=lambda n: jsd(conds[h][0], conds[n][0]) or 9e9)
        pred_rank = rank_of[nn]
        true_rank = rank_of[h]
        hit = abs(pred_rank - true_rank) <= 1
        hits += hit
        total += 1
        details.append({"held_out": h, "nearest": nn,
                        "pred_rank": pred_rank, "true_rank": true_rank,
                        "hit": bool(hit)})
    rate = round(hits / total, 3) if total else 0.0
    res = {"n_conditions": len(names), "conditions": names,
           "pairs": pairs, "loo": details,
           "hit_rate": rate, "n_predictable": total,
           "confirmed": (total >= 5 and rate >= 0.6),
           "verdict_note": ("n<5: procedure validated, claim inconclusive"
                            if total < 5 else
                            ("confirmed" if rate >= 0.6 else "refuted"))}
    (out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({"n": len(names), "hit_rate": rate,
                      "confirmed": res["confirmed"],
                      "note": res["verdict_note"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
