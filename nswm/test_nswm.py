"""
Tests for the Neuro-Symbolic World Model.

Run with: python -m pytest nswm/test_nswm.py -v
"""

import torch
import pytest

from nswm.tnorm import ProductTNorm, GodelTNorm, LukasiewiczTNorm, create_tnorm
from nswm.predicates import (
    UnaryPredicate,
    BinaryPredicate,
    ActionPredicate,
    PredicateSet,
)
from nswm.rules import SymbolicRule, SymbolicTransitionRules
from nswm.model import NSWM, NeuroSymbolicTransition, Encoder, Decoder
from nswm.training import (
    NSWMTrainer,
    vicreg_loss,
    rule_sparsity_loss,
    rule_confidence_loss,
    rule_consistency_loss,
)
from nswm.demo import GridWorld, generate_data


# ---------------------------------------------------------------------------
# T-Norm Tests
# ---------------------------------------------------------------------------

class TestTNorms:
    def test_product_identity(self):
        tnorm = ProductTNorm()
        a = torch.tensor([0.5, 1.0, 0.0])
        b = torch.tensor([1.0, 1.0, 0.5])
        result = tnorm(a, b)
        expected = torch.tensor([0.5, 1.0, 0.0])
        assert torch.allclose(result, expected, atol=1e-6)

    def test_product_tconorm(self):
        tnorm = ProductTNorm()
        a = torch.tensor([0.3, 0.7])
        b = torch.tensor([0.4, 0.6])
        s = tnorm.tconorm(a, b)
        # S(a,b) = a + b - a*b = 1 - (1-a)*(1-b)
        expected = torch.tensor([0.58, 0.88])
        assert torch.allclose(s, expected, atol=1e-6)

    def test_godel_range(self):
        tnorm = GodelTNorm(temperature=0.01)
        a = torch.rand(100)
        b = torch.rand(100)
        result = tnorm(a, b)
        assert (result >= 0).all() and (result <= 1).all()

    def test_lukasiewicz_range(self):
        tnorm = LukasiewiczTNorm(temperature=0.05)
        a = torch.rand(100)
        b = torch.rand(100)
        result = tnorm(a, b)
        assert (result >= 0).all() and (result <= 1).all()

    def test_create_tnorm(self):
        for name in ["product", "godel", "lukasiewicz"]:
            tnorm = create_tnorm(name)
            assert tnorm is not None

        with pytest.raises(ValueError):
            create_tnorm("nonexistent")


# ---------------------------------------------------------------------------
# Predicate Tests
# ---------------------------------------------------------------------------

class TestPredicates:
    def test_unary_predicate_output_range(self):
        pred = UnaryPredicate(state_dim=8)
        z = torch.randn(16, 8)
        scores = pred(z)
        assert scores.shape == (16, 1)
        assert (scores >= 0).all() and (scores <= 1).all()

    def test_binary_predicate_output_range(self):
        pred = BinaryPredicate(state_dim=8)
        z1 = torch.randn(16, 8)
        z2 = torch.randn(16, 8)
        scores = pred(z1, z2)
        assert scores.shape == (16, 1)
        assert (scores >= 0).all() and (scores <= 1).all()

    def test_action_predicate_output_range(self):
        pred = ActionPredicate(action_dim=4)
        a = torch.randn(16, 4)
        scores = pred(a)
        assert scores.shape == (16, 1)
        assert (scores >= 0).all() and (scores <= 1).all()

    def test_predicate_set(self):
        ps = PredicateSet(state_dim=16, action_dim=4, num_unary=6, num_binary=3, num_action=4)
        z = torch.randn(8, 16)
        a = torch.randn(8, 4)

        unary_scores = ps.score_unary(z)
        assert unary_scores.shape == (8, 6)

        binary_scores = ps.score_binary(z, z)
        assert binary_scores.shape == (8, 3)

        action_scores = ps.score_action(a)
        assert action_scores.shape == (8, 4)

        assert ps.total_predicates() == 13


# ---------------------------------------------------------------------------
# Rule Tests
# ---------------------------------------------------------------------------

