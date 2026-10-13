#!/usr/bin/env python3
"""把私钥从 run 目录里清出去（默认只 dry-run，不写盘）。

为什么需要这支脚本：信任根那次修复（loop.py 在存盘前把 `key_priv` 置 None）只管住了**之后的写者**，
管不了已经躺在盘上和已经进了 git 历史的那批。现读：`demo/runs/*/state.json` 里 28 份带可用私钥，
其中 27 份同样存在于 HEAD 的提交里，28 把私钥互不相同。被审对象自己持有签名权力时，
"产物被签过"这句话没有任何外部支撑——改产物、用同一把私钥重签、覆盖 key_pub，验签照样绿。

安全边界（都写在代码里，不靠注释）：
  1. 默认 dry-run。要写盘必须显式 `--apply`。
  2. `status == "RUNNING"` 的 run 一律跳过：那是别的会话正在用的对象。
  3. 写之前把原文件整份备份到仓外目录，并记下 md5；写完立刻回读校验（改完不回读等于没改）。
  4. 清完必须重跑一次验签：legacy 判决的合法性来自注册表/固定表里的公钥，不来自 state.json，
     所以私钥拿掉之后 verdict 必须逐条不变。变了就还原。
  5. 本脚本**不碰 git 历史**。历史里那 27 份要单独处理（脚本末尾打印判据与命令），
     而且只要这个仓将来被 push，这些私钥就等同于已泄露。
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "demo" / "runs"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def find_leaks() -> list:
    out = []
    for st in sorted(RUNS.glob("*/state.json")):
        try:
            d = json.loads(st.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  SKIP-UNREADABLE {st.parent.name}: {e}")
            continue
        if d.get("key_priv"):
            out.append((st, d))
    return out


def verify_snapshot() -> dict:
    """跑一次现有验签，把每个 run 的 verdict 记下来（清钥前后要逐条相同）。"""
    sys.path.insert(0, str(ROOT / "src"))
    from ai_researcher import keystore as KS
    res = {}
    for run in sorted(p.parent for p in RUNS.glob("*/state.json")):
        try:
            chk = KS.verify_run(run)
            res[run.name] = {"valid": chk.get("valid"), "reason": str(chk.get("reason"))[:70]}
        except Exception as e:
            res[run.name] = {"valid": None, "reason": f"{type(e).__name__}: {str(e)[:60]}"}
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写盘；不给就只报告")
    ap.add_argument("--backup-dir", default=str(Path.home() / ".ai-researcher-scrub-backup"))
    a = ap.parse_args()

    leaks = find_leaks()
    print(f"带私钥的 state.json: {len(leaks)} 份 | 唯一私钥数: "
          f"{len({str(d.get('key_priv')) for _, d in leaks})} 把")
    # 比对用 run 名而不是路径：git ls-files 给的是相对 cwd 的路径，而 st 是绝对路径，
    # 直接 set  membership 会永远为假（"0 份被跟踪"这种"看起来正常的 0"最危险）。
    tracked = {Path(x).parent.name for x in subprocess.run(
        ["git", "ls-files", "demo/runs"], capture_output=True, text=True, cwd=ROOT).stdout.split()}
    in_git = sum(1 for st, _ in leaks if st.parent.name in tracked)
    print(f"其中被 git 跟踪: {in_git} 份（HEAD 里同样带私钥的要另算，见末尾）")

    if not a.apply:
        print("\nDRY-RUN：没有写任何文件。要写盘加 --apply。")
        for st, d in leaks[:6]:
            print(f"  {st.parent.name:26s} key_priv={str(d['key_priv'])[:10]}… "
                  f"status={d.get('status')} loop_schema={d.get('loop_schema')}")
        if len(leaks) > 6:
            print(f"  …共 {len(leaks)} 份")
        return 0

    skip_live = [(st, d) for st, d in leaks if str(d.get("status")) == "RUNNING"]
    todo = [(st, d) for st, d in leaks if str(d.get("status")) != "RUNNING"]
    stamp = time.strftime("%Y%m%dT%H%M%SZ")
    bdir = Path(a.backup_dir) / stamp
    bdir.mkdir(parents=True, exist_ok=True)

    before = verify_snapshot()
    written = []
    for st, d in todo:
        bak = bdir / f"{st.parent.name}__state.json"
        shutil.copy2(st, bak)
        h_before = md5(st)
        d["key_priv"] = None
        tmp = st.with_suffix(".json.scrubtmp")
        tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, st)                                    # 原子替换，不留半截文件
        back = json.loads(st.read_text(encoding="utf-8"))
        assert back.get("key_priv") is None, f"{st}: 回读仍然有私钥"
        assert back.get("key_pub") == d.get("key_pub"), f"{st}: key_pub 被改动"
        written.append({"run": st.parent.name, "backup": str(bak),
                        "md5_before": h_before, "md5_after": md5(st)})
    print(f"\n写了 {len(written)} 份，跳过 {len(skip_live)} 份（RUNNING，属于别人正在跑的对象）")
    for s in skip_live:
        print("  SKIP-LIVE", s[0].parent.name)

    after = verify_snapshot()
    changed = [k for k in before if before[k] != after.get(k)]
    print("\n验签 verdict 对照（清钥前后必须逐条相同，因为信任来自注册表而不是 run 目录）:")
    print(f"  前: {sum(1 for v in before.values() if v['valid'])} valid / {len(before)} runs")
    print(f"  后: {sum(1 for v in after.values() if v['valid'])} valid / {len(after)} runs")
    if changed:
        print("  !! verdict 变了，说明验签偷偷读过 state.json 的私钥 —— 这是判据要抓的事：")
        for k in changed[:5]:
            print(f"     {k}: {before[k]} -> {after.get(k)}")
        print("  还原目录：%s（cp 回去即可）" % bdir)
        return 2
    print("  verdict 一字未变 ✓")
    print(f"\n备份：{bdir}")
    print("判据（未做，需你点头）：HEAD 里那批提交仍带私钥。要么本仓永不 push，"
          "要么 push 前把这 28 把私钥当作已泄露处理（轮换 + 把相关判决标 non-authoritative）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
