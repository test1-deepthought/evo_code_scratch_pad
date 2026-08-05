"""
Demonstration of the Neuro-Symbolic World Model on a simple grid-world
navigation task.

The environment is a 5x5 grid where an agent can move UP, DOWN, LEFT, RIGHT.
The world model learns to:
    1. Encode grid positions into latent representations
    2. Extract interpretable predicates (e.g., "is at edge", "is at corner")
    3. Learn symbolic transition rules for navigation dynamics
    4. Predict future states and explain which rules fire

This demo shows the full pipeline: data generation, model training,
evaluation, and rule explanation.

Run:
    python -m nswm.demo
"""

import torch
import numpy as np

from .model import NSWM
from .training import NSWMTrainer


# ---------------------------------------------------------------------------
# Grid World Environment
# ---------------------------------------------------------------------------

class GridWorld:
    """Simple 5x5 grid world with discrete movement actions.

    Actions: 0=UP, 1=DOWN, 2=LEFT, 3=RIGHT
    State: (x, y) position in [0, 4] x [0, 4]

    The agent cannot move through walls; actions that would take it
    out of bounds are no-ops.
    """

    def __init__(self, size: int = 5, seed: int = 42):
        self.size = size
        self.rng = np.random.RandomState(seed)
        self.pos = np.array([0, 0], dtype=np.float32)

    def reset(self) -> np.ndarray:
        """Reset to a random position. Returns observation."""
        self.pos = np.array([
            self.rng.randint(0, self.size),
            self.rng.randint(0, self.size),
        ], dtype=np.float32)
        return self.pos.copy()

    def step(self, action: int) -> tuple[np.ndarray, np.ndarray]:
        """Take an action. Returns (next_obs, action_onehot)."""
        prev = self.pos.copy()

        if action == 0:   # UP
            self.pos[1] = min(self.pos[1] + 1, self.size - 1)
        elif action == 1: # DOWN
            self.pos[1] = max(self.pos[1] - 1, 0)
        elif action == 2: # LEFT
            self.pos[0] = max(self.pos[0] - 1, 0)
        elif action == 3: # RIGHT
            self.pos[0] = min(self.pos[0] + 1, self.size - 1)

        action_onehot = np.zeros(4, dtype=np.float32)
        action_onehot[action] = 1.0

        return self.pos.copy(), action_onehot


