"""One canonical, kernel-readable absolute path for this repository.

Why this module exists. The working tree's real directory name contains a single
backslash: /home/liuzewen/F:\\deepseek/ai-researcher. Nearly every ordinary way of
deriving a path here -- the shell's $PWD, os.getcwd(), pathlib.resolve(),
os.path.abspath, __file__ under `python -m` -- reports it with the backslash
DOUBLED, and any path built from that doubled form fails an existence check on a
file that is present. During the 2026-10-11 recovery this cost hours of "no repo
root" and "GSM8K missing" failures whose artifacts did not exist at all, plus a
run that reported a refutation because it could not read its own item bank.

The fix is not cleverness, it is centralisation: ONE function, verified by
actually READING a deep marker file, used by the loop and every harness. A path
that cannot read data/gsm8k/test.jsonl is not the repository root as far as this
tree is concerned.
"""
from __future__ import annotations

import os

# The single-backslash form, written explicitly. Derived forms are all doubled.
_MANUAL_ROOT = "/home/liuzewen/F:" + chr(92) + "deepseek/ai-researcher"

# Deep marker: readable only under the correct form. A shallow marker like
# src/ai_researcher/loop.py is readable under BOTH forms and cannot discriminate.
_MARKER = os.path.join("data", "gsm8k", "test.jsonl")


def _readable(path: str) -> bool:
    try:
        with open(os.path.join(path, _MARKER), "rb"):
            return True
    except OSError:
        return False


def repo_root() -> str:
    """The repository root, in a form the kernel can walk."""
    if _readable(_MANUAL_ROOT):
        return _MANUAL_ROOT
    cands = []
    env = os.environ.get("EVO_REPO_ROOT")
    if env:
        cands.append(env)
    try:
        import pathlib
        here = pathlib.Path(os.path.abspath(__file__))
        cands.append(str(here.parents[2]))
        cands.append(os.getcwd())
    except Exception:
        pass
    for c in cands:
        for form in (c, c.replace(chr(92) * 2, chr(92))):
            if _readable(form):
                return form
    raise RuntimeError(f"no kernel-readable repository root; tried {cands}")


def join(*parts: str) -> str:
    return os.path.join(repo_root(), *parts)
