# 缺口（GAPS）：决议记录

> 2026-10-10 修订：G1 由“不并”变为“已合并”，决议原文保留作废弃记录。

> 2026-10-09 全部落定：G1 不并、G2(b) 不等、G3(b) 收窄。本文件转为决议记录，
> OUTLINE 已同步。下面原文保留，只加决议行。

## G1. scorer 修正合不合并 —— 负责人：本人，验收：一个签字

> **决议 2026-10-09：不并**（2026-10-10 作废，被现实超越）。
> **2026-10-10 实际：已合并。** 已合并（2026-10-10，commit `cad68c7`，本地；push 待本人定）。合并在“全做”授权下执行；`frozen/prod_scorer_20261009.py`（`62b240b7`）保留合并前基线，8 个按路径读裁判的脚本默认钉冻结件。

- 现状：补丁包 `patches/scorer-runtime-guard/` 交付（可应用、双向证据、测试 39→47），但 `/tmp` 共享评分器没动（另一会话在用，动它＝换别人的分母）。
- 验收二选一：
  - (a) 合并：lineage 全部臂按新规则重算，`result.json` 更新，amendment 记一笔；或
  - (b) 不合并：论文明确声明数字基于 commit `b05cf87` 的生产裁判，补丁作为附录交付物。
- 在验收前，论文里所有 scorer 相关数字必须标注版本号，不许裸写。

## G2. 终止性表征没跑 —— 负责人： agent（跑）＋本人（批机器窗口），验收：预注册三腿全绿

> **决议 2026-10-09：(b) 不等。**
> **2026-10-10 关闭：L1+L2+L3 跑完，STOP-EXTEND full。C2 升级为已表征；OUTLINE §5 已恢复。**


- 现状：现象已记录（C2），表征零进展。预注册草案 `终止性预注册草案-v3c-nontermination-2026-10-09.md` 未签。
- 三腿（草案原文）：L1 8 项×5 次重复、L2 v3b 同题对照、L3 机器状态扰动；判据 `done_reason=="stop"`，150 s 与 1024 tokens 两个天花板分开注册。
- 验收：三腿按草案跑完，结论二选一写进论文——
  - (a) v3c 稳定不终止、v3b 稳定终止 → 可用性缺陷成立，与能力轴正交；
  - (b) 复现不出 → C2 降级为"单次观测"，论文只保留 C3＋C4（纯裁判故事），标题与摘要重写。
- 资源：真空闲机器 1.5–3 h（持锁不够，要看着没有并发进程；G10 教训：训练作业不走 guard 锁）。

## G3. 裁判 bug 缺第二族证据 —— 负责人：agent（找）＋本人（定收窄与否），验收：二选一

> **决议 2026-10-09：(b) 收窄写。** 标题限定 failure_diagnosis；venue 定 workshop/short。找第二族转为开放式后续工作，不 blocking。


- 现状：16 项误删全在一个任务族（failure_diagnosis）、一个 run。单族 bug 修补撑不起一般性主张。
- 验收二选一：
  - (a) 找到第二族：换一族任务（或换一个模型）复现"短而正确被删"，补丁在该族同样双向成立；或
  - (b) 收窄 claim：标题/摘要/结论明确限定为"failure_diagnosis 类任务的文本模式裁判缺陷"，并承认单族边界；venue 相应下调（workshop/short，不投 full）。
- 禁止事项：不许把单族证据写成"短回答裁判普遍有问题"。

## 进展 2026-10-09（G3 分析部分已做完，不需再挖）


- 语料全扫：83 个 `out_*.jsonl`（papers＋runs 全树），196 个 `runtime_error` **全在 lineage-01**（原始轮 v1 50/v2 14/v3 2/v3b 5/v3c 18、runs 镜像、干净轮 v3c 18），其余 0 个。边界确认。
- 陷阱面实测（`test_50.jsonl` 50 题）：触发词（timeout/connection refused/240s）**只存在于 failure_diagnosis 题干（10/10）**，另 4 族 40 题天然免疫。故该 bug 在本 eval 内的 blast radius ＝ 整个 failure_diagnosis 族；v3c 该族 10 项全删，v2 删 6 项。
- 结论：G3(a)（第二族）**靠分析关不掉**——现存语料里没有第二族；要找必须收新数据（＝新研究动作，需另行 GO）。G3(b)（收窄）现已就绪，claim 可一字不改地写成"failure_diagnosis 类任务的文本模式裁判缺陷"，数字就是上面这两行。