def generate_data(
    num_episodes: int = 100,
    steps_per_episode: int = 20,
    grid_size: int = 5,
    seed: int = 42,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Generate training data from the grid world.

    Returns:
        obs: [N, 2] current positions
        actions: [N, 4] one-hot action vectors
        next_obs: [N, 2] next positions
    """
    env = GridWorld(size=grid_size, seed=seed)
    all_obs = []
    all_actions = []
    all_next_obs = []

    for _ in range(num_episodes):
        obs = env.reset()
        for _ in range(steps_per_episode):
            action = env.rng.randint(0, 4)
            next_obs, action_onehot = env.step(action)
            all_obs.append(obs.copy())
            all_actions.append(action_onehot)
            all_next_obs.append(next_obs.copy())
            obs = next_obs

    return (
        torch.tensor(np.stack(all_obs), dtype=torch.float32),
        torch.tensor(np.stack(all_actions), dtype=torch.float32),
        torch.tensor(np.stack(all_next_obs), dtype=torch.float32),
    )


def main():
    print("=" * 60)
    print("Neuro-Symbolic World Model (NSWM) - Grid World Demo")
    print("=" * 60)
    print()

    # --- Configuration ---
    obs_dim = 2          # (x, y) position
    action_dim = 4       # 4 discrete actions (one-hot)
    latent_dim = 16
    num_epochs = 50
    batch_size = 64
    grid_size = 5

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Latent dim: {latent_dim}, Grid size: {grid_size}x{grid_size}")
    print()

    # --- Generate data ---
    print("Generating training data...")
    obs, actions, next_obs = generate_data(
        num_episodes=100, steps_per_episode=20, grid_size=grid_size
    )
    print(f"  Generated {obs.shape[0]} transitions")
    print(f"  Obs shape: {obs.shape}, Actions shape: {actions.shape}")
    print()

    # --- Create model ---
    print("Building NSWM model...")
    model = NSWM(
        obs_dim=obs_dim,
        action_dim=action_dim,
        latent_dim=latent_dim,
        num_unary_predicates=6,
        num_binary_predicates=2,
        num_action_predicates=4,
        num_rules=12,
        tnorm_name="product",
        observation_type="vector",
    )
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {num_params:,}")
    print(f"  Predicates: {model.transition.predicates.total_predicates()}")
    print(f"  Rules: {model.transition.rules.num_rules}")
    print()

    # --- Train ---
    print("Training...")
    trainer = NSWMTrainer(
        model=model,
        learning_rate=1e-3,
        kl_weight=1e-3,
        recon_weight=1.0,
        latent_pred_weight=0.5,
        vicreg_weight=0.05,
        sparsity_weight=0.02,
        confidence_weight=0.01,
        consistency_weight=0.01,
        device=device,
    )

    obs = obs.to(device)
    actions = actions.to(device)
    next_obs = next_obs.to(device)

    n_samples = obs.shape[0]

    for epoch in range(num_epochs):
        # Shuffle
        perm = torch.randperm(n_samples)
        epoch_losses = []

        for start in range(0, n_samples, batch_size):
            idx = perm[start : start + batch_size]
            batch_obs = obs[idx]
            batch_actions = actions[idx]
            batch_next_obs = next_obs[idx]

            losses = trainer.train_step(
                batch_obs, batch_actions, batch_next_obs
            )
            epoch_losses.append(losses)

        # Compute mean losses for epoch
        mean_losses = {
            k: np.mean([l[k] for l in epoch_losses])
            for k in epoch_losses[0]
        }

        if (epoch + 1) % 10 == 0:
            print(
                f"  Epoch {epoch + 1:3d}/{num_epochs} | "
                f"total: {mean_losses['total']:.4f} | "
                f"recon: {mean_losses['recon_loss']:.4f} | "
                f"pred: {mean_losses['latent_pred_loss']:.4f} | "
                f"sparsity: {mean_losses['sparsity_loss']:.4f}"
            )

    print()

    # --- Evaluate ---
    print("Evaluating...")
    eval_losses = trainer.evaluate(obs[:200], actions[:200], next_obs[:200])
    print(f"  Recon loss:     {eval_losses['recon_loss']:.6f}")
    print(f"  Latent pred:    {eval_losses['latent_pred_loss']:.6f}")
    print(f"  Mean active rules: {eval_losses['mean_active_rules']:.2f} / 12")
    print()

    # --- Explain some predictions ---
    print("Explaining predictions (first 3 transitions)...")
    explanations = model.explain_prediction(
        obs[:3].to(device), actions[:3].to(device)
    )
    for i, expl in enumerate(explanations):
        pos = obs[i].numpy()
        act_idx = actions[i].argmax().item()
        action_names = ["UP", "DOWN", "LEFT", "RIGHT"]
        print(f"  Transition {i + 1}: pos=({pos[0]:.0f},{pos[1]:.0f}), "
              f"action={action_names[act_idx]}")
        if expl:
            for rule in expl[:3]:
                print(
                    f"    Rule {rule['rule_index']:2d}: "
                    f"strength={rule['firing_strength']:.3f}, "
                    f"condition={rule['condition_strength']:.3f}, "
                    f"confidence={rule['confidence']:.3f}"
                )
        else:
            print("    No rules fired above threshold")
    print()

    # --- Latent imagination demo ---
    print("Latent imagination demo...")
    # Start from a known position and imagine 5 steps of UP action
    z_start_mean, _ = model.encode(
        torch.tensor([[2.0, 2.0]], device=device)
    )
    imagined_actions = torch.zeros(1, 5, action_dim, device=device)
    # All UP actions
    imagined_actions[:, :, 0] = 1.0

    trajectory = model.imagine_trajectory(z_start_mean, imagined_actions, 5)
    print("  Starting from (2, 2), imagining 5 UP steps:")
    for t, step in enumerate(trajectory):
        z_t = step["z"]
        pred_obs_t = model.decoder(z_t).cpu().detach().numpy()[0]
        print(f"    Step {t + 1}: predicted pos = "
              f"({pred_obs_t[0]:.2f}, {pred_obs_t[1]:.2f})")
        active_rules = (step["rule_info"]["rule_fired"] > 0.05).sum().item()
        print(f"      ({active_rules} rules active)")

    print()
    print("=" * 60)
    print("Demo complete. The NSWM has learned:")
    print("  - A latent encoding of grid positions")
    print("  - Interpretable predicates over the latent space")
    print("  - Symbolic transition rules for each movement direction")
    print("  - The ability to imagine future trajectories in latent space")
    print("=" * 60)


if __name__ == "__main__":
    main()