class TestRules:
    def test_symbolic_rule(self):
        tnorm = ProductTNorm()
        rule = SymbolicRule(num_predicates=8, latent_dim=4, tnorm=tnorm, max_conditions=3)
        scores = torch.rand(4, 8)
        delta, fired = rule(scores)
        assert delta.shape == (4, 4)
        assert fired.shape == (4, 1)
        assert (fired >= 0).all() and (fired <= 1).all()

    def test_symbolic_transition_rules(self):
        rules = SymbolicTransitionRules(
            num_predicates=12, latent_dim=8, num_rules=10, tnorm_name="product"
        )
        scores = torch.rand(4, 12)
        out = rules(scores)
        assert out["delta"].shape == (4, 8)
        assert out["rule_deltas"].shape == (4, 10, 8)
        assert out["rule_fired"].shape == (4, 10)

    def test_explain_transition(self):
        rules = SymbolicTransitionRules(
            num_predicates=12, latent_dim=8, num_rules=8
        )
        scores = torch.rand(3, 12)
        explanations = rules.explain_transition(scores)
        assert len(explanations) == 3
        for expl in explanations:
            assert isinstance(expl, list)
            for entry in expl:
                assert "rule_index" in entry
                assert "firing_strength" in entry


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestNSWM:
    def test_forward_pass_vector(self):
        model = NSWM(
            obs_dim=4, action_dim=2, latent_dim=16,
            num_unary_predicates=4, num_binary_predicates=2,
            num_action_predicates=2, num_rules=8,
            observation_type="vector",
        )
        obs = torch.randn(8, 4)
        action = torch.randn(8, 2)
        out = model(obs, action)

        assert out["z"].shape == (8, 16)
        assert out["z_next"].shape == (8, 16)
        assert out["pred_obs"].shape == (8, 4)
        assert out["predicate_scores"].shape == (8, 8)  # 4+2+2

    def test_encode_decode(self):
        model = NSWM(obs_dim=4, action_dim=2, latent_dim=16,
                      observation_type="vector")
        obs = torch.randn(4, 4)
        z_mean, z_logvar = model.encode(obs)
        assert z_mean.shape == (4, 16)
        assert z_logvar.shape == (4, 16)

        z = model.reparameterize(z_mean, z_logvar)
        assert z.shape == (4, 16)

        decoded = model.decoder(z)
        assert decoded.shape == (4, 4)

    def test_imagine_trajectory(self):
        model = NSWM(
            obs_dim=4, action_dim=2, latent_dim=16,
            num_rules=8, observation_type="vector",
        )
        z_start = torch.randn(2, 16)
        actions = torch.randn(2, 5, 2)
        traj = model.imagine_trajectory(z_start, actions, horizon=5)
        assert len(traj) == 5
        for step in traj:
            assert step["z"].shape == (2, 16)

    def test_explain_prediction(self):
        model = NSWM(
            obs_dim=4, action_dim=2, latent_dim=16,
            num_rules=6, observation_type="vector",
        )
        obs = torch.randn(3, 4)
        action = torch.randn(3, 2)
        expl = model.explain_prediction(obs, action)
        assert len(expl) == 3

    def test_neuro_symbolic_transition(self):
        trans = NeuroSymbolicTransition(
            state_dim=16, action_dim=4, latent_dim=16,
            num_unary=6, num_binary=2, num_action_preds=4, num_rules=10,
        )
        z = torch.randn(8, 16)
        a = torch.randn(8, 4)
        out = trans(z, a)
        assert out["z_next"].shape == (8, 16)
        assert out["predicate_scores"].shape == (8, 12)  # 6+2+4


# ---------------------------------------------------------------------------
# Training Tests
# ---------------------------------------------------------------------------

class TestTraining:
    def test_vicreg_loss(self):
        z = torch.randn(32, 16)
        losses = vicreg_loss(z)
        assert "total" in losses
        assert losses["total"].item() >= 0

    def test_rule_sparsity_loss(self):
        fired = torch.rand(16, 8)
        loss = rule_sparsity_loss(fired, target_sparsity=0.1)
        assert loss.item() >= 0

    def test_rule_confidence_loss(self):
        fired = torch.rand(16, 8)
        loss = rule_confidence_loss(fired)
        assert loss.item() >= 0

    def test_rule_consistency_loss(self):
        fired = torch.rand(16, 8)
        preds = torch.rand(16, 12)
        loss = rule_consistency_loss(fired, preds)
        assert loss.item() >= 0

    def test_trainer_step(self):
        model = NSWM(
            obs_dim=4, action_dim=2, latent_dim=16,
            num_unary_predicates=4, num_binary_predicates=2,
            num_action_predicates=2, num_rules=8,
            observation_type="vector",
        )
        trainer = NSWMTrainer(model, learning_rate=1e-3, device="cpu")

        obs = torch.randn(16, 4)
        actions = torch.randn(16, 2)
        next_obs = torch.randn(16, 4)

        losses = trainer.train_step(obs, actions, next_obs)
        assert "total" in losses
        assert losses["total"] < 100.0  # Should not explode

    def test_trainer_evaluate(self):
        model = NSWM(
            obs_dim=4, action_dim=2, latent_dim=16,
            num_rules=8, observation_type="vector",
        )
        trainer = NSWMTrainer(model, device="cpu")
        obs = torch.randn(8, 4)
        actions = torch.randn(8, 2)
        next_obs = torch.randn(8, 4)
        results = trainer.evaluate(obs, actions, next_obs)
        assert "mean_active_rules" in results


# ---------------------------------------------------------------------------
# Demo / Environment Tests
# ---------------------------------------------------------------------------

class TestGridWorld:
    def test_reset(self):
        env = GridWorld(size=5, seed=42)
        obs = env.reset()
        assert obs.shape == (2,)
        assert 0 <= obs[0] < 5
        assert 0 <= obs[1] < 5

    def test_step_bounds(self):
        env = GridWorld(size=5, seed=42)
        env.pos = np.array([0, 0], dtype=np.float32)
        # Try to move left from (0,0) - should stay
        next_obs, _ = env.step(2)  # LEFT
        assert next_obs[0] == 0
        assert next_obs[1] == 0

    def test_step_movement(self):
        env = GridWorld(size=5, seed=42)
        env.pos = np.array([2, 2], dtype=np.float32)
        next_obs, action = env.step(3)  # RIGHT
        assert next_obs[0] == 3
        assert next_obs[1] == 2
        assert action[3] == 1.0

    def test_generate_data(self):
        obs, actions, next_obs = generate_data(
            num_episodes=5, steps_per_episode=10, grid_size=5, seed=42
        )
        assert obs.shape == (50, 2)
        assert actions.shape == (50, 4)
        assert next_obs.shape == (50, 2)
