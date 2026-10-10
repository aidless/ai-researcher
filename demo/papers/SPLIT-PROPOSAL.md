# Splitting the project: two papers, or one?

Draft, 2026-10-10. The review's recommendation, evaluated against what the
evidence can actually support rather than against what a top venue prefers.

## Option A: split (as the review recommends)

**Paper 1 - the empirical claim.** "A prospectively confirmed arithmetic effect
of step-by-step prompting in local models, with null results outside arithmetic."
Content: the confirmatory family (3 endpoints), the boundary conditions (code
repair, inference budget, amplification), the prompt ablation, the cross-dataset
arm when it lands. Statistical core: cluster-robust intervals, per-family exact
tests, project-level BH over the confirmatory family.

Strength: one claim, tight, defensible, reviewer-legible in twenty minutes.
Weakness: it is a negative-result-heavy paper about a positive result that
several existing works already suggest (self-consistency, CoT, Thoughtology).
Novelty is the confirmation discipline plus the domain boundary - both real, both
modest.

**Paper 2 - the machine.** "An autonomous research loop with preregistration,
signed evidence, and project-level multiplicity control." Content: the envelope
contract, the power gate, config binding, stop-on-unmeasurable, the proposal
loop, the CI sweep, and the catalogue of nine supervision failures that each
produced a clean-looking false state and were each converted into a fail-closed
invariant. That catalogue is the method contribution: not "we built automation"
but "here are the specific ways automation lies, what each looked like, and the
invariant that now prevents it."

Strength: genuinely novel, immediately useful to anyone building research
automation, and it requires no new experiments - the evidence is already signed.
Weakness: none of it has been evaluated outside this project. It needs an
external evaluation or, at minimum, an artifact others can run.

## Option B: one paper

Keep the current manuscript. Its form is honest, and the cross-dataset arm plus
the prompt ablation strengthen it, but neither changes its shape, which the
review correctly identifies as an audit log.

## Recommendation

Split, but not equally, and not yet.

- Paper 2's material is complete, signed, and novel. Its weakness (no external
  evaluation) can be addressed by releasing the artifact and asking for
  reproduction, which can start immediately and does not wait on GPU.
- Paper 1 is NOT finished: the cross-dataset arm is queued, and a reviewer of the
  arithmetic claim will ask about at least one more independent source.
  Splitting it now means writing it twice.
- The mechanism draft gives both papers a shared Discussion without new
  experiments, and gives Paper 1 an answer to "why does this happen" that is not
  the withdrawn headroom account.

Sequence: finish the cross-dataset arm, then write Paper 1. Publish Paper 2
independently, since its claim does not depend on the arithmetic result at all -
which is the argument for two papers rather than one that mentions both.
