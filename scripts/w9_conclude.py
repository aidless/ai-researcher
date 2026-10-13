#!/usr/bin/env python3
"""W9 收口驱动：判读通过后——状态机 已批→已跑→出结论 + writer 草稿。

与 w8_conclude.py 同纪律同机制（复用其 flip_state/_entries_of），只换目标
提案与理由文本：

  - 只在 w9_critic_verdict.json 存在且 verdict ∈ {pass, insufficient} 时
    才动状态机；verdict=fail ⇒ 不迁移（先修实验或修主张）。
  - 迁移走 ai_researcher.store.transition() 四道门，新对象回填列表 +
    report(entries) 重算，整文件自洽落盘。
  - 草稿由 writer.draft() 生成；verdict=insufficient 时 writer 按其预注册
    claim_lint 拒稿——这是**正确行为**（L-ops-159），不是失败：负结果完整
    落账、不自动升格为论文草稿头条。
  - 幂等安全：状态不是「已批」⇒ 拒绝。
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

TARGET_ID = "2312.11361v3"
ALLOWED_VERDICTS = ("pass", "insufficient")


def _w8_mod():
    """按文件路径装入 w8_conclude（scripts/ 不是包，不能裸 import）。"""
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

    by1 = wc.flip_state(state_path, "已批", "已跑",
                        f"W9 多语相关性判定跑完：items={items_path}"
                        "（3 语×2 子集×30=180 条），判读 verdict=%s（重算门 + "
                        "verdict 一致性门 + scope/caliber 门见 "
                        "w9_critic_verdict.json）" % v)
    by2 = wc.flip_state(state_path, "已跑", "出结论", claim)
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
        os.path.join(ROOT, "ai-researcher", "store", "w9_critic_verdict.json"),
        os.path.join(ROOT, "ai-researcher", "store", "w9_summary.json"),
        os.path.join(ROOT, "ai-researcher", "store", "w9_items.jsonl"))
    print(json.dumps({k: v for k, v in out.items() if k != "claim"},
                     ensure_ascii=False, indent=2))
    # by_state 落地即算收口成功；草稿被拒是设计行为，报明即可
    return 0 if out.get("by_state") else 1


if __name__ == "__main__":
    sys.exit(main())
