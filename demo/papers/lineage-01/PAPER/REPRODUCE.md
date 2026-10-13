# 可复现清单（REPRODUCE）

只列亲自验证存在的东西。路径全部是核对过的；没有"应该有"。
结论 → 表格 → 原始文件的链条，任何一段断了都算本清单作废，修清单不修结论。

## 证据三处（互不覆盖）

| 位置 | 内容 | 状态 |
|---|---|---|
| `demo/papers/lineage-01/evidence/round-01/artifacts/` | 原始轮：`out_*.jsonl`、`pred_*.jsonl`、`sum_*.json`、`result.json` | 一字未动 |
| `demo/runs/lineage-01-clean/round-01/` | 干净重跑：`artifacts/`（pred/out/sum/result＋`fixed/comparison.json`）、`amendment.json`、`model_digests.json`、`contamination_watch.jsonl` | 追加 only |
| `文档/Default Project/frozen/` | `test_50.jsonl`＋生产裁判 `prod_scorer_20261009.py`＋`frozen_manifest.json`（sha256 逐项） | /tmp 重启即丢的替代品 |

## 每个数字的重算命令

```bash
# 1. 原始 McNemar 1:14（10 秒）
python3 文档/Default\ Project/lineage01_confound_casestudy.py
# 断言：fixed=1 broken=14 p=0.0010 EXACT MATCH，否则脚本非 0 退出

# 2. 干净重跑裁决（需 artifacts 已有，不重跑模型）
python3 文档/Default\ Project/adjudicate_lineage_clean.py
# 注册判据 → STOP-REFUTED（只读 v3b/v3c 各 50）

# 3. 三口径对照（修正裁判）
python3 文档/Default\ Project/rescore_lineage_fixed.py
# → artifacts/fixed/comparison.json：−0.0234 / +0.0461 / −0.0784
# 补丁自检：python3 文档/Default\ Project/copilot_scorer_fixed.py --selftest

# 4. 双向证据（老规则删 10/0、新规则 0/0；测试 39→47）
cd 文档/Default\ Project/patches/scorer-runtime-guard && ./prove_red_differential.py
```

## 脚本索引（都在 `文档/Default Project/`，全部 `ls` 见过）

- `lineage01_confound_casestudy.py` — 原始轮复现＋机制分解（§1–§5 VERDICT 段已被另一会话按 A8 级更正过，复现断言仍 EXACT MATCH，exit 0）
- `adjudicate_lineage_clean.py` — 注册判据裁决（**没改**：换判据是本人决定；`broken_short` <300 地板仍在里面，与 ollama_guard"短≠错"冲突，见裁决文档 G2）
- `adjudicate_corrected.py` — 三口径对照
- `copilot_scorer_fixed.py` / `rescore_lineage_fixed.py` — 修正裁判＋全臂重算
- `arm_termination_census.py`、`judge_length_coupling_check.py`、`judge_coupling_corpus_scan.py`、`v3b_replication_check.py`、`paired_score_test.py`、`probe_ollama_health.py`、`lineage01_v3c_length_audit.py` — 专项审计
- `lineage_chunk.py`、`launch_clean_lineage.py`、`start_lineage_clean.sh`、`lineage_scheduled_run.py`、`watch_ollama.py` — 10-08 跑批工具链（含 4 块污染存证与 cron 记录，已停用；cron 条目已删）

## 已知不可复现项（写死，不许滑过去）

1. v1 五版本谱系：`copilot-3b-lora:latest` 不可加载（HTTP 500 tensor 维度），两次运行 50/50 HTTPError。任何"五版本"表述都是错的。
2. envelope 未签：`ai-researcher/proposals/envelopes/envelope_lineage-01_confound_audit.json` 的 `approved_by` 为空、`methods` 是 post-hoc 补的——引用时必须标注 exploratory，不能写"预注册"。
3. `gen()` 不送 seed：干净 v3b 与原始 v3b 仅 40/50 逐字节相同（5 项字符偏移处分叉）。跨轮逐项对比只认 id 级结论，不认逐字节。
4. 数据集与裁判曾经来自 `/tmp/ind-audit` 外部 checkout：现用 `frozen/` 副本（sha256 见 manifest；且已用冻结副本重算原始 v3c 全 50 项，与 live 输出逐条相同）。
