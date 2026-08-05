"""
Core NSWM architecture.

Combines JEPA-style joint embedding, DreamerV3-style RSSM components,
and NeSyCoCo-style differentiable symbolic transition rules into a
unified neuro-symbolic world model.

Architecture:
    1. Encoder:     observation -> latent state (CNN/MLP)
    2. Predicates:  latent state -> predicate scores [0,1] per predicate
    3. Symbolic Transition: predicate scores + action -> next predicate scores
       (via learned symbolic rules with t-norm composition)
    4. Decoder:     latent state -> reconstructed observation

The key innovation: the transition model (step 3) uses SymbolicTransitionRules
instead of a black-box MLP, making the world model's dynamics interpretable
as logical rules over learned predicates.
"""

import torch
import torch.nn as nn

from .predicates import PredicateSet
from .rules import SymbolicTransitionRules


class Encoder(nn.Module):
    """Encodes observations into latent representations.

    For image observations: uses a small CNN.
    For vector observations: uses an MLP.
    """

    def __init__(
        self,
        obs_dim: int | tuple[int, int, int],
        latent_dim: int,
        observation_type: str = "vector",
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.observation_type = observation_type

        if observation_type == "image":
            c, h, w = obs_dim
            self.net = nn.Sequential(
                nn.Conv2d(c, 32, 4, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(32, 64, 4, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(64, 64, 4, stride=2, padding=1),
                nn.ReLU(),
                nn.Flatten(),
            )
            # Compute conv output size
            with torch.no_grad():
                dummy = torch.zeros(1, c, h, w)
                conv_out = self.net(dummy).shape[1]
            self.head = nn.Linear(conv_out, 2 * latent_dim)
        else:
            self.net = nn.Sequential(
                nn.Linear(obs_dim, 256),
                nn.ReLU(),
                nn.Linear(256, 256),
                nn.ReLU(),
                nn.Linear(256, 2 * latent_dim),
            )

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode observation into latent mean and log-variance.

        Args:
            obs: observation tensor

        Returns:
            z_mean: [batch, latent_dim]
            z_logvar: [batch, latent_dim]
        """
        out = self.net(obs)
        z_mean, z_logvar = out.chunk(2, dim=-1)
        return z_mean, z_logvar


class Decoder(nn.Module):
    """Decodes latent states back into observations."""

    def __init__(
        self,
        latent_dim: int,
        obs_dim: int | tuple[int, int, int],
        observation_type: str = "vector",
    ):
        super().__init__()
        self.observation_type = observation_type

        if observation_type == "image":
            c, h, w = obs_dim
            self.fc = nn.Sequential(
                nn.Linear(latent_dim, 1024),
                nn.ReLU(),
                nn.Linear(1024, 64 * (h // 8) * (w // 8)),
                nn.ReLU(),
            )
            self.deconv = nn.Sequential(
                nn.ConvTranspose2d(64, 64, 4, stride=2, padding=1),
                nn.ReLU(),
                nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1),
                nn.ReLU(),
                nn.ConvTranspose2d(32, c, 4, stride=2, padding=1),
            )
        else:
            self.net = nn.Sequential(
                nn.Linear(latent_dim, 256),
                nn.ReLU(),
                nn.Linear(256, 256),
                nn.ReLU(),
                nn.Linear(256, obs_dim),
            )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Decode latent state back to observation space."""
        if self.observation_type == "image":
            h = self.fc(z)
            h = h.view(h.shape[0], 64, h.shape[-1] // 64, 1).squeeze(-1)
            # Reshape based on expected spatial dims -- handle dynamically
            spatial = int((h.shape[-1]) ** 0.5)
            if spatial * spatial == h.shape[-1]:
                h = h.view(h.shape[0], 64, spatial, spatial)
            else:
                h = h.view(h.shape[0], 64, 4, 4)
            return self.deconv(h)
        return self.net(z)


class NeuroSymbolicTransition(nn.Module):
    """Neuro-symbolic transition model: the core innovation.

    Combines:
        - Predicate extraction (neural)
        - Symbolic rule-based transition (symbolic)
        - Latent state update (neural projection)

    The forward pass:
        1. Score all predicates over current latent state
        2. Also score action predicates
        3. Concatenate into full predicate vector
        4. Apply symbolic transition rules -> delta
        5. Update latent: z_next = z_current + delta
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        latent_dim: int,
        num_unary: int = 8,
        num_binary: int = 4,
        num_action_preds: int = 4,
        num_rules: int = 16,
        tnorm_name: str = "product",
        hidden_dim: int = 64,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.latent_dim = latent_dim

        self.predicates = PredicateSet(
            state_dim=state_dim,
            action_dim=action_dim,
            num_unary=num_unary,
            num_binary=num_binary,
            num_action=num_action_preds,
            hidden_dim=hidden_dim,
        )

        total_preds = self.predicates.total_predicates()

        self.rules = SymbolicTransitionRules(
            num_predicates=total_preds,
            latent_dim=latent_dim,
            num_rules=num_rules,
            tnorm_name=tnorm_name,
        )

    def extract_predicate_scores(
        self, z: torch.Tensor, a: torch.Tensor
    ) -> torch.Tensor:
        """Extract all predicate scores from latent state and action.

        Args:
            z: [batch, state_dim] current latent state
            a: [batch, action_dim] action

        Returns:
            scores: [batch, total_predicates] in [0, 1]
        """
        unary = self.predicates.score_unary(z)
        action_preds = self.predicates.score_action(a)
        # Binary predicates compare current state to itself
        # (in practice: compare to learned prototypes or previous states)
        binary = self.predicates.score_binary(z, z)
        return torch.cat([unary, binary, action_preds], dim=-1)

    def forward(
        self, z: torch.Tensor, a: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """Predict next latent state.

        Args:
            z: [batch, state_dim] current latent state
            a: [batch, action_dim] action

        Returns:
            dict with:
                z_next: [batch, latent_dim] predicted next state
                predicate_scores: [batch, total_predicates]
                rule_info: from SymbolicTransitionRules.forward
        """
        predicate_scores = self.extract_predicate_scores(z, a)
        rule_info = self.rules(predicate_scores)
        z_next = z + rule_info["delta"]
        return {
            "z_next": z_next,
            "predicate_scores": predicate_scores,
            "rule_info": rule_info,
        }


class NSWM(nn.Module):
    """Neuro-Symbolic World Model.

    Full architecture:
        Encoder -> Latent z -> NeuroSymbolicTransition -> z_next -> Decoder

    Designed for learning world dynamics in a JEPA-style framework:
    the model predicts latent representations (not raw observations)
    and uses symbolic rules for the transition, enabling both
    structured generalization and interpretability.
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        latent_dim: int = 128,
        num_unary_predicates: int = 8,
        num_binary_predicates: int = 4,
        num_action_predicates: int = 4,
        num_rules: int = 16,
        tnorm_name: str = "product",
        observation_type: str = "vector",
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.action_dim = action_dim

        self.encoder = Encoder(obs_dim, latent_dim, observation_type)
        self.transition = NeuroSymbolicTransition(
            state_dim=latent_dim,
            action_dim=action_dim,
            latent_dim=latent_dim,
            num_unary=num_unary_predicates,
            num_binary=num_binary_predicates,
            num_action_preds=num_action_predicates,
            num_rules=num_rules,
            tnorm_name=tnorm_name,
        )
        self.decoder = Decoder(latent_dim, obs_dim, observation_type)

    def encode(
        self, obs: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode observation to latent distribution."""
        return self.encoder(obs)

    def reparameterize(
        self, z_mean: torch.Tensor, z_logvar: torch.Tensor
    ) -> torch.Tensor:
        """Sample latent using reparameterization trick."""
        std = torch.exp(0.5 * z_logvar)
        eps = torch.randn_like(std)
        return z_mean + eps * std

    def forward(
        self, obs: torch.Tensor, action: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """Full forward pass: encode -> transition -> decode.

        Args:
            obs: [batch, obs_dim] current observation
            action: [batch, action_dim] action taken

        Returns:
            dict with z, z_next, pred_obs, predicate_scores, rule_info
        """
        z_mean, z_logvar = self.encode(obs)
        z = self.reparameterize(z_mean, z_logvar)

        transition_out = self.transition(z, action)
        z_next = transition_out["z_next"]

        pred_obs = self.decoder(z_next)

        return {
            "z": z,
            "z_mean": z_mean,
            "z_logvar": z_logvar,
            "z_next": z_next,
            "pred_obs": pred_obs,
            "predicate_scores": transition_out["predicate_scores"],
            "rule_info": transition_out["rule_info"],
        }

    def imagine_trajectory(
        self,
        z_start: torch.Tensor,
        actions: torch.Tensor,
        horizon: int,
    ) -> list[dict[str, torch.Tensor]]:
        """Roll out an imagined trajectory using the symbolic transition.

        This is the JEPA/Dreamer-style latent imagination: given a
        starting latent state and a sequence of actions, predict the
        future latent states without decoding to observations.

        Args:
            z_start: [batch, latent_dim] starting latent state
            actions: [batch, horizon, action_dim] action sequence
            horizon: number of steps to imagine

        Returns:
            List of dicts with z, predicate_scores, rule_info per step
        """
        trajectory = []
        z = z_start
        for t in range(horizon):
            a = actions[:, t, :]
            out = self.transition(z, a)
            z = out["z_next"]
            trajectory.append({
                "z": z,
                "predicate_scores": out["predicate_scores"],
                "rule_info": out["rule_info"],
            })
        return trajectory

    def explain_prediction(
        self, obs: torch.Tensor, action: torch.Tensor
    ) -> list[list[dict]]:
        """Explain which symbolic rules fired for a given transition.

        Useful for interpretability and debugging the learned dynamics.

        Args:
            obs: [batch, obs_dim]
            action: [batch, action_dim]

        Returns:
            List of rule explanations per batch item
        """
        z_mean, _ = self.encode(obs)
        predicate_scores = self.transition.extract_predicate_scores(
            z_mean, action
        )
        return self.transition.rules.explain_transition(predicate_scores)
