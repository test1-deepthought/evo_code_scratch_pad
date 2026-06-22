"""
I3: Composable Evidence Dimensions — replaces EVO's six rigid tiers with
composable evidence tags that can be mixed freely.

Tasks declare their evidence requirements using a set of tags rather than
picking a single tier. Tags compose naturally: a task can require
[computation, derivation, source] without being forced into a single category.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Optional


class EvidenceDimension(Flag):
    """Composable evidence requirement dimensions.
    
    Unlike EVO's six mutually exclusive tiers, NOVA dimensions can be
    combined freely. A task can require COMPUTATION | DERIVATION | SOURCE.
    """
    NONE = 0
    COMPUTATION = auto()       # Numeric/symbolic computation result
    DERIVATION = auto()        # Deductive derivation with proof trace
    SOURCE = auto()            # External source (web, repository, document)
    FORMAL = auto()            # Machine-checked formal proof
    TESTED = auto()            # Unit/integration test evidence
    EXPERT = auto()            # Expert knowledge or authoritative reference
    EMPIRICAL = auto()         # Empirical/statistical evidence
    STRUCTURAL = auto()        # Code structure, dependency graph, type system
    SIMULATION = auto()        # Simulation, sampling, or Monte Carlo
    EXPLANATION = auto()       # Explanatory narrative (for expository tasks)


# Legacy tier mapping: EVO tiers map to NOVA dimension sets
LEGACY_TIER_MAP = {
    "LITE": EvidenceDimension.SOURCE | EvidenceDimension.COMPUTATION,
    "COMPUTE": EvidenceDimension.COMPUTATION,
    "MATHS": EvidenceDimension.DERIVATION,
    "CODE": EvidenceDimension.STRUCTURAL | EvidenceDimension.SOURCE | EvidenceDimension.TESTED,
    "REASON": EvidenceDimension.DERIVATION | EvidenceDimension.SOURCE,
    "PROVE": EvidenceDimension.FORMAL | EvidenceDimension.DERIVATION,
}


@dataclass
class EvidenceRequirement:
    """A single evidence requirement for a task."""
    dimension: EvidenceDimension
    description: str
    min_confidence: float = 0.7
    required: bool = True


@dataclass
class EvidenceProfile:
    """The full evidence profile for a task."""
    dimensions: EvidenceDimension
    requirements: list[EvidenceRequirement] = field(default_factory=list)
    primary_tool: str = ""
    fallback_tools: list[str] = field(default_factory=list)
    
    def requires(self, dim: EvidenceDimension) -> bool:
        return bool(self.dimensions & dim)
    
    def meets(self, provided: EvidenceDimension) -> bool:
        """Check if provided evidence satisfies ALL required dimensions."""
        return (self.dimensions & provided) == self.dimensions


# -- Tool-to-dimension mapping --
# Maps each tool to the evidence dimensions it can provide.

TOOL_EVIDENCE_MAP: dict[str, EvidenceDimension] = {
    "prolog_exec": EvidenceDimension.DERIVATION,
    "python_exec": EvidenceDimension.COMPUTATION,
    "sympy_exec": EvidenceDimension.COMPUTATION | EvidenceDimension.DERIVATION,
    "lean4_exec": EvidenceDimension.FORMAL,
    "lean4_probe": EvidenceDimension.FORMAL,
    "prove_problem": EvidenceDimension.FORMAL,
    "maths_problem": EvidenceDimension.DERIVATION,
    "mathlib_check": EvidenceDimension.FORMAL,
    "mathlib_search": EvidenceDimension.FORMAL,
    "web_search": EvidenceDimension.SOURCE,
    "web_browse": EvidenceDimension.SOURCE,
    "github": EvidenceDimension.SOURCE | EvidenceDimension.STRUCTURAL,
    "git": EvidenceDimension.SOURCE | EvidenceDimension.STRUCTURAL,
    "code_scratch_pad": EvidenceDimension.TESTED,
    "matplotlib_exec": EvidenceDimension.COMPUTATION | EvidenceDimension.EMPIRICAL,
    "networkx_exec": EvidenceDimension.STRUCTURAL | EvidenceDimension.COMPUTATION,
    "deepseek_prover": EvidenceDimension.FORMAL | EvidenceDimension.DERIVATION,
    "bfs_prover": EvidenceDimension.FORMAL,
    "lean4_builder": EvidenceDimension.FORMAL,
    "internal_knowledge": EvidenceDimension.EXPLANATION,
}


def classify_dimensions(description: str) -> EvidenceDimension:
    """Classify a task description into evidence dimensions.
    
    Uses keyword matching (lighter than EVO's tier0 LLM triage) to
    propose an initial evidence profile.
    """
    text = description.lower()
    dims = EvidenceDimension.NONE
    
    # Computation keywords
    if any(kw in text for kw in ["calculate", "compute", "evaluate", "solve",
                                  "integral", "derivative", "sum", "product",
                                  "numerical", "numeric"]):
        dims |= EvidenceDimension.COMPUTATION
    
    # Derivation keywords
    if any(kw in text for kw in ["prove", "proof", "theorem", "lemma",
                                  "derive", "deduce", "reason", "logic",
                                  "infer", "syllogism"]):
        dims |= EvidenceDimension.DERIVATION
    
    # Source keywords
    if any(kw in text for kw in ["search", "find", "look up", "research",
                                  "browse", "web", "documentation"]):
        dims |= EvidenceDimension.SOURCE
    
    # Formal keywords
    if any(kw in text for kw in ["lean", "mathlib", "formal", "machine-checked",
                                  "theorem prover", "lean-eval", "lean_eval"]):
        dims |= EvidenceDimension.FORMAL
    
    # Code/structural keywords
    if any(kw in text for kw in ["code", "program", "implement", "function",
                                  "algorithm", "script", "repository",
                                  "github", "dependency", "api"]):
        dims |= EvidenceDimension.STRUCTURAL | EvidenceDimension.TESTED
    
    # Empirical keywords
    if any(kw in text for kw in ["statistics", "data", "analysis", "dataset",
                                  "regression", "correlation", "simulation",
                                  "sample", "monte carlo"]):
        dims |= EvidenceDimension.COMPUTATION | EvidenceDimension.EMPIRICAL
    
    # Default: if nothing matched, use derivation (like EVO's REASON default)
    if dims == EvidenceDimension.NONE:
        dims = EvidenceDimension.DERIVATION | EvidenceDimension.SOURCE
    
    return dims


def recommend_tools(dimensions: EvidenceDimension) -> list[str]:
    """Recommend tools that can satisfy the requested evidence dimensions."""
    scored: list[tuple[int, str]] = []
    for tool, tool_dims in TOOL_EVIDENCE_MAP.items():
        overlap = bin(int(dimensions & tool_dims)).count("1")
        if overlap > 0:
            scored.append((overlap, tool))
    scored.sort(key=lambda x: -x[0])
    return [tool for _, tool in scored]
