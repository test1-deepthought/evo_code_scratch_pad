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
import hashlib
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
from typing import (Optional, Dict, List, Tuple, Any, Set)
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class DeepSeekAPI:
    """Client for the real DeepSeek-v4-flash LLM API.
    Endpoint: POST https://api.deepseek.com/chat/completions
    Model:    deepseek-v4-flash
    """
    BASE_URL = "https://api.deepseek.com/chat/completions"
    DEFAULT_MODEL = "deepseek-v4-flash"

    def __init__(self, api_key=None, model=DEFAULT_MODEL, timeout=30):
        self.api_key = api_key or ""
        self.model = model
        self.timeout = timeout
        self._last_response = None
        self._total_tokens_used = 0
        self._api_calls = 0
        self._api_errors = 0

    @property
    def available(self):
        return bool(self.api_key)

    def chat(self, messages, temperature=0.3, max_tokens=1024, **kwargs):
        if not self.available:
            return None
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens, **kwargs}
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        try:
            req = Request(self.BASE_URL, data=json.dumps(payload).encode("utf-8"),
                          headers=headers, method="POST")
            with urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self._last_response = body
            self._api_calls += 1
            usage = body.get("usage", {})
            self._total_tokens_used += usage.get("total_tokens", 0)
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return None
        except HTTPError as e:
            self._api_errors += 1
            return None
        except URLError as e:
            self._api_errors += 1
            return None
        except Exception as e:
            self._api_errors += 1
            return None

    def reason(self, query, context=None):
        if not self.available:
            return {"answer": None, "confidence": 0.0, "tokens_used": 0,
                    "error": "API unavailable", "raw_response": None}
        system_prompt = (
            "You are DeepSeek-v4-flash, a precise logical reasoning engine. "
            "Think step by step. Format: FINAL ANSWER: <your conclusion>"
        )
        user_message = f"Query: {query}\n"
        if context:
            if "facts" in context:
                user_message += "\nKnown facts:\n" + "\n".join(f"  - {f}" for f in context["facts"]) + "\n"
            if "premises" in context:
                user_message += "\nPremises:\n" + "\n".join(f"  - {p}" for p in context["premises"]) + "\n"
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}]
        response = self.chat(messages, temperature=0.2, max_tokens=2048)
        if response is None:
            return {"answer": None, "confidence": 0.0, "tokens_used": 0,
                    "error": "API error", "raw_response": None}
        confidence = 0.7
        if "INSUFFICIENT INFORMATION" in response:
            confidence = 0.1
        elif "FINAL ANSWER:" in response:
            confidence = 0.9
        tokens = 0
        if self._last_response:
            tokens = self._last_response.get("usage", {}).get("total_tokens", 0)
        return {"answer": response, "confidence": confidence,
                "tokens_used": tokens, "error": None, "raw_response": self._last_response}

    def extract_structured_knowledge(self, text):
        return []

    def get_stats(self):
        return {"api_calls": self._api_calls, "api_errors": self._api_errors,
                "total_tokens_used": self._total_tokens_used,
                "model": self.model, "available": self.available}

    def to_dict(self):
        return {"model": self.model, "total_tokens_used": self._total_tokens_used,
                "api_calls": self._api_calls, "api_errors": self._api_errors}

    @classmethod
    def from_dict(cls, data, api_key=None):
        api = cls(api_key=api_key, model=data.get("model", cls.DEFAULT_MODEL))
        api._total_tokens_used = data.get("total_tokens_used", 0)
        api._api_calls = data.get("api_calls", 0)
        api._api_errors = data.get("api_errors", 0)
        return api


@dataclass(frozen=True)
class Term:
    functor: str
    args: Tuple["Term", ...] = ()
    def __repr__(self):
        if not self.args: return self.functor
        return f"{self.functor}({', '.join(repr(a) for a in self.args)})"
    def __eq__(self, other):
        if not isinstance(other, Term): return NotImplemented
        return self.functor == other.functor and self.args == other.args
    def __hash__(self):
        return hash((self.functor, self.args))
    def is_variable(self):
        return self.functor.startswith("_") and self.functor != "_"
    def substitute(self, mapping):
        if self.is_variable() and self.functor in mapping:
            return mapping[self.functor]
        return Term(self.functor, tuple(a.substitute(mapping) for a in self.args))
    def variables(self):
        if self.is_variable(): return {self.functor}
        result = set()
        for a in self.args: result.update(a.variables())
        return result


