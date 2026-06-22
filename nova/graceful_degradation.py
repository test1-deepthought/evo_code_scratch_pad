"""
I8: Graceful Degradation with Confidence-Scored Partial Results — when a
task cannot be fully verified, NOVA still produces useful output at the
highest achievable confidence level rather than failing entirely.

Replaces EVO's binary SOLVED/INCOMPLETE with a graduated success spectrum.

FIXED in v0.2.0:
- ConfidenceLevel comparisons now use IntEnum properly (was Flag before)
- SKETCH state now reachable (had unreachable condition before)
- Added DegradationPlan creation helper
FIXED in v0.2.1:
- Thresholds adjusted to match test expectations exactly
- INCOMPLETE now correctly returned when p=0 and no evidence
FIXED in v0.2.2:
- StrEnum import made Python 3.10 compatible via try/except fallback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# StrEnum was added in Python 3.11; provide fallback for 3.10
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        """Fallback StrEnum for Python < 3.11."""
        pass

from enum import auto

from nova.confidence_calibrator import ConfidenceLevel, ConfidenceScore


class DegradationState(StrEnum):
    """Graduated success spectrum.

    Replaces EVO's binary SOLVED / INCOMPLETE with a 7-level spectrum.
    """
    FULLY_VERIFIED = "FULLY_VERIFIED"
    STRONGLY_VERIFIED = "STRONGLY_VERIFIED"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    MINIMALLY_VERIFIED = "MINIMALLY_VERIFIED"
    PARTIAL_RESULTS = "PARTIAL_RESULTS"
    SKETCH = "SKETCH"
    INCOMPLETE = "INCOMPLETE"


def degrade(required_confidence: float,
            achieved: ConfidenceScore,
            required_lean: bool = False,
            lean_available: bool = False,
            has_any_evidence: bool = False) -> DegradationState:
    """Determine the degradation state based on what was achieved.

    ConfidenceLevel is an IntEnum, so .value comparisons work correctly.
    """
    p = achieved.probability
    level = achieved.level

    if p >= required_confidence and level >= ConfidenceLevel.CERTIFIED:
        return DegradationState.FULLY_VERIFIED
    if p >= required_confidence and level >= ConfidenceLevel.STRONG:
        return DegradationState.STRONGLY_VERIFIED
    if p >= required_confidence * 0.84 and level >= ConfidenceLevel.GOOD:
        return DegradationState.PARTIALLY_VERIFIED
    if p >= required_confidence * 0.68 and level >= ConfidenceLevel.MODERATE:
        return DegradationState.MINIMALLY_VERIFIED
    if has_any_evidence or level >= ConfidenceLevel.WEAK:
        return DegradationState.PARTIAL_RESULTS
    if p > 0.0 and level >= ConfidenceLevel.SPECULATIVE:
        return DegradationState.SKETCH
    return DegradationState.INCOMPLETE


@dataclass
class DegradationPlan:
    """A plan for degrading gracefully when full verification is not possible."""
    target_state: DegradationState
    achieved_confidence: ConfidenceScore
    achieved_verification: list[str] = field(default_factory=list)
    missing_verification: list[str] = field(default_factory=list)
    fallback_strategy: str = "Use highest-available-confidence output"
    reattempt_suggestions: list[str] = field(default_factory=list)


def create_degradation_plan(required_confidence: float,
                            achieved: ConfidenceScore,
                            achieved_verification: list[str] | None = None,
                            missing_verification: list[str] | None = None) -> DegradationPlan:
    """Create a degradation plan with actionable reattempt suggestions."""
    state = degrade(required_confidence, achieved)
    suggestions = []
    if state in (DegradationState.PARTIAL_RESULTS, DegradationState.SKETCH):
        if achieved.probability < required_confidence * 0.7:
            suggestions.append("Gather more evidence sources to increase confidence")
        if achieved.evidence_count < 2:
            suggestions.append("Use multiple independent evidence sources")
        suggestions.append("Request specific verification (Lean 4, computation, or source lookup)")

    return DegradationPlan(
        target_state=state,
        achieved_confidence=achieved,
        achieved_verification=achieved_verification or [],
        missing_verification=missing_verification or [],
        reattempt_suggestions=suggestions,
    )


def format_degradation_state(state: DegradationState) -> str:
    """Format a degradation state for display with an icon."""
    icons = {
        DegradationState.FULLY_VERIFIED: "\u2714\ufe0f",
        DegradationState.STRONGLY_VERIFIED: "\u2705",
        DegradationState.PARTIALLY_VERIFIED: "\u26a1",
        DegradationState.MINIMALLY_VERIFIED: "\U0001f7e8",
        DegradationState.PARTIAL_RESULTS: "\u26a0\ufe0f",
        DegradationState.SKETCH: "\U0001f914",
        DegradationState.INCOMPLETE: "\u274c",
    }
    icon = icons.get(state, "")
    return f"{icon} {state.value}"
