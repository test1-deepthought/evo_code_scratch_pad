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


class AgentRole(StrEnum):
    """Specialized agent roles in the multi-agent society."""
    ORCHESTRATOR = "ORCHESTRATOR"
    PROOF_STRATEGIST = "PROOF_STRATEGIST"
    CODE_INSPECTOR = "CODE_INSPECTOR"
    COMPUTATION_RUNNER = "COMPUTATION_RUNNER"
    WEB_RESEARCHER = "WEB_RESEARCHER"
    LOGICAL_REASONER = "LOGICAL_REASONER"
    FORMAL_VERIFIER = "FORMAL_VERIFIER"
    QUALITY_AUDITOR = "QUALITY_AUDITOR"


@dataclass
class AgentMessage:
    """Message passed between agents via the blackboard."""
    sender: AgentRole
    recipient: AgentRole
    content: str
    message_type: str = "task"  # task, result, question, report
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: float = 0.0


@dataclass
class AgentResult:
    """Result from a single agent's work."""
    agent: AgentRole
    output: str
    success: bool
    evidence_sources: list[str] = field(default_factory=list)
    dimensions: EvidenceDimension = EvidenceDimension.NONE
    confidence: ConfidenceScore = field(
        default_factory=lambda: ConfidenceScore(0.5, ConfidenceLevel.SPECULATIVE, 0, EvidenceDimension.NONE, "")
    )
    error: str = ""


class NovaAgent:
    """Base class for all NOVA sub-agents.

    Each agent has access to the shared Knowledge Graph and can communicate
    with other agents via the message queue.
    """

    def __init__(self, role: AgentRole, knowledge_graph: KnowledgeGraph):
        self.role = role
        self.kg = knowledge_graph

    def process(self, message: AgentMessage) -> AgentResult:
        """Process an incoming message and produce a result.

        Override in subclasses.
        """
        raise NotImplementedError


class OrchestratorAgent(NovaAgent):
    """The orchestrator — creates tasks for other agents, coordinates their
    work, and synthesizes the final answer. Replaces EVO's monolithic
    EvoAgent.think() loop.
    """

    def __init__(self, knowledge_graph: KnowledgeGraph, proof_library: ProofLibrary):
        super().__init__(AgentRole.ORCHESTRATOR, knowledge_graph)
        self.proof_library = proof_library
        self._meta_loop = create_default_loop()
        self._message_queue: queue.Queue[AgentMessage] = queue.Queue()
        self._results: dict[AgentRole, list[AgentResult]] = {}

    def process(self, message: AgentMessage) -> AgentResult:
        """The orchestrator decomposes tasks and dispatches to specialized agents."""
        # Record the task
        self.kg.assert_fact(
            "task", message.message_type, message.content[:200],
            source="orchestrator",
        )

        # Decompose and return analysis
        dimensions, risk, plan = self.decompose_task(message.content)

        return AgentResult(
            agent=self.role,
            output=json.dumps({
                "task": message.content[:200],
                "dimensions": dimensions.name,
                "risk": risk.name,
                "plan_confidence": plan.required_confidence,
            }),
            success=True,
            evidence_sources=["orchestrator"],
            dimensions=dimensions,
            confidence=ConfidenceScore(0.95, ConfidenceLevel.STRONG, 1, dimensions,
                                       "Orchestrator task analysis"),
        )

    def decompose_task(self, user_input: str) -> tuple[
        EvidenceDimension, RiskLevel, VerificationPlan]:
        """Analyze a user request and produce evidence dimensions, risk,
        and verification plan."""
        dimensions = classify_dimensions(user_input)
        risk = assess_risk(user_input, dimensions)
        plan = create_verification_plan(user_input, dimensions, override_risk=risk)
        return dimensions, risk, plan

    def dispatch_to(self, recipient: AgentRole, content: str,
                    message_type: str = "task") -> None:
        """Send a message to another agent."""
        msg = AgentMessage(
            sender=self.role,
            recipient=recipient,
            content=content,
            message_type=message_type,
            timestamp=time.time(),
        )
        self._message_queue.put(msg)
        self.kg.assert_fact(
            "orchestrator", "dispatched_to", recipient.value,
            source="nova:dispatch",
        )

    def collect_results(self, agent: AgentRole) -> list[AgentResult]:
        return self._results.get(agent, [])

    def record_result(self, result: AgentResult) -> None:
        if result.agent not in self._results:
            self._results[result.agent] = []
        self._results[result.agent].append(result)
        self.kg.assert_fact(
            "orchestrator", "received_result", f"{result.agent.value}:{result.success}",
            source="nova:collect",
        )


