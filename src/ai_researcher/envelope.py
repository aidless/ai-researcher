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
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KillRow:
    """One mutually exclusive outcome row: condition -> action."""
    condition: str          # e.g. "gain >= 0.10"
    action: str             # STOP-EXTEND | STOP-REFUTED | STOP-REFUTED-REVERSE | CONTINUE
    note: str = ""          # why this threshold (power analysis, cost, prior)


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
        return problems

    def to_dict(self) -> dict:
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
        }

    @staticmethod
    def from_dict(d: dict) -> "Envelope":
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
        )

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @staticmethod
    def load(path) -> "Envelope":
        return Envelope.from_dict(
            json.loads(Path(path).read_text(encoding="utf-8")))