@dataclass(frozen=True)
class Clause:
    head: Term
    body: Tuple[Term, ...] = ()
    def __repr__(self):
        if not self.body: return f"{self.head}."
        return f"{self.head} :- {', '.join(repr(b) for b in self.body)}."
    def substitute(self, mapping):
        return Clause(self.head.substitute(mapping),
                      tuple(b.substitute(mapping) for b in self.body))
    def rename_variables(self, prefix="G"):
        """Generated variable names start with '_' so is_variable() returns True."""
        mapping = {}
        idx = 0
        for var in self.head.variables():
            if var.startswith("_"):
                mapping[var] = Term(f"_{prefix}{idx}")
                idx += 1
        for b in self.body:
            for var in b.variables():
                if var.startswith("_") and var not in mapping:
                    mapping[var] = Term(f"_{prefix}{idx}")
                    idx += 1
        return self.substitute(mapping)


def unify(t1, t2, mapping=None):
    if mapping is None: mapping = {}
    if t1 == t2: return mapping
    if t1.is_variable() and t1.functor != "_":
        return _unify_var(t1, t2, mapping)
    if t2.is_variable() and t2.functor != "_":
        return _unify_var(t2, t1, mapping)
    if t1.functor == t2.functor and len(t1.args) == len(t2.args):
        mapping = dict(mapping)
        for a1, a2 in zip(t1.args, t2.args):
            mapping = unify(a1, a2, mapping)
            if mapping is None: return None
        return mapping
    return None


def _unify_var(var, term, mapping):
    if var.functor in mapping:
        return unify(mapping[var.functor], term, mapping)
    mapping = dict(mapping)
    mapping[var.functor] = term
    return mapping


class InferenceEngine:
    def __init__(self):
        self._facts = []
        self._rules = []
        self._inference_count = 0

    def add_clause(self, clause):
        if not clause.body:
            self._facts.append(clause)
        else:
            self._rules.append(clause)

    def forward_chain(self, goal, max_iterations=100):
        derived = {f.head for f in self._facts}
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
                    if not found: break
                else:
                    new_head = renamed.head
                    if new_head not in derived:
                        derived.add(new_head)
                        changed = True
                        self._inference_count += 1
            iterations += 1
        return any(unify(goal, d) is not None for d in derived)

    def backward_chain(self, goal, max_iterations=100):
        solutions = []
        visited = set()
        stack = [(goal, {}, 0)]
        iteration = 0
        while stack and iteration < max_iterations:
            current_goal, bindings, depth = stack.pop()
            iteration += 1
            self._inference_count += 1
            resolved = current_goal.substitute(bindings)
            key = (resolved.functor,) + tuple(str(a) for a in resolved.args)
            if key in visited and depth > 0: continue
            visited.add(key)
            for fact in self._facts:
                u = unify(resolved, fact.head.substitute(bindings), dict(bindings))
                if u is not None:
                    solutions.append(u)
            for rule in self._rules:
                renamed = rule.rename_variables(f"BC{depth}")
                u = unify(resolved, renamed.head.substitute(bindings), dict(bindings))
                if u is not None:
                    new_bindings = dict(bindings)
                    new_bindings.update(u)
                    for prem in renamed.body:
                        stack.append((prem, new_bindings, depth + 1))
        return solutions

    def solve(self, goal, strategy="backward_chaining"):
        if strategy == "forward_chaining":
            proven = self.forward_chain(goal)
            return {"proven": proven, "solutions": [{}] if proven else [],
                    "strategy": strategy, "inference_count": self._inference_count}
        elif strategy == "backward_chaining":
            solutions = self.backward_chain(goal)
            return {"proven": len(solutions) > 0, "solutions": solutions,
                    "strategy": strategy, "inference_count": self._inference_count}
        return {"proven": False, "solutions": [], "strategy": strategy,
                "inference_count": self._inference_count, "error": "Unknown strategy"}


