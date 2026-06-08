import hashlib
import logging
import os
import re
import subprocess
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

%% -- Query helpers

%% List all strategies by priority (lowest first)
strategies_by_priority(Strategies) :-
    findall(Prio-Strat,
            propose_strategy(Strat, _, _, Prio),
            Pairs),
    sort(Pairs, Sorted),
    findall(Strat, member(_-Strat, Sorted), Strategies).

%% Get the highest-priority unprocessed strategy
next_strategy(StrategyId) :-
    strategies_by_priority([StrategyId|_]),
    \+ strategy_result(StrategyId, _, _).

%% Get all traces for a given turn, ordered
traces_for_turn(Turn, Traces) :-
    findall(Layer-Goal-Status-Detail,
            trace(Turn, Layer, Goal, Status, Detail),
            Traces).

%% Check if a strategy has any open critique
has_open_critique(StrategyId) :-
    critique_gap(StrategyId, _, Severity, _),
    ( Severity = ''high'' ; Severity = ''medium'' ).

%% Get pending critiques for a strategy
pending_critiques(StrategyId, Critiques) :-
    findall(Severity-Gap-Suggestion,
            critique_gap(StrategyId, Gap, Severity, Suggestion),
            Critiques).

%% Count verified theorems
verified_count(Count) :-
    findall(T, verified(T, _), All),
    length(All, Count).
'''


class SharedKB:
    """Prolog-backed shared knowledge base for Mind-EvoAgent communication."""

    def __init__(self, storage_tag: str = "shared"):
        self._kb_path = os.path.join(
            tempfile.gettempdir(), f"evo_shared_kb_{storage_tag}.pl"
        )
        self._write_header()

    @property
    def path(self) -> str:
        return self._kb_path

    def asserta(self, fact: str) -> None:
        escaped = self._ensure_period(fact)
        self._append(escaped + "\n")

    def assertz(self, facts: list[str]) -> None:
        block = "".join(self._ensure_period(f) + "\n" for f in facts)
        self._append(block)

    def retractall(self, predicate: str) -> str:
        if not os.path.exists(self._kb_path):
            return ""
        with open(self._kb_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        header_lines = _SHARED_KB_HELPERS.split("\n")
        old_lines = []
        new_lines = lines[:len(header_lines)]
        for line in lines[len(header_lines):]:
            stripped = line.strip()
            if stripped.startswith(predicate + "("):
                old_lines.append(line)
            else:
                new_lines.append(line)
        with open(self._kb_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return "".join(old_lines)

    def query(self, query_str: str) -> str:
        if not os.path.exists(self._kb_path):
            return "Shared KB is empty."
        try:
            with open(self._kb_path, "r", encoding="utf-8") as f:
                kb_content = f.read()
        except OSError as e:
            return f"Failed to read shared KB: {e}"
        return self._run_swipl_query(kb_content, query_str)

    def propose_strategy(
        self, strategy_id: str, problem: str, description: str, priority: int = 5
    ) -> None:
        pid = _esc(strategy_id)
        pprob = _esc(problem)
        pdesc = _esc(description)
        self.asserta(
            f"propose_strategy({pid}, {pprob}, {pdesc}, {priority})"
        )
        self._log_event(strategy_id, "proposed", f"priority={priority}")

    def claim_strategy(self) -> Optional[str]:
        result = self.query("next_strategy(S)")
        for line in (result or "").split("\n"):
            line = line.strip()
            if "S =" in line or line.startswith("S ="):
                sid = line.split("=", 1)[1].strip().rstrip(".")
                sid = sid.strip("'")
                self.asserta(f"strategy_result({sid}, in_progress, 'claimed')")
                self.asserta(f"active_strategy({sid})")
                self._log_event(sid, "selected", "")
                return sid
        return None

    def report_strategy_result(
        self, strategy_id: str, status: str, detail: str = ""
    ) -> None:
        sid = _esc(strategy_id)
        sstatus = _esc(status)
        sdetail = _esc(detail)
        self.asserta(f"strategy_result({sid}, {sstatus}, {sdetail})")
        event = "completed" if status == "succeeded" else status
        self._log_event(strategy_id, event, detail)

    def write_trace(
        self, turn: int, layer: str, goal: str, status: str, detail: str = ""
    ) -> None:
        l = _esc(layer)
        g = _esc(goal)
        s = _esc(status)
        d = _esc(detail)
        self.asserta(f"trace({turn}, {l}, {g}, {s}, {d})")

    def read_traces(self, turn: Optional[int] = None) -> str:
        if turn is not None:
            return self.query(f"traces_for_turn({turn}, Traces)")
        return self.query("findall(T-L-G-S-D, trace(T, L, G, S, D), All)")

    def write_critique(
        self, strategy_id: str, gap: str, severity: str = "medium", suggestion: str = ""
    ) -> None:
        sid = _esc(strategy_id)
        g = _esc(gap)
        sev = _esc(severity)
        sug = _esc(suggestion)
        self.asserta(f"critique_gap({sid}, {g}, {sev}, {sug})")
        self._log_event(strategy_id, "critiqued", f"{severity}: {gap[:60]}")

    def read_critiques(self, strategy_id: Optional[str] = None) -> str:
        if strategy_id:
            return self.query(f"pending_critiques({_esc(strategy_id)}, Critiques)")
        return self.query("findall(S-G-Sev-Sug, critique_gap(S, G, Sev, Sug), All)")

    def record_verification(self, theorem_name: str, lean_code: str) -> None:
        h = hashlib.sha256(lean_code.encode("utf-8")).hexdigest()[:16]
        self.asserta(f"verified({_esc(theorem_name)}, {_esc(h)})")

    def verified_theorems(self) -> str:
        return self.query("findall(T, verified(T, _), Theorems)")

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

    def _log_event(
        self, strategy_id: str, event: str, payload: str
    ) -> None:
        ts = int(time.time())
        sid = _esc(strategy_id)
        ev = _esc(event)
        pl = _esc(payload[:200])
        self._append(f"strategy_log({sid}, {ts}, {ev}, {pl}).\n")

    def _run_swipl_query(
        self, kb_content: str, query_str: str
    ) -> str:
        # SWI-Prolog not available; return a mock result for claim_strategy
        swipl = os.environ.get("SWIPL_PATH", "swipl")
        return "SWI-Prolog (swipl) not found. Set SWIPL_PATH in config."

    @staticmethod
    def _ensure_period(fact: str) -> str:
        fact = fact.strip()
        if not fact.endswith("."):
            fact += "."
        return fact


def _esc(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    if len(s) > 500:
        s = s[:500] + "[...truncated]"
    return f"'{s}'"
