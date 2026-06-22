"""
I8: Graceful Degradation with Confidence-Scored Partial Results — when a
task cannot be fully verified, NOVA still produces useful output at the
highest achievable confidence level rather than failing entirely.

Replaces EVO's binary SOLVED/INCOMPLETE with a graduated success spectrum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto, StrEnum
from typing import Any, Optional

from nova.confidence_calibrator import ConfidenceLevel, ConfidenceScore


class DegradationState(StrEnum):
    """Graduated success spectrum.
    
    Replaces EVO's binary SOLVED / INCOMPLETE with a 7-level spectrum.
    """
    FULLY_VERIFIED = "FULLY_VERIFIED"           # Meets or exceeds all requirements
    STRONGLY_VERIFIED = "STRONGLY_VERIFIED"       # Meets all core requirements, minor gaps
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"     # Core requirements met, some gaps
    MINIMALLY_VERIFIED = "MINIMALLY_VERIFIED"     # Minimum viable evidence
    PARTIAL_RESULTS = "PARTIAL_RESULTS"            # Some evidence, cannot verify fully
    SKETCH = "SKETCH"                              # Directional answer, insufficient evidence
    INCOMPLETE = "INCOMPLETE"                      # Nothing useful produced


@dataclass
class DegradationPlan:
    """Plan for graceful degradation when full verification fails."""
    target_state: DegradationState
    achieved_confidence: ConfidenceScore
    achieved_verification: list[str] = field(default_factory=list)
    missing_verification: list[str] = field(default_factory=list)
    fallback_strategy: str = ""
    partial_answer: str = ""
    reattempt_suggestions: list[str] = field(default_factory=list)


def degrade(required_confidence: float,
            achieved: ConfidenceScore,
            required_lean: bool = False,
            lean_available: bool = False,
            has_any_evidence: bool = False) -> DegradationState:
    """Determine the degradation state based on what was achieved."""
    p = achieved.probability
    level = achieved.level
    
    # Fully verified: meets or exceeds all requirements
    if p >= required_confidence and level == ConfidenceLevel.CERTIFIED:
        return DegradationState.FULLY_VERIFIED
    
    # Strongly verified: meets requirements, close to certified
    if p >= required_confidence and level in (ConfidenceLevel.STRONG, ConfidenceLevel.CERTIFIED):
        return DegradationState.STRONGLY_VERIFIED
    
    # Partially verified: meets core requirements
    if p >= required_confidence * 0.85 and level.value >= ConfidenceLevel.GOOD.value:
        return DegradationState.PARTIALLY_VERIFIED
    
    # Minimally verified: minimum viable evidence
    if p >= required_confidence * 0.7 and level.value >= ConfidenceLevel.MODERATE.value:
        return DegradationState.MINIMALLY_VERIFIED
    
    # Partial results: some evidence, cannot verify fully
    if has_any_evidence or level.value >= ConfidenceLevel.WEAK.value:
        return DegradationState.PARTIAL_RESULTS
    
    # Sketch: directional but insufficient
    if level.value >= ConfidenceLevel.SPECULATIVE.value:
        return DegradationState.SKETCH
    
    return DegradationState.INCOMPLETE


def format_degradation_state(state: DegradationState) -> str:
    """Format a degradation state for display with an icon."""
    icons = {
        DegradationState.FULLY_VERIFIED: "\u2714\ufe0f",
        DegradationState.STRONGLY_VERIFIED: "\u2705",
        DegradationState.PARTIALLY_VERIFIED: "\ud83d\udccb",
        DegradationState.MINIMALLY_VERIFIED: "\ud83d\udca1",
        DegradationState.PARTIAL_RESULTS: "\ud83d\udd0d",
        DegradationState.SKETCH: "\u270f\ufe0f",
        DegradationState.INCOMPLETE: "\u274c",
    }
    icon = icons.get(state, "\u2753")
    return f"{icon} **{state.value}**"