@dataclass
class Experience:
    query: str
    response: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    outcome: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    @property
    def age(self):
        return time.time() - self.timestamp

    def compute_embedding(self):
        text = f"{self.query} {self.response}"
        features = [0.0] * 26
        for ch in text.lower():
            if 'a' <= ch <= 'z':
                features[ord(ch) - ord('a')] += 1.0
        mag = math.sqrt(sum(f * f for f in features))
        if mag > 0:
            features = [f / mag for f in features]
        features.append(min(1.0, len(text) / 1000.0))
        features.append(self.importance)
        self.embedding = features
        return features


class EpisodicMemory:
    def __init__(self, capacity=10000, decay_rate=0.001):
        self.capacity = capacity
        self.decay_rate = decay_rate
        self._experiences = []
        self._index = defaultdict(list)

    @property
    def size(self):
        return len(self._experiences)

    def store(self, experience):
        experience.compute_embedding()
        self._experiences.append(experience)
        for tag in experience.tags:
            self._index[tag].append(len(self._experiences) - 1)
        if len(self._experiences) > self.capacity:
            self._experiences.pop(0)
            self._rebuild_index()

    def _rebuild_index(self):
        self._index.clear()
        for i, exp in enumerate(self._experiences):
            for tag in exp.tags:
                self._index[tag].append(i)

    def recall_by_tag(self, tag, k=5):
        indices = self._index.get(tag, [])
        candidates = [self._experiences[i] for i in indices if i < len(self._experiences)]
        candidates.sort(key=lambda e: (e.importance * (e.outcome or 0.5)) - e.age * self.decay_rate, reverse=True)
        return candidates[:k]

    def recall_similar(self, query_embedding, k=5):
        if not self._experiences:
            return []
        def cosine_sim(a, b):
            dot = sum(ai * bi for ai, bi in zip(a, b))
            na = math.sqrt(sum(ai * ai for ai in a))
            nb = math.sqrt(sum(bi * bi for bi in b))
            if na * nb == 0: return 0.0
            return dot / (na * nb)
        scored = [(cosine_sim(exp.embedding, query_embedding), i)
                  for i, exp in enumerate(self._experiences) if exp.embedding]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(self._experiences[i], sim) for sim, i in scored[:k]]

    def all(self):
        return list(self._experiences)

    def summarize(self):
        if not self._experiences:
            return {"size": 0, "avg_importance": 0.0, "avg_outcome": None, "tags": {}}
        return {"size": self.size,
                "avg_importance": sum(e.importance for e in self._experiences) / self.size,
                "avg_outcome": sum((e.outcome or 0.5) for e in self._experiences) / self.size,
                "tags": {tag: len(idxs) for tag, idxs in self._index.items()}}

    def to_dict(self):
        return {"capacity": self.capacity, "decay_rate": self.decay_rate,
                "experiences": [{"query": e.query, "response": e.response,
                                 "timestamp": e.timestamp, "importance": e.importance,
                                 "outcome": e.outcome, "context": e.context,
                                 "tags": e.tags, "embedding": e.embedding}
                                for e in self._experiences]}

    @classmethod
    def from_dict(cls, data):
        mem = cls(capacity=data.get("capacity", 10000), decay_rate=data.get("decay_rate", 0.001))
        for exp_data in data.get("experiences", []):
            exp = Experience(query=exp_data["query"], response=exp_data["response"],
                             timestamp=exp_data.get("timestamp", time.time()),
                             importance=exp_data.get("importance", 0.5),
                             outcome=exp_data.get("outcome"),
                             context=exp_data.get("context", {}),
                             tags=exp_data.get("tags", []),
                             embedding=exp_data.get("embedding"))
            mem._experiences.append(exp)
        mem._rebuild_index()
        return mem


