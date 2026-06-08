from typing import Optional
from pr1_mind.shared_kb import SharedKB

class EvoKBAdapter:
    """EvoAgent-side adapter for the Shared KB Protocol."""
    def __init__(self, kb: SharedKB):
        self._kb = kb
        self._current_strategy: Optional[str] = None
        self._current_turn: int = 0

    def claim_next_strategy(self) -> Optional[str]:
        sid = self._kb.claim_strategy()
        if sid:
            self._current_strategy = sid
            self._current_turn = 0
        return sid

    def begin_strategy(self, sid: str) -> None:
        self._current_strategy = sid
        self._current_turn = 0
        self._kb.report_strategy_result(sid, "in_progress")

    def complete_strategy(self, sid: str, status: str = "succeeded", detail: str = "") -> None:
        self._kb.report_strategy_result(sid, status, detail)
        if sid == self._current_strategy:
            self._current_strategy = None

    def write_trace(self, layer: str, goal: str, status: str = "derived", detail: str = "") -> None:
        self._current_turn += 1
        self._kb.write_trace(self._current_turn, layer, goal, status, detail)

    def check_for_critiques(self, sid: Optional[str] = None) -> list[dict]:
        sid = sid or self._current_strategy
        if not sid:
            return []
        return self._parse_critique_result(self._kb.read_critiques(sid))

    def has_open_critique(self, sid: Optional[str] = None) -> bool:
        sid = sid or self._current_strategy
        if not sid:
            return False
        r = self._kb.query(f"has_open_critique({_esc_q(sid)})")
        return "true" in r.lower() or "Query result:\ntrue" in r

    def backtrack(self, sid: str, reason: str = "critique received") -> None:
        self._kb.report_strategy_result(sid, "needs_critique", reason)
        if sid == self._current_strategy:
            self._current_strategy = None

    def should_check_for_new_strategies(self, result: str) -> bool:
        if not result:
            return False
        lower = result.lower()
        indicators = ["cannot prove", "failed to derive", "contradiction",
                      "no solution found", "exhausted", "dead end",
                      "incomplete", "stuck", "unsolved goals"]
        return any(i in lower for i in indicators)

    @staticmethod
    def _parse_critique_result(result: str) -> list[dict]:
        critiques = []
        for line in (result or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("Query") or line == "true":
                continue
            parts = line.split("-", 2)
            if len(parts) >= 1:
                critiques.append({
                    "severity": parts[0].strip().strip("'\""),
                    "gap": parts[1].strip().strip("'\"") if len(parts) > 1 else "",
                    "suggestion": parts[2].strip().strip("'\"") if len(parts) > 2 else "",
                })
        return critiques


def _esc_q(s: str) -> str:
    return f"'{s.replace(chr(39), chr(92) + chr(39))}'"
