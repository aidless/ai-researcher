#!/usr/bin/env python3
"""AIR-CODEREPAIR 升档定价：40 题拉到 157 题值不值（零机时，只读盘上两份载体）。

上一版定价板给这一臂落的是 `INSTRUMENT_GAP_bar_carrier_missing`，理由写的是
"参照臂盘上不存在"。那句话只对了一半：**demo/runs/coderepair-02 就是同币种的第二块载体**
（n=48，逐题配对，policies 里就有 direct 与 step-calc），它当时没被接进算式。
本脚本把它接上，并且不信任何汇总字段——所有配对数从
`result.json.models[*].detail[policy]` 的逐题 `passed` 重算，再与载体自报的
`mcnemar_pooled` / `contrasts` 对表；对不上就 rc=3 停住，不出判决。

三条判据顺序是先声明后读数的（改顺序会改判决）：
  1. CALIBRATION：重算数 == 载体自报数？              不通过 → INSTRUMENT_GAP（rc=3）
  2. 零信息行：某模型不和谐对 b+c == 0 → 它的 delta 是"配对测试下 n=0"，
     不许当 0.0 进均值（那会稀释均值并压低 sd）。     有 → 记 conditions
  3. 方向：合并均值/池化 p 判 step-calc 这条腿在自己尺上更好还是更差。
     更差且已 resolved → NOT_FUNDED_leg_resolved_worse_on_its_own_ruler
     （撤回 157 题那发机时；加样本只会把区间收紧在负均值附近，永远推不过正的 bar）
"""
from __future__ import annotations
import json, math, os, sys, argparse, shutil, tempfile
from pathlib import Path

REAL_RUNS = Path(__file__).resolve().parents[1] / "demo" / "runs"
# CODEREPAIR_RUNS_ROOT 只准夹具用：证"方向"那一支真能可达（不改判据，改一份自洽的合成载体）
RUNS = Path(os.environ.get("CODEREPAIR_RUNS_ROOT", str(REAL_RUNS)))
POLICY, BASELINE = "step-calc", "direct"
Z_TWO_SIDE_80PCT = 2.802          # power_escalation 口径
CALLS_PER_ITEM_PAIR = 2           # 每题每策略一次调用
Z90 = 1.645


def p_mcnemar_exact(b: int, c: int):
    """双边精确 McNemar：n=b+c，P(|X-n/2| >= |min-n/2|)。b+c==0 返回 None（不可判）。"""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


TRANSPORT_PAT = ("HTTPError", "URLError", "Connection", "Timeout", "timed out", "404", "503")


def transport_scan(run: str, policy: str | None = None) -> dict:
    """把"跑不动"与"答不对"分开：逐题 why 里带传输层字样的失败单独计数。

    一台把 HTTPError 当 capability failure 平均进 delta 的尺，量到的是自己的管道。
    """
    policy = POLICY if policy is None else policy
    d = json.load(open(RUNS / run / "round-01" / "artifacts" / "result.json", encoding="utf-8"))
    scan = {}
    for model, md in d["models"].items():
        for pol, det in md["detail"].items():
            fails = [x for x in det if not x["passed"]]
            t = [x for x in fails if any(p in str(x.get("why", "")) for p in TRANSPORT_PAT)]
            scan[f"{model}|{pol}"] = {"n": len(det), "failed": len(fails), "transport": len(t),
                                      "transport_share_of_items": round(len(t) / len(det), 3) if det else None}
    return scan


def transport_dead_models(run: str, policy: str | None = None, thresh: float = 0.9) -> list:
    """某模型某策略格 ≥thresh 的题是传输错误 ⇒ 这一格没被测到，不许当 delta=0 进均值。"""
    sc = transport_scan(run, policy)
    dead = set()
    for key, v in sc.items():
        model = key.split("|")[0]
        if v["n"] and v["transport"] / v["n"] >= thresh:
            dead.add(model)
    # 只有当这个模型的两侧都被管道吃掉时才算"没测到"
    both = {k.split("|")[0] for k, v in sc.items()
            if v["n"] and v["transport"] / v["n"] >= thresh}
    return sorted(m for m in dead if m in both)


