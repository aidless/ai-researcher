arXiv submission package (generated 2026-10-09, do not hand-edit).

  paper.tex                  manuscript, converted from demo/papers/SYNTHESIS.md
  fig1_transfer_forest.pdf   Figure 1 (per-family gains with 95% CIs)
  fig2_project_alpha.pdf     Figure 2 (project-level BH p-values)

Source of truth is the markdown manuscript plus the signed evidence bundles in
the repository (aidless/ai-researcher). The .tex was produced by a one-shot
converter (/tmp/md2tex.py, not committed) with hand-applied figure placement;
regenerate by re-running the converter on a fresh SYNTHESIS.md rather than
editing the .tex. Every number in the text and both figures recomputes from a
signed bundle or from scripts/project_alpha.py output.

Compile: pdflatex paper.tex (no bibliography step; references are inline).
