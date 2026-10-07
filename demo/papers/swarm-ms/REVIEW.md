# Two-seat review: multi-seed swarm excess (4/5 seeds positive)

- methodology: 5/10 NOT_READY — 6 rounds + 4 tasks insufficient for a generalizable trend; task-specificity risk unaddressed.
- devil: 3/10 NOT_READY — confound: abstentions skip updates, so swarm-size interacts with the abstention mechanism itself, not just bias. Larger swarms have more judge calls and more abstention opportunities; the slope gap may reflect mechanism interaction rather than bias amplification.
- joint: NOT_READY

## What this means

The 4/5 replication upgrades the finding from suggestive to robust-pilot, but
NOT to verified: (1) scale is small (6 rounds, 4 tasks); (2) the devil's
abstention-confound is real and unaddressed — the fix is to log abstention
rates per arm and re-analyze, or force-decide ties in a follow-up arm.
Next: 8/16/32 subagents ONLY after the confound is measured, or the scaling
curve will inherit it.