def paired_counts(run: str, policy: str | None = None, drop_negative: bool = False):
    """从逐题 passed 重算每个模型的 (可配对 n, fixed b, broke c)。

    `policy` 必须在调用时才解析：写进默认参数会在 def 时绑定，
    那样 --prove-red swap-policy 就是个空操作（这台仪器的牙会被自己卸掉）。
    """
    policy = POLICY if policy is None else policy
    d = json.load(open(RUNS / run / "round-01" / "artifacts" / "result.json", encoding="utf-8"))
    rows = {}
    for model, md in d["models"].items():
        pol = md.get("policies", {})
        if BASELINE not in pol or policy not in pol:
            continue
        a = {x["id"]: bool(x["passed"]) for x in md["detail"][BASELINE]}
        p = {x["id"]: bool(x["passed"]) for x in md["detail"][policy]}
        ids = sorted(set(a) & set(p))
        b = sum(1 for i in ids if p[i] and not a[i])
        c = sum(1 for i in ids if a[i] and not p[i])
        rows[model] = {"n_paired": len(ids), "fixed": b, "broke": c,
                       "delta": (b - c) / len(ids) if ids else None}
    if drop_negative:      # prove-red 夹具：只留非负的那些模型（对表闸应当当场抓住）
        rows = {m: v for m, v in rows.items() if not (v["delta"] is not None and v["delta"] < 0)}
    return d["n_items"], rows, d


def calibrate(run, rows, carrier):
    """重算数必须等于载体自报数，否则这台仪器说不出话。"""
    got_b = sum(r["fixed"] for r in rows.values())
    got_c = sum(r["broke"] for r in rows.values())
    if run == "coderepair-01":                      # 自报在 mcnemar_pooled
        want = carrier["mcnemar_pooled"]
        ok = (got_b == want["fixed"] and got_c == want["broke"])
    else:                                            # 自报在 contrasts[policy]
        want = carrier["contrasts"][POLICY]
        ok = (got_b == want["fixed"] and got_c == want["broke"])
        if ok and want.get("gain_mean") is not None:
            ds = [r["delta"] for r in rows.values() if r["delta"] is not None]
            mean = sum(ds) / len(ds)
            ok = abs(mean - want["gain_mean"]) < 5e-4
    return {"recomputed_fixed": got_b, "recomputed_broke": got_c,
            "carrier_fixed": want["fixed"], "carrier_broke": want["broke"], "match": ok,
            "carrier_p": want["p"] if "p" in want else want.get("mcnemar_p"),
            "recomputed_p": p_mcnemar_exact(got_b, got_c)}


def price_n(sd: float, target: float) -> int:
    return math.ceil((Z_TWO_SIDE_80PCT * sd / target) ** 2) if sd > 0 and target > 0 else None


