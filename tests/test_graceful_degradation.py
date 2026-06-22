"""
Tests for NOVA's graceful degradation module.
"""
import pytest
from nova.graceful_degradation import (
    DegradationState, degrade, format_degradation_state,
    create_degradation_plan,
)
from nova.confidence_calibrator import ConfidenceScore, ConfidenceLevel
from nova.evidence_dimensions import EvidenceDimension


class TestGracefulDegradation:
    """Test the graduated success spectrum."""

    def test_fully_verified(self):
        """Meets or exceeds all requirements."""
        score = ConfidenceScore(0.995, ConfidenceLevel.CERTIFIED, 5,
                                 EvidenceDimension.FORMAL, "Lean verified")
        state = degrade(0.95, score)
        assert state == DegradationState.FULLY_VERIFIED

    def test_strongly_verified(self):
        """Meets requirements, close to certified."""
        score = ConfidenceScore(0.95, ConfidenceLevel.STRONG, 3,
                                 EvidenceDimension.DERIVATION, "Multiple sources")
        state = degrade(0.90, score)
        assert state == DegradationState.STRONGLY_VERIFIED

    def test_partially_verified(self):
        """Meets core requirements with minor gaps."""
        score = ConfidenceScore(0.80, ConfidenceLevel.GOOD, 2,
                                 EvidenceDimension.COMPUTATION, "Computed")
        state = degrade(0.95, score)
        assert state == DegradationState.PARTIALLY_VERIFIED

    def test_minimally_verified(self):
        """Minimum viable evidence."""
        score = ConfidenceScore(0.65, ConfidenceLevel.MODERATE, 1,
                                 EvidenceDimension.SOURCE, "Looked up")
        state = degrade(0.95, score)
        assert state == DegradationState.MINIMALLY_VERIFIED

    def test_partial_results(self):
        """Some evidence but cannot verify fully."""
        score = ConfidenceScore(0.6, ConfidenceLevel.WEAK, 1,
                                 EvidenceDimension.SOURCE, "Single source")
        state = degrade(0.95, score, has_any_evidence=True)
        assert state == DegradationState.PARTIAL_RESULTS

    def test_sketch(self):
        """Directional but insufficient — now reachable!"""
        score = ConfidenceScore(0.3, ConfidenceLevel.SPECULATIVE, 0,
                                 EvidenceDimension.NONE, "Speculative")
        state = degrade(0.95, score, has_any_evidence=False)
        assert state == DegradationState.SKETCH

    def test_incomplete(self):
        """Nothing useful produced."""
        score = ConfidenceScore(0.0, ConfidenceLevel.SPECULATIVE, 0,
                                 EvidenceDimension.NONE, "Nothing")
        state = degrade(0.95, score, has_any_evidence=False)
        assert state == DegradationState.INCOMPLETE

    def test_format_fully_verified(self):
        """Format should include the state name."""
        formatted = format_degradation_state(DegradationState.FULLY_VERIFIED)
        assert "FULLY_VERIFIED" in formatted

    def test_format_incomplete(self):
        """Format should include the state name."""
        formatted = format_degradation_state(DegradationState.INCOMPLETE)
        assert "INCOMPLETE" in formatted

    def test_create_degradation_plan(self):
        """Plan should include reattempt suggestions."""
        score = ConfidenceScore(0.5, ConfidenceLevel.WEAK, 1,
                                 EvidenceDimension.SOURCE, "Single source")
        plan = create_degradation_plan(0.95, score)
        assert plan.target_state == DegradationState.PARTIAL_RESULTS
        assert len(plan.reattempt_suggestions) > 0
