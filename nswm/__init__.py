"""
Neuro-Symbolic World Model (NSWM)
==================================

An original implementation combining ideas from:

- **JEPA** (Dawid & LeCun, 2023): Joint Embedding Predictive Architecture -
  learns latent-space world models by predicting representations rather than pixels,
  using contrastive or regularized methods to prevent collapse.
- **DreamerV3** (Hafner et al., 2023): RSSM-based world model that learns from
  imagined rollouts, achieving strong performance across diverse RL tasks.
- **UWM-JEPA** (Radha & Goktas, 2026): Unitary density-matrix latent space
  preserving joint-state spectrum during blind rollout with counterfactual targets.
- **NeSyCoCo** (Kamali et al., AAAI 2025): Differentiable symbolic program
  execution via soft t-norm composition of predicate scores, achieving SOTA
  on systematic generalization benchmarks.
- **Neuro-Symbolic Spatio-Temporal Reasoning** (Lee et al., 2022): Integration
  of neural perception with symbolic reasoning for spatio-temporal tasks.

Core innovation: Replace black-box MLP transition predictors in JEPA/Dreamer
world models with **differentiable symbolic transition rules** using learned
predicates composed via soft t-norm (product, Godel, or Lukasiewicz). This
combines the structured generalization of symbolic AI with the gradient-based
learning of deep world models.
"""

__version__ = "0.1.0"
