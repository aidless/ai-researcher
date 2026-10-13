#!/usr/bin/env python3
"""判据回填器：把「缺判据/缺观测」的阻塞提案，读原论文后定出可跑实验。

## 它解决什么

store 里 41 条被阻塞提案的 blocking_reason 全是同一族：「缺判据/缺观测/缺对象
——需回原论文补齐后才能定实验」。这不是技术天花板，是**信息缺口**：压缩过的
笔记里没有可判定的比较与可观测量，而原文里有。

## 它绝不做什么（铁律）

1. **绝不编造实验设计**：每个字段只能来自原文（abstract/HTML 正文）里逐字
   出现的数字与设定；抽不到就标 `insufficient_fields` 并保持阻塞。
2. **绝不改 store 状态**：只产出 `store/w10_criteria.json`（回填证据 + 判决），
   迁移是 store.transition 的事，且需人工批准（本脚本不给已批）。
3. **不联网写回 wiki**：arXiv 抓取只读，落盘只进 ai-researcher/store/。
4. 抓取失败（网络/改版/付费墙）⇒ 该条标 `fetch_failed`，保持阻塞，不猜。

## 判决口径（fail-closed）

对每条提案，从原文提取四类可判定要素：
  - benchmark/数据集名（用于判定「数据可得性」）
  - 主指标定义与方向（higher_is_better / lower_is_better）
  - 可复现的规模数字（模型规模、数据量、采样数等，逐字带出处句）
  - 官方数据可得性（URL/许可线索）

判定 `verdict ∈ {measurable, needs_decomposition, insufficient}`：
  - measurable：有 ≥1 个可指认评测对象 + ≥1 个可算指标 + ≥1 个可比锚数字
    ⇒ 交人工批准后才可跑；本脚本只给「可测量」结论，不给已批。
  - needs_decomposition：对象/指标齐但规模超出本机（如需多卡/大模型）⇒
    建议拆到本机可跑的子问题。
  - insufficient：抓不到或要素不足 ⇒ 保持阻塞。

## 用法

    python3 scripts/w10_criteria_fill.py --selftest
    python3 scripts/w10_criteria_fill.py --limit 5           # 试跑前 5 条
    python3 scripts/w10_criteria_fill.py --ids 2312.11361v3 # 指定
"""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(ROOT, "ai-researcher", "store")
STATE_PATH = os.path.join(STATE_PATH_DEFAULT := os.path.join(STORE, "proposals_state.json"))
OUT_PATH = os.path.join(STORE, "w10_criteria.json")
UA = "Mozilla/5.0 (compatible; local-research/1.0)"

# 指标词典：出现即视为「可算指标」，带方向
METRIC_PATTERNS = [
    (r"\baccuracy\b|\bacc\b|准确率", "accuracy", "higher"),
    (r"\bF1\b|\bF-?score\b|\bmacro-?F1\b", "f1", "higher"),
    (r"\bprecision\b|精确率", "precision", "higher"),
    (r"\brecall\b|召回率", "recall", "higher"),
    (r"\bMRR\b|\bnDCG\b|\bNDCG\b|\bRecall@\d+|\bHits?@\d+|\bEM\b",
     "ranking_metric", "higher"),
    (r"\bhallucination rate\b|幻觉率", "hallucination_rate", "lower"),
    (r"\bperplexity\b|\bPPL\b|困惑度", "ppl", "lower"),
    (r"\bpass@\d+|\bpass rate\b|通过率", "pass_rate", "higher"),
    (r"\bASR\b|\battack success rate\b|越狱成功率", "attack_success", "lower"),
    (r"\bMMR\b|\bMAE\b|\bRMSE\b|误差", "error_metric", "lower"),
    (r"\bthroughput\b|\blatency\b|\btokens/s\b|\b延迟", "efficiency", "lower"),
    (r"\bAUROC\b|\bAUC\b|\bFPR\b|\bTPR\b", "auc", "higher"),
    (r"\bwin rate\b|\belo\b|\bElo\b|胜率", "win_rate", "higher"),
]
BENCHMARK_HINT = re.compile(
    # 具体基准名（已知清单；不收 MATH/ARC/DROP 这类过泛的普通词）
    r"\b(?:GSM\d*k|MMLU(?:-?Pro)?|SWE-?bench\w*|HumanEval\w*|MBPP\w*|AGIEval|"
    r"TruthfulQA|JailbreakBench|NoMIRACL|MIRACL\w*|MSMARCO|MS MARCO|TREC\w*|"
    r"RAGAS\w*|BBH|BIG-?Bench\w*|HotpotQA|HellaSwag|WikiQA|SQuAD\w*|"
    r"Natural Questions|Glue\w*|SQuAD)\b"
    # 泛化：xxx-bench / xxxBench 族
    r"|\b[A-Za-z][A-Za-z0-9_\-]{1,}[Bb]ench\w*\b", re.I)