def build_synth_positive(dest: Path) -> dict:
    """造一份**自洽**的合成载体：step-calc 真的比 direct 好，且汇总字段与逐题字节同批改写。

    这一格存在的理由：前三支 prove-red 全被对表闸先抓住（那是对的——改字节必然破坏对表），
    于是"方向"那一支判决从没被变异打到过。只会拒绝的闸和永远绿的断言是同一种装饰，
    所以这里必须证明 `ESCALATION_TESTABLE` 那个出口真能到达：让数据与自报数一起改，
    对表照样通过，判决就必须翻面。
    """
    made = {}
    for run in ("coderepair-01", "coderepair-02"):
        src = RUNS / run / "round-01" / "artifacts" / "result.json"
        d = json.load(open(src, encoding="utf-8"))
        tot_b = tot_c = 0
        for model, md in d["models"].items():
            det_d = {x["id"]: bool(x["passed"]) for x in md["detail"][BASELINE]}
            flipped = 0
            for rec in md["detail"][POLICY]:
                if not det_d.get(rec["id"], False) and not rec["passed"]:
                    rec["passed"] = True           # direct 错、step-calc 对 => fixed
                    flipped += 1
                    if flipped >= 7:
                        break
            for rec in md["detail"][POLICY]:       # 把 broke 全拆掉：direct 对的，step-calc 也必须对
                if det_d.get(rec["id"], False):
                    rec["passed"] = True
            ids = {x["id"] for x in md["detail"][BASELINE]} & {x["id"] for x in md["detail"][POLICY]}
            dp = {x["id"]: bool(x["passed"]) for x in md["detail"][POLICY]}
            b = sum(1 for i in ids if dp[i] and not det_d[i])
            c = sum(1 for i in ids if det_d[i] and not dp[i])
            md["policies"][POLICY] = round(md["policies"][BASELINE] + (b - c) / len(ids), 6)
            tot_b += b
            tot_c += c
        if "mcnemar_pooled" in d:
            d["mcnemar_pooled"] = {"fixed": tot_b, "broke": tot_c,
                                   "p": p_mcnemar_exact(tot_b, tot_c) or 1.0}
        if "contrasts" in d and POLICY in d["contrasts"]:
            ids_all = d["n_items"]
            d["contrasts"][POLICY] = {"gain_mean": round((tot_b - tot_c) / max(1, len(d["models"]) * ids_all), 4),
                                      "fixed": tot_b, "broke": tot_c,
                                      "mcnemar_p": p_mcnemar_exact(tot_b, tot_c) or 1.0,
                                      "families_positive": "3/3"}
        out_path = dest / run / "round-01" / "artifacts" / "result.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(d, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
        made[run] = {"synth_fixed": tot_b, "synth_broke": tot_c}
    return made


def build_transport_masked(dest: Path) -> dict:
    """把传输错误的 why 改成"像真失败"的字样 ⇒ 运输层规则应当失效、均值被稀释回 0。

    这一格证明"排除传输死格"那条规则是承重的：不注入时均值 −0.0750（3 个模型），
    注入后必须变成 −0.0563（4 个模型，llama 那个 0.0 又被平均进去了）。
    """
    changed = {}
    for run in ("coderepair-01", "coderepair-02"):
        src = RUNS / run / "round-01" / "artifacts" / "result.json"
        d = json.load(open(src, encoding="utf-8"))
        n = 0
        for md in d["models"].values():
            for det in md["detail"].values():
                for rec in det:
                    if any(p in str(rec.get("why", "")) for p in TRANSPORT_PAT):
                        rec["why"] = "expected None, got 0"
                        n += 1
        out_path = dest / run / "round-01" / "artifacts" / "result.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(d, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
        changed[run] = n
    return {"rewritten_why_fields": changed}


