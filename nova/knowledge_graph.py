"""
I1: Persistent Knowledge Graph — accumulates facts, proofs, and strategies
across sessions. Prolog facts persist in a triplestore backed by JSON.

Extracts the relation-tracking infrastructure from evo-ai's Prolog base.pl
and evo_context.py's session_kb, replacing ephemeral session state with
persistent storage and queryable history.

FIXED in v0.2.0:
- Added export_prolog_facts() method (was missing, breaking agent.py imports)
- Added dedup for identical facts
- Added expiry cleanup mechanism
- Fixed _save() edge cases for empty paths
FIXED in v0.2.1:
- export_prolog_facts() now includes source in the Prolog fact output
"""

import json
import os
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Fact:
    """A single knowledge graph fact (triple with metadata)."""
    subject: str
    predicate: str
    object_: str
    confidence: float = 1.0
    source: str = "internal"
    timestamp: float = 0.0
    turn: int = 0
    expires_at: Optional[float] = None

    def to_tuple(self) -> tuple[str, str, str]:
        return (self.subject, self.predicate, self.object_)


@dataclass
class ProofRecord:
    """A recorded proof with metadata."""
    theorem: str
    proof_code: str
    strategy: str = ""
    lemmas_used: list[str] = field(default_factory=list)
    verified: bool = False
    timestamp: float = 0.0
    turn: int = 0
    confidence: float = 1.0


@dataclass
class Pattern:
    """A learned pattern from past reasoning."""
    name: str
    description: str
    prolog_template: str = ""
    success_count: int = 0
    failure_count: int = 0
    first_seen: float = 0.0
    last_used: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class KnowledgeGraph:
    """Thread-safe persistent knowledge graph.

    Replaces evo-ai's ephemeral session_kb (evo_context.py) with a persistent
    triplestore that accumulates across sessions. Facts can expire, have
    confidence scores, and be annotated with source provenance.
    """

    def __init__(self, path: str = ""):
        from nova.config import NOVA_KNOWLEDGE_GRAPH_PATH
        self._path = path or NOVA_KNOWLEDGE_GRAPH_PATH
        self._lock = threading.RLock()
        self._facts: dict[str, list[Fact]] = {}  # predicate -> list of facts
        self._proofs: dict[str, ProofRecord] = {}
        self._patterns: dict[str, Pattern] = {}
        self._turn_counter: int = 0
        self._load()

    # -- Persistence ---------------------------------------------------------

    def _load(self) -> None:
        """Load graph from disk."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            for p, facts_list in data.get("facts", {}).items():
                self._facts[p] = [Fact(**f) for f in facts_list]
            for key, pr in data.get("proofs", {}).items():
                self._proofs[key] = ProofRecord(**pr)
            for key, pat in data.get("patterns", {}).items():
                self._patterns[key] = Pattern(**pat)
            self._turn_counter = data.get("turn", 0)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        """Write graph to disk."""
        try:
            data = {
                "facts": {
                    p: [asdict(f) for f in flist]
                    for p, flist in self._facts.items()
                },
                "proofs": {k: asdict(v) for k, v in self._proofs.items()},
                "patterns": {k: asdict(v) for k, v in self._patterns.items()},
                "turn": self._turn_counter,
            }
            dirname = os.path.dirname(self._path) or "."
            os.makedirs(dirname, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except OSError:
            pass  # Gracefully handle disk-full or permission errors

    # -- Fact management ----------------------------------------------------

    def next_turn(self) -> int:
        with self._lock:
            self._turn_counter += 1
            self._save()
            return self._turn_counter

    def assert_fact(self, subject: str, predicate: str, object_: str,
                    confidence: float = 1.0, source: str = "internal",
                    turn: Optional[int] = None, expires_in_seconds: Optional[float] = None) -> Fact:
        """Add a fact to the knowledge graph (with dedup)."""
        with self._lock:
            now = time.time()
            expires_at = (now + expires_in_seconds) if expires_in_seconds else None
            fact = Fact(
                subject=subject,
                predicate=predicate,
                object_=object_,
                confidence=confidence,
                source=source,
                timestamp=now,
                turn=turn if turn is not None else self._turn_counter,
                expires_at=expires_at,
            )
            # Dedup: replace if same triple exists
            if predicate in self._facts:
                self._facts[predicate] = [
                    f for f in self._facts[predicate]
                    if f.to_tuple() != fact.to_tuple()
                ]
            else:
                self._facts[predicate] = []
            self._facts[predicate].append(fact)
            self._save()
            return fact

    def query(self, subject: Optional[str] = None,
              predicate: Optional[str] = None,
              object_: Optional[str] = None) -> list[Fact]:
        """Query facts by subject, predicate, or object."""
        with self._lock:
            self._expire_stale()
            results = []
            for p, flist in self._facts.items():
                if predicate and p != predicate:
                    continue
                for f in flist:
                    if subject and f.subject != subject:
                        continue
                    if object_ and f.object_ != object_:
                        continue
                    results.append(f)
            return results

    def query_all(self, predicate: str) -> list[Fact]:
        """Get all facts for a given predicate."""
        return self.query(predicate=predicate)

    def clear(self, predicate: Optional[str] = None) -> None:
        """Clear facts, optionally filtered by predicate."""
        with self._lock:
            if predicate:
                self._facts.pop(predicate, None)
            else:
                self._facts.clear()
            self._save()

    def _expire_stale(self) -> None:
        """Remove expired facts."""
        now = time.time()
        for predicate in list(self._facts.keys()):
            self._facts[predicate] = [
                f for f in self._facts[predicate]
                if f.expires_at is None or f.expires_at > now
            ]
            if not self._facts[predicate]:
                del self._facts[predicate]

    def export_prolog_facts(self) -> str:
        """Export all current facts as Prolog-compatible assertions.

        Returns a string of Prolog facts that can be prepended to a
        Prolog program for querying.
        """
        with self._lock:
            self._expire_stale()
            lines = []
            for predicate, flist in self._facts.items():
                for f in flist:
                    # Escape Prolog strings
                    subj = f.subject.replace("'", "\\'")
                    obj = f.object_.replace("'", "\\'")
                    pred = predicate.replace("'", "\\'")
                    src = f.source.replace("'", "\\'")
                    lines.append(
                        f"fact('{subj}', '{pred}', '{obj}', {f.confidence:.4f}, "
                        f"{int(f.turn)}, source='{src}')."
                    )
            return "\n".join(lines)

    # -- Proof management ---------------------------------------------------

    def store_proof(self, record: ProofRecord) -> None:
        with self._lock:
            self._proofs[record.theorem] = record
            self._save()

    def get_proof(self, theorem: str) -> Optional[ProofRecord]:
        return self._proofs.get(theorem)

    def list_proofs(self, verified_only: bool = False) -> list[ProofRecord]:
        proofs = list(self._proofs.values())
        if verified_only:
            proofs = [p for p in proofs if p.verified]
        return proofs

    # -- Pattern management -------------------------------------------------

    def store_pattern(self, pattern: Pattern) -> None:
        with self._lock:
            self._patterns[pattern.name] = pattern
            self._save()

    def get_pattern(self, name: str) -> Optional[Pattern]:
        return self._patterns.get(name)

    def list_patterns(self) -> list[Pattern]:
        return list(self._patterns.values())
