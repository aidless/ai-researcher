"""Demo experiment: does lowercasing improve exact-match on 4 fixed cases?

Writes artifacts/result.json with {gain, n, passed}. Deterministic, <1s.
"""
import json, pathlib
CASES = [("hello","hello"),("HeLLo","hello"),("  world  ","world"),("  EvOlVe ","evolve")]
out = pathlib.Path("artifacts")
out.mkdir(exist_ok=True)
base = sum(1 for i,e in CASES if i==e)
fixed = sum(1 for i,e in CASES if i.strip().lower()==e)
gain = (fixed-base)/len(CASES)
(out/"result.json").write_text(json.dumps({"gain":gain,"n":len(CASES),"passed":fixed,"baseline":base},indent=2)+"\n")
print(json.dumps({"gain":gain}))
