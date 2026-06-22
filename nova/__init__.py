"""
NOVA — Neurally-Orchestrated Verification Architecture

v0.2.3 — CI fixes:
- StrEnum 3.10 compatibility (agent.py, meta_cognitive_loop.py, graceful_degradation.py)
- CI import-check now installs dependencies before verifying
- Fixed degrade() signature regression (was breaking Python 3.12 tests)
- Restored original DegradationPlan fields to match test expectations
"""

__version__ = "0.2.3"
