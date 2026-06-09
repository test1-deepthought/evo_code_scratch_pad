import os
import sys
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    import pytest
except ImportError:
    pytest = None

from pr1_mind.shared_kb import SharedKB, _esc
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter

def _cleanup(kb):
    try:
        if os.path.exists(kb.path):
            os.unlink(kb.path)
    except OSError:
        pass

def _make_kb():
    tag = f"test_{os.urandom(4).hex()}"
    return SharedKB(storage_tag=tag)

if pytest:
    @pytest.fixture
    def shared_kb():
        kb = _make_kb()
        yield kb
        _cleanup(kb)
    @pytest.fixture
    def mind_adapter(shared_kb):
        return MindKBAdapter(shared_kb)
    @pytest.fixture
    def evo_adapter(shared_kb):
        return EvoKBAdapter(shared_kb)
    class TestSharedKBCore:
        def test_init_creates_header(self, shared_kb):
            assert os.path.exists(shared_kb.path)
            with open(shared_kb.path) as f:
                content = f.read()
            assert "propose_strategy/4" in content
            assert "next_strategy(" in content
        def test_ensure_period(self):
            assert SharedKB._ensure_period("fact(a)") == "fact(a)."
            assert SharedKB._ensure_period("fact(a).") == "fact(a)."
        def test_esc_handles_special_chars(self):
            result = _esc("it's a \"test\" with newline")
            assert "\\'" in result
            assert "\\n" in result
    class TestStrategyLayer:
        def test_mind_proposes_strategies(self, shared_kb):
            shared_kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
            shared_kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
            with open(shared_kb.path) as f:
                content = f.read()
            assert "propose_strategy(s1" in content
            assert "propose_strategy(s2" in content
            assert "strategy_log(s1" in content
        def test_strategy_result_propagation(self, shared_kb):
            shared_kb.propose_strategy("s1", "Problem", "Test strategy", priority=5)
            shared_kb.asserta("strategy_result(s1, in_progress, 'claimed')")
            shared_kb.report_strategy_result("s1", "succeeded", "All derivations completed")
            with open(shared_kb.path) as f:
                content = f.read()
            assert "strategy_result(s1" in content
            assert "succeeded" in content
    class TestCriticLoop:
        PROBLEM = "Find all primes p such that p^2 + 2 is also prime."
        def test_full_critic_loop(self, shared_kb, mind_adapter, evo_adapter):
            proposed = mind_adapter.classify_and_propose(self.PROBLEM)
            assert len(proposed) > 0
            assert "strat_0001" in proposed
            claimed = proposed[0]
            shared_kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
            shared_kb.asserta(f"active_strategy({claimed})")
            evo_adapter.begin_strategy(claimed)
            evo_adapter.write_trace("REASON", "problem_spec(...)", "derived")
            evo_adapter.write_trace("COMPUTE", "python_exec: test p=2,3,5,7,11...", "derived")
            evo_adapter.complete_strategy(claimed, "succeeded", "Found p=3")
            traces = mind_adapter.read_traces()
            assert len(traces) > 0
            mind_adapter.critique_strategy(claimed, gap="Missing p=3 case", severity="low", suggestion="Verify 3^2+2=11 is prime")
            critiques = evo_adapter.check_for_critiques(claimed)
            assert len(critiques) > 0
            with open(shared_kb.path) as f:
                content = f.read()
            assert "strategy_log(" in content
            assert "proposed" in content
            assert "selected" in content
        def test_backtrack_flow(self, shared_kb, mind_adapter, evo_adapter):
            mind_adapter.propose_custom_strategy("strat_direct", self.PROBLEM, "Attempt direct factorization", priority=2)
            mind_adapter.propose_custom_strategy("strat_modular", self.PROBLEM, "Use modular arithmetic mod 3", priority=3)
            evo_adapter._current_strategy = "strat_direct"
            evo_adapter._current_turn = 0
            shared_kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")
            evo_adapter.write_trace("REASON", "direct_factorization_impossible", "failed", "No algebraic factorization found")
            mind_adapter.critique_strategy("strat_direct", gap="Cannot prove uniqueness", severity="high", suggestion="Switch to modular")
            assert evo_adapter.has_open_critique("strat_direct")
            evo_adapter.backtrack("strat_direct", "high-severity critique received")
            with open(shared_kb.path) as f:
                content = f.read()
            assert "needs_critique" in content
    def run_tests():
        passed = 0
        failed = 0
        for cls in [TestSharedKBCore, TestStrategyLayer, TestCriticLoop]:
            instance = cls()
            for name in dir(cls):
                if name.startswith("test_"):
                    try:
                        getattr(instance, name)()
                        passed += 1
                        print(f"  PASS: {name}")
                    except Exception as e:
                        failed += 1
                        print(f"  FAIL: {name}: {e}")
        print(f"\nResults: {passed}/{passed + failed} passed")
        return failed == 0
    if __name__ == "__main__":
        success = run_tests()
        sys.exit(0 if success else 1)
