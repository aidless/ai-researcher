"""One synthetic round for a fresh clone. No API key and no network.

The methods command writes ``result.json``. Both review seats are read from
``fixtures/offline/review.json`` and stamped ``fixture: true``. A ``STOP-*``
status is the kill-switch label for that file. It is not scientific acceptance.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from . import keystore as KS
from .loop import main as loop_main

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "offline"
_ENV_KEYS = (
    "AI_RESEARCHER_KEYS_DIR",
    "AI_RESEARCHER_ROOT_KEY",
    "AI_RESEARCHER_REVIEW_FIXTURE",
)


def _methods(script: Path) -> str:
    # json.dumps quotes the path so a space in the checkout does not split it.
    return f"{sys.executable} {json.dumps(str(script))}"


def run(workdir: Path) -> int:
    """Approve, run, and verify one synthetic round under ``workdir``.

    Trust keys stay inside ``workdir/.trust``. The caller's environment is
    restored on the way out.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    keys = workdir / ".trust"
    keys.mkdir(parents=True, exist_ok=True)
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    try:
        os.environ["AI_RESEARCHER_KEYS_DIR"] = str(keys)
        os.environ["AI_RESEARCHER_ROOT_KEY"] = str(keys / "private.key")
        os.environ["AI_RESEARCHER_REVIEW_FIXTURE"] = str(FIXTURE / "review.json")
        if not (FIXTURE / "envelope.json").is_file():
            print(f"missing fixture envelope: {FIXTURE / 'envelope.json'}", file=sys.stderr)
            return 2
        KS.init_root(keys)
        raw = json.loads((FIXTURE / "envelope.json").read_text(encoding="utf-8"))
        if raw.get("methods") != "OFFLINE_SYNTHETIC":
            print("refusing: fixture envelope methods is not OFFLINE_SYNTHETIC",
                  file=sys.stderr)
            return 2
        raw["methods"] = _methods(FIXTURE / "write_result.py")
        env_path = workdir / "envelope.json"
        env_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        rc = loop_main(["approve", str(env_path), "--by", "offline-fixture"])
        if rc != 0:
            return rc
        rc = loop_main(["run", str(env_path), "--workdir", str(workdir)])
        if rc != 0:
            return rc
        state_path = workdir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        review = (state.get("rounds") or [{}])[0].get("review") or {}
        result_path = workdir / "round-01" / "artifacts" / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"status: {state.get('status')}")
        print(f"review: fixture={'true' if review.get('fixture') else 'false'} "
              f"joint={review.get('joint')}")
        print("STOP is the kill-switch label on a synthetic result.json. "
              "It is not scientific acceptance.")
        if not str(state.get("status", "")).startswith("STOP-"):
            print("refusing: fixture run did not reach a STOP label", file=sys.stderr)
            return 1
        if not review.get("fixture"):
            print("refusing: review was not stamped fixture=true", file=sys.stderr)
            return 1
        if result.get("synthetic_fixture") is not True:
            print("refusing: result.json is not marked synthetic_fixture", file=sys.stderr)
            return 1
        return loop_main(["verify", str(workdir)])
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        print("usage: python -m ai_researcher.offline_fixture", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="ar-offline-") as td:
        return run(Path(td) / "run")


if __name__ == "__main__":
    sys.exit(main())