MODEL_SIZE_HINT = re.compile(
    r"\b(\d+(?:\.\d+)?\s?[BM]\b(?=\s*(?:param|parameter|model))|"
    r"\b\d+B\b|\b\d+\.\d+B\b|\b\d+M\b)")
DATA_SIZE_HINT = re.compile(
    r"([\d,]{3,})\s*(examples|samples|questions|queries|documents|"
    r"instances|test cases|problems|items)")
CODE_URL_HINT = re.compile(r"https?://(?:github\.com|huggingface\.co)/[^\s\"'<>)]+")


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">")
              .replace("&quot;", '"').replace("&#x27;", "'"))
    return re.sub(r"[ \t]+", " ", txt)


def fetch_arxiv(aid: str, timeout: int = 60) -> dict:
    """只读抓 abs + html；任何失败都显式返回，绝不静默编造。"""
    base = aid.split("v")[0]
    out = {"arxiv_id": aid, "abs_ok": False, "html_ok": False,
           "abstract": "", "body": "", "error": []}
    url = f"https://arxiv.org/abs/{base}"
    try:
        r = subprocess.run(["curl", "-sSL", "-m", str(timeout), "-A", UA, url],
                           capture_output=True, timeout=timeout + 15)
        html = r.stdout.decode("utf-8", "ignore")
        if r.returncode == 0 and "Abstract" in html:
            out["abs_ok"] = True
            m = re.search(r'(?is)<blockquote class="abstract[^"]*">(.*?)</blockquote>',
                          html)
            if m:
                out["abstract"] = strip_html(m.group(1)).strip()
    except Exception as e:                                  # noqa: BLE001
        out["error"].append(f"abs: {type(e).__name__}")
    try:
        r = subprocess.run(["curl", "-sSL", "-m", str(timeout), "-A", UA,
                            f"https://arxiv.org/html/{base}"],
                           capture_output=True, timeout=timeout + 15)
        html = r.stdout.decode("utf-8", "ignore")
        if r.returncode == 0 and len(html) > 5000 and "<html" in html.lower():
            out["html_ok"] = True
            out["body"] = strip_html(html)
    except Exception as e:                                  # noqa: BLE001
        out["error"].append(f"html: {type(e).__name__}")
    return out


def _sentences_with(text: str, pattern: re.Pattern, limit: int = 4) -> list[dict]:
    """返回逐字出处句（数字必须能追到具体句子，不能只给总数）。"""
    hits = []
    for m in pattern.finditer(text):
        s = text.rfind(".", 0, m.start()) + 1
        e = text.find(".", m.end())
        e = e if e > 0 else m.end() + 120
        sent = text[s:e].strip()
        if 12 <= len(sent) <= 400 and sent not in hits:
            hits.append({"value": m.group(0), "quote": sent})
        if len(hits) >= limit:
            break
    return hits


def extract_criteria(fetch: dict) -> dict:
    text = (fetch.get("abstract") or "") + "\n" + (fetch.get("body") or "")
    text = re.sub(r"\s+", " ", text)
    metrics = []
    for pat, name, direction in METRIC_PATTERNS:
        hits = _sentences_with(text, re.compile(pat, re.I), limit=2)
        if hits:
            metrics.append({"metric": name, "direction": direction,
                            "evidence": hits})
    benches = _sentences_with(text, BENCHMARK_HINT, limit=3)
    sizes = _sentences_with(text, MODEL_SIZE_HINT, limit=3)
    datas = _sentences_with(text, DATA_SIZE_HINT, limit=3)
    urls = []
    for u in CODE_URL_HINT.findall(text or fetch.get("body", "")):
        if u not in urls:
            urls.append(u)
        if len(urls) >= 3:
            break
    return {"metrics": metrics, "benchmarks": benches, "model_sizes": sizes,
            "data_sizes": datas, "asset_urls": urls,
            "has_text": bool(text.strip())}


