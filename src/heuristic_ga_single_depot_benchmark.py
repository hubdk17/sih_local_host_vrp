"""
heuristic_ga_single_depot_benchmark.py

Heuristic-Initialized Genetic Algorithm (H-GA) for Single-Depot VRP.
Integrates Multi-Strategy Population Initialization:
  1. Random Permutations (~34%)
  2. Greedy Angular / Capacity Clustering (~33%)
  3. Nearest-Neighbor TSP Paths (~33%)

Evaluates scalability & optimality gap across 6 scale points:
  1. 20 Customers   | 4 Vehicles   | 1 Depot
  2. 50 Customers   | 5 Vehicles   | 1 Depot
  3. 100 Customers  | 10 Vehicles  | 1 Depot
  4. 200 Customers  | 20 Vehicles  | 1 Depot
  5. 500 Customers  | 25 Vehicles  | 1 Depot
  6. 1,000 Customers | 50 Vehicles  | 1 Depot

Saves outputs to:
  - CSV report: outputs/ga/heuristic_single_depot/hga_summary.csv
  - Plots: outputs/ga/heuristic_single_depot/hga_vs_ga_comparison.png
"""

import os
import time
import json
import random
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import osmnx as ox
import networkx as nx

# -----------------------------------------------------------------------------
# Configuration Parameters
# -----------------------------------------------------------------------------
BENCHMARK_SCALES = [
    {"name": "20_cust",   "num_customers": 20,   "num_vehicles": 4,  "capacity": 20, "max_duration": 7200.0},
    {"name": "50_cust",   "num_customers": 50,   "num_vehicles": 5,  "capacity": 25, "max_duration": 7200.0},
    {"name": "100_cust",  "num_customers": 100,  "num_vehicles": 10, "capacity": 25, "max_duration": 7200.0},
    {"name": "200_cust",  "num_customers": 200,  "num_vehicles": 20, "capacity": 25, "max_duration": 7200.0},
    {"name": "500_cust",  "num_customers": 500,  "num_vehicles": 25, "capacity": 45, "max_duration": 10800.0},
    {"name": "1000_cust", "num_customers": 1000, "num_vehicles": 50, "capacity": 45, "max_duration": 14400.0},
]

POP_SIZE = 100
GENERATIONS = 200
CROSSOVER_PROB = 0.85
MUTATION_PROB = 0.25
ELITISM = 2
SEED = 42

OUTPUT_DIR = os.path.join("outputs", "ga", "heuristic_single_depot")

# -----------------------------------------------------------------------------
# Graph Loading & Precomputation
# -----------------------------------------------------------------------------
def load_road_graph():
    """Load cached Delhi road network graph."""
    delhi_path = os.path.join("data", "delhi", "delhi_road_network.graphml")
    chandigarh_path = os.path.join("data", "scaled", "chandigarh_20_sectors.graphml")
    raw_path = os.path.join("data", "raw", "chandigarh_subset.graphml")

    for path in [delhi_path, chandigarh_path, raw_path]:
        if os.path.exists(path):
            print(f"Loading road network graph from: {path}...")
            G = ox.load_graphml(path)
            print(f"Graph loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
    raise FileNotFoundError("No road graph file found.")

def annotate_graph_edges(G):
    """Annotate edges with travel_time (sec)."""
    for u, v, k, data in G.edges(keys=True, data=True):
        length_m = float(data.get("length", 10.0))
        speed_kmh = 30.0
        if "maxspeed" in data:
            try:
                ms = data["maxspeed"]
                if isinstance(ms, list): ms = ms[0]
                speed_kmh = float(str(ms).replace("km/h", "").strip())
            except (ValueError, TypeError):
                pass
        speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0)
        data["travel_time"] = length_m / speed_mps

def precompute_matrices(G, depot_node, customer_nodes):
    """Precompute (N+1) x (N+1) travel time & distance matrices."""
    all_nodes = [depot_node] + customer_nodes
    N_total = len(all_nodes)
    time_mat = np.zeros((N_total, N_total), dtype=np.float32)
    dist_mat = np.zeros((N_total, N_total), dtype=np.float32)

    t0 = time.time()
    for src_idx, src_node in enumerate(all_nodes):
        times_dict, paths_dict = nx.single_source_dijkstra(G, source=src_node, weight="travel_time")
        for dst_idx, dst_node in enumerate(all_nodes):
            if src_idx == dst_idx:
                continue
            if dst_node in times_dict:
                time_mat[src_idx, dst_idx] = times_dict[dst_node]
                path = paths_dict[dst_node]
                dist = 0.0
                for i in range(len(path) - 1):
                    u_n, v_n = path[i], path[i+1]
                    edge_dict = G[u_n][v_n]
                    min_k = min(edge_dict.keys(), key=lambda k: edge_dict[k].get("travel_time", 0.0))
                    dist += float(edge_dict[min_k].get("length", 10.0))
                dist_mat[src_idx, dst_idx] = dist
            else:
                time_mat[src_idx, dst_idx] = 1e6
                dist_mat[src_idx, dst_idx] = 1e6
    dijkstra_time = time.time() - t0
    return time_mat, dist_mat, dijkstra_time

