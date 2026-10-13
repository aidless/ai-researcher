# ai-researcher 未结事项（2026-10-10 现读）

零 GitHub 写。这里的每条都带现读数字，判据由脚本给，不由本文命名。

## 1. 【最重】28 份 run 目录里带着可用的 Ed25519 私钥，其中 27 份已在 HEAD 里

现读（`scripts/scrub_run_signing_keys.py` dry-run，未写盘）：

```
带私钥的 state.json: 28 份 | 唯一私钥数: 28 把
其中被 git 跟踪: 27 份 | HEAD 提交里同样带私钥: 27 份 | HEAD 读不到（未跟踪新增）: 1 份（confirmation-8fam）
```

**这 27 份是我自己放进历史的**：`git log --diff-filter=A` 现读，它们随
`611d15e`（2026-10-09 01:00:52 CST「全量入版本库：466 个未跟踪文件进历史」）进入 git，
而把 `key_priv` 置 None 的信任根修复 `144abb3` 在 **38 分钟后**（01:39:31 CST）才落地。
⇒ 我那次"治理类提交"顺手把 27 把可用私钥永久写进了历史，还在提交信息里写了"零推送"当护栏。
护栏不是修复：只要将来 push，这 28 把私钥（含未跟踪那一份）就等同泄露。

抽查自证（`demo/runs/confirmation-8fam/state.json`）：由 `key_priv` 推出的公钥与该文件里的
`key_pub` **逐字节相同**，用它签一条消息再拿 `key_pub` 验 → 通过。
⇒ 那不是残留的装饰字段，是一把能用的签名私钥。

为什么这条要排在任何科学结论前面：信任根那次修复（`loop.py:252/696` 存盘前把 `key_priv` 置 None）
只管住了**之后的写者**。而"产物被签过"这句话的外部支撑，前提是签名权在被审对象之外。
只要 run 目录自己带私钥，改产物 → 用同一把重签 → 覆盖 `key_pub` 就仍然成立，
而且这批 key 不在注册表/固定表里（`grep -rl 339783ad demo/` 只命中它自己的 `state.json`）
⇒ 现在的闸会判 InvalidSignature（正确），但**攻击面是"任何人都能把伪造说成真"**。

已做的（不需要我替你决定的）：
- `scripts/verify_all.py` 加了 `check_signing_power()`：把这条不变量按字节查，不再靠写者自觉。
  它现在让 `scripts/gate.sh` 与 `verify_all.py` 整体会 **FAIL** —— 这是刻意的：
  一条会腐烂的不变量如果只写在注释里，等于没有。
- `tests/test_signing_power.py` 四格夹具（两向 + 不可解析 + 真树现状）：
  A 注入 `key_priv` ⇒ 必须红且点名"不在任何固定表里"；
  B `key_priv=None`/`""` ⇒ 必须一条不报（少这格，"永远红"和"真的在查"长得一样）；
  C `state.json` 读不了 ⇒ 判红并说"cannot run"，不许当干净；
  D 真树现状 ⇒ scrub 之后这格会转绿，届时请把期望改成 0 **并保留夹具**，
    因为"曾经抓到 28 份"是这台仪器存在理由的凭据。

**要你点头的（我没做，两件都是不可逆或会碰别人的对象）**：
1. 清盘：`python3 scripts/scrub_run_signing_keys.py --apply`。
   脚本自带安全边界：`status == RUNNING` 一律跳过（现读 `confirmation-8fam-r2` 是 RUNNING，
   且它的 `key_priv` 已经是 `False` ⇒ 这一格跳过是**保险**，不是当轮必需——将来有 in-flight run
   正巧带着新私钥时它才有活干）；写前整份备份到 `~/.ai-researcher-scrub-backup/<UTC 时戳>/`，
   原子替换，写完回读校验，
   并且**清完自动重跑一次全树验签、要求 verdict 逐条不变**——如果变了，说明验签偷偷读了
   run 目录里的私钥，那本身就是判据要抓的事，脚本会打印还原路径并退出 2。
   要不要现在做、由谁做，等你点名。
