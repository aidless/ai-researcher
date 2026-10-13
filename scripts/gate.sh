#!/usr/bin/env bash
# One command = the five integrity steps .github/workflows/evidence-integrity.yml would run, plus
# the trust-root prerequisites. Why this exists: ai-researcher has no git remote and its
# .github/ was untracked until 2026-10-09, so GitHub Actions has NEVER executed that
# workflow -- the control was real code that had never once rung. This is the local rung.
#
#   bash scripts/gate.sh              run every step, exit 1 if any step fails
#   bash scripts/gate.sh --prove-red  run the mutation battery (control + 2 defects)
#
# Path note for this workspace: the repo root literally contains "F:" and ':' is the
# PYTHONPATH separator, so PYTHONPATH must stay the RELATIVE "src" or the value splits
# into "/...F" + "\deepseek/...". That is not a style choice here.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 9
export PYTHONPATH=src

fails=0
step() {   # step <name> <command...>
  local name="$1"; shift
  printf '\n--- %s ---\n' "$name"
  if "$@"; then printf '[PASS] %s\n' "$name"
  else printf '[FAIL] %s (rc=%s)\n' "$name" "$?"; fails=$((fails+1)); fi
}

contract() {
  python3 - <<'PY'
from ai_researcher.envelope import required_n
from ai_researcher.protocols import check_emits
import ai_researcher.keystore as KS
assert required_n(0.10) > 40, "power pre-check regressed"
for name in ("paired-transfer", "boundary-probe", "judge-agreement", "confound-audit"):
    assert not check_emits(name), f"{name} emit contract broken"
# trust root must be pinned, or every verdict below is unverifiable
assert KS.root_pub(KS.default_root_dir()), f"missing {KS.default_root_dir()/KS.ROOT_PUB}"
assert (KS.default_root_dir()/KS.LEGACY).exists(), f"missing {KS.LEGACY}"
print("contract + trust-root prerequisites ok")
PY
}

run_all() {
  step "unit tests"                 python3 -m pytest tests/ -q
  step "preregistration contract"   contract
  step "figure caption consistency" python3 demo/papers/figures/check_consistency.py
  step "evidence and gate sweep"    python3 scripts/verify_all.py
  # AIR-CODEREPAIR 那台定价尺的对表夹具：期望值抄自两份载体（demo/runs/coderepair-0{1,2}），
  # 有人改了汇总字段或逐题字节而没改判决时，这一格会红。变异电池另由 --prove-red 那五格负责。
  step "coderepair ruler calibration" python3 scripts/coderepair_escalation_verdict.py --selftest-only
  printf '\n=== gate: %s ===\n' "$([ "$fails" -eq 0 ] && echo 'all steps passed' || echo "$fails step(s) FAILED")"
  return $((fails > 0))
}

# ---------------------------------------------------------------- prove-red
# A gate that has never been shown to fail is a decoration (AGENTS.md rule 8). Each case
# prints the md5 of the file it touched before and after, because a mutation that never
# landed on disk explains nothing -- and the unmodified control runs first, so a battery
# that is itself broken cannot be read as "the gate works".
prove_red() {
  local base; base=$(mktemp -d /tmp/gate-proof-XXXXXX)
  # expand the path into the trap now: `local` is gone by the time EXIT runs, and an
  # unbound $base in the trap means the temp tree is never removed.
  trap "rm -rf '$base'" EXIT
  local rc=0
  cp -a . "$base/ctrl" 2>/dev/null || { echo "copy failed"; return 1; }

  echo "=== control: an untouched copy MUST stay green ==="
  ( cd "$base/ctrl" && PYTHONPATH=src python3 scripts/verify_all.py >/dev/null 2>&1 )
  if [ $? -eq 0 ]; then echo "  control green  [OK]"; else
    echo "  control RED -- the battery explains nothing, fix the harness first"; return 1; fi

  echo "=== case 1: pinned trust root removed (verification becomes impossible) ==="
  cp -a . "$base/c1" >/dev/null 2>&1
  local pub="$base/c1/keys/root_ed25519.pub"
  echo "  before md5: $(md5sum "$pub" | cut -d' ' -f1)"
  rm "$pub"
  echo "  after  md5: (file absent)"
  ( cd "$base/c1" && PYTHONPATH=src python3 scripts/verify_all.py >/dev/null 2>&1 )
  if [ $? -ne 0 ]; then echo "  gate went RED  [OK]"; else
    echo "  gate stayed GREEN with no trust root -- FAIL"; rc=1; fi

  echo "=== case 2: a signed round's envelope.json deleted (signature hidden, not broken) ==="
  cp -a . "$base/c2" >/dev/null 2>&1
  local ep="$base/c2/demo/runs/coderepair-01/round-01/envelope.json"
  echo "  before md5: $(md5sum "$ep" | cut -d' ' -f1)"
  rm "$ep"
  echo "  after  md5: (file absent)"
  ( cd "$base/c2" && PYTHONPATH=src python3 scripts/verify_all.py >/dev/null 2>&1 )
  if [ $? -ne 0 ]; then echo "  gate went RED  [OK]"; else
    echo "  gate stayed GREEN with a deleted signature -- FAIL"; rc=1; fi

  echo "=== case 3: artifact tampered and re-signed in place (the laundering path) ==="
  cp -a . "$base/c3" >/dev/null 2>&1
  ( cd "$base/c3" && PYTHONPATH=src python3 - <<'PY'
import json, pathlib
from ai_researcher import evidence as EV
wd = pathlib.Path("demo/runs/coderepair-01/round-01")
res = wd / "artifacts/result.json"
doc = json.loads(res.read_text()); doc["n_items"] = 40.5
res.write_text(json.dumps(doc, indent=1) + "\n")
priv, pub = EV.generate_keypair()
envl = EV.sign_round(wd / "artifacts", priv, "forger", "r01")
(wd / "envelope.json").write_text(json.dumps(envl, indent=1))
st = pathlib.Path("demo/runs/coderepair-01/state.json")
s = json.loads(st.read_text()); s["key_pub"] = pub.hex(); s["key_priv"] = priv.hex()
st.write_text(json.dumps(s, indent=1))
print("  tamper + re-sign + run-dir key rewrite applied")
PY
  )
  ( cd "$base/c3" && PYTHONPATH=src python3 scripts/verify_all.py >/dev/null 2>&1 )
  if [ $? -ne 0 ]; then echo "  gate went RED  [OK]"; else
    echo "  gate stayed GREEN after a laundered bundle -- FAIL"; rc=1; fi

  [ $rc -eq 0 ] && echo "prove-red: every injected defect was caught" \
                || echo "prove-red: AT LEAST ONE DEFECT SLIPPED"
  return $rc
}

case "${1:-}" in
  --prove-red) prove_red; exit $? ;;
  *) run_all; exit $? ;;
esac