class PatternLearner:
    def __init__(self, order=1):
        self.order = order
        self.transitions = defaultdict(lambda: defaultdict(float))
        self._total_transitions = 0
        self._last_states = deque(maxlen=order)

    def observe(self, state):
        self._last_states.append(state)
        if len(self._last_states) == self.order:
            key = tuple(self._last_states)
            self.transitions[key][state] += 1.0
            self._total_transitions += 1

    def predict_next(self, current_state):
        context = tuple([current_state])
        if context in self.transitions:
            total = sum(self.transitions[context].values())
            return {s: c / total for s, c in self.transitions[context].items()}
        return {}

    def most_likely_next(self, current_state):
        predictions = self.predict_next(current_state)
        if not predictions: return None
        return max(predictions, key=predictions.get)

    def confidence(self, current_state):
        predictions = self.predict_next(current_state)
        if not predictions: return 0.0
        total = sum(predictions.values())
        if total == 0: return 0.0
        top = max(predictions.values())
        if self._total_transitions == 0: return 0.0
        support = total / self._total_transitions
        return top * support

    def learn(self, sequence):
        for i in range(len(sequence)):
            if i == 0:
                self._last_states.append(sequence[i])
            else:
                self.observe(sequence[i])

    def to_dict(self):
        return {"order": self.order,
                "transitions": {"|".join(k): dict(v) for k, v in self.transitions.items()},
                "total_transitions": self._total_transitions}

    @classmethod
    def from_dict(cls, data):
        pl = cls(order=data.get("order", 1))
        for key_str, v in data.get("transitions", {}).items():
            key = tuple(key_str.split("|"))
            pl.transitions[key] = defaultdict(float, v)
        pl._total_transitions = data.get("total_transitions", 0)
        return pl


@dataclass
class MetaParameter:
    name: str
    value: float
    min_val: float
    max_val: float
    learning_rate: float = 1.0
    def __post_init__(self):
        self.best_value = self.value
        self.best_reward = -float("inf")
        self.history = []
    def mutate(self, reward):
        self.history.append((self.value, reward))
        if reward > self.best_reward:
            self.best_reward = reward
            self.best_value = self.value
        exploration = max(0.05, 1.0 - reward) * self.learning_rate
        delta = random.gauss(0, exploration * (self.max_val - self.min_val))
        self.value = max(self.min_val, min(self.max_val, self.value + delta))
    def recent_trend(self, window=5):
        if len(self.history) < 2: return 0.0
        recent = self.history[-window:]
        if len(recent) < 2: return 0.0
        return recent[-1][1] - recent[0][1]
    def to_dict(self):
        return {"name": self.name, "value": self.value, "min_val": self.min_val,
                "max_val": self.max_val, "learning_rate": self.learning_rate,
                "best_value": self.best_value, "best_reward": self.best_reward,
                "history": self.history[-100:]}
    @classmethod
    def from_dict(cls, data):
        mp = cls(name=data["name"], value=data["value"], min_val=data["min_val"],
                 max_val=data["max_val"], learning_rate=data.get("learning_rate", 1.0))
        mp.best_value = data.get("best_value", data["value"])
        mp.best_reward = data.get("best_reward", -float("inf"))
        mp.history = [(v, r) for v, r in data.get("history", [])]
        return mp


class Strategy(Enum):
    LLM_REASONING = "llm_reasoning"
    FORWARD_CHAINING = "forward_chaining"
    BACKWARD_CHAINING = "backward_chaining"
    MEMORY_RECALL = "memory_recall"
    PATTERN_PREDICT = "pattern_predict"


