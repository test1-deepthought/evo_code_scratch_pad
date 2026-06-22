"""
I1: Persistent Knowledge Graph — accumulates facts, proofs, and strategies
across sessions. Prolog facts persist in a triplestore backed by JSON.

Extracts the relation-tracking infrastructure from evo-ai's Prolog base.pl
and evo_context.py's session_kb, replacing ephemeral session state with
persistent storage and queryable history.
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
        data = {
            "facts": {
                p: [asdict(f) for f in flist]
                for p, flist in self._facts.items()
            },
            "proofs": {k: asdict(v) for k, v in self._proofs.items()},
            "patterns": {k: asdict(v) for k, v in self._patterns.items()},
            "turn": self._turn_counter,
        }
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # -- Fact management ----------------------------------------------------

    def next_turn(self) -> int:
        with self._lock:
            self._turn_counter += 1
            self._save()
            return self._turn_counter

    @property
    def current_turn(self) -> int:
        with self._lock:
            return self._turn_counter

    def assert_fact(self, subject: str, predicate: str, object_: str,
                    confidence: float = 1.0, source: str = "internal",
                    expires_in: Optional[float] = None) -> Fact:
        """Add a fact to the graph."""
        with self._lock:
            now = time.time()
            fact = Fact(
                subject=subject,
                predicate=predicate,
                object_=object_,
                confidence=confidence,
                source=source,
                timestamp=now,
                turn=self._turn_counter,
                expires_at=(now + expires_in) if expires_in else None,
            )
            if predicate not in self._facts:
                self._facts[predicate] = []
            self._facts[predicate].append(fact)
            self._save()
            return fact

    def query(self, predicate: str, subject: Optional[str] = None,
              object_: Optional[str] = None,
              min_confidence: float = 0.0) -> list[Fact]:
        """Query facts by predicate, optionally filtering by subject/object."""
        with self._lock:
            now = time.time()
            results = []
            for fact in self._facts.get(predicate, []):
                if fact.expires_at and fact.expires_at < now:
                    continue
                if fact.confidence < min_confidence:
                    continue
                if subject and fact.subject != subject:
                    continue
                if object_ and fact.object_ != object_:
                    continue
                results.append(fact)
            return results

    def query_triple(self, subject: str, predicate: str, object_: str) -> Optional[Fact]:
        """Find an exact triple match."""
        results = self.query(predicate, subject=subject, object_=object_)
        return results[0] if results else None

    def retract(self, predicate: str, subject: Optional[str] = None,
                object_: Optional[str] = None) -> int:
        """Remove matching facts. Returns count removed."""
        with self._lock:
            before = len(self._facts.get(predicate, []))
            self._facts[predicate] = [
                f for f in self._facts.get(predicate, [])
                if (subject and f.subject != subject)
                or (object_ and f.object_ != object_)
                or (not subject and not object_)
            ]
            removed = before - len(self._facts.get(predicate, []))
            if removed:
                self._save()
            return removed

    # -- Proof management ---------------------------------------------------

    def store_proof(self, theorem: str, proof_code: str,
                    strategy: str = "", lemmas_used: Optional[list[str]] = None,
                    verified: bool = False,
                    confidence: float = 1.0) -> ProofRecord:
        with self._lock:
            record = ProofRecord(
                theorem=theorem,
                proof_code=proof_code,
                strategy=strategy,
                lemmas_used=lemmas_used or [],
                verified=verified,
                timestamp=time.time(),
                turn=self._turn_counter,
                confidence=confidence,
            )
            self._proofs[theorem] = record
            self._save()
            return record

    def lookup_proof(self, theorem: str) -> Optional[ProofRecord]:
        with self._lock:
            return self._proofs.get(theorem)

    def find_similar_proofs(self, theorem: str, min_similarity: float = 0.3) -> list[ProofRecord]:
        """Find proofs with overlapping strategy or lemma names."""
        with self._lock:
            query_tokens = set(theorem.lower().replace("_", " ").split())
            scored: list[tuple[float, ProofRecord]] = []
            for name, record in self._proofs.items():
                if name == theorem:
                    continue
                name_tokens = set(name.lower().replace("_", " ").split())
                lemma_tokens = set(
                    l.lower().replace("_", " ") for l in record.lemmas_used
                )
                all_tokens = name_tokens | lemma_tokens
                if not all_tokens:
                    continue
                overlap = len(query_tokens & all_tokens)
                similarity = overlap / max(len(query_tokens), len(all_tokens))
                if similarity >= min_similarity:
                    scored.append((similarity, record))
            scored.sort(key=lambda x: -x[0])
            return [r for _, r in scored]

    # -- Pattern learning ---------------------------------------------------

    def record_pattern(self, name: str, description: str,
                       prolog_template: str = "", success: bool = True) -> Pattern:
        with self._lock:
            now = time.time()
            if name not in self._patterns:
                self._patterns[name] = Pattern(
                    name=name,
                    description=description,
                    prolog_template=prolog_template,
                    first_seen=now,
                )
            pattern = self._patterns[name]
            if success:
                pattern.success_count += 1
            else:
                pattern.failure_count += 1
            pattern.last_used = now
            if prolog_template:
                pattern.prolog_template = prolog_template
            self._save()
            return pattern

    def get_recommended_pattern(self, description: str) -> Optional[Pattern]:
        """Find the best matching pattern by keyword overlap."""
        with self._lock:
            query_tokens = set(description.lower().split())
            best_pattern: Optional[Pattern] = None
            best_score = 0.0
            for pattern in self._patterns.values():
                desc_tokens = set(pattern.description.lower().split())
                overlap = len(query_tokens & desc_tokens)
                if overlap > best_score and pattern.success_rate > 0.5:
                    best_score = overlap
                    best_pattern = pattern
            return best_pattern

    def export_prolog_facts(self) -> str:
        """Export relevant facts as Prolog code for the reasoner."""
        with self._lock:
            lines = ["%% Auto-exported from NOVA Knowledge Graph"]
            now = time.time()
            for predicate, facts in self._facts.items():
                for fact in facts:
                    if fact.expires_at and fact.expires_at < now:
                        continue
                    s = fact.subject.replace("'", "\\'")
                    p = predicate
                    o = fact.object_.replace("'", "\\'")
                    lines.append(f"relation('{s}', {p}, '{o}').")
            return "\n".join(lines)
