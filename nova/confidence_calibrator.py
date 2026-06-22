"""
I6: Bayesian Confidence Calibrator — assigns a posterior probability to each
conclusion based on evidence strength, source reliability, and verification
depth.

Distinguishes "proved with Lean" (p ≈ 1.0) from "found in web search"
(p ≈ 0.7) from "model internal knowledge" (p ≈ 0.5).

EXTENSIVELY FIXED from v0.1.0:
- ConfidenceLevel changed from Flag to IntEnum for proper ordered comparison
- Added format_score() static method (was missing)
- Added format_short() for concise display
- Added combine() for merging multiple confidence estimates
- All graceful_degradation comparisons now work correctly
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Optional

from nova.evidence_dimensions import EvidenceDimension


class ConfidenceLevel(IntEnum):
    """Interpretable confidence levels — IntEnum so .value comparisons work."""
    SPECULATIVE = auto()  # p < 0.50  — Hedged, uncertain, or inferred
    WEAK = auto()         # p >= 0.50 — Internal knowledge, no tool verification
    MODERATE = auto()     # p >= 0.65 — Single evidence source, reasonable
    GOOD = auto()         # p >= 0.80 — Single strong evidence source
    STRONG = auto()       # p >= 0.90 — Multiple independent evidence sources
    CERTIFIED = auto()    # p >= 0.99 — Lean verified or exhaustive proof


@dataclass
class ConfidenceScore:
    """A calibrated confidence score with provenance."""
    probability: float           # 0.0 to 1.0
    level: ConfidenceLevel
    evidence_count: int = 0
    dimensions: EvidenceDimension = EvidenceDimension.NONE
    explanation: str = ""

    def __str__(self) -> str:
        return f"{self.level.name} (p={self.probability:.3f}, {self.evidence_count} sources)"


# Base prior probabilities for each evidence dimension
DIMENSION_PRIORS = {
    EvidenceDimension.FORMAL: 0.99,
    EvidenceDimension.DERIVATION: 0.90,
    EvidenceDimension.TESTED: 0.85,
    EvidenceDimension.STRUCTURAL: 0.80,
    EvidenceDimension.COMPUTATION: 0.85,
    EvidenceDimension.SOURCE: 0.70,
    EvidenceDimension.EMPIRICAL: 0.75,
    EvidenceDimension.SIMULATION: 0.70,
    EvidenceDimension.EXPLANATION: 0.50,
}

# Source reliability weights
SOURCE_RELIABILITY = {
    "lean4_exec": 0.99,
    "prove_problem": 0.99,
    "lean4_builder": 0.97,
    "prolog_exec": 0.90,
    "python_exec": 0.85,
    "sympy_exec": 0.88,
    "web_search": 0.65,
    "web_browse": 0.60,
    "github": 0.80,
    "git": 0.80,
    "internal_knowledge": 0.50,
    "deepseek_prover": 0.80,
    "bfs_prover": 0.75,
    "code_scratch_pad": 0.85,
    "matplotlib_exec": 0.75,
    "networkx_exec": 0.75,
    "mathlib_check": 0.99,
    "mathlib_search": 0.70,
    "maths_problem": 0.90,
}


class ConfidenceCalibrator:
    """Bayesian confidence calibrator.

    Given a set of evidence sources and their dimensions, computes a posterior
    probability that the conclusion is correct using a simple Bayesian update.
    """

    @staticmethod
    def estimate(evidence_sources: list[str],
                 dimensions: EvidenceDimension = EvidenceDimension.NONE,
                 consistency_passed: bool = True,
                 independent_sources: int = 1) -> ConfidenceScore:
        """
        Estimate confidence from evidence sources and dimensions.

        Uses a noisy-OR approximation: each independent evidence source
        increases the probability that the conclusion is correct.
        """
        # Start with a neutral prior (no information)
        prior = 0.5

        # Apply dimension prior (stronger for formal, derivation, etc.)
        for dim in EvidenceDimension:
            if dim in dimensions and dim in DIMENSION_PRIORS:
                prior = max(prior, DIMENSION_PRIORS[dim] * 0.5 + 0.25)

        # Bayesian update for each evidence source
        posterior = prior
        for source in evidence_sources:
            reliability = SOURCE_RELIABILITY.get(source, 0.5)
            # Likelihood ratio: how much more likely the conclusion is
            # correct given this evidence source
            lr = reliability / (1.0 - reliability + 1e-10)
            odds = posterior / (1.0 - posterior + 1e-10)
            odds *= lr
            posterior = odds / (odds + 1.0)

        # Multiple independent sources increase confidence multiplicatively
        if independent_sources > 1:
            for _ in range(independent_sources - 1):
                odds = posterior / (1.0 - posterior + 1e-10)
                odds *= 1.5  # Each independent source adds evidence
                posterior = odds / (odds + 1.0)

        # Consistency penalty
        if not consistency_passed:
            posterior *= 0.5

        posterior = max(0.01, min(0.999, posterior))

        # Map to level
        if posterior >= 0.99:
            level = ConfidenceLevel.CERTIFIED
        elif posterior >= 0.90:
            level = ConfidenceLevel.STRONG
        elif posterior >= 0.80:
            level = ConfidenceLevel.GOOD
        elif posterior >= 0.65:
            level = ConfidenceLevel.MODERATE
        elif posterior >= 0.50:
            level = ConfidenceLevel.WEAK
        else:
            level = ConfidenceLevel.SPECULATIVE

        return ConfidenceScore(
            probability=round(posterior, 4),
            level=level,
            evidence_count=len(evidence_sources),
            dimensions=dimensions,
            explanation=(
                f"Posterior p={posterior:.3f} from {len(evidence_sources)} sources "
                f"({', '.join(evidence_sources[:3])}) "
                f"over {dimensions.name}"
            ),
        )

    @staticmethod
    def combine(scores: list[ConfidenceScore]) -> ConfidenceScore:
        """Combine multiple confidence scores into one aggregate score."""
        if not scores:
            return ConfidenceScore(0.5, ConfidenceLevel.SPECULATIVE, 0,
                                   EvidenceDimension.NONE, "No scores to combine")

        # Average probabilities weighted by evidence count
        total_weight = sum(s.evidence_count + 1 for s in scores)
        avg_prob = sum(s.probability * (s.evidence_count + 1) for s in scores) / total_weight

        # Combine dimensions
        combined_dim = EvidenceDimension.NONE
        for s in scores:
            combined_dim |= s.dimensions

        # Combined evidence count
        total_evidence = sum(s.evidence_count for s in scores)

        # Determine level from averaged probability
        if avg_prob >= 0.99:
            level = ConfidenceLevel.CERTIFIED
        elif avg_prob >= 0.90:
            level = ConfidenceLevel.STRONG
        elif avg_prob >= 0.80:
            level = ConfidenceLevel.GOOD
        elif avg_prob >= 0.65:
            level = ConfidenceLevel.MODERATE
        elif avg_prob >= 0.50:
            level = ConfidenceLevel.WEAK
        else:
            level = ConfidenceLevel.SPECULATIVE

        return ConfidenceScore(
            probability=round(avg_prob, 4),
            level=level,
            evidence_count=total_evidence,
            dimensions=combined_dim,
            explanation=f"Combined from {len(scores)} scores (avg p={avg_prob:.3f})",
        )

    @staticmethod
    def format_score(score: ConfidenceScore) -> str:
        """Format a confidence score for display (rich format)."""
        icon = {
            ConfidenceLevel.CERTIFIED: "\u2714\ufe0f",
            ConfidenceLevel.STRONG: "\u2705",
            ConfidenceLevel.GOOD: "\u2139\ufe0f",
            ConfidenceLevel.MODERATE: "\ud83d\udca1",
            ConfidenceLevel.WEAK: "\u2753",
            ConfidenceLevel.SPECULATIVE: "\u26a0\ufe0f",
        }.get(score.level, "\u2753")
        return f"{icon} **{score.level.name}** (p={score.probability:.3f})"

    @staticmethod
    def format_short(score: ConfidenceScore) -> str:
        """Format a confidence score concisely."""
        return f"{score.level.name}@{score.probability:.2f}"
