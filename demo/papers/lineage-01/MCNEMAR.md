# Lineage McNemar follow-up (per-item paired analysis)

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