## 进展 2026-10-10（L1+L2+L3 全跑完，G2 关闭）

- L1（v3c 8 项×5 次）：40/40 撞 150 s 顶，0 字符，无 `done_reason`；逐项 5/5 无一例外。
- L2（v3b 同 8 项×5 次）：40/40 `done_reason="stop"`，同题输出逐字节相同。
- 独占记录：僵死进程显式豁免（CPU/elapsed 记档）、guard 锁被僵尸持有故未强夺（强夺会静默分叉互斥），前后快照＋误差分布为安全网。
- Verdict 按注册判据：**PENDING L3**，不是 STOP-EXTEND（三腿合取缺一不可）。
- L3 envelope 草案已写（`runs/lineage-01-termination/round-01/L3-envelope-draft.json`，未签）、L3 仪器未写。
  载体：`runs/lineage-01-termination/round-01/`（termination.jsonl 80 行、ROUND_SUMMARY.md）。

## 进展 2026-10-10（L3 跑完，G2 可关）

- L3a（冷）：8/8 `length`；L3b（热＋30 warmup）：8/8 `length`（首次 attempt 因 GPU 训练竞争 4/8 HTTPError，整腿作废重跑，截断时间戳裁决）；L3c（qwen3:0.6b 可控竞争 14 次）：8/8 `length`，三腿输出逐项逐字节相同。
- kill switch 合取成立：**STOP-EXTEND（full）**。载体：`runs/lineage-01-termination/round-01/`（termination.jsonl 134 行、ROUND_SUMMARY.md）。
- G2 状态→**可关闭**（三腿全绿）；§5 恢复与否待本人一句话（OUTLINE 已按 G2(b) 锁定，恢复＝改锁定，需明确指令）。

## 进展 2026-10-10（confirmatory round 备好，未签未跑）

- 预注册 `runs/lineage-01-confirmatory/PREREG.md`（DRAFT-UNSIGNED）：
  主 estimand 端到端（非答案=0），次为条件/可用性/法官不对称；
  惯例全固定（敏感性只作次要呈现）；臂 v3b/v3c 配对为主、v2/v3 exploratory；
  kill switch 五分支；人工标注协议（需真人）。
- 功效：端到端 dz=-0.243 → n≈140（取 150）；条件 dz=+0.393 → n≈55。
  题库 5×30=150（failure_diagnosis 30 中 20 触发词＋10 对照），机器验证零失败，
  sha256 `ec6a7242…`（bank.sha256）。
- **零数据流动**：签之前连一个 token 都不跑。签（一句话）＋闲机器（~4h，
  v3b/v3c 300 calls；v2/v3 另加）两者齐了才开跑。

## 进展 2026-10-10（开放题库方向：G3 补充证据，不开新数据）

经测，可直接用的开放项只有 R26 的 TriviaQA/EntityQuestions 400 条真实答案
（`paper_workflow_kb/results/r26_answers_{trivia,entity}.jsonl`，qwen2:7b temp 0）。
其余候选不适配：GAIA 是 agent 场景非纯 prompt；benchmark_dataset 仅 2 条。

- 旧规则全量扫描 400 条：**0 误伤**。含义是双向的：(a) 没有第二个自然家族
  可供"被救"（这些答案本就不含触发词）；(b) blast radius 上界再收紧一格——
  在 400 条验证短答上旧规则安静，误伤只发生在触发词 bearing prompts。
- 合成探针（12 条：8 跨族短正确答案＋2 真回声＋2 干净）：11/12 符合设计；
  唯一偏离是裸 `"timeout"` 碎片（无 prompt 上下文）新规则不 flag——已报备为已知边界，
  in-corpus 影响零。**方法论自白**：探针答案是我 hand-authored（见过规则），
  它测的是规则力学，不是经验 prevalence；prevalence 证据仍是 lineage-01 的 16 项。
- 结论：G3(a)（真第二族）仍需新数据收集，不在本轮 scope；G3(b) 收窄 claim
  现有三层支撑——16 项实测＋400 项零误伤界＋12 探针力学。够 workshop，不够 main。
