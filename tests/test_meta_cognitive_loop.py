"""
Tests for NOVA's meta-cognitive loop module.
"""
import pytest
from nova.meta_cognitive_loop import (
    MetaCognitiveLoop, GateType, GateViolation, MetaCognitiveState,
    create_default_loop,
)


class TestMetaCognitiveLoop:
    """Test the self-healing meta-cognitive loop."""

    def test_create_default_loop(self):
        """Default loop should have repair handlers for common gates."""
        loop = create_default_loop()
        assert loop.state.max_repair_attempts == 3

    def test_record_violation(self):
        """Violations should be recorded."""
        loop = MetaCognitiveLoop()
        violation = loop.record_violation(
            GateType.CONSISTENCY, "KB not checked for consistency"
        )
        assert violation.gate == GateType.CONSISTENCY
        assert len(loop.state.violations) == 1

    def test_attempt_repair(self):
        """Repair should return a repair instruction string."""
        loop = create_default_loop()
        loop.record_violation(
            GateType.CONSISTENCY, "KB not checked for consistency"
        )
        repair = loop.attempt_repair()
        assert repair is not None
        assert "META-REPAIR" in repair

    def test_repair_exhausted(self):
        """After max attempts, repair should return None."""
        loop = MetaCognitiveLoop(max_repairs=1)
        loop.record_violation(GateType.CONSISTENCY, "test")
        loop.attempt_repair()  # First attempt
        repair = loop.attempt_repair()  # Should be exhausted
        assert repair is None

    def test_stuck_pattern_detection(self):
        """Same gate 3+ times should trigger stuck pattern."""
        loop = create_default_loop()
        for _ in range(4):
            loop.record_violation(GateType.CONSISTENCY, "test")
        assert loop.state.stuck_pattern

    def test_stuck_pattern_stops_repairs(self):
        """Stuck pattern should prevent further repairs."""
        loop = create_default_loop()
        for _ in range(4):
            loop.record_violation(GateType.CONSISTENCY, "test")
        repair = loop.attempt_repair()
        assert repair is None

    def test_reset(self):
        """Reset should clear all state."""
        loop = create_default_loop()
        loop.record_violation(GateType.CONSISTENCY, "test")
        loop.reset()
        assert len(loop.state.violations) == 0
        assert loop.state.repair_attempts == 0

    def test_get_summary_no_violations(self):
        """Summary should show no violations when none recorded."""
        loop = MetaCognitiveLoop()
        summary = loop.get_summary()
        assert "no violations" in summary

    def test_get_summary_with_violations(self):
        """Summary should list recorded violations."""
        loop = create_default_loop()
        loop.record_violation(GateType.CONSISTENCY, "KB not checked")
        loop.record_violation(GateType.LATEX, "Bare command")
        summary = loop.get_summary()
        assert "2 violation(s)" in summary
        assert "CONSISTENCY" in summary
        assert "LATEX" in summary

    def test_run(self):
        """run() should attempt all possible repairs."""
        loop = create_default_loop()
        loop.record_violation(GateType.CONSISTENCY, "test")
        loop.record_violation(GateType.LATEX, "test")
        actions = loop.run()
        assert len(actions) >= 1

    def test_tick(self):
        """tick() should return one repair action at a time."""
        loop = create_default_loop()
        loop.record_violation(GateType.CONSISTENCY, "test")
        action = loop.tick()
        assert action is not None
        action2 = loop.tick()  # No more repairable violations
        assert action2 is None

    def test_check_and_repair_passes(self):
        """check_and_repair should return None when condition is met."""
        loop = create_default_loop()
        result = loop.check_and_repair(GateType.CONSISTENCY, condition_met=True,
                                        description="All good")
        assert result is None

    def test_check_and_repair_fails(self):
        """check_and_repair should auto-repair when condition fails."""
        loop = create_default_loop()
        result = loop.check_and_repair(GateType.CONSISTENCY, condition_met=False,
                                        description="Missing check")
        assert result is not None
        assert "META-REPAIR" in result

    def test_prolog_first_handler(self):
        """Prolog first repair should include code block."""
        from nova.meta_cognitive_loop import _repair_prolog_first
        violation = GateViolation(GateType.PROLOG_FIRST, "", "")
        repair = _repair_prolog_first(violation)
        assert repair is not None
        assert "prolog_exec" in repair
        assert "```prolog" in repair

    def test_latex_handler(self):
        """LaTeX repair should mention delimiters."""
        from nova.meta_cognitive_loop import _repair_latex
        violation = GateViolation(GateType.LATEX, "", "")
        repair = _repair_latex(violation)
        assert "\\\\" in repair or "$" in repair