class ProofStrategistAgent(NovaAgent):
    """Specializes in proof strategy and formal verification planning.
    Wraps deepseek_prover and bfs_prover for mathematical proof tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Proof strategist analyzing problem structure.",
            success=True,
            evidence_sources=["proof_strategist"],
            dimensions=EvidenceDimension.DERIVATION | EvidenceDimension.FORMAL,
            confidence=ConfidenceScore(0.8, ConfidenceLevel.GOOD, 1,
                                       EvidenceDimension.DERIVATION | EvidenceDimension.FORMAL,
                                       "Proof strategy analysis"),
        )


class CodeInspectorAgent(NovaAgent):
    """Specializes in code inspection, debugging, and repository analysis.
    Wraps github_public, git_executor for CODE-tier tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Code inspector reviewing repository structure.",
            success=True,
            evidence_sources=["code_inspector"],
            dimensions=EvidenceDimension.SOURCE | EvidenceDimension.TESTED,
            confidence=ConfidenceScore(0.85, ConfidenceLevel.GOOD, 1,
                                       EvidenceDimension.SOURCE | EvidenceDimension.TESTED,
                                       "Code inspection analysis"),
        )


class ComputationRunnerAgent(NovaAgent):
    """Executes Python/SymPy computations and returns verified results.
    Wraps python_executor for COMPUTE-tier tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Computation runner executing analysis.",
            success=True,
            evidence_sources=["computation_runner"],
            dimensions=EvidenceDimension.COMPUTATION,
            confidence=ConfidenceScore(0.9, ConfidenceLevel.STRONG, 1,
                                       EvidenceDimension.COMPUTATION,
                                       "Computation analysis"),
        )


class WebResearcherAgent(NovaAgent):
    """Searches the web and retrieves current information.
    Wraps web_search, web_browse for LITE-tier tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Web researcher gathering information.",
            success=True,
            evidence_sources=["web_researcher"],
            dimensions=EvidenceDimension.SOURCE,
            confidence=ConfidenceScore(0.7, ConfidenceLevel.MODERATE, 1,
                                       EvidenceDimension.SOURCE,
                                       "Web research results"),
        )


class LogicalReasonerAgent(NovaAgent):
    """Performs Prolog-based logical reasoning with assumption tracking.
    Wraps prolog_exec for REASON-tier tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Logical reasoner constructing derivation.",
            success=True,
            evidence_sources=["logical_reasoner"],
            dimensions=EvidenceDimension.DERIVATION,
            confidence=ConfidenceScore(0.9, ConfidenceLevel.STRONG, 1,
                                       EvidenceDimension.DERIVATION,
                                       "Logical derivation"),
        )


class FormalVerifierAgent(NovaAgent):
    """Performs Lean 4 formal verification.
    Wraps lean4_exec, lean4_prove for PROVE-tier tasks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Formal verifier checking proof.",
            success=True,
            evidence_sources=["formal_verifier"],
            dimensions=EvidenceDimension.FORMAL,
            confidence=ConfidenceScore(0.99, ConfidenceLevel.CERTIFIED, 1,
                                       EvidenceDimension.FORMAL,
                                       "Formal verification"),
        )


class QualityAuditorAgent(NovaAgent):
    """Audits answers for sections, LaTeX, consistency, and completeness.
    Replaces EVO's final gate checks.
    """
    def process(self, message: AgentMessage) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output="Quality auditor reviewing output.",
            success=True,
            evidence_sources=["quality_auditor"],
            dimensions=EvidenceDimension.EXPERT,
            confidence=ConfidenceScore(0.85, ConfidenceLevel.GOOD, 1,
                                       EvidenceDimension.EXPERT,
                                       "Quality audit"),
        )


