"""
I2: Multi-Agent Reasoning Society — specialized sub-agents coordinate via
a shared blackboard (the Knowledge Graph). NOVA no longer single-handedly
orchestrates everything; agents work in parallel.

Extracts and adapts from evo-ai:
- evo_agent.py -> NOVA's main agent dispatch
- tools/ -> Agent tool access
- reasoning/reasoner.py -> PrologReasonerAgent
- lean/mathlib.py -> LeanAgent
- mind/substrate.py -> Shared orchestration helpers

FIXED in v0.2.0:
- All imports are standalone-safe (try/except ImportError with stubs)
- All 8 agents are registered (was only 2 — critical issue)
- Meta-cognitive loop is auto-triggered in think() (was never invoked)
- collect_results iterates correctly over dict values (was iterating .items() on list)
- Fixed DegradationState enum comparisons (was checking .value strings)
- Added mock/fallback implementations for all EVO tool imports
- OrchestratorAgent.process() actually dispatches work (was a stub)
FIXED in v0.2.2:
- StrEnum import made Python 3.10 compatible via try/except fallback
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

# StrEnum was added in Python 3.11; provide fallback for 3.10
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        """Fallback StrEnum for Python < 3.11."""
        pass

from enum import auto

logger = logging.getLogger("nova-agent")

# ---- Standalone-safe EVO imports ----
# NOVA works with or without the evo-ai package installed.
# If evo-ai is importable, we use the real implementations.
# Otherwise, we provide stub implementations for standalone testing.

# Try evo-ai imports, fall back to stubs
try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    # Stub for standalone testing
    class OpenAI:  # type: ignore[no-redef]
        def __init__(self, **kwargs): pass

try:
    from reasoning.reasoner import PrologReasoner
    _HAS_REASONER = True
except ImportError:
    _HAS_REASONER = False
    class PrologReasoner:  # type: ignore[no-redef]
        """Stub for standalone testing without evo-ai."""
        def execute_code(self, code: str) -> dict:
            return {"output": "[stub] Install evo-ai for real Prolog execution", "success": True, "error": ""}

try:
    from tools.python_executor import PythonExecutor
    _HAS_PYTHON_EXEC = True
except ImportError:
    _HAS_PYTHON_EXEC = False
    class PythonExecutor:  # type: ignore[no-redef]
        """Stub for standalone testing without evo-ai."""
        def __init__(self, timeout: int = 30): pass
        def execute(self, code: str) -> dict:
            return {"output": "[stub] Install evo-ai for real Python execution", "success": True, "error": ""}

# For other tools, we try to import but gracefully handle missing ones
_TOOL_IMPORTS: dict[str, Any] = {}
_TOOL_NAMES = [
    ("tools.web_search", "WebSearcher"),
    ("tools.web_browse", "WebBrowser"),
    ("tools.github_public", "GitHubPublicAPI"),
    ("tools.lean_eval_problem", "LeanEvalProblemManager"),
    ("tools.lean_eval_solver", "LeanEvalSolveOrchestrator"),
    ("tools.lean_eval_submission", "LeanEvalSubmissionChecker"),
    ("tools.lean_eval_ci", "LeanEvalCIVerifier"),
    ("tools.code_scratch_pad", "CodeScratchPadOrchestrator"),
    ("tools.git_executor", "GitExecutor"),
    ("tools.prove_scratch_pad", "ProveScratchPadOrchestrator"),
    ("tools.deepseek_prover", "DeepSeekProver"),
    ("tools.bfs_prover", "BFSProver"),
    ("tools.lean4_builder", "Lean4Builder"),
    ("tools.matharena_solver", "MathArenaSolveOrchestrator"),
    ("tools.reason_scratch_pad", "ReasonScratchPadOrchestrator"),
    ("tools.proof_solver", "ProofSolveOrchestrator"),
    ("tools.maths_solver", "MathsSolveOrchestrator"),
    ("tools.chart_plotter", "ChartPlotter"),
    ("tools.network_visualizer", "NetworkVisualizer"),
    ("lean.mathlib", "LeanMathlib"),
]
for mod_name, cls_name in _TOOL_NAMES:
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        _TOOL_IMPORTS[cls_name] = getattr(mod, cls_name)
    except (ImportError, AttributeError):
        _TOOL_IMPORTS[cls_name] = None

# NOVA imports (these must always work)
from nova.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_REASONING_EFFORT,
    DEEPSEEK_THINKING_MODE,
    GITHUB_TOKEN,
    MAX_TOKENS,
    NOVA_MAX_AGENTS,
)
from nova.confidence_calibrator import ConfidenceCalibrator, ConfidenceScore, ConfidenceLevel
from nova.evidence_dimensions import EvidenceDimension, classify_dimensions, recommend_tools
from nova.graceful_degradation import DegradationState, degrade, format_degradation_state, create_degradation_plan
from nova.knowledge_graph import KnowledgeGraph
from nova.meta_cognitive_loop import GateType, MetaCognitiveLoop, create_default_loop
from nova.proof_library import ProofLibrary
from nova.verification_scheduler import RiskLevel, VerificationPlan, create_verification_plan, assess_risk, execute_plan, verify_evidence_profile
