import logging
from typing import Optional

from mind.shared_kb import SharedKB

logger = logging.getLogger("evo-kb-adapter")


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
            logger.info("Claimed strategy: %s", sid)
        return sid

    def begin_strategy(self, strategy_id: str) -> None:
        self._current_strategy = strategy_id
        self._current_turn = 0
        self._kb.report_strategy_result(strategy_id, "in_progress")
        logger.info("Beginning strategy: %s", strategy_id)

    def complete_strategy(
        self, strategy_id: str, status: str = "succeeded",
        detail: str = ""
    ) -> None:
        self._kb.report_strategy_result(strategy_id, status, detail)
        if strategy_id == self._current_strategy:
            self._current_strategy = None
        logger.info("Strategy %s completed with status: %s", strategy_id, status)

    def write_trace(
        self, layer: str, goal: str, status: str = "derived",
        detail: str = ""
    ) -> None:
        self._current_turn += 1
        self._kb.write_trace(
            self._current_turn, layer, goal, status, detail
        )

    def check_for_critiques(self, strategy_id: Optional[str] = None) -> list[dict]:
        sid = strategy_id or self._current_strategy
        if not sid:
            return []
        result = self._kb.read_critiques(sid)
        return self._parse_critique_result(result)

    def has_open_critique(self, strategy_id: Optional[str] = None) -> bool:
        sid = strategy_id or self._current_strategy
        if not sid:
            return False
        result = self._kb.query(
            f"has_open_critique({_esc_q(sid)})"
        )
        return "true" in result.lower() or "Query result:\ntrue" in result

    def backtrack(
        self, strategy_id: str, reason: str = "critique received"
    ) -> None:
        self._kb.report_strategy_result(
            strategy_id, "needs_critique", reason
        )
        if strategy_id == self._current_strategy:
            self._current_strategy = None
        logger.info("Backtrack requested for %s: %s", strategy_id, reason)

    def should_check_for_new_strategies(self, result: str) -> bool:
        if not result:
            return False
        lower = result.lower()
        dead_end_indicators = [
            "cannot prove", "failed to derive", "contradiction",
            "no solution found", "exhausted", "dead end",
            "incomplete", "stuck", "unsolved goals",
        ]
        return any(indicator in lower for indicator in dead_end_indicators)

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
    s = s.replace("'", "\\'")
    return f"'{s}'"