def judge(crit: dict) -> dict:
    """fail-closed：要素不足 ⇒ insufficient（保持阻塞），绝不乐观放行。"""
    n_metric = len({m["metric"] for m in crit["metrics"]})
    n_bench = len(crit["benchmarks"])
    n_anchor = len(crit["model_sizes"]) + len(crit["data_sizes"])
    missing = []
    if n_bench == 0:
        missing.append("评测对象")
    if n_metric == 0:
        missing.append("可算指标")
    if n_anchor == 0:
        missing.append("可比锚数字")
    if missing:
        return {"verdict": "insufficient", "missing_fields": missing,
                "note": "原文抓取到但要素不足或抓取失败，保持阻塞，不猜"}
    return {"verdict": "measurable", "missing_fields": [],
            "note": "要素齐；跑批前仍需人工批准 + 本机能力测量（store 门不变）"}


def _atomic_dump(payload: dict, out_path: str) -> None:
    """原子落盘：先写临时文件再 replace —— 半截文件绝不会取代上一份好数据。

    实测教训：跑全量 41 条时进程被系统回收，旧的「末尾一次性 json.dump」
    让已抓的 22 条全丢，落盘只剩试跑那 5 条。逐条落盘后，被回收只会丢
    当前这一条。
    """
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, out_path)


def _payload(items: dict) -> dict:
    return {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": "w10_criteria_fill.py",
            "policy": "只读 arXiv；不编造；不改 store；insufficient 保持阻塞",
            "items": items}


