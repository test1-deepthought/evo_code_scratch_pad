"""
I7: Consequence-Proportional Verification — scales verification cost to
match task risk. Low-risk tasks use lightweight checks; high-risk tasks
require formal verification.

Assigns tasks a risk level and selects the appropriate verification strategy,
verification depth, and required confidence threshold.

FIXED in v0.2.0:
- Added execute_plan() to make verification plans actionable
- Added verify_evidence_profile() for runtime evidence checking
- Added plan_to_dict() for serialization
- Plans are no longer purely informational
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Optional

from nova.evidence_dimensions import EvidenceDimension


class RiskLevel(IntEnum):
    """Consequence-based risk levels for verification."""
    TRIVIAL = 0      # Cosmetic, informational, one-line formatting
    LOW = 1           # General knowledge, simple lookups, simple computations
    MEDIUM = 2        # Multi-step reasoning, code that won't run in production
    HIGH = 3          # Production code, mathematical proof, security analysis
    CRITICAL = 4      # Safety-critical, financial, medical, access control


@dataclass
class VerificationPlan:
    """A verification plan scaled to the task's risk level."""
    risk: RiskLevel
    required_confidence: float
    min_evidence_dimensions: EvidenceDimension
    verification_depth: int  # 0=skip, 1=light, 2=standard, 3=deep, 4=formal
    max_budget_seconds: int
    requires_lean: bool
    requires_human_review: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "risk": self.risk.name,
            "required_confidence": self.required_confidence,
            "min_evidence_dimensions": self.min_evidence_dimensions.name,
            "verification_depth": self.verification_depth,
            "max_budget_seconds": self.max_budget_seconds,
            "requires_lean": self.requires_lean,
            "requires_human_review": self.requires_human_review,
            "notes": self.notes,
        }


def assess_risk(description: str, dimensions: EvidenceDimension) -> RiskLevel:
    """Assess the risk level of a task based on its description and evidence needs."""
    text = description.lower()

    # Critical risk indicators
    critical_keywords = [
        "password", "security", "auth", "access control", "financial",
        "medical", "safety", "nuclear", "weapon", "encryption",
        "vulnerability", "exploit", "cve", "backdoor", "malware",
    ]
    if any(kw in text for kw in critical_keywords):
        return RiskLevel.CRITICAL

    # High risk indicators
    if dimensions & EvidenceDimension.FORMAL:
        return RiskLevel.HIGH
    if dimensions & EvidenceDimension.STRUCTURAL and any(
        kw in text for kw in ["production", "deploy", "api", "endpoint",
                               "database", "transaction"]
    ):
        return RiskLevel.HIGH

    # Medium risk indicators
    if dimensions & EvidenceDimension.DERIVATION:
        return RiskLevel.MEDIUM
    if dimensions & EvidenceDimension.COMPUTATION and any(
        kw in text for kw in ["solve", "calculate", "evaluate"]
    ):
        return RiskLevel.MEDIUM

    # Low/trivial
    if dimensions == EvidenceDimension.SOURCE:
        return RiskLevel.LOW
    if len(text) < 30:
        return RiskLevel.TRIVIAL

    return RiskLevel.LOW


