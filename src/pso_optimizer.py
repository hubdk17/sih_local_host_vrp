"""
pso_optimizer.py

Discrete / Permutation-based Particle Swarm Optimization (PSO) solver
for Vehicle Routing Problem (VRP) over the Chandigarh road network model.

Uses Swap Operators and Swap Sequences for discrete velocity update:
  V(t+1) = w * V(t) (+) c1*r1 * (pbest (-) X(t)) (+) c2*r2 * (gbest (-) X(t))
"""

import random
from typing import List, Tuple, Dict, Any
from src.route_evaluator import RouteEvaluator

class DiscretePSO_VRP:
    """
    Discrete Particle Swarm Optimization (PSO) for permutation-based VRP.
    """

    def __init__(
        self,
        instance,
        num_particles: int = 100,
        iterations: int = 150,
        w: float = 0.7,
        c1: float = 0.5,
        c2: float = 0.5,
        penalty_per_violation: float = 5000.0,
        random_seed: int = 42
    ):
        self.instance = instance
        self.evaluator = RouteEvaluator(instance)
        self.num_particles = num_particles
        self.iterations = iterations
        self.w = w
        self.c1 = c1
        self.c2 = c2
        self.penalty_per_violation = penalty_per_violation
        self.customer_ids = list(instance.customer_ids)

        if random_seed is not None:
            random.seed(random_seed)

    @staticmethod
    def compute_swap_sequence(p_source: List[int], p_target: List[int]) -> List[Tuple[int, int]]:
        """
        Compute the minimal sequence of swap operators (i, j) that transforms
        p_source into p_target. Equivalent to: p_target (-) p_source.
        """
        swaps = []
        temp = list(p_source)
        pos_map = {val: idx for idx, val in enumerate(temp)}

        for i in range(len(temp)):
            target_val = p_target[i]
            if temp[i] != target_val:
                j = pos_map[target_val]
                
                # Perform swap on temp
                val_i = temp[i]
                temp[i], temp[j] = temp[j], temp[i]
                pos_map[target_val] = i
                pos_map[val_i] = j

                swaps.append((i, j))

        return swaps

    @staticmethod
    def apply_swap_sequence(permutation: List[int], swap_seq: List[Tuple[int, int]]) -> List[int]:
        """Apply a sequence of swap operators to a permutation."""
        result = list(permutation)
        for i, j in swap_seq:
            result[i], result[j] = result[j], result[i]
        return result

    @staticmethod
    def scale_swap_sequence(swap_seq: List[Tuple[int, int]], prob: float) -> List[Tuple[int, int]]:
        """
        Scale a swap sequence by probability factor c.
        Retains each swap operator with probability c.
        """
        if prob <= 0:
            return []
        if prob >= 1.0:
            return list(swap_seq)

        scaled = [swap for swap in swap_seq if random.random() < prob]
        return scaled

    def evaluate_fitness(self, individual: List[int]) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate individual fitness.
        Objective: Minimize total travel time + penalty for violations.
        Fitness: Negative of total cost (higher is better).
        """
        eval_res = self.evaluator.evaluate(individual)
        total_time = eval_res["total_travel_time"]
        violations = eval_res["total_violations"]

        cap_penalty = sum(max(0, r["load"] - r["capacity"]) * 1000.0 for r in eval_res["capacity"]["reports"])
        dur_penalty = sum(max(0, r["time"] - r["max_duration"]) * 10.0 for r in eval_res["duration"]["reports"])

        total_cost = total_time + (violations * self.penalty_per_violation) + cap_penalty + dur_penalty
        fitness = -total_cost

        return fitness, eval_res

    def optimize(self) -> Dict[str, Any]:
        """
        Run the Discrete Particle Swarm Optimization loop.
        """
        # 1. Initialize Particles
        swarm_positions = []
        swarm_velocities = [] # Each velocity is a list of swap operators
        pbest_positions = []
        pbest_fitnesses = []
        pbest_evals = []

        gbest_position = None
        gbest_fitness = float("-inf")
        gbest_eval = None

        for _ in range(self.num_particles):
            pos = list(self.customer_ids)
            random.shuffle(pos)
            
            fit, eval_d = self.evaluate_fitness(pos)
            
            swarm_positions.append(pos)
            swarm_velocities.append([]) # Initial velocity is empty swap sequence
            pbest_positions.append(list(pos))
            pbest_fitnesses.append(fit)
            pbest_evals.append(eval_d)

            if fit > gbest_fitness:
                gbest_fitness = fit
                gbest_position = list(pos)
                gbest_eval = eval_d

        history_gbest_fitness = []
        history_gbest_time = []
        history_gbest_distance = []
        history_violations = []

        print(f"[PSO] Starting optimization: SwarmSize={self.num_particles}, Iterations={self.iterations}")

        # 2. Main PSO Iteration Loop
        for it in range(1, self.iterations + 1):
            for i in range(self.num_particles):
                curr_pos = swarm_positions[i]
                curr_vel = swarm_velocities[i]

                # Compute cognitive component: pbest (-) curr_pos
                cognitive_swaps = self.compute_swap_sequence(curr_pos, pbest_positions[i])
                r1 = random.random()
                scaled_cognitive = self.scale_swap_sequence(cognitive_swaps, self.c1 * r1)

                # Compute social component: gbest (-) curr_pos
                social_swaps = self.compute_swap_sequence(curr_pos, gbest_position)
                r2 = random.random()
                scaled_social = self.scale_swap_sequence(social_swaps, self.c2 * r2)

                # Scale inertia component: w * curr_vel
                scaled_inertia = self.scale_swap_sequence(curr_vel, self.w)

                # Combine velocity components: V_new = V_inertia (+) V_cognitive (+) V_social
                new_vel = scaled_inertia + scaled_cognitive + scaled_social
                
                # Limit velocity length to prevent excessive distortion
                max_swaps = len(self.customer_ids)
                if len(new_vel) > max_swaps:
                    new_vel = new_vel[:max_swaps]

                # Update Position: X_new = X_curr (+) V_new
                new_pos = self.apply_swap_sequence(curr_pos, new_vel)

                # Diversity preservation: apply 2-opt subsegment inversion with probability 0.20
                if random.random() < 0.20 and len(new_pos) >= 4:
                    idx1, idx2 = sorted(random.sample(range(len(new_pos)), 2))
                    new_pos[idx1:idx2+1] = reversed(new_pos[idx1:idx2+1])

                # Evaluate new position
                fit, eval_d = self.evaluate_fitness(new_pos)

                swarm_positions[i] = new_pos
                swarm_velocities[i] = new_vel

                # Update pbest
                if fit > pbest_fitnesses[i]:
                    pbest_fitnesses[i] = fit
                    pbest_positions[i] = list(new_pos)
                    pbest_evals[i] = eval_d

                    # Update gbest
                    if fit > gbest_fitness:
                        gbest_fitness = fit
                        gbest_position = list(new_pos)
                        gbest_eval = eval_d

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

        print("[PSO] Optimization loop finished.\n")

        return {
            "best_individual": gbest_position,
            "best_evaluation": gbest_eval,
            "history_best_fitness": history_gbest_fitness,
            "history_best_time": history_gbest_time,
            "history_best_distance": history_gbest_distance,
            "history_violations": history_violations
        }
