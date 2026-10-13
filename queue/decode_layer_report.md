# 变更报告：needs_decode 独立配对层（任务③）

- 新增文件：`queue/decode_layer.json`（283 条）——独立层，共享 wiki **零改动**（本脚本对 wiki 只读）。
- 共享 wiki：未修改任何笔记（scanner/decode_queue 同款只读约束）。
- **已解码 0 / 283**：标签展开全部待人工（decode_queue 铁律：自动展开=编造）。`decoded` 全空，auto_expanded=0 不变量保持。
- 配对完成 283 / 283：每条压缩标签已配上同笔记的原文【做法】段（wiki 逐字取证）与【与本项目关系】段，展开标签时不再需要回翻 wiki。
- 与队列对账：method_mismatch_vs_queue = []（两条取证路径逐字一致）。

## 展开标签的正确姿势（给未来的人）

1. 打开 `queue/decode_layer.json`，按 tier/score 从高到低挑条目；
2. 读 `note_verbatim.method_from_wiki` 与 `compressed_label`，把标签展开成 ≥12 字散文（不得保留「XX；XX」形态）；
3. `source` 写明展开依据（如「原 agent 会话」「笔记做法段+论文摘要」）；
4. 跑 `python3 -m ai_researcher.decode_queue`（check_all）验收。

## 为什么不自动展开（一段话）

标签第二短语（如「位置限」「泛化限」）在笔记三段里没有对应句；把「位置限」猜成「位置编码受限」看起来完全合理，但链上没有任何一处可追溯到原文——这正是 decode_queue.py 拒绝自动展开的原因。
