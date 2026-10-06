"""ai_researcher —— 本工作区的全自动研究员 agent。

四层，每层一个模块，各自的边界写在模块头：

    L0 scanner.py  从已有笔记抽研究问题（只读 wiki，永不写）
    L1 ranker.py   确定性打分 + 返回理由（本机 6GB 约束进评分）
    L2 runner.py   问题 → 可跑实验 → 溯源落盘（fail-closed）
    L3 store.py    结果回 wiki，带机械门禁 + 计数复验

公共纪律（AGENTS.md 铁律 6/7/15）：共享 wiki 无锁、每次写留备份、
写后复验、每个门配"注入违规必须失败"的反证。
"""

__all__ = ["scanner", "ranker", "runner", "store"]
