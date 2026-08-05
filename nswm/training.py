"""
Training loop for the Neuro-Symbolic World Model.

Combines JEPA-style latent prediction objectives with NeSyCoCo-style
differentiable rule induction. The training uses two complementary losses:

1. **Latent prediction loss (JEPA-style)**: Predict the next latent state
   from the current latent state + action. Uses MSE in latent space,
   optionally with a variance-invariance-covariance regularization
   to prevent representation collapse.

2. **Rule induction loss (NeSyCoCo-style)**: Encourage the symbolic
   transition rules to be:
   - Sparse: only a few rules should fire per transition
   - Confident: fired rules should have high confidence
   - Consistent: similar transitions should fire similar rules

3. **Reconstruction loss (DreamerV3-style)**: Decode the predicted
   latent state back to observation space and compare with the true
   next observation.

4. **KL divergence**: Regularize the latent distribution toward a
   standard Gaussian prior.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from .model import NSWM


def vicreg_loss(
    z: torch.Tensor,
    lambda_var: float = 1.0,
    lambda_inv: float = 1.0,
    lambda_cov: float = 0.04,
    gamma: float = 1.0,
) -> dict[str, torch.Tensor]:
    """VICReg regularization to prevent latent collapse.

    Based on the VICReg approach used in JEPA for preventing
    representation collapse in joint embedding architectures.

    Args:
        z: [batch, latent_dim] latent representations
        lambda_var, lambda_inv, lambda_cov: loss weights
        gamma: target standard deviation for variance term

    Returns:
        dict with var_loss, inv_loss, cov_loss, total
    """
    batch_size, dim = z.shape

    # Variance loss: encourage std dev >= gamma along each dimension
    std = torch.sqrt(z.var(dim=0) + 1e-4)
    var_loss = torch.mean(F.relu(gamma - std))

    # Invariance loss: zero for single-branch (placeholder)
    inv_loss = torch.tensor(0.0, device=z.device)

    # Covariance loss: decorrelate dimensions
    z_centered = z - z.mean(dim=0)
    cov = (z_centered.T @ z_centered) / (batch_size - 1)
    # Penalize off-diagonal entries
    cov_loss = (cov.pow(2).sum() - cov.diag().pow(2).sum()) / dim

    total = lambda_var * var_loss + lambda_inv * inv_loss + lambda_cov * cov_loss

    return {
        "var_loss": var_loss,
        "inv_loss": inv_loss,
        "cov_loss": cov_loss,
        "total": total,
    }


def rule_sparsity_loss(
    rule_fired: torch.Tensor, target_sparsity: float = 0.1
) -> torch.Tensor:
    """Encourage sparse rule firing (only a few rules per transition).

    Args:
        rule_fired: [batch, num_rules] firing strengths in [0, 1]
        target_sparsity: desired mean fraction of rules firing

    Returns:
        scalar loss
    """
    mean_firing = rule_fired.mean(dim=0)
    return torch.mean((mean_firing - target_sparsity).pow(2))


def rule_confidence_loss(
    rule_fired: torch.Tensor,
) -> torch.Tensor:
    """Encourage rules that do fire to fire confidently (near 0 or 1).

    Uses a "tent" loss: penalty for values in the middle range.

    Args:
        rule_fired: [batch, num_rules] firing strengths in [0, 1]

    Returns:
        scalar loss
    """
    # Penalize values near 0.5 — encourage binary firing
    return torch.mean(rule_fired * (1.0 - rule_fired))


def rule_consistency_loss(
    rule_fired: torch.Tensor,
    predicate_scores: torch.Tensor,
    temperature: float = 0.5,
) -> torch.Tensor:
    """Encourage similar predicate scores to produce similar rule firing.

    Args:
        rule_fired: [batch, num_rules] firing strengths
        predicate_scores: [batch, num_predicates]
        temperature: softmax temperature

    Returns:
        scalar loss
    """
    # Compute similarity between all pairs of samples
    pred_norm = F.normalize(predicate_scores, dim=-1)
    sim = (pred_norm @ pred_norm.T) / temperature  # [batch, batch]

    rule_norm = F.normalize(rule_fired, dim=-1)
    rule_sim = (rule_norm @ rule_norm.T)

    # KL-divergence style: align the two similarity matrices
    sim_weights = F.softmax(sim, dim=-1)
    loss = -torch.mean(torch.sum(sim_weights * F.log_softmax(rule_sim, dim=-1), dim=-1))
    return loss


class NSWMTrainer:
    """Trainer for the Neuro-Symbolic World Model."""

    def __init__(
        self,
        model: NSWM,
        learning_rate: float = 1e-3,
        kl_weight: float = 1e-4,
        recon_weight: float = 1.0,
        latent_pred_weight: float = 1.0,
        vicreg_weight: float = 0.1,
        sparsity_weight: float = 0.01,
        confidence_weight: float = 0.01,
        consistency_weight: float = 0.01,
        device: str = "cpu",
    ):
        self.model = model.to(device)
        self.device = device
        self.kl_weight = kl_weight
        self.recon_weight = recon_weight
        self.latent_pred_weight = latent_pred_weight
        self.vicreg_weight = vicreg_weight
        self.sparsity_weight = sparsity_weight
        self.confidence_weight = confidence_weight
        self.consistency_weight = consistency_weight

        self.optimizer = torch.optim.Adam(
            model.parameters(), lr=learning_rate
        )

    def compute_loss(
        self,
        obs: torch.Tensor,
        action: torch.Tensor,
        next_obs: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Compute the full training loss.

        Args:
            obs: [batch, obs_dim] current observations
            action: [batch, action_dim] actions taken
            next_obs: [batch, obs_dim] actual next observations

        Returns:
            dict with all loss components and total
        """
        out = self.model(obs, action)

        # --- Reconstruction loss (DreamerV3-style) ---
        recon_loss = F.mse_loss(out["pred_obs"], next_obs)

        # --- KL divergence (VAE-style) ---
        kl_loss = -0.5 * torch.mean(
            1 + out["z_logvar"] - out["z_mean"].pow(2) - out["z_logvar"].exp()
        )

        # --- Latent prediction loss (JEPA-style) ---
        # Encode next observation and compare to predicted latent
        with torch.no_grad():
            next_z_mean, _ = self.model.encode(next_obs)
        latent_pred_loss = F.mse_loss(out["z_next"], next_z_mean)

        # --- VICReg on latent representations ---
        vicreg = vicreg_loss(out["z"])

        # --- Rule induction losses (NeSyCoCo-style) ---
        rule_fired = out["rule_info"]["rule_fired"]
        sparsity_loss = rule_sparsity_loss(rule_fired)
        confidence_loss = rule_confidence_loss(rule_fired)
        consistency_loss = rule_consistency_loss(
            rule_fired, out["predicate_scores"]
        )

        # --- Total ---
        total = (
            self.recon_weight * recon_loss
            + self.kl_weight * kl_loss
            + self.latent_pred_weight * latent_pred_loss
            + self.vicreg_weight * vicreg["total"]
            + self.sparsity_weight * sparsity_loss
            + self.confidence_weight * confidence_loss
            + self.consistency_weight * consistency_loss
        )

        return {
            "total": total,
            "recon_loss": recon_loss,
            "kl_loss": kl_loss,
            "latent_pred_loss": latent_pred_loss,
            "vicreg_loss": vicreg["total"],
            "sparsity_loss": sparsity_loss,
            "confidence_loss": confidence_loss,
            "consistency_loss": consistency_loss,
        }

    def train_step(
        self,
        obs: torch.Tensor,
        action: torch.Tensor,
        next_obs: torch.Tensor,
    ) -> dict[str, float]:
        """Single training step.

        Args:
            obs: [batch, obs_dim]
            action: [batch, action_dim]
            next_obs: [batch, obs_dim]

        Returns:
            dict of loss values (floats)
        """
        self.model.train()
        self.optimizer.zero_grad()

        loss_dict = self.compute_loss(obs, action, next_obs)
        loss_dict["total"].backward()

        # Gradient clipping for stability
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=10.0)

        self.optimizer.step()

        return {k: v.item() for k, v in loss_dict.items()}

    @torch.no_grad()
    def evaluate(
        self,
        obs: torch.Tensor,
        action: torch.Tensor,
        next_obs: torch.Tensor,
    ) -> dict[str, float]:
        """Evaluate the model without training.

        Also computes the mean number of rules fired per transition
        as an interpretability metric.
        """
        self.model.eval()
        loss_dict = self.compute_loss(obs, action, next_obs)

        out = self.model(obs, action)
        rule_fired = out["rule_info"]["rule_fired"]
        # Count rules fired above threshold
        num_active = (rule_fired > 0.05).float().sum(dim=1).mean()

        return {
            **{k: v.item() for k, v in loss_dict.items()},
            "mean_active_rules": num_active.item(),
        }
