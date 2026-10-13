# 批准记录（APPROVAL_RECORD）— verbatim

> Purpose: the signature block's qualifier says "in-session verbal approval,
> recorded by agent". This file holds the verbatim text and the exact
> sequence, so the claim can be checked rather than believed.

## Verbatim

> 用户原话（opencode session，2026-10-11）：
> **"我同意了 你帮我签名 刘泽文 2026.10.11"**

## Sequence (all timestamps CST, 2026-10-11)

| time | event |
|---|---|
| 15:13 | current session clock when the approval arrived |
| 15:13 | approval received (verbatim above) |
| 15:13 | `PREREG.md` §4 bank sha256 + §8 signature block filled by agent; qualifier added by agent |
| 15:13 | this file written |
| after | §7b pre-launch checks (bank human spot-check, artifact loadability, machine exclusivity) |
| after | first data row (if any) |

**Before the first data row**: approval recorded, sha pinned, session
timestamped. That ordering is the property this round was built for.

## What was approved

Per the message: the PREREG as a whole — which SIGNING_BRIEF.md reduced to
three items (primary estimand + conventions; three secondary estimands;
five kill-switch branches). No partial or conditional approval was stated.

## Known limitations of this approval form

1. Not a hand signature. Accountability rests on the session log plus this
   file, not on a signature that survives dispute.
2. The 150-item bank was machine-validated (format zero failures) and
   sha-pinned; human spot-check is a §7b pre-launch step, performed by the
   executor AFTER this approval — it is listed, not claimed done.
3. If this round ever reaches a venue, the approval form must be described
   as "verbal, recorded in-session", never as "hand-signed" or "pre-registered
   and approved" without that qualifier.
