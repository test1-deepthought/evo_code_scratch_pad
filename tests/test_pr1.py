"""
PR #1 Tests - Shared KB Protocol (Pattern D)

Works both with pytest (pip install pytest) and standalone.
"""
import os, sys
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pr1_mind.shared_kb import SharedKB, _esc
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter

PROBLEM = "Find all primes p such that p^2 + 2 is also prime."

def _cleanup(kb):
    try:
        if os.path.exists(kb.path):
            os.unlink(kb.path)
    except OSError:
        pass

def _make_kb():
    tag = f"test_{os.urandom(4).hex()}"
    return SharedKB(storage_tag=tag)

def run_all_tests():
    passed = 0
    failed = 0
    def t(name, fn):
        nonlocal passed, failed
        try:
            fn()
            passed += 1
            print(f"  PASS: {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")

    print("=" * 65)
    print("PR #1 Tests - Shared KB Protocol (Pattern D)")
    print("=" * 65)

    # === TestSharedKBCore ===
    print("\n--- TestSharedKBCore ---")
    def test_init():
        kb = _make_kb()
        try:
            assert os.path.exists(kb.path)
            with open(kb.path) as f:
                c = f.read()
            assert "propose_strategy/4" in c
            assert "next_strategy(" in c
        finally:
            _cleanup(kb)
    t("init_creates_header", test_init)

    def test_period():
        assert SharedKB._ensure_period("fact(a)") == "fact(a)."
        assert SharedKB._ensure_period("fact(a).") == "fact(a)."
    t("ensure_period", test_period)

    def test_esc():
        r = _esc("safe string")
        assert r.startswith("'") and r.endswith("'")
        r2 = _esc("it's a test")
        assert "'" in r2
    t("esc_handles_special_chars", test_esc)

    # === TestStrategyLayer ===
    print("\n--- TestStrategyLayer ---")
    def test_propose():
        kb = _make_kb()
        try:
            kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
            kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
            with open(kb.path) as f:
                c = f.read()
            assert "propose_strategy(s1" in c
            assert "propose_strategy(s2" in c
            assert "strategy_log(s1" in c
        finally:
            _cleanup(kb)
    t("mind_proposes_strategies", test_propose)

    def test_result():
        kb = _make_kb()
        try:
            kb.propose_strategy("s1", "Problem", "Test", priority=5)
            kb.asserta("strategy_result(s1, in_progress, 'claimed')")
            kb.report_strategy_result("s1", "succeeded", "Done")
            with open(kb.path) as f:
                c = f.read()
            assert "strategy_result(s1" in c
            assert "succeeded" in c
        finally:
            _cleanup(kb)
    t("strategy_result_propagation", test_result)

    # === TestCriticLoop ===
    print("\n--- TestCriticLoop ---")
    def test_loop():
        kb = _make_kb()
        try:
            m = MindKBAdapter(kb)
            e = EvoKBAdapter(kb)
            proposed = m.classify_and_propose(PROBLEM)
            assert len(proposed) > 0
            assert "strat_0001" in proposed
            claimed = proposed[0]
            kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
            kb.asserta(f"active_strategy({claimed})")
            e.begin_strategy(claimed)
            e.write_trace("REASON", "problem_spec(...)", "derived")
            e.write_trace("COMPUTE", "python_exec: test p=2,3,5,7,11...", "derived")
            e.write_trace("PROVE", "lean4_exec: theorem ...", "derived")
            e.complete_strategy(claimed, "succeeded", "Found p=3")
            traces = m.read_traces()
            assert len(traces) > 0
            m.critique_strategy(claimed, gap="Missing explicit p=3 case", severity="low",
                                suggestion="Add verification that 3^2+2=11 is prime")
            critiques = e.check_for_critiques(claimed)
            assert len(critiques) > 0
            kb.record_verification("prime_p_sq_plus_two", "theorem ... := ...")
            with open(kb.path) as f:
                c = f.read()
            assert "strategy_log(" in c
            assert "proposed" in c
        finally:
            _cleanup(kb)
    t("full_critic_loop", test_loop)

    def test_backtrack():
        kb = _make_kb()
        try:
            m = MindKBAdapter(kb)
            e = EvoKBAdapter(kb)
            m.propose_custom_strategy("strat_direct", PROBLEM,
                                      "Attempt direct factorization", priority=2)
            m.propose_custom_strategy("strat_modular", PROBLEM,
                                      "Use modular arithmetic mod 3", priority=3)
            e._current_strategy = "strat_direct"
            e._current_turn = 0
            kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")
            e.write_trace("REASON", "direct_factorization_impossible", "failed",
                          "No algebraic factorization found")
            m.critique_strategy("strat_direct",
                                gap="Cannot prove uniqueness",
                                severity="high",
                                suggestion="Switch to modular arithmetic")
            assert e.has_open_critique("strat_direct")
            e.backtrack("strat_direct", "high-severity critique received")
            with open(kb.path) as f:
                c = f.read()
            assert "needs_critique" in c
        finally:
            _cleanup(kb)
    t("backtrack_flow", test_backtrack)

    # === Summary ===
    print()
    total = passed + failed
    print(f"{'=' * 65}")
    print(f"Results: {passed}/{total} passed")
    if failed:
        print(f"FAILURES: {failed}")
    else:
        print("All tests passed.")
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
