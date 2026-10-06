"""T0 reanalysis: does the cross-model >> self-eval pattern survive balancing?

The published design has 8 text-domain vs 3 visual-domain strategies, so text
has more slots to accumulate weight before any evaluator effect. This script
restricts every weight vector to a balanced 3-text + 3-visual subset
(top-3 by mean weight within each modality, fixed before seeing the answer),
renormalizes to the simplex, recomputes PCI, and compares the cross-model vs
self-eval ordering on full vs balanced sets.

Writes artifacts/result.json {full, balanced, verdict}.
No model calls. Deterministic.
"""
import json
import math
import os
import pathlib
import sys

sys.path.insert(0, "/tmp/ind-audit/mm-epc")
from compute_normalized_metrics import pci, TEXT_STRATEGIES, VISUAL_STRATEGIES

out = pathlib.Path(os.environ.get("EVO_OUT", "artifacts"))
out.mkdir(parents=True, exist_ok=True)
g = json.load(open("/tmp/ind-audit/mm-epc/experiments/gpt4o_weights_1rep.json"))
s = json.load(open("/tmp/ind-audit/mm-epc/experiments/mm_epc_ds_selfeval_final.json"))
srep = s["results"][0] if isinstance(s.get("results"), list) else s
sw = srep.get("w_TV", srep.get("w_T", {}))


def mean_w(ds, k):
    vals = [d[k] for d in ds if k in d]
    return sum(vals) / len(vals)


cands = [g["w_TV"], sw]
t3 = sorted([k for k in TEXT_STRATEGIES if all(k in d for d in cands)],
            key=lambda k: -mean_w(cands, k))[:3]
v3 = sorted([k for k in VISUAL_STRATEGIES if all(k in d for d in cands)],
            key=lambda k: -mean_w(cands, k))[:3]
keep = t3 + v3


def sub(w):
    s_ = sum(w[k] for k in keep)
    return {k: w[k] / s_ for k in keep}


full = {"cross": pci(g["w_TV"]), "self": pci(sw)}
bal = {"cross": pci(sub(g["w_TV"])), "self": pci(sub(sw))}
res = {"n_strategies_full": 11, "n_strategies_balanced": 6,
       "kept_text": t3, "kept_visual": v3,
       "full": full, "balanced": bal,
       "full_order": "cross>self" if full["cross"] > full["self"] else "self>=cross",
       "balanced_order": "cross>self" if bal["cross"] > bal["self"] else "self>=cross",
       "confirmed": (bal["cross"] > bal["self"])}
(out / "result.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps({"full": full, "balanced": bal,
                  "confirmed": res["confirmed"]}, indent=1))
