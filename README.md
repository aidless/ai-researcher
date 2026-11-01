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

## 证明什么 / 不证明什么

> 诚实性约束（fail-closed）：本仓证明的是**「信封（envelope）约束下的自主研究回路」是可执行、可验证、不可绕过的**；不证明任何具体研究结论。

**证明什么**

1. **契约先于执行**：`envelope.py` 的 `validate()` 会在循环启动前拒绝任何不完整的信封（缺 kill-switch 行、缺 required artifact、预算为 0 等）。没有 override 标志——卡住的运行只能换信封，不能绕过（`loop.py` 注释与设计规则）。
2. **证据链可验证**：每个 round 的 `evidence.py` 产出 Ed25519 签名 bundle（sha256 manifest → bundle id → 绑定信封）。`python -m ai_researcher.loop verify demo/runs/exp-01` 返回 `1 valid`——已提交的 demo 运行在**固定信任根**上可复验（见下方复算段）。
3. **两席分歧评分**：`two_seat.py` 报 `contradiction`（两席 verdict 不同或分差 ≥3），不报均值——单一 PASS 且无反对记录是弱信号。
4. **kill-switch 是结果判定**：demo 的 `gain=0.75` 命中 `gain>=0.5` → `STOP-EXTEND`；而两席评审因 n=4 判 `NOT_READY`。**循环测效果、席位测证据**，二者按设计分歧。

**不证明什么**

1. **不证明 demo 的研究结论**：demo 假设「lowercasing+trimming 提升 4 例精确匹配」是**演示用**的确定性玩具（`demo/exp-01/run_exp.py`），n=4 无统计意义；两席已正确判 `NOT_READY`（2/10、1/10）。
2. **不证明自主回路能产出可信论文**：本仓只证明回路**在其信封内正确执行**；研究质量取决于信封内容与模型，回路本身不评审科学价值。
3. **不证明免于伪造**：证据链是**可感知篡改**（sha256 哈希 + Ed25519 签名），不是防篡改加密存储；攻击者若控制签名私钥可伪造（`keystore.py` 设计如此）。
4. **不证明无需人工**：信封的 `approved_by` / `approved_at` 是唯一的人工授权点；回路不产生新授权。

## 复算（Reproduction）

README 中的数字都能从本仓落盘证据重算：

| 数字 | 从哪里重算 | 命令 |
|---|---|---|
| 57 个测试通过 | `tests/` 下 10 个 `test_*.py` | `python3 -m pytest -q`（先 `pip install cryptography`） |
| `gain=0.75, n=4` | `demo/exp-01/run_exp.py`（确定性，`CASES` 4 例） | `python3 demo/exp-01/run_exp.py` → `{"gain": 0.75}` |
| 信封绑定验证 | `demo/runs/exp-01/round-01/` 的签名 bundle | `PYTHONPATH=src python3 -m ai_researcher.loop verify demo/runs/exp-01` → `1 valid` |
| STOP-EXTEND 判定 | `state.json` 的 `kill_row` + `verdict` | 读取 `demo/runs/exp-01/state.json` |
| 两席 NOT_READY | `two_seat.py` 的评审逻辑（demo 输出） | 见 `demo/` 与 `two_seat.py` 单元测试 |

**验证脚本入口**：`.github/workflows/checks.yml`（CI 先装 `requirements.txt` 的 `cryptography`，再跑 pytest）。

> 数字一致性由 `tests/test_signing_power.py` / `tests/test_kill_binding.py` 守护：签名 bundle 必须在固定信任根上验证、kill-switch 判定必须匹配信封行。

## Design rules (no exceptions)

- No override flag. A stuck run gets a new envelope, not a bypass.
- A kill-switch row that cannot be evaluated cannot authorize continuation.
- A review that cannot say what would change its mind has not reviewed.
- `yaml.safe_load` passing is not enough; `actionlint` before every push.
- A green run means nothing until the gate earns it (mutation-control).
