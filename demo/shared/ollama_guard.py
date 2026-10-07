"""Shared ollama client: locked, validated, retried.

Lesson learned 2026-10-07 (lineage-01): four experiments hitting local ollama
concurrently produced connection errors and truncated outputs that were baked
into prediction files as text and scored as model failures. The v3c "regression"
(1:14, p=0.001) was infrastructure contamination, not a model finding.

Two rules enforced here, not documented:
1. EXCLUSIVE LOCK: only one experiment process calls ollama at a time
   (file lock with stale detection). Concurrency corrupts silently; queueing
   is slower but honest.
2. OUTPUT VALIDATION: responses matching error patterns (connection refused,
   timeout, empty, absurdly short for the task) raise instead of returning
   text. Callers must handle the exception by retrying or recording an
   infra-error, never by scoring error text as a model answer.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
LOCKFILE = "/tmp/ollama_guard.lock"

ERROR_PATTERNS = (
    "connection refused", "connection reset", "timeout",
    "model not found", "no such model", "internal server error",
    "out of memory", "context length exceeded",
)


def _is_error_text(t: str, min_chars: int = 20) -> bool:
    low = (t or "").lower()
    if len(t or "") < min_chars:
        return True
    return any(p in low[:300] for p in ERROR_PATTERNS)


def _acquire_lock(timeout_s: int = 600):
    """Exclusive ollama lock. Stale locks (dead pid) are taken over."""
    import fcntl
    t0 = time.monotonic()
    while True:
        try:
            fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode())
            return fd
        except FileExistsError:
            try:
                with open(LOCKFILE) as f:
                    pid = int(f.read().strip().split()[0])
                os.kill(pid, 0)
            except Exception:
                try:
                    os.unlink(LOCKFILE)
                except Exception:
                    pass
                continue
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError("ollama lock held too long")
            time.sleep(5)


def _release_lock(fd) -> None:
    try:
        os.close(fd)
    except Exception:
        pass
    try:
        os.unlink(LOCKFILE)
    except Exception:
        pass


def call(model: str, prompt: str, timeout: int = 150, num_predict: int = None,
         temperature: float = 0.0) -> str:
    """One locked, validated ollama call. Raises on infra failure."""
    opts = {"temperature": temperature}
    if num_predict:
        opts["num_predict"] = num_predict
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": opts}).encode()
    fd = _acquire_lock()
    try:
        req = urllib.request.Request(OLLAMA, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = json.loads(r.read().decode())["response"]
    finally:
        _release_lock(fd)
    if _is_error_text(text):
        raise RuntimeError(f"ollama returned error-text ({len(text)} chars): "
                           f"{text[:120]!r}")
    return text