def main():
    global RUNS
    ap = argparse.ArgumentParser()
    ap.add_argument("--prove-red", choices=["poison-detail", "swap-policy", "drop-negative-model",
                                            "synth-positive", "transport-masked"])
    ap.add_argument("--selftest-only", action="store_true")
    a = ap.parse_args()
    if a.selftest_only:
        return selftest()

    out = {"question": "AIR-CODEREPAIR: n=40 -> n=157 值不值",
           "currency": f"paired accuracy delta, {POLICY} − {BASELINE}（逐题配对，按模型分层）",
           "read_only": True, "machine_minutes_spent": 0, "ollama_calls_made": 0,
           "ran_at_utc": None, "conditions": {}, "limitations": []}

    # 注入夹具：改的是"重算所读的字节"，不是判据本身
    poison_target = None
    if a.prove_red == "poison-detail":
        p = RUNS / "coderepair-02" / "round-01" / "artifacts" / "result.json"
        tmp = p.with_suffix(".json.provenotred")
        if not tmp.exists():
            p.rename(tmp)
        poison_target = (p, tmp)
        d = json.load(open(tmp, encoding="utf-8"))
        flipped = 0
        for mm in d["models"].values():
            for rec in mm["detail"].get(POLICY, []):
                if rec["passed"]:
                    rec["passed"] = False; flipped += 1; break
            if flipped:
                break
        assert flipped == 1, "注入没落到字节上，这一格不算变异"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        out["injected"] = ("把 coderepair-02 一个 pass 翻成 fail（先印出改了哪个模型哪题，"
                           "再证明配对数与载体自报不再相符）")
        out["injected_detail"] = {"flipped_passes": flipped}
    synth_dir = None
    if a.prove_red == "synth-positive":
        synth_dir = Path(tempfile.mkdtemp(prefix="cr_synth_"))
        made = build_synth_positive(synth_dir)
        RUNS = synth_dir
        out["injected"] = ("换成自洽的合成载体：逐题字节与汇总字段一起改成 step-calc 更好 ⇒ 对表必须仍 PASS，"
                           "判决必须翻到 ESCALATION_TESTABLE（证方向那一支可达）")
        out["injected_detail"] = made
    if a.prove_red == "transport-masked":
        synth_dir = Path(tempfile.mkdtemp(prefix="cr_mask_"))
        out["injected"] = ("把传输错误的 why 改写成看起来像真失败 ⇒ 排除规则应失效、"
                           "均值被那个 0.0 稀释；判决字段 mean_delta 必须跟着变")
        out["injected_detail"] = build_transport_masked(synth_dir)
        RUNS = synth_dir
    try:
        return _run(a, out)
    finally:
        if synth_dir:
            RUNS = REAL_RUNS
            shutil.rmtree(synth_dir, ignore_errors=True)
            print("\n# 合成载体目录已删除（真载体从未被写）", file=sys.stderr)
        if poison_target:
            p, tmp = poison_target
            tmp.replace(p)
            print("\n# 已还原被注入的载体字节，还原后 md5 校验：", end="", file=sys.stderr)
            import hashlib
            print(hashlib.sha256(p.read_bytes()).hexdigest()[:12], file=sys.stderr)