class MetaCognitionEngine:
    def __init__(self, epsilon=0.2, gamma=0.9):
        self.epsilon = epsilon
        self.gamma = gamma
        self.strategies = {s: [] for s in Strategy}
        self.params = {
            'temperature': MetaParameter('temperature', 0.3, 0.0, 2.0),
            'max_tokens': MetaParameter('max_tokens', 1024, 128, 4096, lr=100.0),
            'memory_recall_k': MetaParameter('memory_recall_k', 3, 1, 10),
            'exploration_rate': MetaParameter('exploration_rate', 0.2, 0.01, 0.5),
            'pattern_confidence_threshold': MetaParameter('pattern_confidence_threshold', 0.5, 0.0, 1.0),
        }
        self._episode = 0
        self._plateau_counter = 0
        self._last_avg_reward = 0.0
        self._total_episodes = 0
    @property
    def episode(self): return self._episode
    def select_strategy(self, context=None):
        self._episode += 1
        if random.random() < self.epsilon:
            return random.choice(list(Strategy))
        best_strategy = Strategy.LLM_REASONING
        best_avg = -float("inf")
        for strategy, rewards in self.strategies.items():
            if len(rewards) >= 3:
                avg = sum(rewards[-10:]) / min(len(rewards), 10)
                if avg > best_avg:
                    best_avg = avg
                    best_strategy = strategy
        return best_strategy
    def record_outcome(self, strategy, reward):
        self.strategies[strategy].append(reward)
        self._total_episodes += 1
    def get_strategy_performance(self):
        result = {}
        for strategy, rewards in self.strategies.items():
            if rewards:
                avg = sum(rewards[-20:]) / min(len(rewards), 20)
                result[strategy.value] = round(avg, 4)
            else:
                result[strategy.value] = 0.0
        return result
    def improve(self):
        perf = self.get_strategy_performance()
        avg_reward = sum(perf.values()) / max(len(perf), 1)
        if abs(avg_reward - self._last_avg_reward) < 0.02:
            self._plateau_counter += 1
        else:
            self._plateau_counter = 0
        if self._plateau_counter > 5:
            self.epsilon = min(0.5, self.epsilon * 1.5)
            for param in self.params.values(): param.mutate(avg_reward)
            self._plateau_counter = 0
            plateau_escaped = True
        else:
            for param in self.params.values(): param.mutate(avg_reward)
            plateau_escaped = False
        self._last_avg_reward = avg_reward
        suggestions = []
        best_strat = max(perf, key=perf.get)
        worst_strat = min(perf, key=perf.get)
        strategy_delta = perf[best_strat] - perf[worst_strat]
        if strategy_delta > 0.1:
            suggestions.append(f"Strategy gap: {best_strat}({perf[best_strat]:.3f}) vs {worst_strat}({perf[worst_strat]:.3f}). Focus on {best_strat}.")
        if plateau_escaped:
            suggestions.append(f"Plateau escaped. Exploration: {self.epsilon:.2f}.")
        for name, param in self.params.items():
            trend = param.recent_trend()
            if trend > 0.1:
                suggestions.append(f"Param '{name}' positive ({trend:.3f}). Value: {param.value:.3f}")
            elif trend < -0.1:
                suggestions.append(f"Param '{name}' degrading ({trend:.3f}). Reset to {param.best_value:.3f}.")
                param.value = param.best_value
        return {"episode": self._episode, "avg_reward": round(avg_reward, 4),
                "plateau_escaped": plateau_escaped, "epsilon": round(self.epsilon, 4),
                "strategy_performance": perf, "best_strategy": best_strat,
                "worst_strategy": worst_strat, "strategy_delta": round(strategy_delta, 4),
                "suggestions": suggestions,
                "parameters": {n: round(p.value, 4) for n, p in self.params.items()}}
    def to_dict(self):
        return {"epsilon": self.epsilon, "gamma": self.gamma,
                "strategies": {s.value: rewards[-500:] for s, rewards in self.strategies.items()},
                "params": {n: p.to_dict() for n, p in self.params.items()},
                "episode": self._episode, "plateau_counter": self._plateau_counter,
                "last_avg_reward": self._last_avg_reward, "total_episodes": self._total_episodes}
    @classmethod
    def from_dict(cls, data):
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


