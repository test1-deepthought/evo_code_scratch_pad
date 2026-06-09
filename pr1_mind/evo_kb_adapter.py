from pr1_mind.shared_kb import SharedKB, _esc


class EvoKBAdapter:
    """EvoAgent-side adapter for the Shared KB protocol."""

    def __init__(self, kb: SharedKB):
        self._kb = kb
        self._current_strategy = None
        self._current_turn = 0

    def begin_strategy(self, sid: str) -> None:
        self._current_strategy = sid
        self._current_turn = 0

    def write_trace(self, layer: str, goal: str, status: str, detail: str = "") -> None:
        self._current_turn += 1
        self._kb.write_trace(self._current_turn, layer, goal, status, detail)

    def complete_strategy(self, sid: str, status: str, detail: str = "") -> None:
        self._kb.report_strategy_result(sid, status, detail)

    def check_for_critiques(self, sid: str):
        result = self._kb.read_critiques(sid)
        parsed = []
        if result:
            for line in result.split("\n"):
                if "-" in line and len(line.strip()) > 5:
                    parts = line.strip().split("-", 2)
                    sev = parts[0].strip() if len(parts) > 0 else "unknown"
                    gap = parts[1].strip() if len(parts) > 1 else ""
                    sug = parts[2].strip() if len(parts) > 2 else ""
                    parsed.append({"severity": sev, "gap": gap, "suggestion": sug})
        return parsed

    def backtrack(self, old_sid: str, reason: str) -> None:
        self._kb.asserta(f"backtrack_event({_esc(old_sid)}, {_esc(reason)})")
        self._kb._log_event(old_sid, "backtracked", reason)
        self._current_strategy = None

    def should_check_for_new_strategies(self, latest_result: str) -> bool:
        indicator_words = ["cannot prove", "no solution found", "failed", "insufficient"]
        if not latest_result:
            return False
        lower = latest_result.lower()
        for word in indicator_words:
            if word in lower:
                return True
        return False

    def record_verification(self, name: str, code: str) -> None:
        self._kb.record_verification(name, code)
