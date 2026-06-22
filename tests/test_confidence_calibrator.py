"""
Tests for NOVA's confidence calibration module.
"""
import pytest
from nova.confidence_calibrator import (
    ConfidenceCalibrator, ConfidenceScore, ConfidenceLevel,
    SOURCE_RELIABILITY, DIMENSION_PRIORS
)
from nova.evidence_dimensions import EvidenceDimension


class TestConfidenceCalibrator:
    """Test the Bayesian confidence calibrator."""

    def test_estimate_lean_high(self):
        """Lean verification should produce high confidence."""
        score = ConfidenceCalibrator.estimate(
            evidence_sources=["lean4_exec", "prolog_exec"],
            dimensions=EvidenceDimension.FORMAL,
        )
        assert score.probability > 0.9
        assert score.level >= ConfidenceLevel.STRONG

    def test_estimate_internal_low(self):
        """Internal knowledge should produce moderate-to-low confidence."""
        score = ConfidenceCalibrator.estimate(
            evidence_sources=["internal_knowledge"],
            dimensions=EvidenceDimension.EXPLANATION,
        )
        assert score.probability < 0.8

    def test_consistency_penalty(self):
        """Inconsistent results should reduce confidence."""
        score_consistent = ConfidenceCalibrator.estimate(
            evidence_sources=["lean4_exec"],
            consistency_passed=True,
        )
        score_inconsistent = ConfidenceCalibrator.estimate(
            evidence_sources=["lean4_exec"],
            consistency_passed=False,
        )
        assert score_inconsistent.probability < score_consistent.probability

    def test_multiple_sources_higher(self):
        """More evidence sources should increase confidence."""
        score_single = ConfidenceCalibrator.estimate(["python_exec"])
        score_multi = ConfidenceCalibrator.estimate(
            ["python_exec", "web_search", "github"]
        )
        assert score_multi.probability >= score_single.probability

    def test_independent_sources_bonus(self):
        """Independent sources should further boost confidence."""
        score = ConfidenceCalibrator.estimate(
            evidence_sources=["python_exec"],
            independent_sources=3,
        )
        assert score.probability > 0.8

    def test_score_bounds(self):
        """Confidence should be bounded between 0.01 and 0.999."""
        score = ConfidenceCalibrator.estimate([], dimensions=EvidenceDimension.NONE)
        assert 0.01 <= score.probability <= 0.999

    def test_format_score(self):
        """format_score should produce a string with markdown."""
        score = ConfidenceCalibrator.estimate(["lean4_exec"])
        formatted = ConfidenceCalibrator.format_score(score)
        assert "**" in formatted
        assert score.level.name in formatted

    def test_format_short(self):
        """format_short should produce a concise string."""
        score = ConfidenceCalibrator.estimate(["lean4_exec"])
        short = ConfidenceCalibrator.format_short(score)
        assert "@" in short
        assert score.level.name in short

    def test_combine(self):
        """combine should merge multiple scores."""
        s1 = ConfidenceCalibrator.estimate(["lean4_exec"])
        s2 = ConfidenceCalibrator.estimate(["internal_knowledge"])
        combined = ConfidenceCalibrator.combine([s1, s2])
        assert combined.probability > 0.5
        assert combined.evidence_count >= 0

    def test_combine_empty(self):
        """combine with empty list should return SPECULATIVE."""
        combined = ConfidenceCalibrator.combine([])
        assert combined.level == ConfidenceLevel.SPECULATIVE

    def test_confidence_level_ordered(self):
        """ConfidenceLevel should be properly ordered as IntEnum."""
        assert ConfidenceLevel.SPECULATIVE < ConfidenceLevel.WEAK
        assert ConfidenceLevel.WEAK < ConfidenceLevel.MODERATE
        assert ConfidenceLevel.MODERATE < ConfidenceLevel.GOOD
        assert ConfidenceLevel.GOOD < ConfidenceLevel.STRONG
        assert ConfidenceLevel.STRONG < ConfidenceLevel.CERTIFIED

    def test_source_reliability_coverage(self):
        """Common sources should have reliability weights."""
        for src in ["lean4_exec", "prolog_exec", "python_exec",
                     "web_search", "internal_knowledge"]:
            assert src in SOURCE_RELIABILITY, f"{src} missing"

    def test_dimension_priors(self):
        """FORMAL should have the highest prior."""
        assert DIMENSION_PRIORS[EvidenceDimension.FORMAL] >= 0.95