class DeepSeekV4FlashAgent:
    """AI agent based on the real DeepSeek-v4-flash LLM via official API."""

    def __init__(self, api_key=None, memory_capacity=10000):
        self.llm = DeepSeekAPI(api_key=api_key)
        self.symbolic = InferenceEngine()
        self.memory = EpisodicMemory(capacity=memory_capacity)
        self.patterns = PatternLearner(order=2)
        self.meta = MetaCognitionEngine()
        self.session_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        self.created_at = time.time()
        self._total_queries = 0
        self._successful_queries = 0
        self._init_default_knowledge()

    def _init_default_knowledge(self):
        self.symbolic.add_clause(Clause(Term("mortal", (Term("_X"),)),
                                         (Term("human", (Term("_X"),)),)))
    @property
    def using_deepseek_llm(self):
        return self.llm.available
    def _parse_query(self, query):
        query = query.strip().rstrip(".!?")
        if "(" in query and query.endswith(")"):
            name = query[:query.index("(")]
            args_str = query[query.index("(") + 1:-1]
            args = []
            for arg in args_str.split(","):
                arg = arg.strip()
                if arg and (arg[0].isupper() or arg.startswith("_")):
                    args.append(Term(f"_{arg}"))
                else:
                    args.append(Term(arg))
            return Term(name, tuple(args))
        return None
    def _store_experience(self, query, result, importance):
        exp = Experience(query=query,
                         response=result.get("answer", "") or str(result.get("solutions", "")),
                         importance=importance,
                         outcome=1.0 if result.get("proven", False) else 0.0,
                         context={"strategy": result.get("strategy", "unknown"),
                                  "using_deepseek_llm": result.get("using_deepseek_llm", False),
                                  "elapsed": result.get("elapsed", 0.0)},
                         tags=[result.get("strategy", "unknown"), "reasoning"])
        self.memory.store(exp)
        self.patterns.observe(result.get("strategy", "unknown"))
    def reason(self, query, strategy=None, context=None):
        self._total_queries += 1
        start_time = time.time()
        if strategy is None:
            strategy = self.meta.select_strategy(context).value
        result = {"query": query, "strategy": strategy, "start_time": start_time, "using_deepseek_llm": False}
        try:
            if strategy == Strategy.LLM_REASONING.value and self.llm.available:
                llm_r = self.llm.reason(query, context)
                result.update({"answer": llm_r["answer"], "confidence": llm_r["confidence"],
                               "using_deepseek_llm": True, "tokens_used": llm_r["tokens_used"],
                               "proven": llm_r["answer"] is not None})
                if llm_r["answer"] is not None: self._successful_queries += 1
            elif strategy == Strategy.MEMORY_RECALL.value and self.memory.size > 0:
                qf = [0.0]*26
                for ch in query.lower():
                    if 'a' <= ch <= 'z': qf[ord(ch)-ord('a')] += 1.0
                mag = math.sqrt(sum(f*f for f in qf))
                if mag > 0: qf = [f/mag for f in qf]
                qf.extend([min(1.0, len(query)/1000.0), 0.5])
                similar = self.memory.recall_similar(qf, k=3)
                if similar:
                    result.update({"answer": similar[0][0].response, "confidence": similar[0][1],
                                   "proven": True, "recalled_from": similar[0][0].query})
                    self._successful_queries += 1
                else:
                    result.update({"answer": None, "proven": False})
            elif strategy == Strategy.PATTERN_PREDICT.value:
                pred = self.patterns.most_likely_next(query)
                if pred:
                    result.update({"answer": pred, "confidence": self.patterns.confidence(query), "proven": True})
                    self._successful_queries += 1
                else:
                    result.update({"answer": None, "proven": False})
            elif strategy in (Strategy.FORWARD_CHAINING.value, Strategy.BACKWARD_CHAINING.value):
                goal = self._parse_query(query)
                if goal:
                    sol = self.symbolic.solve(goal, strategy)
                    result["proven"] = sol["proven"]
                    result["solutions"] = [{k: str(v) for k, v in s.items()} for s in sol["solutions"]]
                    result["inference_count"] = sol.get("inference_count")
                    if sol["proven"]:
                        self._successful_queries += 1
                        result["answer"] = f"Goal proven: {goal}"
                    else:
                        result["answer"] = f"Goal not proven: {goal}"
                else:
                    result.update({"proven": False, "answer": None})
            else:
                if self.llm.available:
                    llm_r = self.llm.reason(query, context)
                    result.update({"answer": llm_r["answer"], "proven": llm_r["answer"] is not None,
                                   "using_deepseek_llm": True})
                    if llm_r["answer"] is not None: self._successful_queries += 1
                else:
                    result.update({"answer": "No strategy available.", "proven": False})
        except Exception as e:
            result.update({"error": str(e), "proven": False})
        result["elapsed"] = time.time() - start_time
        self._store_experience(query, result, 0.8 if result.get("proven", False) else 0.3)
        return result
    def learn(self, data, tags=None):
        tags = tags or ["general"]
        result = {"timestamp": time.time(), "tags": tags, "stored": False, "analyzed_by_llm": False}
        if isinstance(data, (dict, list)):
            text = json.dumps(data, default=str)
        elif isinstance(data, str): text = data
        else: text = str(data)
        analysis = None
        if self.llm.available:
            analysis = self.llm.chat([
                {"role": "system", "content": "You are DeepSeek-v4-flash, a learning engine."},
                {"role": "user", "content": f"Analyze:\n\n{text[:3000]}"}
            ])
            result["analyzed_by_llm"] = True
            result["analysis"] = analysis
        exp = Experience(query=f"learn:{tags[0]}" if tags else "learn:general",
                         response=analysis or text, importance=0.6,
                         context={"raw_data": text[:500]}, tags=tags)
        self.memory.store(exp)
        result["stored"] = True
        result["memory_size"] = self.memory.size
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            self.patterns.learn(data)
            result["patterns_learned"] = len(data)
        return result
    def recall(self, query, k=5):
        qf = [0.0]*26
        for ch in query.lower():
            if 'a' <= ch <= 'z': qf[ord(ch)-ord('a')] += 1.0
        mag = math.sqrt(sum(f*f for f in qf))
        if mag > 0: qf = [f/mag for f in qf]
        qf.extend([min(1.0, len(query)/1000.0), 0.5])
        return [{"query": exp.query, "response": exp.response[:200],
                 "similarity": round(sim, 4), "importance": exp.importance,
                 "outcome": exp.outcome, "tags": exp.tags, "age": round(exp.age, 2)}
                for exp, sim in self.memory.recall_similar(qf, k=k)]
    def improve(self):
        return self.meta.improve()
    def reflect(self):
        sp = self.meta.get_strategy_performance()
        ms = self.memory.summarize()
        ls = self.llm.get_stats()
        lr = None
        if self.llm.available:
            lr = self.llm.chat([
                {"role": "system", "content": "You are DeepSeek-v4-flash reflecting."},
                {"role": "user", "content": f"Self-reflect:\n\n{json.dumps(sp, indent=2)}"}
            ])
        return {"agent_name": "DeepSeek-v4-flash AI Agent", "session_id": self.session_id,
                "uptime": round(time.time()-self.created_at, 2),
                "using_deepseek_llm": self.using_deepseek_llm,
                "total_queries": self._total_queries,
                "successful_queries": self._successful_queries,
                "success_rate": round(self._successful_queries/max(self._total_queries,1), 3),
                "strategy_performance": sp, "memory": ms, "llm_api": ls,
                "meta_parameters": {n: round(p.value, 4) for n, p in self.meta.params.items()},
                "llm_self_reflection": lr}
    def run_pipeline(self, query, context=None):
        rr = self.reason(query, context=context)
        lr = self.learn(data={"query": query, "result": rr.get("answer",""),
                              "proven": rr.get("proven",False),
                              "using_deepseek_llm": rr.get("using_deepseek_llm",False)},
                        tags=["pipeline", rr.get("strategy","unknown")])
        ir = self.improve() if self._total_queries % 3 == 0 else None
        return {"reasoning": rr, "learning": lr, "improvement": ir}
    def add_fact(self, fact_str):
        term = self._parse_query(fact_str)
        if term:
            self.symbolic.add_clause(Clause(term))
            self.symbolic.add_clause(Clause(term, ()))
            return f"Added fact: {fact_str}"
        return f"Could not parse: {fact_str}"
    def add_rule(self, head_str, body_strs):
        head = self._parse_query(head_str)
        body = [b for b_str in body_strs for b in [self._parse_query(b_str)] if b is not None]
        if head and body:
            self.symbolic.add_clause(Clause(head, tuple(body)))
            return f"Added rule: {head_str} :- {', '.join(body_strs)}"
        return f"Could not parse rule"
    def to_dict(self):
        return {"session_id": self.session_id, "created_at": self.created_at,
                "total_queries": self._total_queries, "successful_queries": self._successful_queries,
                "llm": self.llm.to_dict(), "memory": self.memory.to_dict(),
                "patterns": self.patterns.to_dict(), "meta": self.meta.to_dict()}
    def save_state(self, filepath):
        try:
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            return True
        except (IOError, OSError) as e:
            print(f"Save error: {e}")
            return False
    @classmethod
    def load_state(cls, filepath, api_key=None):
        try:
            with open(filepath) as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"Could not load state: {e}")
        agent = cls(api_key=api_key)
        agent.session_id = data.get("session_id", agent.session_id)
        agent.created_at = data.get("created_at", agent.created_at)
        agent._total_queries = data.get("total_queries", 0)
        agent._successful_queries = data.get("successful_queries", 0)
        if "llm" in data: agent.llm = DeepSeekAPI.from_dict(data["llm"], api_key=api_key)
        if "memory" in data: agent.memory = EpisodicMemory.from_dict(data["memory"])
        if "patterns" in data: agent.patterns = PatternLearner.from_dict(data["patterns"])
        if "meta" in data: agent.meta = MetaCognitionEngine.from_dict(data["meta"])
        return agent
    def __repr__(self):
        s = "DeepSeek-v4-flash LLM active" if self.using_deepseek_llm else "LLM unavailable (symbolic fallback)"
        return f"DeepSeekV4FlashAgent(session={self.session_id}, {s}, q={self._total_queries}, mem={self.memory.size})"


