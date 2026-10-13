# 预注册：lineage-01 confirmatory round（未签、未跑）

> 状态：**DRAFT-UNSIGNED。`approved_by` 为空；签之前收任何数据即违规。**
> 本文件起草 2026-10-10（agent 会话，受 blanket 授权；签署权仅属本人）。
> 题库 `bank_d001_d150.jsonl`（150 项，机器验证零失败）与本文件同目录；
> 发起运行前先签后跑，顺序不可反。

## 0. 为什么需要这一轮

lineage-01 已有关闭结论全部来自 post-hoc 分析（n=50 单轮、单题库、
`answered-only` 事后指定）。顶会主会不接受 post-hoc 主结果。
本轮是 confirmatory：同一批问题、新题、新数据、预先固定的全部规则。

## 1.  estimands（主次已定，跑后不许换）

| 位 | estimand | 定义 |
|---|---|---|
| 主 | 端到端任务成功率差 | v3c − v3b，同 150 题，非答案计 0，fixed scorer |
| 次1 | 条件答案质量差 | 仅两臂皆有分题，v3c − v3b |
| 次2 | 可用性差 | 非终止率差（`done_reason` 缺失率），v3c − v3b |
| 次3 | 法官不对称 | frozen-old vs fixed-new 删除率差（新题上） |

多重性：主检验恰一个（端到端配对），不校正；其余全部 exploratory/descriptive，
显著性只报告不下结论。5 任务族各自只做描述统计，不做族内检验
（族内检验若做，Holm——但本轮不做，只描述）。

## 2. 固定惯例（跑后不许改）

- 非答案计 **0**（主）；敏感性（0.5/1.0）只作次要呈现，不参与主 verdict。
- 排除规则：fixed scorer（合并后生产版，commit `cad68c7`；以跑时 `sha256`
  为准记档）。frozen-old（`62b240b7`）仅用于次3 的新旧对比。
- 分数：scorer 原样输出（ partial credits 保留，不二值化）。
- 臂：v3b vs v3c 配对为主；v2/v3 同题库为 exploratory（机器空闲才跑，
  先声明为 exploratory，不进主 verdict）。

## 3. 样本量（功效已算，不拍脑袋）

- 端到端：pilot dz=−0.243（mean −0.0783, sd 0.3218, n=50）→
  80% power（α=0.05 双侧，Wilcoxon 按 0.955 效率折算）需 **n≈140**。
  取 n=150（5 族×30，复刻原题库结构）。
- 条件质量：pilot dz=+0.393 → 需 n≈55；150 富余，余量用于族内描述。
- 法官不对称：分类变量（删/不删），pilot 10/10 vs 0/10——功效不是约束，
  **新题**才是（避免在同一 10 题上重复验证）。

## 4. 题库（已冻结，跑前只读）

- `bank_d001_d150.jsonl`：150 行，id 唯一，5×30 平衡，无重复 prompt，
  键集合法，全部检查类型在 DISPATCH 内，逐任务签名与生产一致。
  验证脚本输出："150 rows, failures: ZERO"（验证命令见 REPRODUCE 附录）。
- failure_diagnosis 30 项中 20 含触发词（含 connection refused/timeout/240s
  自然语境）＋10 无触发词（族内对照）。
- **题库冻结后，任何人（含作者）不得改一字**；要改就发新版 bank 并重签。
  sha256：ec6a72426aa08d671ff8c518e6ac8a9a26ad733a5525282f7be3291cca32aff4

## 5. 运行协议（与 termination 同级）

- 全程独占（进程表＋GPU 双监控；僵死豁免规则沿用，显式记档）。
- temp 0、无 `num_predict`（与产线一致；终止性若出现，按终止性 kill switch 另记，不混入主 verdict）。
- 逐行 JSONL flush；错误计入分母不删行（HTTPError＝无测量，按 void 规则另行裁决，不计入任一分母——见 termination round 的 void-leg 先例）。
- 主分析用 Wilcoxon 配对（tie 校正渐近分布）＋符号检验＋bootstrap CI
  （paired diffs 有放回，20000 reps）＋rank-biserial＋Hodges-Lehmann——
  与 pilot 同一套，不许换检验。

## 6. Futility stop（2026-10-11 追加，经用户追加同意）

**动机（可量化）**：这台机器能稳定提供 ≤2h 独占窗口，而 300 次顶格调用需
4–12h；confirmation-8fam 已因 12h 墙钟被杀一次。pilot 证据（端到端
p=0.0490 临界、bootstrap CI 过零、符号检验 p=0.79、结论随非答案惯例翻转）
指向“大概率本就是阴性”，故预注册一个**只能得出阴性**的中途停止。

**规则（跑前钉死，判据不自作主张）**：
- 中途点：两臂**各完成 ≥75 题**后，且只在那时，计算一次。
- 判据：以已收数据估计端到端配对差的 95% CI（paired bootstrap，20000 reps，
  与主分析同一函数）。若 CI **上界 < pilot 观测效应的 40%**（pilot mean
  diff −0.0783 × 0.4 = −0.0313；CI 上界 < −0.0313 表示效应即便真实也小到
  不足以支撑任何“回归”叙事），则 **STOP-REFUTED-BY-FUTILITY**：停手，
  按 REFUTED 记录，停止收数。
