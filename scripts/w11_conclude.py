#!/usr/bin/env python3
"""W11 收口驱动：判读通过后——状态机 已批→已跑→出结论 + writer 草稿。

与 w9_conclude.py 同纪律同机制（复用 w8_conclude 的 flip_state/_entries_of，
只借机制不借目标与文本）：
  - 只在 w11_critic_verdict.json 存在且 verdict ∈ {pass, insufficient} 时
    才动状态机；verdict=fail ⇒ 不迁移（先修实验或修主张）。
  - 迁移走 store.transition() 四道门；新对象回填列表 + report(entries) 重算。
  - 草稿由 writer.draft() 生成；verdict=insufficient 时 writer 按其预注册
    门拒**头条**稿、改出 negreport（这是正确行为，不是失败）。
  - 幂等安全：state 不是「已批」⇒ 拒绝。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ai-researcher", "src"))
import ai_researcher.store as st          # noqa: E402
import ai_researcher.writer as wr         # noqa: E402

TARGET_ID = "2107.03374v2"
ALLOWED_VERDICTS = ("pass", "insufficient")


def _w8_mod():
    p = os.path.join(ROOT, "ai-researcher", "scripts", "w8_conclude.py")
    spec = importlib.util.spec_from_file_location("w8_conclude", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def conclude(state_path: str, verdict_path: str, summary_path: str,
             items_path: str, drafts_dir: str | None = None) -> dict:
    wc = _w8_mod()
    wc.TARGET_ID = TARGET_ID                     # 只借机制，不借目标与文本
    try:
        verdict = wc.load_verdict(verdict_path)
    except FileNotFoundError as e:
        return {"ok": False, "why": str(e)}
    v = verdict.get("verdict")
    if v not in ALLOWED_VERDICTS:
        return {"ok": False, "why": f"verdict={v} 不在 {ALLOWED_VERDICTS}——"
                                    "判读没过就不迁移状态机"}
    claim = verdict.get("claim", "")
    if len(claim) < 30:
        return {"ok": False, "why": "verdict.claim 缺失或过短——结论必须从判读器来"}

    n_items = sum(1 for l in open(items_path, encoding="utf-8") if l.strip())
    log = os.path.join(ROOT, "ai-researcher", "store", "transitions.jsonl")
    actor = "agent_w11_conclude"        # 不要沿用 w8 的 actor 名——那会把
                                        # W11 的迁移标成 agent_w8_conclude
    by1 = wc.flip_state(state_path, "已批", "已跑",
                        f"W11 HumanEval pass@1 跑完：items={items_path}（{n_items} 行），"
                        f"判读 verdict={v}（重算门 + 分母完整性门 + 独立重跑门 + "
                        f"scope/caliber 门见 w11_critic_verdict.json）",
                        actor=actor, log_path=log)
    by2 = wc.flip_state(state_path, "已跑", "出结论", claim,
                        actor=actor, log_path=log)
    draft_path, why = wr.draft(TARGET_ID, summary_path, verdict_path,
                               state_path=state_path, drafts_dir=drafts_dir)
    if draft_path is None:
        return {"ok": False, "why": f"出结论后草稿被拒（按预注册规则）：{why}",
                "by_state": by2}
    return {"ok": True, "verdict": v, "by_state_after_run": by1,
            "by_state_final": by2, "draft": draft_path, "claim": claim}


def main() -> int:
    state = os.path.join(ROOT, "ai-researcher", "store", "proposals_state.json")
    out = conclude(
        state,
        os.path.join(ROOT, "ai-researcher", "store", "w11_critic_verdict.json"),
        os.path.join(ROOT, "ai-researcher", "store", "w11_humaneval_summary.json"),
        os.path.join(ROOT, "ai-researcher", "store", "w11_humaneval_items.jsonl"))
    print(json.dumps({k: v for k, v in out.items() if k != "claim"},
                     ensure_ascii=False, indent=2))
    return 0 if out.get("by_state_final") else 1


if __name__ == "__main__":
    sys.exit(main())