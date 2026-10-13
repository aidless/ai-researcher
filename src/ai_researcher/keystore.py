"""Out-of-run trust root for evidence bundles.

Why this module exists. Before 2026-10-09 the verification key was read from the run's
own ``state.json`` (``loop.cmd_verify``), and ``state.json`` also carried the *private*
key. Demonstrated consequence (throwaway probe on a copy of coderepair-01): change a
printed number in ``result.json``, re-sign with a brand-new keypair, overwrite
``key_pub`` in the copy's ``state.json`` -> ``verify`` printed ``valid=True, reason=ok``.
The same tamper *without* re-signing did go red, so the control caught slips and hand
edits (it caught swarm-fd) but not a deliberate laundering.

What this fixes, and the boundary it does not cross. Trust is now pinned in files that
live OUTSIDE every run directory:

    keys/root_ed25519.pub      the signing key every new bundle must be signed with
    keys/registry.jsonl        append-only, hash-chained record of every bundle_id
    keys/legacy_pubkeys.jsonl  per-run keys from the pre-trust-root era, allowlisted

so forging a green bundle now requires editing pinned files at the repo root -- which
are in version control and show up in a diff -- instead of just writing inside the run
directory. The private key is NOT kept in the repo (``AI_RESEARCHER_ROOT_KEY`` or
``~/.config/ai-researcher/root_ed25519.key``). Remaining known limit, stated plainly:
an attacker with write access to the whole machine can still rotate the root key and
append to the registry; this raises the bar from "one unsigned file write in a run dir"
to "edit audited files outside it", it is not a hardware root of trust.

Legacy era is an explicit allowlist, following the project's own convention for
pre-power-gate envelopes (``demo/legacy_envelopes.txt``): history is not rewritten, and
it is labelled instead, so ``verify`` stays meaningful rather than permanently red.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
from datetime import datetime, timezone

from . import evidence as EV

ROOT_PUB = "root_ed25519.pub"
REGISTRY = "registry.jsonl"
LEGACY = "legacy_pubkeys.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_root_dir() -> pathlib.Path:
    """Pinned files live at the repo root, never inside a run directory.

    AI_RESEARCHER_KEYS_DIR overrides it so a test (or CI) can run the whole signing
    path against a throwaway root instead of appending test bundles to the real
    keys/registry.jsonl.
    """
    env = os.environ.get("AI_RESEARCHER_KEYS_DIR")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve()
    return here.parents[2] / "keys"


def private_key_path(root_dir=None) -> pathlib.Path:
    """Where the signing key lives. Never inside a run directory.

    Precedence: explicit env override; an explicitly-passed root_dir (tests and
    hermetic use keep the key beside it); otherwise the production location outside
    the repo. The fall-through to the user config directory is for the default repo
    root only -- otherwise two temp dirs in a row silently share one private key.
    """
    env = os.environ.get("AI_RESEARCHER_ROOT_KEY")
    if env:
        return pathlib.Path(env)
    if root_dir is not None:
        rd = pathlib.Path(root_dir)
        if rd != default_root_dir() or (rd / "private.key").exists():
            return rd / "private.key"
    return pathlib.Path.home() / ".config" / "ai-researcher" / "root_ed25519.key"


def init_root(root_dir) -> dict:
    """Create the root keypair if absent. Returns the public half.

    Test/hermetic use: the private half may sit in root_dir. Production use: keep it
    outside the repo via AI_RESEARCHER_ROOT_KEY, and refuse it if it is inside a run.
    """
    root_dir = pathlib.Path(root_dir)
    root_dir.mkdir(parents=True, exist_ok=True)
    pub_file = root_dir / ROOT_PUB
    priv_path = private_key_path(root_dir)
    if priv_path.is_relative_to(root_dir) and "runs" in priv_path.parts:
        raise ValueError(f"refusing a root private key inside a run directory: {priv_path}")
    if not priv_path.exists():
        priv_path.parent.mkdir(parents=True, exist_ok=True)
        priv, pub = EV.generate_keypair()
        priv_path.write_bytes(priv)
        try:
            os.chmod(priv_path, 0o600)
        except OSError:
            pass
        pub_file.write_text(pub.hex() + "\n", encoding="utf-8")
    elif not pub_file.exists():
        raise FileNotFoundError(f"{priv_path} exists but {pub_file} does not: "
                                f"the pinned public half is missing")
    return {"pub_hex": pub_file.read_text(encoding="utf-8").strip()}


def root_pub(root_dir):
    f = pathlib.Path(root_dir) / ROOT_PUB
    return bytes.fromhex(f.read_text(encoding="utf-8").strip()) if f.exists() else None


def legacy_pubs(root_dir) -> list:
    f = pathlib.Path(root_dir) / LEGACY
    out = []
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out.append((bytes.fromhex(rec["key_pub"]), rec))
    return out


def registered_ids(root_dir) -> set:
    f = pathlib.Path(root_dir) / REGISTRY
    ids = set()
    if not f.exists():
        return ids
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.add(json.loads(line)["bundle_id"])
    return ids


def sign_with_root(artifacts_dir, root_dir=None, round_id: str = "r01",
                   signer: str = "ai-researcher-loop",
                   expires_at: str = "2027-10-06T00:00:00+00:00") -> dict:
    root_dir = pathlib.Path(root_dir) if root_dir else default_root_dir()
    priv = private_key_path(root_dir).read_bytes()
    return EV.sign_round(artifacts_dir, priv, signer, round_id, expires_at)


def register(envl: dict, run_name: str, root_dir=None) -> dict:
    """Append one hash-chained line per bundle. Append-only by convention:
    a line is never edited, and verify treats absence as not-verified."""
    root_dir = pathlib.Path(root_dir) if root_dir else default_root_dir()
    root_dir.mkdir(parents=True, exist_ok=True)
    f = root_dir / REGISTRY
    prev = ""
    if f.exists():
        lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            prev = hashlib.sha256(lines[-1].encode()).hexdigest()
    bid = envl["bundle"]["bundle_id"]
    rec = {"bundle_id": bid, "sha256": envl["bundle"]["sha256"], "run": run_name,
           "registered_at": _now(), "prev_line_sha256": prev}
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def _rounds_of(run_dir: pathlib.Path) -> list:
    """Works for loop-managed runs (state.json) and for bare round dirs, but the
    trust decision never consults the run directory's own key."""
    run_dir = pathlib.Path(run_dir)
    st_file = run_dir / "state.json"
    if st_file.exists():
        st = json.loads(st_file.read_text(encoding="utf-8"))
        return [run_dir / f"round-{r['round']:02d}" for r in st.get("rounds", [])]
    return sorted(p for p in run_dir.glob("round-*") if (p / "envelope.json").exists())


