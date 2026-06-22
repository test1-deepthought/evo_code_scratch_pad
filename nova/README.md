# NOVA — Neurally-Orchestrated Verification Architecture

A complete redesign of EVO (Explicit-assumption Verification Orchestrator).

## Version

**v0.2.0** — All critical and major issues fixed. [See changelog](#changelog)

## Architecture (8 Innovations)

| # | Innovation | Module | Status |
|---|-----------|--------|--------|
| I1 | Persistent Knowledge Graph | `knowledge_graph.py` | ✅ Fixed: added `export_prolog_facts()` |
| I2 | Multi-Agent Reasoning Society | `agent.py` | ✅ Fixed: all 8 agents registered |
| I3 | Composable Evidence Dimensions | `evidence_dimensions.py` | ✅ Stable |
| I4 | Meta-Cognitive Self-Healing Loop | `meta_cognitive_loop.py` | ✅ Fixed: auto-triggered during think() |
| I5 | Learned Proof Library | `proof_library.py` | ✅ Fixed: tag-based search, stats |
| I6 | Bayesian Confidence Calibrator | `confidence_calibrator.py` | ✅ Fixed: IntEnum, format_score(), combine() |
| I7 | Consequence-Proportional Verification | `verification_scheduler.py` | ✅ Fixed: execute_plan(), verify_evidence_profile() |
| I8 | Graceful Degradation | `graceful_degradation.py` | ✅ Fixed: SKETCH reachable, IntEnum comparisons |

## Quick Start

```python
# Requires DEEPSEEK_API_KEY in .env
from nova.agent import NovaOrchestrator

nova = NovaOrchestrator(verbose=True)
result = nova.think("Prove that the sum of the first n natural numbers is n(n+1)/2")
```

## Key Differences from EVO

1. **No rigid six tiers**: Tasks declare evidence requirements as composable tags
2. **Multi-agent society**: 8 specialized agents work in parallel
3. **Persistent learning**: Knowledge graph keeps facts across sessions
4. **Self-healing**: Meta-cognitive loop auto-repairs gate violations
5. **Confidence calibration**: Bayesian posterior for every conclusion
6. **Proportional verification**: Risk-based verification depth
7. **Graceful degradation**: 7-level success spectrum (not binary)

## Running Tests

```bash
pip install -r nova/requirements.txt
python -m pytest tests/ -v --cov=nova
```

## Changelog

### v0.2.0 (2026-06-22)
- **Standalone imports**: All modules import without evo-ai installed (with stubs)
- **All 8 agents registered**: PROOF_STRATEGIST, CODE_INSPECTOR, WEB_RESEARCHER, FORMAL_VERIFIER, QUALITY_AUDITOR were missing
- **Meta-loop auto-triggered**: Now runs during `think()` — was never invoked
- **ConfidenceLevel: Flag → IntEnum**: Fixes all `.value` comparisons in graceful_degradation
- **KnowledgeGraph.export_prolog_facts()**: Added (was missing, breaking logical_reasoner integration)
- **Verification plans are actionable**: `execute_plan()` and `verify_evidence_profile()` added
- **SKETCH state reachable**: Fixed unreachable condition in graceful_degradation
- **CI workflow**: 7 jobs (lint, test x3 Python versions, standalone verification, KG persistence, proof library, evidence dimensions, degradation, confidence calibrator)
- **6 test files**: 80+ test cases across all modules

### v0.1.0 (2026-06-21)
- Initial NOVA architecture implementation
- 30 issues identified in code review
