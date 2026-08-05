"""
Symbolic rule learning and differentiable composition.

Defines transition rules as symbolic expressions over predicate scores,
composed using t-norms. Each rule has the form:

    IF condition THEN next_state_predicate

where the condition is a t-norm composition of predicate scores.
Following the NeSyCoCo approach, rules are differentiable end-to-end
through the soft t-norm composition.

A rule set is a collection of such rules that together predict the
next latent state representation from the current state and action.
"""

import torch
import torch.nn as nn

from .tnorm import TNorm, create_tnorm


class SymbolicRule(nn.Module):
    """A single differentiable symbolic rule.

    Represents: IF condition THEN effect, where:
        - condition: a t-norm composition of selected predicates
        - effect: a linear transformation mapping predicate scores to
          the predicted next-state component
    """

    def __init__(
        self,
        num_predicates: int,
        latent_dim: int,
        tnorm: TNorm,
        max_conditions: int = 4,
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.max_conditions = max_conditions
        self.tnorm = tnorm

        # Learnable soft attention over which predicates participate
        self.condition_weights = nn.Parameter(
            torch.randn(max_conditions, num_predicates) * 0.1
        )

        # Effect: maps predicate activations to latent delta (linear
        # for interpretability)
        self.effect = nn.Linear(num_predicates, latent_dim, bias=True)

        # Rule confidence (learned)
        self.confidence = nn.Parameter(torch.tensor(0.5))

    def compute_condition(
        self, predicate_scores: torch.Tensor
    ) -> torch.Tensor:
        """Compute the rule's condition score from predicate scores.

        Args:
            predicate_scores: [batch, num_predicates] in [0, 1]

        Returns:
            condition_score: [batch, 1] in [0, 1]
        """
        weights = torch.softmax(self.condition_weights, dim=-1)
        weighted = weights.unsqueeze(0) * predicate_scores.unsqueeze(1)
        condition_scores = weighted.sum(dim=-1)

        # Compose conditions using t-norm (fuzzy conjunction)
        result = condition_scores[:, 0]
        for i in range(1, self.max_conditions):
            result = self.tnorm(result, condition_scores[:, i])
        return result.unsqueeze(-1)

    def forward(
        self, predicate_scores: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply the rule.

        Args:
            predicate_scores: [batch, num_predicates] in [0, 1]

        Returns:
            delta: [batch, latent_dim] predicted latent change
            fired: [batch, 1] how strongly the rule fired
        """
        condition_strength = self.compute_condition(predicate_scores)
        confidence = torch.sigmoid(self.confidence)
        fired = condition_strength * confidence
        delta = self.effect(predicate_scores) * fired
        return delta, fired


class SymbolicTransitionRules(nn.Module):
    """A set of symbolic transition rules composing the world model.

    Replaces the black-box MLP transition predictor with an ensemble of
    symbolic rules. Each rule captures a specific transition pattern, and
    together they predict the next latent state.

    This is the core innovation bridging JEPA/Dreamer world models with
    NeSyCoCo-style differentiable symbolic reasoning.
    """

    def __init__(
        self,
        num_predicates: int,
        latent_dim: int,
        num_rules: int = 16,
        tnorm_name: str = "product",
        max_conditions_per_rule: int = 4,
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.num_rules = num_rules

        self.tnorm = create_tnorm(tnorm_name)

        self.rules = nn.ModuleList([
            SymbolicRule(
                num_predicates, latent_dim, self.tnorm, max_conditions_per_rule
            )
            for _ in range(num_rules)
        ])

        # Global transition bias (learned)
        self.global_bias = nn.Parameter(torch.zeros(latent_dim))

        # Small residual MLP for cases rules don't cover
        # (inspired by DreamerV3's RSSM residual structure)
        self.residual_mlp = nn.Sequential(
            nn.Linear(num_predicates, 64),
            nn.ReLU(),
            nn.Linear(64, latent_dim),
        )
        self.residual_scale = nn.Parameter(torch.tensor(0.1))

    def forward(
        self, predicate_scores: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """Predict next latent state delta from predicate scores.

        Args:
            predicate_scores: [batch, num_predicates] in [0, 1]

        Returns:
            dict with:
                delta: [batch, latent_dim] predicted latent change
                rule_deltas: [batch, num_rules, latent_dim] per-rule
                rule_fired: [batch, num_rules] per-rule firing strengths
                residual: [batch, latent_dim] residual MLP contribution
        """
        batch_size = predicate_scores.shape[0]
        device = predicate_scores.device

        rule_deltas = torch.zeros(
            batch_size, self.num_rules, self.latent_dim, device=device
        )
        rule_fired = torch.zeros(batch_size, self.num_rules, device=device)

        for i, rule in enumerate(self.rules):
            delta_i, fired_i = rule(predicate_scores)
            rule_deltas[:, i, :] = delta_i
            rule_fired[:, i] = fired_i.squeeze(-1)

        symbolic_delta = rule_deltas.sum(dim=1)

        residual = self.residual_mlp(predicate_scores) * torch.sigmoid(
            self.residual_scale
        )

        delta = symbolic_delta + residual + self.global_bias

        return {
            "delta": delta,
            "rule_deltas": rule_deltas,
            "rule_fired": rule_fired,
            "residual": residual,
        }

    def explain_transition(
        self, predicate_scores: torch.Tensor
    ) -> list[list[dict]]:
        """Provide human-readable explanation of which rules fired.

        Args:
            predicate_scores: [batch, num_predicates] in [0, 1]

        Returns:
            List per batch item of dicts with rule_index, confidence,
            condition_strength, firing_strength
        """
        with torch.no_grad():
            explanations = []
            for b in range(predicate_scores.shape[0]):
                batch_explanations = []
                for i, rule in enumerate(self.rules):
                    condition = rule.compute_condition(
                        predicate_scores[b : b + 1]
                    )
                    conf = torch.sigmoid(rule.confidence)
                    strength = (condition * conf).item()
                    if strength > 0.01:
                        batch_explanations.append({
                            "rule_index": i,
                            "confidence": conf.item(),
                            "condition_strength": condition.item(),
                            "firing_strength": strength,
                        })
                batch_explanations.sort(
                    key=lambda x: x["firing_strength"], reverse=True
                )
                explanations.append(batch_explanations)
            return explanations
