# Project-level multiplicity audit (2026-10-08)

## Result

| arm | rank | p (BH, project) | survives |
|---|---|---|---|
| matrix-01 (8 families, arithmetic) | 1 | <1e-16 | **yes** |
| transfer-01 (2 families, arithmetic) | 2 | <1e-16 | **yes** |
| swarm-ms (amplification, multi-seed) | 3 | 0.244 | no |
| coderepair-01 (code repair, refutation) | 4 | 0.244 | no |
| swarm-fd | 5 | 1.000 | no |
| swarm-fd2 | 6 | 1.000 | no |

**2 of 6 survive. Both are the transfer effect.**

## What this costs

Narrowing the paper to what survives *lowered* the venue gate score:

| | before scoping | after scoping |
|---|---|---|
| methodology | 8.29 | 8.00 |
| devil | 7.29 | 6.57 |

This is the right outcome and should not be optimised away. The gate measures a
paper against a zone-1 ideal; a paper that claims three effects and supports one
scores better than a paper that claims one effect and supports it, because breadth
and significance are being credited for claims the evidence does not carry. The
gate score is a proxy. The objective is a paper a reviewer cannot argue with, and
the reviewer who runs `scripts/project_alpha.py` will find the arithmetic family
survives and the rest does not.

## Two ways the numbers above are optimistic

1. **Ten arms carry a directional claim with no recomputable test at this n**:
   collapse-01/02, exp-01, failclosed-01, mimicry-02, swarm-01/02,
   sweetspot-01/02/03. They are outside the family because there is nothing to
   correct, which understates multiplicity. Any of them cited as evidence makes
   every p above too small.
2. lineage-01 is excluded (verdict withdrawn for contamination); coderepair-02 is
   excluded (still running).

## Method note

Endpoints are recomputed from per-item evidence, never read from a summary field.
The first version of this script read only `out_*.jsonl` and therefore dropped
matrix-01 and transfer-01 -- the two arms most likely to survive -- producing a
flattering "0/5". A parser that cannot see the strongest results understates the
problem it was built to measure. That is the seventh time this project has let a
missing value resolve to something comfortable.

Run: `PYTHONPATH=src python3 scripts/project_alpha.py`
