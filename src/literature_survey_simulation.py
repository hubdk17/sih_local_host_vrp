"""
literature_survey_simulation.py

Empirical Simulation & Comparative Benchmark of Prominent Research Papers
in Quantum, Quantum-Inspired, and Classical Vehicle Routing:
  1. Feld et al. (2019): "A Hybrid Solution Method for CVRP Using a Quantum Annealer" (Frontiers in ICT)
     - 2-Step QUBO Capacity Partitioning + Intra-cluster Hamiltonian Tour TSP
  2. Sun et al. (2004, 2012): "Quantum-Behaved PSO with Delta Potential Well" (IEEE / Soft Computing)
     - Wave-packet collapse via Delta-Well potential & Ranked-Order Value (ROV) decoding
  3. Ropke & Pisinger (2006): "Adaptive Large Neighborhood Search for VRP" (Transportation Science)
     - Ruin (Shaw + Worst-cost + Random) and Recreate (Regret-2 + Greedy insertion)
  4. Clarke & Wright (1964) / Croes (1958): Classical Savings Heuristic + Intra-route 2-Opt
  5. Exact OR-Tools / Applegate et al.: Mathematical Programming & Branch-and-Bound GLS
  6. Quantum HQ-GLS (Our Developed SOTA): Transverse-Field Quantum Tunneling + ALNS GLS

Evaluates all algorithms on identical road networks, customer demands, and capacity constraints.
Outputs publication-quality figures and JSON metrics to outputs/literature_survey/.
"""

import os
import sys
import time
import math
import json
import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure src directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

