"""
Tests for NOVA's verification scheduler module.
"""
import pytest
from nova.verification_scheduler import (
    RiskLevel, VerificationPlan, assess_risk, create_verification_plan,
    execute_plan, verify_evidence_profile,
)
from nova.evidence_dimensions import EvidenceDimension


class TestVerificationScheduler:
    """Test the consequence-proportional verification scheduler."""

    def test_risk_assessment_trivial(self):
        """Short descriptions are trivial risk."""
        risk = assess_risk("Hi", EvidenceDimension.NONE)
        assert risk == RiskLevel.TRIVIAL

    def test_risk_assessment_low(self):
        """Source-only tasks are low risk."""
        risk = assess_risk("What is the capital of France?",
                           EvidenceDimension.SOURCE)
        assert risk == RiskLevel.LOW

    def test_risk_assessment_medium_derivation(self):
        """Derivation tasks are medium risk."""
        risk = assess_risk("Prove that 2 + 2 = 4",
                           EvidenceDimension.DERIVATION)
        assert risk == RiskLevel.MEDIUM

    def test_risk_assessment_high_formal(self):
        """Formal proof tasks are high risk."""
        risk = assess_risk("Formally verify a theorem",
                           EvidenceDimension.FORMAL)
        assert risk == RiskLevel.HIGH

    def test_risk_assessment_critical_security(self):
        """Security-related tasks are critical risk."""
        risk = assess_risk("Analyze this password hashing function",
                           EvidenceDimension.STRUCTURAL)
        assert risk == RiskLevel.CRITICAL

    def test_create_plan_trivial(self):
        """Trivial plan should have skip-level verification."""
        plan = create_verification_plan("Hi", EvidenceDimension.NONE)
        assert plan.required_confidence == 0.60
        assert plan.verification_depth == 0

    def test_create_plan_high(self):
        """High risk plan should require Lean."""
        plan = create_verification_plan(
            "Prove a theorem in Lean",
            EvidenceDimension.FORMAL,
            override_risk=RiskLevel.HIGH,
        )
        assert plan.requires_lean
        assert plan.required_confidence >= 0.90

    def test_create_plan_critical(self):
        """Critical plan should require human review."""
        plan = create_verification_plan(
            "Check this security vulnerability",
            EvidenceDimension.STRUCTURAL,
            override_risk=RiskLevel.CRITICAL,
        )
        assert plan.requires_human_review
        assert plan.required_confidence >= 0.99

    def test_create_plan_override(self):
        """Override risk should take precedence over assessment."""
        plan = create_verification_plan(
            "Hi",
            EvidenceDimension.NONE,
            override_risk=RiskLevel.HIGH,
        )
        assert plan.risk == RiskLevel.HIGH

    def test_execute_plan_pass(self):
        """Plan should pass with sufficient evidence."""
        plan = create_verification_plan(
            "Calculate 2+2",
            EvidenceDimension.COMPUTATION,
        )
        result = execute_plan(plan, ["python_exec"])
        # With python_exec, computation dimension is covered
        assert not result["missing_dimensions"]

    def test_execute_plan_missing_dimensions(self):
        """Plan should report missing dimensions."""
        plan = create_verification_plan(
            "Formally prove a theorem",
            EvidenceDimension.FORMAL,
            override_risk=RiskLevel.HIGH,
        )
        result = execute_plan(plan, ["web_search"], lean_verified=False)
        assert len(result["missing_dimensions"]) > 0

    def test_execute_plan_lean_requirement(self):
        """Plan should check Lean requirement."""
        plan = create_verification_plan(
            "Formally prove a theorem",
            EvidenceDimension.FORMAL | EvidenceDimension.DERIVATION,
            override_risk=RiskLevel.HIGH,
        )
        result_no_lean = execute_plan(plan, [], lean_verified=False)
        result_with_lean = execute_plan(plan, [], lean_verified=True)
        assert not result_no_lean["lean_verified"]
        assert result_with_lean["lean_verified"]

    def test_verify_evidence_profile_output(self):
        """Verify output should include risk and depth."""
        plan = create_verification_plan("Hi", EvidenceDimension.NONE)
        report = verify_evidence_profile(plan, ["internal_knowledge"])
        assert "TRIVIAL" in report
        assert "depth" in report

    def test_verification_plan_to_dict(self):
        """Plan should serialize to dict."""
        plan = create_verification_plan("Test", EvidenceDimension.NONE)
        d = plan.to_dict()
        assert d["risk"] == plan.risk.name
        assert d["required_confidence"] == plan.required_confidence
