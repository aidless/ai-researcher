# 待签清单（SIGNATURES）：只剩这些需要本人手写

> 原则：agent 不写任何名字、不填任何日期。每一项都标了"签什么＋签之前看什么＋签完解锁什么"。
> 签完一项就在本文件打勾 √，别处的清单保持原样（它们是证据链的一部分）。

## S1. Confirmatory PREREG 签署（解锁：开跑）

文件：`runs/lineage-01-confirmatory/PREREG.md` §8，三空：
- [ ] `approved_by`：________（签中文名或 ID，与 envelope 惯例一致）
- [ ] `approved_at`：________（签之前先读题库，见下）
- [ ] `bank_sha256`：________（先跑 `sha256sum bank_d001_d150.jsonl`，
  期望 `ec6a72426aa08d671ff8c518e6ac8a9a26ad733a5525282f7be3291cca32aff4`，
  对上才填；对不上停下来找我）
- 签之前必读：`bank_d001_d150.jsonl` 抽查（建议随机 20 题看 prompt＋检查项是否合理）、
  §1 estimand 表、§6 kill switch 表。读完签字约 20 分钟。
- 签署即表示：题库已读、惯例接受、kill switch 接受。签署后收的第一行数据才算数。

## S2. 稿件复核清单 15 项（解锁：投稿）

文件：`PAPER/MANUSCRIPT_draft_v1.md` 末节。逐项签字后删除该节。
其中 agent 已独立验过的（供你抽查时省时间，不代替你签）：
- §6 表格三行：comparison.json 数值我重算过一致
- Wilcoxon/scipy：我对表过（0.03125 / 0.0490）
- 121 轮询：我数过（121 行 0 竞争）
- 引用 5 篇：2 篇验实（venue/页码/DOI），3 篇仅验存在——**这三篇必须你亲眼看过**
- 其余（c021 对照表跑过否、标题接受否、envelope 维持不签否）：纯你定

## S3. cad68c7 push（解锁：审稿人可验证合并）

- 决定 push 到哪里（origin 哪个分支？）＋用谁的身份推。
- 我不碰你的 git credentials，也不动 `/tmp` 那份 checkout。
- 不 push 的代价：审稿人只能看 frozen 基线＋补丁包（也够，但弱一档）。

## S4. envelope approved_by（建议：明确不签）

- `proposals/envelopes/envelope_lineage-01_confound_audit.json`。
- 我的建议：**不要补签**。跑都跑完了，现在签是倒填日期，比空着更不诚实。
  post-hoc 标注就是最终状态。请你亲口确认"不签"，我记档（确认本身就是决定）。

## S5. 人工标注安排（解锁：16 项语义复核）

- 找 2 个标注员＋盲标方案（PREREG §7 已写好，直接用）。
- agent 不碰（自己判自己是 circular）。

## S6. venue＋标题终定（解锁：投稿）

- 二选一：(a) 现标题 workshop/short（已锁定）；(b) 审稿人建议的 case-study 标题。
- 定完告诉我，我同步 OUTLINE/GAPS/稿件三处（一分钟活）。

## S7. 免费 API key（Wave 2 前置，与本文无关，单列以免忘）

- 你本人申。我碰不了。
