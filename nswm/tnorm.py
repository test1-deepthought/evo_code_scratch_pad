"""
Differentiable t-norm composition operators.

Based on the NeSyCoCo (Kamali et al., AAAI 2025) approach of using
soft t-norm composition of predicate scores for differentiable
symbolic program execution. We implement three standard t-norms
and their dual t-conorms, all fully differentiable for gradient-based
learning.

T-norms (fuzzy conjunction):
    - Product:    T(a, b) = a * b
    - Godel:      T(a, b) = min(a, b)
    - Lukasiewicz: T(a, b) = max(0, a + b - 1)

T-conorms (fuzzy disjunction, dual via De Morgan):
    - Product:    S(a, b) = a + b - a * b
    - Godel:      S(a, b) = max(a, b)
    - Lukasiewicz: S(a, b) = min(1, a + b)

Inspired by: NeSyCoCo - Neuro-Symbolic Concept Composer
(https://arxiv.org/abs/2412.15588v1)
"""

import torch
import torch.nn as nn


class TNorm(nn.Module):
    """Differentiable t-norm base class."""

    def forward(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError

    def tconorm(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """Dual t-conorm: S(a,b) = 1 - T(1-a, 1-b)"""
        return 1.0 - self.forward(1.0 - a, 1.0 - b)


class ProductTNorm(TNorm):
    """Product t-norm: T(a,b) = a * b.
    Smooth, strictly decreasing. Good for gradient flow.
    """

    def forward(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        return a * b


class GodelTNorm(TNorm):
    """Godel t-norm: T(a,b) = min(a,b).
    Idempotent (T(x,x) = x). Good for logical interpretation.
    Uses sigmoid-based soft approximation for differentiability.
    """

    def __init__(self, temperature: float = 0.1):
        super().__init__()
        self.temperature = temperature

    def forward(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        sa = torch.sigmoid((b - a) / self.temperature)
        sb = torch.sigmoid((a - b) / self.temperature)
        return a * sa + b * sb


class LukasiewiczTNorm(TNorm):
    """Lukasiewicz t-norm: T(a,b) = max(0, a + b - 1).
    The natural choice for fuzzy logic with negation.
    """

    def __init__(self, temperature: float = 0.1):
        super().__init__()
        self.temperature = temperature

    def forward(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        raw = a + b - 1.0
        return torch.nn.functional.softplus(
            raw, beta=1.0 / self.temperature
        ) * self.temperature


def create_tnorm(name: str, **kwargs) -> TNorm:
    """Factory for creating t-norm operators by name."""
    variants = {
        "product": ProductTNorm,
        "godel": GodelTNorm,
        "lukasiewicz": LukasiewiczTNorm,
    }
    if name.lower() not in variants:
        raise ValueError(
            f"Unknown t-norm '{name}'. Choose from: {list(variants.keys())}"
        )
    return variants[name.lower()](**kwargs)
