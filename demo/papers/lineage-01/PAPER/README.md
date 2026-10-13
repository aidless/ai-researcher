# lineage-01 论文项目（PAPER）

> 本目录是论文工作区，不是运行证据。运行证据在 `../evidence/`（原始轮）
> 与 `demo/runs/lineage-01-clean/round-01/`（干净重跑），一字未动。
> `../DRAFT_SEED.md` 是机器填空模板，不是稿子——开稿从 `OUTLINE.md` 起。

## 这篇论文是什么，不是什么

- **不是** "v3c 能力退化"——那个主张已死（STOP-REFUTED，见 CLAIMS.md C1）。
- **是**一篇 methods 短文，两个支柱：
  1. 生产裁判 `classify_runtime` 删掉答对的简洁回答（v3c 10 项、v2 6 项），且 2026-07 修过一次、8 月模型重建后过期（无回归测试）。
  2. v3c 8/50 不终止（可用性缺陷，能力轴之外）——**尚未表征**（见 GAPS.md G2）。
- published 的 −0.0234 两头同时错（捏造能力损失 −0.0234 vs 答了即算 +0.0461；抹掉可用性损失 vs 不终止记零 −0.0784），这是全文的钩子。

## 文件

| 文件 | 内容 |
|---|---|
| `CLAIMS.md` | 候选主张追踪：每条的状态（ESTABLISHED / NEEDS-WORK / DEAD）＋证据载体 |
| `OUTLINE.md` | 真实 manuscript 大纲（从裁决文档起草，有数字有载体） |
| `GAPS.md` | 三个缺口＋验收标准＋负责人（开稿前必须关闭或收窄 claim） |
| `REPRODUCE.md` | 可复现清单：冻结证据、哈希、脚本索引、重算命令 |
| `MANUSCRIPT_draft_v0.md` + `.pdf` | 初稿（已作废，被 v1 取代；留存备查） |
| `MANUSCRIPT_draft_v1.md` + `.pdf` | Major Revision 改写稿（当前稿；`build_pdf.py` 重建） |
| `REVIEW_RESPONSE_v1.md` / `_v2.md` | 两轮审稿逐条对账（接受/反驳/留作者定） |
| `APPENDIX_per_item_table.md` | 42 common items 逐项表（机器生成） |
| `APPENDIX_nli_adjudication.md` + `nli_adjudication.json` + `nli_adjudicate.py` | 开源 NLI 裁决（重跑逐字节相同） |
| `SIGNATURES.md` | 7 项待签清单（仅本人可签） |
| `AUTHORIZATION.md` | agent 授权记录＋两条红线（不代签、不碰别会话） |
| `build_pdf.py` | md→tex→PDF 构建脚本（含反斜杠路径坑注记） |

## 状态（2026-10-10，两轮审稿＋confirmatory 备战后）

- 稿 v1：10 页 PDF，零已知瑕疵；引用 2 验实＋3 验存在零编造；`verify_all.py`
  （Default Project 根）一键 21 项全绿 exit 0。
- NLI 开源裁决：10 项 4 支持／0 反驳／6 NEI——证伪"矛盾"，没证出"正确"；
  人工双人标注仍缺（需真人）。
- Confirmatory：PREREG（未签）＋150 题库（机器验证零失败，sha256 已记）备好；
  **零数据流动**，签字＋闲机器两者齐了才开跑。
- 待本人：SIGNATURES.md 7 项（签字、标注员、push、venue、key）。

## 状态（2026-10-09，已锁定）

- G1：**已合并**——2026-10-10 commit `cad68c7`（本地，未 push）；冻结件保留合并前基线；本目录决议原文作废留痕，见 GAPS.md。
- G2：**关闭（STOP-EXTEND full，2026-10-10）**——L1 40/40 顶格、L2 40/40 stop、L3a/b/c 8/8 length 且三腿输出逐字节相同；OUTLINE §5 已恢复。
- G3：**(b) 收窄**——标题限定 failure_diagnosis；venue 定 workshop/short。
- OUTLINE 已按以上三条落定（§5 删除，标题、摘要、§1、§8 同步），可开写正文（含 §5）。
- 干净重跑完成：v3b/v3c 各 50 项，独占锁，sidecar 121 轮询 0 竞争。
- envelope：`approved_by` 空着（post-hoc 标注，不倒签）。

## 变更记录（本目录）

- 2026-10-09：建 PAPER/。只新增文件；`../CLAIM_LEDGER.md`、`../MCNEMAR.md`、`../DRAFT_SEED.md`、`../evidence/` 均未动。
