#!/usr/bin/env python3
"""
Standalone test runner for PR #1 - Shared KB Protocol.
No pytest dependency needed. Runs directly with: python3 tests/run_tests.py
"""
import os, sys, tempfile, time

# Ensure we can import from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pr1_mind.shared_kb import SharedKB, _esc
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {name}: {e}")
        import traceback
        traceback.print_exc()

def make_kb():
    tag = f"test_{os.urandom(4).hex()}"
    return SharedKB(storage_tag=tag)

def cleanup(kb):
    try:
        if os.path.exists(kb.path):
            os.unlink(kb.path)
    except OSError:
        pass

print("=" * 65)
print("PR #1 Tests - Shared KB Protocol (Pattern D)")
print("=" * 65)

# ===== TestSharedKBCore =====
print("\n--- TestSharedKBCore ---")

def test_init_creates_header():
    kb = make_kb()
    try:
        assert os.path.exists(kb.path), "KB file should exist"
        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy/4" in c, "Header should contain propose_strategy/4"
        assert "next_strategy(" in c, "Header should contain next_strategy"
    finally:
        cleanup(kb)

test("init_creates_header", test_init_creates_header)

def test_ensure_period():
    assert SharedKB._ensure_period("fact(a)") == "fact(a)."
    assert SharedKB._ensure_period("fact(a).") == "fact(a)."

test("ensure_period", test_ensure_period)

def test_esc_handles_special_chars():
    r = _esc("safe string")
    assert r.startswith("'") and r.endswith("'"), f"Should be quoted: {r}"
    # Test with special chars
    r2 = _esc("it's a test")
    assert "'" in r2

test("esc_handles_special_chars", test_esc_handles_special_chars)

# ===== TestStrategyLayer =====
print("\n--- TestStrategyLayer ---")

