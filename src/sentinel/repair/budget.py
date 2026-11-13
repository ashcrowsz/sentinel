"""Stop conditions for the repair loop.

The verifier is code (the test suite), never the model's opinion. The loop
stops on the first of: tests green, max iterations, cost budget, or the same
failure twice in a row (no progress).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum


class StopReason(str, Enum):
    fixed = "fixed"
    max_iterations = "max_iterations"
    budget = "budget"
    no_progress = "no_progress"
    tampering = "tampering"


# timestamps, durations, memory addresses and tmp paths change between runs
_NOISE = re.compile(r"(0x[0-9a-f]+|\d+\.\d+s|\d{2}:\d{2}:\d{2}|/tmp/[\w/.-]+)")


def failure_fingerprint(log: str) -> str:
    """Stable hash of a failure, ignoring run-to-run noise."""
    lines = [ln for ln in log.splitlines() if "Error" in ln or "FAILED" in ln or "assert" in ln]
    normalized = _NOISE.sub("<x>", "\n".join(lines[-40:]))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


@dataclass
class RepairBudget:
    max_iterations: int = 4
    max_cost_usd: float = 0.50
    iterations: int = 0
    cost_usd: float = 0.0
    fingerprints: list[str] = field(default_factory=list)

    def record(self, *, cost_usd: float, failure_log: str | None) -> None:
        self.iterations += 1
        self.cost_usd += cost_usd
        if failure_log is not None:
            self.fingerprints.append(failure_fingerprint(failure_log))

    def should_stop(self, *, tests_passed: bool) -> StopReason | None:
        if tests_passed:
            return StopReason.fixed
        if len(self.fingerprints) >= 2 and self.fingerprints[-1] == self.fingerprints[-2]:
            return StopReason.no_progress
        if self.cost_usd >= self.max_cost_usd:
            return StopReason.budget
        if self.iterations >= self.max_iterations:
            return StopReason.max_iterations
        return None
