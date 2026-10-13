# AIR-CODEREPAIR：40 题拉到 157 题值不值（判决 NOT_FUNDED，撤回那发机时）

跑法：`python3 scripts/coderepair_escalation_verdict.py` ｜ 零机时（machine_minutes_spent=0、ollama_calls_made=0）｜ 产物 `reports/coderepair_escalation_verdict.json`｜ 对账夹具 `--selftest-only`（15 条，PASS）

**判决**：NOT_FUNDED_leg_resolved_worse_on_its_own_ruler（触发规则：direction，规则顺序在脚本 docstring 里先声明后读数）

## 这一件纠正了定价板自己的一句话

`reports/agi_arm_price_board.md` 给这一臂落 `INSTRUMENT_GAP_bar_carrier_missing`，限制项写「参照臂盘上不存在」。**只对了一半**：`demo/runs/coderepair-02` 就是同币种的第二块载体（n=48、逐题配对、policies 里就有 direct 与 step-calc），当时没被接进算式。接进来之后 GAP 消失，取而代之的是一个更硬的判决——而且原板那一格的均值也是错的（见下）。

## 现读：两块独立题池，配对数从逐题 `passed` 重算，不信任何汇总字段

| 载体 | n_items | 有数据的模型 | 进均值的模型 | step-calc − direct 均值 | 模型间 sd | 池化 fixed/broke | 精确 McNemar p |
|---|---|---|---|---|---|---|---|
| coderepair-01 | 40 | 4 | 3 | **-0.0750** | 0.1521 | 12/21 | 0.16276 |
| coderepair-02 | 48 | 3 | 3 | **-0.1042** | 0.1804 | 12/27 | 0.02370 |

对表（重算 vs 载体自报，两把尺逐位相符才准出判决）：

```
{
 "coderepair-01": {
  "recomputed": "12/21",
  "carrier": "12/21",
  "p_recomputed": 0.162756,
  "p_carrier": 0.162756
 },
 "coderepair-02": {
  "recomputed": "12/27",
  "carrier": "12/27",
  "p_recomputed": 0.023703,
  "p_carrier": 0.023703
 }
}
```

## 逐模型结构：负向不是噪声，是一个模型在两块池上复制

- **coderepair-01**
  - gemma3:4b            fixed= 0 broke=10 delta=-0.2500 p=0.0020
  - llama3.2:3b          fixed= 0 broke= 0 delta=+0.0000 p=—（零不和谐对 ⇒ 配对检验下这一格 n=0） ⟵ 传输层死格，已排除出均值
  - qwen2.5-coder:7b     fixed= 4 broke= 4 delta=+0.0000 p=1.0000
  - qwen2.5:7b           fixed= 8 broke= 7 delta=+0.0250 p=1.0000
- **coderepair-02**
  - gemma3:4b            fixed= 0 broke=15 delta=-0.3125 p=0.0001
  - qwen2.5-coder:7b     fixed= 4 broke= 4 delta=+0.0000 p=1.0000
  - qwen2.5:7b           fixed= 8 broke= 8 delta=+0.0000 p=1.0000

两个 7B qwen 在**两块池**上都是 fixed≈broke（01：8/7 与 4/4；02：8/8 与 4/4）⇒ 探测不到效应；`gemma3:4b` 两块池都强负且 resolved（01：0/10 p=0.0020；02：0/15 p=0.0001）。

## 顺带抓到一条会让旧均值变好看的仪器错：`llama3.2:3b` 那一格从来没被测到

`coderepair-01` 的 `llama3.2:3b` 两个策略各 **40/40 条 `HTTPError: HTTP Error 404: Not Found`**，而 `policies` 记成 `direct: 0.0 / step-calc: 0.0`。⇒ 它的 `delta=0.0` 不是「两种策略一样差」，是**80 次调用全没成功**。定价板当时把 4 个模型一起平均，得到 −0.0563；排除这一格之后是 **−0.0750**（3 个模型）——负得更狠。方向不变，但**原板的数被管道故障稀释了 25%**。

这条现在由机器盯着：`transport_scan()` 逐题读 `why` 里的传输字样，`transport_dead_models()` 只在**两侧策略同超 90%** 时判死格并排除出均值；夹具 `--prove-red transport-masked`（把 `why` 改写成看起来像真失败）一注入，均值立刻回到 −0.0563 ⇒ 证明这条规则是承重的，不是装饰。

## 撤回的成本与「名义可判」

```
{
 "what_would_cost": {
  "cells_at_157": 1256,
  "throughput_calls_per_min_carrier": 64.1,
  "extrapolated_minutes": 19.6,
  "status": "假设（线性外推），且本轮决定不花"
 },
 "escalation_arithmetic": {
  "n_for_a_positive_target": 409,
  "arithmetic": "n = ceil((2.802 x sd / target)^2)，sd 取两块池里较大的模型间 sd=0.1804",
  "why_unusable": "这个 n 是为『正效应』算的功效；观测均值是负的，把 n 提到它也不会翻正 ⇒ 只是名义可判"
 }
}
```

