"""
continuous_pso_optimizer.py

Continuous Particle Swarm Optimization (Continuous PSO) solver for Vehicle Routing
Problem (VRP) using Random Key / Smallest Position Value (SPV) encoding.

Positions X and Velocities V are continuous vectors in R^N.
Decoding maps sorted indices of continuous X to valid customer permutations.
"""

import random
import numpy as np
from typing import List, Tuple, Dict, Any
from src.route_evaluator import RouteEvaluator

class ContinuousPSO_VRP:
    """
    Continuous PSO optimizer using Random Key / SPV rule for VRP permutations.
    """

    def __init__(
        self,
        instance,
        num_particles: int = 100,
        iterations: int = 300,
        w_max: float = 0.9,
        w_min: float = 0.4,
        c1: float = 1.496,
        c2: float = 1.496,
        v_max: float = 2.0,
        penalty_per_violation: float = 5000.0,
        random_seed: int = 42
    ):
        self.instance = instance
        self.evaluator = RouteEvaluator(instance)
        self.num_particles = num_particles
        self.iterations = iterations
        self.w_max = w_max
        self.w_min = w_min
        self.c1 = c1
        self.c2 = c2
        self.v_max = v_max
        self.penalty_per_violation = penalty_per_violation

        self.customer_ids = np.array(instance.customer_ids)
        self.dim = len(self.customer_ids)

        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)

    def position_to_permutation(self, X: np.ndarray) -> List[int]:
        """
        Convert continuous position vector X in R^N to a discrete customer permutation
        using the Smallest Position Value (SPV) / Random Key rule.
        """
        sorted_indices = np.argsort(X)
        return [int(x) for x in self.customer_ids[sorted_indices]]

    def evaluate_fitness(self, X: np.ndarray) -> Tuple[float, Dict[str, Any], List[int]]:
        """
        Decode X to permutation and evaluate fitness on Chandigarh road graph.
        """
        permutation = self.position_to_permutation(X)
        eval_res = self.evaluator.evaluate(permutation)
        total_time = eval_res["total_travel_time"]
        violations = eval_res["total_violations"]

        cap_penalty = sum(max(0, r["load"] - r["capacity"]) * 1000.0 for r in eval_res["capacity"]["reports"])
        dur_penalty = sum(max(0, r["time"] - r["max_duration"]) * 10.0 for r in eval_res["duration"]["reports"])

        total_cost = total_time + (violations * self.penalty_per_violation) + cap_penalty + dur_penalty
        fitness = -total_cost

        return fitness, eval_res, permutation

    def optimize(self) -> Dict[str, Any]:
        """
        Run continuous PSO optimization loop.
        """
        # 1. Initialize Particles in continuous domain [-4.0, 4.0]
        X = np.random.uniform(-4.0, 4.0, size=(self.num_particles, self.dim))
        V = np.random.uniform(-self.v_max, self.v_max, size=(self.num_particles, self.dim))

        pbest_X = np.copy(X)
        pbest_fitnesses = np.full(self.num_particles, -np.inf)
        pbest_evals = [None] * self.num_particles
        pbest_perms = [None] * self.num_particles

        gbest_X = None
        gbest_fitness = -np.inf
        gbest_eval = None
        gbest_perm = None

        for i in range(self.num_particles):
            fit, eval_d, perm = self.evaluate_fitness(X[i])
            pbest_fitnesses[i] = fit
            pbest_evals[i] = eval_d
            pbest_perms[i] = perm

            if fit > gbest_fitness:
                gbest_fitness = fit
                gbest_X = np.copy(X[i])
                gbest_eval = eval_d
                gbest_perm = perm

        history_gbest_fitness = []
        history_gbest_time = []
        history_gbest_distance = []
        history_violations = []

        print(f"[Continuous PSO] Starting optimization: SwarmSize={self.num_particles}, Iterations={self.iterations}")

        # 2. Main Continuous PSO Iteration Loop
        for it in range(1, self.iterations + 1):
            # Dynamic inertia weight damping from w_max to w_min
            w = self.w_max - ((self.w_max - self.w_min) * (it / self.iterations))

            r1 = np.random.rand(self.num_particles, self.dim)
            r2 = np.random.rand(self.num_particles, self.dim)

            # Continuous Velocity Update Equation
            cognitive = self.c1 * r1 * (pbest_X - X)
            social = self.c2 * r2 * (gbest_X - X)
            V = (w * V) + cognitive + social

            # Velocity Clamping
            V = np.clip(V, -self.v_max, self.v_max)

            # Continuous Position Update
            X = X + V

            # Position Boundary Clamping
            X = np.clip(X, -10.0, 10.0)

            # Evaluate Swarm
            for i in range(self.num_particles):
                fit, eval_d, perm = self.evaluate_fitness(X[i])

                if fit > pbest_fitnesses[i]:
                    pbest_fitnesses[i] = fit
                    pbest_X[i] = np.copy(X[i])
                    pbest_evals[i] = eval_d
                    pbest_perms[i] = perm

                    if fit > gbest_fitness:
                        gbest_fitness = fit
                        gbest_X = np.copy(X[i])
                        gbest_eval = eval_d
                        gbest_perm = perm

            history_gbest_fitness.append(gbest_fitness)
            history_gbest_time.append(gbest_eval["total_travel_time"])
            history_gbest_distance.append(gbest_eval["total_distance"])
            history_violations.append(gbest_eval["total_violations"])

            if it == 1 or it % 10 == 0 or it == self.iterations:
                valid_str = "VALID" if gbest_eval["is_valid"] else f"INVALID ({gbest_eval['total_violations']} viols)"
                print(
                    f"Iter {it:3d}/{self.iterations} | "
                    f"Best Time: {gbest_eval['total_travel_time']:.1f}s | "
                    f"Distance: {gbest_eval['total_distance']:.1f}m | "
                    f"Status: {valid_str}"
                )

        print("[Continuous PSO] Optimization loop finished.\n")

        return {
            "best_individual": gbest_perm,
            "best_continuous_X": gbest_X,
            "best_evaluation": gbest_eval,
            "history_best_fitness": history_gbest_fitness,
            "history_best_time": history_gbest_time,
            "history_best_distance": history_gbest_distance,
            "history_violations": history_violations
        }
