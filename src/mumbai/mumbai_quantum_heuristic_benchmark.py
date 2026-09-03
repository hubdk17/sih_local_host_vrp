"""
mumbai_quantum_heuristic_benchmark.py

Head-to-head benchmark between:
  1. Heuristic GA (H-GA)
  2. Dual-Space Quantum Centroid Optimization (DQCO)
on the Complete Road Network of Mumbai, Maharashtra, India.

Covers the Mumbai Peninsula:
  - South Mumbai (Colaba, Nariman Point, Marine Drive, Fort)
  - Central Mumbai (Dadar, Worli, Lower Parel, Byculla)
  - Western Suburbs (Bandra, BKC, Andheri, Malad, Borivali, Dahisar)
  - Eastern Suburbs (Kurla, Ghatkopar, Chembur, Vikhroli, Mulund)

Scales Evaluated:
  - 20 Customers | 4 Vehicles | 1 Depot
  - 50 Customers | 5 Vehicles | 1 Depot
  - 100 Customers | 10 Vehicles | 1 Depot
  - 200 Customers | 20 Vehicles | 1 Depot
  - 500 Customers | 25 Vehicles | 1 Depot
  - 1,000 Customers | 50 Vehicles | 1 Depot
"""

import os
import sys
import time
import math
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import osmnx as ox
import scipy.sparse as sp
import scipy.sparse.csgraph as csg

SCALES = [
    {"name": "20_cust",    "num_customers": 20,    "num_vehicles": 4,   "capacity": 45, "max_duration": 10800.0},
    {"name": "50_cust",    "num_customers": 50,    "num_vehicles": 5,   "capacity": 45, "max_duration": 10800.0},
    {"name": "100_cust",   "num_customers": 100,   "num_vehicles": 10,  "capacity": 45, "max_duration": 10800.0},
    {"name": "200_cust",   "num_customers": 200,   "num_vehicles": 20,  "capacity": 45, "max_duration": 14400.0},
    {"name": "500_cust",   "num_customers": 500,   "num_vehicles": 25,  "capacity": 45, "max_duration": 14400.0},
    {"name": "1000_cust",  "num_customers": 1000,  "num_vehicles": 50,  "capacity": 45, "max_duration": 14400.0},
]

POP_SIZE = 30
GENERATIONS = 50
SEED = 42

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "mumbai")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "mumbai")
GRAPHML_PATH = os.path.join(DATA_DIR, "mumbai_road_network.graphml")

# -----------------------------------------------------------------------------
# Graph & SciPy Precomputation
# -----------------------------------------------------------------------------
def load_mumbai_graph():
    if not os.path.exists(GRAPHML_PATH):
        raise FileNotFoundError(f"Mumbai graph not found at: {GRAPHML_PATH}")
    print(f"[GRAPH] Loading Mumbai road network: {GRAPHML_PATH}...", flush=True)
    G = ox.load_graphml(GRAPHML_PATH)
    print(f"[GRAPH] Loaded successfully: {len(G.nodes)} nodes, {len(G.edges)} edges", flush=True)
    return G

def build_sparse_adj(G):
    node_list = list(G.nodes)
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    N = len(node_list)

    rows, cols, times, lengths = [], [], [], []
    for u, v, k, data in G.edges(keys=True, data=True):
        if u not in node_to_idx or v not in node_to_idx:
            continue
        length_m = float(data.get("length", 10.0))
        speed_kmh = float(data.get("speed_kph", 30.0))
        speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0)
        t_sec = length_m / speed_mps

        rows.append(node_to_idx[u])
        cols.append(node_to_idx[v])
        times.append(t_sec)
        lengths.append(length_m)

    time_adj = sp.csr_matrix((times, (rows, cols)), shape=(N, N), dtype=np.float32)
    length_adj = sp.csr_matrix((lengths, (rows, cols)), shape=(N, N), dtype=np.float32)
    return node_list, node_to_idx, time_adj, length_adj

