import os
import sys

_SKIP_SWIPL = os.environ.get("SWIPL_PATH") is None

import pytest

from mind.shared_kb import SharedKB
from mind.mind_kb_adapter import MindKBAdapter
from mind.evo_kb_adapter import EvoKBAdapter


@pytest.fixture
def shared_kb():
    tag = f"test_{os.urandom(4).hex()}"
    kb = SharedKB(storage_tag=tag)
    yield kb
    try:
        if os.path.exists(kb.path):
            os.unlink(kb.path)
    except OSError:
        pass


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
        from mind.shared_kb import _esc
        result = _esc("it's a \"test\"\nwith newline")
        assert "\\'" in result
        assert "\\n" in result


class TestStrategyLayer:
    def test_mind_proposes_strategies(self, shared_kb):
        kb = shared_kb
        kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
        kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
        with open(kb.path) as f:
            content = f.read()
        assert 'propose_strategy(s1' in content
        assert 'propose_strategy(s2' in content
        assert 'strategy_log(s1' in content

    def test_strategy_result_propagation(self, shared_kb):
        kb = shared_kb
        kb.propose_strategy("s1", "Problem", "Test strategy", priority=5)
        kb.asserta("strategy_result(s1, in_progress, 'claimed')")
        kb.report_strategy_result("s1", "succeeded", "All derivations completed")
        with open(kb.path) as f:
            content = f.read()
        assert 'strategy_result(s1' in content
        assert 'succeeded' in content


class TestCriticLoop:
    PROBLEM = "Find all primes p such that p^2 + 2 is also prime."

    def test_full_critic_loop(self, shared_kb, mind_adapter, evo_adapter):
        kb = shared_kb

        proposed = mind_adapter.classify_and_propose(self.PROBLEM)
        assert len(proposed) > 0
        assert "strat_0001" in proposed

        claimed = proposed[0]
        kb.asserta(f"strategy_result({claimed}, in_progress, 'claimed')")
        kb.asserta(f"active_strategy({claimed})")

        evo_adapter.begin_strategy(claimed)
        evo_adapter.write_trace("REASON", "problem_spec(...)", "derived")
        evo_adapter.write_trace("COMPUTE", "python_exec: test p=2,3,5,7,11...", "derived", "p=2 -> 6 not prime")
        evo_adapter.write_trace("PROVE", "lean4_exec: theorem only_p_equals_3", "derived", "Verified p=3 works")
        evo_adapter.complete_strategy(claimed, "succeeded", "Found p=3 as the only solution")

        traces = mind_adapter.read_traces()
        assert len(traces) > 0

        mind_adapter.critique_strategy(
            claimed,
            gap="Did not consider p=3 case explicitly for p^2+2 primality",
            severity="low",
            suggestion="Add explicit verification that 3^2+2=11 is prime"
        )

        critiques = evo_adapter.check_for_critiques(claimed)
        assert len(critiques) > 0

        kb.record_verification("only_prime_p_squared_plus_two", "theorem ... := by ...")

        with open(kb.path) as f:
            content = f.read()
        assert "strategy_log(" in content
        assert "proposed" in content
        assert "selected" in content
        assert "completed" in content

    def test_backtrack_flow(self, shared_kb, mind_adapter, evo_adapter):
        kb = shared_kb

        mind_adapter.propose_custom_strategy(
            "strat_direct", self.PROBLEM,
            "Attempt direct algebraic factorisation", priority=2
        )
        mind_adapter.propose_custom_strategy(
            "strat_modular", self.PROBLEM,
            "Use modular arithmetic mod 3", priority=3
        )

        evo_adapter._current_strategy = "strat_direct"
        evo_adapter._current_turn = 0
        kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")

        evo_adapter.write_trace("REASON", "conclusion(direct_factorisation_impossible)", "failed",
                                "No algebraic factorisation found for p^2+2")
        evo_adapter.write_trace("COMPUTE", "python_exec: test p=2..100", "derived",
                                "Only p=3 works but no proof")

        mind_adapter.critique_strategy(
            "strat_direct",
            gap="Direct factorisation cannot prove uniqueness",
            severity="high",
            suggestion="Switch to modular arithmetic approach mod 3"
        )

        critiques = evo_adapter.check_for_critiques("strat_direct")
        assert len(critiques) > 0
        assert critiques[0]["severity"] == "high"

        evo_adapter.backtrack("strat_direct", "Direct approach insufficient per Mind critique")

        new_sid = mind_adapter.propose_backtrack(
            "strat_direct",
            "Direct factorisation cannot prove uniqueness without infinite descent",
            "Use modular arithmetic: if p != 3 mod 3 then p^2 ≡ 1 mod 3 so p^2+2 ≡ 0 mod 3",
            new_priority=2
        )
        assert new_sid == "strat_backtrack_strat_direct"

        with open(kb.path) as f:
            content = f.read()
        assert 'propose_strategy(strat_backtrack' in content


class TestEvoIntegrationHelpers:
    def test_should_check_for_new_strategies(self, evo_adapter):
        assert evo_adapter.should_check_for_new_strategies("cannot prove the statement") is True
        assert evo_adapter.should_check_for_new_strategies("The answer is 42.") is False
        assert evo_adapter.should_check_for_new_strategies("no solution found in the search space") is True
        assert evo_adapter.should_check_for_new_strategies("") is False


class TestEdgeCases:
    def test_retractall_removes_facts(self, shared_kb):
        kb = shared_kb
        kb.asserta("critique_gap(s1, 'gap1', high, 'fix1').")
        kb.asserta("critique_gap(s1, 'gap2', medium, 'fix2').")
        kb.asserta("propose_strategy(s1, 'p', 'd', 1).")

        old = kb.retractall("critique_gap")
        assert "gap1" in old
        assert "gap2" in old

        with open(kb.path) as f:
            content = f.read()
        assert "next_strategy(" in content
        assert "propose_strategy(s1" in content
        assert "critique_gap" not in content

    def test_empty_kb_query_does_not_crash(self, shared_kb):
        result = shared_kb.query("findall(X, propose_strategy(X, _, _, _), L)")
        assert result is not None

    def test_unicode_in_facts(self, shared_kb):
        from mind.shared_kb import _esc
        escaped = _esc("x² + y² = z² (Pythagorean)")
        assert "²" in escaped or "\\\\" in escaped

    def test_long_fact_truncation(self, shared_kb):
        from mind.shared_kb import _esc
        long_str = "A" * 1000
        escaped = _esc(long_str)
        assert "[...truncated]" in escaped
        assert len(escaped) < 600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
