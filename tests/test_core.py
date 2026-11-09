"""Envelope, signature, and kill-switch smokes.

These used to be asserts at import time, so pytest collected zero tests and a
green count hid them. They need no API key.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_researcher import evidence as EV  # noqa: E402
from ai_researcher.envelope import Envelope, KillRow, Power  # noqa: E402
from ai_researcher.loop import _eval_kill  # noqa: E402


def _envelope(**overrides) -> Envelope:
    # A complete envelope satisfies the current contract: fixed seed, power
    # analysis, a stated tension, and a negative_publish choice. These became
    # required after the power gate landed (2026-10-07).
    args = dict(
        hypothesis="h?", methods="cmd", max_rounds=3,
        kill_switch=[KillRow("gain>=0.1", "STOP-EXTEND", "x")],
        seed=42,
        power=Power(n=120, alpha=0.05, min_detectable_effect=0.25, power_at_mde=0.8),
        tension="t" * 80,
        negative_publish="replication-report",
    )
    args.update(overrides)
    return Envelope(**args)


class EnvelopeContract(unittest.TestCase):
    def test_missing_approval_is_refused(self):
        problems = _envelope().validate()
        self.assertTrue(any("approved" in p for p in problems), problems)

    def test_approved_envelope_is_executable(self):
        env = _envelope()
        env.approved_by = "t"
        self.assertEqual(env.validate(), [])


class SignatureRoundTrip(unittest.TestCase):
    def test_sign_verifies_and_tamper_does_not(self):
        priv, pub = EV.generate_keypair()
        with tempfile.TemporaryDirectory() as td:
            (pathlib.Path(td) / "result.json").write_text('{"gain":0.75}', encoding="utf-8")
            env = EV.sign_round(td, priv, "test", "r01")
            self.assertTrue(EV.verify_round(td, env["bundle"], env["envelope"], pub)["valid"])
            (pathlib.Path(td) / "result.json").write_text('{"gain":0.99}', encoding="utf-8")
            self.assertFalse(EV.verify_round(td, env["bundle"], env["envelope"], pub)["valid"])


class KillSwitch(unittest.TestCase):
    def test_rows_and_unevaluable_input(self):
        rows = [
            {"condition": "gain >= 0.5", "action": "STOP-EXTEND"},
            {"condition": "gain >= 0.0", "action": "CONTINUE"},
        ]
        self.assertEqual(_eval_kill(rows, {"gain": 0.75})[0], "STOP-EXTEND")
        self.assertEqual(_eval_kill(rows, {"gain": 0.1})[0], "CONTINUE")
        # An unevaluable row cannot authorize a stop by itself; the caller
        # turns a CONTINUE-plus-unevaluable into STOP-KILL-UNEVALUABLE.
        self.assertEqual(_eval_kill(rows, {})[0], "CONTINUE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