def process(aids: list[str], out_path: str = OUT_PATH,
            sleep_s: float = 2.0, fresh: bool = False,
            retry: int = 1) -> dict:
    prev = {}
    if os.path.exists(out_path) and not fresh:
        prev = json.load(open(out_path, encoding="utf-8")).get("items", {})
    items = dict(prev)
    for aid in aids:
        f = fetch_arxiv(aid)
        # 抓取抖动是真缺陷（见 L-ops-182）：同一 id 两轮可翻转。重试仍失败
        # 才落 insufficient，并显式标 fetch_failed，让汇总能把「没抓到」
        # 与「原文确实没有」分开计数。
        attempt = 0
        while not (f["abs_ok"] or f["html_ok"]) and attempt < retry:
            attempt += 1
            time.sleep(5 * attempt)
            f = fetch_arxiv(aid)
        crit = extract_criteria(f) if (f["abs_ok"] or f["html_ok"]) else {
            "metrics": [], "benchmarks": [], "model_sizes": [],
            "data_sizes": [], "asset_urls": [], "has_text": False}
        j = judge(crit)
        j["fetch_failed"] = not (f["abs_ok"] or f["html_ok"])
        items[aid] = {
            "fetch": {k: f[k] for k in ("abs_ok", "html_ok", "error")},
            "criteria": crit, "judge": j,
            "attempts": attempt + 1,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        print(f"{aid}: {j['verdict']} "
              f"metric={len({m['metric'] for m in crit['metrics']})} "
              f"bench={len(crit['benchmarks'])} "
              f"anchor={len(crit['model_sizes']) + len(crit['data_sizes'])}"
              f"{' [抓取失败]' if j['fetch_failed'] else ''}"
              f"{f' (重试{attempt}次)' if attempt else ''}",
              flush=True)
        _atomic_dump(_payload(items), out_path)   # 逐条落盘，被回收只丢这一条
        time.sleep(sleep_s)
    payload = _payload(items)
    _atomic_dump(payload, out_path)
    return payload


def blocked_ids(state_path: str = STATE_PATH) -> list[str]:
    d = json.load(open(state_path, encoding="utf-8"))
    return [e["arxiv_id"] for e in d["entries"] if e["state"] == "被阻塞"]


def selftest() -> int:
    bad = []

    def ck(name, got, want):
        if got != want:
            bad.append(f"{name}: got {got!r} want {want!r}")

    # strip_html：去标签保留正文
    ck("去标签", strip_html("<p>Hello <b>world</b></p>").strip(), "Hello world")
    ck("去script", "alert" not in strip_html("<script>alert(1)</script><p>x</p>"), True)

    # extract_criteria：合成正文里的指标/基准/规模都能抽出，且带逐字出处
    body = ("We evaluate on GSM8K and MATH benchmarks using accuracy and F1. "
            "Our 7B model is trained on 5000 examples from the Pile. "
            "Code is at https://github.com/example/thing")
    crit = extract_criteria({"abstract": "", "body": body, "abs_ok": False,
                             "html_ok": True})
    names = {m["metric"] for m in crit["metrics"]}
    ck("抽到 accuracy", "accuracy" in names, True)
    ck("抽到 f1", "f1" in names, True)
    ck("方向对", next(m["direction"] for m in crit["metrics"]
                      if m["metric"] == "accuracy"), "higher")
    ck("抽到基准", len(crit["benchmarks"]) > 0, True)
    ck("抽到规模", len(crit["model_sizes"]) + len(crit["data_sizes"]) > 0, True)
    ck("抽到资源链接", crit["asset_urls"] == ["https://github.com/example/thing"], True)
    ck("出处句非空", all(m["evidence"][0]["quote"] for m in crit["metrics"]), True)

    # judge：要素齐 ⇒ measurable；缺对象/指标/锚 ⇒ insufficient（fail-closed）
    full = {"metrics": [{"metric": "accuracy"}], "benchmarks": [{"value": "GSM8K"}],
            "model_sizes": [{"value": "7B"}], "data_sizes": []}
    ck("要素齐可测量", judge(full)["verdict"], "measurable")
    for drop in ("benchmarks", "metrics", "model_sizes"):
        part = dict(full)
        part[drop] = []
        if drop == "model_sizes":
            part["data_sizes"] = []
        ck(f"缺{drop}⇒insufficient", judge(part)["verdict"], "insufficient")
    ck("全空⇒insufficient",
       judge({"metrics": [], "benchmarks": [], "model_sizes": [],
              "data_sizes": []})["verdict"], "insufficient")

    # 抓取失败不得编造：空文本 ⇒ 无指标
    empty = extract_criteria({"abstract": "", "body": "", "abs_ok": False,
                              "html_ok": False})
    ck("空文本无指标", empty["metrics"], [])
    ck("空文本判阻塞", judge(empty)["verdict"], "insufficient")

    # 逐条原子落盘：进程在循环中被回收也必须保住已完成条目
    # （反证：旧实现末尾才 json.dump，被回收 ⇒ 已抓条目全丢）
    with tempfile.TemporaryDirectory() as td:
        op = os.path.join(td, "criteria.json")
        first = {"x": {"judge": {"verdict": "measurable"}}}
        _atomic_dump(_payload(first), op)
        ck("原子落盘可读回", json.load(open(op))["items"]["x"]["judge"]["verdict"],
           "measurable")
        ck("不留临时文件", os.path.exists(op + ".tmp"), False)
        # 续跑：新一批只追加，旧条目不被覆盖
        _atomic_dump(_payload({**first, "y": {"judge": {"verdict": "insufficient"}}}),
                     op)
        got2 = json.load(open(op))["items"]
        ck("续跑保留旧条目", sorted(got2) == ["x", "y"], True)

    # 幂等：同文本两次抽取结果一致（不因时间/顺序漂移）
    c1 = extract_criteria({"abstract": "acc on GSM8K with 7B", "body": "",
                           "abs_ok": True, "html_ok": False})
    c2 = extract_criteria({"abstract": "acc on GSM8K with 7B", "body": "",
                           "abs_ok": True, "html_ok": False})
    ck("幂等", c1 == c2, True)

    print(f"selftest: {len(bad)} 处失败")
    for x in bad:
        print("  FAIL", x)
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    args = sys.argv[1:]
    if "--ids" in args:
        aids = args[args.index("--ids") + 1].split(",")
    else:
        aids = blocked_ids()
        if "--limit" in args:
            aids = aids[:int(args[args.index("--limit") + 1])]
    if not aids:
        print("无待处理提案")
        return 0
    fresh = "--fresh" in args
    retry = 2 if "--retry2" in args else 1
    payload = process(aids, fresh=fresh, retry=retry)
    by = {}
    for v in payload["items"].values():
        by[v["judge"]["verdict"]] = by.get(v["judge"]["verdict"], 0) + 1
    print("汇总:", by, "→", OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())