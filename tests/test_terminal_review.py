"""Behavioral test: a round that REFUTES must still be reviewed.

Not a grep of the source. This runs the real `cmd_run` against a throwaway repo root
(own trust root, own registry) with a stubbed reviewer, and asserts the terminal verdict
round carries a review record. The bug this pins: the review stage sat AFTER the terminal
branch's `break`, so seed6-01 (2026-10-09, the first run of the repaired loop) reached
STOP-REFUTED with review=None -- and the forward-dated gate check missed it because that
run's started_at is 2026-10-08T18:23Z while "today" locally is already 10-09.

Two directions: a refuting single-round run gets reviewed (the fix), and the stub records
the claim/evidence it was handed (so the assertion cannot be satisfied by an empty dict).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TerminalReview(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ar-review-")
        self.tmp = pathlib.Path(self._tmp.name)
        self.keys = self.tmp / "keys"
        self.keys.mkdir()
        # both overrides: AI_RESEARCHER_KEYS_DIR moves the pinned root, and
        # AI_RESEARCHER_ROOT_KEY makes init create a fresh pair beside it instead of
        # reusing the developer's ~/.config key
        os.environ["AI_RESEARCHER_KEYS_DIR"] = str(self.keys)
        os.environ["AI_RESEARCHER_ROOT_KEY"] = str(self.keys / "private.key")
        self.calls = []

    def tearDown(self):
        os.environ.pop("AI_RESEARCHER_KEYS_DIR", None)
        os.environ.pop("AI_RESEARCHER_ROOT_KEY", None)
        self._tmp.cleanup()

    def _envelope(self):
        # the round's "experiment" is a shell command that writes a result.json saying
        # the hypothesis failed -- the exact shape that ends a run on a STOP row
        writer = (
            "python3 -c \"import json,os,pathlib;"
            "d=pathlib.Path(os.environ.get('EVO_OUT','artifacts'));d.mkdir(parents=True,exist_ok=True);"
            "d.joinpath('result.json').write_text(json.dumps({'confirmed': False,'n_seeds':6}))\""
        )
        env = {
            "hypothesis": "stub: the effect replicates on 5 of 6 seeds",
            "methods": writer,
            "max_rounds": 1,
            "max_cost_usd": 0.0,
            "max_wall_hours": 0.1,
            "seed": 20261009,
            "power": {"n": 6, "alpha": 0.05, "min_detectable_effect": 0.5,
                      "power_at_mde": 0.8, "endpoint": "sign test"},
            "kill_switch": [
                {"condition": "confirmed == False", "action": "STOP-REFUTED",
                 "note": "stub row"},
                {"condition": "confirmed == True", "action": "STOP-EXTEND", "note": "stub"},
            ],
            "required_artifacts": ["result.json"],
            "negative_publish": "replication-report",
            "tension": "x" * 80,
            "approved_by": "test harness (hermetic; no human claim is being made here)",
            "approved_at": "2026-10-09T00:00:00+00:00",
        }
        p = self.tmp / "envelope.json"
        p.write_text(json.dumps(env, indent=2), encoding="utf-8")
        return p

    def test_refuting_round_is_still_reviewed(self):
        from ai_researcher import keystore as KS
        from ai_researcher import loop as L

        KS.init_root(self.keys)

        def fake_review(claim=None, evidence=None, **kw):
            self.calls.append({"claim": claim, "evidence": evidence})
            return {"joint": "NOT_READY", "contradiction": "stub contradiction",
                    "methodology": {"verdict": "weak"},
                    "devil": {"verdict": "fatal", "strongest_objection": "y" * 600}}

        original = L.two_seat_review
        L.two_seat_review = fake_review
        try:
            env_path = self._envelope()
            work = self.tmp / "run-01"
            rc = L.cmd_run(SimpleNamespace(envelope=str(env_path), workdir=str(work)))
        finally:
            L.two_seat_review = original
        self.assertEqual(rc, 0, "cmd_run should finish, not raise")

        st = json.loads((work / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(st["status"], "STOP-REFUTED", st["status"])
        rec = st["rounds"][0]
        self.assertIn("review", rec,
                      "a terminal STOP-REFUTED round must carry a review record -- "
                      "this is the placement bug seed6-01 exposed")
        self.assertEqual(len(self.calls), 1, "the reviewer must actually have been called")
        self.assertIn("replicates", self.calls[0]["claim"] or "")
        self.assertIn("confirmed", self.calls[0]["evidence"] or "",
                      "the reviewer must be handed the round's own result, not a placeholder")
        self.assertEqual(rec["review"]["devil_objection"], "y" * 500,
                         "objection must be stored truncated to 500 chars, not dropped")
        # and the bundle must still verify under this hermetic trust root
        vres = KS.verify_run(work, root_dir=self.keys)
        self.assertTrue(vres["valid"], vres["reason"])

    def test_review_is_not_attempted_on_non_review_rounds(self):
        """Direction two: cadence still gates mid-run rounds; otherwise the check is just
        'always call the reviewer' and the cadence it claims to honour is decoration."""
        from ai_researcher import keystore as KS
        from ai_researcher import loop as L
        KS.init_root(self.keys)
        self.assertTrue(L.should_review(1, 1))
        self.assertFalse(L.should_review(1, 3))
        self.assertTrue(L.should_review(3, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
