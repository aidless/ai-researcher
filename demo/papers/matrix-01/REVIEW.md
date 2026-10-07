# matrix-01 review and verdict

## Measured

| family | n | direct | step-calc | gain | fail->pass | pass->fail |
|---|---|---|---|---|---|---|
| qwen2.5:7b | 40 | 0.125 | 0.825 | +0.700 | 28 | 0 |
| llama3.1:8b | 40 | 0.025 | 0.400 | +0.375 | 15 | 0 |
| qwen2:7b | 40 | 0.025 | 0.450 | +0.425 | 18 | 1 |
| gemma3:4b | 40 | 0.025 | 0.800 | +0.775 | 31 | 0 |
| deepseek-r1:7b | 40 | 0.225 | 0.925 | +0.700 | 29 | 1 |
| qwen3:4b | 40 | 0.725 | 0.875 | +0.150 | 7 | 1 |
| qwen2.5-coder:7b | 40 | 0.300 | 0.900 | +0.600 | 24 | 0 |
| llama3.2:1b | 40 | 0.000 | 0.525 | +0.525 | 21 | 0 |

- 8/8 families positive. Sign test across families: p = 0.004.
- Pooled paired McNemar: 173:3, p = 1.9e-47.
- Gain tracks headroom, not size: qwen3:4b has the highest baseline (0.725) and the
  smallest gain (+0.150); llama3.2:1b has a zero baseline and gains +0.525.
- Span: 1B-8B, general / reasoning / coder families.

## Verdict: STOP-EXTEND (analyst-assigned, not preregistered)

The envelope's kill-switch required `confirmed`, a field the script never wrote.
`_eval_kill` swallowed the NameError and the run was filed as a clean
STOP-ROUNDS-EXHAUSTED. Recorded as an amendment; `loop.py` now fails closed
(STOP-KILL-UNEVALUABLE). The verdict above is therefore analyst-assigned from the
measured data and must be labelled as such wherever it is cited.

## Two-seat review: 7 / 3, joint NOT_READY

- methodology (7): n=40 per family is thin for a transferability claim, and the
  direct baselines span 0.000-0.725, so the set is not exchangeable across
  families.
- devil (3): the pooled McNemar p-value is "statistically suspect". This
  objection is wrong on its own terms -- pooling 8 families of paired items does
  not inflate significance, the test is exact, and the effect (173 flips vs 3)
  is not an artifact of n. But it names the real weakness: 40 items is one
  GSM8K-style set, so this is breadth across *models*, not across *tasks*.
- The honest claim: the effect replicates across every model family tested.
  Not: it replicates across task domains.

## Upgrade path (to make the breadth claim Zone1-defensible)

1. A second held-out set from a different task family (code repair or
   instruction following), same protocol, pre-registering `confirmed` this time.
2. Per-family CIs rather than a pooled test; report the sign test as primary.
3. Reframe the paper's breadth claim to "across model families on one task
   domain", which is what the data supports.