"""Resolve this repository from the file tree, not from a personal machine path.

A checkout whose directory name contains a single backslash can make
``os.path`` and ``pathlib`` double that slash, so an existence check misses a
file that is present. Set ``EVO_REPO_ROOT`` to the form the kernel can open.
This module does not embed a home directory.
"""
from __future__ import annotations

import os

# Deep marker: readable only under the correct form. A shallow marker like
# src/ai_researcher/loop.py is readable under BOTH a doubled-backslash path
# and the real path, and cannot discriminate.
_MARKER = os.path.join("data", "gsm8k", "test.jsonl")


def _readable(path: str) -> bool:
    try:
        with open(os.path.join(path, _MARKER), "rb"):
            return True
    except OSError:
        return False


def repo_root() -> str:
    """The repository root, in a form the kernel can walk."""
    cands = []
    env = os.environ.get("EVO_REPO_ROOT")
    if env:
        cands.append(env)
    try:
        here = os.path.abspath(__file__)
        # src/ai_researcher/canonical.py -> repository root
        cands.append(os.path.dirname(os.path.dirname(os.path.dirname(here))))
        cands.append(os.getcwd())
    except Exception:
        pass
    tried = []
    for c in cands:
        for form in (c, c.replace(chr(92) * 2, chr(92))):
            if form in tried:
                continue
            tried.append(form)
            if _readable(form):
                return form
    raise RuntimeError(
        "no kernel-readable repository root; set EVO_REPO_ROOT. tried "
        + repr(tried))


def join(*parts: str) -> str:
    return os.path.join(repo_root(), *parts)
