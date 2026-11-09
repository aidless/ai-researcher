"""Synthetic methods command for the offline fixture.

Writes artifacts/result.json and exits. The numbers below are chosen so the
committed envelope's STOP-EXTEND row matches. They are not a measurement.
"""
from __future__ import annotations

import json
from pathlib import Path

BODY = """{
  "gain": 0.75,
  "n": 120,
  "synthetic_fixture": true,
  "cost_usd": 0,
  "note": "Written by fixtures/offline/write_result.py. Not an experimental finding."
}
"""


def main() -> int:
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    payload = json.loads(BODY)
    (out / "result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gain": payload["gain"], "synthetic_fixture": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
