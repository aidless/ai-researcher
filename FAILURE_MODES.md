# Failure modes

A signed bundle and a `STOP-*` label can still be false progress. A two-seat record can still be a false green. An envelope can still be written so that the contract is satisfied without the measurement the hypothesis names. None of these labels is scientific acceptance.

The notes below describe this tree as it is. They are limits of the control loop, not a procedure for attacking someone else's run.

## Signed chain, false progress

The signature in `evidence.py` covers the artifact bytes and a best-effort environment snapshot. It does not check that `result.json` measures the hypothesis. `loop.py` runs `methods` as a shell command with the round directory as cwd. That command may write any JSON. The offline fixture does this on purpose and marks the file `synthetic_fixture: true`. A methods command that omits the mark looks the same to the signature.

`expect` is optional. Without it, a bundle from a different experiment still verifies if the files hash. The loop comments record that this happened (`breadth-02`): the methods string selected the wrong input, the bundle signed, and a kill-switch row fired.

`measurable: false` stops the run only when no kill-switch row's condition, action, or note contains the substring `measurable` or `abstention`. A row that mentions the word and then matches a numeric field still produces a `STOP-*` label.

Kill-switch evaluation walks rows in order and returns on the first match. Unevaluable rows force `STOP-KILL-UNEVALUABLE` only when the matched action would otherwise be `CONTINUE`. An early, easy match hides later rows that never ran.

`verify_round` returns `valid: true` when the signature matches and the environment snapshot has drifted. The reason string says so. A caller that reads only `valid` treats drift as success.

The trust root (`keys/root_ed25519.pub`, `keys/registry.jsonl`) lives in the repo, and the signer appends to the same registry the verifier reads. `keystore.py` states the remaining limit: write access to those files can rotate the pinned key and append a line. That is a higher bar than editing one run directory. It is not a hardware root of trust. The private key is outside the repo by default (`AI_RESEARCHER_ROOT_KEY` or the user config path). Whoever can set that variable can sign as the root.

`collect_environment` records an ollama digest of `unknown` when it cannot ask ollama. Two machines that both failed the lookup look alike.

## Two-seat false greens

Both seats are one model, one endpoint, and two prompts (`two_seat.review`). Disagreement is requested in the prompt. It is not a second implementation.

`family_of` takes the text before the first `/`. `google/gemma3:4b` compared with `gemma3:4b` is reported as cross-family. `tests/test_review_backend.py` pins that behavior so it stays visible.

A review exception is stored as `review.error`. The kill-switch label is still written. `STOP-EXTEND` with a missing review is a legal state of the loop.

`joint` is `READY` when neither seat says `NOT_READY`. An empty objection does not downgrade it. The module text calls a unanimous pass with no objection a weak signal. The loop stores `joint` and continues. `NOT_READY` does not stop the run either, so a `STOP-*` label and a `NOT_READY` review can sit on the same round. `status` alone hides the review.

`AI_RESEARCHER_REVIEW_FIXTURE` replaces both seats with a JSON file. The result is stamped `fixture: true`, and `verify` prints that a fixture is not a two-seat verdict. If the variable is left set during a live run, the file is the review. The signature does not look at the variable. A reader who ignores `review.fixture` can treat the canned seats as a model.

`_resolve_backend` treats a URL as local when it contains `127.0.0.1`, `localhost`, or `::1`, and then does not require `SILICONFLOW_API_KEY`. The check is a substring test, not a parsed host.

Scores are not clamped before the disagreement arithmetic. A seat that returns a non-numeric score raises. A seat that returns a number outside 0–10 is stored as given.

## Envelope gaming

`approve --by` writes a string and a timestamp. There is no second person and no signature on the approval.

`seed` must be non-zero or `validate` refuses. The loop does not export `EVO_SEED` into the methods process. A command that ignores the field still satisfies the contract.

The power block can be satisfied by declaring a larger `min_detectable_effect`, or by an endpoint string that contains `sign test`, which uses a different minimum `n`. `power.n` is not compared to `result.json`'s `n`. The offline fixture sets both to 120 so this file does not demonstrate that hole. The hole remains for every other envelope.

`max_cost_usd` of `0` disables the budget check (`cost > cap and cap > 0`). A zero cap is not "no spend allowed". Unknown spend (`cost_usd` absent) does not move the meter, so a command that never reports cost cannot trip the budget.

`max_rounds: 1` plus a row that matches the file the command writes ends the run in one round with a signed bundle. That is a finished state machine. It is not evidence that the hypothesis was tested.

Kill conditions are evaluated as Python expressions over numeric fields in the result. The approver chooses the expression. The loop cannot tell a threshold that was registered before the data from a threshold written to match a script the approver already ran.

`demo/envelope.json` is still in the tree. Re-approving it fails the current validator, and its methods path is one workstation. The README does not use it as the fresh-clone path.

## What a STOP label is

`STOP-EXTEND`, `STOP-REFUTED`, `STOP-REFUTED-REVERSE`, `STOP-INCONCLUSIVE`, `STOP-BUDGET`, `STOP-TIME`, `STOP-INVALID`, `STOP-KILL-UNEVALUABLE`, `STOP-UNMEASURABLE`, `STOP-CONFIG-MISMATCH`, `STOP-CONFIG-UNBOUND`, and `STOP-ROUNDS-EXHAUSTED` are labels the state machine writes. They are not scientific acceptance, rejection, or peer review. The offline fixture's label is one of these, on a synthetic file, with a fixture review.
