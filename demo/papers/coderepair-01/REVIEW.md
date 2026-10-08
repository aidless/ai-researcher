# coderepair-01: the arithmetic gain does not transfer to code repair

## What was run

40 held-out code-repair items, four bug classes (off-by-one, None handling, type
coercion, missing guard), scored by executing each model's corrected function
against hidden test vectors. Direct versus step-calc (state the defect in one
line, then write the fix). No LLM judge, so no evaluator disagreement to
interpret. Preregistered kill-switch on `confirmed`.

## Result: STOP-REFUTED

| family | direct | step-calc | gain |
|---|---|---|---|
| qwen2.5:7b | 0.525 | 0.550 | +0.025 |
| qwen2.5-coder:7b | 0.525 | 0.525 | 0.000 |
| gemma3:4b | 0.625 | 0.375 | **-0.250** |
| ~~llama3.2:3b~~ | — | — | not installed; see correction |

Pooled paired McNemar over the three measured families: 12 fixed, 21 broken,
p = 0.163. Families positive: 1/3. Sign test p = 1.0. `confirmed = False`.

The preregistered localization prediction also failed: unhinted items moved 8
fixed / 11 broken, hinted items 4 fixed / 10 broken. The gap was not larger when
the defect had to be located.

## What this means for the paper

The central mechanism claim -- that the effect is about protocol design rather
than content, and should therefore follow the policy into any domain requiring a
defect to be found before answering -- **does not survive contact with code
repair.** On arithmetic the same policy gained +0.15 to +0.775 across eight
families; here it is flat in one family and negative in another, and it broke more
items than it fixed.

So the honest scope narrows. The paper may claim breadth across *models* on
*arithmetic*, and it may not claim domain-general protocol benefit. The second
sentence of the contribution has to go, or the paper has to argue that arithmetic
is a special case and say why -- which is a much larger claim than the evidence
supports.

This is the outcome the kill-switch was written for. It is also a result: a
protocol effect that reverses across domains is a sharper finding than one that
holds everywhere, provided the reversal is reported as such.

## Correction: one family was never measured

80 of 320 calls targeted `llama3.2:3b`, which is not installed locally (only
`llama3.2:1b` exists). Every call returned HTTP 404; the harness caught the
exception and scored it as a model failure, so that family reads 0.00/0.00. That
is an absent model read as a measured zero -- the sixth time this project has let
absence resolve as a value. `run_coderepair.py` now preflights `/api/tags`,
excludes absent tags before any measurement, prints and records the exclusion, and
`--selftest` asserts the preflight drops a nonexistent tag.

The signed bundle predates the fix and still verifies, because the artifact itself
is intact; the correction lives in the amendment.

## Failure-reason profile (all 160 measured calls per policy)

| reason | direct | step-calc |
|---|---|---|
| HTTP 404 (absent model, excluded above) | 40 | 40 |
| candidate raised on some vector | 32 | 23 |
| returned a value where the guard should return None | 18 | 17 |
| wrong value | 13 | 12 |

The dominant genuine failure is not arithmetic slips but **missing the guard
entirely**: models returned `0` or a stringified error where the item required
`None`. Reasoning about the defect first did not help them notice the requirement.

## Two-seat review

- methodology: the negative is well-powered enough to be believed at the family
  level (3 families, 120 paired items) but n=40 per family leaves the
  gemma3 reversal itself under-powered; the claim that should be written is
  "no reliable gain on code repair", not "harmful on code repair".
- devil: the arithmetic/code contrast is the most interesting thing in the paper
  and hiding it inside a limitations paragraph would be the actual failure. It
  should be a section.
