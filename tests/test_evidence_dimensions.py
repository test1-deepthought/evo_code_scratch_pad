"""
Tests for NOVA's evidence dimensions module.
"""
import pytest
from nova.evidence_dimensions import (
    EvidenceDimension, classify_dimensions, recommend_tools,
    EvidenceProfile, TOOL_EVIDENCE_MAP, LEGACY_TIER_MAP
)
from nova.verification_scheduler import assess_risk, RiskLevel


class TestEvidenceDimensions:
    """Test the composable evidence dimension system."""

    def test_dimension_composition(self):
        """Dimensions should compose via bitwise OR."""
        combined = EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION
        assert combined & EvidenceDimension.COMPUTATION
        assert combined & EvidenceDimension.DERIVATION
        assert not (combined & EvidenceDimension.FORMAL)

    def test_dimension_none(self):
        """NONE should be the zero value."""
        assert EvidenceDimension.NONE == 0
        assert not (EvidenceDimension.NONE & EvidenceDimension.COMPUTATION)

    def test_classify_computation(self):
        """Computation keywords should be detected."""
        dims = classify_dimensions("Calculate the integral of x^2 from 0 to 1")
        assert EvidenceDimension.COMPUTATION in dims

    def test_classify_derivation(self):
        """Derivation keywords should be detected."""
        dims = classify_dimensions("Prove that the sum of first n numbers is n(n+1)/2")
        assert EvidenceDimension.DERIVATION in dims

    def test_classify_source(self):
        """Source keywords should be detected."""
        dims = classify_dimensions("What is the capital of France? Look it up")
        assert EvidenceDimension.SOURCE in dims

    def test_classify_formal(self):
        """Formal proof keywords should be detected."""
        dims = classify_dimensions("Formally verify that 2 + 2 = 4 in Lean")
        assert EvidenceDimension.FORMAL in dims

    def test_classify_code(self):
        """Code inspection keywords should be detected."""
        dims = classify_dimensions("Review this Python code for bugs")
        assert EvidenceDimension.STRUCTURAL in dims

    def test_recommend_computation(self):
        """python_exec should be recommended for computation tasks."""
        tools = recommend_tools(EvidenceDimension.COMPUTATION)
        assert "python_exec" in tools

    def test_recommend_formal(self):
        """lean4_exec should be recommended for formal tasks."""
        tools = recommend_tools(EvidenceDimension.FORMAL)
        assert "lean4_exec" in tools

    def test_recommend_source(self):
        """web_search should be recommended for source tasks."""
        tools = recommend_tools(EvidenceDimension.SOURCE)
        assert "web_search" in tools

    def test_legacy_tier_mapping(self):
        """EVO legacy tiers should map to correct dimension sets."""
        assert LEGACY_TIER_MAP["COMPUTE"] == EvidenceDimension.COMPUTATION
        assert EvidenceDimension.DERIVATION in LEGACY_TIER_MAP["MATHS"]
        assert EvidenceDimension.FORMAL in LEGACY_TIER_MAP["PROVE"]

    def test_evidence_profile_requires(self):
        """EvidenceProfile.requires should check dimension membership."""
        prof = EvidenceProfile(
            dimensions=EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION
        )
        assert prof.requires(EvidenceDimension.COMPUTATION)
        assert prof.requires(EvidenceDimension.DERIVATION)
        assert not prof.requires(EvidenceDimension.FORMAL)

    def test_evidence_profile_meets(self):
        """EvidenceProfile.meets should check all required dimensions."""
        required = EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION
        prof = EvidenceProfile(dimensions=required)
        assert prof.meets(EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION)
        assert prof.meets(EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION | EvidenceDimension.FORMAL)
        assert not prof.meets(EvidenceDimension.COMPUTATION)

    def test_risk_assessment_trivial(self):
        """Short descriptions should get trivial risk."""
        risk = assess_risk("Hi", EvidenceDimension.NONE)
        assert risk == RiskLevel.TRIVIAL

    def test_risk_assessment_high_formal(self):
        """Formal evidence should get high risk."""
        risk = assess_risk("Prove a theorem", EvidenceDimension.FORMAL)
        assert risk == RiskLevel.HIGH

    def test_risk_assessment_critical(self):
        """Security keywords should get critical risk."""
        risk = assess_risk("Check this password storage", EvidenceDimension.STRUCTURAL)
        assert risk == RiskLevel.CRITICAL

    def test_tool_evidence_map(self):
        """Every NOVA tool should be in the evidence map."""
        known_tools = [
            "prolog_exec", "python_exec", "lean4_exec", "web_search",
            "web_browse", "github", "git", "sympy_exec",
        ]
        for tool in known_tools:
            assert tool in TOOL_EVIDENCE_MAP, f"{tool} not in TOOL_EVIDENCE_MAP"
