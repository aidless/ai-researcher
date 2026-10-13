#!/usr/bin/env python3
"""Build MANUSCRIPT_draft_v1.pdf from the markdown draft (xelatex).

Reproducible: rerun this script. Requires xelatex + AR PL UMing/UKai fonts
(present on this box). Output next to the .md.
Usage: python3 build_pdf.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEM = sys.argv[1] if len(sys.argv) > 1 else "MANUSCRIPT_draft_v1"
MD = HERE / (STEM + ".md")
TEX = HERE / (STEM + ".tex")

LATEX_SPECIALS = {"&": r"\&", "%": r"\%", "$": r"\$",
                  "#": r"\#", "_": r"\_", "{": r"\{",
                  "}": r"\}", "~": r"\textasciitilde{}",
                  "^": r"\textasciicircum{}"}


def esc(text: str) -> str:
    out = []
    for ch in text:
        out.append(LATEX_SPECIALS.get(ch, ch))
    return "".join(out)


def inline(text: str) -> str:
    """`code` -> texttt, **bold** -> textbf, with escaping outside them."""
    parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`"):
            out.append(r"\texttt{" + esc(p[1:-1]) + "}")
        elif p.startswith("**") and p.endswith("**"):
            out.append(r"\textbf{" + esc(p[2:-2]) + "}")
        else:
            out.append(esc(p))
    return "".join(out)


def convert(md: str) -> str:
    lines = md.splitlines()
    body: list[str] = []
    i = 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            body.append(r"\end{itemize}")
            in_list = False

    title_done = False
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or s == "---":
            close_list()
            i += 1
            continue
        if s.startswith("# ") and not title_done:
            title_done = True
            body.append(r"\title{" + inline(s[2:].strip()) + "}")
            body.append(r"\author{DRAFT v0 --- author review required before any citation or submission}")
            body.append(r"\date{2026-10-10}")
            body.append(r"\maketitle")
            i += 1
            continue
        if s.startswith("# "):
            close_list()
            body.append(r"\section*{" + inline(s[2:].strip()) + "}")
            i += 1
            continue
        if s.startswith("## "):
            close_list()
            body.append(r"\section*{" + inline(s[3:].strip()) + "}")
            i += 1
            continue
        if s.startswith("> "):
            close_list()
            body.append(r"\begin{quote}\small" + inline(s[2:].strip())
                        + r"\end{quote}")
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\|[\s:\-|]+\|\s*$", lines[i + 1]):
            close_list()
            header = [c.strip() for c in s.strip("|").split("|")]
            ncol = len(header)
            # p-columns wrap long cells; l-columns overflowed the page
            # (reviewer: "§5 table garbled"). 15.5cm over ncol columns.
            w = 15.5 / ncol
            body.append(r"\begin{center}\small\begin{tabular}{%s}"
                        % ("|".join([f"p{{{w:.1f}cm}}"] * ncol)))
            body.append(r"\hline")
            body.append(" & ".join(inline(c) for c in header) + r" \\ \hline")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip("|").split("|")]
                body.append(" & ".join(inline(c) for c in row) + r" \\ \hline")
                i += 1
            body.append(r"\end{tabular}\end{center}")
            continue
        if re.match(r"^(\- \[[ x]\]|\- |\* )", s):
            if not in_list:
                body.append(r"\begin{itemize}")
                in_list = True
            item = re.sub(r"^(\- \[[ x]\]|\- |\* )", "", s)
            if item.startswith("["):
                item = item[3:].strip()
            body.append(r"\item " + inline(item))
            i += 1
            continue
        close_list()
        body.append(inline(s) + "\n")
        i += 1
    close_list()

    return "\n".join([
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage{xeCJK}",
        r"\setCJKmainfont{AR PL UMing CN}",
        r"\usepackage[margin=2.5cm]{geometry}",
        r"\usepackage{hyperref}",
        r"\usepackage{longtable}",
        r"\setlength{\parskip}{0.6em}",
        r"\begin{document}",
        *body,
        r"\end{document}",
        "",
    ])


def main() -> int:
    TEX.write_text(convert(MD.read_text(encoding="utf-8")),
                   encoding="utf-8")
    # NOTE: never pass the absolute path (the backslash in F:\deepseek is
    # parsed as TeX escapes). cd in and use the bare filename.
    for _ in range(2):
        r = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", TEX.name],
            capture_output=True, text=True, timeout=300, cwd=str(HERE))
    logp = HERE / (STEM + ".log")
    log = (logp.read_text(encoding="utf-8", errors="replace")
           if logp.exists() else "")
    if "Output written on" in log:
        import re as _re
        m = _re.search(r"Output written on .*? \((\d+) pages?", log)
        print(f"PDF OK ({m.group(1) if m else '?'} pages): "
              f"{HERE / (STEM + '.pdf')}")
        return 0
    print("XELATEX FAILED; tail of log:")
    print("\n".join(log.splitlines()[-25:]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
