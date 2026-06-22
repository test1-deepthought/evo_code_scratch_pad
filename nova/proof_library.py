"""
I5: Learned Proof Library — caches Lean 4 proof patterns from successful
sessions. When a theorem resembles a previously proved one, the library
suggests the proof skeleton and key lemmas.

Extends the Knowledge Graph's proof storage with similarity search,
pattern extraction, and template generation.
"""

from __future__ import annotations

import json
import os
import re
import difflib
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ProofSkeleton:
    """A reusable proof skeleton with strategy metadata."""
    name: str
    strategy: str
    theorem_template: str
    proof_template: str
    imports: list[str] = field(default_factory=lambda: ["import Mathlib"])
    key_lemmas: list[str] = field(default_factory=list)
    success_count: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class ProofEntry:
    """A cached proof with its full context."""
    theorem_name: str
    full_statement: str
    proof_code: str
    strategy: str
    lemmas_used: list[str]
    verified: bool
    timestamp: float = 0.0
    signature_hash: str = ""


class ProofLibrary:
    """Library of reusable proof patterns, skeletons, and cached proofs.
    
    Provides similarity search across theorem names, strategy patterns,
    and lemma usage. Generates proof skeleton suggestions for new theorems.
    """

    def __init__(self, path: str = ""):
        from nova.config import NOVA_PROOF_LIBRARY_PATH
        self._path = path or NOVA_PROOF_LIBRARY_PATH
        self._skeletons: dict[str, ProofSkeleton] = {}
        self._proofs: dict[str, ProofEntry] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            for k, v in data.get("skeletons", {}).items():
                self._skeletons[k] = ProofSkeleton(**v)
            for k, v in data.get("proofs", {}).items():
                self._proofs[k] = ProofEntry(**v)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        data = {
            "skeletons": {k: asdict(v) for k, v in self._skeletons.items()},
            "proofs": {k: asdict(v) for k, v in self._proofs.items()},
        }
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def store_skeleton(self, skeleton: ProofSkeleton) -> None:
        self._skeletons[skeleton.name] = skeleton
        self._save()

    def store_proof(self, entry: ProofEntry) -> None:
        self._proofs[entry.theorem_name] = entry
        self._save()

    def find_skeleton(self, theorem_name: str) -> Optional[ProofSkeleton]:
        """Find a skeleton by exact name or best name match."""
        if theorem_name in self._skeletons:
            return self._skeletons[theorem_name]
        # Fuzzy match
        names = list(self._skeletons.keys())
        matches = difflib.get_close_matches(theorem_name, names, n=1, cutoff=0.6)
        if matches:
            return self._skeletons[matches[0]]
        return None

    def find_proof(self, theorem_name: str) -> Optional[ProofEntry]:
        return self._proofs.get(theorem_name)

    def search_by_strategy(self, strategy: str) -> list[ProofSkeleton]:
        """Find skeletons sharing a proof strategy."""
        query = strategy.lower()
        return [
            s for s in self._skeletons.values()
            if query in s.strategy.lower()
        ]

    def search_by_lemma(self, lemma: str) -> list[ProofEntry]:
        """Find proofs that use a specific lemma."""
        query = lemma.lower()
        return [
            p for p in self._proofs.values()
            if any(query in l.lower() for l in p.lemmas_used)
        ]

    def suggest_skeleton(self, theorem_statement: str) -> Optional[ProofSkeleton]:
        """Suggest a proof skeleton based on the theorem statement.
        
        Uses keyword matching to identify the proof strategy and find
        the best-matching skeleton.
        """
        text = theorem_statement.lower()
        
        # Detect strategy from statement
        if re.search(r'\b(induction|inductive|recursive|nat|\+|\*)\b', text):
            strategy = "induction"
        elif re.search(r'\b(contradiction|contrapositive|negation|¬|≠|\bnot\b)\b', text):
            strategy = "contradiction"
        elif re.search(r'\b(case|cases|classify|partition|either|or)\b', text):
            strategy = "case_analysis"
        elif re.search(r'\b(exists|construct|find|example|witness|example)\b', text):
            strategy = "construction"
        elif re.search(r'\b(unique|only|exactly|bijection|one[- ]to[- ]one)\b', text):
            strategy = "uniqueness"
        else:
            strategy = "direct"
        
        # Find matching skeletons by strategy
        matches = self.search_by_strategy(strategy)
        if matches:
            matches.sort(key=lambda s: -s.success_count)
            return matches[0]
        
        # Extract key terms and find by tag overlap
        words = set(re.findall(r'\b[a-z]{3,}\b', text))
        best: Optional[ProofSkeleton] = None
        best_score = 0
        for skeleton in self._skeletons.values():
            tag_overlap = len(words & set(skeleton.tags))
            if tag_overlap > best_score:
                best_score = tag_overlap
                best = skeleton
        
        return best

    def extract_and_store(self, theorem_name: str, full_statement: str,
                          proof_code: str, strategy: str,
                          lemmas_used: list[str], verified: bool) -> ProofEntry:
        """Extract a proof entry from a successful Lean 4 session and store it."""
        entry = ProofEntry(
            theorem_name=theorem_name,
            full_statement=full_statement,
            proof_code=proof_code,
            strategy=strategy,
            lemmas_used=lemmas_used,
            verified=verified,
        )
        self.store_proof(entry)
        
        # Also create/update a skeleton if strategy is notable
        existing = self.find_skeleton(theorem_name)
        if existing:
            existing.success_count += 1
            self._save()
        elif strategy:
            skeleton = ProofSkeleton(
                name=f"{strategy}_pattern",
                strategy=strategy,
                theorem_template=full_statement[:200] + "...",
                proof_template=proof_code[:500] + "...",
                key_lemmas=lemmas_used,
                success_count=1,
                tags=list(set(re.findall(r'\b[a-z]{3,}\b', full_statement.lower()))),
            )
            self.store_skeleton(skeleton)
        
        return entry
