import sys; sys.path.insert(0, 'src')
from ai_researcher.envelope import Envelope, KillRow
from ai_researcher import evidence as EV

# 1. envelope validation catches the missing approval
e = Envelope("h?", "cmd", 3, kill_switch=[KillRow("gain>=0.1","STOP-EXTEND","x")])
assert any("approved" in p for p in e.validate()), "must require approval"
e.approved_by = "t"; assert e.validate() == [], e.validate()
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
