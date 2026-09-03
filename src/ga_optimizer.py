"""
ga_optimizer.py

Genetic Algorithm (GA) solver for Vehicle Routing Problem (VRP)
over the Chandigarh road network model.

Uses Order Crossover (OX), Swap/Inversion Mutation, Elitism, and Tournament
Selection with constraint penalty evaluation.
"""

import random
from typing import List, Tuple, Dict, Any
from src.route_evaluator import RouteEvaluator

class GeneticAlgorithmVRP:
    """
    Genetic Algorithm optimizer for VRP permutation solutions.
    """

    def __init__(
        self,
        instance,
        pop_size: int = 50,
        generations: int = 100,
        crossover_prob: float = 0.85,
        mutation_prob: float = 0.25,
        tournament_size: int = 3,
        elitism_count: int = 2,
        penalty_per_violation: float = 5000.0,
        random_seed: int = 42
    ):
        self.instance = instance
        self.evaluator = RouteEvaluator(instance)
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
        Objective: Minimize total travel time + penalty for violations.
        Fitness: Negative of total cost (higher is better).
        """
        eval_res = self.evaluator.evaluate(individual)
        total_time = eval_res["total_travel_time"]
        violations = eval_res["total_violations"]

        # Penalty for capacity and duration excesses
        cap_penalty = sum(max(0, r["load"] - r["capacity"]) * 1000.0 for r in eval_res["capacity"]["reports"])
        dur_penalty = sum(max(0, r["time"] - r["max_duration"]) * 10.0 for r in eval_res["duration"]["reports"])

        total_cost = total_time + (violations * self.penalty_per_violation) + cap_penalty + dur_penalty
        fitness = -total_cost

        return fitness, eval_res

    def tournament_selection(self, population: List[List[int]], fitnesses: List[float]) -> List[int]:
        """Select best individual among a random tournament sample."""
        sample_indices = random.sample(range(len(population)), self.tournament_size)
        best_idx = max(sample_indices, key=lambda idx: fitnesses[idx])
        return list(population[best_idx])

    def order_crossover(self, parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
        """Order Crossover (OX) for permutation sequences."""
        size = len(parent1)
        if size <= 2 or random.random() > self.crossover_prob:
            return list(parent1), list(parent2)

        def ox_single(p1, p2):
            cx1, cx2 = sorted(random.sample(range(size), 2))
            child = [None] * size
            child[cx1:cx2] = p1[cx1:cx2]

            p2_filtered = [item for item in p2 if item not in child[cx1:cx2]]
            
            # Fill remaining positions
            idx = 0
            for i in range(size):
                if child[i] is None:
                    child[i] = p2_filtered[idx]
                    idx += 1
            return child

        child1 = ox_single(parent1, parent2)
        child2 = ox_single(parent2, parent1)
        return child1, child2

    def mutate(self, individual: List[int]) -> List[int]:
        """Apply Swap or Inversion mutation with mutation probability."""
        mutated = list(individual)
        size = len(mutated)

        if random.random() < self.mutation_prob and size >= 2:
            if random.random() < 0.5:
                # Swap Mutation
                i, j = random.sample(range(size), 2)
                mutated[i], mutated[j] = mutated[j], mutated[i]
            else:
                # Inversion Mutation
                i, j = sorted(random.sample(range(size), 2))
                mutated[i:j+1] = reversed(mutated[i:j+1])

        return mutated

    def optimize(self) -> Dict[str, Any]:
        """
        Run the Genetic Algorithm optimization loop.
        """
        population = self.initialize_population()

        history_best_fitness = []
        history_best_time = []
        history_best_distance = []
        history_violations = []

        global_best_ind = None
        global_best_fitness = float("-inf")
        global_best_eval = None

        print(f"[GA] Starting optimization: PopSize={self.pop_size}, Generations={self.generations}")

        for gen in range(1, self.generations + 1):
            # Evaluate population fitnesses
            eval_results = [self.evaluate_fitness(ind) for ind in population]
            fitnesses = [res[0] for res in eval_results]
            eval_dicts = [res[1] for res in eval_results]

            # Track generation best
            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_fitness = fitnesses[gen_best_idx]
            gen_best_eval = eval_dicts[gen_best_idx]
            gen_best_ind = list(population[gen_best_idx])

            if gen_best_fitness > global_best_fitness:
                global_best_fitness = gen_best_fitness
                global_best_ind = gen_best_ind
                global_best_eval = gen_best_eval

            history_best_fitness.append(global_best_fitness)
            history_best_time.append(gen_best_eval["total_travel_time"])
            history_best_distance.append(gen_best_eval["total_distance"])
            history_violations.append(gen_best_eval["total_violations"])

            if gen == 1 or gen % 10 == 0 or gen == self.generations:
                valid_str = "VALID" if gen_best_eval["is_valid"] else f"INVALID ({gen_best_eval['total_violations']} viols)"
                print(
                    f"Gen {gen:3d}/{self.generations} | "
                    f"Best Time: {gen_best_eval['total_travel_time']:.1f}s | "
                    f"Distance: {gen_best_eval['total_distance']:.1f}m | "
                    f"Status: {valid_str}"
                )

            # Build next generation with Elitism
            sorted_indices = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
            next_pop = [list(population[idx]) for idx in sorted_indices[:self.elitism_count]]

            # Fill remaining with Crossover and Mutation
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

        print("[GA] Optimization loop finished.\n")

        return {
            "best_individual": global_best_ind,
            "best_evaluation": global_best_eval,
            "history_best_fitness": history_best_fitness,
            "history_best_time": history_best_time,
            "history_best_distance": history_best_distance,
            "history_violations": history_violations
        }
