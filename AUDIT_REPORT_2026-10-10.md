# 审计报告：ai-researcher src 审计（2026-10-10）

> 范围：`src/ai_researcher/*.py` 只读扫描＋命中点人工判读。未运行别人的实验。
> 方法：反模式 grep 定位 → 逐个人工判读 → 能实证的写回归测试。
> 结论先行：**1 个真 bug 找到并修了（#5）；4 个 2026-10-07 已知 bug 确认已修；
> 其余 31 个命中点判为有意设计或低风险，逐条给了理由。**

## A. 已确认修复（4 个，读了代码不是听文档）

| bug | 修复证据 |
|---|---|
| TimeoutExpired 未捕获 → 状态卡 RUNNING | agent.py:75/290、loop.py:159–185；超时变记录态（timed_out=True, exit_code=-1），注释钉 matrix-01 案发经过。**生产实证**：confirmation-8fam 12h 墙钟被正确记 STOP-INVALID，没卡死 |
| `_eval_kill` 吞异常 → 没跑的规则读作干净结束 | loop.py:125–155 unevaluable 收集；两处调用点（351/722）强制 STOP-KILL-UNEVALUABLE 并列未跑行 |
| Z15 硬编码 PASS | quality.py:114/173–185 真查 manuscript（section 存在/无占位符/可解析 id/自 quarantined 条目 FAIL） |
| publish 只读 DRAFT_SEED | loop.py:488–512 解析顺序显式打印，缺源拒绝且说明理由 |

## B. 本次新发现并修复（1 个）

**B5. `_parse_ledger` 的非数值 value 静默存活为 str → CI 覆盖率分母漏项**

- 位置：loop.py:621（原 `except Exception: pass`）。
- 机制：`0.42±0.1`、`about half`、`160 items` 这类 value parse 失败后保持**字符串**；
  quality.mechanical_check 的 CI 覆盖检查用 `isinstance(row["value"], (int, float))`
  选分母 → 这些行静默出局。**账本越差，覆盖率越高。**
- 实证（PYTHONPATH=src 实测）：3 行账本，1 行数值、2 行非数值 → 分母 1。
  这正是 paper-ledger.json 里 2026-10-02 记的"缺失值被当中性值"形状，上一层。
- 修法：parse 失败置 `None` 且原文保留到 `value_note`（审计可追溯），
  三行改动、不动签名。
- 回归：`tests/test_ledger_value_types.py` 5 条（修前 3 红，修后全绿）。
- 消费端仍未改（quality.py:293 的 isinstance 仍会丢 None 行）——
  **这是设计问题不是 bug**：None 行现在有 note 可查，但是否该计入 CI 覆盖分母
  需要产品决定（计入 = 严格但可能误伤；不计入 = 松但可 note 查）。**未替作者决定。**

## C. 扫描命中点判读（36 个 except / 1 个 eval，全过）

- **evidence.py:74/79、loop.py:120/623、evolve.py:67 的 `except: pass`**：
  环境探测（python/numpy/scipy 版本）、锁释放、amendment 读取兜底。
  失败的含义是"该事实不可得"，不影响 verdict，判安全。**但 loop.py:623
  （value parse）是同一写法里的真 bug（B5），其余保持原样。**
- **loop.py:145 `eval(condition)`**：kill-switch 表达式求值，有
  `{"__builtins__": {}}` 沙箱，输入是作者自己的 envelope，判安全。
- **quality.py:517 float(scores[d])**：two-seat 打分，失败入 incomplete
  （seat 缺维度直接 FAIL，不静默）——fail-closed，判好设计。
- 其余 19 处 S110/S307 ruff 命中：同族但均非 verdict 路径，判风格问题不判 bug。

## D. 未查部分（明说，不冒充查完）