def verify_run(run_dir, root_dir=None) -> dict:
    root_dir = pathlib.Path(root_dir) if root_dir else default_root_dir()
    rp = root_pub(root_dir)
    legacy = legacy_pubs(root_dir)
    reg = registered_ids(root_dir)
    rounds = _rounds_of(pathlib.Path(run_dir))
    if not rounds:
        return {"valid": False, "reason": "no signed round found under this run dir",
                "rounds": []}
    results = []
    for rd in rounds:
        envl_file = rd / "envelope.json"
        if not envl_file.exists():
            results.append({"round": rd.name, "valid": False, "reason": "no envelope.json"})
            continue
        envl = json.loads(envl_file.read_text(encoding="utf-8"))
        bundle, signed = envl.get("bundle"), envl.get("envelope")
        if not bundle or not signed:
            results.append({"round": rd.name, "valid": False,
                            "reason": "envelope.json has no bundle/signature to check"})
            continue
        chk = None
        if rp is not None:
            chk = EV.verify_round(rd / "artifacts", bundle, signed, rp)
            if chk["valid"]:
                if bundle["bundle_id"] not in reg:
                    chk = {"valid": False,
                           "reason": f"signature ok but {bundle['bundle_id']} is absent "
                                     f"from {REGISTRY}: an unregistered bundle is not a "
                                     f"verified one"}
                results.append({"round": rd.name, **chk})
                continue
        # not the root key: fall through to the pinned legacy allowlist only
        hit = None
        for pub, rec in legacy:
            c = EV.verify_round(rd / "artifacts", bundle, signed, pub)
            if c["valid"]:
                hit = {"round": rd.name, "valid": True,
                       "reason": f"ok (legacy era: pinned in {LEGACY}, not from the run "
                                 f"dir; {rec.get('note', 'pre-trust-root bundle')})"}
                break
        if hit:
            results.append(hit)
        else:
            base = chk if chk else {"valid": False, "reason": "no pinned root key present"}
            results.append({"round": rd.name, "valid": False,
                            "reason": f"{base['reason']}; and not signed by any key pinned "
                                      f"in {LEGACY} -- trust is never taken from this run "
                                      f"directory"})
    valid = all(r["valid"] for r in results)
    bad = [r for r in results if not r["valid"]]
    reason = "all rounds verify under a pinned key" if valid else \
        "; ".join(f"{r['round']}: {r['reason']}" for r in bad)
    return {"valid": valid, "reason": reason, "rounds": results}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m ai_researcher.keystore",
                                 description="Pinned trust root for evidence bundles.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create the root keypair (private half outside the repo)")
    sub.add_parser("where", help="print where each pinned file lives")
    pl = sub.add_parser("pin-legacy",
                        help="allowlist the pre-trust-root per-run keys so history keeps verifying")
    pl.add_argument("runs_dir")
    pl.add_argument("--note", default="pre-trust-root")
    args = ap.parse_args(argv)
    root = default_root_dir()
    if args.cmd == "init":
        info = init_root(root)
        print(f"root public key pinned: {root / ROOT_PUB}")
        print(f"private half: {private_key_path(root)} (mode 600, kept outside the repo)")
        print(f"pub: {info['pub_hex'][:16]}...")
        return 0
    if args.cmd == "where":
        for f in (ROOT_PUB, REGISTRY, LEGACY):
            p = root / f
            print(f"  {'present' if p.exists() else 'MISSING':8s} {p}")
        print(f"  private: {private_key_path(root)}")
        return 0
    if args.cmd == "pin-legacy":
        runs = pathlib.Path(args.runs_dir)
        seen, added = set(), 0
        for st_file in sorted(runs.glob("*/state.json")):
            st = json.loads(st_file.read_text(encoding="utf-8"))
            kp = st.get("key_pub")
            if not kp or kp in seen:
                continue
            seen.add(kp)
            record_legacy(st_file.parent.name, kp, root, note=args.note)
            added += 1
        print(f"pinned {added} legacy run keys into {root / LEGACY}")
        print("NOTE: legacy bundles verify but are NON-AUTHORITATIVE -- their signing "
              "key sat in the run's own state.json, so they prove only that the files "
              "were not edited after signing.")
        return 0
    return 1


def record_legacy(run_name: str, key_pub_hex: str, root_dir, note: str = "pre-trust-root") -> None:
    """Pin a pre-trust-root per-run public key so its history keeps verifying."""
    root_dir = pathlib.Path(root_dir)
    root_dir.mkdir(parents=True, exist_ok=True)
    f = root_dir / LEGACY
    seen = {rec["key_pub"] for rec in map(json.loads,
                                         (l for l in f.read_text(encoding='utf-8').splitlines() if l.strip()))} \
        if f.exists() else set()
    if key_pub_hex in seen:
        return
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"run": run_name, "key_pub": key_pub_hex, "era": note}) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