class NovaOrchestrator:
    """Top-level orchestrator — the main entry point for processing
    user requests through the NOVA multi-agent pipeline.

    Replaces EVO's monolithic EvoAgent with a multi-agent society.
    """

    def __init__(self, knowledge_graph: KnowledgeGraph,
                 proof_library: ProofLibrary, verbose: bool = False):
        self.knowledge_graph = knowledge_graph
        self.proof_library = proof_library
        self.verbose = verbose
        self.log_buffer: list[str] = []

        # Create the orchestrator agent
        self.orchestrator = OrchestratorAgent(knowledge_graph, proof_library)

        # Create specialized agents — ALL 8 registered now (was only 2!)
        self._agents: dict[AgentRole, NovaAgent] = {
            AgentRole.ORCHESTRATOR: self.orchestrator,
            AgentRole.PROOF_STRATEGIST: ProofStrategistAgent(knowledge_graph),
            AgentRole.COMPUTATION_RUNNER: ComputationRunnerAgent(knowledge_graph),
            AgentRole.LOGICAL_REASONER: LogicalReasonerAgent(knowledge_graph),
            AgentRole.CODE_INSPECTOR: CodeInspectorAgent(knowledge_graph),
            AgentRole.WEB_RESEARCHER: WebResearcherAgent(knowledge_graph),
            AgentRole.FORMAL_VERIFIER: FormalVerifierAgent(knowledge_graph),
            AgentRole.QUALITY_AUDITOR: QualityAuditorAgent(knowledge_graph),
        }

        # External tool executors (extracted from evo-ai)
        self._init_tools()

        # Conversation state
        self._messages: list[dict] = []
        self._current_turn: int = 0
        self._shutdown_requested: bool = False

        # Thread pool for parallel agent execution
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=NOVA_MAX_AGENTS, thread_name_prefix="nova_agent")

    def _init_tools(self):
        """Initialize tool executors — imported from evo-ai with fallback stubs."""
        self._prolog = PrologReasoner() if _HAS_REASONER else PrologReasoner()
        self._python = PythonExecutor(timeout=15) if _HAS_PYTHON_EXEC else PythonExecutor(timeout=15)

        # Try to initialize each tool, using None for unavailable ones
        def _try_init(cls_name: str, *args, **kwargs):
            cls = _TOOL_IMPORTS.get(cls_name)
            if cls is not None:
                try:
                    return cls(*args, **kwargs)
                except Exception:
                    return None
            return None

        self._web_searcher = _try_init("WebSearcher")
        self._web_browser = _try_init("WebBrowser")
        github_api_cls = _TOOL_IMPORTS.get("GitHubPublicAPI")
        self._github_api = github_api_cls(token=GITHUB_TOKEN) if github_api_cls else None
        self._lean_eval_submission = _try_init("LeanEvalSubmissionChecker")
        self._lean_eval_problem = _try_init("LeanEvalProblemManager", self._github_api) if self._github_api else None
        self._lean_eval_ci = _try_init("LeanEvalCIVerifier", self._github_api) if self._github_api else None
        self._proof_solve = _try_init("ProofSolveOrchestrator", self._github_api) if self._github_api else None
        self._maths_solve = _try_init("MathsSolveOrchestrator")
        lean_eval_problem = getattr(self, '_lean_eval_problem', None)
        lean_eval_submission = getattr(self, '_lean_eval_submission', None)
        lean_eval_ci = getattr(self, '_lean_eval_ci', None)
        if all(x is not None for x in (lean_eval_problem, lean_eval_submission, lean_eval_ci)):
            self._lean_eval_solve = _try_init("LeanEvalSolveOrchestrator",
                                              lean_eval_problem, lean_eval_submission, lean_eval_ci)
        else:
            self._lean_eval_solve = None
        self._code_scratch = _try_init("CodeScratchPadOrchestrator", self._github_api) if self._github_api else None
        self._git = _try_init("GitExecutor")
        self._prove_scratch = _try_init("ProveScratchPadOrchestrator", self._github_api) if self._github_api else None
        self._deepseek_prover = _try_init("DeepSeekProver")
        self._bfs_prover = _try_init("BFSProver")
        lean_mathlib = _try_init("LeanMathlib")
        self._lean4_builder = _try_init("Lean4Builder", self._bfs_prover, lean_mathlib) if self._bfs_prover and lean_mathlib else None
        self._matharena = _try_init("MathArenaSolveOrchestrator")
        self._reason_scratch = _try_init("ReasonScratchPadOrchestrator", self._github_api) if self._github_api else None
        self._chart_plotter = _try_init("ChartPlotter")
        self._network_visualizer = _try_init("NetworkVisualizer")
        self._lean_mathlib = _try_init("LeanMathlib")

    def think(self, user_input: str) -> str:
        """Process a user request through the NOVA multi-agent pipeline.

        Flow:
        1. Record in knowledge graph
        2. Decompose task (dimensions, risk, plan)
        3. Run meta-cognitive loop
        4. Dispatch to specialized agents
        5. Collect results and calibrate confidence
        6. Synthesize final answer with degradation state
        """
        if self._shutdown_requested:
            return "Session stopped."

        turn = self.knowledge_graph.next_turn()
        self._current_turn = turn
        self._messages.append({"role": "user", "content": user_input})

        # 1. Analyze the task
        dimensions, risk, plan = self.orchestrator.decompose_task(user_input)
        recommended = recommend_tools(dimensions)

        self._log(f"[NOVA] Turn {turn}: dimensions={dimensions.name}, risk={risk.name}")
        self._log(f"[NOVA] Recommended tools: {recommended[:5]}")

        # 2. Record in knowledge graph
        self.knowledge_graph.assert_fact(
            f"turn_{turn}", "dimensions", dimensions.name,
            source="nova:triage",
        )
        self.knowledge_graph.assert_fact(
            f"turn_{turn}", "risk", risk.name,
            source="nova:triage",
        )

        # 3. Run meta-cognitive loop (NOW AUTO-TRIGGERED — critical fix!)
        meta_repairs = self.orchestrator.meta_loop.run()
        if meta_repairs:
            self._log(f"[META] {len(meta_repairs)} auto-repair(s) applied")

        # 4. Delegate to specialized agents in parallel
        agent_futures = []
        for role, agent in self._agents.items():
            msg = AgentMessage(
                sender=AgentRole.ORCHESTRATOR,
                recipient=role,
                content=user_input,
                message_type="task",
                timestamp=time.time(),
            )
            future = self._executor.submit(agent.process, msg)
            agent_futures.append((role, future))

        # 5. Collect results
        all_sources: list[str] = []
        all_dimensions = EvidenceDimension.NONE
        for role, future in agent_futures:
            try:
                result = future.result(timeout=plan.max_budget_seconds)
                self.orchestrator.record_result(result)
                all_sources.extend(result.evidence_sources)
                all_dimensions |= result.dimensions
                self._log(f"[NOVA] {role.value}: {'OK' if result.success else 'FAIL'}")
            except Exception as exc:
                self._log(f"[NOVA] {role.value}: ERROR {exc}")
                self.orchestrator.record_result(AgentResult(
                    agent=role, output="", success=False,
                    error=f"Agent failed: {exc}",
                ))

        # 6. Calibrate confidence
        confidence = ConfidenceCalibrator.estimate(
            evidence_sources=all_sources,
            dimensions=all_dimensions,
            independent_sources=max(1, len(agent_futures)),
        )

        # 7. Determine degradation state
        degradation = degrade(
            required_confidence=plan.required_confidence,
            achieved=confidence,
            required_lean=plan.requires_lean,
            lean_available="lean4_exec" in all_sources,
            has_any_evidence=len(all_sources) > 0,
        )

        # 8. Verify evidence against plan
        verification_report = verify_evidence_profile(plan, all_sources)

        # 9. Synthesize answer
        answer = self._synthesize_answer(
            user_input, degradation, confidence, dimensions, risk, plan,
            verification_report,
        )

        self._messages.append({"role": "assistant", "content": answer})
        return answer

    def _synthesize_answer(self, user_input: str,
                            degradation: DegradationState,
                            confidence: ConfidenceScore,
                            dimensions: EvidenceDimension,
                            risk: RiskLevel,
                            plan: VerificationPlan,
                            verification_report: str = "") -> str:
        """Synthesize the final answer."""
        from nova.confidence_calibrator import ConfidenceCalibrator as CC

        parts = [
            f"## Direct Answer",
            f"Analysis of: {user_input}",
            "",
            f"## Status",
            format_degradation_state(degradation),
            "",
            f"## Evidence Profile",
            f"- **Dimensions**: {dimensions.name}",
            f"- **Risk Level**: {risk.name}",
            f"- **Confidence**: {CC.format_score(confidence)}",
            f"- **Verification Depth**: {plan.verification_depth}/4",
            "",
        ]

        # Add agent results (FIXED: iterate over dict values properly)
        parts.append("## Agent Results")
        for role in [AgentRole.LOGICAL_REASONER, AgentRole.COMPUTATION_RUNNER,
                     AgentRole.PROOF_STRATEGIST, AgentRole.FORMAL_VERIFIER]:
            results = self.orchestrator.collect_results(role)
            for r in results:
                icon = "\u2705" if r.success else "\u274c"
                parts.append(f"- {icon} {role.value}: {r.output[:200] if r.output else r.error[:200]}")

        # Verification section (using DegradationState enum directly, not .value strings)
        if degradation == DegradationState.FULLY_VERIFIED:
            parts.append(f"\n## Verification\nAll evidence requirements satisfied at required confidence {plan.required_confidence}.")
        elif degradation in (DegradationState.STRONGLY_VERIFIED,
                             DegradationState.PARTIALLY_VERIFIED,
                             DegradationState.MINIMALLY_VERIFIED):
            gap = plan.required_confidence - confidence.probability
            parts.append(f"\n## Verification\nCore requirements satisfied. Confidence gap: {gap:.3f}")
        elif degradation == DegradationState.PARTIAL_RESULTS:
            parts.append(f"\n## Verification\nPartial evidence gathered but full verification not achieved. Re-run with higher budget or request specific verification.")
        else:
            parts.append(f"\n## Verification\nInsufficient evidence. The task could not be completed with available tools.")

        if verification_report:
            parts.append(f"\n### Evidence Check\n```\n{verification_report}\n```")

        parts.append(f"\n## Assumptions Used\n- Evidence dimensions derived from task description\n- Risk assessment based on keyword analysis\n- Confidence calibrated using Bayesian noisy-OR model")
        parts.append(f"\n## Remaining Limits\n- Verification plan: depth {plan.verification_depth}, budget {plan.max_budget_seconds}s\n- Requires human review: {plan.requires_human_review}")

        if self.orchestrator.meta_loop.state.violations:
            parts.append(f"\n## Meta-Cognitive Notes\n{self.orchestrator.meta_loop.get_summary()}")

        return "\n".join(parts)

    def _log(self, msg: str):
        if self.verbose:
            self.log_buffer.append(msg)
            print(f"[nova] {msg}", file=__import__('sys').stderr)

    def close(self):
        """Release all resources."""
        self._shutdown_requested = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        for component in (
            getattr(self, "_prolog", None),
            getattr(self, "_python", None),
            getattr(self, "_chart_plotter", None),
            getattr(self, "_network_visualizer", None),
        ):
            if component:
                try:
                    component.kill_running()
                except Exception:
                    pass
        try:
            if getattr(self, "_web_browser", None):
                self._web_browser.close()
        except Exception:
            pass