2. git 历史：那 27 份也在 HEAD 里。**我没有改写历史，也不会替你改写**
   （这仓现在有多个会话并行在写，filter-repo 会砸掉别人正在跑的对象）。
   判据很清楚：只要 `ai-researcher` 这批目录将来被 push，这 28 把私钥就必须按"已泄露"处理
   ——轮换密钥、把用它们签过的判决在台账里标 `non-authoritative`。
   要么先清历史再 push，要么这个仓永不 push。

## 1b. 工作树已清干净（2026-10-10 16:24），但**不是我清的**

`--apply` 的现跑回执：`带私钥的 state.json: 0 份 … 写了 0 份`，
备份目录 `~/.ai-researcher-scrub-backup/20261010T162428Z/` 里 **0 个文件**。
而 28 份 `state.json` 的 mtime 全部落在同一秒 **16:24:20**，比我脚本第一次具备写能力的动作早 8 秒
⇒ **另一个会话（或另一个进程）先做了同样的清理，而且没有留备份**。

这不是"反正结果一样"就算了的事，三条读数必须一起记：

1. **内容没坏**：逐份把 HEAD 版与现版 `json.loads` 后深度对比，剥掉 `key_priv` 之后
   **28/28 完全相同**（`rounds`、`key_pub`、`status` 一字未动）。
2. **可回退路径只剩 git**：没有改前副本，唯一的"改前状态"就是 HEAD 的 blob——
   而那批 blob 恰好还带着私钥，所以现在想还原随时能还原，想彻底清掉反而要靠它。
   这正是那条老教训的又一面：并发提交会让 .bak/备份成为唯一的改前状态，
   这次我的脚本"本该留下的那份备份"是空的。
3. **闸的状态是真的**：`verify_all.check_signing_power` 现读 `ok: 30 份 state.json 无一持有私钥`；
   `tests/test_signing_power.py::test_D` 由"必须抓到 ≥1 份"翻成"必须为 0"并**保留夹具**
   （删掉这格等于把已修好的东西重新变回没人查），整条 `gate.sh` 五步全绿、`pytest tests/` 47 passed。

**仍未做**：HEAD 里那 27 份带私钥的 blob 还在历史里。filter-repo 我没跑——
这仓此刻有多个会话并行写，改写历史会砸掉别人正在跑的对象，而且不可回退。
判据不变：只要 `ai-researcher` 将来被 push，这 28 把就按已泄露处理（轮换 + 相关判决标 non-authoritative）。

## 2. `confirmation-8fam`：一条 loop_schema=2 的 run 到了终态却没有评审记录

现读：`status: STOP-INVALID`、1 个 round、`round-01.action=None`、`review=None`、
`loop_schema=2`、`key_era=root`、`started_at=2026-10-09T04:26:43Z`（**晚于**信任根那次修复的本地提交时刻）。
`verify_all.py` 两条 FAIL 都指向它：签名不可验（见上，它自带未注册的 key 对）+ 判决阶段不可达。

我没有动这个目录：它是别的会话的对象，且 `?? ` 未跟踪（`git status` 现读）。
需要它的所有者回答的问题只有一个——**那把私钥是谁写进去的**：
仓内 HEAD 的 `loop.py` 三处写入点都置 None（`grep -n 'key_priv' src/ai_researcher/loop.py` 现读），
`/tmp` 下六份旧 `loop.py` 副本（`airpush/airpkg/airpkg2/airpkg3/airpkg5/airv`）
都不含 `LOOP_SCHEMA` 字样（`grep -c LOOP_SCHEMA` 现读全 0），而全盘 `grep -rl loop_schema /tmp --include='*.py'`
**零命中** ⇒ 这个带 `loop_schema=2` 又带私钥的 state.json，不是我在盘上任何一份 `.py` 写得出来的。
这正是"两份可写副本会周期性红回来"的那类问题，只是这次连写者都不在可寻址范围内。

