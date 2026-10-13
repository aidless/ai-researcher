"""L0 扫描器：从已有笔记里抽研究问题。**只读，永不写 wiki。**

## 它为什么存在

AI 全自动研究员的第一层不该是"去找新论文"——那个 dots-agent 已经在做了。
它该做的是把**已经读过的一千多篇笔记里的开放点**变成待验证的假设。那是
别人没有的输入，而且是已经付过阅读成本的那种。

实测（2026-10-02）：`research_wiki` 1037 篇三段齐备笔记里 1037 条能抽出
【开放点】，扣掉过短的还剩约七成可判定。

## 它绝不做什么

- **不写 `research_wiki.json`**。那是跨会话共享、无锁、别的线也在写的
  真相源（AGENTS.md 铁律 6）。本模块只产出候选清单，由上层带门禁落盘。
- **不改写笔记内容**。问题是从开放点**推导**出来的，推导结果单独存，
  原文一个字不动。
- **不用标题猜内容**。抽取失败就是失败，计入 rejected，不补位。

## 抽取器的坑（自己踩的，已修）

第一版终止符写成"下一段标记（【与本项目关系】）"，结果 **343/1037 篇**
把【与本项目关系】整段吞进【开放点】——因为有些笔记的段序不是三段固定序，
还夹着 `【格式归一】` 这类戳。表现为"48% 的开放点无法分类"，那 48% 根本
不是噪声，是抽取器的 bug。

修法：终止符认**任何** `【…】` 标记（`【[^】]{2,8}】`），而不是枚举下一段。
教训：**终止符不该枚举"接下来是什么"，该认"边界长什么样"**。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict, field
from typing import Any, Iterator

WIKI = os.path.expanduser("~/.dsh/storages/research_wiki.json")
SECTIONS = ("做法", "开放点", "与本项目关系")
# 通用终止符：任何 2–8 字的【标记】都算边界（戳、段名、别的标记都挡住）
_BOUNDARY = r"【[^】]{2,8}】"
_ANY_MARK = re.compile(r"【[^】]{2,8}】")

# 开放点最短有效长度：低于此值是"抽到了标记但没抽到内容"
MIN_OPEN_LEN = 12


def section_of(notes: str, name: str) -> str:
    """取【段名】的正文，直到**下一个任意**【标记】或文末。

    不要枚举下一段名——段序不固定，还夹着归一化戳，枚举必漏（见模块头）。
    """
    m = re.search(r"【%s】(.*?)(?=%s|\Z)" % (name, _BOUNDARY), notes or "", re.S)
    return " ".join(m.group(1).split()) if m else ""


def all_sections_ok(notes: str) -> bool:
    return all("【%s】" % s in (notes or "") for s in SECTIONS)


# 归一化时用过的宽松标记。它们的**内容**仍留在笔记开头（搬运未删原文），
# 所以【开放点】里可能混进「与C1-C3: ……」这类不是开放点的东西。
_LEGACY_PREFIX = re.compile(
    r"与C1-C3\s*[:：]|与C1\s*[:：]|与本项目\s*[:：]|关系\s*[:：]|"
    r"全库查重干净|直取证伪|之\d+齐|"
    # 光秃秃的「与C1-C3」：归一化在残留处被下一个【标记】截断，冒号都没轮到
    r"与C1-C3\b")

# 归一化搬运的另两类损伤，都要拦：
#  1) 书目元数据混进【开放点】——「Google系；2020年。」「ICLR载」说的是
#     这篇是哪里的，不是这篇缺什么。首跑 24/79 条如此。
#     注意 `载`/`系` 单独出现太宽（"承载""体系"会误杀），故要求成词。
_BIBLIO = re.compile(
    r"[A-Za-z]{2,}(系|载)|"
    r"ACL|EMNLP|NeurIPS|ICLR|ICML|CVPR|AAAI|IJCAI|KDD|WWW|"
    r"(19|20)\d{2}\s*年|预印|期刊|顶会")

#  2) 压缩标签——「省半质；泛化限」是用户自己 agent 写的三字缩写，不是散文。
#     判别信息**不是长度**（那是 MIN_OPEN_LEN 的活，两者会互相吃掉）：
#     是那个「两个极短分句」的结构。第一版我写成"≤14 字且无句读"，
#     结果「短短十个字而已哦」这种纯短句也被报成"需人工解码"，
#     12 字门槛形同虚设——门看着在，其实在被上一道门吃掉。
_COMPRESSED = re.compile(r"^[^，。；;！？、]{1,6}[；;][^，。；;！？、]{1,6}[；;]?$")


def split_residue(opening: str) -> tuple[str, str]:
    """把归一化残留切开，返回 (可用前缀, 被切掉的尾部)。

    这是**纯切割**：在第一个归一化标记处截断，一个字都不新增、不改写。
    机械安全，所以可以自动做。不可自动做的是**展开缩写**——「省半质」
    要变成「dropout 随机置零带来的质量损失」那是编造（AGENTS.md 铁律 2），
    必须由人解码。所以切完标 needs_decode 交给上层，不猜。

    实测 2026-10-02：641 篇残留里 496 篇切出的是中位 9 字的压缩标签，
    145 篇切出 11–31 字的真短语（「细粒度路由开销；共享专家容量」）。
    两者用同一个动作处理、不同的标记上报。
    """
    m = _LEGACY_PREFIX.search(opening)
    if not m:
        return opening.strip(), ""
    head = opening[:m.start()].strip(" ；;，,。.、")
    return head, opening[m.start():].strip()


def fidelity(opening: str) -> tuple[str, str]:
    """返回 (rejected_reason, kind)。kind ∈ {"ok","residue","bib","compressed"}。

    拆成四类而不是"合格/不合格"，是因为四类的**下游处理完全不同**：
    residue 是搬运损伤、可以纯切尾抢救（标 needs_decode）；bib 同理但切完
    常为空；compressed 是别人的私有缩写，救不了也不该猜；只有 ok 能直接
    当作散文候选进排序层。
    """
    body = opening.strip().rstrip("。．.!?！？")   # 尾句读不算分句
    if _ANY_MARK.search(opening):
        return ("开放点内仍有其他【标记】——抽取器可能越界", "residue")
    if _LEGACY_PREFIX.search(opening):
        return ("开放点内混入关系段/查重记录（归一化搬运残留）", "residue")
    if _BIBLIO.search(opening):
        return ("开放点写的是书目元数据（机构/会议/年份）而非缺口", "bib")
    if len(body) <= 14 and _COMPRESSED.match(body):
        return ("开放点是压缩标签而非散文（%d字），需人工解码" % len(body),
                "compressed")
    return ("", "ok")


def is_faithful(opening: str) -> str:
    """检查【开放点】是不是**真的**只写了开放点。返回 ""=合格，否则是不合格理由。

    薄封装，判别逻辑一律走 `fidelity()`。

    ## 这道门是被数据教出来的

    2026-10-02 首跑：1037 篇抽出 1037 条「开放点」，看着很好；跑真实数据
    才发现 283 条「本机可跑」里读出来是这样：

        【开放点】省半质；泛化限。与C1-C3: C1正则gap证据；C2随机模板；
                  C3正则agent。1206.5984直取证伪（…）；全库查重干净。

    ——开放点里塞着**关系段和查重记录**。原因：归一化脚本把宽松格式
    （`做法: / 开口: / 与C1-C3: `）的**整段原文**搬进了【开放点】，而终止符
    只认「下一段标记」，笔记开头那串残留的宽松标记挡不住它。

    真实开放点只有前 6 个字：「省半质；泛化限。」

    这类笔记占 328/1365（24%），若不拦，排序层会把「全库查重干净」当成
    一个研究问题推给用户——**看起来完全合理，所以极难被发现**。

    注：本函数原先在文件里有**两份定义**（一份薄封装、一份内联正则），
    后者静默胜出，前者是死代码。已合并成这一份走 `fidelity()`。
    """
    return fidelity(opening)[0]


# ── 缺口类型：决定这个问题能不能在 6GB 显存的本机上跑 ────────────────────
# 每类给两样东西：识别正则，以及**默认可行性**（fit_local）。
# fit_local=False 的类型不会因为"看起来有意思"而被排到前面——那是本机
# 根本跑不动的实验，排前面就是浪费人的审核时间。
GAP_TYPES: dict[str, dict[str, Any]] = {
    "eval_not_comparable": {
        "label": "评测不可比",
        "pattern": r"不可比|不可复现|自报|非公开|未披露|私有|榜单|leaderboard|"
                   r"评测口径|数字自报|评估集|协议不",
        "fit_local": True,      # 跑评测协议对比不需要 GPU
    },
    "missing_real_experiment": {
        "label": "缺真实验",
        "pattern": r"缺.{0,6}实验|未.{0,4}验证|待验证|待补|没有.{0,4}实验|尚未|需.{0,4}验证",
        "fit_local": True,
    },
    "reproducibility": {
        "label": "可复现性",
        "pattern": r"复现|重现|开源|代码.{0,4}(未|缺)|artifact|权重.{0,4}未",
        "fit_local": True,
    },
    "not_generalized": {
        "label": "方法未泛化",
        "pattern": r"未泛化|泛化|过拟合|特化|窄|仅在|局限|限制|假设|只在",
        "fit_local": True,
    },
    "data_labeling": {
        "label": "数据/标注",
        "pattern": r"标注|数据.{0,4}(少|缺|不足|偏)|偏差|噪声|覆盖|样本",
        "fit_local": True,
    },
    "cost_scale": {
        "label": "成本/规模",
        "pattern": r"成本|开销|延迟|latency|吞吐|扩展|scale|显存|内存|token|预算",
        # 成本类问题多半要压测大模型/长上下文 → 6GB 本机跑不动，降到低优先
        "fit_local": False,
    },
}

# 反向：这些词说明这个开放点是"这人不做"的偏好，不是可判定缺口
SUBJECTIVE = re.compile(
    r"综述口径|survey|挑战只点名|待我|将来|未来工作方向|篇幅|写作|表述")


@dataclass
class Gap:
    """一个待验证的研究问题。全部字段都来自原文，不含推测。"""

    arxiv_id: str
    title: str
    open_problem: str          # 原文摘录，未改写
    gap_types: list[str] = field(default_factory=list)
    fit_local: bool = True
    project_relation: str = ""  # 【与本项目关系】原文
    url: str = ""
    rejected: str = ""           # 非空表示被拒，原因必填
    kind: str = "ok"             # ok/residue/bib/compressed/short/no_gap/subjective
    # 纯机械切尾救回来的内容。needs_decode=True 表示切出来的是用户自己的
    # 三字缩写（「省半质」），**没有**自动展开——展开即编造，必须人解码。
    salvaged: str = ""
    dropped_tail: str = ""
    needs_decode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify(opening: str) -> tuple[list[str], bool]:
    """返回 (命中的缺口类型, 是否适合本机)。**必须给理由**。"""
    hits = [k for k, v in GAP_TYPES.items()
            if re.search(v["pattern"], opening, re.I)]
    fit = any(GAP_TYPES[h]["fit_local"] for h in hits) if hits else False
    return hits, fit


def extract(arxiv_id: str, row: dict[str, Any]) -> Gap:
    """单篇抽取。失败时 Gap.rejected 非空——**不猜、不补位**。

    归一化损伤走**纯切尾抢救**（`split_residue`），不直接丢：
    641 篇残留里有 145 篇能切出 11–31 字的真短语，丢掉是浪费已读的
    1365 篇。切不出来的（切完为空/过短）才拒，理由必填。
    """
    notes = row.get("notes") or ""
    title = (row.get("title") or "").strip()
    rel = ""
    if not all_sections_ok(notes):
        return Gap(arxiv_id, title, "", rejected="三段不齐", kind="incomplete")
    op = section_of(notes, "开放点")
    rel = section_of(notes, "与本项目关系")
    url = row.get("url") or ""

    # fidelity 先于长度判断：压缩标签只有 5–8 字，先判长度会把它报成
    # "过短"——那是不可行动的诊断；报"压缩标签"才告诉上层要人解码。
    bad, kind = fidelity(op)
    salvaged, tail, decode = "", "", False
    if kind in ("residue", "bib"):
        # bib 没有可切的标记（它本身就是「Google系」），只对 residue 切
        if kind == "residue":
            salvaged, tail = split_residue(op)
        if kind == "bib" and not _BIBLIO.sub("", op).strip(" ；;，,。.、"):
            return Gap(arxiv_id, title, op, rejected=bad, kind="bib")
        if not salvaged:
            # 整段都是归一化标记 = 原文里压根没写过开放点。报"残留"是
            # 不可行动的诊断（听上去像"修一下抽取器"），得说清要人做什么。
            return Gap(arxiv_id, title, op,
                       rejected=bad + "（切尾后为空：原文未写开放点）",
                       kind=kind, dropped_tail=tail)
        cand = salvaged
    elif bad:
        return Gap(arxiv_id, title, op, rejected=bad, kind=kind)
    else:
        cand = op

    # 判别：切出来的是「压缩标签」还是「散文残句」。
    # 顺序有意义——压缩标签 7 字，低于 MIN_OPEN_LEN=12；先判长度会把它
    # 当"过短"拒掉，而那正是切尾要救回来的东西。长度门槛的含义是
    # **散文短到读不出信息**，不是"任何不足 12 字的文本"。
    # （这个交互是我自己踩的：第一版先判长度，496 篇压缩标签全被拒，
    #   切尾等于白做。）
    is_compressed = bool(len(cand) <= 14
                      and _COMPRESSED.match(
                          cand.strip().rstrip("。．.!?！？")))
    # 上面必须包 bool()：`and` 返回的是 Match 对象而不是 True/False。dataclass
    # 的类型标注不会强制，于是 needs_decode 字段里装的全是 <re.Match ...>，
    # 序列化进 JSON 就是一段 repr 垃圾，而且 `g.needs_decode == True` 全为假
    # （真值判断为真、相等判断为假——这个组合最难查）。
    if not is_compressed and len(cand) < MIN_OPEN_LEN:
        return Gap(arxiv_id, title, op,
                   rejected=("%s（切尾后仍过短）" % bad) if bad
                            else "开放点过短(%d字)" % len(op),
                   kind=kind if bad else "short",
                   salvaged=cand, dropped_tail=tail)
    decode = is_compressed
    hits, fit = classify(cand)
    if not hits:
        subj = bool(SUBJECTIVE.search(cand))
        return Gap(arxiv_id, title, op,
                   rejected="主观偏好而非可判定缺口" if subj
                            else "未命中任何缺口类型",
                   kind="subjective" if subj else "no_gap",
                   salvaged=cand, dropped_tail=tail, needs_decode=decode)
    return Gap(
        arxiv_id=arxiv_id,
        title=title,
        open_problem=cand,
        gap_types=hits,
        fit_local=fit,
        project_relation=rel,
        url=url,
        rejected="",
        kind="ok",
        salvaged=cand if bad else "",
        dropped_tail=tail,
        needs_decode=decode,
    )


def load_papers(wiki_path: str = WIKI) -> dict[str, Any]:
    with open(wiki_path, encoding="utf-8") as fh:
        return json.load(fh)["tables"]["papers"]


def scan(papers: dict[str, Any] | None = None) -> list[Gap]:
    papers = papers if papers is not None else load_papers()
    return [extract(k, v if isinstance(v, dict) else {})
            for k, v in sorted(papers.items())]


def usable(gaps: list[Gap]) -> list[Gap]:
    return [g for g in gaps if not g.rejected]


def summary(gaps: list[Gap]) -> dict[str, Any]:
    ok = usable(gaps)
    from collections import Counter
    c = Counter(t for g in ok for t in g.gap_types)
    return {
        "scanned": len(gaps),
        "usable": len(ok),
        "rejected": len(gaps) - len(ok),
        "fit_local": sum(1 for g in ok if g.fit_local),
        "by_type": {GAP_TYPES[t]["label"]: n for t, n in c.most_common()},
        "by_reject_kind": dict(Counter(
            g.kind for g in gaps if g.rejected).most_common()),
        "top_reject_reasons": dict(Counter(
            g.rejected.split("(")[0] for g in gaps if g.rejected
        ).most_common(5)),
    }


# ── 自测 ──────────────────────────────────────────────────────────────────
def selftest() -> int:
    # 反证 1：三段不齐必须拒
    g = extract("x", {"notes": "【做法】abc", "title": "t"})
    assert g.rejected == "三段不齐", "三段不齐却放行"
    print("  通过：三段不齐被拒")

    # 反证 2：过短被拒（12 字门槛，10 字须落在 12–14 之间才够判过短，
    # 否则会被压缩标签门先接住——门序是有意义的，不是随便排的）
    g = extract("x", {"notes": "【做法】" + "长" * 30 + "【开放点】短短十个字而已哦"
                      + "【与本项目关系】" + "长" * 30})
    assert "过短" in g.rejected, "过短却放行：%s" % g.rejected
    print("  通过：过短被拒")

    # 反证 3：段序颠倒时，终止符仍不越界（本模块头那个 bug 的回归）
    notes = ("【与本项目关系】关系段的内容在这里写清楚"
             "【开放点】真正的开放点是阈值未消融"
             "【做法】做法段的内容也在这里")
    assert section_of(notes, "开放点") == "真正的开放点是阈值未消融", \
        "抽取越界：%r" % section_of(notes, "开放点")
    assert "【" not in section_of(notes, "开放点"), "开放点里漏进其他标记"
    print("  通过：段序颠倒不越界（343 篇回归）")

    # 反证 4：中间夹戳也不越界
    notes = ("【做法】做法内容在这里写清楚足够了"
             "【开放点】这个开放点本身是有效的"
             "【格式归一】2026-01-01 机器加的戳"
             "【与本项目关系】关系内容在这里")
    assert section_of(notes, "开放点") == "这个开放点本身是有效的", \
        "戳导致越界：%r" % section_of(notes, "开放点")
    print("  通过：夹归一化戳不越界")

    # 反证 5：抽取器不许把标记漏进结果（自检用）
    g = extract("2601.00001", {"title": "t", "notes":
        "【做法】" + "长" * 20 + "【开放点】评测口径不统一，数字自报且不可比"
        + "【与本项目关系】" + "长" * 20})
    assert not g.rejected, "合格开放点被拒：%s" % g.rejected
    assert g.gap_types == ["eval_not_comparable"], "分类错：%s" % g.gap_types
    assert g.fit_local, "评测类应判本机可跑"
    print("  通过：合格开放点抽出且分类正确")

    # 反证 6：成本类必须被降级（6GB 跑不动）
    g = extract("2601.00002", {"title": "t", "notes":
        "【做法】" + "长" * 20 + "【开放点】显存开销与推理延迟成本仍高"
        + "【与本项目关系】" + "长" * 20})
    assert g.gap_types == ["cost_scale"], "分类错：%s" % g.gap_types
    assert not g.fit_local, "成本类被判本机可跑"
    print("  通过：成本类降级为不可本地跑")

    # 反证 7：主观偏好不算缺口
    g = extract("2601.00003", {"title": "t", "notes":
        "【做法】" + "长" * 20 + "【开放点】综述口径需要注意挑战只点名"
        + "【与本项目关系】" + "长" * 20})
    assert "主观" in g.rejected, "主观偏好被当成缺口：%s" % g.rejected
    print("  通过：主观偏好被拒")

    # 反证 8：把分类器打瞎，usable 必须塌成 0（门不能靠巧合成立）
    saved = GAP_TYPES["eval_not_comparable"]["pattern"]
    try:
        GAP_TYPES["eval_not_comparable"]["pattern"] = r"绝不匹配的模式"
        gaps = scan(load_papers())
        s = summary(gaps)
        assert s["by_type"].get("评测不可比", 0) == 0, "打瞎后仍有命中"
    finally:
        GAP_TYPES["eval_not_comparable"]["pattern"] = saved
    print("  通过：分类器打瞎后对应类型归零")

    # 反证 9（首跑真数据才抓到的）：归一化残留必须被**切干净**而不是整段放行。
    # 这条笔记来自 1207.0580v1 真实数据，开放点里塞着关系段与查重记录。
    # 修法是纯切尾抢救（不丢 641 篇），但切出来的东西必须：
    #   ① 不含任何归一化标记；② 短标签要标 needs_decode（不许自动展开缩写）。
    poisoned = (
        "T04-G06之1。做法: Dropout防共适应。开口: 省半质；泛化限。"
        "与C1-C3: C1正则gap证据；C2随机模板。全库查重干净。\n"
        "【做法】Dropout防共适应。\n"
        "【开放点】省半质；泛化限。与C1-C3: C1正则gap证据；"
        "C2随机模板；C3正则agent。1206.5984直取证伪；全库查重干净。\n"
        "【与本项目关系】C1正则gap证据；C2随机模板。")
    g = extract("1207.0580v1", {"title": "Dropout", "notes": poisoned})
    assert g.open_problem == "省半质；泛化限", "切尾不干净：%r" % g.open_problem
    assert not _LEGACY_PREFIX.search(g.open_problem), "切完仍有归一化标记"
    assert "全库查重干净" in g.dropped_tail, "尾部没记下来，丢了可审计性"
    # 必须用 `is True`，不能用真值判断：needs_decode 曾经装的是 regex 的
    # Match 对象而不是 bool（`len<=14 and _COMPRESSED.match(...)` 直接返回
    # Match）。真值判断对 Match 也成立，所以旧断言永远通过，bug 活到今天。
    # 真值判断和相等判断在这里给出相反的答案，是最难查的一类。
    assert g.needs_decode is True, \
        "压缩标签未标 needs_decode——会被当成散文推给用户"
    assert g.salvaged == g.open_problem, "救回内容未记入 salvaged"
    print("  通过：归一化残留被切干净且标 needs_decode（1207.0580v1 回归）")

    # 反证 10：整段都是归一化标记 = 原文压根没写开放点，必须拒，且要
    # 说清「要人做什么」——只报"残留"听上去像"修抽取器就行"，不可行动。
    g = extract("x", {"title": "t", "notes":
        "【做法】" + "长" * 20
        + "【开放点】全库查重干净。"
        + "【与本项目关系】" + "长" * 20})
    assert g.rejected, "切完为空却放行：%r" % g.open_problem
    assert "为空" in g.rejected and "未写" in g.rejected, \
        "拒绝理由不可行动：%s" % g.rejected
    print("  通过：切完为空被拒（诊断可行动）")

    # 反证 11：真·干净的开放点不能被这道门误杀。
    # 「机制解释浅；阈值未消融」一条都没命中缺口类型——那是**分类层**该
    # 管的，不是抽取层。这里只验证抽取层不误杀：分类拒了要说"未命中类型"
    # 而不是"残留"，否则两层的结论会被混起来。
    g = extract("2402.11651v2", {"title": "t", "notes":
        "【做法】" + "长" * 20
        + "【开放点】前后缀标记法简单，机制解释浅；阈值未消融。"
        + "【与本项目关系】" + "长" * 20})
    assert "残留" not in g.rejected, "干净开放点被抽取层误杀：%s" % g.rejected
    print("  通过：干净开放点不被抽取层误杀（2402.11651v2 真实数据回归）")

    # 反证 12（真实数据 1606.07947v4 / 2004.02349v2 抓到的第三类损伤）：
    # 【开放点】里写的是「EMNLP载；NMT域。」「Google系；2020年。」——这是
    # 书目元数据，不是缺口。放行的话排序层会把"Google系"当研究问题。
    g = extract("1606.07947v4", {"title": "t", "notes":
        "【做法】SeqKD 词级蒸馏；MIT系。"
        "【开放点】EMNLP载；NMT域。"
        "【与本项目关系】序列律，A线必引。"})
    assert g.kind == "bib", "书目元数据未识别：%s" % (g.rejected or g.kind)
    print("  通过：书目元数据被拒（1606.07947v4 真实数据回归）")

    # 反证 13：书目门槛不能过宽——「承载」「体系」不是书目
    g = extract("x", {"title": "t", "notes":
        "【做法】" + "长" * 20
        + "【开放点】当前评测体系承载不了这个任务，泛化未验证。"
        + "【与本项目关系】" + "长" * 20})
    assert g.kind != "bib", "误杀正常开放点：%s" % g.rejected
    print("  通过：书目门槛不误杀「承载/体系」")

    # 反证 14（真实数据 2301.13379v3 抓到的第四类）：残留被下一个【标记】
    # 截断，冒号都没轮到，留下光秃秃的「与C1-C3」。老正则要 `[:：]` 才命中，
    # 会让它整段进排序层——「翻译错即全错。与C1-C3」读起来像个问题。
    g = extract("2301.13379v3", {"title": "t", "notes":
        "T17-G06之4。做法：两阶段翻译加求解器。留下开口：求解器覆盖域有限。"
        "与C1-C3关系：C2神经符号分工范式。\n"
        "【做法】两阶段翻译加求解器，忠实性由构造保证。"
        "【开放点】求解器覆盖域有限，翻译错即全错。与C1-C3"
        "【与本项目关系】C2神经符号分工范式。"})
    assert g.open_problem == "求解器覆盖域有限，翻译错即全错", \
        "截断残留没切掉：%r" % g.open_problem
    assert "C1-C3" in g.dropped_tail, "截断标记没进尾部"
    assert g.salvaged and not g.needs_decode, "切出的真短语不该标 needs_decode"
    print("  通过：截断残留被切掉（2301.13379v3 真实数据回归）")

    # 反证 15：压缩标签必须可诊断为「需人工解码」而不是「过短」
    # 「省半质；泛化限」7 字：若先判长度会报"过短"，那是不可行动的诊断。
    g = extract("1207.0580v1", {"title": "t", "notes":
        "【做法】Dropout 防共适应，随机省半破过拟合。"
        "【开放点】省半质；泛化限。"
        "【与本项目关系】C1正则gap证据。"})
    assert g.kind == "compressed", "压缩标签未识别：%s" % (g.rejected or g.kind)
    assert "解码" in g.rejected, "诊断不可行动：%s" % g.rejected
    print("  通过：压缩标签给出可行动诊断（1207.0580v1 真实数据回归）")

    # 反证 16：kind 汇总必须能区分四类损伤（防止统计口径再次合并）
    gaps = scan(load_papers())
    s = summary(gaps)
    assert s["usable"] + sum(s["by_reject_kind"].values()) == s["scanned"], \
        "口径不自洽：%s" % s
    assert s["usable"] == 0 or s["by_reject_kind"], "拒因分类丢失"
    print("  通过：kind 口径自洽（%d = %d + %d）"
          % (s["scanned"], s["usable"], sum(s["by_reject_kind"].values())))
    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    # 之前这个入口是缺的：`python3 -m ai_researcher.scanner --selftest`
    # 直接 exit 0 且一行输出都没有，看起来像"跑过了"，实际根本没跑
    # （第 7 条：门必须能失败——一个调不到的门永远"通过"）。
    import sys as _sys
    if "--selftest" in _sys.argv:
        _sys.exit(selftest())
    _s = summary(scan())
    print("扫描 %d 篇：可用 %d / 拒 %d，本机可跑 %d"
          % (_s["scanned"], _s["usable"], _s["rejected"], _s["fit_local"]))
    for _k, _v in _s["by_reject_kind"].items():
        print("  拒因 %-11s %d" % (_k, _v))
    _sys.exit(0)
