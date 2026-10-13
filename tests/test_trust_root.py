"""Trust-root tests: a bundle must not be launderable by re-signing it with a key
that lives inside the run directory.

Red reason for the whole file today: `ai_researcher.keystore` does not exist -- the
control was never built. The defect itself was demonstrated empirically first
(/tmp probe: tamper n_items -> re-sign with a fresh keypair -> overwrite state.json's
key_pub -> loop verify printed valid=True, reason=ok).

Two directions are covered on purpose (a check that only ever goes red is as useless
as one that only ever goes green):
  * false-negative guard -- a legitimate legacy bundle must still verify (T3),
    otherwise "everything invalid" would look like a working gate;
  * false-positive guard -- an untouched bundle whose registry line is deleted must
    NOT verify (T5), otherwise registry membership is decorative.

Nothing here writes into the project: every key, registry and tampered copy lives
under a tempfile.TemporaryDirectory that is removed at teardown.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_researcher import evidence as EV          # noqa: E402
from ai_researcher import keystore as KS          # noqa: E402  <-- absent today

LEGACY_RUN = ROOT / "demo" / "runs" / "coderepair-01"


def _copy_run(dst: Path) -> Path:
    target = dst / "run"
    shutil.copytree(LEGACY_RUN, target)
    return target


def _tamper(run: Path) -> str:
    """Change a printed number inside a signed artifact. Returns the field name."""
    p = run / "round-01" / "artifacts" / "result.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    field = next(k for k, v in doc.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
    doc[field] = doc[field] + 0.5
    p.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return field


class TrustRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ar-trustroot-")
        self.tmp = Path(self._tmp.name)
        self.root_dir = self.tmp / "keys"
        self.root_dir.mkdir()
        KS.init_root(self.root_dir)  # every case runs with a pinned root key present,
        # so "invalid" here always means the trust check itself refused, never
        # "the harness had no key to check against".

    def tearDown(self):
        self._tmp.cleanup()

    # ---- T1: naive tamper, no re-sign. The existing control already catches this.
    def test_t1_tamper_without_resign_is_invalid(self):
        run = _copy_run(self.tmp)
        _tamper(run)
        chk = KS.verify_run(run, root_dir=self.root_dir)
        self.assertFalse(chk["valid"], chk)
        self.assertIn("hash", chk["reason"])

    # ---- T2: the hole. tamper AND re-sign AND overwrite the run-local pubkey.
    def test_t2_forged_resign_is_invalid(self):
        run = _copy_run(self.tmp)
        _tamper(run)
        priv, pub = EV.generate_keypair()
        envl = EV.sign_round(run / "round-01" / "artifacts", priv, "forger", "r01")
        (run / "round-01" / "envelope.json").write_text(json.dumps(envl, indent=1), encoding="utf-8")
        st = json.loads((run / "state.json").read_text(encoding="utf-8"))
        st["key_pub"], st["key_priv"] = pub.hex(), priv.hex()
        (run / "state.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
        chk = KS.verify_run(run, root_dir=self.root_dir)
        self.assertFalse(chk["valid"], f"laundering must not verify: {chk}")
        self.assertIn("pinned", chk["reason"],
                      "the refusal must name the pinned trust root, proving the decision "
                      "came from outside the run directory rather than from state.json")

    # ---- T3: false-negative guard. The untouched legacy bundle still verifies,
    #         via keys pinned OUTSIDE the run directory (never via state.json).
    def test_t3_legacy_bundle_still_valid(self):
        pinned = self.root_dir / "legacy_pubkeys.jsonl"
        st = json.loads((LEGACY_RUN / "state.json").read_text(encoding="utf-8"))
        pinned.write_text(json.dumps({"run": LEGACY_RUN.name, "key_pub": st["key_pub"],
                                      "era": "pre-trust-root"}) + "\n", encoding="utf-8")
        chk = KS.verify_run(_copy_run(self.tmp), root_dir=self.root_dir)
        self.assertTrue(chk["valid"], f"legacy bundle must not be orphaned: {chk}")

    # ---- T4: a bundle signed under the root key verifies, and its bundle_id is
    #         recorded in the append-only registry outside the run tree.
    def test_t4_root_signed_round_verifies_and_is_registered(self):
        ks = KS.init_root(self.root_dir)
        run = self.tmp / "fresh_run"
        arts = run / "round-01" / "artifacts"
        arts.mkdir(parents=True)
        (arts / "result.json").write_text(json.dumps({"confirmed": True}) + "\n", encoding="utf-8")
        envl = KS.sign_with_root(arts, root_dir=self.root_dir, round_id="r01")
        (run / "round-01" / "envelope.json").write_text(json.dumps(envl, indent=1), encoding="utf-8")
        KS.register(envl, run_name="fresh_run", root_dir=self.root_dir)
        chk = KS.verify_run(run, root_dir=self.root_dir)
        self.assertTrue(chk["valid"], chk)
        reg = (self.root_dir / "registry.jsonl").read_text(encoding="utf-8")
        self.assertIn(envl["bundle"]["bundle_id"], reg)

    # ---- T5: false-positive guard. Delete the registry line and the same root-signed
    #         bundle must stop verifying -- otherwise the registry is decoration.
    def test_t5_missing_registry_line_is_invalid(self):
        KS.init_root(self.root_dir)
        run = self.tmp / "fresh_run"
        arts = run / "round-01" / "artifacts"
        arts.mkdir(parents=True)
        (arts / "result.json").write_text(json.dumps({"confirmed": True}) + "\n", encoding="utf-8")
        envl = KS.sign_with_root(arts, root_dir=self.root_dir, round_id="r01")
        (run / "round-01" / "envelope.json").write_text(json.dumps(envl, indent=1), encoding="utf-8")
        KS.register(envl, run_name="fresh_run", root_dir=self.root_dir)
        (self.root_dir / "registry.jsonl").write_text("", encoding="utf-8")
        chk = KS.verify_run(run, root_dir=self.root_dir)
        self.assertFalse(chk["valid"], f"unregistered bundle must not verify: {chk}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
