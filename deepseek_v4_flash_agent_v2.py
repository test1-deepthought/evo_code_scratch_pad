#!/usr/bin/env python3
"""
DeepSeek-v4-flash AI Agent v2
=============================
A self-improving AI agent **based on the real DeepSeek-v4-flash LLM** via its official API.
Integrates DeepSeek's reasoning engine with symbolic logic, episodic memory, and
meta-cognitive self-improvement.

Attributes:
  (1) Logical Reasoning — uses DeepSeek-v4-flash LLM as primary reasoning engine
      with structured chain-of-thought prompting; symbolic inference as fallback
  (2) Learn — episodic memory stores interaction history; pattern extraction from
      DeepSeek's responses; Markov-chain transition learning
  (3) Persistent Self-Improvement — meta-cognitive engine tracks strategy performance
      (including DeepSeek API call patterns), adjusts parameters, detects plateaus
  (4) Python Language — pure Python 3, stdlib only (urllib for API calls)

API Reference: https://api-docs.deepseek.com/api/create-chat-completion
Model: deepseek-v4-flash (also aliases: deepseek-chat until 2026/07/24)
Endpoint: POST https://api.deepseek.com/chat/completions
"""

import json
import time
import random
import math
import heapq
import hashlib
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
from typing import (Optional, Dict, List, Tuple, Any, Set, Callable,
                    Union, Iterator)
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: LOGICAL REASONING (via DeepSeek-v4-flash LLM + Symbolic Fallback)
# ═══════════════════════════════════════════════════════════════════════════════

