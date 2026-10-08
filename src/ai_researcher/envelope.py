"""Preregistration envelope: the one human decision, made executable.

A fully automatic researcher cannot mean "no human ever" -- that is how you get
a machine that spends money proving nothing. It means the human decides ONCE, up
front, inside a machine-checkable contract, and the machine then runs unattended
inside that contract. Anything outside it stops the run without asking.

The envelope is:
  hypothesis   -- what is claimed, in falsifiable form
  methods      -- the exact command that produces evidence, plus what counts
  budget       -- max rounds, max cost, max wall-clock; exceeding any stops the run
  kill_switch  -- pre-registered decision rules in the H10 style: mutually
                  exclusive outcome rows, each naming its action. No row may say
                  "decide later".
  evidence     -- what artifacts must exist for a round to count

The loop (loop.py) refuses to start without a signed envelope, and refuses to
continue past any violated bound. There is no override flag by design.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KillRow:
    """One mutually exclusive outcome row: condition -> action."""
    condition: str          # e.g. "gain >= 0.10"
    action: str             # STOP-EXTEND | STOP-REFUTED | STOP-REFUTED-REVERSE | CONTINUE
    note: str = ""          # why this threshold (power analysis, cost, prior)


@dataclass
class Power:
    """Pre-registered power analysis. Thresholds without power are guesses."""
    n: int = 0                # planned sample size per condition
    alpha: float = 0.05
    min_detectable_effect: float = 0.0   # smallest effect worth detecting
    power_at_mde: float = 0.0            # must be >= 0.8 to be executable
    # What the power block is actually about. `required_n` computes a paired
    # proportion difference, which does not describe every endpoint: a
    # "does at least one decision flip" endpoint is a count, and forcing it into
    # the paired formula produced a nonsense mde (breadth-02: 0.6 flips of a
    # proportion). Declaring the endpoint keeps the mismatch visible instead of
    # letting a wrong-shaped claim pass as if it were checked.
    endpoint: str = ""



def required_n(mde: float, alpha: float = 0.05, power: float = 0.8,
               paired: bool = True, baseline: float = 0.5) -> int:
    """Smallest n (per arm, paired items) that detects `mde` at the given power.

    Normal approximation on paired proportions with worst-case discordance:
    var = (b + c - (b - c) ** 2 / n) / n, maximised over the discordant fraction at
    b + c = 2 * mde-ish scale, which for a two-sided paired test at baseline 0.5 is
    approximately var = 2 * p_disc / n with p_disc = 2 * mde. Solved for n.

    Returns 0 when mde is unusable. Intentionally conservative: it over-estimates
    n slightly, because over-collecting is recoverable and under-collecting is
    the failure this project kept paying for.
    """
    try:
        mde = float(mde)
        alpha = float(alpha)
        power = float(power)
    except (TypeError, ValueError):
        return 0
    if not (0 < mde < 1) or not (0 < power < 1):
        return 0
    z_a = {0.05: 1.959964, 0.01: 2.575829}.get(round(alpha, 2), 1.959964)
    # normal quantile for the requested power
    z_b = {0.80: 0.841621, 0.85: 1.036433, 0.90: 1.281552, 0.95: 1.644854}.get(
        round(power, 2))
    if z_b is None:  # crude interpolation for unusual targets
        z_b = 0.841621 + (power - 0.80) * 3.0
    if paired:
        # McNemar: n >= (z_a + z_b)^2 * p_disc / mde^2 with p_disc ~ 2*mde
        p_disc = min(1.0, 2.0 * mde)
        n = ((z_a + z_b) ** 2) * p_disc / (mde ** 2)
    else:
        p = min(max(baseline + mde, 1e-6), 1 - 1e-6)
        pbar = min(max(baseline + mde / 2.0, 1e-6), 1 - 1e-6)
        var = p * (1 - p) + pbar * (1 - pbar)
        n = ((z_a + z_b) ** 2) * 2.0 * var / (mde ** 2)
    return int(math.ceil(n))


@dataclass
class Envelope:
    hypothesis: str
    methods: str            # the exact command, e.g. "python scripts/run_exp.py --config {config}"
    max_rounds: int
    max_cost_usd: float = 0.0
    max_wall_hours: float = 24.0
    kill_switch: list = field(default_factory=list)   # list[KillRow]
    required_artifacts: list = field(default_factory=list)
    approved_by: str = ""
    approved_at: str = ""
    seed: int = 0           # fixed seed for the methods command (EVO_SEED); 0 = not fixed
    power: object = None    # Power; None = not declared (refused by validate)
    negative_publish: str = ""  # what happens on refute: "replication-report" | "archive" (must choose)
    tension: str = ""       # the research tension (oral practice #1 + Hamming):
                            # an unmet operational requirement OR a discrepancy between
                            # theoretical expectation and reported observation, plus what
                            # answering it would change. A hypothesis without a tension
                            # is a solution in search of a problem and is refused.

    def validate(self) -> list:
        """Return a list of problems. Empty means executable."""
        problems = []
        if not self.hypothesis.strip():
            problems.append("hypothesis is empty")
        if not self.methods.strip():
            problems.append("methods is empty (must be an exact command)")
        if self.max_rounds < 1:
            problems.append("max_rounds must be >= 1")
        if not self.kill_switch:
            problems.append("kill_switch has no rows: the loop would not know when to stop")
        actions = {r.action for r in self.kill_switch}
        if "CONTINUE" in actions and len(actions) == 1:
            problems.append("kill_switch has only CONTINUE: nothing ever stops the run")
        for r in self.kill_switch:
            if r.action not in ("STOP-EXTEND", "STOP-REFUTED", "STOP-REFUTED-REVERSE",
                                "STOP-INCONCLUSIVE", "CONTINUE"):
                problems.append(f"unknown action {r.action!r} (row: {r.condition!r})")
            if not r.condition.strip():
                problems.append("kill_switch row with empty condition")
        if not self.approved_by:
            problems.append("not approved: approved_by is empty (the one human decision)")
        if self.seed == 0:
            problems.append("seed is 0 (not fixed): same command must give same assignment; "
                            "set EVO_SEED via methods")
        p = self.power
        if p is None:
            problems.append("no power analysis: thresholds without power are guesses; "
                            "declare n/alpha/min_detectable_effect/power_at_mde")
        else:
            if p.power_at_mde < 0.8:
                problems.append(f"power_at_mde={p.power_at_mde} < 0.8: underpowered by design; "
                                f"raise n (now {p.n}) or narrow the claim")
            if p.alpha not in (0.05, 0.01):
                problems.append(f"alpha={p.alpha}: use 0.05 or 0.01 unless preregistered otherwise")
            # Power pre-check: the declared n must actually detect the declared
            # minimum effect. Every two-seat review in this project eventually
            # said the same thing -- "n=40 cannot resolve a 1-2 point difference" --
            # so the shortfall was discovered after spending the compute. The
            # check is deliberately conservative (normal approximation on paired
            # proportions) and refuses rather than warns.
            need = required_n(getattr(p, "min_detectable_effect", None) or 0.1,
                              alpha=p.alpha, power=p.power_at_mde,
                              paired=True, baseline=0.5)
            if need and p.n < need:
                problems.append(
                    f"underpowered by design: n={p.n} cannot detect "
                    f"mde={getattr(p, 'min_detectable_effect', None)} at alpha={p.alpha} "
                    f"with power={p.power_at_mde}; need n>={need}. Either raise n or "
                    f"declare a larger min_detectable_effect (i.e. promise less)")
        if self.negative_publish not in ("replication-report", "archive"):
            problems.append("negative_publish must be 'replication-report' or 'archive': "
                            "a refute without a publication plan is publication bias by design")
        if len(self.tension.strip()) < 50:
            problems.append("tension too short (<50 chars): state the unmet requirement or "
                            "the theory-vs-observation discrepancy, plus what answering it "
                            "would change. Cf. Hamming: which important problem is this?")
        return problems

    def to_dict(self) -> dict:
        p = self.power
        return {
            "hypothesis": self.hypothesis,
            "methods": self.methods,
            "max_rounds": self.max_rounds,
            "max_cost_usd": self.max_cost_usd,
            "max_wall_hours": self.max_wall_hours,
            "kill_switch": [{"condition": r.condition, "action": r.action,
                             "note": r.note} for r in self.kill_switch],
            "required_artifacts": self.required_artifacts,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "seed": self.seed,
            "tension": self.tension,
            "power": {"n": p.n, "alpha": p.alpha,
                      "min_detectable_effect": p.min_detectable_effect,
                      "power_at_mde": p.power_at_mde} if p else None,
            "negative_publish": self.negative_publish,
        }

    @staticmethod
    def from_dict(d: dict) -> "Envelope":
        pd = d.get("power")
        return Envelope(
            hypothesis=d.get("hypothesis", ""),
            methods=d.get("methods", ""),
            max_rounds=int(d.get("max_rounds", 0)),
            max_cost_usd=float(d.get("max_cost_usd", 0.0)),
            max_wall_hours=float(d.get("max_wall_hours", 24.0)),
            kill_switch=[KillRow(**r) for r in d.get("kill_switch", [])],
            required_artifacts=list(d.get("required_artifacts", [])),
            approved_by=d.get("approved_by", ""),
            approved_at=d.get("approved_at", ""),
            seed=int(d.get("seed", 0)),
            power=Power(**pd) if isinstance(pd, dict) else None,
            negative_publish=d.get("negative_publish", ""),
            tension=d.get("tension", ""),
        )

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @staticmethod
    def load(path) -> "Envelope":
        return Envelope.from_dict(
            json.loads(Path(path).read_text(encoding="utf-8")))
