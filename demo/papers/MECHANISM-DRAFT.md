# When does reasoning before answering help? A mechanism proposal, with the evidence that constrains it

Draft, 2026-10-10. This is a hypothesis, not a result. It is written as a
hypothesis on purpose: every attempt in this project at a mechanism reading has
been tested and failed, most recently the headroom account, which was withdrawn
after Spearman correlation of +0.048 and -0.429 with a same-baseline
counterexample left it unable to distinguish two families at identical baselines
(-0.062 vs +0.444).

## The regularity, stated as a property of tasks rather than of models

Across the domains measured, whether reasoning-before-answering helps tracks
**whether the task has an intermediate representation that the final answer does
not already contain**.

- **Arithmetic word problems.** The answer is a number; the reasoning that
  produces it is a sequence of arithmetic operations, which is a real object the
  number does not contain. Naming it commits the model to intermediate results
  that a wrong final number would contradict. Effect: positive in every family
  and every wording tested (+0.23 to +0.65).
- **Code repair.** The answer IS the artifact. Reasoning has nowhere to live
  except in tokens that are not the answer, so committing to a prose defect
  description before writing code adds a statement that can be wrong without
  invalidating the code. Effect: negative in one family (-0.250, interval
  excluding zero), zero in two, monotonically worse with more demanded reasoning.

The formal claim:

> Let a be the answer and r an intermediate representation. Reasoning-first
> helps iff r is not already contained in a, and the task's checker can
> invalidate an inconsistency between r and a.

Concretely: a checker that can only see the answer cannot be helped by reasoning
that lives outside it; a checker that constrains both helps a great deal. This
is falsifiable in a way the headroom account was not.

## Three further constraints the existing data already impose

1. **Wording does not rescue a mismatched domain.** On code repair, spec-first
   (restate the whole specification including edge cases) is the WORST policy
   (-0.188), worse than step-calc (-0.104) and worse than test-first (-0.028).
   If reasoning-first were uniformly helpful, the specification-explicit variant
   would be the best one. It is the worst.
2. **Wording also does not rescue a domain where it helps.** On arithmetic all
   four tested wordings work, with gains ordered by how much reasoning they
   elicit (verbose +0.646 > terse +0.600 > canonical +0.396 > equations-only
   +0.233). The mechanism is therefore not "any reasoning text" but "reasoning
   that constrains the answer".
3. **Local GPU inference is not deterministic at temperature 0.** Between runs of
   identical items agreement ranged from 19/40 to 40/40, and the treatment arm
   moved more than the control in every pair measured. Mechanism claims built on
   single-run magnitudes are unfalsifiable at that noise floor; this one is built
   on direction and on monotone orderings, which survive the noise.

## What would falsify it

- A task where the answer ALREADY contains the intermediate representation (for
  instance, outputting a derivation with the final answer embedded) should show
  little or no effect even if it looks like arithmetic. That is a prediction,
  not a post hoc fit.
- A task where the checker sees both the answer and a separately produced
  reasoning field should show an effect LARGER than arithmetic, if the checker
  can be made to penalize inconsistency. That is the constructive direction.
- The dose-response should flip sign when the domain flips from
  answer-space-external to answer-space-internal, and it has already been
  observed to flip in the two domains measured.

## What is NOT claimed

No formal proof; the statement above is a compact description of an observed
regularity, not a theorem. No cross-checker experiment has been run. The
mechanism has the status of a newly proposed falsifiable hypothesis.
