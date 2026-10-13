# Manuscript 大纲（OUTLINE）

> 从裁决文档起草，不是机器模板。每个数字后面跟载体；没有载体的句子不许进正文。
> 2026-10-09 锁定（G3(b) 收窄）；2026-10-10 修订：G2 关闭（STOP-EXTEND full），§5 恢复；G1 由“不并”改“已合并”（commit `cad68c7` 本地，push 待定）。
> 修订由本人指令“全做”触发；标题与 venue 不变。
> 2026-10-10 Major Revision（两轮最高标准审稿）：MANUSCRIPT_draft_v1.md 已按
> 审稿重写——标题换方向、三轴术语、端到端为主分析、敏感性进正文。
> 本 OUTLINE 的旧表述（"能力没退化"无条件句、G2(b) 版§5缺席）以 v1 稿和
> REVIEW_RESPONSE_v1.md 为准，不再逐行改历史。
> 下面是锁定后的版本，不再有备用方案。

## 标题（已定，不再候选）

《The Judge Deleted the Correct Answers: A Text-Pattern Grading Bug in Failure-Diagnosis Tasks That Manufactured a Capability Regression》

## 摘要骨架（100–150 词，数字先行）

- 背景一句：checkpoint 谱系 v3b→v3c 的 published 回归 −0.0234（McNemar 1:14、p=0.001）。
- 反转一句：干净重跑＋修正裁判后，只算答了的项 v3c 0.7778 vs v3b 0.7317（+0.0461，Wilcoxon 精确 p=0.03125）——能力没退化。
- 真缺陷一句：v3c 8/50 不终止，三腿表征完成（L1 40/40 顶格、L2 40/40 stop、L3a/b/c 8/8 length 且三腿输出逐字节相同）——可用性轴，能力轴之外。
- 机制一句：生产裁判 `classify_runtime` 按"<200 字符＋含 timeout 字样"删除运行时错误，而被删的 c021–c030 恰是题干自带该字样的 `failure_diagnosis` 题；2026-07 修过一次，8 月模型重建后过期（无回归测试）。
- 边界一句：单任务族证据（16 项全 failure_diagnosis）；补丁包＋双向证据＋测试 39→47。

## 节结构

### 1. 引言（0.5 页）
- 钩子：一个 p=0.001 的显著回归，撤回后发现两头同时错（C5）。
- 范围句（第一段末尾必须有）：本文两条腿——裁判 bug（C3＋C4）与可用性缺陷（C2，§5）；v3c 8/50 不终止已表征，不再是观测。
- 不许写：任何"v3c 能力退化"的肯定句（C1 DEAD）。

### 2. 背景与谱系（0.5 页）
- copilot-3b-lora v1..v3c，50 项 copilot eval；v1 从未产生输出（构件不可加载，NOT_RECOVERABLE）——"五版本谱系"不成立，实际四个版本被测（C5 附带）。
- 原始轮：v3b→v3c 1:14、p=0.001（`../MCNEMAR.md`）；撤回原因：四实验共享无锁 ollama（C6）。
- 表：原始 error 率 2/50→5/50→18/50（载体：`../evidence/round-01/artifacts/sum_*.json`）。

### 3. 干净重跑（0.5 页，方法可复现）
- 范围修订：注册 250 项改跑 v3b/v3c 各 50（v1 不可加载、v2/v3 不在配对比较；`result.json` 不可当五版本谱系引用）。
- 独占：全程持 `/tmp/ollama_guard.lock`，sidecar 121 轮询 0 竞争（载体：`contamination_watch.jsonl`）。
- 协议与产线 `gen()` 逐字一致（temp 0、无 num_predict、150 s 超时、`[:1500]`）。
- 结果：v3b 0/50 剔除（原始 5 个 Timeout 全消失——guard 教训为真但非 1:14 成因）；v3c 10 项剔除＋8 项不终止。

