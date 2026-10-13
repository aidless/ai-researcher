"""归一化器的门禁测试 —— AGENTS.md 铁律 #7「门必须能失败」。

每个测试都配一条**反证**：注入违规后必须 exit≠0。
没有反证的校验门是装饰，这一节的每个 assert 都成对存在。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.normalize_notes import (  # noqa: E402
    Result,
    already_strict,
    classify,
    extract_sections,
    normalize_one,
)

LOOSE = (
    "做法：ExpertFlow以单前向路由路径预测加token调度与预测性专家缓存，"
    "单GPU省显存93.72%吞吐10倍。留下开口：卸载基线大胜但无精度/agent任务分解。"
    "C1-C3关系：C1是SLM单卡部署的关键系统解，C2为路由依赖的利用率优化，C3端侧MoE推理。"
)

STRICT = "【做法】x\n【开放点】y\n【与本项目关系】z\n"


class TestExtraction(unittest.TestCase):
    def test_extracts_all_three_sections(self):
        """正向：宽松笔记三段全抽得到。"""
        found, missing = extract_sections(LOOSE)
        self.assertEqual(missing, [])
        self.assertIn("ExpertFlow", found["做法"])
        self.assertIn("卸载基线", found["开放点"])
        self.assertIn("SLM单卡", found["与本项目关系"])

    def test_relation_section_does_not_swallow_gap_section(self):
        """反证：段间不能互相吞（贪婪匹配的典型失败）。"""
        found, _ = extract_sections(LOOSE)
        self.assertNotIn("留下开口", found["与本项目关系"])
        self.assertNotIn("C1-C3关系", found["做法"])

    def test_missing_section_is_reported(self):
        """反证：缺段必须报缺，不能静默通过。"""
        _, missing = extract_sections("做法：只有做法没有别的段落内容在这里凑够十个字")
        self.assertIn("开放点", missing)
        self.assertIn("与本项目关系", missing)

    def test_empty_notes_fails_cleanly(self):
        """反证：空笔记不得被当作合格。"""
        self.assertFalse(already_strict(""))
        found, missing = extract_sections("")
        self.assertEqual(missing, list(("做法", "开放点", "与本项目关系")))


class TestNormalize(unittest.TestCase):
    def test_normalize_produces_strict_format(self):
        r = normalize_one("k1", {"notes": LOOSE}, "2026-10-02")
        self.assertTrue(r.ok)
        self.assertTrue(already_strict(r.notes))
        # 搬运而非改写：原文必须仍在输出里
        self.assertIn("单GPU省显存93.72%吞吐10倍", r.notes)

    def test_normalize_is_idempotent(self):
        """幂等：已合格的再跑一次不得变形（否则重复执行会污染全库）。"""
        first = normalize_one("k1", {"notes": LOOSE}, "2026-10-02")
        second = normalize_one("k1", {"notes": first.notes}, "2026-10-02")
        self.assertEqual(second.notes, first.notes)

    def test_incomplete_source_is_rejected_not_guessed(self):
        """反证：抽不全必须拒收 —— 绝不允许"根据标题猜一段做法"。

        这是本模块最重要的一条：它拦住的是伪造 P1 数字的路径。
        """
        r = normalize_one("k1", {"title": "Some Paper", "notes": "做法：abc"}, "2026-10-02")
        self.assertFalse(r.ok)
        self.assertIsNone(r.notes)  # 不产出任何新 notes
        self.assertTrue(r.missing)

    def test_stamp_marks_machine_origin(self):
        """正向：机器改写的痕迹必须永远可辨。"""
        r = normalize_one("k1", {"notes": LOOSE}, "2026-10-02")
        self.assertIn("【格式归一】2026-10-02", r.notes)


class TestClassify(unittest.TestCase):
    def _wiki(self):
        return {"tables": {"papers": {
            "a": {"tags": ["world-sota-A"], "notes": STRICT},
            "b": {"tags": ["lit1000"], "notes": LOOSE},
            "c": {"tags": ["lit1000"], "notes": "做法：短"},
        }}}

    def test_buckets_partition_all_papers(self):
        """正向：三桶互斥且完备 —— 不重不漏，否则漏掉的篇永远没人管。"""
        b = classify(self._wiki())
        all_keys = {x for v in b.values() for x in v}
        self.assertEqual(all_keys, {"a", "b", "c"})
        for name in b:
            for k, v in b.items():
                if name != k:
                    self.assertFalse(set(b[name]) & set(v))

    def test_needs_human_is_not_empty_when_source_incomplete(self):
        """反证：不完整的必须进人工桶，而不是被静默归一化。"""
        b = classify(self._wiki())
        self.assertIn("c", b["needs_human"])
        self.assertNotIn("c", b["normalizable"])


if __name__ == "__main__":
    unittest.main(verbosity=2)