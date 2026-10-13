"""The reviewer is an instrument: it must name itself, and a same-family reviewer is not
independent.

Before 2026-10-09 the judgment half had never executed anywhere (0 of 27 recorded rounds
carry a review; CI says so in its own summary). The blocker was a config choice, not a
missing feature: `_resolve_backend` required an API key even for a localhost endpoint, so
the one free cross-family reviewer on this machine -- ollama -- was unusable, while
executors and judge were both qwen2.5:7b (demo/swarm/run_swarm.py:26-27).

Both directions are pinned: a localhost endpoint without a key must WORK, and a remote
endpoint without a key must still REFUSE (dropping the check entirely would have been the
other kind of silent failure).
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest
import unittest.mock as mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_researcher import two_seat as TS  # noqa: E402


class BackendResolution(unittest.TestCase):
    def test_local_endpoint_needs_no_key(self):
        env = {"LLM_API_URL": "http://127.0.0.1:11434/v1/chat/completions",
               "REVIEW_MODEL": "llama3.1:8b", "SILICONFLOW_API_KEY": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            model, url, key, prov = TS._resolve_backend()
        self.assertEqual(model, "llama3.1:8b")
        self.assertEqual(prov["endpoint_class"], "local")
        self.assertTrue(prov["review_is_not_authorship"],
                        "a review must never be readable as approval")

    def test_remote_endpoint_without_key_still_refuses(self):
        env = {"LLM_API_URL": "https://openrouter.ai/api/v1/chat/completions",
               "SILICONFLOW_API_KEY": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(RuntimeError):
                TS._resolve_backend()


class FamilyIndependence(unittest.TestCase):
    def test_different_family_counts(self):
        self.assertTrue(TS.cross_family("llama3.1:8b", ["qwen2.5:7b", "qwen2.5:7b"]))

    def test_same_family_is_not_independent(self):
        self.assertFalse(TS.cross_family("qwen2.5:7b", ["qwen2.5:7b"]),
                         "a qwen reviewer over qwen output supplies no independence")

    def test_prefix_only_comparison_overclaims_for_hub_ids(self):
        """Documented limitation, pinned as BEHAVED not as DESIRED: family_of() takes the
        first path segment, so a hub-prefixed id ("google/gemma3:4b") compares "google"
        against "gemma3" and reports independence where there is none. Anyone wiring a
        HF-hub reviewer onto local qwen/gemma output must match on the model name, not the
        namespace. Recorded here so the overclaim is visible instead of latent."""
        self.assertTrue(TS.cross_family("google/gemma3:4b", ["gemma3:4b"]),
                        "behaviour changed -- update this test AND the limitation note")


class ProducerIdentity(unittest.TestCase):
    def test_digest_lookup_degrades_to_unknown_not_a_guess(self):
        sys.path.insert(0, str(ROOT / "demo" / "swarm"))
        import importlib
        os.environ.setdefault("EVO_SEEDS", "1,2")
        m = importlib.import_module("run_swarm")
        got = m._model_digests(["definitely-not-a-model:zz"])
        self.assertEqual(got, {"definitely-not-a-model:zz": "unknown"},
                         "a model that cannot be identified is recorded as unknown, "
                         "never as an empty string and never as a guessed digest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
