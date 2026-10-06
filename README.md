# ai-researcher — autonomous research loop with a signed evidence chain

A fully automatic AI researcher does not mean "no human ever". It means the human
decides **once**, up front, inside a machine-checkable contract — and the machine
then runs unattended inside that contract. Anything outside it stops the run
without asking.

```
human approves envelope ONCE
        │
        ▼
┌─ loop.py ─────────────────────────────┐
│ each round:                           │
│  budget? → run methods → artifacts? → │
│  sign bundle → kill-switch? →         │
│  every 2nd round: two-seat review     │
└───────────────────────────────────────┘
        │
        ▼
signed bundles + verdict (STOP-EXTEND / STOP-REFUTED / …)
```

## The four pieces

| File | What it is | Where the idea comes from |
|---|---|---|
| `envelope.py` | Preregistration as an executable contract: hypothesis, exact methods command, budget caps, kill-switch rows, required artifacts, and the approver's name. `validate()` returns problems; the loop refuses to start on any. | The H10 kill-switch decision rule (pre-registered, mutually exclusive outcome rows) |
| `loop.py` | Autonomous executor. State machine with resume. No `--force`, no `--skip-gate`, no override flag — a run that cannot proceed inside its envelope is a run that should not proceed. | `auto-research-driver`'s S1–S6 state machine, minus the five human checkpoints, plus teeth |
| `two_seat.py` | Methodology vs Devil's Advocate, via the account's OpenRouter chain (`mistralai/mistral-large`, a different family from the main model). Scores the *disagreement*, not the average. A unanimous PASS with no recorded objection is a weak signal. | The two-seat ARS review that caught real problems in a paper draft |
| `evidence.py` | Per-round Ed25519-signed bundle: sha256 manifest of every artifact, bundle id from the manifest hash, envelope binding. A round that does not verify is not a round. | `gsm8k-self-evolve`'s evidence chain, generalized |

## Why two seats, not one or five

One seat confirms. It takes a second seat, instructed to disagree, to falsify.
The module reports `contradiction` (verdicts differ, or scores differ by ≥3)
separately from `joint` (either seat says NOT_READY → NOT_READY). Majority vote
over five seats would drown the one correct objection; contradiction-seeking
keeps it.

## Quick start

```bash
pip install cryptography   # only third-party dependency
export SILICONFLOW_API_KEY=<your OpenRouter key>   # named by the llm.py rule
export REVIEW_MODEL=mistralai/mistral-large
export LLM_API_URL=https://openrouter.ai/api/v1/chat/completions

# 1. write an envelope (see demo/envelope.json), then approve it — the one human act
python -m ai_researcher.loop approve demo/envelope.json --by "your-name"

# 2. run unattended
python -m ai_researcher.loop run demo/envelope.json --workdir demo/runs/exp-01

# 3. inspect and re-verify
python -m ai_researcher.loop status demo/runs/exp-01
python -m ai_researcher.loop verify demo/runs/exp-01
```

The demo hypothesis ("lowercasing+trimming improves exact-match", gain 0.75 on
n=4) ends `STOP-EXTEND` after one round with a valid signed bundle — and the
two-seat review correctly calls it `NOT_READY` (2/10 and 1/10), because n=4 is
meaningless. The loop and the review disagree the way they should: the
kill-switch measures the *effect*, the seats measure the *evidence*.

## Design rules (no exceptions)

- No override flag. A stuck run gets a new envelope, not a bypass.
- A kill-switch row that cannot be evaluated cannot authorize continuation.
- A review that cannot say what would change its mind has not reviewed.
- `yaml.safe_load` passing is not enough; `actionlint` before every push.
- A green run means nothing until the gate earns it (mutation-control).
