"""
single_depot_benchmark.py

Scalability Benchmark Suite for Single-Depot VRP using Genetic Algorithm (GA).
Evaluates performance across 6 scale points:
  1. 20 Customers   | 4 Vehicles   | 1 Depot
  2. 50 Customers   | 5 Vehicles   | 1 Depot
  3. 100 Customers  | 10 Vehicles  | 1 Depot
  4. 200 Customers  | 20 Vehicles  | 1 Depot
  5. 500 Customers  | 25 Vehicles  | 1 Depot
  6. 1,000 Customers | 50 Vehicles  | 1 Depot

Saves results to:
  - CSV report: outputs/ga/single_depot/single_depot_summary.csv
  - Visualizations: outputs/ga/single_depot/single_depot_comparison.png
"""

import os
import time
import json
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import osmnx as ox
import networkx as nx

# -----------------------------------------------------------------------------
# Configuration & Benchmark Parameters
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

OUTPUT_DIR = os.path.join("outputs", "ga", "single_depot")

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def load_road_graph():
    """Load cached Delhi graph or fallback to Chandigarh graph."""
    delhi_path = os.path.join("data", "delhi", "delhi_road_network.graphml")
    chandigarh_path = os.path.join("data", "scaled", "chandigarh_20_sectors.graphml")
    raw_path = os.path.join("data", "raw", "chandigarh_subset.graphml")

    for path in [delhi_path, chandigarh_path, raw_path]:
        if os.path.exists(path):
            print(f"Loading road network graph from: {path}...")
            G = ox.load_graphml(path)
            print(f"Graph loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
    raise FileNotFoundError("No road graph file found in data directory.")

def annotate_graph_edges(G):
    """Annotate graph edges with travel_time in seconds."""
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
    """
    Precompute (N+1) x (N+1) travel time & distance matrices using Dijkstra.
    Index 0: Depot
    Indices 1..N: Customers
    """
    all_nodes = [depot_node] + customer_nodes
    N_total = len(all_nodes)
    time_mat = np.zeros((N_total, N_total), dtype=np.float32)
    dist_mat = np.zeros((N_total, N_total), dtype=np.float32)

    # Dictionary mapping graph_node -> matrix_idx
    node_to_idx = {node: idx for idx, node in enumerate(all_nodes)}

    t0 = time.time()
    for src_idx, src_node in enumerate(all_nodes):
        times_dict, paths_dict = nx.single_source_dijkstra(G, source=src_node, weight="travel_time")
        for dst_idx, dst_node in enumerate(all_nodes):
            if src_idx == dst_idx:
                continue
            if dst_node in times_dict:
                time_mat[src_idx, dst_idx] = times_dict[dst_node]
                # Approximate distance from node path
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
# Fast Single-Depot Vectorized Route Evaluator
# -----------------------------------------------------------------------------
class FastSingleDepotEvaluator:
    def __init__(self, time_mat, dist_mat, demands, num_vehicles, vehicle_capacity, max_duration):
        self.time_mat = time_mat
        self.dist_mat = dist_mat
        self.demands = np.array([0] + list(demands), dtype=np.int32)  # 0 for depot
        self.num_customers = len(demands)
        self.num_vehicles = num_vehicles
        self.vehicle_capacity = vehicle_capacity
        self.max_duration = max_duration

    def split_chromosome(self, chromosome):
        """Split customer permutation evenly across vehicles."""
        routes = np.array_split(chromosome, self.num_vehicles)
        return [r.tolist() for r in routes]

    def evaluate(self, chromosome):
        """Vectorized evaluation of total travel time, total distance, and constraint violations."""
        routes = self.split_chromosome(chromosome)
        total_time = 0.0
        total_dist = 0.0
        capacity_violations = 0
        duration_violations = 0

        for r in routes:
            if len(r) == 0:
                continue
            
            # Check capacity
            route_demand = np.sum(self.demands[r])
            if route_demand > self.vehicle_capacity:
                capacity_violations += (route_demand - self.vehicle_capacity)

            # Check time & distance: 0 -> r[0] -> r[1] -> ... -> r[-1] -> 0
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
# GA Engine for Single-Depot VRP
# -----------------------------------------------------------------------------
def run_single_depot_ga(evaluator, num_customers, pop_size=100, generations=200):
    t0 = time.time()

    # Initial population: random permutations of customer indices [1 .. N]
    population = [np.random.permutation(np.arange(1, num_customers + 1)).tolist() for _ in range(pop_size)]

    best_chrom = None
    best_fit = float("inf")
    best_time = float("inf")
    best_dist = float("inf")
    best_violations = 0

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

        # Selection (Tournament)
        new_pop = []
        # Elitism
        sorted_indices = np.argsort(fitnesses)
        for e_idx in range(ELITISM):
            new_pop.append(population[sorted_indices[e_idx]])

        while len(new_pop) < pop_size:
            # Tournament selection (k=3)
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

            new_pop.append(child)

        population = new_pop

    ga_time = time.time() - t0
    ms_per_gen = (ga_time / generations) * 1000.0
    return best_time, best_dist, best_violations, ga_time, ms_per_gen

# -----------------------------------------------------------------------------
# Main Benchmark Execution
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 74)
    print("      SINGLE-DEPOT VRP GA SCALABILITY BENCHMARK SUITE")
    print("=" * 74)

    G = load_road_graph()
    annotate_graph_edges(G)

    # Select 1 Central Depot Node
    # Pick a high degree central node
    node_degrees = dict(G.degree())
    depot_node = max(node_degrees.keys(), key=lambda n: node_degrees[n])
    print(f"\nDepot Node selected: {depot_node} (Degree = {node_degrees[depot_node]})")

    results = []

    # Get available candidate customer nodes (excluding depot)
    candidate_nodes = [n for n in G.nodes() if n != depot_node]

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print(f"\n" + "-" * 74)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | 1 Depot")
        print(f"-" * 74)

        # Sample customer nodes
        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        # 1. Precompute matrices
        print(f"  [Dijkstra] Precomputing shortest paths for {num_cust + 1} locations...")
        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)

        # 2. Run GA
        evaluator = FastSingleDepotEvaluator(
            time_mat=time_mat,
            dist_mat=dist_mat,
            demands=demands,
            num_vehicles=num_veh,
            vehicle_capacity=capacity,
            max_duration=max_duration
        )

        print(f"  [GA] Optimizing single-depot routes over {GENERATIONS} generations...")
        best_time_s, best_dist_m, violations, ga_time, ms_per_gen = run_single_depot_ga(
            evaluator, num_customers=num_cust, pop_size=POP_SIZE, generations=GENERATIONS
        )

        total_runtime = dijkstra_time + ga_time
        best_dist_km = best_dist_m / 1000.0
        is_valid = (violations == 0)

        print(f"  --> Total Runtime   : {total_runtime:.2f} s (Dijkstra: {dijkstra_time:.2f}s, GA: {ga_time:.2f}s)")
        print(f"  --> Speed           : {ms_per_gen:.2f} ms / generation")
        print(f"  --> Best Travel Time: {best_time_s:.1f} s ({best_time_s/3600.0:.2f} hrs)")
        print(f"  --> Best Distance   : {best_dist_km:.2f} km")
        print(f"  --> Violations      : {violations} ({'VALID' if is_valid else 'INVALID'})")

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "num_depots": 1,
            "total_runtime_s": round(total_runtime, 2),
            "dijkstra_time_s": round(dijkstra_time, 2),
            "ga_time_s": round(ga_time, 2),
            "ms_per_gen": round(ms_per_gen, 2),
            "best_travel_time_s": round(best_time_s, 1),
            "best_distance_km": round(best_dist_km, 2),
            "violations": int(violations),
            "is_valid": is_valid
        })

    # -------------------------------------------------------------------------
    # Save CSV Report
    # -------------------------------------------------------------------------
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "single_depot_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Summary report saved to: {csv_path}")

    # -------------------------------------------------------------------------
    # Plot Visualizations
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Single-Depot VRP GA Scalability Comparison (1 Depot, 20 to 1,000 Customers)", fontsize=14, fontweight="bold")

    cust_labels = [f"{r['num_customers']} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: Execution Time Breakdown
    ax1 = axes[0, 0]
    ax1.bar(cust_labels, [r['dijkstra_time_s'] for r in results], label="Dijkstra Precompute (s)", color="#3498db")
    ax1.bar(cust_labels, [r['ga_time_s'] for r in results], bottom=[r['dijkstra_time_s'] for r in results], label="GA Evolution (s)", color="#2ecc71")
    ax1.set_ylabel("Time (seconds)")
    ax1.set_title("Runtime Breakdown by Scale")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: MS per Generation
    ax2 = axes[0, 1]
    ax2.plot(cust_labels, [r['ms_per_gen'] for r in results], marker="o", color="#e74c3c", linewidth=2.5)
    ax2.set_ylabel("ms / Generation")
    ax2.set_title("GA Speed per Generation")
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Panel 3: Best Total Distance (km)
    ax3 = axes[1, 0]
    ax3.plot(cust_labels, [r['best_distance_km'] for r in results], marker="s", color="#9b59b6", linewidth=2.5)
    ax3.set_ylabel("Total Distance (km)")
    ax3.set_title("Best Route Distance vs Scale")
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Violations & Feasibility Status
    ax4 = axes[1, 1]
    colors = ["#2ecc71" if r['is_valid'] else "#e74c3c" for r in results]
    ax4.bar(cust_labels, [r['violations'] for r in results], color=colors)
    ax4.set_ylabel("Violation Count")
    ax4.set_title("Constraint Violations (Green = 100% Feasible)")
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "single_depot_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"[VISUALIZATION] Scalability charts saved to: {plot_path}")
    print("=" * 74)
    print("      SINGLE-DEPOT BENCHMARK SUITE COMPLETE!")
    print("=" * 74)

if __name__ == "__main__":
    main()
