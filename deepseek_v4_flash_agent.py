#!/usr/bin/env python3
"""
DeepSeek-v4-flash AI Agent
==========================
A self-improving, logically-reasoning autonomous agent with persistent
learning, built in pure Python.

Attributes:
  (1) Logical Reasoning  — Symbolic horn-clause inference engine
  (2) Learn              — Experience-weighted memory with adaptive recall
  (3) Persistent Self-Improvement — Meta-cognitive strategy optimizer
  (4) Python Language    — Zero external dependencies beyond stdlib
"""

from __future__ import annotations

import json
import time
import random
import heapq
import math
import hashlib
import itertools
import dataclasses
import threading
import os
import re
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Callable, Set, Union, Iterator
from abc import ABC, abstractmethod


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1 — LOGICAL REASONING ENGINE
# ═══════════════════════════════════════════════════════════════════════

class Term:
    """A logical term: either a constant, a variable, or a compound term."""
    def __init__(self, functor: str, args: Optional[List[Term]] = None):
        self.functor = functor
        self.args = args if args is not None else []
        self._hash = None

    @staticmethod
    def constant(value: Any) -> Term:
        return Term(str(value))

    @staticmethod
    def variable(name: str) -> Term:
        t = Term(name)
        t.is_variable = True
        return t

    def is_var(self) -> bool:
        return hasattr(self, 'is_variable') and self.is_variable

    def __repr__(self) -> str:
        if self.is_var():
            return f'?{self.functor}'
        if not self.args:
            return self.functor
        return f'{self.functor}({", ".join(repr(a) for a in self.args)})'

    def __eq__(self, other):
        if not isinstance(other, Term):
            return False
        if self.is_var() or other.is_var():
            return self.functor == other.functor and self.is_var() == other.is_var()
        return self.functor == other.functor and self.args == other.args

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.functor, tuple(self.args), self.is_var()))
        return self._hash

    def substitute(self, mapping: Dict[str, Term]) -> Term:
        if self.is_var():
            return mapping.get(self.functor, self)
        if not self.args:
            return self
        return Term(self.functor, [a.substitute(mapping) for a in self.args])


class Clause:
    """A Horn clause: Head :- Body1, Body2, ..., BodyN.
    A fact is a clause with no body (Head :- True)."""
    def __init__(self, head: Term, body: Optional[List[Term]] = None):
        self.head = head
        self.body = body if body is not None else []
        self.id = None
        self.weight = 1.0  # For learnable rule weighting

    def is_fact(self) -> bool:
        return len(self.body) == 0

    def __repr__(self) -> str:
        if self.is_fact():
            return f'{self.head}.'
        return f'{self.head} :- {", ".join(repr(b) for b in self.body)}.'


def unify(t1: Term, t2: Term, mapping: Optional[Dict[str, Term]] = None) -> Optional[Dict[str, Term]]:
    """Unify two terms and return the most general unifier (mapping), or None."""
    if mapping is None:
        mapping = {}

    if t1 == t2:
        return mapping

    if t1.is_var():
        return _unify_var(t1, t2, mapping)
    if t2.is_var():
        return _unify_var(t2, t1, mapping)

    if t1.functor != t2.functor or len(t1.args) != len(t2.args):
        return None

    for a1, a2 in zip(t1.args, t2.args):
        mapping = unify(a1, a2, mapping)
        if mapping is None:
            return None
    return mapping


def _unify_var(var: Term, term: Term, mapping: Dict[str, Term]) -> Optional[Dict[str, Term]]:
    if var.functor in mapping:
        return unify(mapping[var.functor], term, mapping)
    # occurs check (simplified)
    def _occurs(v, t):
        if v == t:
            return True
        return any(_occurs(v, a) for a in t.args)
    if not term.is_var() and _occurs(var, term):
        return None
    mapping = dict(mapping)
    mapping[var.functor] = term
    return mapping


