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
from enum import auto, StrEnum
from typing import Any, Callable, Optional

from openai import OpenAI

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
from nova.confidence_calibrator import ConfidenceCalibrator, ConfidenceScore
from nova.evidence_dimensions import EvidenceDimension, classify_dimensions, recommend_tools
from nova.graceful_degradation import DegradationState, degrade, format_degradation_state
from nova.knowledge_graph import KnowledgeGraph
from nova.meta_cognitive_loop import GateType, MetaCognitiveLoop, create_default_loop
from nova.proof_library import ProofLibrary
from nova.verification_scheduler import RiskLevel, VerificationPlan, create_verification_plan, assess_risk

logger = logging.getLogger("nova-agent")


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
        default_factory=lambda: ConfidenceScore(0.5, "MODERATE", 0, EvidenceDimension.NONE, "")
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
        # The orchestrator's primary job is to decompose tasks and
        # dispatch to specialized agents.
        return AgentResult(
            agent=self.role,
            output=f"Orchestrator received: {message.content[:100]}...",
            success=True,
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
            source=f"nova:dispatch:{message_type}",
        )

    def collect_results(self, agent: AgentRole) -> list[AgentResult]:
        return self._results.get(agent, [])

    def record_result(self, result: AgentResult) -> None:
        if result.agent not in self._results:
            self._results[result.agent] = []
        self._results[result.agent].append(result)
        self.kg.assert_fact(
            result.agent.value, "produced_result", "success" if result.success else "failure",
            confidence=result.confidence.probability,
            source="nova:agent_result",
        )

    @property
    def meta_loop(self) -> MetaCognitiveLoop:
        return self._meta_loop


class LogicalReasonerAgent(NovaAgent):
    """Prolog-based logical reasoner. Extracts from evo-ai's PrologReasoner
    (reasoning/reasoner.py) and adapts to the multi-agent architecture.
    """

    def __init__(self, knowledge_graph: KnowledgeGraph):
        super().__init__(AgentRole.LOGICAL_REASONER, knowledge_graph)
        from reasoning.reasoner import PrologReasoner
        self._prolog = PrologReasoner()

    def process(self, message: AgentMessage) -> AgentResult:
        """Execute a Prolog program and return results."""
        code = message.content
        
        # Augment with knowledge graph facts
        kg_facts = self.kg.export_prolog_facts()
        augmented_code = f"% Knowledge graph facts\n{kg_facts}\n\n% Task code\n{code}"
        
        try:
            result = self._prolog.execute_code(augmented_code)
            sources = ["prolog_exec"]
            if kg_facts.strip():
                sources.append("knowledge_graph")
            return AgentResult(
                agent=self.role,
                output=result.get("output", ""),
                success=result.get("success", False),
                evidence_sources=sources,
                dimensions=EvidenceDimension.DERIVATION,
                error=result.get("error", ""),
            )
        except Exception as exc:
            return AgentResult(
                agent=self.role,
                output="",
                success=False,
                evidence_sources=["prolog_exec"],
                dimensions=EvidenceDimension.DERIVATION,
                error=str(exc),
            )


class ComputationRunnerAgent(NovaAgent):
    """Python/SymPy computation runner. Extracts from evo-ai's PythonExecutor
    (tools/python_executor.py).
    """

    def __init__(self, knowledge_graph: KnowledgeGraph):
        super().__init__(AgentRole.COMPUTATION_RUNNER, knowledge_graph)
        from tools.python_executor import PythonExecutor
        self._python = PythonExecutor(timeout=30)

    def process(self, message: AgentMessage) -> AgentResult:
        code = message.content
        try:
            result = self._python.execute(code)
            return AgentResult(
                agent=self.role,
                output=result.get("output", ""),
                success=result.get("success", False),
                evidence_sources=["python_exec"],
                dimensions=EvidenceDimension.COMPUTATION,
                error=result.get("error", ""),
            )
        except Exception as exc:
            return AgentResult(
                agent=self.role,
                output="",
                success=False,
                evidence_sources=["python_exec"],
                dimensions=EvidenceDimension.COMPUTATION,
                error=str(exc),
            )


