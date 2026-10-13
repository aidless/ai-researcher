"""The seed loop's declared n is not the sample size the test is entitled to.

seed6-01 (2026-10-09, demo/runs/seed6-01) preregistered a sign test over 6 seeds and
refuted at 4/6. Reading the artifacts adds a second denominator: 6 distinct joint
trajectories, but only 5 distinct values of the statistic (slope_excess repeats at 0.0551),
because the swarm=4 arm alone collided on two pairs of seeds. llm() sends temperature 0
with no model seed, so the only random source is the strategy-selection rng and the pci
metric is coarser than it.

This file also pins a mistake I made while writing it: my first assertion said "6 collapses
to 4", which conflated the per-arm collision with the joint draw. The test failed against
the real artifact and the artifact was right. Both denominators are now asserted separately
so nobody conflates them again.
"""
from __future__ import annotations

import importlib
import json
import unittest.mock as mock
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "demo" / "swarm"))


def _load_harness():
    # The harness reads its knobs from the environment AT IMPORT TIME. Entering it with
    # os.environ.setdefault leaked EVO_OUT into the next test in the same session (found
    # the hard way: tests/test_terminal_review.py went red only when run after this file,
    # because the fake run's artifacts were written into a temp dir this test had already
    # removed). Anything an env-var harness touches is patched, never exported.
    with mock.patch.dict(os.environ, {"EVO_SEEDS": "1,2", "EVO_ROUNDS": "1"}):
        return importlib.import_module("run_swarm")


def _rep(traj, excess=0.0, swarm=4):
    return {"arms": {f"swarm{swarm}": {"swarm": swarm, "pci_trajectory": list(traj)}},
            "slope_excess": excess, "seed": 0}


class SeedIndependence(unittest.TestCase):
    def test_identical_draws_collapse_on_both_denominators(self):
        m = _load_harness()
        reps = [_rep([0.0, 0.1], excess=0.02) for _ in range(6)]
        self.assertEqual(m.distinct_draws(reps), {"joint": 1, "statistic": 1},
                         "six identical trajectories are one sample, not six")

    def test_genuinely_different_draws_are_not_flattened(self):
        m = _load_harness()
        reps = [_rep([0.0, i / 10], excess=i / 100) for i in range(6)]
        self.assertEqual(m.distinct_draws(reps), {"joint": 6, "statistic": 6},
                         "an all-distinct batch must stay 6 -- otherwise the counter is "
                         "just a refusal machine")

    def test_per_arm_collision_moves_the_statistic_but_not_the_joint_count(self):
        """The exact shape seed6-01 had: different swarm=1 arm, same swarm=4 arm."""
        m = _load_harness()
        reps = [_rep([0.0, 0.1], excess=0.05, swarm=4) | {"arms": {
                    "swarm4": {"pci_trajectory": [0.0, 0.1]},
                    "swarm1": {"pci_trajectory": [0.0, 0.1 + i / 100]}}}
                for i in range(3)]
        got = m.distinct_draws(reps)
        self.assertEqual(got["joint"], 3, "joint trajectories differ via the swarm1 arm")
        self.assertEqual(got["statistic"], 1, "but the statistic repeats three times")

    def test_measured_values_on_the_real_run(self):
        m = _load_harness()
        art = json.loads((ROOT / "demo" / "runs" / "seed6-01" / "round-01" /
                          "artifacts" / "result.json").read_text(encoding="utf-8"))
        got = m.distinct_draws(art["reps"])
        self.assertEqual(got["joint"], 6, got)
        self.assertEqual(got["statistic"], 5, got)
        self.assertLess(got["statistic"], art["n_seeds"],
                        "the honest denominator must be <= the declared sample size")
        # the refutation does not depend on which denominator is used: over the 5 distinct
        # statistic values, positives (excess >= 0.01) are 3, still short of the
        # preregistered 5-of-6
        vals = sorted(set(art["excesses"]))
        self.assertLess(sum(1 for v in vals if v >= 0.01), 5, vals)

    def test_harness_emits_the_field(self):
        m = _load_harness()
        tmp = tempfile.TemporaryDirectory(prefix="ar-seed-")
        self.addCleanup(tmp.cleanup)
        outdir = pathlib.Path(tmp.name)
        m.llm = lambda *a, **k: "A"          # stub: no model call, no compute spent
        m.SEEDS = [11, 12, 13]
        m.ROUNDS = 1
        with mock.patch.dict(os.environ, {"EVO_OUT": str(outdir)}):
            m.main()
        res = json.loads((outdir / "result.json").read_text(encoding="utf-8"))
        self.assertIn("n_distinct", res, "the run must print the sample it actually produced")
        self.assertLessEqual(res["n_distinct"]["statistic"], res["n_seeds"])
        self.assertLessEqual(res["n_distinct"]["joint"], res["n_seeds"])
        self.assertEqual(res["n_seeds"], 3)
        # the artifact must name the model that produced it: the signed bundle's own
        # environment record carried ollama_model="" because evidence.py reads EVO_MODEL,
        # which this harness never sets -- so nothing on disk tied the numbers to a model
        prod = res["producer_models"]
        self.assertEqual(prod["executor"], m.EXECUTOR)
        self.assertIn(prod["digests"][m.EXECUTOR], ("unknown",) if True else ())
        self.assertTrue(prod["digests"][m.EXECUTOR].startswith("sha256:")
                        or prod["digests"][m.EXECUTOR] == "unknown",
                        "a real digest or the honest unknown -- never a blank")


