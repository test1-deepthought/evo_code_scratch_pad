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
'''

def _esc(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    if len(s) > 500:
        s = s[:500] + "..."
    return f"'{s}'"


class SharedKB:
    """Prolog-backed shared knowledge base for Mind-EvoAgent communication."""

    def __init__(self, storage_tag: str = "shared"):
        self._kb_path = os.path.join(tempfile.gettempdir(), f"evo_shared_kb_{storage_tag}.pl")
        self._write_header()

    @property
    def path(self) -> str:
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
        """Query the KB. Parses facts from the file and processes known queries."""
        if not os.path.exists(self._kb_path):
            return "Shared KB is empty."
        try:
            with open(self._kb_path, "r", encoding="utf-8") as f:
                kb_content = f.read()
            return self._run_query(kb_content, query_str)
        except OSError as e:
            return f"Failed to read shared KB: {e}"

    def propose_strategy(self, sid: str, problem: str, desc: str, priority: int = 5) -> None:
        self.asserta(f"propose_strategy({_esc(sid)}, {_esc(problem)}, {_esc(desc)}, {priority})")
        self._log_event(sid, "proposed", f"priority={priority}")

    def claim_strategy(self) -> Optional[str]:
        facts = self._parse_facts("propose_strategy")
        # Find unclaimed strategies sorted by priority (higher priority = lower number)
        unclaimed = []
        for f in facts:
            sid = f.get("args", [None])[0]
            if sid and not self._fact_exists("strategy_result", sid):
                # priority is the 4th arg (index 3)
                priority = int(f["args"][3]) if len(f["args"]) > 3 else 5
                unclaimed.append((priority, sid))
        unclaimed.sort()
        if unclaimed:
            sid = unclaimed[0][1]
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
        facts = self._parse_facts("trace")
        if turn is not None:
            facts = [f for f in facts if str(turn) == f["args"][0]]
        if not facts:
            return "Query: read_traces\n(no traces found)"
        lines = ["Query: read_traces"]
        for f in facts:
            lines.append(f"trace({', '.join(f['args'])})")
        return "\n".join(lines)

    def write_critique(self, sid: str, gap: str, severity: str = "medium", suggestion: str = "") -> None:
        self.asserta(f"critique_gap({_esc(sid)}, {_esc(gap)}, {_esc(severity)}, {_esc(suggestion)})")
        self._log_event(sid, "critiqued", f"{severity}: {gap[:60]}")

    def read_critiques(self, sid: Optional[str] = None) -> str:
        facts = self._parse_facts("critique_gap")
        if sid:
            facts = [f for f in facts if f["args"][0] == sid]
        if not facts:
            return "Query: read_critiques\n(no critiques found)"
        lines = ["Query: read_critiques"]
        for f in facts:
            lines.append(f"{f['args'][2]}-{f['args'][1]}-{f['args'][3]}")
        return "\n".join(lines)

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

    def _log_event(self, sid: str, event: str, detail: str) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        self.asserta(f"strategy_log({_esc(sid)}, {_esc(event)}, \"{ts}\", {_esc(detail)})")

    @staticmethod
    def _ensure_period(fact: str) -> str:
        fact = fact.strip()
        return fact if fact.endswith(".") else fact + "."

    def _parse_facts(self, predicate: str) -> list[dict]:
        """Parse all facts with the given predicate name from the KB file."""
        if not os.path.exists(self._kb_path):
            return []
        facts = []
        with open(self._kb_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(predicate + "(") and line.endswith("."):
                    # Extract arguments between parentheses
                    inner = line[len(predicate) + 1:-1]
                    facts.append({"raw": line, "args": self._parse_args(inner)})
        return facts

    @staticmethod
    def _parse_args(inner: str) -> list[str]:
        """Parse Prolog arguments accounting for quoted strings."""
        args = []
        depth = 0
        current = ""
        in_quote = False
        for ch in inner:
            if ch == "'":
                in_quote = not in_quote
                current += ch
            elif ch == "(" and not in_quote:
                depth += 1
                current += ch
            elif ch == ")" and not in_quote:
                depth -= 1
                current += ch
            elif ch == "," and depth == 0 and not in_quote:
                args.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            args.append(current.strip())
        return args

    def _fact_exists(self, predicate: str, arg0: str) -> bool:
        """Check if a fact with the given predicate and first argument exists."""
        facts = self._parse_facts(predicate)
        for f in facts:
            if f["args"] and f["args"][0] == arg0:
                return True
        return False

    def _run_query(self, kb_content: str, query_str: str) -> str:
        """Run a query against the KB content using parsed facts.

        Supports:
        - next_strategy(S) - find unclaimed strategy
        - has_open_critique(S) - check for high/medium critiques
        - pending_critiques(S, Critiques) - list critiques for strategy
        - findall(...) - find all facts of a type
        - traces_for_turn(T, Traces) - find traces for a turn
        """
        q = query_str.strip()

        # has_open_critique(S)
        if q.startswith("has_open_critique("):
            sid = q[len("has_open_critique("):-1].strip().strip("'\"")
            facts = self._parse_facts("critique_gap")
            for f in facts:
                if f["args"][0] == sid and f["args"][2] in ("high", "medium"):
                    return f"Query: {q}\ntrue"
            return f"Query: {q}\nfalse"

        # pending_critiques(S, Critiques)
        if q.startswith("pending_critiques("):
            sid = q[len("pending_critiques("):q.index(",")].strip().strip("'\"")
            facts = self._parse_facts("critique_gap")
            result = [f"Query: {q}"]
            for f in facts:
                if f["args"][0] == sid:
                    result.append(f"{f['args'][2]}-{f['args'][1]}-{f['args'][3]}")
            if len(result) == 1:
                result.append("(no critiques)")
            return "\n".join(result)

        # next_strategy(S)
        if q.startswith("next_strategy("):
            proposed = self._parse_facts("propose_strategy")
            results = []
            for p in proposed:
                sid = p["args"][0]
                if not self._fact_exists("strategy_result", sid):
                    priority = int(p["args"][3]) if len(p["args"]) > 3 else 5
                    results.append((priority, sid))
            results.sort()
            if results:
                return f"Query: {q}\nS = '{results[0][1]}'"
            return f"Query: {q}\nfalse"

        # traces_for_turn(T, Traces)
        if q.startswith("traces_for_turn("):
            turn = q[len("traces_for_turn("):q.index(",")].strip()
            facts = self._parse_facts("trace")
            result = [f"Query: {q}"]
            for f in facts:
                if f["args"][0] == turn:
                    result.append(f"{f['args'][1]}-{f['args'][2]}-{f['args'][3]}-{f['args'][4]}")
            if len(result) == 1:
                result.append("(no traces)")
            return "\n".join(result)

        # findall fallback - return matching predicate facts
        if q.startswith("findall("):
            # Extract predicate name from findall template
            import re
            m = re.search(r'trace\(T,\s*L,\s*G,\s*S,\s*D\)', q)
            if m:
                facts = self._parse_facts("trace")
                result = [f"Query: {q}"]
                for f in facts:
                    result.append("trace(" + ", ".join(f["args"]) + ")")
                if len(result) == 1:
                    result.append("(no traces)")
                return "\n".join(result)
            m = re.search(r'critique_gap\(S,\s*G,\s*Sev,\s*Sug\)', q)
            if m:
                facts = self._parse_facts("critique_gap")
                result = [f"Query: {q}"]
                for f in facts:
                    result.append(f"{f['args'][0]}-{f['args'][2]}-{f['args'][1]}-{f['args'][3]}")
                if len(result) == 1:
                    result.append("(no critiques)")
                return "\n".join(result)
            # Generic findall: extract predicate name after trace
            # Use simple heuristic
            return f"Query: {q}\n(findall query not fully supported)"

        return f"Query: {q}\n(query not recognized)"