## 3. 定价板那格的均值被管道故障稀释了（已纠正，留此备案）

`reports/agi_arm_price_board.md` 给 AIR-CODEREPAIR 的 `INSTRUMENT_GAP_bar_carrier_missing`
写着"参照臂盘上不存在"——`demo/runs/coderepair-02` 就是同币种的第二块载体，当时没接进算式。
接进来后判决变为 `NOT_FUNDED_leg_resolved_worse_on_its_own_ruler`（见
`reports/coderepair_escalation_verdict.md`），并且顺带抓到：
`coderepair-01` 的 `llama3.2:3b` 两格各 40/40 条 `HTTPError 404`，
`policies` 却记成 `direct: 0.0 / step-calc: 0.0` ⇒ 那 80 次调用从未成功，
它的 `delta=0.0` 不是"两种策略一样差"。按 4 个模型平均得 −0.0563，排除这一格得 **−0.0750**
（稀释 25%，且方向是往"看起来无害"那边稀释）。新尺 `scripts/coderepair_escalation_verdict.py`
把这条做成判据（两侧同超 90% 才算死格），夹具 `--prove-red transport-masked` 证明它承重。

## 4. 其它未结（不在本轮能独立推进的范围）

- `taixuan-web` 的 3 条红要你拍板契约（缺 `is_alive()`、router 无 key 时 `error` 为 `None`
  而非 `'primary_disabled'`、qwen3 间歇性空正文）——补丁见 `../aidless-maintenance/patches/F26-...`。
- `life-planner` 的 `trust_cap` 走哪条路（发布/vendor/摘中间件）；补丁见 F24。
- `taixuan-web` 的 TLS：**我 10-09 记的"443 无服务 ⇒ 无 TLS"已经过期，现读作废**。
  2026-10-10 16:30 实测：443 开着，证书 `CN=wanxiangapp.xyz`、SAN 含 `www.`，
  Let's Encrypt（中间 CA `YR2`，链到 `ISRG Root X1`），有效期 `Sep 19 → Dec 18 2026`，
  用 `--resolve` 走域名打 https → `200`、`ssl_verify_result=0`（链验得过）；域名 HTTP → `301 Location: https://wanxiangapp.xyz/`。
  还剩下的三条真缺口（都在 IP 这一侧）：① README 第 7 行给的在线地址是 `http://116.62.69.83`，
  而**裸 IP 走 https 必然名字不匹配**（证书是给域名的）⇒ 指着 IP 教人用 HTTP 就是这条老问题的残躯；
  ② IP vhost 与域名 vhost **是两套不同的构建**：IP 版 3,339 字节、标题「传统文化工具箱」、链 `/liupai/bazi` 等，
  域名版 4,967 字节、标题「历法、天文与传统文化学习工具」、链 `/calendar.html`/`/culture.html`
  ⇒ 同一个箱子在公开面上跑着两个版本，README 宣传的是看起来较旧那一个；
  ③ HTTPS 侧**没有 HSTS**（现读响应头无 `Strict-Transport-Security`），且 `8080` 端口开着但对 GET 空应答（服务身份未辨）。
  另注：本机 `getent hosts wanxiangapp.xyz` 解析到 `198.18.0.26`（像是本地代理段），
  所以"公网 DNS 是否指向这台 ECS"本轮**未证**，上面全部结论都是用 `--resolve` 直连 `116.62.69.83` 得到的。
- nightly 重新启用、以及 10 条 issue 的关闭顺序——都需要 token 或你的点名。
- `AGI-KIT` 与 `agi-research` 两臂在工作区无本地载体（`not_carried` 现读），
  定价板里它们是 `NOT_CARRIED` 而不是"已定价为 0"。