`n_for_a_positive_target` 是为**正效应**算的功效；观测均值是负的 ⇒ 把 n 提到它也不会翻正。这一格必须连注释一起引用，单独摘出来说「要 409 题」是错的。

## 夹具：五格，两边都要能打红，且升档出口必须可达

| 注入 | 改的是什么 | 实跑 |
|---|---|---|
| `poison-detail` | 翻 coderepair-02 一个 pass（跑完还原并现印 md5） | rc=3 `INSTRUMENT_GAP…`（对表红） |
| `swap-policy` | 被审策略换成 spec-first | rc=3 `INSTRUMENT_GAP…` |
| `drop-negative-model` | 剔掉 resolved 的负向模型 | rc=3 `INSTRUMENT_GAP…`；重算 12/11、p=1.0 ⇒ **剔除负向腿会把「有害」洗成「无效」** |
| `synth-positive` | 逐题字节与汇总字段**一起**改成正向（自洽） | rc=0 `ESCALATION_TESTABLE…`，均值 +0.275 / +0.229 ⇒ 方向那支判决真能翻面 |
| `transport-masked` | 把传输错误的 `why` 伪装成真失败 | rc=0 但均值 −0.0750 → **−0.0563** ⇒ 运输层规则承重 |

前四格里三格被同一道对表闸抓住，这不够——所以必须有 `synth-positive` 那种「对表仍过、判决翻面」的夹具，否则「方向」那一支从没被变异打到过，只会拒绝的闸和永远绿的断言是同一种装饰。

## 补测之后（2026-10-10）：第四个模型有了数，符号随容量翻

`llama3.2:3b` 那格原来是 40/40 条 `HTTPError 404`（模型没装）。本机装上之后用**同 seed、
同 40 题（`items.json` 的 id 集合与顺序与 coderepair-01 逐位相同，已核）**补了一发探针，
产物落在 `demo/probes/coderepair-llama32-3b/`（**未注册**：无 envelope/签名/评审两席，不许引当论文证据）：

| 模型 | direct → step-calc | delta | fixed/broke | 精确 p |
|---|---|---|---|---|
| qwen2.5:7b | 0.525 → 0.550 | +0.025 | 8/7 | 1.00 |
| qwen2.5-coder:7b | 0.525 → 0.525 | 0.000 | 4/4 | 1.00 |
| gemma3:4b | 0.625 → 0.375 | **−0.250** | 0/10 | 0.0020 |
| llama3.2:3b（新探针） | 0.425 → 0.575 | **+0.150** | 11/5 | 0.2101 |

四模型均值 = **−0.0188**（排除传输死格的三模型是 −0.0750）。

判读不变的部分：`NOT_FUNDED`（40→157 那发仍撤回）——把题数加到一个均值仍为负、
且**符号随模型容量翻**的合并主张上，加样本翻不了正。
判读变化的部分：这一臂真正的问题不是"step-calc 有没有用"，是两个 7B 平、4B 显著受损、3B 正向未测开
⇒ 下一格该买的是"按模型分层 + 每个模型自己的功效"，其中 3b 这一格从 p=0.21 到能判需要的
是它自己的重复数，不是同一个池的题数（单模型 sd 无载体，本轮没算它的 n）。

## 局限

- 这些模型的不和谐对 b+c=0 ⇒ 在配对检验下它的 n 就是 0，不是 delta=0.0。若把它当 0.0 进均值，会把负均值往 0 拉并压低 sd（01 里 llama3.2:3b 就是这一格）。
- sd 是模型间方差（4 或 3 个点），不是逐题方差：n_for_a_positive_target 只能当量级看。
- 两块池的题集不同（01 是 40 题、02 是 48 题）⇒ 负向是跨池复制的，不是同一批题重跑。
- 02 只有 3 个模型可配对（models_measured 见字段），第 4 个当时没跑成。
- throughput 64.1 次/分来自 01 的一次实测，换模型/换长度不复用。

## 下一步该买什么（不是题数）

1. **先修发送端再谈这一臂**：`llama3.2:3b` 那 80 次 404 是一次配置/端点错，不是模型能力。零机时能查的是 `run_coderepair.py` 里那个模型名的请求路径；修好后重跑该格 ≈ 80 次调用 ≈ 1.2 分钟（按 64.1 次/分外推，假设）。
2. 主张要收窄成现读支撑的那一句：**「step-calc 在两个 7B qwen 上无可探测效应，在 gemma3:4b 上显著有害（两块独立题池复制，p=0.0020 与 0.0001）」**。写成「推理策略对代码修复无效」会越过数据。

零 GitHub 写；本件所有数由脚本从两份载体重算，判据顺序与夹具都写在 `scripts/coderepair_escalation_verdict.py`。
