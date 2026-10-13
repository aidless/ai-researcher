# 附录：开源 NLI 裁决（替代人工标注的第一步，不是替代品）

> 方法：VitaminC-MNLI（`tals/albert-xlarge-vitaminc-mnli`，本地 snapshot，
> CPU，truncation 512）。premise＝v3b 对同题的长回答，hypothesis＝v3c 短回答，
> 双向。原始输出：`nli_adjudication.json`（本目录；`nli_adjudicate.py` 重跑逐字节相同，已验证）。
> 依赖：torch（系统已有）＋ sentencepiece（`/tmp/nli-pkgs`，uv `--target` 安装，
> 注意 cp312 版——cp311 版会 ImportError，此坑已踩过）。
> 明确不是什么：NLI ≠ 人工语义判断；一致 ≠ 正确（两臂可能同错）。
> 人工双人标注仍缺（需真人，见 SIGNATURES.md S5）。

## 结果（10 项，long→short 方向）

| id | SUPPORTS | REFUTES | NEI | 读法 |
|---|---|---|---|---|
| c021 | 0.037 | 0.174 | 0.788 | NEI |
| c022 | 0.844 | 0.048 | 0.108 | 支持 |
| c023 | 0.330 | 0.391 | 0.279 | 接近，未达 |
| c024 | 0.883 | 0.022 | 0.095 | 支持 |
| c025 | 0.072 | 0.172 | 0.756 | NEI |
| c026 | 0.053 | 0.160 | 0.787 | NEI |
| c027 | 0.024 | 0.059 | 0.917 | NEI |
| c028 | 0.056 | 0.176 | 0.768 | NEI |
| c029 | 0.961 | 0.014 | 0.025 | 支持 |
| c030 | 0.888 | 0.029 | 0.083 | 支持（注：裸复读被长文蕴含 trivially） |

反向（short→long）全部 NEI（0.85–0.91）——短文本蕴含不了千字长文，符合预期，
不是负证据。

## 诚实解读

- **证伪了"矛盾"**：10 项 REFUTES 最高 0.391，无一项以 REFUTES 为主。
  NLI 模型从未说短回答与长回答矛盾。
- **没证出"正确"**：6 项 NEI 为主。NEI 占优与领域失配有关
  （VitaminC 训练于英文事实 claim，本数据是中英混合技术诊断），不能解读为
  "答案不好"，同样不能解读为"答案好"。
- 三角定位（每项独立证据，不互相替代）：过全部 reference 检查（强）＋
  12/16 含实质因果内容（描述性）＋NLI 零矛盾（弱支持）。
- v2 的 6 项未测（无跨臂长回答对照）；c030 类裸复读的 SUPPORT 系 trivial 蕴含，
  已注明，不计入"语义正确"证据。

## 可复现

```bash
PYTHONPATH=/tmp/nli-pkgs python3 PAPER/nli_adjudicate.py  # 重写 nli_adjudication.json
# 已验证：重跑与存档逐字节相同（byte-identical，比对过）。
# 注意：/tmp 重启即丢。若 nli-pkgs 没了，用附录顶部命令重装（30 秒），不要动系统 pip。
```
sentencepiece 安装坑已踩过（见会话记录）：PEP 668 拦系统 pip，uv 默认解释器
下错 cp311 包，必须 `--python /usr/bin/python3`。重装时照抄上面命令。