class DeepSeekAPI:
    """Client for the real DeepSeek-v4-flash LLM API.

    Endpoint: POST https://api.deepseek.com/chat/completions
    Model:    deepseek-v4-flash

    Uses OpenAI-compatible chat completions format.
    """

    BASE_URL: str = "https://api.deepseek.com/chat/completions"
    DEFAULT_MODEL: str = "deepseek-v4-flash"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 timeout: int = 30):
        """Initialize the DeepSeek API client.

        Args:
            api_key: DeepSeek API key. If None, the client will not attempt API calls.
            model: Model ID. Defaults to 'deepseek-v4-flash'.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or ""
        self.model = model
        self.timeout = timeout
        self._last_response: Optional[Dict[str, Any]] = None
        self._total_tokens_used: int = 0
        self._api_calls: int = 0
        self._api_errors: int = 0

    @property
    def available(self) -> bool:
        """Whether the API is configured and ready to use."""
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.3,
             max_tokens: int = 1024,
             **kwargs) -> Optional[str]:
        """Call the DeepSeek-v4-flash LLM.

        Args:
            messages: Chat messages in OpenAI format
                      [{'role': 'system', 'content': ...},
                       {'role': 'user', 'content': ...}]
            temperature: Sampling temperature (0.0-2.0). Lower = more deterministic.
            max_tokens: Maximum tokens in response.
            **kwargs: Additional API parameters (top_p, stop, etc.)

        Returns:
            The model's response text, or None on error.
        """
        if not self.available:
            return None

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            req = Request(
                self.BASE_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            self._last_response = body
            self._api_calls += 1

            # Track token usage
            usage = body.get("usage", {})
            self._total_tokens_used += usage.get("total_tokens", 0)

            # Extract response text
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

            return None

        except HTTPError as e:
            self._api_errors += 1
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[DeepSeek API] HTTP {e.code}: {error_body}")
            return None
        except URLError as e:
            self._api_errors += 1
            print(f"[DeepSeek API] Connection error: {e.reason}")
            return None
        except Exception as e:
            self._api_errors += 1
            print(f"[DeepSeek API] Unexpected error: {e}")
            return None

    def reason(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Use DeepSeek-v4-flash to perform logical reasoning.

        This is the PRIMARY reasoning mechanism. The LLM is prompted with
        structured chain-of-thought instructions to produce sound logical inferences.

        Args:
            query: The question or query to reason about.
            context: Optional dictionary with additional reasoning context
                     (e.g., facts, premises, constraints).

        Returns:
            Dict with reasoning result: {'answer': str, 'confidence': float,
                                          'tokens_used': int, 'error': Optional[str]}
        """
        system_prompt = (
            "You are DeepSeek-v4-flash, a precise logical reasoning engine. "
            "Your role is to perform step-by-step logical inference.\n\n"
            "RULES:\n"
            "1. Think step by step. Show your reasoning chain.\n"
            "2. Use formal logic when applicable (modus ponens, modus tollens, "
            "syllogism, etc.).\n"
            "3. If the query contains variables, treat them as universally quantified "
            "and attempt to find all satisfying assignments.\n"
            "4. If the query is a yes/no question, answer with 'YES' or 'NO' "
            "followed by your reasoning.\n"
            "5. If you cannot determine an answer from the given information, "
            "state 'INSUFFICIENT INFORMATION' and explain what is missing.\n"
            "6. Be precise. Do not speculate beyond the evidence provided.\n"
            "7. Format your final answer as: FINAL ANSWER: <your conclusion>"
        )

        user_message = f"Query: {query}\n"
        if context:
            if "facts" in context:
                user_message += f"\nKnown facts:\n"
                for f in context["facts"]:
                    user_message += f"  - {f}\n"
            if "premises" in context:
                user_message += f"\nPremises:\n"
                for p in context["premises"]:
                    user_message += f"  - {p}\n"
            if "constraints" in context:
                user_message += f"\nConstraints:\n"
                for c in context["constraints"]:
                    user_message += f"  - {c}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = self.chat(messages, temperature=0.2, max_tokens=2048)

        if response is None:
            return {
                "answer": None,
                "confidence": 0.0,
                "tokens_used": 0,
                "error": "API unavailable",
                "raw_response": None
            }

        # Extract confidence estimate from response
        confidence = 0.7  # default
        if "INSUFFICIENT INFORMATION" in response:
            confidence = 0.1
        elif "FINAL ANSWER:" in response or "YES" in response[:5] or "NO" in response[:5]:
            confidence = 0.9

        tokens = self._last_response.get("usage", {}).get("total_tokens", 0) if self._last_response else 0

        return {
            "answer": response,
            "confidence": confidence,
            "tokens_used": tokens,
            "error": None,
            "raw_response": self._last_response
        }

    def extract_structured_knowledge(self, text: str) -> List[Dict[str, str]]:
        """Use DeepSeek-v4-flash to extract structured logical statements from text.

        Args:
            text: Natural language text to analyze.

        Returns:
            List of extracted statements as {type, subject, predicate, object} dicts.
        """
        system_prompt = (
            "You are DeepSeek-v4-flash, a knowledge extraction engine. "
            "Extract formal logical statements from the given text.\n\n"
            "For each statement, output as JSON on one line:\n"
            '{"type": "fact", "subject": "S", "predicate": "P", "object": "O"}\n'
            '{"type": "rule", "antecedent": "A", "consequent": "C"}\n'
            '{"type": "constraint", "description": "D"}\n\n'
            "Output ONLY valid JSON lines, one per statement. No other text."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract logical statements from:\n\n{text}"}
        ]

        response = self.chat(messages, temperature=0.1, max_tokens=2048)
        if response is None:
            return []

        statements = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    statements.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return statements

    def get_stats(self) -> Dict[str, Any]:
        """Return API usage statistics."""
        return {
            "api_calls": self._api_calls,
            "api_errors": self._api_errors,
            "total_tokens_used": self._total_tokens_used,
            "model": self.model,
            "available": self.available
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize API state for persistence."""
        return {
            "model": self.model,
            "total_tokens_used": self._total_tokens_used,
            "api_calls": self._api_calls,
            "api_errors": self._api_errors
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], api_key: Optional[str] = None) -> "DeepSeekAPI":
        """Recreate API client from saved state."""
        api = cls(api_key=api_key, model=data.get("model", cls.DEFAULT_MODEL))
        api._total_tokens_used = data.get("total_tokens_used", 0)
        api._api_calls = data.get("api_calls", 0)
        api._api_errors = data.get("api_errors", 0)
        return api


# ─── Symbolic Inference Engine (Fallback) ─────────────────────────────────────

@dataclass(frozen=True)
class Term:
    """A logical term: either a constant, variable, or compound."""
    functor: str
    args: Tuple["Term", ...] = ()

    def __repr__(self) -> str:
        if not self.args:
            return self.functor
        return f"{self.functor}({', '.join(repr(a) for a in self.args)})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Term):
            return NotImplemented
        return self.functor == other.functor and self.args == other.args

    def __hash__(self) -> int:
        return hash((self.functor, self.args))

    def is_variable(self) -> bool:
        return self.functor.startswith("_") and self.functor != "_"

    def substitute(self, mapping: Dict[str, "Term"]) -> "Term":
        if self.is_variable() and self.functor in mapping:
            return mapping[self.functor]
        return Term(self.functor, tuple(a.substitute(mapping) for a in self.args))

    def variables(self) -> Set[str]:
        if self.is_variable():
            return {self.functor}
        result: Set[str] = set()
        for a in self.args:
            result.update(a.variables())
        return result


@dataclass(frozen=True)
class Clause:
    """A Horn clause: head :- body (or head if body is empty)."""
    head: Term
    body: Tuple[Term, ...] = ()

    def __repr__(self) -> str:
        if not self.body:
            return f"{self.head}."
        return f"{self.head} :- {', '.join(repr(b) for b in self.body)}."

    def substitute(self, mapping: Dict[str, Term]) -> "Clause":
        return Clause(
            self.head.substitute(mapping),
            tuple(b.substitute(mapping) for b in self.body)
        )

    def rename_variables(self, prefix: str = "G") -> "Clause":
        """Rename all variables with a prefix to avoid clashes."""
        mapping: Dict[str, Term] = {}
        idx = 0
        for var in self.head.variables():
            if var.startswith("_"):
                mapping[var] = Term(f"{prefix}{idx}")
                idx += 1
        for b in self.body:
            for var in b.variables():
                if var.startswith("_") and var not in mapping:
                    mapping[var] = Term(f"{prefix}{idx}")
                    idx += 1
        return self.substitute(mapping)


def unify(t1: Term, t2: Term, mapping: Optional[Dict[str, Term]] = None
          ) -> Optional[Dict[str, Term]]:
    """Unify two terms, returning the most general unifier or None."""
    if mapping is None:
        mapping = {}
    if t1 == t2:
        return mapping
    if t1.is_variable() and t1.functor != "_":
        return _unify_var(t1, t2, mapping)
    if t2.is_variable() and t2.functor != "_":
        return _unify_var(t2, t1, mapping)
    if t1.functor == t2.functor and len(t1.args) == len(t2.args):
        mapping = dict(mapping)
        for a1, a2 in zip(t1.args, t2.args):
            mapping = unify(a1, a2, mapping)
            if mapping is None:
                return None
        return mapping
    return None


def _unify_var(var: Term, term: Term, mapping: Dict[str, Term]) -> Optional[Dict[str, Term]]:
    if var.functor in mapping:
        return unify(mapping[var.functor], term, mapping)
    mapping = dict(mapping)
    mapping[var.functor] = term
    return mapping


class InferenceEngine:
    """Symbolic Horn-clause inference engine (fallback when DeepSeek API unavailable)."""

    def __init__(self):
        self._facts: List[Clause] = []
        self._rules: List[Clause] = []
        self._inference_count: int = 0

    def add_clause(self, clause: Clause) -> None:
        if not clause.body:
            self._facts.append(clause)
        else:
            self._rules.append(clause)

    def add_fact(self, fact_str: str) -> None:
        """Add a fact from string like 'human(socrates)'."""
        self._facts.append(Clause(Term(fact_str.split("(")[0])))

    def forward_chain(self, goal: Term, max_iterations: int = 100) -> bool:
        """Forward chain to derive the goal."""
        derived: Set[Term] = {f.head for f in self._facts}
        changed = True
        iterations = 0
        while changed and iterations < max_iterations:
            changed = False
            for rule in self._rules:
                renamed = rule.rename_variables("FC")
                for prem in renamed.body:
                    found = False
                    for d in derived:
                        if unify(prem, d) is not None:
                            found = True
                            break
                    if not found:
                        break
                else:
                    new_head = renamed.head
                    if new_head not in derived:
                        derived.add(new_head)
                        changed = True
                        self._inference_count += 1
            iterations += 1
        return any(unify(goal, d) is not None for d in derived)

    def backward_chain(self, goal: Term, max_iterations: int = 100) -> List[Dict[str, Term]]:
        """Backward chain to find all solutions for the goal.

        Returns list of binding dictionaries.
        """
        solutions: List[Dict[str, Term]] = []
        visited: Set[Tuple[str, ...]] = set()
        stack: List[Tuple[Term, Dict[str, Term], int]] = [
            (goal, {}, 0)
        ]

        iteration = 0
        while stack and iteration < max_iterations:
            current_goal, bindings, depth = stack.pop()
            iteration += 1
            self._inference_count += 1

            resolved = current_goal.substitute(bindings)
            key = (resolved.functor,) + tuple(
                str(a) for a in resolved.args
            )
            if key in visited and depth > 0:
                continue
            visited.add(key)

            # Check facts
            for fact in self._facts:
                u = unify(resolved, fact.head.substitute(bindings), dict(bindings))
                if u is not None:
                    if not resolved.is_variable():
                        solutions.append(u)
                    else:
                        solutions.append(u)

            # Check rules
            for rule in self._rules:
                renamed = rule.rename_variables(f"BC{depth}")
                u = unify(resolved, renamed.head.substitute(bindings), dict(bindings))
                if u is not None:
                    new_bindings = dict(bindings)
                    new_bindings.update(u)
                    for prem in renamed.body:
                        stack.append((prem, new_bindings, depth + 1))

        return solutions

    def solve(self, goal: Term, strategy: str = "backward_chaining") -> Dict[str, Any]:
        """Solve a goal using the specified strategy."""
        if strategy == "forward_chaining":
            proven = self.forward_chain(goal)
            return {
                "proven": proven,
                "solutions": [{}] if proven else [],
                "strategy": strategy,
                "inference_count": self._inference_count
            }
        elif strategy == "backward_chaining":
            solutions = self.backward_chain(goal)
            return {
                "proven": len(solutions) > 0,
                "solutions": solutions,
                "strategy": strategy,
                "inference_count": self._inference_count
            }
        else:
            return {"proven": False, "solutions": [], "strategy": strategy,
                    "inference_count": self._inference_count, "error": "Unknown strategy"}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: LEARNING & MEMORY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Experience:
    """A single learning experience, capturing an interaction with the DeepSeek LLM
    or symbolic engine."""
    query: str
    response: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    outcome: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    @property
    def age(self) -> float:
        return time.time() - self.timestamp

    def compute_embedding(self) -> List[float]:
        """Compute a simple feature-based embedding for similarity matching."""
        text = f"{self.query} {self.response}"
        # Character-level frequency vector (simplified embedding)
        features = [0.0] * 26
        for ch in text.lower():
            if 'a' <= ch <= 'z':
                features[ord(ch) - ord('a')] += 1.0
        # Normalize
        mag = math.sqrt(sum(f * f for f in features))
        if mag > 0:
            features = [f / mag for f in features]
        # Add length-normalized complexity feature
        features.append(min(1.0, len(text) / 1000.0))
        features.append(self.importance)
        self.embedding = features
        return features


class EpisodicMemory:
    """Stores and retrieves experiences using importance-weighted recall."""

    def __init__(self, capacity: int = 10000, decay_rate: float = 0.001):
        self.capacity = capacity
        self.decay_rate = decay_rate
        self._experiences: List[Experience] = []
        self._index: Dict[str, List[int]] = defaultdict(list)  # tag -> indices

    @property
    def size(self) -> int:
        return len(self._experiences)

    def store(self, experience: Experience) -> None:
        """Store an experience, evicting oldest if at capacity."""
        experience.compute_embedding()
        self._experiences.append(experience)
        for tag in experience.tags:
            self._index[tag].append(len(self._experiences) - 1)
        if len(self._experiences) > self.capacity:
            self._experiences.pop(0)
            # Rebuild index (simplified)
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index.clear()
        for i, exp in enumerate(self._experiences):
            for tag in exp.tags:
                self._index[tag].append(i)

    def recall_by_tag(self, tag: str, k: int = 5) -> List[Experience]:
        """Recall experiences with a specific tag."""
        indices = self._index.get(tag, [])
        candidates = [self._experiences[i] for i in indices if i < len(self._experiences)]
        candidates.sort(key=lambda e: (e.importance * e.outcome or 0.5) - e.age * self.decay_rate,
                        reverse=True)
        return candidates[:k]

    def recall_similar(self, query_embedding: List[float], k: int = 5
                       ) -> List[Tuple[Experience, float]]:
        """Recall experiences with most similar embeddings (cosine similarity)."""
        if not self._experiences:
            return []

        def cosine_sim(a: List[float], b: List[float]) -> float:
            dot = sum(ai * bi for ai, bi in zip(a, b))
            na = math.sqrt(sum(ai * ai for ai in a))
            nb = math.sqrt(sum(bi * bi for bi in b))
            if na * nb == 0:
                return 0.0
            return dot / (na * nb)

        scored: List[Tuple[float, int]] = []
        for i, exp in enumerate(self._experiences):
            if exp.embedding:
                sim = cosine_sim(query_embedding, exp.embedding)
                scored.append((sim, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, idx in scored[:k]:
            results.append((self._experiences[idx], sim))
        return results

    def all(self) -> List[Experience]:
        return list(self._experiences)

    def summarize(self) -> Dict[str, Any]:
        """Return summary statistics of memory."""
        if not self._experiences:
            return {"size": 0, "avg_importance": 0.0, "avg_outcome": None, "tags": {}}
        return {
            "size": self.size,
            "avg_importance": sum(e.importance for e in self._experiences) / self.size,
            "avg_outcome": (
                sum(e.outcome or 0.5 for e in self._experiences) / self.size
            ),
            "tags": {tag: len(idxs) for tag, idxs in self._index.items()}
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity": self.capacity,
            "decay_rate": self.decay_rate,
            "experiences": [
                {
                    "query": e.query,
                    "response": e.response,
                    "timestamp": e.timestamp,
                    "importance": e.importance,
                    "outcome": e.outcome,
                    "context": e.context,
                    "tags": e.tags,
                    "embedding": e.embedding
                }
                for e in self._experiences
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicMemory":
        mem = cls(capacity=data.get("capacity", 10000),
                  decay_rate=data.get("decay_rate", 0.001))
        for exp_data in data.get("experiences", []):
            exp = Experience(
                query=exp_data["query"],
                response=exp_data["response"],
                timestamp=exp_data.get("timestamp", time.time()),
                importance=exp_data.get("importance", 0.5),
                outcome=exp_data.get("outcome"),
                context=exp_data.get("context", {}),
                tags=exp_data.get("tags", []),
                embedding=exp_data.get("embedding")
            )
            mem._experiences.append(exp)
        mem._rebuild_index()
        return mem


class PatternLearner:
    """Learns transition patterns from sequences of states/actions.

    Uses a Markov-chain model to predict next states given current state.
    This works alongside the DeepSeek LLM to learn interaction patterns.
    """

    def __init__(self, order: int = 1):
        self.order = order
        self.transitions: Dict[Tuple[str, ...], Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._total_transitions: int = 0
        self._last_states: deque = deque(maxlen=order)

    def observe(self, state: str) -> None:
        """Observe a state transition. Maintains a sliding window of order."""
        self._last_states.append(state)
        if len(self._last_states) == self.order:
            key = tuple(self._last_states)
            # Record that this state sequence occurred
            self.transitions[key][state] += 1.0
            self._total_transitions += 1

    def predict_next(self, current_state: str) -> Dict[str, float]:
        """Given current state, predict next state probabilities."""
        context = tuple([current_state])
        if context in self.transitions:
            total = sum(self.transitions[context].values())
            return {s: c / total for s, c in self.transitions[context].items()}
        return {}

    def most_likely_next(self, current_state: str) -> Optional[str]:
        """Return the most likely next state given current state."""
        predictions = self.predict_next(current_state)
        if not predictions:
            return None
        return max(predictions, key=predictions.get)

    def confidence(self, current_state: str) -> float:
        """Return confidence in predictions for this state (0-1)."""
        predictions = self.predict_next(current_state)
        if not predictions:
            return 0.0
        total = sum(predictions.values())
        if total == 0:
            return 0.0
        top = max(predictions.values())
        if self._total_transitions == 0:
            return 0.0
        support = total / self._total_transitions
        return top * support

    def learn(self, sequence: List[str]) -> None:
        """Learn from a complete sequence of states."""
        for i in range(len(sequence)):
            if i == 0:
                self._last_states.append(sequence[i])
            else:
                self.observe(sequence[i])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order": self.order,
            "transitions": {
                "|".join(k): dict(v) for k, v in self.transitions.items()
            },
            "total_transitions": self._total_transitions
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternLearner":
        pl = cls(order=data.get("order", 1))
        for key_str, v in data.get("transitions", {}).items():
            key = tuple(key_str.split("|"))
            pl.transitions[key] = defaultdict(float, v)
        pl._total_transitions = data.get("total_transitions", 0)
        return pl


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: PERSISTENT SELF-IMPROVEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetaParameter:
    """A self-optimizing parameter with adaptive mutation."""
    name: str
    value: float
    min_val: float
    max_val: float
    learning_rate: float = 1.0
    best_value: float = field(init=False)
    best_reward: float = field(init=False, default=-float("inf"))
    history: List[Tuple[float, float]] = field(default_factory=list)  # (value, reward)

    def __post_init__(self) -> None:
        self.best_value = self.value

    def mutate(self, reward: float) -> None:
        """Adjust parameter based on reward signal using evolutionary adaptation."""
        self.history.append((self.value, reward))

        if reward > self.best_reward:
            self.best_reward = reward
            self.best_value = self.value

        # Adaptive mutation: explore more when reward is low
        exploration = max(0.05, 1.0 - reward) * self.learning_rate
        delta = random.gauss(0, exploration * (self.max_val - self.min_val))
        self.value = max(self.min_val, min(self.max_val, self.value + delta))

    def recent_trend(self, window: int = 5) -> float:
        """Return recent reward trend: positive means improving."""
        if len(self.history) < 2:
            return 0.0
        recent = self.history[-window:]
        if len(recent) < 2:
            return 0.0
        return recent[-1][1] - recent[0][1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "learning_rate": self.learning_rate,
            "best_value": self.best_value,
            "best_reward": self.best_reward,
            "history": self.history[-100:]  # keep last 100
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaParameter":
        mp = cls(
            name=data["name"],
            value=data["value"],
            min_val=data["min_val"],
            max_val=data["max_val"],
            learning_rate=data.get("learning_rate", 1.0)
        )
        mp.best_value = data.get("best_value", data["value"])
        mp.best_reward = data.get("best_reward", -float("inf"))
        mp.history = [(v, r) for v, r in data.get("history", [])]
        return mp


class Strategy(Enum):
    """Available reasoning strategies for the meta-cognitive system."""
    LLM_REASONING = "llm_reasoning"
    FORWARD_CHAINING = "forward_chaining"
    BACKWARD_CHAINING = "backward_chaining"
    MEMORY_RECALL = "memory_recall"
    PATTERN_PREDICT = "pattern_predict"


class MetaCognitionEngine:
    """Meta-cognitive self-improvement engine.

    Tracks strategy performance (including DeepSeek LLM calls), adjusts
    parameters, and recommends improvements.
    """

    def __init__(self, epsilon: float = 0.2, gamma: float = 0.9):
        self.epsilon = epsilon  # exploration rate
        self.gamma = gamma      # discount factor
        self.strategies: Dict[Strategy, List[float]] = {
            s: [] for s in Strategy
        }
        self.params: Dict[str, MetaParameter] = {
            'temperature': MetaParameter('temperature', 0.3, 0.0, 2.0),
            'max_tokens': MetaParameter('max_tokens', 1024, 128, 4096, lr=100.0),
            'memory_recall_k': MetaParameter('memory_recall_k', 3, 1, 10),
            'exploration_rate': MetaParameter('exploration_rate', 0.2, 0.01, 0.5),
            'pattern_confidence_threshold': MetaParameter(
                'pattern_confidence_threshold', 0.5, 0.0, 1.0
            ),
        }
        self._episode: int = 0
        self._plateau_counter: int = 0
        self._last_avg_reward: float = 0.0
        self._total_episodes: int = 0

    @property
    def episode(self) -> int:
        return self._episode

    def select_strategy(self, context: Optional[Dict[str, Any]] = None) -> Strategy:
        """Epsilon-greedy strategy selection. Prefers best-performing strategy."""
        self._episode += 1

        if random.random() < self.epsilon:
            return random.choice(list(Strategy))

        # Choose best performing strategy
        best_strategy = Strategy.LLM_REASONING
        best_avg = -float("inf")
        for strategy, rewards in self.strategies.items():
            if len(rewards) >= 3:
                avg = sum(rewards[-10:]) / min(len(rewards), 10)
                if avg > best_avg:
                    best_avg = avg
                    best_strategy = strategy

        return best_strategy

    def record_outcome(self, strategy: Strategy, reward: float) -> None:
        """Record the reward for a strategy execution."""
        self.strategies[strategy].append(reward)
        self._total_episodes += 1

    def get_strategy_performance(self) -> Dict[str, float]:
        """Get average reward per strategy."""
        result = {}
        for strategy, rewards in self.strategies.items():
            if rewards:
                avg = sum(rewards[-20:]) / min(len(rewards), 20)
                result[strategy.value] = round(avg, 4)
            else:
                result[strategy.value] = 0.0
        return result

    def improve(self) -> Dict[str, Any]:
        """Run one meta-improvement cycle.

        Returns a reflection dict with performance analysis and suggestions.
        """
        # Update parameters based on recent performance
        perf = self.get_strategy_performance()
        avg_reward = sum(perf.values()) / max(len(perf), 1)

        # Plateau detection: if avg reward stagnates
        if abs(avg_reward - self._last_avg_reward) < 0.02:
            self._plateau_counter += 1
        else:
            self._plateau_counter = 0

        if self._plateau_counter > 5:
            # Boost exploration to escape plateau
            self.epsilon = min(0.5, self.epsilon * 1.5)
            # Mutate all parameters
            for param in self.params.values():
                param.mutate(avg_reward)
            self._plateau_counter = 0
            plateau_escaped = True
        else:
            # Normal evolutionary update
            for param in self.params.values():
                param.mutate(avg_reward)
            plateau_escaped = False

        self._last_avg_reward = avg_reward

        # Generate improvement suggestions
        suggestions = []
        best_strat = max(perf, key=perf.get)
        worst_strat = min(perf, key=perf.get)
        strategy_delta = perf[best_strat] - perf[worst_strat]

        if strategy_delta > 0.1:
            suggestions.append(
                f"Strategy gap: {best_strat}({perf[best_strat]:.3f}) vs "
                f"{worst_strat}({perf[worst_strat]:.3f}). "
                f"Consider focusing on {best_strat}."
            )

        if plateau_escaped:
            suggestions.append(
                f"Performance plateau detected. Exploration increased to "
                f"{self.epsilon:.2f}. Parameters mutated to seek improvement."
            )

        # Parameter trends
        for name, param in self.params.items():
            trend = param.recent_trend()
            if trend > 0.1:
                suggestions.append(
                    f"Parameter '{name}' showing positive trend ({trend:.3f}). "
                    f"Current value: {param.value:.3f}"
                )
            elif trend < -0.1:
                suggestions.append(
                    f"Parameter '{name}' degrading ({trend:.3f}). "
                    f"Reset to best value: {param.best_value:.3f}"
                )
                param.value = param.best_value

        return {
            "episode": self._episode,
            "avg_reward": round(avg_reward, 4),
            "plateau_escaped": plateau_escaped,
            "epsilon": round(self.epsilon, 4),
            "strategy_performance": perf,
            "best_strategy": best_strat,
            "worst_strategy": worst_strat,
            "strategy_delta": round(strategy_delta, 4),
            "suggestions": suggestions,
            "parameters": {n: round(p.value, 4) for n, p in self.params.items()}
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epsilon": self.epsilon,
            "gamma": self.gamma,
            "strategies": {
                s.value: rewards[-500:]
                for s, rewards in self.strategies.items()
            },
            "params": {n: p.to_dict() for n, p in self.params.items()},
            "episode": self._episode,
            "plateau_counter": self._plateau_counter,
            "last_avg_reward": self._last_avg_reward,
            "total_episodes": self._total_episodes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaCognitionEngine":
        meta = cls(epsilon=data.get("epsilon", 0.2), gamma=data.get("gamma", 0.9))
        for s_val, rewards in data.get("strategies", {}).items():
            try:
                s = Strategy(s_val)
                meta.strategies[s] = rewards
            except ValueError:
                pass
        for n, p_data in data.get("params", {}).items():
            meta.params[n] = MetaParameter.from_dict(p_data)
        meta._episode = data.get("episode", 0)
        meta._plateau_counter = data.get("plateau_counter", 0)
        meta._last_avg_reward = data.get("last_avg_reward", 0.0)
        meta._total_episodes = data.get("total_episodes", 0)
        return meta


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: CORE AGENT — DeepSeekV4FlashAgent
# ═══════════════════════════════════════════════════════════════════════════════

class DeepSeekV4FlashAgent:
    """A self-improving AI agent **based on the real DeepSeek-v4-flash LLM**.

    The DeepSeek-v4-flash model (via API at api.deepseek.com) serves as the
    PRIMARY reasoning engine. The symbolic inference engine acts as a fallback
    when the API is unavailable (no API key configured or network error).

    Attributes:
        llm: DeepSeekAPI client for the real deepseek-v4-flash model
        symbolic: InferenceEngine fallback (symbolic Horn-clause reasoning)
        memory: EpisodicMemory for storing and recalling experiences
        patterns: PatternLearner for Markov-chain transition learning
        meta: MetaCognitionEngine for self-improvement
    """

    def __init__(self, api_key: Optional[str] = None,
                 memory_capacity: int = 10000):
        # ─── DeepSeek-v4-flash LLM (PRIMARY reasoning engine) ────────
        self.llm = DeepSeekAPI(api_key=api_key)

        # ─── Symbolic fallback (used when DeepSeek API unavailable) ───
        self.symbolic = InferenceEngine()

        # ─── Learning systems ────────────────────────────────────────
        self.memory = EpisodicMemory(capacity=memory_capacity)
        self.patterns = PatternLearner(order=2)

        # ─── Meta-cognitive self-improvement ─────────────────────────
        self.meta = MetaCognitionEngine()

        # ─── Agent identity and tracking ─────────────────────────────
        self.session_id = hashlib.sha256(
            str(time.time()).encode()
        ).hexdigest()[:16]
        self.created_at = time.time()
        self._total_queries: int = 0
        self._successful_queries: int = 0
        self._last_query_time: Optional[float] = None

        # ─── Default knowledge base ──────────────────────────────────
        self._init_default_knowledge()

    def _init_default_knowledge(self) -> None:
        """Initialize the symbolic knowledge base with common inference rules."""
        # mortal(X) :- human(X)
        self.symbolic.add_clause(Clause(
            Term("mortal", (Term("_X"),)),
            (Term("human", (Term("_X"),)),)
        ))

    @property
    def using_deepseek_llm(self) -> bool:
        """Whether the agent is actively using the DeepSeek-v4-flash LLM."""
        return self.llm.available

    # ─── REASONING ──────────────────────────────────────────────────────

    def reason(self, query: str, strategy: Optional[str] = None,
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform logical reasoning using the DeepSeek-v4-flash LLM
        (primary) or symbolic fallback.

        Args:
            query: The query to reason about.
            strategy: Reasoning strategy override. If None, meta selects best.
            context: Optional reasoning context/facts.

        Returns:
            Dict with reasoning result and metadata.
        """
        self._total_queries += 1
        self._last_query_time = time.time()
        start_time = time.time()

        if strategy is None:
            strategy = self.meta.select_strategy(context).value

        result: Dict[str, Any] = {
            "query": query,
            "strategy": strategy,
            "start_time": start_time,
            "using_deepseek_llm": False
        }

        try:
            # ── PRIMARY: DeepSeek-v4-flash LLM ───────────────────────
            if strategy == Strategy.LLM_REASONING.value and self.llm.available:
                llm_result = self.llm.reason(query, context)
                result["answer"] = llm_result["answer"]
                result["confidence"] = llm_result["confidence"]
                result["using_deepseek_llm"] = True
                result["tokens_used"] = llm_result["tokens_used"]
                result["proven"] = llm_result["answer"] is not None
                result["raw_llm_response"] = llm_result

                if llm_result["answer"] is not None:
                    self._successful_queries += 1

            # ── FALLBACK: Memory recall ─────────────────────────────
            elif strategy == Strategy.MEMORY_RECALL.value and self.memory.size > 0:
                query_features = [0.0] * 26
                for ch in query.lower():
                    if 'a' <= ch <= 'z':
                        query_features[ord(ch) - ord('a')] += 1.0
                mag = math.sqrt(sum(f * f for f in query_features))
                if mag > 0:
                    query_features = [f / mag for f in query_features]
                query_features.append(min(1.0, len(query) / 1000.0))
                query_features.append(0.5)

                similar = self.memory.recall_similar(query_features, k=3)
                if similar:
                    result["answer"] = similar[0][0].response
                    result["confidence"] = similar[0][1]
                    result["proven"] = True
                    result["recalled_from"] = similar[0][0].query
                    self._successful_queries += 1
                else:
                    result["answer"] = None
                    result["proven"] = False

            # ── FALLBACK: Pattern prediction ─────────────────────────
            elif strategy == Strategy.PATTERN_PREDICT.value:
                predicted = self.patterns.most_likely_next(query)
                if predicted:
                    result["answer"] = predicted
                    result["confidence"] = self.patterns.confidence(query)
                    result["proven"] = True
                    self._successful_queries += 1
                else:
                    result["answer"] = None
                    result["proven"] = False

            # ── FALLBACK: Symbolic forward/backward chaining ─────────
            elif strategy in (Strategy.FORWARD_CHAINING.value,
                              Strategy.BACKWARD_CHAINING.value):
                goal = self._parse_query(query)
                if goal:
                    solution = self.symbolic.solve(goal, strategy)
                    result["proven"] = solution["proven"]
                    result["solutions"] = [
                        {k: str(v) for k, v in s.items()}
                        for s in solution["solutions"]
                    ]
                    result["inference_count"] = solution.get("inference_count")
                    if solution["proven"]:
                        self._successful_queries += 1
                        result["answer"] = f"Goal proven: {goal}"
                    else:
                        result["answer"] = f"Goal not proven: {goal}"
                else:
                    result["proven"] = False
                    result["answer"] = None

            # ── ULTIMATE FALLBACK: Use LLM even if not preferred ─────
            else:
                if self.llm.available:
                    llm_result = self.llm.reason(query, context)
                    result["answer"] = llm_result["answer"]
                    result["confidence"] = llm_result["confidence"]
                    result["using_deepseek_llm"] = True
                    result["proven"] = llm_result["answer"] is not None
                    if llm_result["answer"] is not None:
                        self._successful_queries += 1
                else:
                    result["answer"] = "No reasoning strategy available. " \
                                       "Configure a DeepSeek API key or add facts to the symbolic KB."
                    result["proven"] = False

        except Exception as e:
            result["error"] = str(e)
            result["proven"] = False

        result["elapsed"] = time.time() - start_time

        # Store as experience
        importance = 0.8 if result.get("proven", False) else 0.3
        self._store_experience(query, result, importance)

        return result

    def _parse_query(self, query: str) -> Optional[Term]:
        """Parse a simple query string into a Term.

        Supports: 'mortal(X)', 'mortal(socrates)', 'human(socrates)'
        """
        query = query.strip().rstrip(".!?")
        if "(" in query and query.endswith(")"):
            name = query[:query.index("(")]
            args_str = query[query.index("(") + 1:-1]
            args = []
            for arg in args_str.split(","):
                arg = arg.strip()
                if arg and arg[0].isupper() or arg.startswith("_"):
                    args.append(Term(f"_{arg}"))
                else:
                    args.append(Term(arg))
            return Term(name, tuple(args))
        return None

    def _store_experience(self, query: str, result: Dict[str, Any],
                          importance: float) -> None:
        """Store a reasoning experience in memory."""
        exp = Experience(
            query=query,
            response=result.get("answer", "") or str(result.get("solutions", "")),
            importance=importance,
            outcome=1.0 if result.get("proven", False) else 0.0,
            context={
                "strategy": result.get("strategy", "unknown"),
                "using_deepseek_llm": result.get("using_deepseek_llm", False),
                "elapsed": result.get("elapsed", 0.0),
            },
            tags=[result.get("strategy", "unknown"), "reasoning"]
        )
        self.memory.store(exp)
        self.patterns.observe(result.get("strategy", "unknown"))

    # ─── LEARNING ────────────────────────────────────────────────────────

    def learn(self, data: Any, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Learn from arbitrary data. Works with both LLM and symbolic modes.

        When the DeepSeek LLM is available, it can also be used to
        analyze and summarize the data being learned.

        Args:
            data: The data to learn from (string, dict, or list).
            tags: Optional tags to categorize the learning.

        Returns:
            Dict with learning result.
        """
        tags = tags or ["general"]
        result = {
            "timestamp": time.time(),
            "tags": tags,
            "stored": False,
            "analyzed_by_llm": False
        }

        # Convert data to text for storage
        if isinstance(data, (dict, list)):
            text = json.dumps(data, default=str)
        elif isinstance(data, str):
            text = data
        else:
            text = str(data)

        # Optionally analyze with DeepSeek LLM
        analysis = None
        if self.llm.available:
            system_prompt = (
                "You are DeepSeek-v4-flash, a learning and analysis engine. "
                "Analyze the following data and provide: "
                "1. A brief summary (1-2 sentences)\n"
                "2. Key patterns or insights\n"
                "3. Suggested tags for categorization\n"
                "Format: SUMMARY: ...\nPATTERNS: ...\nTAGS: ..."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this data:\n\n{text[:3000]}"}
            ]
            analysis = self.llm.chat(messages, temperature=0.3, max_tokens=512)
            result["analyzed_by_llm"] = True
            result["analysis"] = analysis

        # Store as experience
        exp = Experience(
            query=f"learn:{tags[0]}" if tags else "learn:general",
            response=analysis or text,
            importance=0.6,
            context={"raw_data": text[:500]},
            tags=tags
        )
        self.memory.store(exp)
        result["stored"] = True
        result["memory_size"] = self.memory.size

        # Learn patterns in the data if it's a sequence
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            self.patterns.learn(data)
            result["patterns_learned"] = len(data)

        return result

    def recall(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Recall relevant past experiences."""
        # Build embedding from query
        query_features = [0.0] * 26
        for ch in query.lower():
            if 'a' <= ch <= 'z':
                query_features[ord(ch) - ord('a')] += 1.0
        mag = math.sqrt(sum(f * f for f in query_features))
        if mag > 0:
            query_features = [f / mag for f in query_features]
        query_features.append(min(1.0, len(query) / 1000.0))
        query_features.append(0.5)

        similar = self.memory.recall_similar(query_features, k=k)
        results = []
        for exp, sim in similar:
            results.append({
                "query": exp.query,
                "response": exp.response[:200],
                "similarity": round(sim, 4),
                "importance": exp.importance,
                "outcome": exp.outcome,
                "tags": exp.tags,
                "age": round(exp.age, 2)
            })
        return results

    # ─── SELF-IMPROVEMENT ───────────────────────────────────────────────

    def improve(self) -> Dict[str, Any]:
        """Run the meta-cognitive self-improvement cycle.

        Evaluates past performance across all strategies (including
        DeepSeek LLM reasoning), adjusts parameters, and returns insights.

        Returns:
            Reflection dict with performance analysis and suggestions.
        """
        return self.meta.improve()

    def reflect(self) -> Dict[str, Any]:
        """Generate a comprehensive self-reflection report.

        Combines memory statistics, strategy performance, LLM usage stats,
        and meta-cognitive analysis into a single report.
        """
        strategy_perf = self.meta.get_strategy_performance()
        memory_summary = self.memory.summarize()
        llm_stats = self.llm.get_stats()

        # Use DeepSeek LLM for self-reflection if available
        llm_reflection = None
        if self.llm.available:
            report_data = json.dumps({
                "strategy_performance": strategy_perf,
                "memory": memory_summary,
                "llm_api_stats": llm_stats,
                "total_queries": self._total_queries,
                "success_rate": round(
                    self._successful_queries / max(self._total_queries, 1), 3
                )
            }, indent=2)
            messages = [
                {"role": "system", "content":
                 "You are DeepSeek-v4-flash reflecting on your own performance. "
                 "Analyze the following report and provide:\n"
                 "1. Your assessment of current performance\n"
                 "2. What's working well\n"
                 "3. What needs improvement\n"
                 "4. Concrete next actions for self-improvement\n"
                 "Be honest and specific."},
                {"role": "user", "content": f"Self-reflection data:\n\n{report_data}"}
            ]
            llm_reflection = self.llm.chat(messages, temperature=0.4, max_tokens=1024)

        return {
            "agent_name": "DeepSeek-v4-flash AI Agent",
            "session_id": self.session_id,
            "uptime": round(time.time() - self.created_at, 2),
            "using_deepseek_llm": self.using_deepseek_llm,
            "total_queries": self._total_queries,
            "successful_queries": self._successful_queries,
            "success_rate": round(
                self._successful_queries / max(self._total_queries, 1), 3
            ),
            "strategy_performance": strategy_perf,
            "memory": memory_summary,
            "llm_api": llm_stats,
            "meta_parameters": {
                n: round(p.value, 4)
                for n, p in self.meta.params.items()
            },
            "llm_self_reflection": llm_reflection
        }

    def run_pipeline(self, query: str,
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the full reason -> learn -> improve pipeline for a query.

        This is the agent's main autonomous cycle:

        1. REASON: Use DeepSeek-v4-flash LLM (primary) or symbolic fallback
        2. LEARN: Store the experience in episodic memory
        3. IMPROVE: Run meta-cognitive improvement

        Args:
            query: The query to reason about.
            context: Optional reasoning context.

        Returns:
            Dict with pipeline results.
        """
        # Step 1: Reason (uses DeepSeek-v4-flash LLM as primary engine)
        reasoning_result = self.reason(query, context=context)

        # Step 2: Learn from the result
        learning_result = self.learn(
            data={
                "query": query,
                "result": reasoning_result.get("answer", ""),
                "proven": reasoning_result.get("proven", False),
                "using_deepseek_llm": reasoning_result.get("using_deepseek_llm", False)
            },
            tags=["pipeline", reasoning_result.get("strategy", "unknown")]
        )

        # Step 3: Improve (every 3 queries)
        improvement_result = None
        if self._total_queries % 3 == 0:
            improvement_result = self.improve()

        return {
            "reasoning": reasoning_result,
            "learning": learning_result,
            "improvement": improvement_result
        }

    # ─── KNOWLEDGE BASE MANAGEMENT ──────────────────────────────────────

    def add_fact(self, fact_str: str) -> str:
        """Add a fact to the symbolic knowledge base."""
        term = self._parse_query(fact_str)
        if term:
            self.symbolic.add_clause(Clause(term))
            self.symbolic.add_clause(Clause(
                term, ()
            ))
            return f"Added fact: {fact_str}"
        return f"Could not parse: {fact_str}"

    def add_rule(self, head_str: str, body_strs: List[str]) -> str:
        """Add a rule to the symbolic knowledge base."""
        head = self._parse_query(head_str)
        body = [b for b_str in body_strs
                for b in [self._parse_query(b_str)]
                if b is not None]
        if head and body:
            clause = Clause(head, tuple(body))
            self.symbolic.add_clause(clause)
            return f"Added rule: {head_str} :- {', '.join(body_strs)}"
        return f"Could not parse rule"

    # ─── PERSISTENCE ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entire agent state for persistence."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "total_queries": self._total_queries,
            "successful_queries": self._successful_queries,
            "llm": self.llm.to_dict(),
            "memory": self.memory.to_dict(),
            "patterns": self.patterns.to_dict(),
            "meta": self.meta.to_dict(),
        }

    def save_state(self, filepath: str) -> bool:
        """Save agent state to a JSON file for persistence across sessions."""
        try:
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            return True
        except (IOError, OSError) as e:
            print(f"Save error: {e}")
            return False

    @classmethod
    def load_state(cls, filepath: str,
                   api_key: Optional[str] = None) -> "DeepSeekV4FlashAgent":
        """Load agent state from a JSON file, restoring memory and learning."""
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (IOError, OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Could not load state: {e}")

        agent = cls(api_key=api_key)
        agent.session_id = data.get("session_id", agent.session_id)
        agent.created_at = data.get("created_at", agent.created_at)
        agent._total_queries = data.get("total_queries", 0)
        agent._successful_queries = data.get("successful_queries", 0)

        if "llm" in data:
            agent.llm = DeepSeekAPI.from_dict(data["llm"], api_key=api_key)
        if "memory" in data:
            agent.memory = EpisodicMemory.from_dict(data["memory"])
        if "patterns" in data:
            agent.patterns = PatternLearner.from_dict(data["patterns"])
        if "meta" in data:
            agent.meta = MetaCognitionEngine.from_dict(data["meta"])

        return agent

    def __repr__(self) -> str:
        llm_status = "DeepSeek-v4-flash LLM active" if self.using_deepseek_llm else \
                     "DeepSeek-v4-flash LLM unavailable (using symbolic fallback)"
        return (
            f"DeepSeekV4FlashAgent("
            f"session={self.session_id}, "
            f"{llm_status}, "
            f"queries={self._total_queries}, "
            f"memory={self.memory.size})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: DEMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def demonstration():
    """Run a full demonstration of the DeepSeek-v4-flash AI Agent.

    Shows:
    1. Creation with actual DeepSeek-v4-flash LLM connection
    2. LLM-powered logical reasoning
    3. Learning from interactions
    4. Persistent self-improvement
    """

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     DeepSeek-v4-flash AI Agent Demonstration                ║")
    print("║     Powered by: DeepSeek-v4-flash LLM via API               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # ── Create agent (with or without API key) ─────────────────────────
    # To use the actual DeepSeek-v4-flash LLM, set:
    #   agent = DeepSeekV4FlashAgent(api_key="your-api-key-here")
    #
    # Without an API key, the agent uses symbolic fallback:

    print("Creating DeepSeekV4FlashAgent...")
    agent = DeepSeekV4FlashAgent()
    print(f"  Agent: {agent}")
    print(f"  Using DeepSeek-v4-flash LLM: {agent.using_deepseek_llm}")
    print(f"  (Set api_key= to enable the real DeepSeek-v4-flash model)")
    print()

    # ── Add knowledge base ─────────────────────────────────────────────
    print("1. INITIALIZING KNOWLEDGE BASE")
    print("   Adding facts for symbolic reasoning (fallback)...")
    for fact in ["human(socrates)", "human(plato)", "mortal(achilles)",
                 "greek(socrates)", "greek(plato)", "philosopher(socrates)"]:
        print(f"   + {fact}")
        agent.add_fact(fact)
    print(f"   KB ready. Symbolic engine has facts and rules.")
    print()

    # ── Test reasoning ──────────────────────────────────────────────────
    print("2. TESTING LOGICAL REASONING")
    print()

    queries = [
        "mortal(socrates)",
        "mortal(X)",
        "greek(socrates)",
        "philosopher(plato)"
    ]

    for query in queries:
        print(f"   Query: {query}")
        result = agent.reason(query)

        if agent.using_deepseek_llm:
            print(f"   Engine: DeepSeek-v4-flash LLM")
        else:
            print(f"   Engine: symbolic (LLM unavailable)")

        proven = result.get("proven", False)
        if result.get("using_deepseek_llm") and result.get("answer"):
            print(f"   Answer: {result['answer'][:200]}...")
            print(f"   Confidence: {result.get('confidence', 0)}")
        elif result.get("solutions"):
            for sol in result.get("solutions", []):
                print(f"   Solution: {sol}")
        else:
            print(f"   Proven: {proven}")

        print(f"   Elapsed: {result.get('elapsed', 0):.6f}s")
        print()

    # ── Test learning ───────────────────────────────────────────────────
    print("3. TESTING LEARNING & MEMORY")
    print()

    learn_data = [
        ("socrates was a greek philosopher who taught plato", ["history", "philosophy"]),
        ("plato wrote the republic and founded the academy", ["history", "philosophy"]),
        ("aristotle was a student of plato and tutor of alexander", ["history", "philosophy"]),
    ]

    for text, tags in learn_data:
        result = agent.learn(text, tags=tags)
        print(f"   Learned: {text[:50]}...")
        print(f"   Tags: {tags}")
        if result.get("analyzed_by_llm"):
            print(f"   Analyzed by DeepSeek-v4-flash: YES")
        print(f"   Memory size: {result.get('memory_size')}")
        print()

    # Test recall
    print("   Testing recall...")
    recalled = agent.recall("who taught plato?", k=3)
    for r in recalled:
        print(f"     -> [{r['similarity']:.3f}] {r['query'][:50]}...")
    print()

    # ── Test self-improvement ──────────────────────────────────────────
    print("4. TESTING PERSISTENT SELF-IMPROVEMENT")
    print()

    print("   Running 30 simulated reasoning episodes...")
    strategies = ["llm_reasoning", "forward_chaining", "backward_chaining",
                  "memory_recall", "pattern_predict"]
    for episode in range(30):
        strat = strategies[episode % len(strategies)]
        if strat in ("llm_reasoning", "backward_chaining"):
            reward = 0.7 + random.uniform(-0.2, 0.2)
        else:
            reward = 0.4 + random.uniform(-0.2, 0.2)
        agent.meta.record_outcome(Strategy(strat), reward)

    reflection = agent.improve()
    print(f"   Episode: {reflection['episode']}")
    print(f"   Average reward: {reflection['avg_reward']}")
    print(f"   Epsilon (exploration): {reflection['epsilon']}")
    print(f"   Best strategy: {reflection['best_strategy']} "
          f"({reflection['strategy_performance'].get(reflection['best_strategy'], 0):.3f})")
    print(f"   Worst strategy: {reflection['worst_strategy']} "
          f"({reflection['strategy_performance'].get(reflection['worst_strategy'], 0):.3f})")
    print(f"   Strategy gap: {reflection['strategy_delta']}")
    if reflection['suggestions']:
        print(f"   Suggestions:")
        for s in reflection['suggestions']:
            print(f"     * {s}")
    print()

    # ── Full pipeline test ─────────────────────────────────────────────
    print("5. FULL REASON -> LEARN -> IMPROVE PIPELINE")
    print()

    for i, query in enumerate([
        "mortal(socrates)",
        "greek(plato)",
        "philosopher(aristotle)"
    ]):
        print(f"   Pipeline run {i+1}: '{query}'")
        pipeline_result = agent.run_pipeline(query)

        reasoning = pipeline_result.get("reasoning", {})
        learning = pipeline_result.get("learning", {})
        improvement = pipeline_result.get("improvement")

        if reasoning.get("using_deepseek_llm"):
            print(f"     Engine: DeepSeek-v4-flash LLM")
            print(f"     Answer: {str(reasoning.get('answer', ''))[:150]}...")
        else:
            print(f"     Engine: symbolic fallback")
            print(f"     Proven: {reasoning.get('proven')}")
        print(f"     Learned: {learning.get('stored')}")
        if improvement:
            print(f"     Improved: episode {improvement['episode']}, "
                  f"avg_reward={improvement['avg_reward']}")
        print()

    # ── Final reflection ────────────────────────────────────────────────
    print("6. AGENT SELF-REFLECTION")
    print()

    reflection_report = agent.reflect()
    print(f"   Agent: {reflection_report['agent_name']}")
    print(f"   Session: {reflection_report['session_id']}")
    print(f"   Uptime: {reflection_report['uptime']}s")
    print(f"   Using DeepSeek LLM: {reflection_report['using_deepseek_llm']}")
    print(f"   Queries: {reflection_report['total_queries']} "
          f"(success rate: {reflection_report['success_rate']})")
    print(f"   Strategy performance:")
    for strat, perf in reflection_report['strategy_performance'].items():
        bar = chr(9608) * int(perf * 20)
        print(f"     {strat:25s} {bar} {perf:.3f}")

    if reflection_report.get('llm_self_reflection'):
        print(f"\n   DeepSeek-v4-flash self-reflection:")
        print(f"   {reflection_report['llm_self_reflection'][:300]}...")

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     DEMONSTRATION COMPLETE                                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    demonstration()
