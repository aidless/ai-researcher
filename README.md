# ai-researcher

[![CI](https://github.com/aidless/ai-researcher/actions/workflows/checks.yml/badge.svg)](https://github.com/aidless/ai-researcher/actions/workflows/checks.yml)

<!-- problem-statement -->
The loop guarantees that after one approval, each round is a budget check, a methods command, an Ed25519 bundle, a kill-switch row, and (on the last round) a recorded review, with no override flag.
It does not claim that a STOP verdict is a scientific result, that the methods command measured the hypothesis, or that two seats agreeing makes a claim true.
Discovery quality, venue acceptance, and external use are outside what a signature can show.
<!-- /problem-statement -->

STATUS: WORK-IN-PROGRESS — not A yet. The gap list is [STATUS.md](STATUS.md). A `STOP-*` label is a kill-switch outcome on `result.json`, not scientific acceptance. See [FAILURE_MODES.md](FAILURE_MODES.md).

`VERSION` is the control-loop revision (`0.1.0`). It matches `pyproject.toml`. The package is not published. There is no PyPI badge. The CI badge tracks [`.github/workflows/checks.yml`](.github/workflows/checks.yml) only.

## Offline path (no API key)

Fresh clone, no network beyond installing the declared dependencies:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest tests -q
python3 -m ai_researcher.offline_fixture
```

`offline_fixture` approves `fixtures/offline/envelope.json`, runs one synthetic methods command, signs the bundle, and loads both review seats from `fixtures/offline/review.json`. That file is stamped `fixture: true`. The command prints a `STOP-*` label and the sentence that the label is not scientific acceptance. `tests/test_public_contract.py` allows 120 seconds for the command. That timeout is the fresh-clone budget this revision claims, not a measured research runtime.

`demo/envelope.json` is a historical record. Its methods string points at one machine, and the file does not satisfy the current envelope contract (seed, power, tension). It is not the fresh-clone path.

## Live path (OpenRouter)

This path needs a network and a credential. The variable is named `SILICONFLOW_API_KEY` for a historical reason: an earlier client used that name (`llm.py` naming rule). The value is the credential for `LLM_API_URL`, not a guarantee that the host is SiliconFlow. The default URL is OpenRouter, so the value is an OpenRouter key unless you change the URL. A URL that contains `127.0.0.1`, `localhost`, or `::1` is treated as local and does not need the variable. Leave `AI_RESEARCHER_REVIEW_FIXTURE` unset. If it is set, the review is the canned file, even when a key is present.

```bash
python3 -m pip install -e ".[dev]"
export SILICONFLOW_API_KEY=...    # historical name; value is the LLM_API_URL credential
export LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
export REVIEW_MODEL=mistralai/mistral-large
python3 -m ai_researcher.keystore init
python3 -m ai_researcher.loop approve path/to/envelope.json --by "your-name"
python3 -m ai_researcher.loop run path/to/envelope.json --workdir runs/exp-01
python3 -m ai_researcher.loop status runs/exp-01
python3 -m ai_researcher.loop verify runs/exp-01
```

## What the four modules do

| Module | Role |
|---|---|
| `envelope.py` | The one human decision as a contract: hypothesis, exact methods command, budget, kill-switch rows, required artifacts, seed, power block, tension. `validate()` returns problems; the loop refuses to start on any. |
| `loop.py` | State machine with resume. No `--force`, no `--skip-gate`, no override flag. The last round is always sent to review, and every second round is too. A review error is recorded; it does not by itself change the kill-switch label. |
| `two_seat.py` | Two prompted seats (Methodology, Devil's Advocate) on one model endpoint. The module records disagreement. It does not stop the run. A fixture file is not a seat. |
| `evidence.py` | Per-round Ed25519 bundle: sha256 manifest, bundle id, signature. A round that does not verify is not counted. A valid signature means the artifact bytes still match. It does not mean the bytes are a finding. |

## Sisters

Separate repositories. This README does not restate their measurements.

| Repo | What that repository says it is |
|---|---|
| [ai-researcher-employee](https://github.com/aidless/ai-researcher-employee) | Skeleton v0.1, manager/worker split, three promotion gates, append-only Journal. Their `--fake` path is a wiring replay. |
| [autoresearcher](https://github.com/aidless/autoresearcher) | Per-segment statistical gate. Their `--dry-run` is offline. They describe the status as M1. |
| [agi-research](https://github.com/aidless/agi-research) | Archimedes, a five-year research log, not this tool. |
| [auto-research-driver](https://github.com/aidless/auto-research-driver) | An agent skill, not a library, for TMLR stages S1–S6. |

## CI

| Workflow | What a green run means here |
|---|---|
| `checks.yml` | `pytest tests` and `python -m ai_researcher.offline_fixture` on Python 3.10 and 3.12. No API key. |
| `evidence-integrity.yml` | `scripts/gate.sh` over historical bundles, plus a mutation check that the gate can go red. Not the offline fixture. The workflow's own summary says the judgment half is not run and green is not a venue verdict. |

## Design rules

- No override flag. A stuck run gets a new envelope, not a bypass.
- A kill-switch row that cannot be evaluated cannot authorize continuation when no earlier row already fired. See FAILURE_MODES.md for the case where an earlier row hides a broken one.
- A review that cannot say what would change its mind has not reviewed. The code records that weakness; it does not automatically downgrade `joint`.
- A green unit-test run is the test suite. It is not acceptance of a claim.
