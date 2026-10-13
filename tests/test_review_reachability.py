"""The judgment stage must be reachable under the envelopes that actually exist.

History: the trigger was `rnd % REVIEW_EVERY == 0` with REVIEW_EVERY = 2, while 14 of the
15 envelopes on disk set max_rounds = 1. The condition was therefore unsatisfiable for
every run this project has ever executed -- and the disk agrees: 0 of 27 recorded rounds
carry a "review" key. Nothing failed, nothing warned; the stage was simply unreachable.

These tests pin the repaired condition in both directions: a single-round run MUST be
reviewed (that is the fix), and a multi-round run must NOT be reviewed on every round
(that is the cadence, and a check that always returns True would be just as worthless as
one that always returned False).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_researcher.loop import REVIEW_EVERY, should_review  # noqa: E402


class ReviewReachability(unittest.TestCase):
    def test_single_round_run_is_reviewed(self):
        # the exact shape of 14/15 envelopes on disk; before the fix this returned False
        self.assertTrue(should_review(1, 1),
                        "a run that ends at round 1 must still be reviewed")
        self.assertFalse(1 % REVIEW_EVERY == 0,
                         "the old modulo-only condition could never fire here -- that is "
                         "why the last-round clause exists")

    def test_cadence_still_applies_to_longer_runs(self):
        self.assertFalse(should_review(1, 2), "round 1 of 2 is not a review point")
        self.assertTrue(should_review(2, 4))
        self.assertFalse(should_review(3, 4))
        self.assertTrue(should_review(4, 4), "the final round is always reviewed")

    def test_other_cadences(self):
        self.assertTrue(should_review(3, 5, every=3))
        self.assertFalse(should_review(4, 5, every=3))
        self.assertTrue(should_review(5, 5, every=3))

    def test_every_round_reviewed_when_cadence_is_one(self):
        self.assertTrue(all(should_review(r, 3, every=1) for r in (1, 2, 3)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
