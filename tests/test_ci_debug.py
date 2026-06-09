#!/usr/bin/env python3
"""CI debug - incremental test."""
import os, sys, tempfile, hashlib, time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pr1_mind.shared_kb import SharedKB, _esc
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter

passed=0; failed=0
PROBLEM = "Find all primes p such that p^2 + 2 is also prime."

def cleanup(kb):
    try:
        if os.path.exists(kb.path): os.unlink(kb.path)
    except OSError: pass

def make_kb():
    return SharedKB(storage_tag=f"test_{os.urandom(4).hex()}")

def t(name, fn):
    global passed, failed
    try:
        fn(); passed+=1; print(f"  PASS: {name}")
    except Exception as e:
        failed+=1; print(f"  FAIL: {name}: {e}")

print("="*65)
print("CI Debug Tests")
print("="*65)

# Test 1: basic init
print("\n--- Basic Init ---")
def test1():
    kb = make_kb()
    try:
        assert os.path.exists(kb.path)
        with open(kb.path) as f: c = f.read()
        assert "propose_strategy/4" in c
    finally: cleanup(kb)
t("init", test1)

# Test 2: propose + read
print("\n--- Propose ---")
def test2():
    kb = make_kb()
    try:
        kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
        with open(kb.path) as f: c = f.read()
        assert "propose_strategy(s1" in c
    finally: cleanup(kb)
t("propose", test2)

# Test 3: result
def test3():
    kb = make_kb()
    try:
        kb.propose_strategy("s1", "P", "desc", 5)
        kb.asserta("strategy_result(s1, in_progress, 'claimed')")
        kb.report_strategy_result("s1", "succeeded", "Done")
        with open(kb.path) as f: c = f.read()
        assert "succeeded" in c
    finally: cleanup(kb)
t("result", test3)

# Test 4: classify_and_propose
def test4():
    kb = make_kb()
    try:
        m = MindKBAdapter(kb)
        proposed = m.classify_and_propose(PROBLEM)
        assert len(proposed) > 0
        assert "strat_0001" in proposed
    finally: cleanup(kb)
t("classify", test4)

# Test 5: trace writing
def test5():
    kb = make_kb()
    try:
        m = MindKBAdapter(kb)
        e = EvoKBAdapter(kb)
        proposed = m.classify_and_propose(PROBLEM)
        claimed = proposed[0]
        # Simulate claiming
        kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
        kb.asserta(f"active_strategy({claimed})")
        e.begin_strategy(claimed)
        e.write_trace("REASON", "test", "derived")
        with open(kb.path) as f: c = f.read()
        assert "trace(" in c
        traces = m.read_traces()
        assert len(traces) > 0
    finally: cleanup(kb)
t("traces", test5)

# Test 6: critique
def test6():
    kb = make_kb()
    try:
        m = MindKBAdapter(kb)
        e = EvoKBAdapter(kb)
        proposed = m.classify_and_propose(PROBLEM)
        claimed = proposed[0]
        kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
        kb.asserta(f"active_strategy({claimed})")
        e.begin_strategy(claimed)
        e.write_trace("REASON", "test", "derived")
        e.complete_strategy(claimed, "succeeded", "Found p=3")
        m.critique_strategy(claimed, gap="test gap", severity="low", suggestion="fix")
        critiques = e.check_for_critiques(claimed)
        assert len(critiques) > 0
    finally: cleanup(kb)
t("critique", test6)

# Test 7: backtrack
def test7():
    kb = make_kb()
    try:
        m = MindKBAdapter(kb)
        e = EvoKBAdapter(kb)
        m.propose_custom_strategy("strat_direct", PROBLEM, "factorization", priority=2)
        e._current_strategy = "strat_direct"; e._current_turn = 0
        kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")
        e.write_trace("REASON", "failed", "failed", "No factorization")
        m.critique_strategy("strat_direct", gap="Cannot prove", severity="high", suggestion="Switch")
        e.backtrack("strat_direct", "critique received")
        with open(kb.path) as f: c = f.read()
        assert "needs_critique" in c
    finally: cleanup(kb)
t("backtrack", test7)

print()
total = passed + failed
print(f"{'='*65}")
print(f"Results: {passed}/{total} passed")
if failed: print(f"FAILURES: {failed}")
else: print("All tests passed.")
sys.exit(0 if failed == 0 else 1)