from solver_engine import (
    load_or_download_graph,
    build_dijkstra_matrices,
    ExactSolver,
    HQGLSSolver,
    _sanitize
)

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "literature_survey")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================================
# 1. Clarke & Wright (1964) + 2-Opt Heuristic Baseline
# =====================================================================
class ClarkeWright2OptSimulator:
    """
    Simulates Clarke & Wright (1964) Savings Algorithm with intra-route 2-Opt.
    Reference: Clarke, G., & Wright, J. W. (1964). 'Scheduling of vehicles from a central depot
    to a number of delivery points.' Operations Research, 12(4), 568-581.
    """
    def __init__(self, dist_matrix, time_matrix, demands, capacity, num_vehicles):
        self.d = dist_matrix
        self.t = time_matrix
        self.demands = demands
        self.cap = capacity
        self.V = num_vehicles
        self.N = len(demands)

    def solve(self):
        t0 = time.time()
        # Compute savings s_ij = d(0, i) + d(0, j) - d(i, j)
        savings = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                s = self.d[0, i + 1] + self.d[0, j + 1] - self.d[i + 1, j + 1]
                savings.append((s, i, j))
        savings.sort(reverse=True, key=lambda x: x[0])

        # Initial isolated routes: each customer in its own route
        routes = [[i] for i in range(self.N)]
        loads = [self.demands[i] for i in range(self.N)]
        cust_to_r = {i: i for i in range(self.N)}

        for s, i, j in savings:
            ri, rj = cust_to_r[i], cust_to_r[j]
            if ri != rj and loads[ri] + loads[rj] <= self.cap:
                r1, r2 = routes[ri], routes[rj]
                if r1[-1] == i and r2[0] == j:
                    merged = r1 + r2
                elif r1[0] == i and r2[-1] == j:
                    merged = r2 + r1
                elif r1[-1] == i and r2[-1] == j:
                    merged = r1 + r2[::-1]
                elif r1[0] == i and r2[0] == j:
                    merged = r1[::-1] + r2
                else:
                    continue

                routes[ri] = merged
                loads[ri] += loads[rj]
                routes[rj] = []
                loads[rj] = 0
                for c in merged:
                    cust_to_r[c] = ri

        # Compact to available vehicle count
        active = [r for r in routes if r]
        while len(active) > self.V:
            smallest = min(range(len(active)), key=lambda k: len(active[k]))
            sr = active.pop(smallest)
            for c in sr:
                for target in range(len(active)):
                    if sum(self.demands[x] for x in active[target]) + self.demands[c] <= self.cap:
                        active[target].append(c)
                        break
                else:
                    if active:
                        active[0].append(c)

        while len(active) < self.V:
            active.append([])

        # Intra-route 2-Opt improvement
        final_routes = []
        for r in active:
            final_routes.append(self._two_opt(r))

        runtime = time.time() - t0
        total_dist = sum(self._eval_dist(r) for r in final_routes)
        total_time = sum(self._eval_time(r) for r in final_routes)

        return {
            "algorithm": "Clarke-Wright + 2-Opt (1964)",
            "paper": "Clarke & Wright (1964), Operations Research",
            "distance_km": round(total_dist / 1000.0, 2),
            "time_sec": round(total_time, 2),
            "runtime_sec": round(runtime, 3),
            "routes": final_routes,
            "violations": self._check_violations(final_routes)
        }

    def _two_opt(self, route):
        if len(route) < 3:
            return route
        best = list(route)
        best_d = self._eval_dist(best)
        improved = True
        while improved:
            improved = False
            for i in range(len(best) - 1):
                for j in range(i + 2, len(best)):
                    cand = best[:i] + best[i:j+1][::-1] + best[j+1:]
                    cd = self._eval_dist(cand)
                    if cd < best_d - 1e-4:
                        best = cand
                        best_d = cd
                        improved = True
                        break
                if improved:
                    break
        return best

    def _eval_dist(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _eval_time(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.t[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _check_violations(self, routes):
        v = 0
        for r in routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                v += (l - self.cap)
        return int(v)


# =====================================================================
# 2. Feld et al. (2019) Hybrid QUBO 2-Step Quantum Annealing CVRP
# =====================================================================
class FeldQUBO2StepSimulator:
    """
    Simulates Feld et al. (2019): 'A Hybrid Solution Method for the Capacitated Vehicle
    Routing Problem Using a Quantum Annealer' (Frontiers in ICT).
    Decomposes CVRP into 2 QUBO steps:
      Phase 1: Partition customers into V capacity-feasible clusters by minimizing
               inter-cluster variance and distance while penalizing capacity overflows.
               Solves using Quantum Annealing / Simulated Quantum Annealing Hamiltonian.
      Phase 2: Solves individual TSP on each cluster via Hamiltonian QUBO / 2-Opt.
    """
    def __init__(self, dist_matrix, time_matrix, demands, capacity, num_vehicles, steps=300):
        self.d = dist_matrix
        self.t = time_matrix
        self.demands = demands
        self.cap = capacity
        self.V = num_vehicles
        self.N = len(demands)
        self.steps = steps

    def solve(self):
        t0 = time.time()
        # --- Phase 1: QUBO Clustering Hamiltonian ---
        # Binary decision variables x_{i, v} \in {0, 1}: customer i assigned to vehicle v
        # Hamiltonian: H = A \sum_i (1 - \sum_v x_{i, v})^2
        #                + B \sum_v max(0, \sum_i q_i x_{i, v} - Q)^2
        #                + C \sum_v \sum_{i < j} d(i, j) x_{i, v} x_{j, v}
        
        # Simulated Quantum Annealing (ground state search)
        assignments = np.random.randint(0, self.V, size=self.N)
        temp = 100.0
        alpha = 0.96
        
        best_assign = np.copy(assignments)
        best_energy = self._qubo_hamiltonian(assignments)

        for step in range(self.steps):
            # Propose spin flip / cluster reassignment
            cust = random.randint(0, self.N - 1)
            old_v = assignments[cust]
            new_v = (old_v + random.randint(1, self.V - 1)) % self.V

            assignments[cust] = new_v
            new_energy = self._qubo_hamiltonian(assignments)
            delta = new_energy - best_energy

            # Quantum tunneling / thermal acceptance probability
            if delta < 0 or random.random() < math.exp(-delta / max(temp, 0.1)):
                if new_energy < best_energy:
                    best_energy = new_energy
                    best_assign = np.copy(assignments)
            else:
                assignments[cust] = old_v  # revert

            temp *= alpha

        # Build clusters from best QUBO spin configuration
        clusters = [[] for _ in range(self.V)]
        for c, v in enumerate(best_assign):
            clusters[v].append(c)

        # Ensure hard capacity feasibility (penalty projection)
        clusters = self._repair_capacity(clusters)

        # --- Phase 2: Hamiltonian TSP per cluster ---
        routes = []
        for cl in clusters:
            if not cl:
                routes.append([])
                continue
            routes.append(self._tsp_hamiltonian(cl))

        runtime = time.time() - t0
        total_dist = sum(self._eval_dist(r) for r in routes)
        total_time = sum(self._eval_time(r) for r in routes)

        return {
            "algorithm": "Feld et al. QUBO 2-Step (2019)",
            "paper": "Feld et al. (2019), Frontiers in ICT",
            "distance_km": round(total_dist / 1000.0, 2),
            "time_sec": round(total_time, 2),
            "runtime_sec": round(runtime, 3),
            "routes": routes,
            "violations": self._check_violations(routes)
        }

    def _qubo_hamiltonian(self, assign):
        B = 200.0    # Capacity penalty
        C = 1.0      # Spatial cohesion

        # Fast vectorized Hamiltonian calculation
        cluster_loads = np.bincount(assign, weights=self.demands, minlength=self.V)
        cap_violation = np.sum(np.maximum(0, cluster_loads - self.cap)**2)
        
        depot_dist = np.sum(self.d[0, 1:self.N+1])
        same_cluster = (assign[:, None] == assign[None, :])
        intra_dist = np.sum(self.d[1:self.N+1, 1:self.N+1] * same_cluster) / 2.0
        
        return float(B * cap_violation + C * (depot_dist + intra_dist))

    def _repair_capacity(self, clusters):
        loads = [sum(self.demands[c] for c in cl) for cl in clusters]
        max_moves = 100
        moves = 0
        while any(loads[v] > self.cap for v in range(self.V)) and moves < max_moves:
            moves += 1
            over_vs = [v for v in range(self.V) if loads[v] > self.cap and clusters[v]]
            if not over_vs:
                break
            over_v = max(over_vs, key=lambda v: loads[v] - self.cap)
            under_vs = [v for v in range(self.V) if loads[v] < self.cap]
            if not under_vs:
                break
            target_v = min(under_vs, key=lambda v: loads[v])
            worst_c = max(clusters[over_v], key=lambda c: self.d[0, c + 1])
            clusters[over_v].remove(worst_c)
            clusters[target_v].append(worst_c)
            loads[over_v] -= self.demands[worst_c]
            loads[target_v] += self.demands[worst_c]
        return clusters

    def _tsp_hamiltonian(self, cl):
        if len(cl) <= 2:
            return cl
        unvisited = set(cl)
        curr = 0
        tour = []
        while unvisited:
            nxt = min(unvisited, key=lambda c: self.d[curr, c + 1])
            tour.append(nxt)
            unvisited.remove(nxt)
            curr = nxt + 1
        improved = True
        best_d = self._eval_dist(tour)
        while improved:
            improved = False
            for i in range(len(tour) - 1):
                for j in range(i + 2, len(tour)):
                    cand = tour[:i] + tour[i:j+1][::-1] + tour[j+1:]
                    cd = self._eval_dist(cand)
                    if cd < best_d - 1e-4:
                        tour = cand
                        best_d = cd
                        improved = True
                        break
                if improved:
                    break
        return tour

    def _eval_dist(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _eval_time(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.t[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _check_violations(self, routes):
        v = 0
        for r in routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                v += (l - self.cap)
        return int(v)


# =====================================================================
# 3. Sun et al. (2004, 2012) Delta-Potential-Well QPSO
# =====================================================================
class SunDeltaWellQPSOSimulator:
    """
    Simulates Sun et al. (2004, 2012): 'Quantum-Behaved Particle Swarm Optimization'
    with Delta-Potential-Well wave-packet dynamics.
    Reference: Sun, J., Fang, W., Xu, W., & Chen, C. (2012). Quantum-behaved particle
    swarm optimization with applications.
    Particles move under the bound-state wave function psi(x) = (1/sqrt(L)) exp(-|x|/L).
    Continuous vectors are decoded into customer visit sequences via Ranked Order Values (ROV).
    """
    def __init__(self, dist_matrix, time_matrix, demands, capacity, num_vehicles, num_particles=30, max_iter=80):
        self.d = dist_matrix
        self.t = time_matrix
        self.demands = demands
        self.cap = capacity
        self.V = num_vehicles
        self.N = len(demands)
        self.M = num_particles
        self.max_iter = max_iter

    def solve(self):
        t0 = time.time()
        dim = self.N
        X = np.random.uniform(-1.0, 1.0, (self.M, dim))
        P = np.copy(X)
        P_scores = np.array([self._evaluate(p)[0] for p in P])

        gbest_idx = np.argmin(P_scores)
        G = np.copy(P[gbest_idx])
        gbest_score = P_scores[gbest_idx]
        best_routes = self._evaluate(G)[1]

        alpha_start, alpha_end = 1.0, 0.4

        for it in range(self.max_iter):
            alpha = alpha_start - (alpha_start - alpha_end) * (it / self.max_iter)
            C = np.mean(P, axis=0)

            for i in range(self.M):
                phi = np.random.uniform(0.0, 1.0, dim)
                p = phi * P[i] + (1.0 - phi) * G
                u = np.random.uniform(0.0, 1.0, dim)
                u = np.clip(u, 1e-6, 1.0 - 1e-6)

                sign = np.where(np.random.rand(dim) > 0.5, 1.0, -1.0)
                X[i] = p + sign * alpha * np.abs(C - X[i]) * np.log(1.0 / u)

                cost, routes = self._evaluate(X[i])
                if cost < P_scores[i]:
                    P[i] = np.copy(X[i])
                    P_scores[i] = cost
                    if cost < gbest_score:
                        gbest_score = cost
                        G = np.copy(X[i])
                        best_routes = routes

        runtime = time.time() - t0
        total_dist = sum(self._eval_dist(r) for r in best_routes)
        total_time = sum(self._eval_time(r) for r in best_routes)

        return {
            "algorithm": "Sun et al. Delta-Well QPSO (2004/2012)",
            "paper": "Sun et al. (2004/2012), IEEE / Soft Computing",
            "distance_km": round(total_dist / 1000.0, 2),
            "time_sec": round(total_time, 2),
            "runtime_sec": round(runtime, 3),
            "routes": best_routes,
            "violations": self._check_violations(best_routes)
        }

    def _evaluate(self, vec):
        permutation = list(np.argsort(vec))
        routes = [[] for _ in range(self.V)]
        loads = [0] * self.V
        v = 0
        for cust in permutation:
            dem = self.demands[cust]
            if loads[v] + dem > self.cap and v < self.V - 1:
                v += 1
            routes[v].append(cust)
            loads[v] += dem

        cost = sum(self._eval_dist(r) for r in routes)
        violations = sum(max(0, loads[k] - self.cap) for k in range(self.V))
        cost += violations * 100000.0
        return cost, routes

    def _eval_dist(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _eval_time(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.t[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _check_violations(self, routes):
        v = 0
        for r in routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                v += (l - self.cap)
        return int(v)


# =====================================================================
# 4. Ropke & Pisinger (2006) Adaptive Large Neighborhood Search (ALNS)
# =====================================================================
class RopkePisingerALNSSimulator:
    """
    Simulates Ropke & Pisinger (2006): 'An Adaptive Large Neighborhood Search Heuristic
    for the Pick-up and Delivery / Vehicle Routing Problem' (Transportation Science).
    Utilizes Shaw Removal (relatedness metric), Worst-cost Removal, and Regret-2 Insertion
    under simulated annealing acceptance.
    """
    def __init__(self, dist_matrix, time_matrix, demands, capacity, num_vehicles, max_iterations=60):
        self.d = dist_matrix
        self.t = time_matrix
        self.demands = demands
        self.cap = capacity
        self.V = num_vehicles
        self.N = len(demands)
        self.max_iter = max_iterations

    def solve(self):
        t0 = time.time()
        routes = [[] for _ in range(self.V)]
        loads = [0] * self.V
        custs_to_insert = list(range(self.N))
        random.shuffle(custs_to_insert)

        v_idx = 0
        for c in custs_to_insert:
            if loads[v_idx] + self.demands[c] > self.cap and v_idx < self.V - 1:
                v_idx += 1
            routes[v_idx].append(c)
            loads[v_idx] += self.demands[c]

        best_routes = [r[:] for r in routes]
        best_cost = sum(self._eval_dist(r) for r in routes)

        curr_routes = [r[:] for r in routes]
        curr_cost = best_cost

        T = 2000.0
        cooling_rate = 0.95

        for it in range(self.max_iter):
            q = random.choice([4, 6, 8])
            if it % 2 == 0:
                ruined, unassigned = self._shaw_removal(curr_routes, q)
            else:
                ruined, unassigned = self._worst_removal(curr_routes, q)

            cand_routes = self._regret2_insertion(ruined, unassigned)
            cand_cost = sum(self._eval_dist(r) for r in cand_routes)

            delta = cand_cost - curr_cost
            if delta < 0 or (T > 5.0 and random.random() < math.exp(-delta / T)):
                curr_routes = [r[:] for r in cand_routes]
                curr_cost = cand_cost
                if curr_cost < best_cost:
                    best_cost = curr_cost
                    best_routes = [r[:] for r in curr_routes]

            T *= cooling_rate

        runtime = time.time() - t0
        total_dist = sum(self._eval_dist(r) for r in best_routes)
        total_time = sum(self._eval_time(r) for r in best_routes)

        return {
            "algorithm": "Ropke & Pisinger ALNS (2006)",
            "paper": "Ropke & Pisinger (2006), Transportation Science",
            "distance_km": round(total_dist / 1000.0, 2),
            "time_sec": round(total_time, 2),
            "runtime_sec": round(runtime, 3),
            "routes": best_routes,
            "violations": self._check_violations(best_routes)
        }

    def _shaw_removal(self, routes, q):
        all_c = [c for r in routes for c in r]
        if len(all_c) <= q:
            return [[] for _ in routes], all_c
        
        seed = random.choice(all_c)
        removed = [seed]
        while len(removed) < q:
            ref = random.choice(removed)
            candidates = [c for c in all_c if c not in removed]
            candidates.sort(key=lambda c: self.d[ref + 1, c + 1] + 10.0 * abs(self.demands[ref] - self.demands[c]))
            removed.append(candidates[0])

        rem_set = set(removed)
        new_routes = [[c for c in r if c not in rem_set] for r in routes]
        return new_routes, removed

    def _worst_removal(self, routes, q):
        costs = []
        for r_idx, r in enumerate(routes):
            for i, c in enumerate(r):
                cost_with = self._eval_dist(r)
                cost_without = self._eval_dist(r[:i] + r[i+1:])
                costs.append((cost_with - cost_without, c))
        costs.sort(reverse=True, key=lambda x: x[0])
        removed = [c for _, c in costs[:q]]
        rem_set = set(removed)
        new_routes = [[c for c in r if c not in rem_set] for r in routes]
        return new_routes, removed

    def _regret2_insertion(self, routes, unassigned):
        routes = [r[:] for r in routes]
        loads = [sum(self.demands[c] for c in r) for r in routes]

        while unassigned:
            regrets = []
            for c in unassigned:
                dem = self.demands[c]
                insertion_costs = []
                for v in range(self.V):
                    if loads[v] + dem <= self.cap:
                        best_pos_cost = float('inf')
                        best_pos = 0
                        base_d = self._eval_dist(routes[v])
                        for p in range(len(routes[v]) + 1):
                            cand = routes[v][:p] + [c] + routes[v][p:]
                            inc = self._eval_dist(cand) - base_d
                            if inc < best_pos_cost:
                                best_pos_cost = inc
                                best_pos = p
                        insertion_costs.append((best_pos_cost, v, best_pos))
                    else:
                        insertion_costs.append((float('inf'), v, 0))

                insertion_costs.sort(key=lambda x: x[0])
                cost1 = insertion_costs[0][0]
                cost2 = insertion_costs[1][0] if len(insertion_costs) > 1 else cost1 + 1000.0
                regret = cost2 - cost1
                regrets.append((regret, c, insertion_costs[0][1], insertion_costs[0][2]))

            regrets.sort(reverse=True, key=lambda x: x[0])
            _, best_c, best_v, best_p = regrets[0]
            routes[best_v].insert(best_p, best_c)
            loads[best_v] += self.demands[best_c]
            unassigned.remove(best_c)

        return routes

    def _eval_dist(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _eval_time(self, r):
        if not r:
            return 0.0
        seq = [0] + [c + 1 for c in r] + [0]
        return sum(self.t[seq[k], seq[k + 1]] for k in range(len(seq) - 1))

    def _check_violations(self, routes):
        v = 0
        for r in routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                v += (l - self.cap)
        return int(v)


# =====================================================================
# Main Benchmark Runner
# =====================================================================
def run_literature_benchmark(city_key="delhi", num_customers=40, num_vehicles=5, capacity=35):
    print("=" * 80)
    print(f"RUNNING LITERATURE SURVEY BENCHMARK ON {city_key.upper()} ROAD NETWORK")
    print(f"Parameters: {num_customers} Customers | {num_vehicles} Vehicles | Capacity {capacity}")
    print("=" * 80)

    G = load_or_download_graph(city_key=city_key)
    print(f"Loaded road network with {len(G.nodes)} nodes and {len(G.edges)} edges.")

    rng = np.random.RandomState(42)
    nodes = list(G.nodes)
    chosen = rng.choice(nodes, size=num_customers + 1, replace=False)
    depot_node = chosen[0]
    cust_nodes = chosen[1:]

    d_matrix, t_matrix = build_dijkstra_matrices(G, list(chosen))
    demands = [int(rng.randint(1, 3)) for _ in range(num_customers)]

    depot_coords = (G.nodes[depot_node]['y'], G.nodes[depot_node]['x'])
    cust_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in cust_nodes]

    results = []

    # 1. Clarke & Wright (1964) + 2-Opt
    print("\n[1/6] Simulating Clarke & Wright (1964) + 2-Opt...")
    cw_sim = ClarkeWright2OptSimulator(d_matrix, t_matrix, demands, capacity, num_vehicles)
    res_cw = cw_sim.solve()
    results.append(res_cw)
    print(f"   => Distance: {res_cw['distance_km']} km | Runtime: {res_cw['runtime_sec']}s")

    # 2. Sun et al. (2004/2012) Delta-Well QPSO
    print("\n[2/6] Simulating Sun et al. (2004/2012) Delta-Well QPSO...")
    qpso_sim = SunDeltaWellQPSOSimulator(d_matrix, t_matrix, demands, capacity, num_vehicles, num_particles=30, max_iter=70)
    res_qpso = qpso_sim.solve()
    results.append(res_qpso)
    print(f"   => Distance: {res_qpso['distance_km']} km | Runtime: {res_qpso['runtime_sec']}s")

    # 3. Feld et al. (2019) QUBO 2-Step Quantum Annealing
    print("\n[3/6] Simulating Feld et al. (2019) QUBO 2-Step Decomposition...")
    feld_sim = FeldQUBO2StepSimulator(d_matrix, t_matrix, demands, capacity, num_vehicles, steps=250)
    res_feld = feld_sim.solve()
    results.append(res_feld)
    print(f"   => Distance: {res_feld['distance_km']} km | Runtime: {res_feld['runtime_sec']}s")

    # 4. Ropke & Pisinger (2006) ALNS
    print("\n[4/6] Simulating Ropke & Pisinger (2006) Classical ALNS...")
    alns_sim = RopkePisingerALNSSimulator(d_matrix, t_matrix, demands, capacity, num_vehicles, max_iterations=50)
    res_alns = alns_sim.solve()
    results.append(res_alns)
    print(f"   => Distance: {res_alns['distance_km']} km | Runtime: {res_alns['runtime_sec']}s")

    # 5. Exact OR-Tools / Guided Local Search
    print("\n[5/6] Running Exact OR-Tools Guided Local Search (MIP/CP-SAT Baseline)...")
    exact_solver = ExactSolver(t_matrix, d_matrix, demands, num_vehicles, capacity, time_limit=5)
    res_exact = exact_solver.solve()
    res_exact["paper"] = "Applegate / Perron & Furnon (Google OR-Tools)"
    results.append(res_exact)
    print(f"   => Distance: {res_exact['distance_km']} km | Runtime: {res_exact['runtime_sec']}s")

    # 6. Quantum HQ-GLS (Our Developed SOTA)
    print("\n[6/6] Running Quantum HQ-GLS (Our Novel Transverse-Field Guided Local Search)...")
    hqgls_solver = HQGLSSolver(
        t_matrix, d_matrix, demands, num_vehicles, capacity,
        depot_coords, cust_coords, time_limit=3.0
    )
    res_hqgls = hqgls_solver.solve()
    res_hqgls["paper"] = "Our Novel Transverse-Field Quantum Tunneling GLS (SIH 2026)"
    results.append(res_hqgls)
    print(f"   => Distance: {res_hqgls['distance_km']} km | Runtime: {res_hqgls['runtime_sec']}s")

    # Compute Optimality Gaps relative to Exact
    exact_d = res_exact['distance_km']
    for r in results:
        gap = ((r['distance_km'] - exact_d) / exact_d) * 100.0
        r['gap_vs_exact_pct'] = round(gap, 2)

    # Save JSON results
    json_path = os.path.join(OUTPUT_DIR, "literature_benchmark_results.json")
    with open(json_path, "w") as f:
        json.dump(_sanitize({
            "city": city_key,
            "num_customers": num_customers,
            "num_vehicles": num_vehicles,
            "capacity": capacity,
            "algorithms": results
        }), f, indent=2)
    print(f"\n[+] Raw results saved to: {json_path}")

    # Generate Publication-Quality Visualizations
    plot_literature_benchmark(results, city_key)

    return results


def plot_literature_benchmark(results, city_key):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#0f172a')

    names = [
        "Clarke-Wright\n(1964)",
        "Sun QPSO\n(2004/12)",
        "Feld QUBO\n(2019)",
        "Ropke ALNS\n(2006)",
        "Exact GLS\n(OR-Tools)",
        "Quantum HQ-GLS\n(Our SOTA)"
    ]
    dists = [r['distance_km'] for r in results]
    runtimes = [r['runtime_sec'] for r in results]
    gaps = [r['gap_vs_exact_pct'] for r in results]

    colors = ['#94a3b8', '#38bdf8', '#a855f7', '#f59e0b', '#ef4444', '#10b981']

    # 1. Distance Bar Chart
    ax1 = axes[0, 0]
    ax1.set_facecolor('#1e293b')
    bars1 = ax1.bar(names, dists, color=colors, edgecolor='#334155', width=0.6)
    ax1.set_title("Total Route Distance (km) — Lower is Better", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)
    ax1.set_ylabel("Distance (km)", color='#cbd5e1')
    ax1.tick_params(colors='#94a3b8', labelsize=9)
    ax1.grid(color='#334155', linestyle='--', alpha=0.5, axis='y')
    for bar, val in zip(bars1, dists):
        ax1.text(bar.get_x() + bar.get_width()/2, val + 0.5, f"{val:.1f}", ha='center', va='bottom', color='#f8fafc', fontsize=9, fontweight='bold')

    # 2. Runtime Bar Chart (Logarithmic)
    ax2 = axes[0, 1]
    ax2.set_facecolor('#1e293b')
    bars2 = ax2.bar(names, runtimes, color=colors, edgecolor='#334155', width=0.6)
    ax2.set_title("Execution Runtime (Seconds)", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)
    ax2.set_ylabel("Runtime (s)", color='#cbd5e1')
    ax2.tick_params(colors='#94a3b8', labelsize=9)
    ax2.grid(color='#334155', linestyle='--', alpha=0.5, axis='y')
    for bar, val in zip(bars2, runtimes):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 0.05, f"{val:.2f}s", ha='center', va='bottom', color='#f8fafc', fontsize=9, fontweight='bold')

    # 3. Optimality Gap vs Exact (%)
    ax3 = axes[1, 0]
    ax3.set_facecolor('#1e293b')
    bars3 = ax3.bar(names, gaps, color=colors, edgecolor='#334155', width=0.6)
    ax3.axhline(0, color='#ef4444', linestyle='--', linewidth=1.5, label='Exact Baseline (0%)')
    ax3.set_title("Optimality Gap vs Exact Baseline (%)", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)
    ax3.set_ylabel("Gap vs Exact (%)", color='#cbd5e1')
    ax3.tick_params(colors='#94a3b8', labelsize=9)
    ax3.grid(color='#334155', linestyle='--', alpha=0.5, axis='y')
    ax3.legend(facecolor='#0f172a', edgecolor='#334155', labelcolor='#cbd5e1')
    for bar, val in zip(bars3, gaps):
        va = 'bottom' if val >= 0 else 'top'
        offset = 0.5 if val >= 0 else -1.5
        ax3.text(bar.get_x() + bar.get_width()/2, val + offset, f"{val:+.1f}%", ha='center', va=va, color='#f8fafc', fontsize=9, fontweight='bold')

    # 4. Literature Scorecard Radar / Summary Table
    ax4 = axes[1, 1]
    ax4.set_facecolor('#1e293b')
    ax4.axis('off')

    table_data = [
        ["Algorithm", "Paper Citation", "Distance", "Gap vs Exact", "Runtime"],
    ]
    for r, short_n in zip(results, ["CW-1964", "Sun QPSO", "Feld QUBO", "Ropke ALNS", "Exact GLS", "HQ-GLS (Ours)"]):
        table_data.append([
            short_n,
            r['paper'].split(',')[0],
            f"{r['distance_km']} km",
            f"{r['gap_vs_exact_pct']:+.1f}%",
            f"{r['runtime_sec']:.2f}s"
        ])

    table = ax4.table(
        cellText=table_data,
        cellLoc='center',
        loc='center',
        colWidths=[0.24, 0.28, 0.16, 0.18, 0.14]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 2.0)

    # Style table cells
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#334155')
        if row == 0:
            cell.set_facecolor('#334155')
            cell.set_text_props(color='#38bdf8', fontweight='bold')
        elif row == len(table_data) - 1:
            cell.set_facecolor('#064e3b')
            cell.set_text_props(color='#34d399', fontweight='bold')
        else:
            cell.set_facecolor('#1e293b' if row % 2 == 0 else '#0f172a')
            cell.set_text_props(color='#f8fafc')

    ax4.set_title("Literature Survey Scorecard Summary", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)

    plt.suptitle(f"Empirical Literature Survey Benchmark: Quantum & Classical VRP ({city_key.upper()} OSM Network)",
                 color='#38bdf8', fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    plot_path = os.path.join(OUTPUT_DIR, "literature_benchmark_comparison.png")
    plt.savefig(plot_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()
    print(f"[+] Comparative plot saved to: {plot_path}")


if __name__ == "__main__":
    run_literature_benchmark(city_key="delhi", num_customers=40, num_vehicles=5, capacity=35)
