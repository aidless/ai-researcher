# Lineage McNemar follow-up (per-item paired analysis)

> **SUPERSEDED 2026-10-09 — do not cite the sentence "The v3c regression is
> real (p=0.001, 15 discordant items)" below.** It stays withdrawn, but for a
> different reason than the 2026-10-07 amendment recorded.
>
> The clean re-run finished today: v3b and v3c, 50 items each, `/tmp/ollama_guard.lock`
> held for the whole window, 0 competing processes across 121 monitor polls.
> Registered verdict: **STOP-REFUTED**.
>
> 1. The named cause explains only **v3b**. Its 5 timeouts vanished under
>    exclusive access (clean v3b: 0 runtime errors, rate 0.7317 over all 50).
> 2. **v3c's failures reproduced exactly**: the same 8 item ids as 10-07
>    (c001–c004, c006–c008, c035), same answered-length census (median 27, max 522).
>    Streaming one of them on an idle locked box showed a numbered list climbing
>    past item 75 at 20.6 chars/s with no EOS. That is the checkpoint's own
>    non-termination, not a shared server.
> 3. The 1:14 was mostly **the scorer, not the data**. 10 of v3c's 18 exclusions
>    are `classify_runtime` deleting any answer under 200 chars that mentions
>    "timeout" — and c021–c030 are `failure_diagnosis` items whose prompts
>    contain `connection refused after 240s timeout` by design. v3b retained the
>    same 10 items because it answered them at 873–1130 chars.
> 4. Three readings of the same two clean arms (`adjudicate_corrected.py`):
>    published **−0.0234**; corrected judge over answered items only
>    **v3c 0.7778 vs v3b 0.7317 = +0.0461** (paired Wilcoxon W=0, exact p=0.03125,
>    scipy agrees); corrected judge with non-answers scored as 0
>    **v3c 0.6533 vs v3b 0.7317 = −0.0784**.
>    So the published number was wrong in both directions at once: the judge
>    manufactured a capability loss by deleting v3c's best-scoring family, and
>    simultaneously hid an availability loss by dropping v3c's 8 non-terminating
>    items from the denominator instead of scoring them. **There is no capability
>    regression — v3c is better where it answers. There is a real availability
>    deficit: 8/50 items it never answers.** The judge rule at fault fails the
>    very check the item tests (`must_distinguish_provider_error`).
>    *(An earlier version of this banner said "0.7367, becomes +0.0050", which
>    scored empty outputs as vacuous half-credit. Superseded — see amendment A6.)*
> 5. The "queued, not done" attribution at the bottom is now done: 8 items
>    non-termination, 10 items judge exclusion, 0 items capability loss.
>
> Carriers: `demo/runs/lineage-01-clean/round-01/amendment.json` (A1–A5, G1–G9),
> `arm_termination_census.py`, `judge_length_coupling_check.py`,
> `judge_coupling_corpus_scan.py` (blast radius: these exclusions appear only in
> this run, in v3c=10 and v2=6; the other 30 scored files in the pipeline flag
> no runtime_error at all).

The rate drops (-0.0085, -0.0158) cannot separate signal from noise alone.
Per-item McNemar on the 50 paired items:

| pair | discordants (fixed:broken) | p | verdict |
|---|---|---|---|
| v3 vs v3b | 2:5 | 0.45 | NOT significant — the -0.0085 dip is noise |
| v3b vs v3c | 1:14 | 0.001 | SIGNIFICANT — v3c broke 14 items, fixed 1 |

The v3c regression is real (p=0.001, 15 discordant items). The v3b dip is not.
Two-seat review concern about n=50 power is answered in the negative for v3b
(correct: nothing there) and in the positive for v3c (the effect is large
enough that even n=50 resolves it).

Next: attribute WHICH 14 items broke (by reference-check type) to localize the
capability loss. That analysis is queued, not done.
