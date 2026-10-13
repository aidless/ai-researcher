"""`verify_all.check_signing_power` 的两向夹具。

判据本身很简单：任何 `demo/runs/*/state.json` 里带着可用私钥 = 被审对象持有签名权力。
简单判据最容易假装在工作，所以两向都要打通：
  A 漏判方向（注入）：往一个合成 run 目录塞 key_priv ⇒ 必须进 FAILS，且那句要点名它能不能被固定表兜住。
  B 误报方向（对照）：同样一份 state.json 但 key_priv=None ⇒ 必须一条都不报。
                       少了这一格，"永远红"和"真的在查"看起来一模一样。
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import verify_all as VA                                              # noqa: E402


def _mk_run(runs: pathlib.Path, name: str, *, priv) -> pathlib.Path:
    run = runs / name
    (run / "round-01" / "artifacts").mkdir(parents=True)
    (run / "round-01" / "artifacts" / "result.json").write_text(
        json.dumps({"confirmed": True}) + "\n", encoding="utf-8")
    (run / "state.json").write_text(json.dumps(
        {"rounds": [], "status": "STOP-REFUTED", "loop_schema": 2, "key_era": "root",
         "key_pub": "ab" * 32, "key_priv": priv}), encoding="utf-8")
    return run


class SigningPower(unittest.TestCase):
    def _run_check(self, runs):
        VA.FAILS.clear()
        VA.NOTES.clear()
        VA.check_signing_power(runs)
        return list(VA.FAILS)

    def test_A_leak_is_caught_and_names_the_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            runs = pathlib.Path(td) / "runs"
            runs.mkdir()
            _mk_run(runs, "leaky-run", priv="cd" * 32)
            fails = self._run_check(runs)
            self.assertEqual(len(fails), 1, fails)
            # 光"报了"不够：那句话必须说清这把钥匙能不能被外部固定表兜住，
            # 否则读的人以为"反正有 pin 就没事"
            self.assertIn("不在任何固定表里", fails[0])
            self.assertIn("leaky-run", fails[0])

    def test_B_clean_tree_reports_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            runs = pathlib.Path(td) / "runs"
            runs.mkdir()
            _mk_run(runs, "clean-run", priv=None)
            _mk_run(runs, "also-clean", priv="")
            self.assertEqual(self._run_check(runs), [], "干净树被误报 = 判据恒红")

    def test_C_unparseable_state_is_not_silently_clean(self):
        with tempfile.TemporaryDirectory() as td:
            runs = pathlib.Path(td) / "runs"
            runs.mkdir()
            (runs / "broken").mkdir(parents=True)
            (runs / "broken" / "state.json").write_text("{not json", encoding="utf-8")
            fails = self._run_check(runs)
            self.assertEqual(len(fails), 1, fails)
            self.assertIn("cannot run", fails[0])

    def test_D_real_tree_is_now_key_free(self):
        """回归护栏：真树必须一份私钥都没有（2026-10-10 工作树清理完成后翻面）。

        这格原本断言 `len(fails) >= 1`，钉住的是 2026-10-09 那次"全量入库"把 28 把可用
        私钥带进树里这个事实（其中 27 份至今仍在 HEAD 的 blob 里，见
        reports/OPEN_ITEMS_20261010.md）。工作树清干净之后期望翻成 **0 并保留**：
        将来任何人再往 run 目录写私钥，这格当场红，而不是等下一轮人工审计再发现。
        删掉这格等于把已经修好的东西重新变回没人查。
        """
        real = pathlib.Path(__file__).resolve().parents[1] / "demo" / "runs"
        fails = self._run_check(real)
        self.assertEqual(fails, [], f"run 目录里又出现私钥: {fails[:2]}")


if __name__ == "__main__":
    unittest.main()