### 4. 裁判缺陷（1 页，本文核心）
- `classify_runtime` 规则原文＋触发条件（<200 字符＋关键词）；c021–c030 题干自带关键词的对照表（载体：`judge_length_coupling_check.py`）。
- 双向证据表：老规则 v3c 删 10 / v3b 删 0；新规则两边 0；测试 39→47（载体：`patches/scorer-runtime-guard/`）。
- 过期链：2026-07 `analysis/001`（同一机制同一任务族）→ 长度护栏 → 8 月重建 → 10 月短答 v3c 引爆 → 无回归测试钉住"短而正确的诊断"（载体：manifest 日期＋`tests/test_scorer.py` 现状）。
- 影响面：16 项全 failure_diagnosis；另 30 个 `out_*.jsonl` 零 `runtime_error`（故其他 runs 不共享此通路）；v2 同病（0.6759(n=36)→0.7222(n=42)→0.6067）。

### 5. 可用性缺陷（0.5 页，2026-10-10 恢复）

- 现象：v3c 8/50 不终止（c001–c004、c006–c008、c035，与原始轮同一批 id）；numbered list 过 item 75 不停，无 EOS（形状描述转引草案 §0；本轮实测：L1 40/40 撞 150 s 顶且 0 字符，L3 24/24 顶 1024-token 格）。
- 三腿（载体：`runs/lineage-01-termination/round-01/termination.jsonl` 134 行、`ROUND_SUMMARY.md`）：
  L1 40/40 不终止；L2 40/40 `stop` 且同题逐字节相同；L3a（冷）/L3b（热＋30 warmup）/L3c（qwen3:0.6b 可控竞争 14 次）各 8/8 `length`，三腿输出逐字节相同。
- 定性句：能力轴之外、infra 之上——checkpoint 自身性质；与"题没答对"是两类失败（答出来的 v3c 反而更好，+0.0461）。
- 诚实注记：L3b 首轮因 GPU 训练竞争 4/8 HTTPError，整腿作废重跑（截断时间戳裁决）；L3 envelope 草案未签，本轮以 agent 名义执行、post-hoc 标注。

### 6. 三个口径与"两头同时错"（0.5 页）
- 同一批干净数据三口径表：published −0.0234 / 答了即算 +0.0461 / 不终止记零 −0.0784（载体：`artifacts/fixed/comparison.json`、`adjudicate_corrected.py`）。
- 错法 A（捏造能力损失）＋错法 B（抹掉可用性损失）各一段；A6 自纠注记（空正文默认通过负面检查，0.7367/+0.0050 作废）。
- 方法论句：分母按臂变动时，"回归"这个词先无定义——先固定分母再谈方向。

### 7. 相关工作（0.5 页）
- LLM-as-judge 已知偏差（位置/长度/格式）→ 本工作补一个新形状：**裁判的文本模式规则与题目文本的耦合**（题目自带关键词触发误删）。
- 评分器回归测试：引用"有保质期的修复"结论，主张"对可重建构件的验证必须配回归测试"。
- 不许写：把 arx / FDR / BH 扯进来（本案 K=1 且无 p 值，与那套无关；硬扯就是第十一次犯"语义去重式"错误）。

### 8. 结论与边界（0.25 页）
- 三句话：能力没退化（答了即算 +0.0461）；裁判删答对（16 项 failure_diagnosis，已修补丁，双向证据）；可用性缺陷是真的（8/50 不终止，三腿表征，§5）。
- 边界段（必须有）：单任务族收窄；v1 谱系缺一臂；envelope 未签（post-hoc 标注）；G1 已合并（2026-10-10，`cad68c7` 本地未 push）——数字基于合并后生产裁判；合并前基线由 `frozen/prod_scorer_20261009.py`（`62b240b7`）保留。
- 可复现声明：frozen 证据＋哈希＋脚本索引见 REPRODUCE.md。

## Venue（已定）

- methods workshop / short paper。单族＋单模型系，full track 不投。
- 收窄声明是标题的一部分（"in Failure-Diagnosis Tasks"），不是脚注里的让步。
