import hashlib
import logging
import os
import tempfile
import time
from typing import Optional

logger = logging.getLogger("shared-kb")

_SHARED_KB_HELPERS = r'''
:- dynamic propose_strategy/4.
:- dynamic active_strategy/1.
:- dynamic strategy_result/3.
:- dynamic strategy_log/4.
:- dynamic trace/5.
:- dynamic critique_gap/4.
:- dynamic verified/2.

strategies_by_priority(Strategies) :-
    findall(Prio-Strats, propose_strategy(Strats, _, _, Prio), Pairs),
    sort(Pairs, Sorted),
    findall(Strat, member(_-Strat, Sorted), Strategies).

next_strategy(StrategyId) :-
    strategies_by_priority([StrategyId|_]),
    \\+ strategy_result(StrategyId, _, _).

traces_for_turn(Turn, Traces) :-
    findall(Layer-Goal-Status-Detail, trace(Turn, Layer, Goal, Status, Detail), Traces).

has_open_critique(StrategyId) :-
    critique_gap(StrategyId, _, Severity, _),
    ( Severity = 'high' ; Severity = 'medium' ).

pending_critiques(StrategyId, Critiques) :-
    findall(Severity-Gap-Suggestion, critique_gap(StrategyId, Gap, Severity, Suggestion), Critiques).

verified_count(Count) :-
    findall(T, verified(T, _), All), length(All, Count).
'''


class SharedKB:
    """Prolog-backed shared knowledge base for Mind-EvoAgent communication."""

    def __init__(self, storage_tag: str = "shared"):
        self._kb_path = os.path.join(tempfile.gettempdir(), f"evo_shared_kb_{storage_tag}.pl")
        self._write_header()

    @property
    def path(self):
        return self._kb_path

    def asserta(self, fact: str) -> None:
        self._append(self._ensure_period(fact) + "\n")

    def assertz(self, facts: list[str]) -> None:
        self._append("".join(self._ensure_period(f) + "\n" for f in facts))

    def retractall(self, predicate: str) -> str:
        if not os.path.exists(self._kb_path):
            return ""
        with open(self._kb_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        hl = len(_SHARED_KB_HELPERS.split("\n"))
        old, new = [], lines[:hl]
        for line in lines[hl:]:
            (old if line.strip().startswith(predicate + "(") else new).append(line)
        with open(self._kb_path, "w", encoding="utf-8") as f:
            f.writelines(new)
        return "".join(old)

    def query(self, query_str: str) -> str:
        if not os.path.exists(self._kb_path):
            return "Shared KB is empty."
        try:
            with open(self._kb_path, "r", encoding="utf-8") as f:
                return self._run_swipl_query(f.read(), query_str)
        except OSError as e:
            return f"Failed to read shared KB: {e}"

    def propose_strategy(self, sid: str, problem: str, desc: str, priority: int = 5) -> None:
        self.asserta(f"propose_strategy({_esc(sid)}, {_esc(problem)}, {_esc(desc)}, {priority})")
        self._log_event(sid, "proposed", f"priority={priority}")

    def claim_strategy(self) -> Optional[str]:
        result = self.query("next_strategy(S)")
        for line in (result or "").split("\n"):
            line = line.strip()
            if "S =" in line or line.startswith("S ="):
                sid = line.split("=", 1)[1].strip().rstrip(".").strip("'")
                self.asserta(f"strategy_result({sid}, in_progress, 'claimed')")
                self.asserta(f"active_strategy({sid})")
                self._log_event(sid, "selected", "")
                return sid
        return None

    def report_strategy_result(self, sid: str, status: str, detail: str = "") -> None:
        self.asserta(f"strategy_result({_esc(sid)}, {_esc(status)}, {_esc(detail)})")
        self._log_event(sid, "completed" if status == "succeeded" else status, detail)

    def write_trace(self, turn: int, layer: str, goal: str, status: str, detail: str = "") -> None:
        self.asserta(f"trace({turn}, {_esc(layer)}, {_esc(goal)}, {_esc(status)}, {_esc(detail)})")

    def read_traces(self, turn: Optional[int] = None) -> str:
        if turn is not None:
            return self.query(f"traces_for_turn({turn}, Traces)")
        return self.query("findall(T-L-G-S-D, trace(T, L, G, S, D), All)")

    def write_critique(self, sid: str, gap: str, severity: str = "medium", suggestion: str = "") -> None:
        self.asserta(f"critique_gap({_esc(sid)}, {_esc(gap)}, {_esc(severity)}, {_esc(suggestion)})")
        self._log_event(sid, "critiqued", f"{severity}: {gap[:60]}")

    def read_critiques(self, sid: Optional[str] = None) -> str:
        if sid:
            return self.query(f"pending_critiques({_esc(sid)}, Critiques)")
        return self.query("findall(S-G-Sev-Sug, critique_gap(S, G, Sev, Sug), All)")

    def record_verification(self, name: str, code: str) -> None:
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        self.asserta(f"verified({_esc(name)}, {_esc(h)})")

    def _write_header(self) -> None:
        try:
            with open(self._kb_path, "w", encoding="utf-8") as f:
                f.write(_SHARED_KB_HELPERS)
        except OSError:
            pass

    def _append(self, text: str) -> None:
        try:
            with open(self._kb_path, "a", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass

    def _log_event(self, sid: str, event: str, payload: str) -> None:
        ts = int(time.time())
        self._append(f"strategy_log({_esc(sid)}, {ts}, {_esc(event)}, {_esc(payload[:200])}).\n")

    def _run_swipl_query(self, kb: str, q: str) -> str:
        return "SWI-Prolog (swipl) not found. Set SWIPL_PATH in config."

    @staticmethod
    def _ensure_period(fact: str) -> str:
        f = fact.strip()
        return f if f.endswith(".") else f + "."


def _esc(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\t", "\\t")
    if len(s) > 500:
        s = s[:500] + "[...truncated]"
    return f"'{s}'"