def test_mind_proposes_strategies():
    kb = make_kb()
    try:
        kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
        kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy(s1" in c, "s1 should be in KB"
        assert "propose_strategy(s2" in c, "s2 should be in KB"
        assert "strategy_log(s1" in c, "Audit log for s1 should exist"
    finally:
        cleanup(kb)

test("mind_proposes_strategies", test_mind_proposes_strategies)

def test_strategy_result_propagation():
    kb = make_kb()
    try:
        kb.propose_strategy("s1", "Problem", "Test", priority=5)
        kb.asserta("strategy_result(s1, in_progress, 'claimed')")
        kb.report_strategy_result("s1", "succeeded", "Done")
        with open(kb.path) as f:
            c = f.read()
        assert "strategy_result(s1" in c
        assert "succeeded" in c
    finally:
        cleanup(kb)

test("strategy_result_propagation", test_strategy_result_propagation)

# ===== TestCriticLoop =====
print("\n--- TestCriticLoop ---")

PROBLEM = "Find all primes p such that p^2 + 2 is also prime."

def test_full_critic_loop():
    kb = make_kb()
    try:
        mind = MindKBAdapter(kb)
        evo = EvoKBAdapter(kb)

        proposed = mind.classify_and_propose(PROBLEM)
        assert len(proposed) > 0, "Should propose at least one strategy"
        assert "strat_0001" in proposed, "First strategy should be strat_0001"

        claimed = proposed[0]
        kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
        kb.asserta(f"active_strategy({claimed})")

        evo.begin_strategy(claimed)
        evo.write_trace("REASON", "problem_spec(...)", "derived")
        evo.write_trace("COMPUTE", "python_exec: test p=2,3,5,7,11...", "derived")
        evo.write_trace("PROVE", "lean4_exec: theorem ...", "derived")
        evo.complete_strategy(claimed, "succeeded", "Found p=3")

        traces = mind.read_traces()
        assert len(traces) > 0, "Traces should be non-empty"

        mind.critique_strategy(claimed, gap="Missing explicit p=3 case", severity="low",
                               suggestion="Add verification that 3^2+2=11 is prime")
        critiques = evo.check_for_critiques(claimed)
        assert len(critiques) > 0, "Should have at least one critique"

        kb.record_verification("prime_p_sq_plus_two", "theorem ... := ...")

        with open(kb.path) as f:
            c = f.read()
        assert "strategy_log(" in c, "Audit log should exist"
        assert "proposed" in c, "Should contain 'proposed' event"
        assert "selected" in c, "Should contain 'selected' event"
    finally:
        cleanup(kb)

test("full_critic_loop", test_full_critic_loop)

def test_backtrack_flow():
    kb = make_kb()
    try:
        mind = MindKBAdapter(kb)
        evo = EvoKBAdapter(kb)

        mind.propose_custom_strategy("strat_direct", PROBLEM,
                                     "Attempt direct factorization", priority=2)
        mind.propose_custom_strategy("strat_modular", PROBLEM,
                                     "Use modular arithmetic mod 3", priority=3)

        evo._current_strategy = "strat_direct"
        evo._current_turn = 0
        kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")

        evo.write_trace("REASON", "conclusion(direct_factorization_impossible)", "failed",
                        "No algebraic factorization found")
        evo.write_trace("COMPUTE", "python_exec: test p=2..100", "derived",
                        "Only p=3 works but no proof")

        mind.critique_strategy("strat_direct",
                               gap="Cannot prove uniqueness",
                               severity="high",
                               suggestion="Switch to modular arithmetic mod 3")
        critiques = evo.check_for_critiques("strat_direct")
        assert len(critiques) > 0, "Should have critiques"
        assert critiques[0]["severity"] == "high", "First critique should be high severity"

        evo.backtrack("strat_direct", "Direct approach insufficient")

        new_sid = mind.propose_backtrack(
            "strat_direct",
            "Direct factorization cannot prove uniqueness",
            "Use modular arithmetic: if p != 3 mod 3 then p^2 ≡ 1 mod 3 => p^2+2 ≡ 0 mod 3",
            new_priority=2
        )
        assert new_sid == "strat_backtrack_strat_direct", f"Backtrack strategy name mismatch: {new_sid}"

        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy(strat_backtrack" in c, "Backtrack strategy should be in KB"
    finally:
        cleanup(kb)

test("backtrack_flow", test_backtrack_flow)

# ===== TestEvoHelpers =====
print("\n--- TestEvoHelpers ---")

def test_should_check_for_new_strategies():
    kb = make_kb()
    try:
        evo = EvoKBAdapter(kb)
        assert evo.should_check_for_new_strategies("cannot prove the statement") is True
        assert evo.should_check_for_new_strategies("The answer is 42.") is False
        assert evo.should_check_for_new_strategies("no solution found") is True
        assert evo.should_check_for_new_strategies("") is False
        assert evo.should_check_for_new_strategies("failed to verify") is True
        assert evo.should_check_for_new_strategies("insufficient evidence") is True
    finally:
        cleanup(kb)

test("should_check_for_new_strategies", test_should_check_for_new_strategies)

# ===== TestEdgeCases =====
print("\n--- TestEdgeCases ---")

def test_retractall_removes_facts():
    kb = make_kb()
    try:
        kb.asserta("critique_gap(s1, 'gap1', high, 'fix1').")
        kb.asserta("critique_gap(s1, 'gap2', medium, 'fix2').")
        kb.asserta("propose_strategy(s1, 'p', 'd', 1).")

        old = kb.retractall("critique_gap")
        assert "gap1" in old, f"gap1 should be in returned old content: {old}"
        assert "gap2" in old, f"gap2 should be in returned old content: {old}"

        with open(kb.path) as f:
            c = f.read()
        assert "next_strategy(" in c, "Helper predicates preserved"
        assert "propose_strategy(s1" in c, "Other predicates preserved"
        assert "critique_gap" not in c, "Critique_gap facts removed"
    finally:
        cleanup(kb)

test("retractall_removes_facts", test_retractall_removes_facts)

def test_empty_kb_query_does_not_crash():
    kb = make_kb()
    try:
        r = kb.query("findall(X, propose_strategy(X, _, _, _), L)")
        assert r is not None, "Query should not crash"
    finally:
        cleanup(kb)

test("empty_kb_query_does_not_crash", test_empty_kb_query_does_not_crash)

def test_unicode_in_facts():
    e = _esc("x² + y² = z² (Pythagorean)")
    assert e is not None, "Unicode should be handled"
    assert len(e) > 0

test("unicode_in_facts", test_unicode_in_facts)

def test_long_fact_truncation():
    e = _esc("A" * 1000)
    assert "[...truncated]" in e, f"Long strings should be truncated: {len(e)} chars"
    assert len(e) < 600, f"Escaped string should be < 600 chars, got {len(e)}"

test("long_fact_truncation", test_long_fact_truncation)

# ===== Summary =====
print("\n" + "=" * 65)
total = passed + failed
print(f"RESULTS: {passed} passed, {failed} failed out of {total} tests")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"{failed} TEST(S) FAILED!")
sys.exit(0 if failed == 0 else 1)
