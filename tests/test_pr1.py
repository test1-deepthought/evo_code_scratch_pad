"""PR #1 Tests - Shared KB Protocol (Pattern D) - MINIMAL 5-STEP"""
import os, sys
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pr1_mind.shared_kb import SharedKB, _esc
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter

import tempfile
tmpdir = tempfile.gettempdir()

# 1: Init
kb = SharedKB(storage_tag="ci_minimal")
assert os.path.exists(kb.path), f"FAIL: KB not at {kb.path}"
print("1/5 init: OK")

# 2: Propose+read
kb.propose_strategy("s1", "P", "desc", 2)
with open(kb.path) as f:
    c = f.read()
assert "propose_strategy(s1" in c
assert "strategy_log(s1" in c
print("2/5 propose: OK")

# 3: Classify
PROBLEM = "Find all primes p such that p^2 + 2 is also prime."
m = MindKBAdapter(kb)
proposed = m.classify_and_propose(PROBLEM)
assert len(proposed) > 0, f"FAIL: no strategies from classify"
assert "strat_0001" in proposed
print(f"3/5 classify: {len(proposed)} strategies: OK")

# 4: Trace
e = EvoKBAdapter(kb)
claimed = proposed[0]
kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
kb.asserta(f"active_strategy({claimed})")
e.begin_strategy(claimed)
e.write_trace("REASON", "test_goal", "derived")
e.complete_strategy(claimed, "succeeded", "OK")
traces = m.read_traces()
assert len(traces) > 0, f"FAIL: empty traces: '{traces}'"
print(f"4/5 trace: {len(traces)} chars: OK")

# 5: Critique + check
m.critique_strategy(claimed, gap="test gap", severity="low", suggestion="fix")
critiques = e.check_for_critiques(claimed)
assert len(critiques) > 0, f"FAIL: no critiques: {critiques}"
print(f"5/5 critique: {len(critiques)} critiques: OK")

os.unlink(kb.path)
print("\nALL 5 TESTS PASSED")
sys.exit(0)
