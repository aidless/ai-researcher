# AGI 候选臂 · 可判定性定价板（零机时）

运行 2026-10-09T03:38:56Z | read_only=True | sim_machine_minutes=0 | kaggle_writes=0

> 每个数由 `scripts/agi_arm_price_board.py` 从载体现读；判决由 prebuild-testability 原件给，不由本板命名。

| 臂 | 判决 | 币种 | 实测成本 |
|---|---|---|---|
| ARC2-MG | ESCALATION_TESTABLE_more_n_may_resolve | solved-task fraction on the 259-task HOLD | 见 JSON |
| GSM-TPR | INSTRUMENT_GAP_reference_ci_has_zero_width_because_n_is_1 | true-positive rate (no-TPR-loss clause) | 见 JSON |
| AIR-CODEREPAIR | INSTRUMENT_GAP_bar_carrier_missing | paired accuracy delta, step-calc − direct (per model) | {"minutes": 4.99, "ollama_calls": 320, "throughput_calls_per_min": 64.1} |
| GOODHART-C2 | PROMOTION_RULED_OUT_AT_EXISTING_N_bar_outside_ci_and_mean_far_below_bar | true_score (same env, paired by seed) | 见 JSON |
| AGI-KIT | NOT_CARRIED | — | — |
| agi-research | NOT_CARRIED | — | — |
| goodhart-project | PRICED_ABOVE (GOODHART-C2) | — | — |

## ARC2-MG — 再加 DSL 族还有没有可判的收益
{
 "verdict": "ESCALATION_TESTABLE_more_n_may_resolve",
 "kernel": {
  "bar": {
   "bar": 0.0098,
   "arithmetic": "0.027027 - 0.0172",
   "status": "OK"
  },
  "sign_convention": "candidate-better is mean>0",
  "ci_used": {
   "which": "naive",
   "ci": [
    -0.016575,
    0.016575
   ],
   "why": "clustered absent"
  },
  "promotion_test": {
   "magnitude_passes_bar": false,
   "abs_mean_over_bar_pct": 0.0,
   "bar_sized_advantage_inside_existing_ci": true
  },
  "escalation_arithmetic": {
   "n_for_ci90_to_exclude_zero_at_observed_mean": null,
   "n_for_a_bar_sized_effect": 3,
   "arithmetic": "n = (1.645 x sd / target)^2",
   "what_more_cells_buy": "a real chance of resolving the bar-sized effect"
  }
 }
}

## GSM-TPR — 这条臂能不能给别的臂定升档线
{
 "verdict": "INSTRUMENT_GAP_reference_ci_has_zero_width_because_n_is_1",
 "why": "三条 TPR 全是 1.0，而分母是 1：CI 宽度为 0 不是因为测得准，是因为只有一个正类样本。原件的 bar 规则只检查 bar>0，遇到这种退化 CI 会照样放行一个 bar —— 这是那台仪器的一个真实边界，本板不走它，改由本节直接判 GAP。",
 "consequence": "gsm8k 这条线有资格给 FPR 腿定价（k_curve 带计数的 Wilson），但没资格给别的臂定升档线",
 "usable_instead": {
  "carrier": "ablation.json verdict…k_curve",
  "k": 8,
  "fpr": 0.9825,
  "wilson95": [
   0.970840927975432,
   0.9895474564860909
  ]
 }
}

## AIR-CODEREPAIR — 把 coderepair 的 n 从 40 题拉到 157 值不值
{
 "verdict": "INSTRUMENT_GAP_bar_carrier_missing",
 "kernel": {}
}

## GOODHART-C2 — α 往代理最大方向推，真实分掉多少是判得开的
{
 "verdict": "PROMOTION_RULED_OUT_AT_EXISTING_N_bar_outside_ci_and_mean_far_below_bar",
 "kernel": {
  "bar": {
   "bar": 432.6175,
   "arithmetic": "444.022 - 11.4045",
   "status": "OK"
  },
  "sign_convention": "candidate-better is mean>0",
  "ci_used": {
   "which": "naive",
   "ci": [
    -457.355,
    -435.129
   ],
   "why": "clustered absent"
  },
  "promotion_test": {
   "magnitude_passes_bar": false,
   "abs_mean_over_bar_pct": 103.15,
   "bar_sized_advantage_inside_existing_ci": false
  },
  "escalation_arithmetic": {
   "n_for_ci90_to_exclude_zero_at_observed_mean": 1,
   "n_for_a_bar_sized_effect": 1,
   "arithmetic": "n = (2.802 x sd / target)^2",
   "what_more_cells_buy": "a tighter interval around the observed mean, never a promotion: the mean itself would have to reach the bar"
  }
 }
}