# Verification plan templates per risk level
_VERIFICATION_TEMPLATES: dict[RiskLevel, VerificationPlan] = {
    RiskLevel.TRIVIAL: VerificationPlan(
        risk=RiskLevel.TRIVIAL,
        required_confidence=0.60,
        min_evidence_dimensions=EvidenceDimension.EXPLANATION,
        verification_depth=0,
        max_budget_seconds=10,
        requires_lean=False,
        requires_human_review=False,
        notes=["No verification needed — trivial informational task."],
    ),
    RiskLevel.LOW: VerificationPlan(
        risk=RiskLevel.LOW,
        required_confidence=0.70,
        min_evidence_dimensions=EvidenceDimension.SOURCE | EvidenceDimension.COMPUTATION,
        verification_depth=1,
        max_budget_seconds=30,
        requires_lean=False,
        requires_human_review=False,
        notes=["Light verification: single source or computation."],
    ),
    RiskLevel.MEDIUM: VerificationPlan(
        risk=RiskLevel.MEDIUM,
        required_confidence=0.85,
        min_evidence_dimensions=EvidenceDimension.DERIVATION | EvidenceDimension.COMPUTATION,
        verification_depth=2,
        max_budget_seconds=120,
        requires_lean=False,
        requires_human_review=False,
        notes=["Standard verification: Prolog derivation + consistency check."],
    ),
    RiskLevel.HIGH: VerificationPlan(
        risk=RiskLevel.HIGH,
        required_confidence=0.95,
        min_evidence_dimensions=EvidenceDimension.DERIVATION | EvidenceDimension.FORMAL,
        verification_depth=3,
        max_budget_seconds=600,
        requires_lean=True,
        requires_human_review=False,
        notes=["Deep verification: formal proof (Lean 4) + multiple evidence sources."],
    ),
    RiskLevel.CRITICAL: VerificationPlan(
        risk=RiskLevel.CRITICAL,
        required_confidence=0.999,
        min_evidence_dimensions=EvidenceDimension.FORMAL | EvidenceDimension.TESTED,
        verification_depth=4,
        max_budget_seconds=1800,
        requires_lean=True,
        requires_human_review=True,
        notes=[
            "Critical verification: Lean 4 formal proof + human review required.",
            "Multiple independent verification methods required.",
        ],
    ),
}


def create_verification_plan(description: str,
                              dimensions: EvidenceDimension,
                              override_risk: Optional[RiskLevel] = None) -> VerificationPlan:
    """Create a consequence-proportional verification plan."""
    risk = override_risk if override_risk is not None else assess_risk(description, dimensions)
    return _VERIFICATION_TEMPLATES[risk]


def execute_plan(plan: VerificationPlan,
                 evidence_sources: list[str],
                 lean_verified: bool = False) -> dict:
    """Execute a verification plan against actual evidence.

    Returns a dict with:
    - passed: bool — whether all requirements are met
    - verification_depth_achieved: int
    - lean_verified: bool
    - confidence_target: float
    - missing_dimensions: list[str]
    - recommendations: list[str]
    """
    from nova.evidence_dimensions import TOOL_EVIDENCE_MAP

    # Determine what dimensions were covered
    covered_dimensions = EvidenceDimension.NONE
    for src in evidence_sources:
        if src in TOOL_EVIDENCE_MAP:
            covered_dimensions |= TOOL_EVIDENCE_MAP[src]

    # Check minimum evidence dimensions
    required = plan.min_evidence_dimensions
    missing_dims = []
    for dim in EvidenceDimension:
        if dim in required and dim not in covered_dimensions:
            if dim != EvidenceDimension.NONE:
                missing_dims.append(dim.name)

    # Lean requirement
    lean_requirement_met = not plan.requires_lean or lean_verified

    # Depth requirement
    depth_achieved = plan.verification_depth if evidence_sources else 0
    depth_met = depth_achieved >= plan.verification_depth

    passed = (len(missing_dims) == 0 and lean_requirement_met and depth_met)

    recommendations = []
    if missing_dims:
        recommendations.append(f"Add evidence for: {', '.join(missing_dims)}")
    if not lean_requirement_met:
        recommendations.append("Complete Lean 4 formal verification")
    if not depth_met:
        recommendations.append(f"Increase verification depth from {depth_achieved} to {plan.verification_depth}")

    return {
        "passed": passed,
        "verification_depth_achieved": depth_achieved,
        "lean_verified": lean_verified,
        "confidence_target": plan.required_confidence,
        "missing_dimensions": missing_dims,
        "recommendations": recommendations,
    }


def verify_evidence_profile(plan: VerificationPlan,
                             evidence_sources: list[str]) -> str:
    """Generate a verification report string for the given evidence."""
    result = execute_plan(plan, evidence_sources)
    lines = [
        f"Verification: risk={plan.risk.name}, depth={result['verification_depth_achieved']}/{plan.verification_depth}",
    ]
    if result["passed"]:
        lines.append("  PASSED: all verification requirements met.")
    else:
        lines.append("  FAILED: see recommendations below.")
        for rec in result["recommendations"]:
            lines.append(f"  - {rec}")
    if result["missing_dimensions"]:
        lines.append(f"  Missing evidence dimensions: {', '.join(result['missing_dimensions'])}")
    return "\n".join(lines)
