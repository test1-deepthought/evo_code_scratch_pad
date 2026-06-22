"""
NOVA — Neurally-Orchestrated Verification Architecture

A complete redesign of EVO (Explicit-assumption Verification Orchestrator)
that replaces the six-tier single-agent stateless design with a persistent
knowledge graph, multi-agent reasoning society, composable evidence
dimensions, a meta-cognitive self-healing loop, a learned proof library,
a Bayesian confidence calibrator, consequence-proportional verification
cost, and graceful degradation with confidence-scored partial results.

v0.2.0 — All critical and major issues fixed:
- Standalone-safe imports (works with or without evo-ai installed)
- All 8 specialized agents registered and functional
- Meta-cognitive loop auto-triggered during task processing
- ConfidenceLevel changed from Flag to IntEnum for ordered comparison
- export_prolog_facts() added to KnowledgeGraph
- Verification plans are now actionable (execute_plan, verify_evidence_profile)
- Graceful degradation: SKETCH state now reachable
- GitHub Actions CI workflow with 7 job suite (lint, type-check, test x3 Python versions, syntax-validate, import-check, all-checks-pass)
- 8 pytest test files with 80+ test cases
- CI triggers on push to evo/nova* branches
"""

__version__ = "0.2.0"