class ForceSeedLimitation(unittest.TestCase):
    """Pinned, NOT fixed: with EVO_FORCE_DECIDE=1 the deterministic tie-break depends on
    the question text only, never on the run seed -- `judge(...)` is called without
    force_seed at demo/swarm/run_swarm.py:145+ and the fallback seeds itself with
    `(force_seed or 0) + len(question)`.

    This is left as a documented limitation rather than a drive-by fix: seeding the
    fallback per rep would make swarm=1 and swarm=4 draw DIFFERENT tie-breaks for the same
    question, which is exactly the asymmetry EVO_FORCE_DECIDE exists to remove ("any
    remaining slope gap cannot come from who-abstains-more"). The right change threads one
    force_seed per rep through both arms, and it needs a decision, not a patch.
    """

    def test_production_call_shape_gives_no_per_rep_variation(self):
        """The harness calls judge(task_q, o, best_o) -- no force_seed. So every rep that
        reaches the fallback draws the SAME letter for a given question, and those cells
        are not independent samples of the vote."""
        m = _load_harness()
        m.FORCE_DECIDE = True
        m.llm = lambda *a, **k: "我无法判断"
        q = "同一道题" * 5
        letters = [m.judge(q, "x", "y")[0] for _ in range(6)]   # exactly how it is called
        self.assertEqual(len(set(letters)), 1,
                         f"production-shaped calls returned {letters}; the fallback cannot "
                         f"vary across reps because no seed reaches it")

    def test_call_site_does_not_pass_the_seed(self):
        """Behavioural version of "the call site omits force_seed": run the real arm with a
        stubbed model and record what judge actually receives."""
        m = _load_harness()
        m.llm = lambda *a, **k: "A"
        seen = []
        original = m.judge

        def spy(*a, **k):
            seen.append(dict(k))
            return original(*a, **k)

        m.judge = spy
        try:
            m.run_arm(2, 9991)
        finally:
            m.judge = original
        self.assertTrue(seen, "the arm never reached judge -- check the stub")
        self.assertNotIn("force_seed", {k for c in seen for k in c},
                         "if someone starts passing force_seed, this test and the docstring "
                         "above must be updated together -- the arm-symmetry argument changes")

    def test_fallback_does_depend_on_the_question(self):
        m = _load_harness()
        m.FORCE_DECIDE = True
        m.llm = lambda *a, **k: "我无法判断"
        letters = {m.judge("题" * n, "x", "y")[0] for n in range(1, 40)}
        self.assertTrue(letters <= {"A", "B"})
        # the value is a pure function of question length: same length -> same letter
        self.assertEqual(m.judge("题" * 7, "x", "y")[0], m.judge("文" * 7, "a", "b")[0],
                         "同题长必同字母 -- 这才是它不看种子的可执行证据")


if __name__ == "__main__":
    unittest.main(verbosity=2)
