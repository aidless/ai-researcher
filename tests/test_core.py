import sys; sys.path.insert(0, 'src')
from ai_researcher.envelope import Envelope, KillRow
from ai_researcher import evidence as EV

# 1. envelope validation catches the missing approval
from ai_researcher.envelope import Power
# A complete envelope satisfies the CURRENT contract: fixed seed, power
# analysis, a stated tension, and a negative_publish choice. These became
# required after the power gate landed (2026-10-07), and this test kept
# constructing a bare one -- so the contract had tightened and the test had
# not, which is the same class of drift as a stale caption.
_p = Power(n=120, alpha=0.05, min_detectable_effect=0.25, power_at_mde=0.8)
_args = dict(hypothesis="h?", methods="cmd", max_rounds=3,
             kill_switch=[KillRow("gain>=0.1", "STOP-EXTEND", "x")],
             seed=42, power=_p,
             tension="t" * 80,
             negative_publish="replication-report")
e = Envelope(**_args)
assert any("approved" in p for p in e.validate()), "must require approval"
e.approved_by = "t"
assert e.validate() == [], e.validate()
print("envelope validation OK")

# 2. evidence round-trip
import tempfile, pathlib
priv, pub = EV.generate_keypair()
with tempfile.TemporaryDirectory() as td:
    (pathlib.Path(td)/"result.json").write_text('{"gain":0.75}')
    env = EV.sign_round(td, priv, "test", "r01")
    assert EV.verify_round(td, env["bundle"], env["envelope"], pub)["valid"]
    pathlib.Path(td,"result.json").write_text('{"gain":0.99}')
    assert not EV.verify_round(td, env["bundle"], env["envelope"], pub)["valid"]
print("evidence sign/verify/tamper OK")

# 3. kill-switch eval
from ai_researcher.loop import _eval_kill
rows = [{"condition":"gain >= 0.5","action":"STOP-EXTEND"},{"condition":"gain >= 0.0","action":"CONTINUE"}]
assert _eval_kill(rows, {"gain":0.75})[0] == "STOP-EXTEND"
assert _eval_kill(rows, {"gain":0.1})[0] == "CONTINUE"
assert _eval_kill(rows, {})[0] == "CONTINUE"  # unevaluable row cannot authorize anything
print("kill-switch eval OK")
