# EVO to NOVA Migration Notes

This document maps every component extracted from the EVO codebase
(machinelearning2014/evo-ai) to its NOVA equivalent.

## Extracted Components (preserved as-is)

| EVO File | NOVA Status | Notes |
|---|---|---|
| `config.py` | → `nova/config.py` | Extended with NOVA-specific config |
| `reasoning/reasoner.py` | Re-imported directly | PrologReasoner wrapped by LogicalReasonerAgent |
| `tools/python_executor.py` | Re-imported directly | PythonExecutor wrapped by ComputationRunnerAgent |
| `tools/deepseek_prover.py` | Re-imported directly | DeepSeekProver specialist |
| `tools/bfs_prover.py` | Re-imported directly | BFSProver specialist |
| `tools/lean4_builder.py` | Re-imported directly | Lean4Builder |
| `tools/web_search.py` | Re-imported directly | WebSearcher with Brave/LangSearch/DDG |
| `tools/web_browse.py` | Re-imported directly | WebBrowser for content extraction |
| `tools/github_public.py` | Re-imported directly | GitHubPublicAPI |
| `tools/git_executor.py` | Re-imported directly | GitExecutor |
| `tools/code_scratch_pad.py` | Re-imported directly | CodeScratchPadOrchestrator |
| `tools/prove_scratch_pad.py` | Re-imported directly | ProveScratchPadOrchestrator |
| `tools/reason_scratch_pad.py` | Re-imported directly | ReasonScratchPadOrchestrator |
| `tools/proof_solver.py` | Re-imported directly | ProofSolveOrchestrator |
| `tools/maths_solver.py` | Re-imported directly | MathsSolveOrchestrator |
| `tools/lean_eval_problem.py` | Re-imported directly | LeanEvalProblemManager |
| `tools/lean_eval_solver.py` | Re-imported directly | LeanEvalSolveOrchestrator |
| `tools/lean_eval_submission.py` | Re-imported directly | LeanEvalSubmissionChecker |
| `tools/lean_eval_ci.py` | Re-imported directly | LeanEvalCIVerifier |
| `tools/matharena_solver.py` | Re-imported directly | MathArenaSolveOrchestrator |
| `tools/chart_plotter.py` | Re-imported directly | ChartPlotter |
| `tools/network_visualizer.py` | Re-imported directly | NetworkVisualizer |
| `lean/mathlib.py` | Re-imported directly | LeanMathlib |
| `mind/substrate.py` | Re-imported directly | Shared orchestration helpers |
| `mind/core.py` | Replaced | `NovaOrchestrator.think()` is the new entry point |

## Replaced Components

| EVO Component | Replaced By | Rationale |
|---|---|---|
| `evo_agent.py` (6702 lines) | `nova/agent.py` (~500 lines) | Monolithic EvoAgent decomposed into multi-agent society |
| `evo_prompt.py` | `nova/evidence_dimensions.py` | Rigid six-tier prompt replaced by composable dimensions |
| `evo_context.py` | `nova/knowledge_graph.py` | Ephemeral session state replaced by persistent graph |
| `evo_cot_monitor.py` | `nova/meta_cognitive_loop.py` | Passive monitoring replaced by active self-healing |
| `evo_evidence.py` | `nova/confidence_calibrator.py` | Binary evidence tracking replaced by Bayesian calibration |
| `evo_gate_breach_ledger.py` | `nova/meta_cognitive_loop.py` | Passive breach recording replaced by auto-repair |
| 6 rigid tiers | `nova/evidence_dimensions.py` | Composable evidence tags (8 dimensions, mixable) |
| SOLVED/INCOMPLETE | `nova/graceful_degradation.py` | 7-level graduated spectrum |

## New Components

| Component | File | Innovation |
|---|---|---|
| Persistent Knowledge Graph | `nova/knowledge_graph.py` | I1 |
| Multi-Agent Society | `nova/agent.py` | I2 |
| Composable Evidence Dimensions | `nova/evidence_dimensions.py` | I3 |
| Meta-Cognitive Self-Healing Loop | `nova/meta_cognitive_loop.py` | I4 |
| Learned Proof Library | `nova/proof_library.py` | I5 |
| Bayesian Confidence Calibrator | `nova/confidence_calibrator.py` | I6 |
| Consequence-Proportional Verification | `nova/verification_scheduler.py` | I7 |
| Graceful Degradation | `nova/graceful_degradation.py` | I8 |