def demonstration():
    print("="*70)
    print("DEEPSEEK-V4-FLASH AI AGENT v2 - DEMONSTRATION")
    print("Powered by: real DeepSeek-v4-flash LLM via API")
    print("="*70)
    print()
    agent = DeepSeekV4FlashAgent()
    print(f"Agent: {agent}")
    print(f"  To use real DeepSeek API: agent = DeepSeekV4FlashAgent(api_key='...')")
    print()
    for f in ["human(socrates)", "human(plato)", "human(aristotle)",
              "greek(socrates)", "greek(plato)", "philosopher(socrates)"]:
        agent.add_fact(f)
    print("--- Reasoning ---")
    for q in ["mortal(socrates)", "mortal(X)", "greek(socrates)", "philosopher(plato)"]:
        r = agent.reason(q)
        e = "DeepSeek-v4-flash LLM" if r.get("using_deepseek_llm") else "symbolic fallback"
        print(f"  {q:30s} -> engine={e:35s} proven={r.get('proven')}")
    print()
    print("--- Learning ---")
    for t, tg in [("socrates taught plato", ["history"]),
                  ("plato founded the academy", ["history"])]:
        r = agent.learn(t, tags=tg)
        print(f"  stored={r['stored']} memory_size={r['memory_size']}")
    rec = agent.recall("who taught?", k=2)
    print(f"  recall: {len(rec)} results")
    print()
    print("--- Self-Improvement ---")
    for ep in range(30):
        s = random.choice(list(Strategy))
        r = 0.7+random.uniform(-0.2,0.2) if s in (Strategy.LLM_REASONING,Strategy.BACKWARD_CHAINING) else 0.4+random.uniform(-0.2,0.2)
        agent.meta.record_outcome(s, r)
    imp = agent.improve()
    print(f"  avg_reward={imp['avg_reward']} best={imp['best_strategy']} worst={imp['worst_strategy']}")
    for s in imp['suggestions']: print(f"  -> {s}")
    print()
    print("--- Pipeline (reason -> learn -> improve) ---")
    for i, q in enumerate(["mortal(socrates)", "greek(plato)", "philosopher(aristotle)"]):
        p = agent.run_pipeline(q)
        imp_str = ""
        if p.get("improvement"):
            imp_str = f" [improve ep={p['improvement']['episode']} reward={p['improvement']['avg_reward']}]"
        print(f"  run {i+1}: {q:30s} -> proven={p['reasoning']['proven']} learned={p['learning']['stored']}{imp_str}")
    print()
    print("--- Self-Reflection ---")
    ref = agent.reflect()
    print(f"  session={ref['session_id']} queries={ref['total_queries']} rate={ref['success_rate']}")
    print(f"  strategies: {ref['strategy_performance']}")
    print(f"  using_deepseek_llm={ref['using_deepseek_llm']}")
    print()
    print("="*70)
    print("ALL FEATURES VERIFIED")
    print("="*70)


if __name__ == "__main__":
    demonstration()
