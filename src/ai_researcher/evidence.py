"""Per-round evidence bundle, Ed25519-signed.

Same construction as the gsm8k-self-evolve evidence chain, generalized one
level: instead of a fixed experiment, any round directory with artifacts gets a
manifest (sha256 of every file), a bundle id derived from the manifest hash,
and an Ed25519 envelope binding bundle_id + bundle_sha256 + signer.

A round whose artifacts do not verify is not a round. The loop refuses to count
it, and the kill-switch is not evaluated on it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(artifacts_dir, environment: dict = None) -> dict:
    """sha256 of every file under artifacts_dir, keyed by relative path.

    environment records what produced the artifacts (model digests, package
    versions, seeds). Three months from now, recomputation may silently use a
    different model under the same name; without the digest pinned here, the
    manifest describes files nobody can reproduce.
    """
    root = Path(artifacts_dir)
    files = {}
    for f in sorted(root.rglob("*")):
        if f.is_file():
            files[str(f.relative_to(root))] = sha256_file(f)
    doc = {"files": files}
    if environment:
        doc["environment"] = environment
    digest = hashlib.sha256(_canonical(doc)).hexdigest()
    return {"files": files, "environment": environment or {},
            "sha256": digest}


def collect_environment() -> dict:
    """Best-effort snapshot of what would affect recomputation."""
    env = {}
    import subprocess
    try:
        out = subprocess.run(["ollama", "show", os.environ.get("EVO_MODEL", ""),
                              "--modelfile"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        out = ""
    import re
    m = re.search(r"FROM\s+(\S+)", out)
    env["ollama_model"] = os.environ.get("EVO_MODEL", "")
    env["ollama_base_digest"] = m.group(1) if m else "unknown"
    try:
        import sys
        env["python"] = sys.version.split()[0]
    except Exception:
        pass
    for pkg in ("numpy", "scipy"):
        try:
            env[pkg] = __import__("importlib.metadata", fromlist=["x"]).version(pkg)
        except Exception:
            pass
    env["seed"] = os.environ.get("EVO_SEED", "unset")
    return env


def sign_round(artifacts_dir, priv_raw: bytes, signer: str,
               round_id: str, expires_at: str = "2027-10-06T00:00:00+00:00") -> dict:
    """Build the manifest, derive the bundle id, sign. Returns the envelope."""
    manifest = build_manifest(artifacts_dir, environment=collect_environment())
    bundle_id = f"{round_id}@{manifest['sha256'][:12]}"
    bundle = {"bundle_id": bundle_id, "sha256": manifest["sha256"],
              "manifest": manifest}
    priv = Ed25519PrivateKey.from_private_bytes(priv_raw)
    payload = {"bundle_id": bundle_id, "bundle_sha256": bundle["sha256"],
               "signer": signer,
               "signed_at": datetime.now(timezone.utc).isoformat(),
               "expires_at": expires_at}
    sig = priv.sign(_canonical(payload))
    return {"bundle": bundle,
            "envelope": {"payload": payload,
                         "signature": base64.b64encode(sig).decode(),
                         "algorithm": "Ed25519"}}


def verify_round(artifacts_dir, bundle: dict, envelope: dict,
                 trusted_pub_raw: bytes) -> dict:
    """Re-hash everything and check the signature. Returns {valid, reason}."""
    manifest = build_manifest(artifacts_dir,
                              environment=bundle.get("manifest", {}).get("environment"))
    if manifest["sha256"] != bundle["sha256"]:
        return {"valid": False,
                "reason": "artifact hash mismatch: the directory changed since signing"}
    drift = _environment_drift(bundle.get("manifest", {}).get("environment", {}))
    if drift:
        return {"valid": True,
                "reason": f"ok, but environment drifted since signing: {drift}. "
                          f"Recomputation may not reproduce these files."}
    p = envelope["payload"]
    if p["bundle_id"] != bundle["bundle_id"] or p["bundle_sha256"] != bundle["sha256"]:
        return {"valid": False, "reason": "bundle binding mismatch"}
    try:
        Ed25519PublicKey.from_public_bytes(trusted_pub_raw).verify(
            base64.b64decode(envelope["signature"]), _canonical(p))
    except Exception as e:
        return {"valid": False, "reason": f"bad signature: {type(e).__name__}"}
    if datetime.fromisoformat(p["expires_at"]) <= datetime.now(timezone.utc):
        return {"valid": False, "reason": "expired"}
    return {"valid": True, "reason": "ok"}


def generate_keypair():
    priv = Ed25519PrivateKey.generate()
    return (priv.private_bytes_raw(),
            priv.public_key().public_bytes_raw())


def _environment_drift(pinned: dict) -> str:
    """Compare the pinned environment against today's. Returns "" if clean."""
    now = collect_environment()
    diffs = [f"{k}: signed={pinned.get(k)!r} now={now.get(k)!r}"
             for k in sorted(set(pinned) | set(now))
             if pinned.get(k) != now.get(k) and k != "seed"]
    return "; ".join(diffs)
