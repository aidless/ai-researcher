# sweetspot-04: the inference-length sweet spot does not exist at this scale

## What was preregistered

sweetspot-03 saw a flat-then-cliff shape in the code family across reasoning caps
(0.833, 0.833, 0.333) and both seats refused it at n = 6 per family as
indistinguishable from noise. This arm re-ran the comparison on 48 code-repair
items (the selftest-covered bank, used whole rather than subsampled) at caps
150 / 400 / 1000, two models, 96 paired observations per cap against the n = 63 a
power calculation requires for a 0.25 effect. Kill-switch: cliff confirmed ->
STOP-EXTEND, not confirmed -> STOP-REFUTED.

## Result: STOP-REFUTED. No cliff, in either direction.

| model | cap 150 | cap 400 | cap 1000 | cap400 fixed | cap1000 broke | McNemar p |
|---|---|---|---|---|---|---|
| qwen2.5:7b | 0.583 | 0.583 | 0.583 | 0 | 0 | 1.000 |
| deepseek-r1:7b | 0.000 | 0.083 | 0.271 | 9 | 0 | 0.0039 |

Pooled: 9 fixed, 0 broken, p = 0.0039 -- but in the **opposite** direction from the
hypothesis. Families where cap 1000 was worse than cap 400: **0 of 2**.
`cliff_confirmed = False`. Truncations: zero in every cell, so the budget was
actually delivered rather than clipped.

## The two behaviours are different, and that is the finding

- **qwen2.5:7b is flat.** Identical accuracy at 150, 400 and 1000 tokens. Its code
  fixes are short enough that the budget is not the binding constraint.
- **deepseek-r1:7b is monotonically increasing.** 0.000 -> 0.083 -> 0.271. More
  budget strictly helps, and at cap 150 it cannot complete a fix at all. What
  looked like a cliff in sweetspot-03 was a low-budget artifact of a different item
  set: at 150 tokens this model simply fails to finish.

So there is no sweet spot to find. There is a family whose budget requirement is
below the smallest cap tested, and a family for which more is monotonically better
over the range tested.

## Positioning against the nearest prior work

Thoughtology (Marjanovic et al., TMLR 2026, arXiv:2504.07128) reports that
DeepSeek-R1 has "a 'sweet spot' of reasoning, where extra inference time can impair
model performance". That is on the full 671B model, whose thinking budget is
controlled internally.

This arm does not contradict that, and it does not support it at small scale: on a
7B reasoning distill the budget response is monotone increasing over 150-1000
tokens, and on a 7B non-reasoning model it is flat. The honest statement is that
the sweet-spot phenomenon is not reproduced on local 7B models, and that whether
it appears at all appears to depend on scale and on whether the model is a
reasoning distill. Confirming or refuting the frontier claim is out of scope here
and would need the frontier model.

## What this retires

- The sweet-spot claim is dropped from the paper entirely. It was never in the
  current title, and after this it should not appear as a finding.
- sweetspot-03's shape is recorded as what it was: a floor/ceiling artifact of six
  items, which is exactly what two-seat review said at the time.
- The budget arm is the clearest case in the project of a suggestive pattern that
  did not survive an adequately powered test, and it is reported as such rather
  than quietly dropped.
