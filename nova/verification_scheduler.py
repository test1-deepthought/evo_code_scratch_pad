"""
I7: Consequence-Proportional Verification — scales verification cost to
match task risk. Low-risk tasks use lightweight checks; high-risk tasks
require formal verification.

Assigns tasks a risk level and selects the appropriate verification strategy,
verification depth, and required confidence threshold.
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
