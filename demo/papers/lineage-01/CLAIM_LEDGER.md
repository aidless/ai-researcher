# CLAIM_LEDGER.md

源运行: demo/runs/lineage-01 | 假设: capability on the 50-item copilot eval is non-monotonic across copilot-3b-lora v1..v3c (some checkpo
最终裁决: STOP-EXTEND | 轮次: 1

| ID | 声明（章节） | 证据文件+字段 | 数值 | 如何验证 | 状态 |
|---|---|---|---|---|---|
| C-rates-v2 | rates.v2 = 0.6759 (n=0) | round-01/artifacts/result.json -> rates.v2 | 0.6759 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3 | rates.v3 = 0.7326 (n=0) | round-01/artifacts/result.json -> rates.v3 | 0.7326 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3b | rates.v3b = 0.7241 (n=0) | round-01/artifacts/result.json -> rates.v3b | 0.7241 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-rates-v3c | rates.v3c = 0.7083 (n=0) | round-01/artifacts/result.json -> rates.v3c | 0.7083 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-regressions[0]-drop | regressions[0].drop = 0.0085 (n=0) | round-01/artifacts/result.json -> regressions[0].drop | 0.0085 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |
| C-regressions[1]-drop | regressions[1].drop = 0.0158 (n=0) | round-01/artifacts/result.json -> regressions[1].drop | 0.0158 | missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication | inconclusive |

## 强断言登记

- 降级 inconclusive + hedge：C-rates-v2 —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3 —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3b —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-rates-v3c —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-regressions[0]-drop —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication
- 降级 inconclusive + hedge：C-regressions[1]-drop —— missing: two-seat joint is absent; n=0 below the n>=30 bar for a verified quantitative claim; needs a larger replication

---

## 人工补记 2026-10-09（本文件由工具生成，此处只做覆盖声明，不改上面表格）

- 顶部 `最终裁决: STOP-EXTEND` 已被覆盖。干净复跑（v3b+v3c 各 50 项、全程持
  `/tmp/ollama_guard.lock`、121 次监控轮询 0 竞争进程）按注册判据给出 **STOP-REFUTED**。
  本行上方的表格仍指向 `demo/runs/lineage-01/round-01/artifacts/result.json`，那个文件没动。
- 上面四条 `C-rates-*` 与两条 `C-regressions-*` 现在多了一个已知缺陷：它们的分母是
  scorer 剔除后的子集（v3b 45、v3c 32），而 v3c 被剔的 10 项是 `classify_runtime` 按
  「短答案 + 含 timeout 字样」删掉的 `failure_diagnosis` 题。修正裁判后三口径并列
  （同一批干净数据，`adjudicate_corrected.py`）：published **−0.0234**；
  只算答了的项 **v3c 0.7778 vs v3b 0.7317 = +0.0461**（配对 Wilcoxon W=0、精确 p=0.03125，scipy 同值）；
  不终止记 0 分 **v3c 0.6533 vs v3b 0.7317 = −0.0784**。
  结论：**能力没有退化（v3c 答出来的反而更好），可用性问题是真的（8/50 不终止）**；
  published 那个数同时朝两个方向错——既造出了不存在的能力损失，又抹掉了真实的可用性损失。
  v2 同病：published 0.6759(n=36) → 答了即算 0.7222(n=42) → 不终止记零 0.6067。
  *（本条早先写的「0.7367 / 变 +0.0050」是错的：它把空正文按负面检查的默认通过给了半分。见 amendment A6。）*
- `n=0` 那栏另有一处需要读对：v1 从未产生过任何模型输出（两次运行都是 50/50 HTTPError，
  构件自 2026-08-08 起未变且不可加载），所以"五版本谱系"的说法不成立，实际只有四个版本被测过。
- 载体：`demo/runs/lineage-01-clean/round-01/amendment.json`（A1–A5、G1–G9）、
  `model_digests.json`、工作区 `arm_termination_census.py` / `judge_length_coupling_check.py` /
  `judge_coupling_corpus_scan.py` / `v3b_replication_check.py`。