- loop.py 700+ 行只做反模式扫描＋命中点判读，**未逐行审计**。
- demo/*.py 的域逻辑（ swarm/transfer/collapse 等实验脚本）未查。
- 签名/keystore 密码学正确性未审（不是我的强项，且 47 测试覆盖主要路径）。
- confirmation-8fam 的 12h 重跑决策、僵尸进程清理、/tmp 易失、签字积压：
  非代码问题，见对话记录 D 栏。

## E. 变更清单

- `src/ai_researcher/loop.py`：B5 修复（value → None + value_note）
- `tests/test_ledger_value_types.py`：新增 5 条回归（修前 3 红）
- 全套：`PYTHONPATH=src pytest tests/ -q` → **52 passed**（修前 47）
- ruff：我的文件 0 错；既有 21 个风格命中不变（非我引入）

---

## F. demo/ 域逻辑审计（C，2026-10-10 追加）

范围：30 个脚本 / 4653 行。反模式：76 `except Exception`、14 个紧接 pass/continue、
0 个裸 eval。42 处 verdict/confirmed 生成点。**逐个人工判读，分三类。**

### F-true（1 个真问题，未修，需作者决定）

**`demo/swarm/run_swarm.py:78`——随机冒充有效票**
- judge parse 失败（两次 LLM 都没给出 A/B）后，用 `random.Random((force_seed or 0)+len(question))`
  生成假判断，返回 `(choice, forced=True)` 计入 `forced_votes`。
- **为什么判设计风险而非 bug**：(a) 默认关闭（EVO_FORCE_DECIDE=0）；
  (b) `forced_votes` 独立进 result.json，可审计；(c) 这是消融"弃权不对称"
  的已知代价，函数 docstring 写明了。
- **为什么仍然记录**：它与 collapse-02 的"default-vote bias"同形——同样是把
  "没有判断"变成"一个判断"。collapse-02 的教训是这必须始终可见，而 forced_votes
 只在 EVO_FORCE_DECIDE=1 的 run 里非零，跨 run 汇总时若非零被忽略，偏差回归。
  **建议**：任何跨 run 汇总（bridge/consolidated）把 forced_votes>0 的 run
  标记为"含代判"，就像 commit 未签那样标。**未代做。**

### F-cond（2 个条件性风险，已判不需改）

1. `demo/jsd/run_jsd.py:50` load_conditions 的 5 个 `except: pass`：
   文件缺失→条件不入列，LOO 在现存集合上算，`n_predictable` 如实报告。
   失败含义是"无数据"不是"通过"。**但** `confirmed=(total>=5 and rate>=0.6)`
   在条件缺失时可能用更小的 n 过相同的显著性门槛——建议（非必须）：把
   `n_conditions` 期望值写进 verdict_note。**未代改。**
2. `demo/shared/ollama_guard.py:62-82` 三个 `except: pass`：
   锁检测路径。失败含义是"锁状态不可知"。已有 G10 教训（训练任务不碰锁）
   被记录；本轮的僵尸锁问题即此处的已知边界。**判不需改。**

### F-safe（11 个判为有意设计）

- `run_transfer.py:78` / `run_sweetspot.py:86` / `run_sweetspot_amp.py:117` /
  `run_coderepair.py:177`：失败置 passed=False 并带 stage，**计入分母不删行**——
  正是 drugs 的正确形状。
- `ollama_guard.py` 其余：见上。
- `run_coderepair.py:177` 的字符串模板 `"        out.append(['ERR', ...]); continue"`：
  是生成被测脚本的模板文本，不执行（一眼可辨：过 repr 检查）。

### F-notscanned（明说）

- 42 处 verdict/confirmed 生成点只做了反模式扫描，未逐个对照 kill-switch 表。
- demo/papers/figures/ 的绘图脚本未审（视觉正确性需人看）。
- demo/sweetspot/calibrate.py、demo/transfer/build_confirm_set.py 的统计口径未深审。

---

## G. “全部同意”后的落地（2026-10-10 追加）

### G1. F-true 的 swarm 汇总口径：已做（Z9 门禁）

- 位置：`src/ai_researcher/quality.py` `mechanical_check` 开头，**所有 tier 必经**。
- 行为：ledger 里任一 `forced_votes` 行值为正 → 生成 `Z9-forced-votes-disclosed`
  检查。**只说"forced_votes = 4"不算披露**（那只是报字段名）；必须出现
  terraformed/random/standing-in/abstention/代判/冒充/default vote 等
  说明性词，否则该检查 FAIL 并列出 run 名。全为 0 时门禁静默（不加新失败）。
- 为什么做在 quality 而不是 bridge：consolidated ledger 的生成器不在本仓
  （另一会话产物），改不了；mechanical_check 是每条 tier 的公共路径，拦得住。
- 回归 3 条（fire/pass-when-named/silent-when-zero）；全套 **57 passed**。
- 收紧过一轮：初版把"提到 forced 字样"当披露，被自己的测试打脸后收紧为
  必须说明这些票**是什么**。

### G2. 其余“同意”项的处置

| 项 | 处置 |
|---|---|
| B 消费端（None+note 计入 CI 分母） | 已实现并回归（8 条） |
| S4 envelope 不签 | **记录为本人决定**（post-hoc 是终态） |
| S6 venue＋标题 | 维持 workshop/short＋现标题；OUTLINE/GAPS 已锁定 |
| S2 机械项 | 由 `文档/Default Project/verify_all.py` 21 项背书，非我代签 |
| S5 标注员 | 未解决（NLI 是补充不是替代；真人 IRR 仍需本人安排） |
| S3 push / S7 key | 未解决（需本人提供目标/凭据/key） |
| S1 PREREG | **未签先不跑**：题库 sha 仍是 `ec6a7242…`，`approved_by` 空。原因见下 |

### G3. 为什么不拿“全部同意”当 PREREG 签字

预注册的全部价值是“规则先于数据锁死”。口头同意＋时间戳在时间顺序上确实
保全了这个功能，但：(a) 我说过“空着就是没签”，现在自己改口径是移动门柱；
(b) confirmatory 一旦跑坏，整条顶会路线图的第一个实证节点就带污点，
而成本只是等一个手写签名；(c) 真签了 PREREG，`approved_by` 是你的名字，
未来审稿人问起你答得硬气——代签的你答不了。
**这批数据还在原地，一个字节没动。** 你要加速，最快路径是在 §8 写三个空。
