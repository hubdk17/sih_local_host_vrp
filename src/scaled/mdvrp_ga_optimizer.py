"""
mdvrp_ga_optimizer.py

Genetic Algorithm optimizer for Multi-Depot VRP.
Reuses the same GA logic (OX crossover, swap/inversion mutation, elitism,
tournament selection) but operates on the MDVRP evaluator/instance.
"""

import random
from typing import List, Tuple, Dict, Any
from src.scaled.mdvrp_route_evaluator import MDVRPRouteEvaluator


class MDVRPGeneticAlgorithm:
    """
    GA optimizer for MDVRP permutation solutions.
    Identical algorithmic structure to the single-depot GA,
    but uses MDVRPRouteEvaluator for multi-depot fitness evaluation.
    """

    def __init__(
        self,
        instance,
        pop_size: int = 100,
        generations: int = 200,
        crossover_prob: float = 0.85,
        mutation_prob: float = 0.25,
        tournament_size: int = 3,
        elitism_count: int = 2,
        penalty_per_violation: float = 5000.0,
        random_seed: int = 42,
    ):
        self.instance = instance
        self.evaluator = MDVRPRouteEvaluator(instance)
        self.pop_size = pop_size
        self.generations = generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.tournament_size = tournament_size
        self.elitism_count = elitism_count
        self.penalty_per_violation = penalty_per_violation
        self.customer_ids = list(instance.customer_ids)

        if random_seed is not None:
            random.seed(random_seed)

    def initialize_population(self) -> List[List[int]]:
        """Generate initial random permutation population."""
        population = []
        for _ in range(self.pop_size):
            ind = list(self.customer_ids)
            random.shuffle(ind)
            population.append(ind)
        return population

    def evaluate_fitness(self, individual: List[int]) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate individual fitness.
        Same objective as single-depot GA: minimize total travel time + penalty.
        """
        eval_res = self.evaluator.evaluate(individual)
        total_time = eval_res["total_travel_time"]
        violations = eval_res["total_violations"]

        cap_penalty = sum(
            max(0, r["load"] - r["capacity"]) * 1000.0
            for r in eval_res["capacity"]["reports"]
        )
        dur_penalty = sum(
            max(0, r["time"] - r["max_duration"]) * 10.0
            for r in eval_res["duration"]["reports"]
        )

        total_cost = total_time + (violations * self.penalty_per_violation) + cap_penalty + dur_penalty
        fitness = -total_cost
        return fitness, eval_res

    def tournament_selection(self, population: List[List[int]], fitnesses: List[float]) -> List[int]:
        """Select best individual from random tournament sample."""
        sample = random.sample(range(len(population)), self.tournament_size)
        best = max(sample, key=lambda idx: fitnesses[idx])
        return list(population[best])

    def order_crossover(self, p1: List[int], p2: List[int]) -> Tuple[List[int], List[int]]:
        """Order Crossover (OX) for permutation sequences."""
        size = len(p1)
        if size <= 2 or random.random() > self.crossover_prob:
            return list(p1), list(p2)

        def ox(parent1, parent2):
            cx1, cx2 = sorted(random.sample(range(size), 2))
            child = [None] * size
            child[cx1:cx2] = parent1[cx1:cx2]
            fill = [x for x in parent2 if x not in child[cx1:cx2]]
            idx = 0
            for i in range(size):
                if child[i] is None:
                    child[i] = fill[idx]
                    idx += 1
            return child

        return ox(p1, p2), ox(p2, p1)

    def mutate(self, individual: List[int]) -> List[int]:
        """Apply swap or inversion mutation."""
        mutated = list(individual)
        size = len(mutated)

        if random.random() < self.mutation_prob and size >= 2:
            if random.random() < 0.5:
                i, j = random.sample(range(size), 2)
                mutated[i], mutated[j] = mutated[j], mutated[i]
            else:
                i, j = sorted(random.sample(range(size), 2))
                mutated[i : j + 1] = reversed(mutated[i : j + 1])

        return mutated

    def optimize(self) -> Dict[str, Any]:
        """
        Run the GA optimization loop with per-generation diagnostics.

        Returns history with extended diversity metrics for scalability analysis.
        """
        population = self.initialize_population()

        # Extended history for scalability diagnostics
        history = {
            "generation": [],
            "best_fitness": [],
            "avg_fitness": [],
            "best_distance": [],
            "best_travel_time": [],
            "best_violations": [],
            "num_valid": [],
            "num_invalid": [],
            "unique_permutations": [],
            "population_diversity": [],
        }

        global_best_ind = None
        global_best_fitness = float("-inf")
        global_best_eval = None

        print(
            f"[MDVRP-GA] Starting: Pop={self.pop_size}, Gen={self.generations}, "
            f"Customers={len(self.customer_ids)}, Vehicles={self.instance.num_vehicles}, "
            f"Depots={self.instance.num_depots}"
        )

        for gen in range(1, self.generations + 1):
            # Evaluate population
            eval_results = [self.evaluate_fitness(ind) for ind in population]
            fitnesses = [r[0] for r in eval_results]
            eval_dicts = [r[1] for r in eval_results]

            # Generation best
            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_fitness = fitnesses[gen_best_idx]
            gen_best_eval = eval_dicts[gen_best_idx]

            if gen_best_fitness > global_best_fitness:
                global_best_fitness = gen_best_fitness
                global_best_ind = list(population[gen_best_idx])
                global_best_eval = gen_best_eval

            # Diversity metrics
            avg_fitness = sum(fitnesses) / len(fitnesses)
            num_valid = sum(1 for e in eval_dicts if e["is_valid"])
            num_invalid = len(eval_dicts) - num_valid
            unique_perms = len(set(tuple(ind) for ind in population))

            # Population diversity: average pairwise Hamming distance (sampled)
            diversity = 0.0
            sample_size = min(20, len(population))
            sampled = random.sample(range(len(population)), sample_size)
            pair_count = 0
            for si in range(len(sampled)):
                for sj in range(si + 1, len(sampled)):
                    ind_a = population[sampled[si]]
                    ind_b = population[sampled[sj]]
                    hamming = sum(1 for a, b in zip(ind_a, ind_b) if a != b)
                    diversity += hamming
                    pair_count += 1
            if pair_count > 0:
                diversity /= pair_count

            # Record history
            history["generation"].append(gen)
            history["best_fitness"].append(global_best_fitness)
            history["avg_fitness"].append(avg_fitness)
            history["best_distance"].append(global_best_eval["total_distance"])
            history["best_travel_time"].append(global_best_eval["total_travel_time"])
            history["best_violations"].append(global_best_eval["total_violations"])
            history["num_valid"].append(num_valid)
            history["num_invalid"].append(num_invalid)
            history["unique_permutations"].append(unique_perms)
            history["population_diversity"].append(diversity)

            if gen == 1 or gen % 10 == 0 or gen == self.generations:
                valid_str = (
                    "VALID" if global_best_eval["is_valid"]
                    else f"INVALID ({global_best_eval['total_violations']} viols)"
                )
                print(
                    f"Gen {gen:3d}/{self.generations} | "
                    f"Best Time: {global_best_eval['total_travel_time']:.1f}s | "
                    f"Dist: {global_best_eval['total_distance']:.1f}m | "
                    f"Valid: {num_valid}/{self.pop_size} | "
                    f"Diversity: {diversity:.1f} | "
                    f"Status: {valid_str}"
                )

            # Build next generation
            sorted_idx = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
            next_pop = [list(population[idx]) for idx in sorted_idx[: self.elitism_count]]

            while len(next_pop) < self.pop_size:
                p1 = self.tournament_selection(population, fitnesses)
                p2 = self.tournament_selection(population, fitnesses)
                c1, c2 = self.order_crossover(p1, p2)
                c1 = self.mutate(c1)
                next_pop.append(c1)
                if len(next_pop) < self.pop_size:
                    c2 = self.mutate(c2)
                    next_pop.append(c2)

            population = next_pop

        print("[MDVRP-GA] Optimization finished.\n")

        return {
            "best_individual": global_best_ind,
            "best_evaluation": global_best_eval,
            "history": history,
        }