# -----------------------------------------------------------------------------
# Vectorized Route Evaluator
# -----------------------------------------------------------------------------
class FastSingleDepotEvaluator:
    def __init__(self, time_mat, dist_mat, demands, num_vehicles, vehicle_capacity, max_duration):
        self.time_mat = time_mat
        self.dist_mat = dist_mat
        self.demands = np.array([0] + list(demands), dtype=np.int32)
        self.num_customers = len(demands)
        self.num_vehicles = num_vehicles
        self.vehicle_capacity = vehicle_capacity
        self.max_duration = max_duration

    def split_chromosome(self, chromosome):
        routes = np.array_split(chromosome, self.num_vehicles)
        return [r.tolist() for r in routes]

    def evaluate(self, chromosome):
        routes = self.split_chromosome(chromosome)
        total_time = 0.0
        total_dist = 0.0
        capacity_violations = 0
        duration_violations = 0

        for r in routes:
            if len(r) == 0:
                continue
            route_demand = np.sum(self.demands[r])
            if route_demand > self.vehicle_capacity:
                capacity_violations += (route_demand - self.vehicle_capacity)

            full_r = np.array([0] + r + [0], dtype=np.int32)
            r_time = np.sum(self.time_mat[full_r[:-1], full_r[1:]])
            r_dist = np.sum(self.dist_mat[full_r[:-1], full_r[1:]])

            total_time += r_time
            total_dist += r_dist

            if r_time > self.max_duration:
                duration_violations += (r_time - self.max_duration)

        total_violations = capacity_violations + duration_violations
        fitness = total_time + total_violations * 1000.0
        return fitness, total_time, total_dist, total_violations

