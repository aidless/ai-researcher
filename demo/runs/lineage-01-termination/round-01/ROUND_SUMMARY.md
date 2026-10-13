# termination round-01: L1+L2 verdict (L3 pending)

> Source: `artifacts/termination.jsonl` (80 rows), `contamination_watch.jsonl`.
> Instrument: `termination_run.py` (Default Project). Protocol: 草案 §2 L1+L2.
> L3 was registered as a separate envelope + second batch — NOT run here.

## Data (recompute: 80 rows, keys leg/item/rep complete, no gaps)

- **L1** (v3c, 8 items x 5 reps, no `num_predict` cap): **40/40 hit the 150 s
  client timeout**, 0 chars received, `done_reason` never arrived
  (elapsed 150.1–150.3 s, all rows). Zero deviations: every item 5/5
  non-terminating.
- **L2** (v3b, same 8 items x 5): **40/40 `done_reason="stop"`**, outputs
  byte-identical across reps within each item (temp-0 determinism holds
  inside this run). Zero deviations.

## Exclusivity record

- Every chunk refused on live competitors; two stuck zombies
  (transfer `run_confirmation.py`, 0:03–0:04 CPU over 11–14 h) explicitly
  exempted per chunk with CPU/elapsed logged.
- Guard lock held-stale by the same stuck pid throughout; not broken
  (breaking it forks mutual exclusion silently). Bypass logged per chunk.
- Post-hoc check available: no error rows, no partial rows, uniform
  elapsed distribution — nothing in the data suggests mid-run contention.

## Verdict: PENDING L3 (not STOP-EXTEND)

Per the registered kill switch, STOP-EXTEND is the conjunction
L1-all-nonstop AND L2-all-stop AND L3-no-state-difference. The first two
conjuncts are satisfied exactly as specified. The third is unmeasured.
Claiming STOP-EXTEND now would be reading a verdict off two legs of a
three-legged switch. L3 needs its own envelope (draft: `L3-envelope-draft`
in this directory, UNSIGNED) and ~30–45 min on a genuinely idle machine.

## What L1+L2 already establish (without L3)

- The 8 items' non-termination reproduces 40/40 across ~4 h wall time,
  five separate chunks, and varying background load (zombies present
  throughout, E2 active during early chunks) — informal state-variation
  evidence, but NOT the registered L3 test. Do not cite it as such.
- v3b terminates on the same items 40/40 with byte-identical outputs:
  the items are answerable; the v3c property is arm-specific.
- The kill-switch question is now reduced to exactly one unmeasured
  conjunct: state-dependence (L3).

---

## L3 legs complete (2026-10-10) — VERDICT: STOP-EXTEND (full)

| leg | condition | n | outcome |
|---|---|---|---|
| L3a cold (no model preloaded) | fresh load per first call | 8 | 8/8 `length`, chars identical to L3b/L3c per item |
| L3b hot (30 warmups first) | 30 warmup calls then measured | 8 | 8/8 `length` (post-void-cutoff rows only; first attempt voided, see below) |
| L3c contended (qwen3:0.6b loop alongside, 14 contender calls completed) | deliberate contention | 8 | 8/8 `length`, byte-identical outputs; elapsed 114–147 s vs 109–116 s uncontended (contention visible in timing, invisible in outcome) |

Kill-switch conjunction now fully measured:
L1-all-nonstop (40/40) AND L2-all-stop (40/40) AND L3-no-difference-across-states.
**STOP-EXTEND**: v3c non-termination on these 8 items is a checkpoint
property, not a machine-state artifact. Next step per the preregistration:
token-level instrumentation (`/api/generate` + stream, EOS probability) —
a new-mechanism question, not a lineage patch.

### L3b first attempt: voided (recorded, not hidden)

First L3b attempt ran 4/8 `length` + 4/8 HTTPError under GPU-trainer
contention invisible to the process monitor (same G10 hole). Whole leg
voided by cutoff `2026-10-10T10:16:46` (see `contamination_watch.jsonl`
void-leg event); re-ran full leg clean. Adjudication uses only post-cutoff
rows — same rule for resume and verdict, so the two cannot disagree.
Monitor now snapshots non-ollama GPU consumers per entry.

### Instrument bugs fixed during this run (own mistakes, kept on record)

1. `termination_run.py` loop body indented under `continue` — ran a full
   chunk writing 0 rows; caught by its own "wrote 0" output.
2. Half-applied monitor patch (call added, `def gpu_state` missing) —
   NameError on first use; caught immediately, fixed, re-verified.
3. Patch scripts applied without assert now assert replacement counts
   (the two bugs above were both unasserted `str.replace`).
