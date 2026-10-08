# coderepair-02: no reasoning policy recovers the gain, and the guard explanation is wrong

## Result (48 items x 3 families = 144 paired observations, power-checked at mde 0.25)

| policy | gain (mean over families) | fixed | broke | McNemar p | families positive |
|---|---|---|---|---|---|
| test-first | -0.028 | 19 | 23 | 0.644 | 1/3 |
| step-calc | -0.104 | 12 | 27 | 0.024 | 0/3 |
| spec-first | **-0.188** | 13 | 40 | 0.0003 | 0/3 |

Per family (direct → each policy):

| family | direct | step-calc | spec-first | test-first |
|---|---|---|---|---|
| qwen2.5:7b | 0.583 | 0.583 | 0.521 | 0.604 |
| qwen2.5-coder:7b | 0.583 | 0.583 | 0.333 | 0.583 |
| gemma3:4b | 0.667 | 0.354 | 0.417 | 0.563 |

**Verdict: STOP-REFUTED.**

## What this settles

coderepair-01 left two readings live: either the mechanism does not generalise,
or step-calc asks for the wrong intermediate step when writing code. This arm
tested the second by changing the policy and holding items, scorer, seed and
models fixed. Neither adaptation helped, so the second reading is refuted: **it is
not a policy-domain mismatch.** No reasoning-first policy tried here recovers a
gain on code repair.

The preregistered interaction prediction also failed, and it is the informative
failure. It predicted that a specification-explicit policy would help most on
guard-bearing classes, since missing guards was the diagnosed cause. Instead the
guard-minus-arithmetic interaction came out at -2, and on guard classes spec-first
still broke more items than it fixed (12 fixed / 28 broken). **Making the
requirement explicit did not make the model notice the requirement.**

## The one pattern worth keeping

The ordering is monotone in how much reasoning is demanded before the code:

    test-first (-0.028)  >  step-calc (-0.104)  >  spec-first (-0.188)

test-first asks only for the assertion the code violates; spec-first demands a
full specification restatement. On code repair, accuracy falls as the required
pre-answer reasoning grows, and the least intrusive variant is the only one whose
interval is compatible with zero. That is a dose-response, not a threshold, and
it is a defensible statement about this domain: writing code is a task where the
answer is the artifact, so intermediate prose is at best overhead and at worst a
source of commitments the model then fails to revise.

It is not a rescue of the arithmetic result. It is the shape of the boundary.

## For the paper

The scope statement gets sharper and simpler: the arithmetic gain does not
transfer to code repair under any reasoning-first policy tested, including two
designed for the domain, and the diagnosed cause of the code-repair failure
(missing guards) is not fixed by making the specification explicit. Section 5's
"policy-task matching" reading is withdrawn; what remains is a domain boundary
whose interior we have only begun to characterise.