class InferenceEngine:
    """Forward and backward chaining inference engine over Horn clauses."""

    def __init__(self):
        self.facts: List[Term] = []
        self.rules: List[Clause] = []
        self.derivation_trace: List[Dict] = []

    def assert_fact(self, fact: Term) -> None:
        if fact not in self.facts:
            self.facts.append(fact)

    def assert_rule(self, rule: Clause) -> None:
        self.rules.append(rule)

    def retract(self, term: Term) -> None:
        self.facts = [f for f in self.facts if f != term]
        self.rules = [r for r in self.rules if r.head != term]

    # ── Forward Chaining ──────────────────────────────────────────

    def forward_chain(self, max_iterations: int = 100) -> List[Term]:
        """Derive all facts reachable from current facts + rules."""
        derived = []
        changed = True
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            for rule in self.rules:
                if all(self._query_fact(b) for b in rule.body):
                    if rule.head not in self.facts and rule.head not in derived:
                        derived.append(rule.head)
                        self.facts.append(rule.head)
                        changed = True
                        self.derivation_trace.append({
                            'step': len(self.derivation_trace),
                            'rule': repr(rule),
                            'derived': repr(rule.head),
                            'method': 'forward_chain'
                        })
        return derived

    def _query_fact(self, goal: Term) -> bool:
        """Check if a ground goal matches any fact."""
        for fact in self.facts:
            if unify(goal, fact, {}) is not None:
                return True
        return False

    # ── Backward Chaining ─────────────────────────────────────────

    def backward_chain(self, goal: Term, max_depth: int = 20) -> List[Dict[str, Term]]:
        """Prove a goal via backward chaining. Returns list of bindings."""
        solutions = []
        visited = set()

        def _prove(g: Term, mapping: Dict[str, Term], depth: int, path: List[str]):
            if depth > max_depth:
                return
            key = (repr(g), frozenset(mapping.items()))
            if key in visited:
                return
            visited.add(key)

            g_sub = g.substitute(mapping)

            # Check facts
            for fact in self.facts:
                m = unify(g_sub, fact, dict(mapping))
                if m is not None:
                    if g_sub.is_var() or (not g_sub.is_var() and m is not None):
                        solutions.append(m)
                        self.derivation_trace.append({
                            'step': len(self.derivation_trace),
                            'goal': repr(g),
                            'fact': repr(fact),
                            'bindings': {k: repr(v) for k, v in m.items()},
                            'method': 'backward_chain'
                        })
                        continue

            # Check rules
            for rule in self.rules:
                m = unify(g_sub, rule.head, dict(mapping))
                if m is not None:
                    # Prove all body goals
                    sub_goals = [b.substitute(m) for b in rule.body]
                    current_mapping = m
                    success = True
                    for sg in sub_goals:
                        # Try to prove each subgoal
                        sg_mapping = None
                        for fact in self.facts:
                            fm = unify(sg, fact, dict(current_mapping))
                            if fm is not None:
                                sg_mapping = fm
                                break
                        if sg_mapping is None:
                            # Try recursive rule application
                            for sub_rule in self.rules:
                                rm = unify(sg, sub_rule.head, dict(current_mapping))
                                if rm is not None:
                                    sg_mapping = rm
                                    break
                        if sg_mapping is not None:
                            current_mapping = sg_mapping
                        else:
                            success = False
                            break

                    if success:
                        solutions.append(current_mapping)
                        self.derivation_trace.append({
                            'step': len(self.derivation_trace),
                            'goal': repr(g),
                            'rule': repr(rule),
                            'bindings': {k: repr(v) for k, v in current_mapping.items()},
                            'method': 'backward_chain'
                        })

        _prove(goal, {}, 0, [])
        return solutions

    def query(self, goal: Term) -> bool:
        """Convenience: return True if goal is provable."""
        return len(self.backward_chain(goal)) > 0

    def explain(self, goal: Term) -> List[str]:
        """Return a human-readable explanation of how a goal was proven."""
        _ = self.backward_chain(goal)
        steps = [t for t in self.derivation_trace if t['method'] == 'backward_chain'
                 and t['goal'] == repr(goal)]
        return [f"Step {s['step']}: {s['goal']} ← {s.get('rule', s.get('fact', '?'))}"
                for s in steps[-5:]]

    def reset_trace(self) -> None:
        self.derivation_trace = []


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2 — LEARNING & MEMORY
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Experience:
    """A single piece of learned experience, with importance weighting."""
    id: str
    timestamp: float
    input_context: Dict[str, Any]
    action_taken: str
    outcome: str
    reward: float
    importance: float = 1.0
    features: Dict[str, float] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: float = 0.0
    consolidated: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> Experience:
        return Experience(**d)


