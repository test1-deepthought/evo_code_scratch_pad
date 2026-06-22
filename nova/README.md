# NOVA — Neurally-Orchestrated Verification Architecture

NOVA is a complete redesign of EVO (Explicit-assumption Verification Orchestrator)
that addresses seven fundamental weaknesses while preserving all six core strengths.

## Architecture Overview

NOVA replaces EVO's six-tier single-agent stateless design with:

| Innovation | Component | Description |
|---|---|---|
| **I1** | `knowledge_graph.py` | Persistent Knowledge Graph — facts, proofs, and strategies accumulate across sessions in a JSON-backed triplestore |
| **I2** | `agent.py` | Multi-Agent Reasoning Society — specialized sub-agents (Orchestrator, LogicalReasoner, ComputationRunner) coordinate via a shared blackboard |
| **I3** | `evidence_dimensions.py` | Composable Evidence Dimensions — replaces EVO's six rigid tiers with composable tags (`COMPUTATION`, `DERIVATION`, `SOURCE`, `FORMAL`, etc.) |
| **I4** | `meta_cognitive_loop.py` | Meta-Cognitive Self-Healing Loop — continuously monitors gate violations and auto-repairs before the user sees errors |
| **I5** | `proof_library.py` | Learned Proof Library — caches Lean 4 proof patterns with similarity search and skeleton suggestion |
| **I6** | `confidence_calibrator.py` | Bayesian Confidence Calibrator — assigns posterior probabilities using a noisy-OR approximation over evidence sources |
| **I7** | `verification_scheduler.py` | Consequence-Proportional Verification — scales verification cost to match risk level (Trivial → Critical) |
| **I8** | `graceful_degradation.py` | Graceful Degradation — 7-level graduated success spectrum replaces EVO's binary SOLVED/INCOMPLETE |

## Migrated from EVO

All infrastructure components from [machinelearning2014/evo-ai](https://github.com/machinelearning2014/evo-ai) are preserved:

- **Prolog Reasoner** (`reasoning/reasoner.py`) — SWI-Prolog subprocess execution
- **Python Executor** (`tools/python_executor.py`) — sandboxed sandboxed execution with SymPy, NumPy, SciPy
- **DeepSeek Prover** (`tools/deepseek_prover.py`) — background proof specialist
- **BFS Prover** (`tools/bfs_prover.py`) — tactic-level Lean 4 completion
- **Lean 4 Integration** (`lean/mathlib.py`) — `lean4_exec`, `mathlib_check`, `mathlib_search`
- **Web Search** (`tools/web_search.py`) — Brave/LangSearch/DuckDuckGo with fallback
- **GitHub API** (`tools/github_public.py`) — authenticated repository operations
- **Lean-Eval** — `solve_lean_eval_problem`, `lean_eval_problem`, `lean_eval_submission_check`
- **Scratch Pads** — `code_scratch_pad`, `prove_scratch_pad`, `reason_scratch_pad`
- **Stage Controllers** — `prove_problem`, `maths_problem`, `solve_matharena_problem`

## Usage

```python
from nova.agent import NovaOrchestrator

nova = NovaOrchestrator(verbose=True)
result = nova.think("Prove that the sum of the first n natural numbers is n(n+1)/2")
```

## Key Differences from EVO

1. **No rigid six tiers**: Tasks declare evidence requirements as composable tags
2. **Persistent learning**: Knowledge graph and proof library survive across sessions
3. **Confidence scoring**: Every conclusion has a Bayesian probability, not just binary status
4. **Graduated success**: 7 levels from FULLY_VERIFIED to INCOMPLETE
5. **Self-healing**: Meta-cognitive loop repairs gate violations automatically
6. **Proportional cost**: Verification depth scales with risk assessment
7. **Multi-agent**: Specialized agents work in parallel via ThreadPoolExecutor