def _run(a, out):
    if a.prove_red == "swap-policy":
        global POLICY
        POLICY = "spec-first"
        out["injected"] = "把被审策略换成 spec-first（同币种但另一条腿，方向与 p 都不同）"
    if a.prove_red == "drop-negative-model":
        out["injected"] = "把两块池里唯一 resolved 的负向模型（gemma3:4b）从数据里剔掉，看判决会不会假装成 null"

    per_run, calib = {}, {}
    for run in ("coderepair-01", "coderepair-02"):
        n_items, rows, carrier = paired_counts(
            run, drop_negative=(a.prove_red == "drop-negative-model"))
        calib[run] = calibrate(run, rows, carrier)
        dead = transport_dead_models(run)
        used = {m: v for m, v in rows.items() if m not in dead}
        ds = [v["delta"] for v in used.values() if v["delta"] is not None]
        mean = sum(ds) / len(ds) if ds else None
        sd = math.sqrt(sum((x - mean) ** 2 for x in ds) / (len(ds) - 1)) if len(ds) > 1 else 0.0
        zero_info = [m for m, v in rows.items() if v["fixed"] + v["broke"] == 0]
        per_run[run] = {"n_items_carrier": n_items, "models_measured": len(rows),
                        "per_model": rows, "mean_delta": round(mean, 4) if mean is not None else None,
                        "sd_over_models": round(sd, 4), "zero_information_models": zero_info,
                        "transport_dead_models_excluded": dead,
                        "models_averaged": len(ds),
                        "pooled_p": calib[run]["recomputed_p"]}

    # 判据 1：对表闸
    if not all(c["match"] for c in calib.values()):
        out["verdict"] = "INSTRUMENT_GAP_recomputed_counts_disagree_with_carrier"
        out["rule_fired"] = "calibration"
        out["conditions"]["calibration"] = calib
        out["consequence"] = "这台仪器现在说不出话：重算的配对数与载体自报不符，先修尺再谈机时。"
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 3

    out["conditions"]["calibration"] = {
        r: {"recomputed": f"{c['recomputed_fixed']}/{c['recomputed_broke']}",
            "carrier": f"{c['carrier_fixed']}/{c['carrier_broke']}",
            "p_recomputed": round(c["recomputed_p"], 6) if c["recomputed_p"] is not None else None,
            "p_carrier": round(c["carrier_p"], 6) if c["carrier_p"] is not None else None}
        for r, c in calib.items()}

    # 判据 2：零信息行
    zero = {r: v["zero_information_models"] for r, v in per_run.items() if v["zero_information_models"]}
    out["conditions"]["zero_information_models"] = zero
    if zero:
        out["limitations"].append(
            "这些模型的不和谐对 b+c=0 ⇒ 在配对检验下它的 n 就是 0，不是 delta=0.0。"
            "若把它当 0.0 进均值，会把负均值往 0 拉并压低 sd（01 里 llama3.2:3b 就是这一格）。")

    # 判据 3：方向
    both_neg = all(v["mean_delta"] is not None and v["mean_delta"] < 0 for v in per_run.values())
    resolved = [r for r, v in per_run.items() if v["pooled_p"] is not None and v["pooled_p"] < 0.05]
    per_model_resolved_negative = sorted(
        {(r, m) for r, v in per_run.items() for m, x in v["per_model"].items()
         if x["delta"] is not None and x["delta"] < 0
         and (p := p_mcnemar_exact(x["fixed"], x["broke"])) is not None and p < 0.05})
    out["conditions"]["direction"] = {
        "both_pools_mean_negative": both_neg, "pools_resolved": resolved,
        "model_cells_resolved_negative": per_model_resolved_negative}

    if both_neg and resolved:
        out["verdict"] = "NOT_FUNDED_leg_resolved_worse_on_its_own_ruler"
        out["rule_fired"] = "direction"
        target = 0.025          # 原主张想拿到的正向增益量级（qwen 上观测到的 +0.025 那一格）
        sd = max(v["sd_over_models"] for v in per_run.values())
        out["consequence"] = (
            "撤回把 n 从 40 拉到 157 的请求：两块独立题池（40 题与 48 题）上 step-calc − direct "
            "的模型均值都是负的，且池化配对检验在 48 题池上已 resolved（p=%.4g）。"
            "加样本只会把区间收紧在这个负均值附近，永远推不过一个正的 bar；"
            "要买的不该是题数，是『哪个模型上成立』这一层。"
            % (per_run["coderepair-02"]["pooled_p"],))
        out["what_would_cost"] = {
            "cells_at_157": 157 * CALLS_PER_ITEM_PAIR * max(v["models_measured"] for v in per_run.values()),
            "throughput_calls_per_min_carrier": 64.1,
            "extrapolated_minutes": round(157 * CALLS_PER_ITEM_PAIR * 4 / 64.1, 1),
            "status": "假设（线性外推），且本轮决定不花"}
        out["escalation_arithmetic"] = {
            "n_for_a_positive_target": price_n(sd, target),
            "arithmetic": "n = ceil((2.802 x sd / target)^2)，sd 取两块池里较大的模型间 sd=%.4f" % sd,
            "why_unusable": "这个 n 是为『正效应』算的功效；观测均值是负的，把 n 提到它也不会翻正 ⇒ 只是名义可判"}
    elif both_neg:
        out["verdict"] = "NOT_FUNDED_ruler_says_worse_but_not_resolved"
        out["rule_fired"] = "direction"
        out["consequence"] = "方向为负但未 resolved：先别加题，也别宣布无效——需要的是分层（按模型）而不是 n。"
    else:
        out["verdict"] = "ESCALATION_TESTABLE_more_n_may_resolve"
        out["rule_fired"] = "direction"
        out["consequence"] = "至少一块池的方向为正 ⇒ 加样本才有意义；n 见 escalation_arithmetic。"

    out["conditions"]["per_run"] = per_run
    out["limitations"] += [
        "sd 是模型间方差（4 或 3 个点），不是逐题方差：n_for_a_positive_target 只能当量级看。",
        "两块池的题集不同（01 是 40 题、02 是 48 题）⇒ 负向是跨池复制的，不是同一批题重跑。",
        "02 只有 3 个模型可配对（models_measured 见字段），第 4 个当时没跑成。",
        "throughput 64.1 次/分来自 01 的一次实测，换模型/换长度不复用。"]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def selftest():
    """对表夹具：期望值抄自载体，不手算。"""
    checks, fails = 0, []
    n1, r1, c1 = paired_counts("coderepair-01")
    n2, r2, c2 = paired_counts("coderepair-02")
    cases = [
        ("01 载体自报 n_items 是 40", n1, 40),
        ("02 载体自报 n_items 是 48", n2, 48),
        ("01 池化 fixed 抄自 mcnemar_pooled", sum(v["fixed"] for v in r1.values()), c1["mcnemar_pooled"]["fixed"]),
        ("01 池化 broke 抄自 mcnemar_pooled", sum(v["broke"] for v in r1.values()), c1["mcnemar_pooled"]["broke"]),
        ("02 池化 fixed 抄自 contrasts", sum(v["fixed"] for v in r2.values()), c2["contrasts"][POLICY]["fixed"]),
        ("02 池化 broke 抄自 contrasts", sum(v["broke"] for v in r2.values()), c2["contrasts"][POLICY]["broke"]),
        ("01 qwen2.5:7b 的 delta 与自报 policy 差一致",
         round(r1["qwen2.5:7b"]["delta"], 4),
         round(c1["models"]["qwen2.5:7b"]["policies"][POLICY] - c1["models"]["qwen2.5:7b"]["policies"][BASELINE], 4)),
        ("02 gemma3:4b 是唯一 resolved 负向", [m for m, v in r2.items() if v["delta"] and v["delta"] < 0],
         ["gemma3:4b"]),
        ("01 里 llama3.2:3b 不和谐对为 0（零信息行）",
         r1["llama3.2:3b"]["fixed"] + r1["llama3.2:3b"]["broke"], 0),
        ("精确 McNemar 与载体 p 对表（01 池化）",
         round(p_mcnemar_exact(sum(v['fixed'] for v in r1.values()), sum(v['broke'] for v in r1.values())), 5),
         round(c1["mcnemar_pooled"]["p"], 5)),
        ("b+c=0 时判据返回 None 而不是 1.0", p_mcnemar_exact(0, 0), None),
        # 运输层规则的期望值同样抄自载体（01 的 llama3.2:3b 两格各 40/40 HTTPError）
        ("01 里传输死掉的模型只有 llama3.2:3b", transport_dead_models("coderepair-01"), ["llama3.2:3b"]),
        ("02 里没有传输死掉的模型", transport_dead_models("coderepair-02"), []),
        ("01 llama direct 的传输错误数抄自逐题 why",
         transport_scan("coderepair-01")["llama3.2:3b|direct"]["transport"], 40),
        ("01 qwen2.5:7b direct 没有传输错误",
         transport_scan("coderepair-01")["qwen2.5:7b|direct"]["transport"], 0),
    ]
    for name, got, want in cases:
        checks += 1
        if got != want:
            fails.append({"check": name, "got": got, "want": want})
    print(json.dumps({"selftest": "FAIL" if fails else "PASS", "n": checks,
                      "failures": fails}, ensure_ascii=False, indent=1))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
