"""An escalation is only armable if the arm can actually take more n.

The proposer derived n=157 from the ledger and wrote "status: ready for approval" for
balanced-01 and breadth-01. Neither arm can reach 157: run_balanced.py is a deterministic
reanalysis over external files ("No model calls"), and run_breadth.py loops over a
hard-coded list of 8 diffs. Both proposals also carry `"methods": "# TODO(...): exact
command ..."` -- so approving one as written buys either a no-op (the loop's own
required-artifacts check fires) or hours of compute that re-measures the same n.

Directions tested: a knob-bearing arm must stay armable (otherwise the check is just a
refusal machine), a knob-less arm must be refused, and an unknown family must be refused
rather than silently passed.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ai_researcher.evolve import Proposal, _arm_scripts, _executability  # noqa: E402


def _prop(kind="power_escalation", run="x-01", n=157):
    return Proposal(kind=kind, title="t", source_run=run, evidence="e", tension="x" * 60,
                    method_sketch="m", kill_switch=[], n=n, mde=0.10)


class Armability(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ar-arm-")
        self.demo = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _arm(self, family, body, name="run_x.py"):
        d = self.demo / family
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")

    def test_knob_bearing_arm_is_not_blocked(self):
        self._arm("swarm", 'SEEDS = os.environ.get("EVO_SEEDS", "1")\n')
        self.assertEqual(_executability(_prop(run="swarm-fd2"), self.demo), "")

    def test_hard_coded_arm_is_blocked_with_evidence(self):
        self._arm("breadth", "DIFFS = [(1, 2), (3, 4)]\nfor did, patch in DIFFS: pass\n")
        why = _executability(_prop(run="breadth-01"), self.demo)
        self.assertTrue(why, "a knob-less arm must be refused")
        self.assertIn("n is not a knob", why)
        self.assertIn("run_x.py", why)          # names what it looked at
        self.assertIn("n=157", why)             # and what was being promised

    def test_unknown_family_is_blocked_not_silently_passed(self):
        why = _executability(_prop(run="ghost-01"), self.demo)
        self.assertTrue(why)
        self.assertIn("cannot arm", why)

    def test_other_kinds_are_untouched(self):
        self._arm("breadth", "DIFFS = []\n")
        self.assertEqual(_executability(_prop(kind="confound_audit", run="breadth-01"), self.demo),
                         "", "only power escalations promise an n change")

    def test_family_matching_prefers_the_longest_prefix(self):
        # demo/transfer and demo/transfer-confirmation both prefix "transfer-confirmation";
        # the exact/longest family dir must win, or the check reads the wrong arm's script
        self._arm("transfer", "nothing knobless\n", name="run_transfer.py")
        self._arm("transfer-confirmation", "EVO_SEEDS\n", name="run_confirm.py")
        got = _arm_scripts("transfer-confirmation", self.demo)
        self.assertTrue(got and got[0].parent.name == "transfer-confirmation",
                        f"matched {got[0].parent if got else None}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
