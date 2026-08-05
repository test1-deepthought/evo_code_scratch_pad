"""
Learned differentiable predicates for state abstraction.

Inspired by NeSyCoCo's predicate learning approach, these modules learn
to score whether a property holds over the latent state. Each predicate
outputs a value in [0, 1] interpreted as a fuzzy truth value.

Predicate types:
    - UnaryPredicate:   Property of a single state (e.g., "is_near_wall")
    - BinaryPredicate:  Relation between two states (e.g., "is_adjacent_to")
    - ActionPredicate:  Property of an action (e.g., "is_move_forward")

Architecture: A small MLP projects the latent state/action into a scalar
score, passed through sigmoid for [0,1] output.
"""

import torch
import torch.nn as nn


class UnaryPredicate(nn.Module):
    """Learned unary predicate: scores a property of a single state.

    Maps latent state z in R^{state_dim} -> score in [0, 1].
    """

    def __init__(self, state_dim: int, hidden_dim: int = 64, name: str = "p"):
        super().__init__()
        self.name = name
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Score property over state z. Returns [batch, 1] in [0, 1]."""
        return self.net(z)

    def __repr__(self) -> str:
        return f"UnaryPredicate({self.name})"


class BinaryPredicate(nn.Module):
    """Learned binary predicate: scores a relation between two states.

    Maps (z1, z2) -> score in [0, 1].
    """

    def __init__(self, state_dim: int, hidden_dim: int = 64, name: str = "r"):
        super().__init__()
        self.name = name
        self.net = nn.Sequential(
            nn.Linear(2 * state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """Score relation between z1 and z2. Returns [batch, 1] in [0, 1]."""
        return self.net(torch.cat([z1, z2], dim=-1))

    def __repr__(self) -> str:
        return f"BinaryPredicate({self.name})"


class ActionPredicate(nn.Module):
    """Learned action predicate: scores a property of an action.

    Maps action a in R^{action_dim} -> score in [0, 1].
    """

    def __init__(self, action_dim: int, hidden_dim: int = 32, name: str = "a"):
        super().__init__()
        self.name = name
        self.net = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, a: torch.Tensor) -> torch.Tensor:
        """Score property of action a. Returns [batch, 1] in [0, 1]."""
        return self.net(a)

    def __repr__(self) -> str:
        return f"ActionPredicate({self.name})"


class PredicateSet(nn.Module):
    """A collection of learned predicates forming the symbolic vocabulary.

    Manages multiple unary, binary, and action predicates that together
    define the symbolic state abstraction language.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        num_unary: int = 8,
        num_binary: int = 4,
        num_action: int = 4,
        hidden_dim: int = 64,
    ):
        super().__init__()
        self.unary = nn.ModuleList([
            UnaryPredicate(state_dim, hidden_dim, f"u{i}")
            for i in range(num_unary)
        ])
        self.binary = nn.ModuleList([
            BinaryPredicate(state_dim, hidden_dim, f"b{i}")
            for i in range(num_binary)
        ])
        self.action = nn.ModuleList([
            ActionPredicate(action_dim, hidden_dim, f"a{i}")
            for i in range(num_action)
        ])
        self.num_unary = num_unary
        self.num_binary = num_binary
        self.num_action = num_action

    def score_unary(self, z: torch.Tensor) -> torch.Tensor:
        """Score all unary predicates. Returns [batch, num_unary]."""
        scores = [p(z) for p in self.unary]
        return torch.cat(scores, dim=-1)

    def score_binary(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """Score all binary predicates. Returns [batch, num_binary]."""
        scores = [p(z1, z2) for p in self.binary]
        return torch.cat(scores, dim=-1)

    def score_action(self, a: torch.Tensor) -> torch.Tensor:
        """Score all action predicates. Returns [batch, num_action]."""
        scores = [p(a) for p in self.action]
        return torch.cat(scores, dim=-1)

    def total_predicates(self) -> int:
        return self.num_unary + self.num_binary + self.num_action
