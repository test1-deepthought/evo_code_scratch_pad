from typing import Optional
from pr1_mind.shared_kb import SharedKB

class MindKBAdapter:
    """Mind-side adapter for the Shared KB Protocol."""
    def __init__(self, kb: SharedKB):
        self._kb = kb

    def classify_and_propose(self, problem_text: str) -> list[str]:
        strategies = self._generate_strategies(problem_text)
        proposed = []
        for i, (desc, priority) in enumerate(strategies, 1):
            sid = f"strat_{i:04d}"
            self._kb.propose_strategy(sid, problem_text[:100], desc, priority)
            proposed.append(sid)
        return proposed

    def propose_custom_strategy(self, sid: str, problem: str, desc: str, priority: int = 5) -> None:
        self._kb.propose_strategy(sid, problem, desc, priority)

    def read_traces(self) -> str:
        return self._kb.read_traces()

    def read_traces_for_turn(self, turn: int) -> str:
        return self._kb.read_traces(turn)

    def critique_strategy(self, sid: str, gap: str, severity: str = "medium", suggestion: str = "") -> None:
        self._kb.write_critique(sid, gap, severity, suggestion)

    def propose_backtrack(self, sid: str, reason: str, new_desc: str, new_priority: int = 6) -> Optional[str]:
        self._kb.write_critique(sid, reason, "high", f"Backtrack: {new_desc[:100]}")
        self._kb.report_strategy_result(sid, "failed", f"critique-triggered backtrack: {reason[:100]}")
        new_sid = f"strat_backtrack_{sid}"
        self._kb.propose_strategy(new_sid, "", new_desc, new_priority)
        return new_sid

    @staticmethod
    def _generate_strategies(text: str) -> list[tuple[str, int]]:
        lower = text.lower()
        strategies = []
        if "prove" in lower or "show" in lower:
            strategies.append(("Attempt direct algebraic manipulation or known identity", 3))
            strategies.append(("Try proof by contradiction or contrapositive", 4))
        if "find all" in lower or "determine all" in lower:
            strategies.append(("Search small cases and look for a pattern", 2))
            strategies.append(("Use invariant or modular arithmetic to constrain search", 3))
        if any(kw in lower for kw in ("prime", "divisible", "mod", "gcd", "lcm")):
            strategies.append(("Apply number theory: modular arithmetic, factorisation", 2))
            strategies.append(("Try infinite descent or minimal counterexample", 4))
        if any(kw in lower for kw in ("inequality", "sum", "function")):
            strategies.append(("Try AM-GM, Cauchy-Schwarz, or Jensen's inequality", 3))
            strategies.append(("Use substitution or homogenisation", 5))
        if any(kw in lower for kw in ("triangle", "circle", "geometry", "angle")):
            strategies.append(("Use coordinate geometry or vector methods", 3))
            strategies.append(("Apply known geometry lemmas", 4))
        if any(kw in lower for kw in ("polynomial", "equation", "root")):
            strategies.append(("Factorise using known roots or Vieta's formulas", 3))
            strategies.append(("Analyse degree and leading coefficients", 5))
        if not strategies:
            strategies.append(("Formalise the problem in Prolog and derive conclusions", 3))
            strategies.append(("Search for similar solved problems", 5))
        return strategies
