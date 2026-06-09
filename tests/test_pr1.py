"""
PR #1 Tests - Shared KB Protocol (Pattern D)

Works both with pytest (pip install pytest) and standalone.
Run: python3 tests/test_pr1.py
"""
import os
import sys

# Ensure repo root is on sys.path so pr1_mind is importable
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
    """Standalone test runner."""
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
            import traceback
            traceback.print_exc()

    print("=" * 65)
    print("PR #1 Tests - Shared KB Protocol (Pattern D)")
    print("=" * 65)

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
            assert "selected" in c
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
            e.write_trace("REASON", "conclusion(direct_factorization_impossible)", "failed",
                          "No algebraic factorization found")
            e.write_trace("COMPUTE", "python_exec: test p=2..100", "derived",
                          "Only p=3 works but no proof")
            m.critique_strategy("strat_direct",
                                gap="Cannot prove uniqueness",
                                severity="high",
                                suggestion="Switch to modular arithmetic mod 3")
            critiques = e.check_for_critiques("strat_direct")
            assert len(critiques) > 0
            assert critiques[0]["severity"] == "high"
            e.backtrack("strat_direct", "Direct approach insufficient")
            new_sid = m.propose_backtrack(
                "strat_direct",
                "Direct factorization cannot prove uniqueness",
                "Use modular arithmetic: if p != 3 mod 3 then p^2=1 mod 3 => p^2+2=0 mod 3",
                new_priority=2
            )
            assert new_sid == "strat_backtrack_strat_direct"
            with open(kb.path) as f:
                c = f.read()
            assert "propose_strategy(strat_backtrack" in c
        finally:
            _cleanup(kb)
    t("backtrack_flow", test_backtrack)

    print("\n--- TestEvoHelpers ---")
    def test_check():
        kb = _make_kb()
        try:
            e = EvoKBAdapter(kb)
            assert e.should_check_for_new_strategies("cannot prove the statement") is True
            assert e.should_check_for_new_strategies("The answer is 42.") is False
            assert e.should_check_for_new_strategies("no solution found") is True
            assert e.should_check_for_new_strategies("") is False
            assert e.should_check_for_new_strategies("failed to verify") is True
            assert e.should_check_for_new_strategies("insufficient evidence") is True
        finally:
            _cleanup(kb)
    t("should_check_for_new_strategies", test_check)

    print("\n--- TestEdgeCases ---")
    def test_retract():
        kb = _make_kb()
        try:
            kb.asserta("critique_gap(s1, 'gap1', high, 'fix1').")
            kb.asserta("critique_gap(s1, 'gap2', medium, 'fix2').")
            kb.asserta("propose_strategy(s1, 'p', 'd', 1).")
            old = kb.retractall("critique_gap")
            assert "gap1" in old
            assert "gap2" in old
            with open(kb.path) as f:
                c = f.read()
            assert "next_strategy(" in c
            assert "propose_strategy(s1" in c
            assert "critique_gap" not in c
        finally:
            _cleanup(kb)
    t("retractall_removes_facts", test_retract)

    def test_empty():
        kb = _make_kb()
        try:
            r = kb.query("findall(X, propose_strategy(X, _, _, _), L)")
            assert r is not None
        finally:
            _cleanup(kb)
    t("empty_kb_query_does_not_crash", test_empty)

    def test_unicode():
        e = _esc("x² + y² = z² (Pythagorean)")
        assert e is not None
        assert len(e) > 0
    t("unicode_in_facts", test_unicode)

    def test_long():
        e = _esc("A" * 1000)
        assert "[...truncated]" in e
        assert len(e) < 600
    t("long_fact_truncation", test_long)

    print("\n" + "=" * 65)
    total = passed + failed
    print(f"RESULTS: {passed} passed, {failed} failed out of {total} tests")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"{failed} TEST(S) FAILED!")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