- 若 CI 上界 ≥ −0.0313：继续收到 150/臂，按 §7 主分析判。
- 中途点**不**做显著性检验、**不**因“看起来显著”而停——它只能用来停为阴性。

**为什么这不碰 I 类错误**：futility 停止只能提前得出“无法拒绝/无实质效应”，
不能提前拒绝 H0。宣布阳性仍然必须走完 n=150 的 §7 主分析。alpha 未花，
无需 spending 校正。

**为什么这不改变主 estimand**：端到端（非答案=0）定义不变、检验不变、
显著性阈值不变；变的只是“何时可以合法关机”。

**记录义务**：中途计算的那一次 CI 与决定，必须连同其时已收题数写进
`contamination_watch.jsonl` 与最终 `result.json` 的 `futility` 字段。
若跑满 150 未触发，该字段记 "not-triggered at n=75 look"（或未到中途点）。

**追加批准状态**：用户于 2026-10-11 回复“同意”（追加批准本条），但**尚未
提供姓名/日期**，故本栏保持空着：`approved_by_futility`：________
`approved_at_futility`：________
——空着即未追加签；futility 规则在追加签之前不生效（跑满 150 的 §7 是唯一
有效路径）。

## 7. Kill switch（跑完判，不看数据再定）

| 条件 | 动作 |
|---|---|
| 端到端 paired Wilcoxon p≤0.05 且方向与 pilot 一致（v3c 低） | 主结论成立（端到端退化可复现），进入人工标注复核 |
| 端到端 n.s. | STOP-REFUTED：pilot 的端到端信号不复现；条件轴与法官 bug 结论不受影响（它们不依赖本轮） |
| 新旧 scorer 删除不对称在新题上复现（old 删短答、新不删） | 机制 CONFIRMED（与端到端 verdict 独立） |
| 新题上 old 规则也不删 | 机制收窄：bug 是题项特异的，回退到 case-study 定位 |
| 任何一臂非终止率 >20% | 先查 infra（独占记录），排除后再谈模型；沿用 lineage-01 的撤回纪律 |

## 7.1 人工标注协议（需真人，agent 不执行）

- 对象：新题中被任一规则删除的全部项＋随机对照 20 项。
- 双人独立标注（语义正确/错误/无法判定），报告 Cohen's kappa；
  分歧由第三人裁决（标注者不许看模型/arm 标签，盲标）。
- 标注在跑数**之后**、结论**之前**进行；标注方案冻结于此，不许事后加规则。
- **IRR fallback（预先注册，跑后不许改）**：若 kappa < 0.6，不改方案、
  不换标注员标准，只做两件事——(a) 扩第三独立标注员并报告三人 pairwise kappa；
  (b) 若仍 <0.6，人工层结论降级为"未达成共识"，论文只保留机器层结论
  （关键词检查通过率），不许用低一致标注支撑任何肯定句。
- 执行人：由本人安排（agent 不冒充 annotator）。

## 7b. 开跑前检查（签字后、收数前逐项打勾，不符即停）

- [ ] 题库人审：至少一人通读 150 题 prompt＋检查项，确认无歧义、无答案泄露、
  无话题重复（机器验过格式，人验语义——格式正确≠题好）。
- [ ] 构件预检：v3b/v3c/v2 模型可加载（各 1 次探针调用成功）；frozen scorer
  与 live scorer sha256 与记录一致；任一不符即停跑，先修构件。
- [ ] 机器独占确认：进程表＋GPU 双空闲（沿用 termination 纪律）。
- [ ] 以上三项由执行人（agent）逐项记录 Filtering 结果到运行日志；
  缺一项即停，不许"先跑起来再说"。

## 8. 签署栏

- `approved_by`：刘泽文（in-session verbal approval 2026-10-11, recorded by
  agent; NOT hand-signed — see the qualifier note below before citing this
  round's approval status）
- `approved_at`：2026.10.11 (user-stated; recorded 2026-10-11T15:13 CST,
  07:13Z — approval and recording are the same session, before any data)
- `bank_sha256`：ec6a72426aa08d671ff8c518e6ac8a9a26ad733a5525282f7be3291cca32aff4
- 签署即表示：题库已读、惯例接受、kill switch 接受；签署后收的第一行数据才算数。

### 8b. What this approval is (and is not)

**What happened** (verbatim in `APPROVAL_RECORD.md`): the user said
"我同意了 你帮我签名 刘泽文 2026.10.11" in the opencode session. The agent
filled this section with the name and date supplied, and added the qualifier
that this was a verbal approval recorded by the agent, not a hand signature.

**Why the qualifier stays**: a bare name in a signature field asserts "this
person hand-signed this document." That assertion would be false. This
section as written asserts what is true: the named person approved, in this
session, before any data was collected, and the agent transcribed it. Anyone
reading the approval record can weigh it correctly. Stripping the qualifier
to make the record look stronger is exactly the class of act this project
exists to catch.

**Evidentiary status, stated plainly**: weaker than a hand signature in
accountability (the hand-signed row would survive a claim of "I never said
that"), but NOT weaker in the property this section actually needs — the
rules, conventions, and kill switch were fixed and approved BEFORE the first
byte of data. The session log is timestamped and contains the approval.

**If a venue or reviewer requires hand signature**: the bar for this round
is currently a transcribed verbal approval; say so. Do not present it as
hand-signed.
