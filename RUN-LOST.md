# What was lost on 2026-10-11, and what has to be re-run

## The loss

The local working tree was wiped. Eighteen signed runs under `demo/runs/` were
deleted and exist nowhere else, because `.gitignore` listed `runs/` -- so the
project's evidence chain had exactly one copy, on the same disk as everything
else. The code, harnesses, envelopes, figures and tests were recovered from the
remote clone; the runs were not.

## Why the mechanism failed, and the fix

The project's central claim is that evidence cannot be silently lost or forged.
Its mechanism was Ed25519 signatures plus SHA-256 manifests, which defend against
tampering and against drift -- and silently do nothing about deletion. A gitignore
rule made deletion routine. `.gitignore` no longer ignores `runs/`; evidence now
travels with the code, so restoring the tree restores the evidence.

## What was lost, and what it means

Every number in the paper had a signed bundle behind it. Those bundles are gone.
What remains for each lost run is the derived record: the hypothesis note in
Obsidian, the consolidated ledger snapshot, the paper text, and — for some runs —
the amendment trail. Those prove the runs happened. They are not what the project
promised reviewers, and the paper must say so.

## Re-run plan, in priority order

A re-run produces a NEW run, not a restored one. It is honest to cite it as an
independent replication, and dishonest to cite it as the original evidence. Each
row below states which it is.

| priority | arm | calls | what it restores | cost |
|---|---|---|---|---|
| 1 | confirmation-8fam-r2 | 2560 | the primary claim's confirmatory evidence (8 families, 160 fresh items) | ~8h |
| 2 | transfer-confirmation | 640 | the two-family prospective confirmation with the fired rule | ~2h |
| 3 | cross-dataset | 1440 | the STOP-REFUTED boundary result (SVAMP/ASDiv) | ~5h |
| 4 | prompt-ablation | 1200 | wording-robustness (four variants, 80 items) | ~4h |
| 5 | coderepair-01/02 | 768 | the code-repair refutation and the policy-adaptation refutation | ~3h |
| 6 | swarm-ms + swarm-fd2 | ~100 | the amplification arm that does not survive correction | ~1h |
| 7 | sweetspot-04 | 288 | the inference-budget refutation | ~1h |

Runs NOT worth re-running: the exploratory 40-item discovery arms (transfer-01,
matrix-01, coderepair-01), whose numbers the paper already reports as
superseded by the larger samples, and lineage-01, whose verdict was withdrawn.
The project-level audit only needs the confirmatory family plus the exploratory
endpoints that appear in the paper; the rest are ledger history.

## What must change in the paper

A paragraph stating that results designated "re-run" were produced after the
evidence loss and are cited as independent replications with new timestamps and
new bundle ids, and that the original bundles no longer exist. Nothing else
changes: the numbers are re-measurable, and re-measuring is the intended property.
