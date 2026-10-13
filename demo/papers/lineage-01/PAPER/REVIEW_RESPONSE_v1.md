# 审稿回复 v1 → v2（两轮最高标准意见，2026-10-10）

> 状态：v1 已按两轮意见重写。本文件逐条记录"审稿要什么 → 改了什么 → 载体在哪"。
> 没改的写明理由，不装改完。

## 3.1 "no capability regression" 与端到端矛盾 → 接受，重构

- "能力"拆三轴（端到端 / 条件质量 / 可用性），端到端为主分析，条件为次。
- 主结论改为："生产 judge 制造了条件质量伪回归，同时掩盖了端到端可用性退化。"
- 标题换方向（Masks an Availability Regression），摘要/§1/§6/§8 全同步。
- 无条件 "no capability regression" 全文删除（grep 验证零残留）。
- 但比审稿要求的走得更远一步：敏感性分析显示端到端结论本身随惯例翻转
  （0→−0.078 p=0.049；0.5→+0.002 p=0.55；1→+0.082 p=0.0002；bootstrap CI 过零），
  所以 v1 **不主张**"端到端退化是真的"——主张的是"结论随惯例翻转，故回归无定义"。
  这比审稿人要的"把端到端当主结果"更弱，但更诚实；若审稿人坚持要一个方向性主结论，
  那需要作者拍板（复核清单已有此项）。

## 3.2 分母不一致 → 接受，全补

- v3b 在 42 common 上 0.7282（独立重算）；v3c 在 32 生产项上 0.7083（与 published 一致）。
- 分数类型：混合部分分 {0.3333, 0.5, 0.6667, 0.75, 1.0}，正文已声明"means, not proportions"。
- 配对明细：6:0:36（逐项差值表已算，最大 +0.5000、最小 +0.2500）。

## 3.3 §3 判据自相矛盾 → 接受，加判据盒

- 清洁轮排除 2×2：[[32, 18], [0, 0]]，discordants 18:0，exact p≈8e-6（独立重算）。
- 与原始 1:14 是两张不同的表（原始轮 v3b 有 5 排除，清洁轮 0 排除），正文明示区分。
- "registered rule" 定义＋STOP-* 定义＋post-hoc 标注进 §3；"significant yet refuted"
  解释为：显著的是**排除不对称**（judge 行为），被反驳的是**能力回归**（模型行为）。

## 3.4 统计严谨性 → 接受，能补的全补

- 符号检验（6:8，p=0.79）与 Wilcoxon（p=0.049）**同时报告**，不一致处不藏。
- rank-biserial −0.278、HL −0.2083（端到端）／+0.3333（条件），bootstrap CI。
- 敏感性四格全表。没补的：per-item 完整 42 行表（太长，放附录候选，作者定）。

## 3.5 补丁泛化与安全边界 → 部分接受

- 已做：83 文件前后对比（600 texts，42 rescued，0 newly flagged，归属到文件）；
  12 合成探针（8 跨族＋2 真回声＋2 干净）：11/12 符合设计。
- **抓到一条真边界**：裸 `"timeout"` 碎片新规则不 flag（老规则 flag）。
  in-corpus 影响零（无此类文本需 flag）；端到端影响近零（ exclusion vs ~0 分）。
  已写入正文 §4 作已知边界，未隐藏。
- 未做（需人工）：被救样本的人工/强 judge 复核。已列入复核清单，不冒充已做。

## 3.6 可用性表格＋条件澄清 → 接受

- 150 s（L1/L2，无 cap，client 超时）vs 1024-token 格（L3，`length`）已分开写；
  `done_reason` 值逐腿列出；输出逐字节相同已声明（L2/L3a/b/c，chars 全同）；
  8 ids 三腿一致已声明；void 规则承认为 post-hoc（非预注册）。
- hash 未逐项列（输出文本存于 pred 文件，可重算；作者若要逐项 hash，进附录）。
- §5 表格 PDF 渲染已重验（见下）。

## 3.7 可复现性 → 接受（draft 内能做的全做）

- 每个关键数字已内联载体（文件＋表＋脚本名）；hash/命令级清单在 REPRODUCE.md。
- cad68c7 未推送：正文声明 frozen 基线＋补丁包路径可获取；push 本人定。
- 复核清单保留在 draft（标注"签字后删除"）；投稿版删除——这是 draft，不是投稿版。
- §2 烂尾/§8 重复：在本 PDF 版未复现（全文已重读），若审稿人指具体行号再改。

## 3.8 相关工作 → 已填实（2026-10-10 联网验证）

- Zheng et al. MT-Bench（NeurIPS 2023，arXiv:2306.05685）：position/verbosity/
  self-enhancement biases＋mitigations，>80% 人机一致——经 NeurIPS 页面＋arXiv 双重验证。
- Wang et al. NewSum 2023（pp.1–11，DOI 10.18653/v1/2023.newsum-1.1）：ChatGPT
  作 NLG evaluator 的早期 meta-evaluation，prompt/数据集敏感——经 ACL Anthology 验证。
- Contamination 方向 survey 级引用三篇 arXiv（2406.04244／2411.03923／2410.09247）：
  仅验证存在，细节待作者投稿前确认（正文明示）。
- 零编造引用。原 3.8 段落作废。

- §7 按形状写 своб段落＋[CITE] 占位；**无一条编造引用**。
- 填实需作者验证每条文献（ venue/年/页码），这是作者工作，不代劳。

## 3.9 标题 → 接受，已换方向

- 新标题：The Judge Deleted Correct Answers: Text-Pattern Coupling in
  Failure-Diagnosis Tasks Masks an Availability Regression。
- "Correct" 首用即操作化定义（过全部 reference checks；12 实质＋4 裸复读分层）。

## 次要问题 1–10

1. p 值统一 0.0010（两位小数精确值）——全文已统一（grep 可验）。
2. 分数类型已声明。3. 0.7083 同一数字同一原因（clean production，n=32）。✓
4. v3b 分布已给全（≥873＋1500 截断 cap 注）。5. v2 六项明细已给（38/38/178/183/190＋任务归属）。
6. v1 NOT_RECOVERABLE 进摘要。7. "No FDR" 段保留但压缩（防蠢审稿人的必要防御，不占地方）。
8. 清单保留在 draft（见上）。9. STOP-* 已定义。10. void 表述已改。

## 关键问题 1–10（给作者的只剩 3 个）

- Q2（0.6533 vs 0.7317 是否显著、是否主结果）：已算（p=0.049/0.79/CI过零），
  主张已收窄为"惯例依赖"，待作者首肯这种弱主张。
- Q4（answered-only 是否预注册）：已标 post-hoc。
- Q5（新规则漏真错）：裸碎片边界已报告；人工复核待作者。
- Q6（跨环境 seed/serving）：未测，Limitations 已写。
- 其余（Q1/Q3/Q7/Q8/Q9/Q10）：正文已答，载体已给。
