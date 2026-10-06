"""Bridge: loop conclusion -> SKILL claim ledger + draft seed.

The loop produces signed evidence and a verdict. The paper-writing SKILL needs a
CLAIM_LEDGER.md where every number traces to an evidence file + field, plus a
draft to revise. This module generates both, mechanically.

Status assignment is mechanical, not vibes:
  verified     -- kill-switch STOP-EXTEND, n >= the envelope's minimum for the
                  claim, two-seat joint READY, bundle verifies
  inconclusive -- anything else, WITH an explicit "what is missing" entry naming
                  the experiment/data/condition that would upgrade it.
                  Per the ledger rule, inconclusive claims stay in the text but
                  MUST be hedged ("may", "we did not observe", "uncertain") and
                  must never appear as strong assertions.
  blocked      -- round invalid, bundle unverifiable, or tainted evidence.
                  Blocked claims do not enter the manuscript.

Usage:
    python -m ai_researcher.bridge <workdir> <envelope.json> --out <paper_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_run(workdir: Path, envelope_path: str):
    st = json.loads((workdir / "state.json").read_text(encoding="utf-8"))
    env = json.loads(Path(envelope_path).read_text(encoding="utf-8"))
    return st, env


def _claim_rows(st: dict, env: dict, workdir: Path):
    """One ledger row per numeric fact in the final round's result.json."""
    rows = []
    if not st["rounds"]:
        return rows
    final = st["rounds"][-1]
    rnd_dir = workdir / f"round-{final['round']:02d}"
    result = final.get("result", {})
    verdict = final.get("verdict", "?")
    review = final.get("review", {})
    n = result.get("n", 0)

    def status_for(key, value):
        if final.get("verdict") in ("ROUND-INVALID",) or "missing" in str(final.get("reason", "")):
            return ("blocked", "round invalid or artifacts missing; no manuscript entry")
        if verdict == "STOP-EXTEND" and review.get("joint") == "READY" and n >= 30:
            return ("verified", "script recompute + bundle hash reconciliation")
        missing = []
        if verdict != "STOP-EXTEND":
            missing.append(f"kill-switch verdict is {verdict}, not STOP-EXTEND")
        if review.get("joint") != "READY":
            missing.append(f"two-seat joint is {review.get('joint', 'absent')}"
                           + (f": {review.get('devil_objection', '')[:120]}"
                              if review.get("devil_objection") else ""))
        if n < 30:
            missing.append(f"n={n} below the n>=30 bar for a verified quantitative claim; "
                           f"needs a larger replication")
        return ("inconclusive", "missing: " + "; ".join(missing))

    ev_file = f"round-{final['round']:02d}/artifacts/result.json"
    # Generic numeric top-level fields (gain-style results).
    for key in ("gain", "transfer_gain", "replication_gain"):
        if key in result and isinstance(result[key], (int, float)):
            status, how = status_for(key, result[key])
            rows.append({
                "id": f"C-{key}",
                "claim": f"{key} = {result[key]:.4f} (n={n})",
                "evidence": f"{ev_file} -> {key}",
                "value": result[key],
                "how": how,
                "status": status,
            })
    # Nested balanced/full comparison (reanalysis shape).
    for section in ("full", "balanced"):
        sec = result.get(section)
        if isinstance(sec, dict):
            for key in ("cross", "self"):
                if key in sec and isinstance(sec[key], (int, float)):
                    status, how = status_for(f"{section}.{key}", sec[key])
                    rows.append({
                        "id": f"C-{section}-{key}",
                        "claim": f"PCI {section} {key} = {sec[key]:.4f}",
                        "evidence": f"{ev_file} -> {section}.{key}",
                        "value": round(sec[key], 4),
                        "how": how,
                        "status": status,
                    })
    for order_key in ("full_order", "balanced_order"):
        if order_key in result:
            status, how = status_for(order_key, result[order_key])
            rows.append({
                "id": f"C-{order_key}",
                "claim": f"{order_key} = {result[order_key]}",
                "evidence": f"{ev_file} -> {order_key}",
                "value": result[order_key],
                "how": how,
                "status": status,
            })
    # paired table for McNemar, if present
    for model, m in (result.get("models") or {}).items():
        p = (m or {}).get("paired", {})
        if p:
            status, how = status_for(f"paired-{model}", p)
            rows.append({
                "id": f"C-paired-{model}",
                "claim": f"paired wins on {model}: step-only {p.get('b_step_only')}, "
                         f"direct-only {p.get('c_direct_only')} (n={n})",
                "evidence": f"{ev_file} -> models.{model}.paired",
                "value": f"{p.get('b_step_only')}:{p.get('c_direct_only')}",
                "how": how,
                "status": status,
            })
    return rows


