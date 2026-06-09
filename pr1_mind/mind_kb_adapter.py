from pr1_mind.shared_kb import SharedKB, _esc


class MindKBAdapter:
    """Mind-side adapter for the Shared KB protocol."""

    def __init__(self, kb: SharedKB):
        self._kb = kb

    def classify_and_propose(self, problem: str):
        """Analyze problem and propose strategies."""
        strategies = {
            "strategy 1: direct proof": "Try direct factorization and primality testing",
            "strategy 2: modular arithmetic": "Use modular arithmetic mod 3",
            "strategy 3: brute force search": "Search small cases for pattern",
        }
        proposed = []
        for i, (name, desc) in enumerate(strategies.items(), 1):
            sid = f"strat_{i:04d}"
            priority = 6 - i
            self._kb.propose_strategy(sid, problem, f"{name}: {desc}", priority=priority)
            proposed.append(sid)
        return proposed

    def propose_custom_strategy(self, sid: str, problem: str, description: str, priority: int = 5) -> None:
        self._kb.propose_strategy(sid, problem, description, priority=priority)

    def read_traces(self):
        return self._kb.read_traces()

    def critique_strategy(self, sid: str, gap: str, severity: str = "medium", suggestion: str = "") -> None:
        self._kb.write_critique(sid, gap=gap, severity=severity, suggestion=suggestion)

    def propose_backtrack(self, old_sid: str, reason: str, new_desc: str, new_priority: int = 5) -> str:
        new_sid = f"strat_backtrack_{old_sid}"
        self._kb.propose_strategy(new_sid, reason, new_desc, priority=new_priority)
        return new_sid
