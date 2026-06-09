#!/usr/bin/env python3
import os
import sys
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
print("\n--- TestSharedKBCore ---")
def test_init_creates_header():
    kb = make_kb()
    try:
        assert os.path.exists(kb.path)
        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy/4" in c
        assert "next_strategy(" in c
    finally:
        cleanup(kb)
test("init_creates_header", test_init_creates_header)
def test_ensure_period():
    assert SharedKB._ensure_period("fact(a)") == "fact(a)."
    assert SharedKB._ensure_period("fact(a).") == "fact(a)."
test("ensure_period", test_ensure_period)
def test_esc_handles_special_chars():
    r = _esc("it's a \"test\"\nwith newline")
    assert "\\'" in r
    assert "\\n" in r
test("esc_handles_special_chars", test_esc_handles_special_chars)
print("\n--- TestStrategyLayer ---")
def test_mind_proposes_strategies():
    kb = make_kb()
    try:
        kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
        kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy(s1" in c
        assert "propose_strategy(s2" in c
        assert "strategy_log(s1" in c
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
print("\n--- TestCriticLoop ---")
PROBLEM = "Find all primes p such that p^2 + 2 is also prime."
def test_full_critic_loop():
    kb = make_kb()
    try:
        mind = MindKBAdapter(kb)
        evo = EvoKBAdapter(kb)
        proposed = mind.classify_and_propose(PROBLEM)
        assert len(proposed) > 0
        assert "strat_0001" in proposed
        claimed = proposed[0]
        kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
        kb.asserta(f"active_strategy({claimed})")
        evo.begin_strategy(claimed)
        evo.write_trace("REASON", "problem_spec(...)", "derived")
        evo.write_trace("COMPUTE", "python_exec: test p=2,3,5,7,11...", "derived")
        evo.write_trace("PROVE", "lean4_exec: theorem ...", "derived")
        evo.complete_strategy(claimed, "succeeded", "Found p=3")
        traces = mind.read_traces()
        assert len(traces) > 0
        mind.critique_strategy(claimed, gap="Missing explicit p=3 case", severity="low", suggestion="Add verification that 3^2+2=11 is prime")
        critiques = evo.check_for_critiques(claimed)
        assert len(critiques) > 0
        kb.record_verification("prime_p_sq_plus_two", "theorem ... := ...")
        with open(kb.path) as f:
            c = f.read()
        assert "strategy_log(" in c
        assert "proposed" in c
        assert "selected" in c
    finally:
        cleanup(kb)
test("full_critic_loop", test_full_critic_loop)
def test_backtrack_flow():
    kb = make_kb()
    try:
        mind = MindKBAdapter(kb)
        evo = EvoKBAdapter(kb)
        mind.propose_custom_strategy("strat_direct", PROBLEM, "Attempt direct factorization", priority=2)
        mind.propose_custom_strategy("strat_modular", PROBLEM, "Use modular arithmetic mod 3", priority=3)
        evo._current_strategy = "strat_direct"
        evo._current_turn = 0
        kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")
        evo.write_trace("REASON", "direct_factorization_impossible", "failed", "No algebraic factorization found")
        mind.critique_strategy("strat_direct", gap="Cannot prove uniqueness", severity="high", suggestion="Switch to modular arithmetic")
        assert evo.has_open_critique("strat_direct")
        evo.backtrack("strat_direct", "high-severity critique received")
        with open(kb.path) as f:
            c = f.read()
        assert "needs_critique" in c
    finally:
        cleanup(kb)
test("backtrack_flow", test_backtrack_flow)
print()
total = passed + failed
print(f"{'=' * 65}")
print(f"Results: {passed}/{total} passed")
if failed:
    print(f"FAILURES: {failed}")
else:
    print("All tests passed.")
sys.exit(0 if failed == 0 else 1)
