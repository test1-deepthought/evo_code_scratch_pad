
"""
Stochastic Lotka-Volterra Predator-Prey Simulation
Uses the Gillespie algorithm (stochastic simulation algorithm / SSA)
for exact simulation of the Markov process.

Reactions:
    R1: X -> 2X   (prey birth)        rate: α·x
    R2: X + Y -> 2Y (predation)       rate: β·x·y
    R3: Y -> ∅    (predator death)    rate: γ·y

State: (x, y) = (prey count, predator count)
"""

import random
import math
from collections import namedtuple

Event = namedtuple('Event', ['time', 'prey', 'predator', 'reaction'])

class LotkaVolterraSSA:
    """Gillespie algorithm for stochastic Lotka-Volterra system."""
    
    def __init__(self, alpha=1.0, beta=0.005, gamma=0.5,
                 prey0=100, predator0=50):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.prey0 = prey0
        self.predator0 = predator0
        self.reset()
    
    def reset(self):
        """Reset to initial conditions."""
        self.t = 0.0
        self.x = self.prey0
        self.y = self.predator0
        self.history = [Event(0.0, self.x, self.y, None)]
    
    def _propensities(self):
        """Compute reaction propensities (rates)."""
        a1 = self.alpha * self.x              # prey birth
        a2 = self.beta * self.x * self.y      # predation
        a3 = self.gamma * self.y              # predator death
        return a1, a2, a3
    
    def step(self):
        """Execute one Gillespie step. Returns True if system continues."""
        a1, a2, a3 = self._propensities()
        a_total = a1 + a2 + a3
        
        if a_total == 0.0:
            return False
        
        dt = random.expovariate(a_total)
        self.t += dt
        
        r = random.uniform(0, a_total)
        
        if r < a1:
            self.x += 1
            reaction = 'prey_birth'
        elif r < a1 + a2:
            self.x -= 1
            self.y += 1
            reaction = 'predation'
        else:
            self.y -= 1
            reaction = 'predator_death'
        
        self.history.append(Event(self.t, self.x, self.y, reaction))
        return True
    
    def run(self, t_max=50.0, max_steps=1_000_000):
        """Run simulation until t_max or max_steps."""
        self.reset()
        steps = 0
        while self.t < t_max and steps < max_steps:
            if not self.step():
                break
            steps += 1
        return self.history
    
    def sample_trajectory(self, dt=0.1, t_max=None):
        """Sample the trajectory at regular time intervals."""
        if t_max is None:
            t_max = self.t
        times, preys, predators = [], [], []
        t_target = 0.0
        i = 0
        n = len(self.history)
        
        while t_target <= t_max and i < n - 1:
            while i < n - 1 and self.history[i + 1].time <= t_target:
                i += 1
            if i >= n - 1:
                break
            times.append(t_target)
            preys.append(self.history[i].prey)
            predators.append(self.history[i].predator)
            t_target += dt
        
        return times, preys, predators
    
    def extinction_time(self):
        """Return time when first species goes extinct, or None."""
        for event in self.history:
            if event.prey == 0 or event.predator == 0:
                return event.time
        return None
    
    def statistics(self):
        """Compute summary statistics of the trajectory."""
        if not self.history:
            return {}
        
        times = [e.time for e in self.history]
        preys = [e.prey for e in self.history]
        predators = [e.predator for e in self.history]
        
        total_weight = times[-1] - times[0]
        if total_weight == 0:
            return {}
        
        avg_prey = sum(
            preys[i] * (times[i+1] - times[i])
            for i in range(len(times) - 1)
        ) / total_weight
        
        avg_predator = sum(
            predators[i] * (times[i+1] - times[i])
            for i in range(len(times) - 1)
        ) / total_weight
        
        return {
            'final_t': times[-1],
            'final_prey': preys[-1],
            'final_predator': predators[-1],
            'avg_prey': avg_prey,
            'avg_predator': avg_predator,
            'n_events': len(self.history) - 1,
            'extinction_time': self.extinction_time(),
            'max_prey': max(preys),
            'max_predator': max(predators),
            'min_prey': min(preys),
            'min_predator': min(predators),
        }


def run_ensemble(sim, n_runs=100, t_max=50.0):
    """Run multiple independent trajectories and collect statistics."""
    all_stats = []
    all_extinction_times = []
    
    for _ in range(n_runs):
        sim.run(t_max=t_max)
        stats = sim.statistics()
        all_stats.append(stats)
        if stats['extinction_time'] is not None:
            all_extinction_times.append(stats['extinction_time'])
    
    ext_proportion = sum(1 for s in all_stats if s['extinction_time'] is not None) / n_runs
    
    avg_final_prey = sum(s['final_prey'] for s in all_stats) / n_runs
    avg_final_predator = sum(s['final_predator'] for s in all_stats) / n_runs
    avg_avg_prey = sum(s['avg_prey'] for s in all_stats) / n_runs
    avg_avg_predator = sum(s['avg_predator'] for s in all_stats) / n_runs
    
    print(f"Ensemble: {n_runs} runs, t_max={t_max}")
    print(f"  Extinction proportion: {ext_proportion:.3f}")
    if all_extinction_times:
        mean_ext = sum(all_extinction_times) / len(all_extinction_times)
        print(f"  Mean extinction time (conditional): {mean_ext:.2f}")
    print(f"  Mean final prey:     {avg_final_prey:.1f}")
    print(f"  Mean final predator:  {avg_final_predator:.1f}")
    print(f"  Mean time-avg prey:   {avg_avg_prey:.1f}")
    print(f"  Mean time-avg predator: {avg_avg_predator:.1f}")
    
    return all_stats


if __name__ == "__main__":
    print("=" * 60)
    print("SINGLE TRAJECTORY DEMO")
    print("=" * 60)
    sim = LotkaVolterraSSA(alpha=1.0, beta=0.005, gamma=0.5, prey0=100, predator0=50)
    sim.run(t_max=100.0)
    stats = sim.statistics()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    ts, xs, ys = sim.sample_trajectory(dt=0.5)
    print(f"\n  Sampled at {len(ts)} points (dt=0.5)")

    print("\n" + "=" * 60)
    print("ENSEMBLE RUNS")
    print("=" * 60)
    sim2 = LotkaVolterraSSA(alpha=1.0, beta=0.005, gamma=0.5, prey0=100, predator0=50)
    run_ensemble(sim2, n_runs=100, t_max=50.0)
