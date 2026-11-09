"""Public-contract locks for the honesty bar.

These checks are about what a fresh clone can run and what the README is
allowed to say. They do not certify a scientific result.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

PROBLEM_RE = re.compile(
    r"<!-- problem-statement -->\n(?P<body>.*?)\n<!-- /problem-statement -->",
    re.S,
)
HOME_PATH = re.compile(r"/home/[A-Za-z0-9_.-]+|F:\\+deepseek")


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


class ProblemStatement(unittest.TestCase):
    def test_three_lines_name_a_guarantee_and_a_non_claim(self):
        m = PROBLEM_RE.search(_readme())
        self.assertIsNotNone(m, "README needs a problem-statement block")
        lines = [ln.strip() for ln in m.group("body").splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 1)
        self.assertLessEqual(len(lines), 3, lines)
        text = " ".join(lines).lower()
        self.assertIn("does not", text)
        self.assertTrue("stop" in text or "kill-switch" in text or "envelope" in text)


class HonestySurface(unittest.TestCase):
    def test_no_pypi_badge_and_no_home_path_in_the_public_contract(self):
        files = [
            ROOT / "README.md",
            ROOT / "FAILURE_MODES.md",
            ROOT / "STATUS.md",
            ROOT / "VERSION",
            ROOT / "pyproject.toml",
            ROOT / ".env.example",
        ]
        for path in files:
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(HOME_PATH.search(text), path)
            self.assertNotIn("pypi.org", text.lower())
            self.assertNotIn("badge/pypi", text.lower())
        src = (SRC / "ai_researcher" / "canonical.py").read_text(encoding="utf-8")
        self.assertIsNone(HOME_PATH.search(src))

    def test_version_file_matches_pyproject(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertIn(f'version = "{version}"', py)

    def test_status_stays_wip_until_the_uniqueness_gap_is_real(self):
        status = (ROOT / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("STATUS: WORK-IN-PROGRESS — not A yet", status)
        self.assertIn("arx", status.lower())

    def test_sister_lines_match_what_those_repos_say_about_themselves(self):
        text = _readme()
        self.assertIn("manager/worker", text)
        self.assertIn("statistical gate", text)
        self.assertIn("Archimedes", text)
        self.assertIn("agent skill", text)
        self.assertIn("not a library", text)
        self.assertIn("does not restate", text)

    def test_siliconflow_name_is_documented_as_historical(self):
        text = _readme() + "\n" + (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("SILICONFLOW_API_KEY", text)
        self.assertIn("OpenRouter", text)
        self.assertIn("historical", text.lower())
        self.assertIn("LLM_API_URL", text)

    def test_readme_commands_match_the_package(self):
        text = _readme()
        self.assertIn('pip install -e ".[dev]"', text)
        self.assertIn("python3 -m pytest tests -q", text)
        self.assertIn("python3 -m ai_researcher.offline_fixture", text)
        self.assertIn("python3 -m ai_researcher.loop", text)
        self.assertIn("python3 -m ai_researcher.keystore init", text)
        # The historical envelope is not the fresh-clone command.
        self.assertIn("demo/envelope.json", text)
        self.assertIn("not the fresh-clone path", text)


class FailureModes(unittest.TestCase):
    def test_names_the_three_holes(self):
        text = (ROOT / "FAILURE_MODES.md").read_text(encoding="utf-8").lower()
        self.assertIn("false progress", text)
        self.assertIn("two-seat", text)
        self.assertIn("false green", text)
        self.assertIn("envelope", text)
        self.assertIn("not scientific acceptance", text)
        self.assertIn("max_cost_usd", text)
        self.assertIn("fixture", text)


class OfflineFixture(unittest.TestCase):
    def test_canned_review_does_not_call_the_network(self):
        from ai_researcher import two_seat as TS

        path = ROOT / "fixtures" / "offline" / "review.json"
        def boom(*_a, **_k):
            raise AssertionError("fixture path called the network")

        with mock.patch.object(TS, "_chat", boom):
            with mock.patch.dict(os.environ, {"AI_RESEARCHER_REVIEW_FIXTURE": str(path)}):
                out = TS.review("claim", "evidence")
        self.assertTrue(out["fixture"])
        self.assertEqual(out["joint"], "NOT_READY")
        self.assertEqual(out["reviewer"]["endpoint_class"], "fixture")
        self.assertTrue(out["reviewer"]["review_is_not_authorship"])

    def test_fixture_file_without_the_flag_is_refused(self):
        from ai_researcher import two_seat as TS

        with tempfile.TemporaryDirectory() as td:
            bad = pathlib.Path(td) / "review.json"
            bad.write_text(json.dumps({
                "methodology": {"score": 9, "verdict": "READY", "strongest_objection": ""},
                "devil": {"score": 9, "verdict": "READY", "strongest_objection": ""},
            }), encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "AI_RESEARCHER_REVIEW_FIXTURE": str(bad),
                "SILICONFLOW_API_KEY": "not-a-real-key",
            }):
                with self.assertRaises(RuntimeError) as ctx:
                    TS.review("claim", "evidence")
            self.assertIn("fixture=true", str(ctx.exception))

    def test_one_round_verifies_then_fails_after_tamper(self):
        from ai_researcher import keystore as KS
        from ai_researcher import offline_fixture

        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td) / "run"
            rc = offline_fixture.run(work)
            self.assertEqual(rc, 0)
            state = json.loads((work / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["status"].startswith("STOP-"), state["status"])
            review = state["rounds"][0]["review"]
            self.assertTrue(review["fixture"])
            self.assertNotEqual(review.get("joint"), "READY")
            result = json.loads(
                (work / "round-01" / "artifacts" / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["synthetic_fixture"])
            keys = work / ".trust"
            self.assertTrue(KS.verify_run(work, root_dir=keys)["valid"])
            art = work / "round-01" / "artifacts" / "result.json"
            art.write_text(art.read_text(encoding="utf-8").replace("0.75", "0.11"),
                           encoding="utf-8")
            self.assertFalse(KS.verify_run(work, root_dir=keys)["valid"])

    def test_cli_names_the_non_claim_and_needs_no_key(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        env.pop("SILICONFLOW_API_KEY", None)
        env.pop("AI_RESEARCHER_REVIEW_FIXTURE", None)
        env.pop("OPENROUTER_API_KEY", None)
        proc = subprocess.run(
            [sys.executable, "-m", "ai_researcher.offline_fixture"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("not scientific acceptance", proc.stdout)
        self.assertIn("fixture=true", proc.stdout)


class RelativePaths(unittest.TestCase):
    def test_nli_clean_dir_is_inside_the_clone(self):
        path = ROOT / "demo" / "papers" / "lineage-01" / "PAPER" / "nli_adjudicate.py"
        # Importing the module pulls torch. Read the assignment instead.
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("/home/", text)
        here = path.resolve().parent
        # Keep this index in lockstep with the assignment in nli_adjudicate.py.
        self.assertIn("HERE.parents[2]", text)
        clean = here.parents[2] / "runs" / "lineage-01-clean" / "round-01" / "artifacts"
        self.assertTrue((clean / "pred_v3b.jsonl").is_file(), clean)

    def test_src_package_has_no_home_directory(self):
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(HOME_PATH.search(text), path)


class ReadmeDoesNotPointAtADeadCommand(unittest.TestCase):
    def test_fixture_envelope_declares_the_same_n_as_the_writer(self):
        env = json.loads((ROOT / "fixtures" / "offline" / "envelope.json").read_text(encoding="utf-8"))
        writer = (ROOT / "fixtures" / "offline" / "write_result.py").read_text(encoding="utf-8")
        self.assertEqual(env["methods"], "OFFLINE_SYNTHETIC")
        self.assertEqual(env["power"]["n"], 120)
        self.assertIn('"n": 120', writer)
        self.assertIsNone(HOME_PATH.search(json.dumps(env)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