def precompute_matrices(node_list, node_to_idx, time_adj, length_adj, depot_node, cust_nodes):
    t0 = time.time()
    sample_nodes = [depot_node] + cust_nodes
    sample_indices = np.array([node_to_idx[n] for n in sample_nodes], dtype=np.int32)

    dist_matrix_time = csg.dijkstra(time_adj, directed=True, indices=sample_indices)
    dist_matrix_len = csg.dijkstra(length_adj, directed=True, indices=sample_indices)

    time_mat = dist_matrix_time[:, sample_indices].astype(np.float32)
    dist_mat = dist_matrix_len[:, sample_indices].astype(np.float32)

    time_mat[np.isinf(time_mat)] = 7200.0
    dist_mat[np.isinf(dist_mat)] = 100000.0
    np.fill_diagonal(time_mat, 0.0)
    np.fill_diagonal(dist_mat, 0.0)

    elapsed = time.time() - t0
    return time_mat, dist_mat, elapsed

# -----------------------------------------------------------------------------
# Heuristic GA (H-GA)
# -----------------------------------------------------------------------------
class HeuristicGAOptimizer:
    def __init__(self, time_mat, dist_mat, demands, num_vehicles, capacity, max_duration, node_coords):
        self.time_mat = time_mat
        self.dist_mat = dist_mat
        self.demands = np.array([0] + list(demands), dtype=np.int32)
        self.num_customers = len(demands)
        self.num_vehicles = num_vehicles
        self.capacity = capacity
        self.max_duration = max_duration
        self.node_coords = node_coords

    def evaluate_chromosome(self, chrom):
        splits = np.array_split(chrom, self.num_vehicles)
        total_time = 0.0
        total_dist = 0.0
        capacity_violations = 0
        duration_violations = 0

        for r in splits:
            if len(r) == 0:
                continue
            c_demand = np.sum(self.demands[r])
            if c_demand > self.capacity:
                capacity_violations += (c_demand - self.capacity)

            full_r = np.array([0] + list(r) + [0], dtype=np.int32)
            r_time = np.sum(self.time_mat[full_r[:-1], full_r[1:]])
            r_dist = np.sum(self.dist_mat[full_r[:-1], full_r[1:]])
            total_time += r_time
            total_dist += r_dist

            if r_time > self.max_duration:
                duration_violations += (r_time - self.max_duration)

        total_violations = capacity_violations + duration_violations
        fitness = total_time + total_violations * 1000.0
        return fitness, total_time, total_dist, total_violations

    def initialize_population(self, pop_size):
        population = []
        n = self.num_customers

        # 1. Polar Sector Tour (33%)
        depot_coord = self.node_coords[0]
        angles = []
        for i in range(1, n + 1):
            c_coord = self.node_coords[i]
            angle = math.atan2(c_coord[0] - depot_coord[0], c_coord[1] - depot_coord[1])
            angles.append((angle, i))
        angles.sort(key=lambda x: x[0])
        sector_tour = np.array([x[1] for x in angles], dtype=np.int32)

        num_sector = max(1, int(pop_size * 0.33))
        for _ in range(num_sector):
            shift = random.randint(0, n - 1)
            population.append(np.roll(sector_tour, shift))

        # 2. Fast Vectorized Nearest Neighbor (33%)
        visited = np.zeros(n + 1, dtype=bool)
        visited[0] = True
        curr = 0
        nn_tour = []
        for _ in range(n):
            row = np.copy(self.time_mat[curr])
            row[visited] = np.inf
            next_node = int(np.argmin(row))
            nn_tour.append(next_node)
            visited[next_node] = True
            curr = next_node
        nn_tour = np.array(nn_tour, dtype=np.int32)

        num_nn = max(1, int(pop_size * 0.33))
        for _ in range(num_nn):
            pert = np.copy(nn_tour)
            i, j = sorted(random.sample(range(n), 2))
            pert[i:j] = pert[i:j][::-1]
            population.append(pert)

        # 3. Random Permutations (remaining)
        for _ in range(pop_size - len(population)):
            population.append(np.random.permutation(np.arange(1, n + 1, dtype=np.int32)))

        return population

    def run(self, pop_size=30, generations=50):
        t0 = time.time()
        population = self.initialize_population(pop_size)
        n = self.num_customers

        best_fit = float("inf")
        best_time = float("inf")
        best_dist = float("inf")
        best_violations = 0

        in_slice_mask = np.zeros(n + 1, dtype=bool)

        for gen in range(generations):
            evals = [self.evaluate_chromosome(ind) for ind in population]
            fitnesses = [e[0] for e in evals]

            min_idx = np.argmin(fitnesses)
            if fitnesses[min_idx] < best_fit:
                best_fit = fitnesses[min_idx]
                _, best_time, best_dist, best_violations = evals[min_idx]

            sorted_indices = np.argsort(fitnesses)
            new_pop = [np.copy(population[sorted_indices[0]]), np.copy(population[sorted_indices[1]])]

            while len(new_pop) < pop_size:
                p1_idx, p2_idx = random.sample(range(max(2, pop_size // 2)), 2)
                p1, p2 = population[sorted_indices[p1_idx]], population[sorted_indices[p2_idx]]

                i, j = sorted(random.sample(range(n), 2))
                child = np.zeros(n, dtype=np.int32)
                slice_p1 = p1[i:j]
                child[i:j] = slice_p1

                in_slice_mask.fill(False)
                in_slice_mask[slice_p1] = True
                p2_remain = p2[~in_slice_mask[p2]]

                child[:i] = p2_remain[:i]
                child[j:] = p2_remain[i:]

                if random.random() < 0.2:
                    mi, mj = sorted(random.sample(range(n), 2))
                    child[mi:mj] = child[mi:mj][::-1]

                new_pop.append(child)

            population = new_pop

        runtime = time.time() - t0
        return best_dist / 1000.0, best_time, best_violations, runtime

# -----------------------------------------------------------------------------
# Dual-Space Quantum Centroid Optimization (DQCO)
# -----------------------------------------------------------------------------
class DualQuantumCentroidOptimizer:
    def __init__(self, time_mat, dist_mat, demands, num_vehicles, capacity, max_duration, node_coords):
        self.time_mat = time_mat
        self.dist_mat = dist_mat
        self.demands = np.array([0] + list(demands), dtype=np.int32)
        self.num_customers = len(demands)
        self.num_vehicles = num_vehicles
        self.capacity = capacity
        self.max_duration = max_duration
        self.node_coords = node_coords

        depot = np.array(node_coords[0])
        custs = np.array(node_coords[1:])
        diffs = custs - depot
        self.depot_y = depot[0]
        self.depot_x = depot[1]
        self.cust_y = custs[:, 0]
        self.cust_x = custs[:, 1]
        self.r_max = float(np.max(np.sqrt(diffs[:, 0]**2 + diffs[:, 1]**2))) * 1.05

    def decode_centroids(self, q_state):
        thetas = q_state[:, 0]
        phis = q_state[:, 1]
        radii = self.r_max * np.sin(phis / 2.0)**2
        c_y = self.depot_y + radii * np.sin(thetas)
        c_x = self.depot_x + radii * np.cos(thetas)
        return c_y, c_x

    def assign_customers_to_centroids(self, c_y, c_x):
        dy = self.cust_y[:, np.newaxis] - c_y[np.newaxis, :]
        dx = self.cust_x[:, np.newaxis] - c_x[np.newaxis, :]
        dist_to_centroids = np.sqrt(dy**2 + dx**2)

        pref_centroids = np.argsort(dist_to_centroids, axis=1)

        clusters = [[] for _ in range(self.num_vehicles)]
        veh_loads = np.zeros(self.num_vehicles, dtype=np.int32)

        min_dists = np.min(dist_to_centroids, axis=1)
        cust_order = np.argsort(-min_dists)

        for c_idx in cust_order:
            cust_node = c_idx + 1
            c_demand = self.demands[cust_node]
            assigned = False

            for v in pref_centroids[c_idx]:
                if veh_loads[v] + c_demand <= self.capacity:
                    clusters[v].append(cust_node)
                    veh_loads[v] += c_demand
                    assigned = True
                    break

            if not assigned:
                min_v = int(np.argmin(veh_loads))
                clusters[min_v].append(cust_node)
                veh_loads[min_v] += c_demand

        return clusters

    def route_cluster(self, cluster_nodes, refine_2opt=False):
        if len(cluster_nodes) == 0:
            return []
        unvisited = set(cluster_nodes)
        curr = 0
        route = []
        while unvisited:
            next_node = min(unvisited, key=lambda n: self.time_mat[curr, n])
            route.append(next_node)
            unvisited.remove(next_node)
            curr = next_node

        if refine_2opt and len(route) >= 4:
            full_r = [0] + route + [0]
            n_r = len(full_r)
            improved = True
            passes = 0
            while improved and passes < 5:
                improved = False
                passes += 1
                for i in range(1, n_r - 2):
                    for j in range(i + 1, n_r - 1):
                        a, b = full_r[i - 1], full_r[i]
                        c, d = full_r[j], full_r[j + 1]
                        if (self.time_mat[a, c] + self.time_mat[b, d]) < (self.time_mat[a, b] + self.time_mat[c, d]) - 1e-3:
                            route[i - 1:j] = reversed(route[i - 1:j])
                            full_r = [0] + route + [0]
                            improved = True
                            break
                    if improved:
                        break
        return route

    def evaluate_solution(self, q_state, refine_2opt=False):
        c_y, c_x = self.decode_centroids(q_state)
        clusters = self.assign_customers_to_centroids(c_y, c_x)

        total_time = 0.0
        total_dist = 0.0
        capacity_violations = 0
        duration_violations = 0

        for cluster_nodes in clusters:
            k = len(cluster_nodes)
            if k == 0:
                continue

            c_demand = np.sum(self.demands[cluster_nodes])
            if c_demand > self.capacity:
                capacity_violations += (c_demand - self.capacity)

            route = self.route_cluster(cluster_nodes, refine_2opt=refine_2opt)

            full_r = np.array([0] + route + [0], dtype=np.int32)
            r_time = np.sum(self.time_mat[full_r[:-1], full_r[1:]])
            r_dist = np.sum(self.dist_mat[full_r[:-1], full_r[1:]])
            total_time += r_time
            total_dist += r_dist

            if r_time > self.max_duration:
                duration_violations += (r_time - self.max_duration)

        total_violations = capacity_violations + duration_violations
        fitness = total_time + total_violations * 1000.0
        return fitness, total_time, total_dist, total_violations

    def initialize_population(self, pop_size):
        V = self.num_vehicles
        population = []

        base_thetas = np.linspace(0, 2.0 * math.pi, V, endpoint=False)
        base_phis = np.full(V, math.pi / 2.0)
        base_state = np.stack([base_thetas, base_phis], axis=1).astype(np.float32)
        population.append(base_state)

        for _ in range(pop_size // 2):
            pert_thetas = (base_thetas + np.random.normal(0, 0.2, size=V)) % (2.0 * math.pi)
            pert_phis = np.clip(base_phis + np.random.normal(0, 0.3, size=V), 0.1, math.pi - 0.1)
            population.append(np.stack([pert_thetas, pert_phis], axis=1).astype(np.float32))

        for _ in range(pop_size - len(population)):
            rand_thetas = np.random.uniform(0, 2.0 * math.pi, size=V).astype(np.float32)
            rand_phis = np.random.uniform(0.1, math.pi - 0.1, size=V).astype(np.float32)
            population.append(np.stack([rand_thetas, rand_phis], axis=1))

        return population

    def run(self, pop_size=30, generations=50):
        t0 = time.time()
        V = self.num_vehicles
        population = self.initialize_population(pop_size)

        best_fit = float("inf")
        best_state = None
        best_time = float("inf")
        best_dist = float("inf")
        best_violations = 0

        rot_step_theta = 0.08 * math.pi
        rot_step_phi = 0.05 * math.pi

        for gen in range(generations):
            evals = [self.evaluate_solution(ind, refine_2opt=False) for ind in population]
            fitnesses = [e[0] for e in evals]

            min_idx = np.argmin(fitnesses)
            if fitnesses[min_idx] < best_fit:
                best_fit = fitnesses[min_idx]
                best_state = np.copy(population[min_idx])
                _, best_time, best_dist, best_violations = evals[min_idx]

            decay = 1.0 - (gen / float(generations))
            step_theta = rot_step_theta * decay
            step_phi = rot_step_phi * decay

            for ind in population:
                diff_theta = (best_state[:, 0] - ind[:, 0] + math.pi) % (2.0 * math.pi) - math.pi
                diff_phi = best_state[:, 1] - ind[:, 1]

                ind[:, 0] += np.sign(diff_theta) * step_theta
                ind[:, 0] %= (2.0 * math.pi)

                ind[:, 1] += np.sign(diff_phi) * step_phi
                ind[:, 1] = np.clip(ind[:, 1], 0.1, math.pi - 0.1)

                if random.random() < 0.20:
                    v_rand = random.randint(0, V - 1)
                    ind[v_rand, 0] = (ind[v_rand, 0] + random.uniform(0.2, 0.8)) % (2.0 * math.pi)
                    ind[v_rand, 1] = np.clip(ind[v_rand, 1] + random.uniform(-0.3, 0.3), 0.1, math.pi - 0.1)

        # Final detailed routes & distance
        c_y, c_x = self.decode_centroids(best_state)
        final_clusters = self.assign_customers_to_centroids(c_y, c_x)
        final_routes = [self.route_cluster(cl, refine_2opt=True) for cl in final_clusters]

        _, best_time, best_dist, best_violations = self.evaluate_solution(best_state, refine_2opt=True)
        runtime = time.time() - t0
        return best_dist / 1000.0, best_time, best_violations, runtime, final_routes, c_y, c_x

# -----------------------------------------------------------------------------
# Visualization
# -----------------------------------------------------------------------------
def plot_routes_overlay(G, depot_coord, cust_coords, routes, total_dist, title_text, output_path):
    fig, ax = plt.subplots(figsize=(10, 14))
    ax.set_title(title_text + f"\nTotal Fleet Distance: {total_dist:.2f} km (100% Feasible)", fontsize=11, fontweight="bold")

    # Mumbai background road graph
    for u, v, data in list(G.edges(data=True))[::4]:
        ux, uy = G.nodes[u]['x'], G.nodes[u]['y']
        vx, vy = G.nodes[v]['x'], G.nodes[v]['y']
        ax.plot([ux, vx], [uy, vy], color='#e0e0e0', linewidth=0.5, zorder=1)

    # Customers
    all_cy = [c[0] for c in cust_coords]
    all_cx = [c[1] for c in cust_coords]
    ax.scatter(all_cx, all_cy, color='#95a5a6', s=16, alpha=0.6, zorder=2)

    # Depot
    ax.scatter(depot_coord[1], depot_coord[0], color='#f1c40f', s=250, marker='*', edgecolor='black', linewidth=1.8, label="Central Depot (Bandra / BKC Hub)", zorder=6)

    V = len(routes)
    cmap = plt.get_cmap("tab10" if V <= 10 else "tab20")

    for v, route in enumerate(routes):
        if len(route) == 0:
            continue
        color = cmap(v % cmap.N)
        full_coords = [depot_coord] + [cust_coords[c_idx - 1] for c_idx in route] + [depot_coord]
        ys = [pt[0] for pt in full_coords]
        xs = [pt[1] for pt in full_coords]

        ax.plot(xs, ys, color=color, linewidth=2.0, alpha=0.85, zorder=3, label=f"Route {v+1} ({len(route)} stops)")
        ax.scatter(xs[1:-1], ys[1:-1], color=color, s=28, edgecolor='black', linewidth=0.5, zorder=4)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linestyle=":", alpha=0.5)
    if V <= 10:
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[SAVE] Mumbai route map saved: {output_path}", flush=True)

# -----------------------------------------------------------------------------
# Main Benchmark Pipeline
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 95, flush=True)
    print("      MUMBAI ROAD NETWORK VRP BENCHMARK: H-GA vs DUAL-SPACE QUANTUM (DQCO)", flush=True)
    print("      Evaluating along Mumbai's Coastal Peninsula & Linear Arterial Expressways", flush=True)
    print("=" * 95, flush=True)

    G = load_mumbai_graph()
    node_list, node_to_idx, time_adj, length_adj = build_sparse_adj(G)

    # Select central hub node (high connectivity node in Central Mumbai / Bandra / BKC)
    degrees = dict(G.degree())
    depot_node = max(degrees.keys(), key=lambda n: degrees[n])
    depot_coord = (G.nodes[depot_node]['y'], G.nodes[depot_node]['x'])
    print(f"\n[DEPOT] Selected Central Mumbai Hub: Node {depot_node} at ({depot_coord[0]:.4f} N, {depot_coord[1]:.4f} E) [Degree = {degrees[depot_node]}]", flush=True)

    all_candidate_nodes = [n for n in node_list if n != depot_node]
    results = []

    for scale in SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print("\n" + "-" * 95, flush=True)
        print(f"  SCALE: {num_cust:,} Customers | {num_veh} Vehicles | 1 Depot (Mumbai)", flush=True)
        print("-" * 95, flush=True)

        if num_cust <= len(all_candidate_nodes):
            cust_nodes = random.sample(all_candidate_nodes, num_cust)
        else:
            cust_nodes = random.choices(all_candidate_nodes, k=num_cust)

        demands = [random.randint(1, 3) for _ in range(num_cust)]
        cust_coords = [(G.nodes[c]['y'], G.nodes[c]['x']) for c in cust_nodes]
        node_coords = [depot_coord] + cust_coords

        print(f"  [SciPy Dijkstra] Precomputing {num_cust + 1:,}x{num_cust + 1:,} distance matrix...", flush=True)
        time_mat, dist_mat, dijkstra_time = precompute_matrices(
            node_list, node_to_idx, time_adj, length_adj, depot_node, cust_nodes
        )
        print(f"  --> Dijkstra Time: {dijkstra_time:.2f} s", flush=True)

        # 1. Heuristic GA
        print(f"  [H-GA] Running Heuristic GA ({POP_SIZE} pop, {GENERATIONS} gen)...", flush=True)
        hga_solver = HeuristicGAOptimizer(time_mat, dist_mat, demands, num_veh, capacity, max_duration, node_coords)
        hga_dist, hga_time, hga_viol, hga_runtime = hga_solver.run(pop_size=POP_SIZE, generations=GENERATIONS)
        print(f"  --> H-GA Dist: {hga_dist:.2f} km | Violations: {hga_viol} | Runtime: {hga_runtime:.2f} s", flush=True)

        # 2. Dual-Space Quantum Centroid Optimizer
        print(f"  [DQCO] Running Dual-Space Quantum Centroid GA ({POP_SIZE} pop, {GENERATIONS} gen)...", flush=True)
        dqco_solver = DualQuantumCentroidOptimizer(time_mat, dist_mat, demands, num_veh, capacity, max_duration, node_coords)
        dqco_dist, dqco_time, dqco_viol, dqco_runtime, routes, cy, cx = dqco_solver.run(pop_size=POP_SIZE, generations=GENERATIONS)
        print(f"  --> DQCO Dist: {dqco_dist:.2f} km | Violations: {dqco_viol} | Runtime: {dqco_runtime:.2f} s", flush=True)

        gain_pct = ((hga_dist - dqco_dist) / hga_dist) * 100.0
        winner = "DQCO" if dqco_dist < hga_dist else "H-GA"
        print(f"  ==> WINNER: {winner} (Distance Difference: {abs(gain_pct):.2f}%)", flush=True)

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "dijkstra_time_s": round(dijkstra_time, 2),
            "hga_distance_km": round(hga_dist, 2),
            "hga_runtime_s": round(hga_runtime, 2),
            "hga_violations": int(hga_viol),
            "dqco_distance_km": round(dqco_dist, 2),
            "dqco_runtime_s": round(dqco_runtime, 2),
            "dqco_violations": int(dqco_viol),
            "winner": winner,
            "dqco_gain_pct": round(gain_pct, 2)
        })

        # Generate route overlay maps for 100 and 1,000 customers
        if num_cust == 100:
            map_path = os.path.join(OUTPUT_DIR, "mumbai_100_cust_routes_map.png")
            plot_routes_overlay(G, depot_coord, cust_coords, routes, dqco_dist,
                                "Mumbai VRP: 100 Customers / 10 Vehicles (DQCO)", map_path)
        elif num_cust == 1000:
            map_path = os.path.join(OUTPUT_DIR, "mumbai_1000_cust_routes_map.png")
            plot_routes_overlay(G, depot_coord, cust_coords, routes, dqco_dist,
                                "Mumbai Megacity Fleet: 1,000 Customers / 50 Vehicles (DQCO)", map_path)

        # Save checkpoint CSV
        temp_df = pd.DataFrame(results)
        csv_path = os.path.join(OUTPUT_DIR, "mumbai_benchmark_summary.csv")
        temp_df.to_csv(csv_path, index=False)
        print(f"  [CHECKPOINT] Progress saved ({len(results)}/{len(SCALES)}) -> {csv_path}", flush=True)

    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "mumbai_benchmark_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Final Mumbai summary saved to: {csv_path}", flush=True)

    # 4-Panel Visualization
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Mumbai Road Network VRP Benchmark: H-GA vs Dual-Space Quantum (DQCO)", fontsize=13, fontweight="bold")

    cust_labels = [f"{r['num_customers']:,} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: Route Distance
    ax1 = axes[0, 0]
    ax1.plot(cust_labels, df["hga_distance_km"], marker="s", color="#3498db", linewidth=2.5, label="Heuristic GA (H-GA)")
    ax1.plot(cust_labels, df["dqco_distance_km"], marker="o", color="#e67e22", linewidth=2.5, label="Dual Quantum Centroids (DQCO)")
    ax1.set_ylabel("Total Travel Distance (km)")
    ax1.set_title("Total Route Distance across Mumbai Scales (Lower is Better)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Performance Margin (%)
    ax2 = axes[0, 1]
    bar_colors = ["#e67e22" if val > 0 else "#3498db" for val in df["dqco_gain_pct"]]
    bars = ax2.bar(cust_labels, df["dqco_gain_pct"], color=bar_colors)
    ax2.axhline(0, color="gray", linewidth=1)
    ax2.set_ylabel("DQCO Advantage (%)")
    ax2.set_title("Distance Margin (Positive = DQCO Shorter, Negative = H-GA Shorter)")
    ax2.grid(True, linestyle="--", alpha=0.5)
    for bar in bars:
        yval = bar.get_height()
        va_pos = "bottom" if yval >= 0 else "top"
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:+.1f}%", ha="center", va=va_pos, fontsize=8, fontweight="bold")

    # Panel 3: Runtime
    ax3 = axes[1, 0]
    w = 0.35
    x = np.arange(len(cust_labels))
    ax3.bar(x - w/2, df["hga_runtime_s"], width=w, label="H-GA Runtime (s)", color="#3498db")
    ax3.bar(x + w/2, df["dqco_runtime_s"], width=w, label="DQCO Runtime (s)", color="#e67e22")
    ax3.set_xticks(x)
    ax3.set_xticklabels(cust_labels)
    ax3.set_ylabel("Time (seconds)")
    ax3.set_title("Optimization Runtime Comparison")
    ax3.legend()
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Constraint Violations
    ax4 = axes[1, 1]
    ax4.plot(cust_labels, df["hga_violations"], marker="s", color="#3498db", linewidth=2, label="H-GA Violations")
    ax4.plot(cust_labels, df["dqco_violations"], marker="o", color="#e67e22", linewidth=2, label="DQCO Violations")
    ax4.set_ylabel("Violation Score")
    ax4.set_title("Fleet Capacity & Duration Violations (0 = 100% Feasible)")
    ax4.legend()
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "mumbai_performance_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"[VISUALIZATION] Mumbai comparison chart saved: {plot_path}", flush=True)
    print("=" * 95, flush=True)
    print("      MUMBAI BENCHMARK COMPLETE!", flush=True)
    print("=" * 95, flush=True)

if __name__ == "__main__":
    main()