class NovaOrchestrator:
    """Main NOVA orchestrator — the entry point for all tasks.
    
    Replaces EvoAgent (evo_agent.py) while retaining all the useful
    infrastructure (tool dispatch, Lean integration, web search, GitHub).
    
    Key improvements over EvoAgent:
    1. Multi-agent society: specialized agents work in parallel
    2. Persistent knowledge graph: learns across sessions
    3. Composable evidence: no rigid six-tier classification
    4. Meta-cognitive loop: self-healing on gate violations
    5. Proof library: caches reusable proof patterns
    6. Confidence calibration: Bayesian probability for each conclusion
    7. Proportional verification: cost scales with risk
    8. Graceful degradation: graduated success spectrum
    """

    def __init__(self, verbose: bool = False):
        if not DEEPSEEK_API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set. Copy .env.example to .env and add your key."
            )
        
        self.verbose = verbose
        self.log_buffer: list[str] = []
        
        # Shared state (cross-session persistence)
        self.knowledge_graph = KnowledgeGraph()
        self.proof_library = ProofLibrary()
        
        # LLM client (extracted from evo-ai)
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.model = DEEPSEEK_MODEL
        
        # Multi-agent society
        self.orchestrator = OrchestratorAgent(self.knowledge_graph, self.proof_library)
        self._agents: dict[AgentRole, NovaAgent] = {
            AgentRole.LOGICAL_REASONER: LogicalReasonerAgent(self.knowledge_graph),
            AgentRole.COMPUTATION_RUNNER: ComputationRunnerAgent(self.knowledge_graph),
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
        """Initialize tool executors — extracted from evo-ai's EvoAgent.__init__."""
        from reasoning.reasoner import PrologReasoner
        from tools.python_executor import PythonExecutor
        from tools.web_search import WebSearcher
        from tools.web_browse import WebBrowser
        from tools.github_public import GitHubPublicAPI
        from tools.lean_eval_problem import LeanEvalProblemManager
        from tools.lean_eval_solver import LeanEvalSolveOrchestrator
        from tools.lean_eval_submission import LeanEvalSubmissionChecker
        from tools.lean_eval_ci import LeanEvalCIVerifier
        from tools.code_scratch_pad import CodeScratchPadOrchestrator
        from tools.git_executor import GitExecutor
        from tools.prove_scratch_pad import ProveScratchPadOrchestrator
        from tools.deepseek_prover import DeepSeekProver
        from tools.bfs_prover import BFSProver
        from tools.lean4_builder import Lean4Builder
        from tools.matharena_solver import MathArenaSolveOrchestrator
        from tools.reason_scratch_pad import ReasonScratchPadOrchestrator
        from tools.proof_solver import ProofSolveOrchestrator
        from tools.maths_solver import MathsSolveOrchestrator
        from tools.chart_plotter import ChartPlotter
        from tools.network_visualizer import NetworkVisualizer
        from lean.mathlib import LeanMathlib
        
        self._prolog = PrologReasoner()
        self._python = PythonExecutor(timeout=15)
        self._web_searcher = WebSearcher()
        self._web_browser = WebBrowser()
        self._github_api = GitHubPublicAPI(token=GITHUB_TOKEN)
        self._lean_eval_submission = LeanEvalSubmissionChecker()
        self._lean_eval_problem = LeanEvalProblemManager(self._github_api)
        self._lean_eval_ci = LeanEvalCIVerifier(self._github_api)
        self._proof_solve = ProofSolveOrchestrator(self._github_api)
        self._maths_solve = MathsSolveOrchestrator()
        self._lean_eval_solve = LeanEvalSolveOrchestrator(
            self._lean_eval_problem,
            self._lean_eval_submission,
            self._lean_eval_ci,
        )
        self._code_scratch = CodeScratchPadOrchestrator(self._github_api)
        self._git = GitExecutor()
        self._prove_scratch = ProveScratchPadOrchestrator(self._github_api)
        self._deepseek_prover = DeepSeekProver()
        self._bfs_prover = BFSProver()
        self._lean4_builder = Lean4Builder(self._bfs_prover, LeanMathlib())
        self._matharena = MathArenaSolveOrchestrator()
        self._reason_scratch = ReasonScratchPadOrchestrator(self._github_api)
        self._chart_plotter = ChartPlotter()
        self._network_visualizer = NetworkVisualizer()
        self._lean_mathlib = LeanMathlib()

    def think(self, user_input: str) -> str:
        """Process a user request through the NOVA multi-agent pipeline.
        
        Flow:
        1. Record in knowledge graph
        2. Decompose task (dimensions, risk, plan)
        3. Dispatch to specialized agents
        4. Collect results and calibrate confidence
        5. Synthesize final answer with degradation state
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
        
        # 3. Delegate to specialized agents
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
        
        # 4. Collect results
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
        
        # 5. Calibrate confidence
        confidence = ConfidenceCalibrator.estimate(
            evidence_sources=all_sources,
            dimensions=all_dimensions,
            independent_sources=max(1, len(agent_futures)),
        )
        
        # 6. Determine degradation state
        degradation = degrade(
            required_confidence=plan.required_confidence,
            achieved=confidence,
            required_lean=plan.requires_lean,
            lean_available="lean4_exec" in all_sources,
            has_any_evidence=len(all_sources) > 0,
        )
        
        # 7. Synthesize answer
        answer = self._synthesize_answer(
            user_input, degradation, confidence, dimensions, risk, plan,
        )
        
        self._messages.append({"role": "assistant", "content": answer})
        return answer

    def _synthesize_answer(self, user_input: str,
                            degradation: DegradationState,
                            confidence: ConfidenceScore,
                            dimensions: EvidenceDimension,
                            risk: RiskLevel,
                            plan: VerificationPlan) -> str:
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
        
        # Add agent results
        parts.append("## Agent Results")
        for role, results in self.orchestrator.collect_results(AgentRole.LOGICAL_REASONER).items():
            for r in results:
                icon = "\u2705" if r.success else "\u274c"
                parts.append(f"- {icon} {role.value}: {r.output[:200] if r.output else r.error[:200]}")
        
        if degradation == DegradationState.FULLY_VERIFIED:
            parts.append(f"\n## Verification\nAll evidence requirements satisfied at required confidence {plan.required_confidence}.")
        elif degradation.value in ("STRONGLY_VERIFIED", "PARTIALLY_VERIFIED", "MINIMALLY_VERIFIED"):
            parts.append(f"\n## Verification\nCore requirements satisfied. Confidence gap: {plan.required_confidence - confidence.probability:.3f}")
        elif degradation == DegradationState.PARTIAL_RESULTS:
            parts.append(f"\n## Verification\nPartial evidence gathered but full verification not achieved. Re-run with higher budget or request specific verification.")
        else:
            parts.append(f"\n## Verification\nInsufficient evidence. The task could not be completed with available tools.")
        
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
            "description": "Execute a self-contained Prolog program for logical reasoning and derivation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Prolog code to execute. Must include main/0."}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Execute Python code for computation, data analysis, or symbolic math.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Python code to execute. Use print() for output."}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lean4_exec",
            "description": "Execute Lean 4 code for formal theorem proving. ALWAYS start with: import Mathlib",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Lean 4 code to execute."}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prove_problem",
            "description": "Stage controller for formal proof verification. Use stage=start, frontier_plan, register_frontier_lemma, verify_frontier_lemma, prove_ready, verify_final.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "start, frontier_plan, register_frontier_lemma, verify_frontier_lemma, prove_ready, verify_final, save_incomplete, or status."},
                    "problem": {"type": "string", "description": "Short proof problem title or id."},
                    "theorem_statement": {"type": "string", "description": "Exact theorem statement to prove."},
                    "candidate_proof": {"type": "string", "description": "Complete final Lean source for verify_final."},
                    "lean_verification": {"type": "string", "description": "Raw lean4_exec output for the exact candidate_proof."},
                    "confirm": {"type": "boolean", "description": "Must be true for verify_final."},
                },
                "required": ["stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "maths_problem",
            "description": "Stage controller for mathematical solving. Stages: start, model, explore, derive, verify_step, verify_final.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "start, model, explore, derive, verify_step, verify_final, or status."},
                    "problem": {"type": "string"},
                    "target": {"type": "string"},
                    "complexity": {"type": "string", "description": "computational, derivational, proof, or formal."},
                    "definitions": {"type": "array", "items": {"type": "string"}},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "claims": {"type": "array", "items": {"type": "string"}},
                    "final_claim": {"type": "string"},
                    "evidence_mode": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "number"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_browse",
            "description": "Browse a webpage and extract content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "selector": {"type": "string", "description": "Optional CSS selector."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github",
            "description": "Unified GitHub tool for repository reads, metadata queries, and authenticated writes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "description": "list_dir, read_file, get_file_sha, query, create_or_update_file, create_repo, create_issue, fork, create_pr"},
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "message": {"type": "string"},
                    "branch": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git",
            "description": "Git and local file operations. Operations: clone, log, diff, grep, show, local_read, test.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "description": "clone, log, diff, grep, show, local_read, test"},
                    "repo": {"type": "string", "description": "GitHub repo URL."},
                    "path": {"type": "string"},
                    "query": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["operation", "repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_scratch_pad",
            "description": "CODE-tier persistent scratch pad. Stages: init, write, write_multi, test, build, pr, teardown, status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string"},
                    "mode": {"type": "string", "description": "inline (GitHub API) or codespace (gh CLI)"},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "files": {"type": "object"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deepseek_prover",
            "description": "Launch a non-blocking Lean 4 proof specialist in the background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string"},
                    "context": {"type": "string"},
                    "run_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bfs_prover",
            "description": "Tactic-level Lean 4 completion model. Takes a Lean goal state and returns the next tactic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string"},
                    "context": {"type": "string", "description": "Lean goal state ending with :::"},
                    "run_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lean4_builder",
            "description": "Automated proof builder. Takes a theorem skeleton with sorry placeholders and fills tactics automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Lean 4 theorem skeleton with sorry placeholders."},
                    "problem": {"type": "string"},
                    "run_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mathlib_check",
            "description": "Verify whether a specific theorem/definition exists in Mathlib by exact name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Exact theorem/definition name."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mathlib_search",
            "description": "Search Mathlib with natural language to find candidate lemmas/theorems.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sympy_exec",
            "description": "Execute SymPy symbolic mathematics code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "matplotlib_exec",
            "description": "Execute Matplotlib plotting code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "networkx_exec",
            "description": "Execute NetworkX graph analysis/plotting code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lean_eval_problem",
            "description": "Manage Lean-Eval problem solving workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "description": "list_unsolved, inspect_problem, prepare_problem, read_solution, write_submission"},
                    "problem": {"type": "string"},
                    "submission": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "solve_lean_eval_problem",
            "description": "Stage controller for solving/fixing Lean-Eval problems with CI preflight.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "new or fix."},
                    "problem": {"type": "string"},
                    "stage": {"type": "string", "description": "start, prove_ready, write_verified, save_incomplete, preflight, ci_verify, status"},
                    "candidate_submission": {"type": "string"},
                    "lean_verification": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_kb",
            "description": "Query the session knowledge base with a Prolog goal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Prolog goal string."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_proof_kb",
            "description": "Query proof memory for verified lemmas, goals, and insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
]

def get_nova_tools() -> list[dict]:
    """Return the NOVA tool definitions."""
    return NOVA_TOOLS
