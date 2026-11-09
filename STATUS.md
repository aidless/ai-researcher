# STATUS

STATUS: WORK-IN-PROGRESS — not A yet

This revision can show the evidence checklist from a fresh clone. It does not award itself grade A.

## Met in this tree

1. The README problem statement is three lines. It says what the loop checks and what it does not claim about discovery quality.
2. `python3 -m ai_researcher.offline_fixture` and `python3 -m pytest tests -q` need no API key. `.github/workflows/checks.yml` runs both on Python 3.10 and 3.12. `.github/workflows/evidence-integrity.yml` is the historical-bundle sweep (`scripts/gate.sh`), not the offline path.
3. There is no PyPI badge and no PyPI release. `SILICONFLOW_API_KEY` is documented as a historical name whose value is the `LLM_API_URL` credential. Sister lines follow those repositories' own descriptions. This repo does not restate their numbers.
4. `FAILURE_MODES.md` records signed-chain false progress, two-seat false greens, and envelope gaming, and says a STOP label is not scientific acceptance.
5. README commands match the package: `pip install -e ".[dev]"`, then `python3 -m ai_researcher.loop` and `python3 -m ai_researcher.offline_fixture`. `tests/test_public_contract.py` fails if that drifts, and it checks that a tampered artifact fails signature verify.
6. The offline path is approve, one synthetic round, and verify. The contract test's timeout is 120 seconds. That is a test bound, not a published timing result.

## Gaps

- Uniqueness against the arx-theme sisters is unresolved. This tree is the one-shot envelope, the kill-switch executor, and the Ed25519 bundle. `autoresearcher` is the per-segment statistical gate and `ai-researcher-employee` is the manager/worker skeleton. Both describe the same research-loop family. Nothing here is a distinct empirical finding, and this revision does not invent one.
- CI never calls the live two-seat endpoint. The only review the offline job runs is `fixtures/offline/review.json`. A green check is not a model disagreement.
- Historical files under `demo/`, `store/`, `reports/`, and some one-off scripts still contain one workstation's absolute paths. They were not rewritten, because many of them are evidence bytes. They are not the fresh-clone entry. `src/ai_researcher/canonical.py` no longer embeds that path. A checkout whose directory name contains a single backslash still needs `EVO_REPO_ROOT`.
- There are no external users and no venue acceptance to report. `VERSION` is `0.1.0`, the first numbered revision of this control loop. It is not a paper version.
