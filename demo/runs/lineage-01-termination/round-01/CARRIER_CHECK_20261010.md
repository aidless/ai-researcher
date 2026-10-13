# Carrier check of ROUND_SUMMARY.md (L1/L2), 2026-10-10 09:20

Independent re-check by another session, from `artifacts/termination.jsonl` only.
Instrument: `Default Project/termination_recheck.py` (read-only, re-runnable while L3 appends;
`--selfcheck` proves its gap/duplicate detector can go red, 6/6 cells).

## Confirmed against the carrier

| ROUND_SUMMARY claim | carrier says | verdict |
|---|---|---|
| 80 rows, keys complete, no gaps | L1 40 + L2 40, all rows carry leg/item/rep/model/elapsed_s/chars/eval_count/done_reason/timeout/error/ts; grid = the 8 documented items x reps 0-4, no duplicates, no gaps | CONFIRMED |
| L1 40/40 hit the 150s client timeout | `timeout=true` on exactly 40/40 L1 rows; `error="TimeoutError"` on the same 40 | CONFIRMED |
| 0 chars received | `chars=0` on all 40 L1 rows | CONFIRMED |
| `done_reason` never arrived | `done_reason=null` x40 (the only value present for L1) | CONFIRMED |
| elapsed 150.1-150.3 s | min 150.1 / max 150.3 | CONFIRMED |
| L2 40/40 `done_reason="stop"` | `"stop"` x40, `timeout=true` x0, `error=null` x40, `chars` 1056-1626 | CONFIRMED |
| zero deviations either leg | none found by the grid or value census | CONFIRMED |
| **L2 outputs byte-identical across reps within each item** | **not evidenced by this carrier** -- see below | NOT_ASSESSED |

## The one claim the row format cannot support

The stored row keeps `chars`, `eval_count`, `done_reason`, timings -- **no answer text and
no digest**. So "byte-identical across reps" cannot be checked from `termination.jsonl` at
all; what the carrier does support is the weaker proxy that `chars` is constant across the
five reps for 8/8 items. Constant length is consistent with byte-identity and is not it:
two different 1056-character repairs are entirely possible, and temp-0 without a seed sent
(see lineage amendment G5/A4, where 10 of 50 v3b items rewrote themselves between
collections) makes "determinism holds" exactly the claim that needs a digest to survive.

This does not weaken the kill-switch reading: L1/L2 turn on *termination*, which is fully
evidenced. It matters only if someone later cites "temp-0 determinism holds inside this
run" as a determinism result. Fix is one field: write `output_sha256` per row (or store
the text) and the sentence becomes checkable retroactively for L3 onward.

## Endorsed: verdict stays PENDING L3

Refusing STOP-EXTEND on two of three legs is correct, and the note that L1/L2's
cross-chunk/cross-load reproducibility is *informal* state-variation evidence rather than
the registered L3 test is the right distinction to draw.

## L3a state at check time (not a judgement, just the census)

7 rows, `num_predict` present on all of them, `done_reason="length"` x7, `timeout=true` x0
-- i.e. with a cap the calls return rather than hanging, which is the expected shape for
the leg that measures "would it have stopped given more budget".

No file in this directory was modified by this check.
