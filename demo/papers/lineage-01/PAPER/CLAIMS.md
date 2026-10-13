# 主张追踪（CLAIMS）

每条候选主张一行：状态、数字、载体。数字只抄裁决文档与账本，不造新数。
状态定义：ESTABLISHED（证据闭环）/ NEEDS-WORK（缺口在 GAPS.md）/ DEAD（已证伪，写进论文当反例或不提）。

## C1. v3c 能力退化（v3b→v3c −0.0234）——DEAD

- 原始数：McNemar 1:14、p=0.001（`../MCNEMAR.md`，已从原始文件精确复现）。
- 干净重跑＋修正裁判后三口径（`runs/lineage-01-clean/round-01/artifacts/fixed/comparison.json`）：
  published −0.0234；只算答了的项 +0.0461（v3c 0.7778 vs v3b 0.7317，配对 42 项 Wilcoxon W=0、精确 p=0.03125）；不终止记 0 则 −0.0784。
- 判决：STOP-REFUTED。**论文里不许出现"能力退化"四个字作为肯定主张**，只能作为"被推翻的原假设"出现。

## C2. v3c 8/50 不终止（可用性缺陷）——ESTABLISHED（表征完成 2026-10-10）

- 现象：干净重跑 v3c 8 项（与原始轮同一批 id：c001–c004、c006–c008、c035）numbered list 写过 item 75 不停，20.6 字符/秒，无 EOS；v3b 0 项。
- 这不是能力轴（答出来的 v3c 反而更好，+0.0461），也不是 infra（独占锁下复现）。
- 缺口：未表征（重复性×对照×机器扰动三腿都没跑）。见 GAPS.md G2。
- 载体：`runs/lineage-01-clean/round-01/artifacts/`（pred/out/sum）、`arm_termination_census.py`、未签的 `终止性预注册草案-v3c-nontermination-2026-10-09.md`。

## C3. `classify_runtime` 删掉答对的简洁回答——ESTABLISHED（单族内）

- 机制：<200 字符且命中 `timeout`/`connection refused`/`240s` 即判运行时错误、`score=None`；而 c021–c030 是 `failure_diagnosis` 题，题干自带 `connection refused after 240s timeout`。
- 范围：v3c 10 项、v2 6 项，**16 项全是 failure_diagnosis**；v3b、v3、v1 为 0。pipeline 另 30 个 `out_*.jsonl` 零 `runtime_error`（故其他 runs 的 STOP-EXTEND 不共享此通路）。
- 双向证据：`patches/scorer-runtime-guard/`——老规则删 v3c 10 条、v3b 0 条；新规则两边 0 条；测试 39→47 全绿；用新裁判重算 clean 数**一个没变**（v3b 0/0.7317/n=50，v3c 同 8 id/0.7778/n=42）。
- 边界（必须写进论文）：单任务族证据。推广到"短回答裁判"需第二族（见 GAPS.md G3），否则 claim 收窄到 failure_diagnosis 类任务。

## C4. 2026-07 修复过期——ESTABLISHED

- 七月 `auditable-llm-eval/analysis/001` 修过同一机制同一任务族（c021/c022/c024 正确诊断被误删逐字在案）。
- 但补的是长度护栏（`len(text) >= 200 → 不判错`）；8 月五个 `copilot-3b-lora*` manifest 重建；10 月 v3c 恰是短答型（中位 27 字符）——残余洞炸了。
- `tests/test_scorer.py` 无任何一条钉住"短而正确的诊断"。
- 结论句（可直接用）：**对着会被重建的构件验一次、又没有回归测试的修复，是有保质期的。**

## C5. published −0.0234 两头同时错——ESTABLISHED

- 同一批干净数据，`adjudicate_corrected.py` 三口径互相印证（0.7317 / 0.7778 / 0.6533）。
- 错法 A（捏造能力损失）：裁判删掉 v3c 一个满分 1.0 的族（与 reviewer_qa 并列最高，非独占最高——原“得分最高”表述已修正）。
- 错法 B（抹掉可用性损失）：8 个不终止被摘出分母。
- v2 同病：published 0.6759(n=36) → 答了即算 0.7222(n=42) → 不终止记零 0.6067。故"能力沿 v1..v3c 非单调"在按臂变动分母的评分下整体不可用。
- 附带：v1 从未产生任何输出（两次运行原始文件实测 50/50 HTTPError；"构件不可加载 NOT_RECOVERABLE"这层机制认定转引自另一会话的证据（空闲机 6/6 复现＋blob 字节数＋mtime，载体 amendment A7＋`model_digests.json`；我自己在满载机器上的探针只能证明"忙"，证伪不了它），"五版本谱系"不成立，实际四个版本被测过。

## C6. 污染机制（四实验共享无锁 ollama）——ESTABLISHED，但不是 1:14 的成因

- 独占访问治好了 v3b（原始 5 个 TimeoutError 全消失，50/50 无剔除）——`ollama_guard.py` 的教训为真。
- 但它解释不了 1:14（那是 C3 + C2）。论文里写清这一句，不多占篇幅。
- 载体：`runs/lineage-01-clean/round-01/contamination_watch.jsonl`（121 轮询 0 竞争）+ 原始轮 error 率 2/50→5/50→18/50。