class EpisodicMemory:
    """Stores and retrieves experiences with importance-weighted decay."""

    def __init__(self, capacity: int = 10000, decay_rate: float = 0.001):
        self.capacity = capacity
        self.decay_rate = decay_rate
        self.experiences: Dict[str, Experience] = {}
        self.importance_queue: List[Tuple[float, str]] = []  # (neg_importance, id)

    def store(self, experience: Experience) -> None:
        """Store an experience, evicting the least important if at capacity."""
        if len(self.experiences) >= self.capacity:
            # Evict lowest importance
            while self.importance_queue:
                neg_imp, eid = heapq.heappop(self.importance_queue)
                if eid in self.experiences:
                    del self.experiences[eid]
                    break

        self.experiences[experience.id] = experience
        heapq.heappush(self.importance_queue, (-experience.importance, experience.id))

    def retrieve_similar(self, query_features: Dict[str, float],
                         top_k: int = 10) -> List[Experience]:
        """Retrieve top-k most similar experiences by feature cosine similarity."""
        scored: List[Tuple[float, Experience]] = []

        for exp in self.experiences.values():
            if not exp.features:
                continue
            sim = self._cosine_similarity(query_features, exp.features)
            if sim > 0:
                scored.append((sim * exp.importance, exp))

        scored.sort(key=lambda x: -x[0])
        results = [exp for _, exp in scored[:top_k]]
        for exp in results:
            exp.access_count += 1
            exp.last_accessed = time.time()
        return results

    def retrieve_by_reward(self, min_reward: float = 0.5,
                           top_k: int = 10) -> List[Experience]:
        """Retrieve highest-reward experiences."""
        candidates = [e for e in self.experiences.values() if e.reward >= min_reward]
        candidates.sort(key=lambda e: -e.reward)
        return candidates[:top_k]

    def _cosine_similarity(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        keys = set(a.keys()) & set(b.keys())
        if not keys:
            return 0.0
        dot = sum(a[k] * b[k] for k in keys)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def consolidate(self) -> int:
        """Periodic consolidation: merge very similar low-importance experiences."""
        merged = 0
        exps = list(self.experiences.values())
        for i, e1 in enumerate(exps):
            if e1.consolidated or e1.importance < 0.1:
                continue
            for j, e2 in enumerate(exps):
                if i >= j or e2.consolidated:
                    continue
                if self._cosine_similarity(e1.features, e2.features) > 0.95:
                    # Merge e2 into e1
                    e1.reward = (e1.reward + e2.reward) / 2
                    e1.access_count += e2.access_count
                    e1.importance = max(e1.importance, e2.importance)
                    e2.consolidated = True
                    merged += 1
        # Remove consolidated
        self.experiences = {k: v for k, v in self.experiences.items() if not v.consolidated}
        return merged

    def size(self) -> int:
        return len(self.experiences)

    def decay_all(self) -> None:
        """Apply time-based decay to all experience importances."""
        now = time.time()
        for exp in self.experiences.values():
            if not exp.consolidated:
                elapsed = now - exp.timestamp
                exp.importance *= math.exp(-self.decay_rate * elapsed)
                exp.importance = max(0.01, min(10.0, exp.importance))


class PatternLearner:
    """Learns probabilistic patterns from experience sequences."""

    def __init__(self):
        # Markov-chain style pattern probabilities
        self.transitions: Dict[Tuple[str, str], float] = defaultdict(float)
        self.sequence_counts: Dict[str, int] = defaultdict(int)
        self.patterns: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def observe(self, sequence: List[str]) -> None:
        """Observe a sequence of actions/outcomes and update transition probabilities."""
        for i in range(len(sequence) - 1):
            state, next_state = sequence[i], sequence[i + 1]
            self.sequence_counts[state] += 1
            key = (state, next_state)
            self.transitions[key] += 1.0

        # Normalize transitions
        for (s, ns), count in list(self.transitions.items()):
            total = self.sequence_counts.get(s, 1)
            self.patterns[s].append((ns, count / total))

    def predict_next(self, current_state: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Predict the most likely next state given current state."""
        candidates = self.patterns.get(current_state, [])
        # Deduplicate by averaging probabilities
        agg: Dict[str, float] = defaultdict(float)
        counts: Dict[str, int] = defaultdict(int)
        for ns, prob in candidates:
            agg[ns] += prob
            counts[ns] += 1
        avg = [(ns, agg[ns] / counts[ns]) for ns in agg]
        avg.sort(key=lambda x: -x[1])
        return avg[:top_k]

    def most_common_sequences(self, min_length: int = 2, top_k: int = 5) -> List[List[str]]:
        """Extract the most common fixed-length sequences from transitions."""
        # Build chains greedily
        sequences = []
        for start_state in list(self.sequence_counts.keys())[:50]:
            seq = [start_state]
            for _ in range(min_length - 1):
                next_states = self.predict_next(seq[-1], top_k=1)
                if next_states:
                    seq.append(next_states[0][0])
                else:
                    break
            if len(seq) >= min_length:
                sequences.append(seq)
        sequences.sort(key=lambda s: -self._sequence_score(s))
        return sequences[:top_k]

    def _sequence_score(self, sequence: List[str]) -> float:
        score = 1.0
        for i in range(len(sequence) - 1):
            prob = self.transitions.get((sequence[i], sequence[i+1]), 0)
            total = self.sequence_counts.get(sequence[i], 1)
            score *= (prob / total) if total > 0 else 0
        return score


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3 — SELF-IMPROVEMENT ENGINE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MetaParameter:
    name: str
    value: float
    min_value: float
    max_value: float
    learning_rate: float = 0.1
    best_value: float = 0.0
    best_reward: float = -float('inf')
    history: List[Tuple[float, float]] = field(default_factory=list)  # (value, reward)

    def mutate(self, temperature: float = 1.0) -> float:
        """Propose a new value by random mutation with temperature scaling."""
        delta = random.gauss(0, self.learning_rate * temperature)
        new_val = self.value + delta
        return max(self.min_value, min(self.max_value, new_val))

    def update(self, new_value: float, reward: float) -> None:
        """Update parameter based on observed reward."""
        self.history.append((new_value, reward))
        self.value = new_value
        if reward > self.best_reward:
            self.best_reward = reward
            self.best_value = new_value

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'value': self.value,
            'min': self.min_value,
            'max': self.max_value,
            'lr': self.learning_rate,
            'best_value': self.best_value,
            'best_reward': self.best_reward
        }


class Strategy:
    """A named strategy with parameterized behavior."""
    def __init__(self, name: str, params: Dict[str, MetaParameter]):
        self.name = name
        self.params = params
        self.total_reward: float = 0.0
        self.apply_count: int = 0
        self.avg_reward: float = 0.0

    def apply(self, **kwargs) -> None:
        """Record that this strategy was applied."""
        self.apply_count += 1

    def record_reward(self, reward: float) -> None:
        self.total_reward += reward
        self.apply_count += 1
        self.avg_reward = self.total_reward / self.apply_count

    def mutate_params(self, temperature: float = 1.0) -> Dict[str, float]:
        return {name: p.mutate(temperature) for name, p in self.params.items()}

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'params': {k: v.to_dict() for k, v in self.params.items()},
            'avg_reward': self.avg_reward,
            'apply_count': self.apply_count
        }


class MetaCognitionEngine:
    """
    Persistent self-improvement via meta-parameter optimization,
    strategy selection, and performance monitoring.
    """

    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
        self.parameter_history: List[Dict] = []
        self.performance_log: List[Dict] = []
        self.strategy_selection_counts: Dict[str, int] = defaultdict(int)
        self.strategy_rewards: Dict[str, float] = defaultdict(float)
        self.exploration_rate: float = 0.3
        self.exploration_decay: float = 0.995
        self.min_exploration: float = 0.01
        self.temperature: float = 1.0
        self.episode_count: int = 0

        # Initialize default strategies
        self._init_default_strategies()

    def _init_default_strategies(self) -> None:
        """Register the core reasoning and learning strategies."""
        strategies = {
            'forward_chaining': {
                'max_iterations': MetaParameter('max_iterations', 50, 10, 200, lr=10.0),
                'fact_retention': MetaParameter('fact_retention', 0.9, 0.1, 1.0, lr=0.05),
            },
            'backward_chaining': {
                'max_depth': MetaParameter('max_depth', 15, 3, 50, lr=2.0),
                'solution_limit': MetaParameter('solution_limit', 5, 1, 50, lr=2.0),
            },
            'memory_recall': {
                'top_k': MetaParameter('top_k', 10, 3, 50, lr=2.0),
                'similarity_threshold': MetaParameter('similarity_threshold', 0.3, 0.0, 1.0, lr=0.05),
            },
            'exploration': {
                'exploration_rate': MetaParameter('exploration_rate', 0.3, 0.01, 1.0, lr=0.05),
                'novelty_bonus': MetaParameter('novelty_bonus', 0.2, 0.0, 1.0, lr=0.05),
            },
            'rule_learning': {
                'min_confidence': MetaParameter('min_confidence', 0.6, 0.1, 1.0, lr=0.05),
                'max_rule_complexity': MetaParameter('max_rule_complexity', 5, 1, 20, lr=1.0),
            },
        }

        for name, params in strategies.items():
            self.add_strategy(Strategy(name, params))

    def add_strategy(self, strategy: Strategy) -> None:
        self.strategies[strategy.name] = strategy

    def select_strategy(self, context: Dict[str, Any]) -> Tuple[str, Strategy]:
        """Select the best strategy for the current context using epsilon-greedy."""
        self.episode_count += 1

        # Exploration: try a random strategy
        if random.random() < self.exploration_rate:
            name = random.choice(list(self.strategies.keys()))
            return name, self.strategies[name]

        # Exploitation: pick the best-performing strategy for similar context
        candidates = []
        for name, strategy in self.strategies.items():
            # Weight by average reward + novelty bonus
            novelty_bonus = self.strategies['exploration'].params.get('novelty_bonus', MetaParameter('x', 0.2, 0, 1)).value
            exploration_value = novelty_bonus * (1.0 / (1.0 + self.strategy_selection_counts[name]))
            score = strategy.avg_reward + exploration_value
            candidates.append((score, name))

        candidates.sort(key=lambda x: -x[0])
        if not candidates:
            return 'forward_chaining', self.strategies['forward_chaining']
        return candidates[0][1], self.strategies[candidates[0][1]]

    def record_outcome(self, strategy_name: str, reward: float,
                       context: Dict[str, Any]) -> None:
        """Record the outcome of applying a strategy."""
        self.strategy_selection_counts[strategy_name] += 1
        self.strategy_rewards[strategy_name] += reward

        if strategy_name in self.strategies:
            self.strategies[strategy_name].record_reward(reward)
            # Apply learning rate decay based on reward
            for param in self.strategies[strategy_name].params.values():
                if reward > param.best_reward:
                    param.best_reward = reward

        self.performance_log.append({
            'timestamp': time.time(),
            'episode': self.episode_count,
            'strategy': strategy_name,
            'reward': reward,
            'exploration_rate': self.exploration_rate,
            'context': context
        })

        # Decay exploration rate
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay
        )

    def adaptive_temperature(self, recent_rewards: List[float]) -> float:
        """Adjust temperature based on reward variance."""
        if len(recent_rewards) < 5:
            return 1.0
        variance = sum((r - sum(recent_rewards)/len(recent_rewards))**2
                      for r in recent_rewards) / len(recent_rewards)
        # High variance -> lower temperature (more conservative)
        # Low variance -> higher temperature (more exploratory)
        self.temperature = 1.0 / (1.0 + math.sqrt(variance))
        return self.temperature

    def self_reflect(self) -> Dict[str, Any]:
        """Meta-cognitive self-reflection: analyze performance and suggest improvements."""
        if not self.performance_log:
            return {'insight': 'No performance data yet', 'suggestions': []}

        recent = self.performance_log[-100:]
        avg_reward = sum(r['reward'] for r in recent) / len(recent) if recent else 0

        # Find best and worst strategies
        strategy_avgs: Dict[str, List[float]] = defaultdict(list)
        for entry in recent:
            strategy_avgs[entry['strategy']].append(entry['reward'])

        best_strategy = max(strategy_avgs, key=lambda s: sum(strategy_avgs[s])/len(strategy_avgs[s]))
        worst_strategy = min(strategy_avgs, key=lambda s: sum(strategy_avgs[s])/len(strategy_avgs[s]))

        suggestions = []
        if avg_reward < 0.3:
            suggestions.append('Increase exploration rate to discover better strategies')
        if self.strategy_selection_counts.get(worst_strategy, 0) > 50:
            suggestions.append(f'Consider deprecating or re-tuning strategy: {worst_strategy}')

        # Detect plateaus
        if len(recent) >= 20:
            recent_rewards = [r['reward'] for r in recent[-20:]]
            if max(recent_rewards) - min(recent_rewards) < 0.05:
                suggestions.append('Performance plateau detected — injecting random strategy perturbation')

        self.parameter_history.append({
            'timestamp': time.time(),
            'episode': self.episode_count,
            'avg_reward': avg_reward,
            'exploration_rate': self.exploration_rate,
            'temperature': self.temperature,
            'best_strategy': best_strategy,
            'worst_strategy': worst_strategy,
            'suggestions': suggestions
        })

        return {
            'avg_reward': avg_reward,
            'best_strategy': best_strategy,
            'worst_strategy': worst_strategy,
            'suggestions': suggestions,
            'total_episodes': self.episode_count
        }

    def get_state(self) -> Dict:
        return {
            'exploration_rate': self.exploration_rate,
            'temperature': self.temperature,
            'episode_count': self.episode_count,
            'strategies': {k: v.to_dict() for k, v in self.strategies.items()},
            'selection_counts': dict(self.strategy_selection_counts),
        }


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4 — CORE AGENT
# ═══════════════════════════════════════════════════════════════════════

class AgentRole(Enum):
    EXPLORER = auto()
    REASONER = auto()
    LEARNER = auto()
    OPTIMIZER = auto()
    REFLECTOR = auto()


@dataclass
class Goal:
    description: str
    priority: int  # lower = higher priority
    created: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    progress: float = 0.0
    completed: bool = False
    subgoals: List[Goal] = field(default_factory=list)

    def is_expired(self) -> bool:
        return self.deadline is not None and time.time() > self.deadline


class DeepSeekV4FlashAgent:
    """
    The main agent class combining all four attributes:

      (1) Logical Reasoning — Horn clause inference engine
      (2) Learn — Episodic memory + pattern learner
      (3) Persistent Self-Improvement — Meta-cognition engine
      (4) Python Language — Pure stdlib implementation
    """

    def __init__(self, name: str = "DeepSeek-v4-flash", config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self.version = "4.0-flash"
        self.start_time = time.time()

        # Core subsystems
        self.inference = InferenceEngine()
        self.memory = EpisodicMemory(capacity=self.config.get('memory_capacity', 10000))
        self.pattern_learner = PatternLearner()
        self.meta_cognition = MetaCognitionEngine()
        self.goals: List[Goal] = []

        # Agent state
        self.current_role: AgentRole = AgentRole.EXPLORER
        self.knowledge_base: Dict[str, Any] = {}
        self.action_history: List[Dict] = []
        self.consecutive_failures: int = 0
        self.session_id = hashlib.sha256(
            f"{name}-{time.time()}-{random.randint(0, 2**32)}".encode()
        ).hexdigest()[:12]

        # Load default knowledge
        self._seed_knowledge()

        self._log(f"Agent {self.name} v{self.version} initialized [session={self.session_id}]")

    # ── Public API ────────────────────────────────────────────────

    def reason(self, premises: List[str], query: str) -> Dict[str, Any]:
        """
        (1) LOGICAL REASONING — Perform deductive inference.

        Args:
            premises: List of logical statements as strings
            query:    The query to prove

        Returns:
            {'proven': bool, 'bindings': dict, 'explanation': [str]}
        """
        self.current_role = AgentRole.REASONER
        self.inference.reset_trace()

        # Parse premises into facts/rules
        for premise in premises:
            self._parse_and_assert(premise)

        # Parse query
        goal = self._parse_term(query)

        # Select reasoning strategy via meta-cognition
        strategy_name, strategy = self.meta_cognition.select_strategy({
            'task': 'reasoning',
            'premises_count': len(premises),
            'query': query
        })

        # Execute reasoning
        start = time.time()

        if strategy_name == 'forward_chaining':
            max_iter = int(strategy.params.get(
                'max_iterations', MetaParameter('x', 50, 10, 200)
            ).value)
            derived = self.inference.forward_chain(max_iterations=max_iter)
            proven = self.inference.query(goal)
            bindings = self.inference.backward_chain(goal, max_depth=1)
        else:
            max_depth = int(strategy.params.get(
                'max_depth', MetaParameter('x', 15, 3, 50)
            ).value)
            bindings = self.inference.backward_chain(goal, max_depth=max_depth)
            proven = len(bindings) > 0
            derived = None

        elapsed = time.time() - start

        # Build result
        bindings_dict = {}
        if bindings:
            bindings_dict = {k: repr(v) for k, v in bindings[0].items()}

        explanation = self.inference.explain(goal) if proven else []

        result = {
            'proven': proven,
            'bindings': bindings_dict,
            'explanation': explanation,
            'derived_facts': [repr(d) for d in derived[:10]] if derived else [],
            'strategy': strategy_name,
            'time_seconds': elapsed
        }

        # Learn from this reasoning episode
        reward = 1.0 if proven else 0.0
        if proven and elapsed < 0.5:
            reward += 0.2  # Fast correct reasoning bonus

        self._learn_from_reasoning(premises, query, proven, reward, strategy_name)

        return result

    def learn(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        (2) LEARN — Store and integrate new knowledge/experience.

        Args:
            data: {'input': ..., 'action': ..., 'outcome': ..., 'reward': ...,
                   'features': {...}}

        Returns:
            {'stored': bool, 'memory_size': int, 'patterns_found': int}
        """
        self.current_role = AgentRole.LEARNER

        exp = Experience(
            id=hashlib.md5(f"{time.time()}-{random.random()}".encode()).hexdigest()[:16],
            timestamp=time.time(),
            input_context=data.get('input', {}),
            action_taken=data.get('action', 'unknown'),
            outcome=data.get('outcome', 'unknown'),
            reward=float(data.get('reward', 0.0)),
            importance=float(data.get('importance', 1.0)),
            features=data.get('features', {}),
        )

        self.memory.store(exp)

        # Update pattern learner if we have a sequence context
        if 'sequence' in data:
            self.pattern_learner.observe(data['sequence'])

        # Extract logical patterns
        extracted = self._extract_patterns(exp)
        for pattern_clause in extracted:
            self.inference.assert_rule(pattern_clause)

        # Record for meta-cognition
        self.meta_cognition.record_outcome(
            'memory_recall' if 'features' in data else 'rule_learning',
            exp.reward,
            {'memory_size': self.memory.size()}
        )

        # Periodic consolidation
        if self.memory.size() % 100 == 0:
            merged = self.memory.consolidate()
            self._log(f"Memory consolidation: merged {merged} experiences")

        return {
            'stored': True,
            'memory_size': self.memory.size(),
            'patterns_found': len(extracted),
            'experience_id': exp.id
        }

    def improve(self) -> Dict[str, Any]:
        """
        (3) PERSISTENT SELF-IMPROVEMENT — Run meta-cognitive reflection
        and adjust strategies.
        """
        self.current_role = AgentRole.OPTIMIZER

        reflection = self.meta_cognition.self_reflect()

        # Apply suggestions
        actions_taken = []
        for suggestion in reflection.get('suggestions', []):
            if 'exploration' in suggestion.lower():
                self.meta_cognition.exploration_rate = min(
                    0.5, self.meta_cognition.exploration_rate * 1.5
                )
                actions_taken.append('increased_exploration_rate')
            elif 'plateau' in suggestion.lower():
                # Perturb all strategy parameters
                for strategy in self.meta_cognition.strategies.values():
                    for param in strategy.params.values():
                        param.value = random.uniform(param.min_value, param.max_value)
                actions_taken.append('random_parameter_perturbation')
                self._log("Plateau detected: random parameter perturbation applied")

        # Decay memory
        self.memory.decay_all()

        # Log improvement
        state = self.get_state()
        state['actions_taken'] = actions_taken
        state['reflection'] = reflection
        self.action_history.append({
            'timestamp': time.time(),
            'type': 'self_improvement',
            'state': state
        })

        self._log(f"Self-improvement cycle complete. "
                  f"Avg reward: {reflection['avg_reward']:.3f}, "
                  f"Best strat: {reflection.get('best_strategy', 'N/A')}")

        return state

    def run_pipeline(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full autonomous pipeline: Reason -> Learn -> Improve

        This is the primary entry point for autonomous operation.
        """
        self.current_role = AgentRole.EXPLORER

        pipeline_start = time.time()
        results = {}

        # Step 1: Reason
        premises = input_data.get('premises', [])
        query = input_data.get('query', '')

        if premises and query:
            reasoning_result = self.reason(premises, query)
            results['reasoning'] = reasoning_result

        # Step 2: Learn from input
        learn_data = {
            'input': input_data.get('context', {}),
            'action': 'pipeline_run',
            'outcome': str(results.get('reasoning', {}).get('proven', 'unknown')),
            'reward': 1.0 if results.get('reasoning', {}).get('proven') else 0.0,
            'features': input_data.get('features', {}),
        }
        learn_result = self.learn(learn_data)
        results['learning'] = learn_result

        # Step 3: Periodically improve
        if len(self.action_history) % 5 == 0:  # Every 5 runs
            improve_result = self.improve()
            results['improvement'] = improve_result

        results['pipeline_time'] = time.time() - pipeline_start
        results['agent_version'] = self.version
        results['session_id'] = self.session_id

        return results

    # ── Persistence ───────────────────────────────────────────────

    def save_state(self, filepath: str) -> bool:
        """Save entire agent state to disk as JSON."""
        try:
            state = {
                'name': self.name,
                'version': self.version,
                'session_id': self.session_id,
                'uptime': time.time() - self.start_time,
                'meta_cognition': self.meta_cognition.get_state(),
                'inference': {
                    'facts': [repr(f) for f in self.inference.facts],
                    'rules': [repr(r) for r in self.inference.rules],
                },
                'action_history': self.action_history[-100:],
                'goals': [asdict(g) for g in self.goals],
                'consecutive_failures': self.consecutive_failures,
            }
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            self._log(f"State saved to {filepath}")
            return True
        except Exception as e:
            self._log(f"Failed to save state: {e}")
            return False

    def load_state(self, filepath: str) -> bool:
        """Load agent state from disk."""
        try:
            with open(filepath) as f:
                state = json.load(f)

            self.name = state.get('name', self.name)
            self.session_id = state.get('session_id', self.session_id)
            self.consecutive_failures = state.get('consecutive_failures', 0)

            # Restore meta-cognition state
            mc = state.get('meta_cognition', {})
            self.meta_cognition.exploration_rate = mc.get('exploration_rate', 0.3)
            self.meta_cognition.temperature = mc.get('temperature', 1.0)
            self.meta_cognition.episode_count = mc.get('episode_count', 0)

            self._log(f"State loaded from {filepath}")
            return True
        except Exception as e:
            self._log(f"Failed to load state: {e}")
            return False

    def get_state(self) -> Dict[str, Any]:
        """Get a full snapshot of the agent's current state."""
        return {
            'name': self.name,
            'version': self.version,
            'uptime_seconds': time.time() - self.start_time,
            'session_id': self.session_id,
            'current_role': self.current_role.name,
            'inference': {
                'facts': len(self.inference.facts),
                'rules': len(self.inference.rules),
                'trace_length': len(self.inference.derivation_trace),
            },
            'memory': {
                'experiences': self.memory.size(),
                'capacity': self.memory.capacity,
            },
            'patterns': {
                'learned_transitions': len(self.pattern_learner.transitions),
            },
            'meta_cognition': self.meta_cognition.get_state(),
            'goals': len(self.goals),
            'action_history': len(self.action_history),
            'consecutive_failures': self.consecutive_failures,
        }

    def set_goal(self, description: str, priority: int = 5,
                 deadline: Optional[float] = None) -> Goal:
        """Set a new goal for the agent."""
        goal = Goal(
            description=description,
            priority=priority,
            deadline=deadline
        )
        self.goals.append(goal)
        self.goals.sort(key=lambda g: g.priority)
        return goal

    # ── Internal Methods ──────────────────────────────────────────

    def _seed_knowledge(self) -> None:
        """Seed the agent with foundational logical knowledge."""
        seed_facts = [
            'true.',
            'knows(agent, self).',
            'capable(reasoning).',
            'capable(learning).',
            'capable(self_improvement).',
            'attribute(self, logical_reasoning).',
            'attribute(self, learning).',
            'attribute(self, persistent_self_improvement).',
            'type(goal, objective).',
            'type(fact, knowledge).',
            'type(rule, knowledge).',
        ]
        for fact in seed_facts:
            self._parse_and_assert(fact)

        seed_rules = [
            'can(A, T) :- capable(T), attribute(A, T).',
            'knows(A, X) :- learned(A, X).',
            'improves(A) :- capable(self_improvement), attribute(A, persistent_self_improvement).',
        ]
        for rule_str in seed_rules:
            self._parse_and_assert(rule_str)

    def _parse_and_assert(self, text: str) -> None:
        """Parse a Prolog-like string and assert it as fact or rule."""
        text = text.strip().rstrip('.')
        if ':-' in text:
            head_str, body_str = text.split(':-', 1)
            head = self._parse_term(head_str.strip())
            body_parts = [self._parse_term(b.strip()) for b in body_str.split(',')]
            clause = Clause(head, body_parts)
            self.inference.assert_rule(clause)
        else:
            term = self._parse_term(text)
            self.inference.assert_fact(term)

    def _parse_term(self, text: str) -> Term:
        """Parse a simple term string into a Term object.
        Supports: constant, constant(args...), and ?variable."""
        text = text.strip()

        # Variable (starts with ? or uppercase)
        if text.startswith('?'):
            return Term.variable(text[1:])
        if text and text[0].isupper():
            return Term.variable(text)

        # Compound term: functor(arg1, arg2, ...)
        if '(' in text and text.endswith(')'):
            idx = text.index('(')
            functor = text[:idx].strip()
            args_str = text[idx+1:-1]
            args = []
            # Simple comma-split (doesn't handle nested commas — sufficient for flat terms)
            depth = 0
            current = []
            for ch in args_str:
                if ch == '(':
                    depth += 1
                    current.append(ch)
                elif ch == ')':
                    depth -= 1
                    current.append(ch)
                elif ch == ',' and depth == 0:
                    args.append(self._parse_term(''.join(current).strip()))
                    current = []
                else:
                    current.append(ch)
            if current:
                args.append(self._parse_term(''.join(current).strip()))
            return Term(functor, args)

        # Constant
        return Term(text)

    def _extract_patterns(self, experience: Experience) -> List[Clause]:
        """Extract logical rules from an experience."""
        patterns = []
        # If the action led to a positive outcome, create a rule
        if experience.reward > 0.5:
            head = Term('success_pattern', [
                Term.constant(experience.action_taken),
                Term.constant(experience.outcome)
            ])
            body = []
            for key, val in experience.input_context.items():
                if isinstance(val, (str, int, float, bool)):
                    body.append(Term('context', [Term.constant(key), Term.constant(str(val))]))
            if body:
                clause = Clause(head, body)
                clause.weight = experience.reward
                patterns.append(clause)
        return patterns

    def _learn_from_reasoning(self, premises: List[str], query: str,
                              proven: bool, reward: float,
                              strategy: str) -> None:
        """Record reasoning experience for future learning."""
        features = {
            'premises_count': float(len(premises)),
            'query_length': float(len(query)),
            'proven': float(proven),
        }
        seq_key = f"reason:{strategy}:{'success' if proven else 'failure'}"
        self.pattern_learner.observe([seq_key])

        self.meta_cognition.record_outcome(
            strategy,
            reward,
            features
        )

        self.action_history.append({
            'timestamp': time.time(),
            'type': 'reasoning',
            'premises': premises[:3],  # Truncate for history
            'query': query,
            'proven': proven,
            'strategy': strategy,
            'reward': reward,
        })

        if not proven:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

    def _log(self, message: str) -> None:
        """Internal logging."""
        timestamp = time.strftime('%H:%M:%S', time.localtime(time.time()))
        print(f"[{timestamp}] [{self.name}] {message}")


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5 — DEMONSTRATION & TEST HARNESS
# ═══════════════════════════════════════════════════════════════════════

def demonstration():
    """Run a comprehensive demonstration of all four attributes."""
    print("=" * 72)
    print("  DeepSeek-v4-flash AI Agent — Demonstration")
    print("=" * 72)

    # Initialize agent
    agent = DeepSeekV4FlashAgent(
        name="DemoAgent",
        config={'memory_capacity': 1000}
    )

    print(f"\nAgent state: {agent.get_state()['inference']['facts']} seed facts loaded\n")

    # ── (1) LOGICAL REASONING ────────────────────────────────────
    print("─" * 72)
    print("  (1) LOGICAL REASONING — Backward Chaining Proof")
    print("─" * 72)

    premises = [
        "mortal(X) :- human(X).",
        "human(socrates).",
        "human(plato).",
        "human(aristotle).",
    ]

    queries = [
        "mortal(socrates)",
        "mortal(X)",
        "human(diogenes)",
    ]

    for query in queries:
        result = agent.reason(premises, query)
        status = "✓ PROVEN" if result['proven'] else "✗ NOT PROVEN"
        print(f"  Query: {query:25s} → {status}")
        if result['bindings']:
            for var, val in result['bindings'].items():
                print(f"           {var} = {val}")
        print(f"  Strategy: {result['strategy']} ({result['time_seconds']:.4f}s)")
        if result['explanation']:
            for line in result['explanation'][-2:]:
                print(f"  {line}")
        print()

    # ── (2) LEARNING ─────────────────────────────────────────────
    print("─" * 72)
    print("  (2) LEARNING — Experience Storage & Pattern Extraction")
    print("─" * 72)

    training_data = [
        {'input': {'problem': 'sorting', 'difficulty': 'easy'},
         'action': 'quick_sort', 'outcome': 'sorted', 'reward': 1.0,
         'features': {'time': 0.1, 'correct': 1.0}},
        {'input': {'problem': 'sorting', 'difficulty': 'hard'},
         'action': 'merge_sort', 'outcome': 'sorted', 'reward': 0.9,
         'features': {'time': 0.3, 'correct': 1.0}},
        {'input': {'problem': 'search', 'difficulty': 'easy'},
         'action': 'linear_search', 'outcome': 'found', 'reward': 1.0,
         'features': {'time': 0.05, 'correct': 1.0}},
        {'input': {'problem': 'search', 'difficulty': 'hard'},
         'action': 'binary_search', 'outcome': 'found', 'reward': 1.0,
         'features': {'time': 0.02, 'correct': 1.0}},
    ]

    for data in training_data:
        result = agent.learn(data)
        print(f"  Learned: {data['action']:15s} → {data['outcome']:8s} "
              f"(reward={data['reward']})  [mem={result['memory_size']}]")

    print(f"  Transitions learned: {len(agent.pattern_learner.transitions)}")
    common = agent.pattern_learner.most_common_sequences(min_length=2, top_k=3)
    for seq in common:
        print(f"  Pattern: {' → '.join(seq)}")
    print()

    # ── (3) PERSISTENT SELF-IMPROVEMENT ──────────────────────────
    print("─" * 72)
    print("  (3) PERSISTENT SELF-IMPROVEMENT — Meta-Cognitive Cycle")
    print("─" * 72)

    # Simulate several reasoning episodes to generate performance data
    for i in range(25):
        # Vary query difficulty
        difficulty = random.uniform(0.1, 1.0)
        success = random.random() < (0.7 + 0.1 * math.sin(i / 3))
        reward = 1.0 if success else 0.0

        agent.meta_cognition.record_outcome(
            random.choice(['forward_chaining', 'backward_chaining', 'memory_recall']),
            reward * (1.0 - difficulty * 0.3),
            {'episode': i, 'difficulty': difficulty}
        )

    # Run self-improvement
    state = agent.improve()
    reflection = state.get('reflection', {})
    print(f"  Avg reward:         {reflection.get('avg_reward', 0):.4f}")
    print(f"  Best strategy:      {reflection.get('best_strategy', 'N/A')}")
    print(f"  Worst strategy:     {reflection.get('worst_strategy', 'N/A')}")
    print(f"  Exploration rate:   {state['meta_cognition']['exploration_rate']:.4f}")
    print(f"  Temperature:        {state['meta_cognition']['temperature']:.4f}")
    print(f"  Suggestions:")
    for s in reflection.get('suggestions', []):
        print(f"    • {s}")
    print(f"  Actions taken:      {state.get('actions_taken', [])}")
    print()

    # ── (4) FULL PIPELINE ────────────────────────────────────────
    print("─" * 72)
    print("  (4) FULL AUTONOMOUS PIPELINE")
    print("─" * 72)

    pipeline_input = {
        'premises': [
            "mammal(X) :- has_hair(X), warm_blooded(X).",
            "has_hair(dolphin).",
            "warm_blooded(dolphin).",
            "has_hair(human).",
            "warm_blooded(human).",
        ],
        'query': 'mammal(X)',
        'context': {'task': 'classification', 'domain': 'biology'},
        'features': {'complexity': 3, 'domain_weight': 0.8},
    }

    result = agent.run_pipeline(pipeline_input)
    print(f"  Reasoning:  {'✓' if result['reasoning']['proven'] else '✗'}")
    for var, val in result['reasoning']['bindings'].items():
        print(f"    {var} = {val}")
    print(f"  Learning:   stored={result['learning']['stored']}, "
          f"mem_size={result['learning']['memory_size']}")
    if 'improvement' in result:
        print(f"  Improvement: cycle triggered")
    print(f"  Pipeline time: {result['pipeline_time']:.4f}s")
    print()

    # ── STATE SUMMARY ────────────────────────────────────────────
    print("─" * 72)
    print("  AGENT STATE SUMMARY")
    print("─" * 72)
    state = agent.get_state()
    print(json.dumps(state, indent=2, default=str))
    print()

    # ── PERSISTENCE ──────────────────────────────────────────────
    print("─" * 72)
    print("  PERSISTENCE TEST (save/load cycle)")
    print("─" * 72)
    save_path = '/tmp/deepseek_v4_flash_state.json'
    saved = agent.save_state(save_path)
    print(f"  Saved:   {saved}")

    # Create a fresh agent and load
    agent2 = DeepSeekV4FlashAgent(name="LoadedAgent")
    loaded = agent2.load_state(save_path)
    print(f"  Loaded:  {loaded}")
    print(f"  Restored session: {agent2.session_id}")
    os.remove(save_path)

    print("\n" + "=" * 72)
    print("  Demonstration Complete.")
    print("=" * 72)

    return agent


if __name__ == '__main__':
    agent = demonstration()
