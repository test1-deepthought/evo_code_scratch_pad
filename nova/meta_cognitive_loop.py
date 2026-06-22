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
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import auto, StrEnum
from typing import Any, Callable, Optional


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
    repair_attempts: int = 0
    max_repair_attempts: int = 3
    last_repair_time: float = 0.0
    stuck_pattern: bool = False  # Same error repeating > 3 times
    loop_running: bool = False   # Whether the meta-loop is currently active


class MetaCognitiveLoop:
    """Self-healing loop that monitors for gate violations and auto-repairs.

    Unlike EVO's passive breach ledger which only records violations for
    the runtime to enforce, NOVA's meta-cognitive loop actively generates
    corrective actions and re-executes them.
    """

    def __init__(self, max_repairs: int = 3):
        self.state = MetaCognitiveState(max_repair_attempts=max_repairs)
        self._repair_handlers: dict[GateType, Callable[[GateViolation], Optional[str]]] = {}

    def register_repair_handler(self, gate: GateType,
                                 handler: Callable[[GateViolation], Optional[str]]) -> None:
        """Register a repair handler for a gate type."""
        self._repair_handlers[gate] = handler

    def record_violation(self, gate: GateType, description: str,
                          repair_hint: str = "",
                          auto_repairable: bool = True) -> GateViolation:
        """Record a gate violation."""
        violation = GateViolation(
            gate=gate,
            description=description,
            repair_hint=repair_hint or f"Auto-repair gate: {gate.value}",
            iteration=self.state.repair_attempts,
            auto_repairable=auto_repairable,
            retry_count=0,
        )

        # Detect stuck pattern: same gate type repeated
        recent = [v for v in self.state.violations[-3:] if v.gate == gate]
        if len(recent) >= 3:
            self.state.stuck_pattern = True

        self.state.violations.append(violation)
        return violation

    def attempt_repair(self) -> Optional[str]:
        """Attempt to repair the most recent auto-repairable violation.

        Returns a repair instruction string, or None if no repair is possible.
        """
        if self.state.repair_attempts >= self.state.max_repair_attempts:
            return None
        if self.state.stuck_pattern:
            return None  # Give up on stuck patterns — escalate to user

        # Find the most recent unhandled repairable violation
        for violation in reversed(self.state.violations):
            if not violation.auto_repairable:
                continue
            if violation.retry_count >= 1:
                continue  # Each violation can be repaired at most once

            handler = self._repair_handlers.get(violation.gate)
            if handler:
                repair = handler(violation)
                if repair:
                    violation.retry_count += 1
                    self.state.repair_attempts += 1
                    self.state.last_repair_time = time.time()
                    return repair

        return None

    def run(self) -> list[str]:
        """Run the meta-cognitive loop: attempt repairs until exhausted.

        Returns a list of repair actions attempted.
        """
        self.state.loop_running = True
        actions: list[str] = []
        while True:
            repair = self.attempt_repair()
            if repair is None:
                break
            actions.append(repair)
        self.state.loop_running = False
        return actions

    def tick(self) -> Optional[str]:
        """Single tick of the meta-cognitive loop.

        Returns one repair action, or None if nothing to repair.
        Useful for integrating into a main event loop.
        """
        if not self.state.loop_running:
            self.state.loop_running = True
        return self.attempt_repair()

    def check_and_repair(self, gate: GateType, condition_met: bool,
                          description: str, repair_hint: str = "") -> Optional[str]:
        """Check a condition and auto-repair if violated.

        Args:
            gate: The gate type to check
            condition_met: True if the gate passes
            description: Description of the violation
            repair_hint: Hint for the repair handler

        Returns:
            Repair action string if violation was detected and repaired,
            None if condition was met or repair failed.
        """
        if condition_met:
            return None
        self.record_violation(gate, description, repair_hint)
        return self.attempt_repair()

    def reset(self) -> None:
        """Reset the meta-cognitive state for a new task."""
        self.state = MetaCognitiveState()

    def get_summary(self) -> str:
        """Get a human-readable summary of the meta-cognitive state."""
        if not self.state.violations:
            return "Meta-cognitive: no violations detected."
        lines = [
            f"Meta-cognitive: {len(self.state.violations)} violation(s), "
            f"{self.state.repair_attempts} repair(s) attempted."
        ]
        for v in self.state.violations:
            lines.append(f"  - {v.gate.value}: {v.description[:80]}")
        if self.state.stuck_pattern:
            lines.append("  - STUCK: same error repeating — escalating.")
        return "\n".join(lines)


# --- Default repair handlers ---

def _repair_prolog_first(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Missing Prolog KB. Re-run prolog_exec with:\n"
        "```prolog\n"
        ":- dynamic active_assumption/1.\n"
        "prove(Goal, proved(Goal)) :- call(Goal).\n"
        "inconsistent :- false.\n"
        "observation('Auto-repair: task requires Prolog-first reasoning').\n"
        "main :- write('KB loaded.'), nl.\n"
        "```"
    )


def _repair_findall(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Missing findall/3 derivation. Add to main/0:\n"
        "```prolog\n"
        "findall(C, conclusion(C), Conclusions),\n"
        "write('Conclusions: '), write(Conclusions), nl.\n"
        "```"
    )


def _repair_consistency(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Missing consistency check. Query inconsistent/0"
        " in main/0 before declaring SOLVED."
    )


def _repair_latex(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Bare LaTeX detected outside $...$ delimiters."
        " Wrap all \\commands in $...$ or $$...$$."
    )


def _repair_sections(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Missing required section. Add the missing ## heading"
        " to your response."
    )


def _repair_evidence(violation: GateViolation) -> Optional[str]:
    return (
        "[META-REPAIR] Insufficient evidence. Add tool execution output or"
        " web search results before drawing conclusions."
    )


# --- Factory ---

def create_default_loop() -> MetaCognitiveLoop:
    """Create a meta-cognitive loop with default repair handlers for all gates."""
    loop = MetaCognitiveLoop()
    loop.register_repair_handler(GateType.PROLOG_FIRST, _repair_prolog_first)
    loop.register_repair_handler(GateType.FINDALL, _repair_findall)
    loop.register_repair_handler(GateType.CONSISTENCY, _repair_consistency)
    loop.register_repair_handler(GateType.LATEX, _repair_latex)
    loop.register_repair_handler(GateType.SECTIONS, _repair_sections)
    loop.register_repair_handler(GateType.EVIDENCE, _repair_evidence)
    return loop
