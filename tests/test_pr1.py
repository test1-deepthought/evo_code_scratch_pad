import os
import pytest
from pr1_mind.shared_kb import SharedKB
from pr1_mind.mind_kb_adapter import MindKBAdapter
from pr1_mind.evo_kb_adapter import EvoKBAdapter


@pytest.fixture
def kb():
    tag = f"tst_{os.urandom(4).hex()}"
    k = SharedKB(storage_tag=tag)
    yield k
    try:
        if os.path.exists(k.path):
            os.unlink(k.path)
    except OSError:
        pass


@pytest.fixture
def mind(kb):
    return MindKBAdapter(kb)


@pytest.fixture
def evo(kb):
    return EvoKBAdapter(kb)


class TestSharedKBCore:
    def test_init_creates_header(self, kb):
        assert os.path.exists(kb.path)
        with open(kb.path) as f:
            c = f.read()
        assert "propose_strategy/4" in c
        assert "next_strategy(" in c

    def test_ensure_period(self):
        assert SharedKB._ensure_period("fact(a)") == "fact(a)."
        assert SharedKB._ensure_period("fact(a).") == "fact(a)."

    def test_esc_handles_special_chars(self):
        from pr1_mind.shared_kb import _esc
        r = _esc("it's a \"test\"\nwith newline")
        assert "\\'" in r
        assert "\\n" in r


class TestStrategyLayer:
    def test_mind_proposes_strategies(self, kb):
        kb.propose_strategy("s1", "Problem A", "Try direct proof", priority=2)
        kb.propose_strategy("s2", "Problem A", "Try contradiction", priority=4)
        with open(kb.path) as f:
            c = f.read()
        assert 'propose_strategy(s1' in c
        assert 'propose_strategy(s2' in c
        assert 'strategy_log(s1' in c

    def test_strategy_result_propagation(self, kb):
        kb.propose_strategy("s1", "Problem", "Test", priority=5)
        kb.asserta("strategy_result(s1, in_progress, 'claimed')")
        kb.report_strategy_result("s1", "succeeded", "Done")
        with open(kb.path) as f:
            c = f.read()
        assert 'strategy_result(s1' in c
        assert 'succeeded' in c


class TestCriticLoop:
    PROBLEM = "Find all primes p such that p^2 + 2 is also prime."

    def test_full_critic_loop(self, kb, mind, evo):
        proposed = mind.classify_and_propose(self.PROBLEM)
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

        mind.critique_strategy(claimed, gap="Missing explicit p=3 case", severity="low",
                               suggestion="Add verification that 3^2+2=11 is prime")
        critiques = evo.check_for_critiques(claimed)
        assert len(critiques) > 0

        kb.record_verification("prime_p_sq_plus_two", "theorem ... := ...")
        with open(kb.path) as f:
            c = f.read()
        assert "strategy_log(" in c
        assert "proposed" in c
        assert "selected" in c

    def test_backtrack_flow(self, kb, mind, evo):
        mind.propose_custom_strategy("strat_direct", self.PROBLEM,
                                     "Attempt direct factorisation", priority=2)
        mind.propose_custom_strategy("strat_modular", self.PROBLEM,
                                     "Use modular arithmetic mod 3", priority=3)

        evo._current_strategy = "strat_direct"
        evo._current_turn = 0
        kb.asserta("strategy_result(strat_direct, in_progress, 'claimed')")

        evo.write_trace("REASON", "conclusion(direct_factorisation_impossible)", "failed",
                        "No algebraic factorisation found")
        evo.write_trace("COMPUTE", "python_exec: test p=2..100", "derived",
                        "Only p=3 works but no proof")

        mind.critique_strategy("strat_direct",
                               gap="Cannot prove uniqueness",
                               severity="high",
                               suggestion="Switch to modular arithmetic mod 3")
        critiques = evo.check_for_critiques("strat_direct")
        assert len(critiques) > 0
        assert critiques[0]["severity"] == "high"

        evo.backtrack("strat_direct", "Direct approach insufficient")

        new_sid = mind.propose_backtrack(
            "strat_direct",
            "Direct factorisation cannot prove uniqueness",
            "Use modular arithmetic: if p != 3 mod 3 then p^2 \u2261 1 mod 3 => p^2+2 \u2261 0 mod 3",
            new_priority=2
        )
        assert new_sid == "strat_backtrack_strat_direct"
        with open(kb.path) as f:
            c = f.read()
        assert 'propose_strategy(strat_backtrack' in c


class TestEvoHelpers:
    def test_should_check_for_new_strategies(self, evo):
        assert evo.should_check_for_new_strategies("cannot prove the statement") is True
        assert evo.should_check_for_new_strategies("The answer is 42.") is False
        assert evo.should_check_for_new_strategies("no solution found") is True
        assert evo.should_check_for_new_strategies("") is False


class TestEdgeCases:
    def test_retractall_removes_facts(self, kb):
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

    def test_empty_kb_query_does_not_crash(self, kb):
        r = kb.query("findall(X, propose_strategy(X, _, _, _), L)")
        assert r is not None

    def test_unicode_in_facts(self):
        from pr1_mind.shared_kb import _esc
        e = _esc("x\u00b2 + y\u00b2 = z\u00b2")
        assert "\u00b2" in e or "\\\\" in e

    def test_long_fact_truncation(self):
        from pr1_mind.shared_kb import _esc
        e = _esc("A" * 1000)
        assert "[...truncated]" in e
        assert len(e) < 600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
