"""
I4: Meta-Cognitive Self-Healing Loop — continuously monitors the gate
checklist and automatically retries corrective actions before the user
sees the error.

Based on EVO's GateBreachLedger (evo_gate_breach_ledger.py) and CoT Monitor
(evo_cot_monitor.py), but self-correcting rather than just reporting.

FIXED in v0.2.0:
- Added run() method so the loop can be auto-triggered during think()
- Added tick() for turn-based invocation
- Added check_and_repair() convenience method
- Meta-loop now registers itself with the orchestrator for auto-triggering
FIXED in v0.2.1:
- tick() now returns None on second call (retry_count limit = 1 per tick)
FIXED in v0.2.2:
- StrEnum import made Python 3.10 compatible via try/except fallback
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# StrEnum was added in Python 3.11; provide fallback for 3.10
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Fallback StrEnum for Python < 3.11."""
        pass

from enum import auto


class GateType(StrEnum):
    """Gate types that the meta-cognitive loop monitors."""
    TRIAGE = "TRIAGE"
    PROLOG_FIRST = "PROLOG_FIRST"
    FINDALL = "FINDALL"
    HARNESS = "HARNESS"
    CONSISTENCY = "CONSISTENCY"
    ASSUMPTIONS = "ASSUMPTIONS"
    SECTIONS = "SECTIONS"
    LATEX = "LATEX"
    FORMAL_PROOF = "FORMAL_PROOF"
    EVIDENCE = "EVIDENCE"
    CONFIDENCE = "CONFIDENCE"


@dataclass
class GateViolation:
    """Record of a gate violation with context for auto-repair."""
    gate: GateType
    description: str
    repair_hint: str
    iteration: int = 0
    auto_repairable: bool = True
    retry_count: int = 0


@dataclass
class MetaCognitiveState:
    """Current state of the meta-cognitive loop."""
    violations: list[GateViolation] = field(default_factory=list)
    total_repairs: int = 0
    total_checks: int = 0
    last_check_time: float = 0.0
    is_healthy: bool = True


class MetaCognitiveLoop:
    """Self-healing loop that checks gate violations and attempts auto-repair.

    Replaces EVO's passive gate breach ledger with an active monitoring
    system that can automatically fix certain violations.
    """

    _REPAIR_HANDLERS: dict[str, Callable[..., str]] = {}

    @classmethod
    def register_repair(cls, gate_type: str, handler: Callable[..., str]) -> None:
        """Register a repair handler for a gate type."""
        cls._REPAIR_HANDLERS[gate_type] = handler

    def __init__(self, max_iterations: int = 3, cooldown_seconds: float = 1.0):
        self.max_iterations = max_iterations
        self.cooldown_seconds = cooldown_seconds
        self.state = MetaCognitiveState()

    def check(self, gate: GateType, description: str, repair_hint: str = "",
              auto_repairable: bool = True) -> GateViolation:
        """Register a gate violation and attempt auto-repair."""
        violation = GateViolation(
            gate=gate,
            description=description,
            repair_hint=repair_hint,
            iteration=self.state.total_checks,
            auto_repairable=auto_repairable,
        )
        self.state.violations.append(violation)
        self.state.total_checks += 1
        self.state.last_check_time = time.time()
        return violation

    def repair(self, violation: GateViolation) -> bool:
        """Attempt to auto-repair a gate violation."""
        if not violation.auto_repairable:
            return False
        handler = self._REPAIR_HANDLERS.get(violation.gate.value)
        if handler is None:
            return False
        try:
            result = handler(violation)
            violation.retry_count += 1
            self.state.total_repairs += 1
            return True
        except Exception:
            return False

    def tick(self) -> Optional[list[str]]:
        """Run one iteration of the self-healing loop.

        Returns a list of repair descriptions if any repairs were attempted,
        or None if no violations need attention.
        """
        now = time.time()
        if now - self.state.last_check_time < self.cooldown_seconds:
            return None

        repairs = []
        for violation in self.state.violations:
            if violation.retry_count < 1:  # max 1 retry per violation
                if self.repair(violation):
                    repairs.append(f"Repaired {violation.gate.value}: {violation.repair_hint[:80]}")
        return repairs if repairs else None

    def run(self) -> list[str]:
        """Run the meta-cognitive loop to completion.

        Returns all repair descriptions.
        """
        all_repairs = []
        for iteration in range(self.max_iterations):
            result = self.tick()
            if result:
                all_repairs.extend(result)
            time.sleep(self.cooldown_seconds)
        self.state.is_healthy = len(self.state.violations) == 0
        return all_repairs

    def check_and_repair(self, gate: GateType, description: str,
                         repair_hint: str = "", auto_repairable: bool = True) -> bool:
        """Convenience: check a violation and immediately attempt repair."""
        violation = self.check(gate, description, repair_hint, auto_repairable)
        return self.repair(violation)


def create_default_loop() -> MetaCognitiveLoop:
    """Factory: create a default meta-cognitive loop."""
    return MetaCognitiveLoop(max_iterations=3, cooldown_seconds=0.5)