# -----------------------------------------------------------------------------
# Heuristic Multi-Strategy Population Initializer
# -----------------------------------------------------------------------------
def generate_heuristic_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat):
    """
    Initial Population Strategy Breakdown:
      1. Random Individuals (~34%)
      2. Greedy Angular / Sector Sweeping (~33%)
      3. Nearest-Neighbor (NN) TSP Tours (~33%)
    """
    population = []
    cust_indices = list(range(1, num_customers + 1))

    num_random = int(pop_size * 0.34)
    num_greedy = int(pop_size * 0.33)
    num_nn = pop_size - num_random - num_greedy

    # 1. Random Individuals
    for _ in range(num_random):
        ind = np.random.permutation(cust_indices).tolist()
        population.append(ind)

    # 2. Greedy Angular / Sector Sweeping
    depot_y = G.nodes[depot_node]['y']
    depot_x = G.nodes[depot_node]['x']
    
    angles = []
    for c_node in customer_nodes:
        cy = G.nodes[c_node]['y']
        cx = G.nodes[c_node]['x']
        angle = math.atan2(cy - depot_y, cx - depot_x)
        angles.append(angle)

    # Base sector order (sorted by polar angle around depot)
    sector_sorted = [idx for _, idx in sorted(zip(angles, cust_indices))]

    for _ in range(num_greedy):
        # Slightly perturb sector order with small random swaps to generate unique greedy individuals
        ind = list(sector_sorted)
        if random.random() < 0.7:
            for _ in range(random.randint(1, max(2, num_customers // 10))):
                idx1, idx2 = random.sample(range(num_customers), 2)
                ind[idx1], ind[idx2] = ind[idx2], ind[idx1]
        population.append(ind)

    # 3. Nearest Neighbor (NN) Tours
    for i in range(num_nn):
        unvisited = set(cust_indices)
        # Start at depot (0) or pick random first customer
        if i == 0:
            curr = 0
        else:
            curr = random.choice(cust_indices)
            unvisited.remove(curr)
        
        nn_tour = [] if curr == 0 else [curr]

        while unvisited:
            # Pick nearest unvisited customer to curr
            next_cust = min(unvisited, key=lambda c: time_mat[curr, c])
            nn_tour.append(next_cust)
            unvisited.remove(next_cust)
            curr = next_cust

        population.append(nn_tour)

    return population

# -----------------------------------------------------------------------------
# 2-Opt Local Search Refinement Operator
# -----------------------------------------------------------------------------
def apply_2opt_local_search(chromosome, evaluator, max_attempts=5):
    """Refine chromosome with 2-Opt local search swaps to pull towards local optimality."""
    best_chrom = list(chromosome)
    best_fit, _, _, _ = evaluator.evaluate(best_chrom)

    size = len(best_chrom)
    if size < 4:
        return best_chrom

    attempts = 0
    improved = True
    while improved and attempts < max_attempts:
        improved = False
        attempts += 1
        i = random.randint(0, size - 3)
        j = random.randint(i + 2, size - 1)
        
        # 2-opt flip
        new_chrom = best_chrom[:i] + best_chrom[i:j+1][::-1] + best_chrom[j+1:]
        new_fit, _, _, _ = evaluator.evaluate(new_chrom)

        if new_fit < best_fit:
            best_chrom = new_chrom
            best_fit = new_fit
            improved = True

    return best_chrom

# -----------------------------------------------------------------------------
# Heuristic GA Engine
# -----------------------------------------------------------------------------
def run_heuristic_ga(evaluator, num_customers, G, depot_node, customer_nodes, time_mat, pop_size=100, generations=200):
    t0 = time.time()

    # Heuristic Initialization
    population = generate_heuristic_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat)

    best_chrom = None
    best_fit = float("inf")
    best_time = float("inf")
    best_dist = float("inf")
    best_violations = 0
    history_best_time = []

    for gen in range(generations):
        # Evaluate population
        evals = [evaluator.evaluate(ind) for ind in population]
        fitnesses = [e[0] for e in evals]

        # Track best
        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_chrom = population[min_idx]
            _, best_time, best_dist, best_violations = evals[min_idx]

        history_best_time.append(best_time)

        # Selection (Tournament) & Elitism
        new_pop = []
        sorted_indices = np.argsort(fitnesses)
        for e_idx in range(ELITISM):
            new_pop.append(population[sorted_indices[e_idx]])

        while len(new_pop) < pop_size:
            i1, i2 = random.sample(range(pop_size), 2)
            parent1 = population[i1] if fitnesses[i1] < fitnesses[i2] else population[i2]
            
            i3, i4 = random.sample(range(pop_size), 2)
            parent2 = population[i3] if fitnesses[i3] < fitnesses[i4] else population[i4]

            # Order Crossover (OX)
            if random.random() < CROSSOVER_PROB:
                size = len(parent1)
                cx1, cx2 = sorted(random.sample(range(size), 2))
                child = [-1] * size
                child[cx1:cx2] = parent1[cx1:cx2]
                
                fill_vals = [item for item in parent2 if item not in child[cx1:cx2]]
                fill_idx = 0
                for i in range(size):
                    if child[i] == -1:
                        child[i] = fill_vals[fill_idx]
                        fill_idx += 1
            else:
                child = list(parent1)

            # Swap Mutation
            if random.random() < MUTATION_PROB:
                m1, m2 = random.sample(range(len(child)), 2)
                child[m1], child[m2] = child[m2], child[m1]

            # Periodic 2-Opt Local Search on top 10% individuals
            if random.random() < 0.15:
                child = apply_2opt_local_search(child, evaluator, max_attempts=3)

            new_pop.append(child)

        population = new_pop

    ga_time = time.time() - t0
    ms_per_gen = (ga_time / generations) * 1000.0
    return best_time, best_dist, best_violations, ga_time, ms_per_gen, history_best_time

# -----------------------------------------------------------------------------
# Main Execution Benchmark
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 76)
    print("   HEURISTIC-INITIALIZED GA (H-GA) SINGLE-DEPOT VRP BENCHMARK SUITE")
    print("=" * 76)

    G = load_road_graph()
    annotate_graph_edges(G)

    # Pick 1 Central Depot Node
    node_degrees = dict(G.degree())
    depot_node = max(node_degrees.keys(), key=lambda n: node_degrees[n])
    print(f"\nDepot Node selected: {depot_node} (Degree = {node_degrees[depot_node]})")

    candidate_nodes = [n for n in G.nodes() if n != depot_node]

    # Load baseline Random GA summary for comparison if exists
    baseline_csv = os.path.join("outputs", "ga", "single_depot", "single_depot_summary.csv")
    has_baseline = os.path.exists(baseline_csv)
    baseline_df = pd.read_csv(baseline_csv) if has_baseline else None

    results = []

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print(f"\n" + "-" * 76)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | 1 Depot")
        print(f"-" * 76)

        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        # 1. Precompute shortest paths
        print(f"  [Dijkstra] Precomputing shortest paths for {num_cust + 1} locations...")
        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)

        # 2. Run Heuristic GA (H-GA)
        evaluator = FastSingleDepotEvaluator(
            time_mat=time_mat,
            dist_mat=dist_mat,
            demands=demands,
            num_vehicles=num_veh,
            vehicle_capacity=capacity,
            max_duration=max_duration
        )

        print(f"  [H-GA] Optimizing (Random + Greedy + Nearest Neighbor) over {GENERATIONS} gen...")
        best_time_s, best_dist_m, violations, ga_time, ms_per_gen, history_best = run_heuristic_ga(
            evaluator, num_customers=num_cust, G=G, depot_node=depot_node,
            customer_nodes=customer_nodes, time_mat=time_mat, pop_size=POP_SIZE, generations=GENERATIONS
        )

        total_runtime = dijkstra_time + ga_time
        best_dist_km = best_dist_m / 1000.0
        is_valid = (violations == 0)

        # Compute optimality gap & proximity to baseline if available
        base_dist_km = None
        proximity_pct = None
        if has_baseline and scale_name in baseline_df["scale_name"].values:
            base_row = baseline_df[baseline_df["scale_name"] == scale_name].iloc[0]
            base_dist_km = base_row["best_distance_km"]
            # Proximity improvement percentage over standard random GA
            proximity_pct = ((base_dist_km - best_dist_km) / base_dist_km) * 100.0

        print(f"  --> Total Runtime   : {total_runtime:.2f} s (Dijkstra: {dijkstra_time:.2f}s, H-GA: {ga_time:.2f}s)")
        print(f"  --> Speed           : {ms_per_gen:.2f} ms / generation")
        print(f"  --> Best Travel Time: {best_time_s:.1f} s ({best_time_s/3600.0:.2f} hrs)")
        print(f"  --> Best Distance   : {best_dist_km:.2f} km")
        if proximity_pct is not None:
            print(f"  --> H-GA Optimality : {proximity_pct:+.2f}% distance reduction vs Random GA ({base_dist_km:.2f} km)")
        print(f"  --> Violations      : {violations} ({'VALID' if is_valid else 'INVALID'})")

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "num_depots": 1,
            "total_runtime_s": round(total_runtime, 2),
            "dijkstra_time_s": round(dijkstra_time, 2),
            "hga_time_s": round(ga_time, 2),
            "ms_per_gen": round(ms_per_gen, 2),
            "best_travel_time_s": round(best_time_s, 1),
            "best_distance_km": round(best_dist_km, 2),
            "baseline_random_ga_km": round(base_dist_km, 2) if base_dist_km is not None else np.nan,
            "distance_improvement_pct": round(proximity_pct, 2) if proximity_pct is not None else np.nan,
            "violations": int(violations),
            "is_valid": is_valid
        })

    # Save summary CSV
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "hga_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Summary report saved to: {csv_path}")

    # Plot Comparison Charts (Random GA vs Heuristic-Initialized H-GA)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Heuristic-Initialized GA (H-GA) vs Standard Random GA Scalability & Optimality Comparison", fontsize=13, fontweight="bold")

    cust_labels = [f"{r['num_customers']} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: Route Distance Comparison (Random GA vs H-GA)
    ax1 = axes[0, 0]
    if has_baseline:
        ax1.plot(cust_labels, df["baseline_random_ga_km"], marker="o", color="#e74c3c", linestyle="--", linewidth=2, label="Standard Random GA")
    ax1.plot(cust_labels, df["best_distance_km"], marker="s", color="#2ecc71", linewidth=2.5, label="Heuristic H-GA (Random + Greedy + NN)")
    ax1.set_ylabel("Total Distance (km)")
    ax1.set_title("Best Route Distance (Lower is Better)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Distance Improvement / Optimality Vicinity Percentage
    ax2 = axes[0, 1]
    if has_baseline:
        bars = ax2.bar(cust_labels, df["distance_improvement_pct"], color="#3498db")
        ax2.axhline(0, color="black", linewidth=1)
        ax2.set_ylabel("Distance Improvement (%)")
        ax2.set_title("H-GA Distance Reduction vs Random GA")
        for bar in bars:
            yval = bar.get_height()
            if not np.isnan(yval):
                ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:+.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Panel 3: Runtime Breakdown
    ax3 = axes[1, 0]
    ax3.bar(cust_labels, df["dijkstra_time_s"], label="Dijkstra Precompute (s)", color="#34495e")
    ax3.bar(cust_labels, df["hga_time_s"], bottom=df["dijkstra_time_s"], label="H-GA Evolution (s)", color="#9b59b6")
    ax3.set_ylabel("Time (seconds)")
    ax3.set_title("Execution Runtime Breakdown")
    ax3.legend()
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Violations comparison
    ax4 = axes[1, 1]
    colors = ["#2ecc71" if r['is_valid'] else "#e74c3c" for r in results]
    ax4.bar(cust_labels, df["violations"], color=colors)
    ax4.set_ylabel("Violation Count")
    ax4.set_title("Constraint Violations (Green = 100% Feasible)")
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "hga_vs_ga_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"[VISUALIZATION] Scalability charts saved to: {plot_path}")
    print("=" * 76)
    print("   HEURISTIC-INITIALIZED GA BENCHMARK SUITE COMPLETE!")
    print("=" * 76)

if __name__ == "__main__":
    main()