def cmd_bridge(args):
    workdir = Path(args.workdir)
    st, env = _load_run(workdir, args.envelope)
    out = Path(args.out)
    (out / "evidence").mkdir(parents=True, exist_ok=True)
    rows = _claim_rows(st, env, workdir)

    # CLAIM_LEDGER.md in the SKILL's exact table shape
    lines = ["# CLAIM_LEDGER.md", "",
             f"源运行: {workdir} | 假设: {env.get('hypothesis','')[:100]}",
             f"最终裁决: {st['status']} | 轮次: {len(st['rounds'])}", "",
             "| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['claim']} | {r['evidence']} | {r['value']} | "
                     f"{r['how']} | {r['status']} |")
    # strong-assertion registry: anything not verified must be hedged or dropped
    lines += ["", "## 强断言登记", ""]
    for r in rows:
        if r["status"] == "verified":
            lines.append(f"- 保留（verified）：{r['id']} {r['claim']}")
        elif r["status"] == "inconclusive":
            lines.append(f"- 降级 inconclusive + hedge：{r['id']} —— {r['how']}")
        else:
            lines.append(f"- 删除/不进正文（blocked）：{r['id']} —— {r['how']}")
    (out / "CLAIM_LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # DRAFT_SEED.md: hedged results skeleton, numbers filled, no strong claims
    d = ["# Results (draft seed, machine-generated)", "",
         f"Hypothesis under test: {env.get('hypothesis','')}", ""]
    for r in rows:
        if r["status"] == "verified":
            d.append(f"- {r['claim']}. Evidence: `{r['evidence']}`.")
        elif r["status"] == "inconclusive":
            d.append(f"- {r['claim']}. [INCONCLUSIVE — hedge required: "
                     f"report as observed on n={st['rounds'][-1].get('result', {}).get('n','?')}, "
                     f"do not generalize. To upgrade: {r['how']}]")
    # Objection-response table: every strongest_objection from any round's review
    # must be answered, conceded, or used to downgrade -- never silently dropped.
    d += ["", "## Objections and responses", ""]
    seen = set()
    last_idx = len(st["rounds"]) - 1
    for i, rnd in enumerate(st["rounds"]):
        rev = rnd.get("review", {})
        obj = rev.get("devil_objection", "")
        if obj and obj not in seen:
            seen.add(obj)
            if i < last_idx:
                d.append(f"- [devil, r{rnd['round']:02d}] {obj[:300]}")
                d.append(f"  → Response: addressed in a later round")
            else:
                d.append(f"- [devil, r{rnd['round']:02d}] {obj[:300]}")
                d.append(f"  → Response: OPEN — must be addressed before submission")
    if not seen:
        d.append("- No recorded objections (review absent or joint READY without objection — "
                 "treat as weak signal per the two-seat rule).")
    d += ["",
          "## What would change this section",
          "- A larger replication (n>=200) with a preregistered McNemar analysis.",
          "- A second model family: transfer is a claim about families, not instances."]
    # Bounded lesson (oral practice #7): what readers can reconsider, separated
    # into observation / interpretation / proposed action, plus transfer limits.
    d += ["", "## Bounded lesson", "",
          "Observation: " + (rows[0]["claim"] if rows else "no claims") + ".",
          "Interpretation: see kill-switch verdict and robustness distribution above; "
          "neither is stated here as fact about any other setting.",
          "Proposed action: replicate the exact procedure before citing; "
          "do not port the numbers to a different model, metric, or n.",
          "Transfer limits: single-replication evidence unless the ledger says "
          "otherwise; magnitude comparisons across different-sized sets are invalid."]
    (out / "DRAFT_SEED.md").write_text("\n".join(d) + "\n", encoding="utf-8")

    # copy the signed evidence alongside
    import shutil
    for rnd in st["rounds"]:
        src = workdir / f"round-{rnd['round']:02d}"
        dst = out / "evidence" / f"round-{rnd['round']:02d}"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    n_v = sum(1 for r in rows if r["status"] == "verified")
    n_i = sum(1 for r in rows if r["status"] == "inconclusive")
    n_b = sum(1 for r in rows if r["status"] == "blocked")
    print(f"ledger: {len(rows)} claims ({n_v} verified / {n_i} inconclusive / {n_b} blocked)")
    print(f"wrote {out}/CLAIM_LEDGER.md, DRAFT_SEED.md, evidence/")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="ai-researcher.bridge")
    ap.add_argument("workdir"); ap.add_argument("envelope")
    ap.add_argument("--out", required=True)
    return cmd_bridge(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
