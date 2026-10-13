#!/usr/bin/env python3
r"""Confirmatory runner for lineage-01 (chunked, resumable, same discipline
as termination_run.py).

RUNS ONLY WHEN PREREG IS SIGNED. The signature gate is a file check, not a
prompt: it reads `approved_by` + `approved_at` + `bank_sha256` from
PREREG.md §8 and refuses (exit 4) if any is blank or the bank hash drifts.
No override flag -- an override here would defeat the only reason this
round exists.

Protocol (PREREG §2/§5, verbatim where it matters):
  * arms v3b, v3c over bank_d001_d150.jsonl, paired
  * temp 0, NO num_predict, timeout 150s, [:1500] truncation (production gen())
  * per-row JSONL flush; HTTPError = void candidate (NOT counted in a
    denominator; void-leg record with cutoff ts, then rerun)
  * refusal: active competitor processes (run_*.py, real CPU) refuse; stuck
    zombies exempted AND recorded; guard lock live-held by a live pid refuses
  * pre/post snapshots per chunk incl. non-ollama GPU consumers

Usage:
  python3 confirmatory_run.py v3b 0 20     # chunk (arm, start, count)
  python3 confirmatory_run.py v3c 0 20
  python3 confirmatory_run.py status       # progress per arm
Writes to <this dir>/artifacts/pred_<arm>.jsonl
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANK = HERE / "bank_d001_d150.jsonl"
PREREG = HERE / "PREREG.md"
OUT = HERE / "artifacts"
OLLAMA = "http://127.0.0.1:11434/api/generate"
LOCKFILE = "/tmp/ollama_guard.lock"
MODELS = {"v3b": "copilot-3b-lora-v3b:latest",
          "v3c": "copilot-3b-lora-v3c:latest"}
TIMEOUT = 150


def gate_signature() -> None:
    """The one gate that decides whether this round may collect data at all."""
    txt = PREREG.read_text(encoding="utf-8")
    body = txt.split("## 8.")[-1] if "## 8." in txt else txt
    approved_by = re.search(r"approved_by`?:?\s*([^\n]*)", body)
    approved_at = re.search(r"approved_at`?:?\s*([^\n]*)", body)
    bank_sha = re.search(r"bank_sha256`?:?\s*([0-9a-f]{16,64})", body)
    blank = lambda m: not m or not m.group(1).strip() or "___" in m.group(1)
    if blank(approved_by) or blank(approved_at):
        print("REFUSED: PREREG §8 not signed. This round's entire value is "
              "that its rules were locked before data; running unsigned would "
              "recreate the post-hoc problem it exists to fix. Fill "
              "approved_by / approved_at (and bank_sha256) by hand.")
        raise SystemExit(4)
    import hashlib
    want = bank_sha.group(1) if bank_sha else ""
    have = hashlib.sha256(BANK.read_bytes()).hexdigest()
    if want and want not in (have, have[: len(want)]):
        print(f"REFUSED: bank sha mismatch. PREREG records {want[:16]}…, "
              f"file is {have[:16]}…. The bank changed after signing; re-read "
              f"and re-sign, or restore the signed bank.")
        raise SystemExit(4)
    print(f"signature gate: approved_by={approved_by.group(1).strip()[:40]} "
          f"at={approved_at.group(1).strip()[:24]}")
    gate_futility()


def _cpu_seconds(t: str) -> float:
    t = t.strip()
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        days = int(d)
    p = t.split(":")
    while len(p) < 3:
        p = ["0"] + p
    return days * 86400 + int(p[-3]) * 3600 + int(p[-2]) * 60 + float(p[-1])


def competitors() -> tuple[list[str], list[str]]:
    out = subprocess.run(["ps", "-eo", "pid,etimes,time,args"],
                         capture_output=True, text=True).stdout.splitlines()
    active, exempt = [], []
    for line in out:
        if not ("run_" in line and ".py" in line and "grep" not in line
                and "confirmatory_run" not in line):
            continue
        parts = line.split(None, 3)
        try:
            elapsed, cpu = int(parts[1]), _cpu_seconds(parts[2])
        except (IndexError, ValueError):
            active.append(line.strip()[:120]); continue
        short = " ".join(line.split()[3:])[:120]
        (active if (cpu >= 60 or elapsed < 1800) else exempt).append(
            short if cpu < 60 and elapsed >= 1800 else short)
    return active, exempt


def gpu_state() -> list:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name",
             "--format=csv,noheader"], capture_output=True, text=True,
            timeout=20).stdout.splitlines()
        return [l.strip()[:100] for l in out if l.strip()
                and "llama-server" not in l]
    except Exception:  # noqa: BLE001
        return ["nvidia-smi-unavailable"]


def acquire_lock():
    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()}\n".encode())
        return fd
    except FileExistsError:
        try:
            pid = int(open(LOCKFILE).read().strip().split()[0])
            os.kill(pid, 0)
        except (ValueError, FileNotFoundError, ProcessLookupError,
                PermissionError):
            try:
                os.remove(LOCKFILE)
            except FileNotFoundError:
                pass
            return acquire_lock()
        return None


def holder_stuck(holder: str) -> bool:
    try:
        out = subprocess.run(["ps", "-o", "etimes,time", "-p", holder],
                             capture_output=True, text=True).stdout.splitlines()
        parts = out[-1].split()
        return int(parts[0]) > 1800 and _cpu_seconds(parts[1]) < 60
    except (IndexError, ValueError, subprocess.SubprocessError):
        return False


def log(tag: str, **kw) -> None:
    rec = {"chunk": tag, "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "gpu_non_ollama": gpu_state(), **kw}
    with open(HERE / "contamination_watch.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def health_probe(model: str) -> tuple[bool, str]:
    """Cheap liveness probe (num_predict=8). Distinguishes 'server wedged'
    from 'this row failed'. Snapshots GPU consumers but not server health --
    that is the gap this exists to close."""
    body = json.dumps({"model": model, "prompt": "OK?", "stream": False,
                       "options": {"temperature": 0, "num_predict": 8}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        # 120s, not 60: the model needs ~18s to (re)load after an eviction,
        # and a dead server never answers at all -- so 120s still detects
        # death but stops false-tripping on slow loads. The 60s version
        # stopped a chunk on a server that was merely reloading (d072).
        with urllib.request.urlopen(req, timeout=120) as r:
            json.loads(r.read().decode())
        return True, f"{time.monotonic() - t0:.0f}s"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__} after {time.monotonic() - t0:.0f}s"


def gen(model: str, prompt: str) -> dict:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            resp = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001 - the timeout IS a measurement here
        return {"elapsed_s": round(time.monotonic() - t0, 1), "chars": 0,
                "done_reason": None, "timeout": True,
                "error": type(e).__name__}
    txt = resp.get("response", "")[:1500]
    return {"elapsed_s": round(time.monotonic() - t0, 1), "chars": len(txt),
            "done_reason": resp.get("done_reason"), "timeout": False,
            "error": None, "output": txt}


def gate_futility() -> bool:
    """PREREG §6 futility rule: active only when the追加 approval block is
    filled. Empty -> the only lawful path is the full 150/arm."""
    txt = PREREG.read_text(encoding="utf-8")
    sec = txt.split("## 6.")[-1].split("## 7.")[0] if "## 6." in txt else ""
    m = re.search(r"approved_by_futility`?:?\s*([^\n]*)", sec)
    filled = (m and m.group(1).strip() and "___" not in m.group(1))
    print(f"futility rule: {'ARMED' if filled else 'NOT ARMED (空着即未追加签)'}")
    return bool(filled)


def load_bank() -> list:
    rows = [json.loads(l) for l in open(BANK, encoding="utf-8") if l.strip()]
    import hashlib
    print(f"bank: {len(rows)} items, sha256 "
          f"{hashlib.sha256(BANK.read_bytes()).hexdigest()[:16]}…")
    return rows


def done_ids(arm: str) -> set:
    p = OUT / f"pred_{arm}.jsonl"
    if not p.exists():
        return set()
    return {json.loads(l)["id"] for l in open(p, encoding="utf-8") if l.strip()}


def status() -> None:
    rows = load_bank()
    for arm in MODELS:
        have = done_ids(arm)
        print(f"{arm}: {len(have)}/{len(rows)} items predicted")


def run_chunk(arm: str, start: int, count: int) -> None:
    model = MODELS[arm]
    act, exempt = competitors()
    if act:
        print(f"REFUSED {arm}: competing processes:")
        for line in act:
            print(f"  {line}")
        raise SystemExit(3)
    for line in exempt:
        print(f"  exempt (stuck, logged): {line[:100]}")
    # G10 lesson, made operational: a non-ollama GPU consumer is invisible
    # to the process-table check above. Recording it is not enough -- the
    # confirmatory needs clean conditions, so REFUSE.
    gpu = gpu_state()
    if gpu:
        print(f"REFUSED {arm}: non-ollama GPU consumers present "
              f"(conditions would be contaminated, not merely slow):")
        for g in gpu:
            print(f"  {g}")
        log(f"gpu-refusal-{arm}", gpu_non_ollama=gpu)
        raise SystemExit(3)
    fd = acquire_lock()
    bypass = False
    if fd is None:
        try:
            holder = open(LOCKFILE).read().strip().split()[0]
        except (OSError, IndexError):
            holder = "?"
        if holder_stuck(holder):
            print(f"  lock held-stale by stuck pid {holder}, not taken")
            bypass = True
            log(f"lock-bypass-{arm}", holder=holder)
        else:
            print(f"REFUSED {arm}: guard lock held by live pid {holder}.")
            raise SystemExit(3)
    bank = load_bank()
    seq = bank[start:start + count]
    if not seq:
        print(f"{arm}[{start}:{start + count}]: empty range")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{arm}[{start}:{start + count}]"
    if exempt:
        log(f"exemptions-{tag}", waived_stuck_processes=exempt)
    log(f"pre-{tag}")
    n_new = n_skip = consec_err = 0
    try:
        with open(OUT / f"pred_{arm}.jsonl", "a", encoding="utf-8") as f:
            for t in seq:
                if t["id"] in done_ids(arm):
                    n_skip += 1
                    continue
                rec = {"id": t["id"], "task": t.get("task"),
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "model": model, **gen(model, t["prompt"])}
                if "output" not in rec:
                    rec["output"] = ""
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                n_new += 1
                if rec["error"]:
                    consec_err += 1
                    ok, how = health_probe(model)
                    rec["server_healthy_after_error"] = ok
                    log(f"row-error-{t['id']}", error=rec["error"],
                        server_probe=ok, probe_detail=how,
                        consecutive_errors=consec_err)
                    if not ok:
                        print(f"  !! server unhealthy after {t['id']} "
                              f"({how}); STOPPING CHUNK", flush=True)
                        log(f"chunk-abort-{arm}", at=t["id"],
                            reason="server health probe failed",
                            rows_collected=n_new)
                        break
                    if consec_err >= 3:
                        print(f"  !! 3 consecutive row errors with healthy "
                              f"server; STOPPING CHUNK for review", flush=True)
                        log(f"chunk-abort-{arm}", at=t["id"],
                            reason="3 consecutive row errors, server healthy",
                            rows_collected=n_new)
                        break
                else:
                    consec_err = 0
                print(f"  {t['id']} done_reason={rec['done_reason']} "
                      f"{rec['elapsed_s']}s chars={rec['chars']}"
                      + (f" ERR={rec['error']}" if rec["error"] else ""),
                      flush=True)
    finally:
        log(f"post-{tag}")
        if not bypass and isinstance(fd, int):
            os.close(fd)
            try:
                os.remove(LOCKFILE)
            except OSError:
                pass
    print(f"{tag}: wrote {n_new}, skipped {n_skip} already-done")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
    elif len(sys.argv) >= 4:
        gate_signature()
        run_chunk(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