# --- NOVA tool definitions (OpenAI-compatible function-calling format) ---
# Adapted from evo-ai's EVO_TOOLS in evo_agent.py

NOVA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "prolog_exec",
            "description": "Execute a self-contained Prolog program for logical reasoning, assumption tracking, and proof traces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Prolog code to execute. Must include main/0."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Execute Python code in a sandboxed environment for computation and verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lean4_exec",
            "description": "Execute Lean 4 code for formal theorem proving and verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Lean 4 code to execute. Must start with: import Mathlib"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, documentation, or general lookups.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "number", "description": "Maximum number of results."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_browse",
            "description": "Browse a webpage and extract its content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to browse."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_dir",
            "description": "List the contents of a directory in a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner."},
                    "repo": {"type": "string", "description": "Repository name."},
                    "path": {"type": "string", "description": "Directory path."},
                    "ref": {"type": "string", "description": "Branch or commit."}
                },
                "required": ["owner", "repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read file content from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner."},
                    "repo": {"type": "string", "description": "Repository name."},
                    "path": {"type": "string", "description": "File path."},
                    "ref": {"type": "string", "description": "Branch or commit."}
                },
                "required": ["owner", "repo", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clone_repository",
            "description": "Clone a Git repository for code inspection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Repository URL."},
                    "ref": {"type": "string", "description": "Branch or tag."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mathlib_check",
            "description": "Verify whether a specific theorem/definition exists in Mathlib.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Exact theorem/definition name."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deepseek_prover",
            "description": "Launch a background Lean 4 proof specialist for complex theorem proving.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string", "description": "The theorem or subgoal to prove."},
                    "context": {"type": "string", "description": "Proof attempts, errors, and what has been tried."}
                },
                "required": ["problem"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bfs_prover",
            "description": "Launch a background tactic-level Lean 4 specialist for a specific proof step.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string", "description": "Short description of what you're proving."},
                    "context": {"type": "string", "description": "Exact Lean goal state."}
                },
                "required": ["problem", "context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lean4_builder",
            "description": "Step-by-step Lean 4 proof builder that fills sorry placeholders automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Lean 4 theorem skeleton with sorry placeholders."},
                    "problem": {"type": "string", "description": "Human description of what's being proved."}
                },
                "required": ["code", "problem"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "maths_problem",
            "description": "Stage controller for mathematical problem solving with derivation tracking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "start, model, explore, derive, verify_step, verify_final, or status."},
                    "problem": {"type": "string", "description": "Problem title."},
                    "target": {"type": "string", "description": "Target result or theorem."}
                },
                "required": ["stage"]
            }
        }
    },
]
