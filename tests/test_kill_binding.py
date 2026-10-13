"""A kill-switch that references a field the harness never emits is decoration.

matrix-01 shipped a row on `confirmed` which its script never emitted; _eval_kill
swallowed the NameError and the run was filed as a clean finish. The shared template
checker (protocols.check_emits) can't catch that class -- it compares two hand-written
lists inside one file. This test binds the envelope to the ARTIFACT instead: it stubs the
model, runs the real harness, and checks every identifier in every preregistered row
against the keys the run actually wrote.

Both directions: seed6b's rows must all resolve, and a deliberately bogus row must be
reported missing (otherwise the check passes for any envelope whatsoever).
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
import unittest.mock as mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "demo" / "swarm"))

IDENT = re.compile(r"\b([a-z_][a-z0-9_]*)\b")
PYWORDS = {"true", "false", "none", "and", "or", "not", "in", "is"}


def _harness():
    os.environ.setdefault("EVO_SEEDS", "1,2")
    os.environ.setdefault("EVO_ROUNDS", "1")
    return importlib.import_module("run_swarm")


def _run_stubbed(m, seeds=(1, 2, 3)):
    tmp = tempfile.TemporaryDirectory(prefix="ar-bind-")
    out = pathlib.Path(tmp.name)
    m.llm = lambda *a, **k: "A"
    m.SEEDS = list(seeds)
    m.ROUNDS = 1
    with mock.patch.dict(os.environ, {"EVO_OUT": str(out)}):
        m.main()
    return json.loads((out / "result.json").read_text(encoding="utf-8")), tmp


def missing_fields(env: dict, artifact: dict) -> set:
    out = set()
    for row in env.get("kill_switch", []):
        for tok in IDENT.findall(row.get("condition", "")):
            if tok.lower() in PYWORDS:
                continue
            if tok not in artifact:
                out.add(tok)
    return out


class KillBinding(unittest.TestCase):
    def test_seed6b_rows_bind_to_emitted_fields(self):
        m = _harness()
        env = json.loads((ROOT / "demo" / "swarm" / "envelope_seed6b.json")
                         .read_text(encoding="utf-8"))
        art, tmp = _run_stubbed(m)
        self.addCleanup(tmp.cleanup)
        got = missing_fields(env, art)
        self.assertFalse(got,
                         f"these preregistered rows reference fields the harness never "
                         f"emits: {sorted(got)} -- the run would silently skip them")
        # the flat scalars exist precisely so a row can be bound to them
        self.assertIn("n_distinct_statistic", art)
        self.assertIn("n_distinct_joint", art)
        self.assertLessEqual(art["n_distinct_statistic"], art["n_seeds"])

    def test_bogus_row_is_caught(self):
        """Direction two: without this, the check above passes for any envelope."""
        m = _harness()
        art, tmp = _run_stubbed(m)
        self.addCleanup(tmp.cleanup)
        fake = {"kill_switch": [{"condition": "totally_invented_field == True",
                                 "action": "STOP-REFUTED", "note": "x"}]}
        self.assertEqual(missing_fields(fake, art), {"totally_invented_field"})

    def test_draft_envelope_has_no_refusal_beyond_the_missing_approval(self):
        """Registration check WITHOUT approving: the only thing standing between this
        envelope and executable is the human act, which is deliberately not faked here."""
        from ai_researcher.envelope import Envelope
        path = ROOT / "demo" / "swarm" / "envelope_seed6b.json"
        problems = Envelope.load(path).validate()
        self.assertEqual([p for p in problems if "approved_by" not in p], [],
                         f"unexpected refusals: {problems}")
        self.assertTrue(any("approved_by" in p for p in problems),
                        "an unapproved draft MUST be refused -- if this stops failing, "
                        "the gate was removed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
