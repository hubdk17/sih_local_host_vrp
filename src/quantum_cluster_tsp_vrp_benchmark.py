"""
quantum_cluster_tsp_vrp_benchmark.py

Two-Level Hierarchical Quantum Algorithm for Single-Depot VRP:
  - Level 1 (Macro): Quantum Rotation Gates optimize Customer-to-Vehicle Cluster Assignments.
  - Level 2 (Micro): Spatial Heuristics (Nearest Neighbor + 2-Opt Local Search) solve optimal
                     intra-route TSP sequencing for each vehicle.

Mathematical Formulation:
  1. Quantum Phase Angle Assignment:
     Each customer i has a quantum phase angle theta_i in [0, 2*pi].
     Vehicle assignment: v(i) = min(V - 1, floor(theta_i / (2*pi / V)))
  2. Quantum Rotation Gate Update:
     Theta^(t+1) = Theta^(t) + sign(Theta_best - Theta) * delta_theta * (1 - t/T)
     Adjusts customer clustering continuously based on global best fleet partition.
  3. Quantum Hadamard Mutation:
     Randomly shifts qubits to restore cluster exploration and avoid local trapping.
  4. Intra-Cluster Spatial Routing (Level 2):
     For each vehicle cluster C_v, builds route via Nearest-Neighbor from depot (0),
     followed by 2-Opt edge untangling.
"""

import os
import time
import math
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import osmnx as ox
import networkx as nx

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BENCHMARK_SCALES = [
    {"name": "20_cust",   "num_customers": 20,   "num_vehicles": 4,  "capacity": 20, "max_duration": 7200.0},
    {"name": "50_cust",   "num_customers": 50,   "num_vehicles": 5,  "capacity": 25, "max_duration": 7200.0},
    {"name": "100_cust",  "num_customers": 100,  "num_vehicles": 10, "capacity": 25, "max_duration": 7200.0},
    {"name": "200_cust",  "num_customers": 200,  "num_vehicles": 20, "capacity": 25, "max_duration": 7200.0},
    {"name": "500_cust",  "num_customers": 500,  "num_vehicles": 25, "capacity": 45, "max_duration": 10800.0},
    {"name": "1000_cust", "num_customers": 1000, "num_vehicles": 50, "capacity": 45, "max_duration": 14400.0},
]

POP_SIZE = 60
GENERATIONS = 150
SEED = 42

# Quantum Rotation Step
QUANTUM_ROT_STEP = 0.08 * math.pi
QUANTUM_MUTATION_PROB = 0.08

OUTPUT_DIR = os.path.join("outputs", "ga", "quantum_cluster")

# -----------------------------------------------------------------------------
# Graph & Distance Matrix Helper
# -----------------------------------------------------------------------------
def load_road_graph():
    delhi_path = os.path.join("data", "delhi", "delhi_road_network.graphml")
    full_delhi_path = os.path.join("data", "delhi", "full_delhi_road_network.graphml")
    chandigarh_path = os.path.join("data", "scaled", "chandigarh_20_sectors.graphml")

    for path in [delhi_path, full_delhi_path, chandigarh_path]:
        if os.path.exists(path):
            print(f"Loading road network graph from: {path}...")
            G = ox.load_graphml(path)
            print(f"Graph loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
    raise FileNotFoundError("No road graph found.")

def annotate_graph_edges(G):
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
# Level 2: Deterministic Intra-Cluster Routing (Nearest Neighbor + 2-Opt)
# -----------------------------------------------------------------------------
def solve_tsp_nearest_neighbor_2opt(cluster_nodes, time_mat, dist_mat):
    """
    Solves optimal TSP route for a single vehicle cluster starting and ending at depot (0).
    Uses Nearest Neighbor path construction followed by 2-Opt local search refinement.
    """
    if len(cluster_nodes) == 0:
        return [], 0.0, 0.0

    # 1. Nearest Neighbor construction from depot (0)
    unvisited = set(cluster_nodes)
    curr = 0
    route = []

    while unvisited:
        next_node = min(unvisited, key=lambda n: time_mat[curr, n])
        route.append(next_node)
        unvisited.remove(next_node)
        curr = next_node

    # 2. Fast 2-Opt local search refinement on the route
    if len(route) >= 4:
        improved = True
        attempts = 0
        while improved and attempts < 15:
            improved = False
            attempts += 1
            full_r = [0] + route + [0]
            n = len(full_r)
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    # Check if reversing route between i and j reduces travel time
                    a, b = full_r[i - 1], full_r[i]
                    c, d = full_r[j], full_r[j + 1]
                    current_cost = time_mat[a, b] + time_mat[c, d]
                    new_cost = time_mat[a, c] + time_mat[b, d]
                    if new_cost < current_cost - 1e-3:
                        route[i - 1:j] = reversed(route[i - 1:j])
                        improved = True
                        break
                if improved:
                    break

    # Calculate final route time and distance
    full_r = np.array([0] + route + [0], dtype=np.int32)
    r_time = float(np.sum(time_mat[full_r[:-1], full_r[1:]]))
    r_dist = float(np.sum(dist_mat[full_r[:-1], full_r[1:]]))
    return route, r_time, r_dist

# -----------------------------------------------------------------------------
# Level 1: Quantum Clustering Evaluator
# -----------------------------------------------------------------------------
class TwoLevelQuantumEvaluator:
    def __init__(self, time_mat, dist_mat, demands, num_vehicles, vehicle_capacity, max_duration):
        self.time_mat = time_mat
        self.dist_mat = dist_mat
        self.demands = np.array([0] + list(demands), dtype=np.int32)
        self.num_customers = len(demands)
        self.num_vehicles = num_vehicles
        self.vehicle_capacity = vehicle_capacity
        self.max_duration = max_duration

    def decode_quantum_angles_to_clusters(self, theta_vector):
        """
        Maps continuous quantum phase angles theta_i in [0, 2*pi] to vehicle cluster indices:
          v(i) = min(V - 1, floor(theta_i / (2*pi / V)))
        """
        bin_width = (2.0 * math.pi) / float(self.num_vehicles)
        cluster_assignments = np.floor(theta_vector / bin_width).astype(int)
        cluster_assignments = np.clip(cluster_assignments, 0, self.num_vehicles - 1)
        
        clusters = [[] for _ in range(self.num_vehicles)]
        for cust_idx, v in enumerate(cluster_assignments, start=1):
            clusters[v].append(cust_idx)
        return clusters

    def evaluate(self, theta_vector):
        """
        Two-level evaluation:
          1. Decode quantum angles into V vehicle clusters.
          2. Solve intra-cluster routes via Nearest Neighbor + 2-Opt.
          3. Evaluate total time, distance, capacity & duration constraints.
        """
        clusters = self.decode_quantum_angles_to_clusters(theta_vector)
        total_time = 0.0
        total_dist = 0.0
        capacity_violations = 0
        duration_violations = 0
        routes = []

        for v_idx, cluster_nodes in enumerate(clusters):
            if len(cluster_nodes) == 0:
                continue

            # Check capacity
            c_demand = np.sum(self.demands[cluster_nodes])
            if c_demand > self.vehicle_capacity:
                capacity_violations += (c_demand - self.vehicle_capacity)

            # Solve intra-cluster routing (Level 2)
            route, r_time, r_dist = solve_tsp_nearest_neighbor_2opt(cluster_nodes, self.time_mat, self.dist_mat)
            routes.append(route)
            total_time += r_time
            total_dist += r_dist

            if r_time > self.max_duration:
                duration_violations += (r_time - self.max_duration)

        total_violations = capacity_violations + duration_violations
        fitness = total_time + total_violations * 1000.0
        return fitness, total_time, total_dist, total_violations, routes

# -----------------------------------------------------------------------------
# Quantum Cluster Chromosome
# -----------------------------------------------------------------------------
class QuantumClusterChromosome:
    def __init__(self, num_customers, theta=None):
        self.num_customers = num_customers
        if theta is None:
            # Random initial phase angles in [0, 2*pi]
            self.theta = np.random.uniform(0.0, 2.0 * math.pi, size=num_customers).astype(np.float32)
        else:
            self.theta = np.array(theta, dtype=np.float32)

    def apply_rotation_gate(self, best_theta, gen, total_generations):
        """
        Quantum Rotation Gate Update in phase angle space:
          theta_i^(t+1) = theta_i^(t) + sign(best_theta_i - theta_i) * delta_theta * (1 - t/T)
        """
        decay = 1.0 - (gen / float(total_generations))
        step = QUANTUM_ROT_STEP * decay
        
        diff = best_theta - self.theta
        # Shortest circular angle difference
        diff = (diff + math.pi) % (2.0 * math.pi) - math.pi
        dTheta = np.sign(diff) * step

        self.theta = (self.theta + dTheta) % (2.0 * math.pi)

    def apply_quantum_mutation(self):
        """Quantum Hadamard / Phase Flip Mutation."""
        mask = np.random.random(size=self.num_customers) < QUANTUM_MUTATION_PROB
        self.theta[mask] = (self.theta[mask] + np.random.uniform(0.1, math.pi, size=np.sum(mask))) % (2.0 * math.pi)

# -----------------------------------------------------------------------------
# Heuristic Angle Initializer
# -----------------------------------------------------------------------------
def initialize_heuristic_quantum_clusters(pop_size, num_customers, num_vehicles, G, depot_node, customer_nodes):
    """
    Initializes Quantum Population:
      - 50% Polar Sector Angle Encoding: Encodes natural geographic angles [0, 2*pi]
        around the depot so vehicles start with geographically compact sectors.
      - 50% Random Perturbed Angles: Preserves global exploration diversity.
    """
    population = []
    depot_y = G.nodes[depot_node]['y']
    depot_x = G.nodes[depot_node]['x']

    # Compute polar angle for each customer around depot in [0, 2*pi]
    base_angles = []
    for c in customer_nodes:
        cy = G.nodes[c]['y']
        cx = G.nodes[c]['x']
        angle = math.atan2(cy - depot_y, cx - depot_x)
        if angle < 0: angle += 2.0 * math.pi
        base_angles.append(angle)
    base_angles = np.array(base_angles, dtype=np.float32)

    # 1. Geographic Polar Sector Angle Individuals
    num_sector = pop_size // 2
    for _ in range(num_sector):
        # Slightly perturbed polar angles
        perturbed = (base_angles + np.random.normal(0, 0.15, size=num_customers)) % (2.0 * math.pi)
        population.append(QuantumClusterChromosome(num_customers, theta=perturbed))

    # 2. Random Exploratory Angle Individuals
    for _ in range(pop_size - num_sector):
        population.append(QuantumClusterChromosome(num_customers))

    return population

# -----------------------------------------------------------------------------
# Two-Level Quantum Cluster-TSP Engine
# -----------------------------------------------------------------------------
def run_quantum_cluster_tsp(evaluator, num_customers, num_vehicles, G, depot_node, customer_nodes, pop_size=60, generations=150):
    t0 = time.time()

    population = initialize_heuristic_quantum_clusters(pop_size, num_customers, num_vehicles, G, depot_node, customer_nodes)

    best_theta = None
    best_fit = float("inf")
    best_time = float("inf")
    best_dist = float("inf")
    best_violations = 0
    best_routes = []

    for gen in range(generations):
        # Level 1 + Level 2 Evaluation
        evals = [evaluator.evaluate(ind.theta) for ind in population]
        fitnesses = [e[0] for e in evals]

        # Track global best
        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_theta = np.copy(population[min_idx].theta)
            _, best_time, best_dist, best_violations, best_routes = evals[min_idx]

        # Quantum Rotation Gate Evolution
        for ind in population:
            ind.apply_rotation_gate(best_theta, gen, generations)
            if random.random() < 0.2:
                ind.apply_quantum_mutation()

    runtime = time.time() - t0
    best_dist_km = best_dist / 1000.0
    return best_dist_km, best_time, best_violations, runtime, best_routes

# -----------------------------------------------------------------------------
# Main Benchmark Execution
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 84)
    print("   TWO-LEVEL QUANTUM CLUSTERING + LOCAL TSP (Q-Cluster-TSP) VRP BENCHMARK")
    print("=" * 84)

    G = load_road_graph()
    annotate_graph_edges(G)

    node_degrees = dict(G.degree())
    depot_node = max(node_degrees.keys(), key=lambda n: node_degrees[n])
    print(f"\nDepot Node selected: {depot_node} (Degree = {node_degrees[depot_node]})")

    candidate_nodes = [n for n in G.nodes() if n != depot_node]

    # Load baseline summaries for comparison
    hga_csv = os.path.join("outputs", "ga", "heuristic_single_depot", "hga_summary.csv")
    prev_qga_csv = os.path.join("outputs", "ga", "quantum_single_depot", "qga_summary.csv")

    hga_df = pd.read_csv(hga_csv) if os.path.exists(hga_csv) else None
    prev_qga_df = pd.read_csv(prev_qga_csv) if os.path.exists(prev_qga_csv) else None

    results = []

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print(f"\n" + "-" * 84)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | 1 Central Depot")
        print(f"-" * 84)

        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        print(f"  [Dijkstra] Precomputing shortest paths for {num_cust + 1} locations...")
        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)

        evaluator = TwoLevelQuantumEvaluator(time_mat, dist_mat, demands, num_veh, capacity, max_duration)

        print(f"  [Q-Cluster-TSP] Evolving Quantum Cluster Assignments + Local 2-Opt TSP...")
        best_dist_km, best_time_s, violations, q_time, best_routes = run_quantum_cluster_tsp(
            evaluator, num_cust, num_veh, G, depot_node, customer_nodes, pop_size=POP_SIZE, generations=GENERATIONS
        )

        total_runtime = dijkstra_time + q_time
        is_valid = (violations == 0)

        # Retrieve comparisons
        hga_dist = hga_df[hga_df["scale_name"] == scale_name]["best_distance_km"].values[0] if hga_df is not None else np.nan
        old_qga_dist = prev_qga_df[prev_qga_df["scale_name"] == scale_name]["best_distance_km"].values[0] if prev_qga_df is not None else np.nan

        gain_vs_old_qga = ((old_qga_dist - best_dist_km) / old_qga_dist) * 100.0 if not np.isnan(old_qga_dist) else np.nan

        print(f"  --> Total Runtime      : {total_runtime:.2f} s (Dijkstra: {dijkstra_time:.2f}s, Q-Cluster: {q_time:.2f}s)")
        print(f"  --> Best Distance      : {best_dist_km:.2f} km")
        print(f"  --> Best Travel Time   : {best_time_s:.1f} s ({best_time_s/3600.0:.2f} hrs)")
        print(f"  --> Violations         : {violations} ({'VALID' if is_valid else 'INVALID'})")
        if not np.isnan(old_qga_dist):
            print(f"  --> Gain vs Old Q-HGA  : {gain_vs_old_qga:+.2f}% distance reduction (vs {old_qga_dist:.2f} km)")
        if not np.isnan(hga_dist):
            print(f"  --> Benchmark vs H-GA  : {best_dist_km:.2f} km vs {hga_dist:.2f} km")

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "total_runtime_s": round(total_runtime, 2),
            "dijkstra_time_s": round(dijkstra_time, 2),
            "q_cluster_time_s": round(q_time, 2),
            "best_distance_km": round(best_dist_km, 2),
            "best_travel_time_s": round(best_time_s, 1),
            "hga_distance_km": round(hga_dist, 2),
            "old_qga_distance_km": round(old_qga_dist, 2),
            "gain_vs_old_qga_pct": round(gain_vs_old_qga, 2),
            "violations": int(violations),
            "is_valid": is_valid
        })

    # Save summary CSV
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "qcluster_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Summary report saved to: {csv_path}")

    # Plot Comparison Charts
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Two-Level Quantum Clustering + Local TSP (Q-Cluster-TSP) vs Old Q-HGA & H-GA", fontsize=13, fontweight="bold")

    cust_labels = [f"{r['num_customers']} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: Route Distance Comparison (Old Q-HGA vs New Q-Cluster-TSP vs H-GA)
    ax1 = axes[0, 0]
    if prev_qga_df is not None:
        ax1.plot(cust_labels, df["old_qga_distance_km"], marker="x", color="#e74c3c", linestyle=":", linewidth=2, label="Old Q-HGA (Rank Mapping)")
    if hga_df is not None:
        ax1.plot(cust_labels, df["hga_distance_km"], marker="s", color="#3498db", linestyle="--", linewidth=2, label="Heuristic GA (H-GA)")
    ax1.plot(cust_labels, df["best_distance_km"], marker="o", color="#2ecc71", linewidth=2.5, label="New Q-Cluster-TSP (Quantum Cluster + 2-Opt)")
    ax1.set_ylabel("Total Distance (km)")
    ax1.set_title("Best Route Distance (Lower is Better)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Improvement over Old Q-HGA (%)
    ax2 = axes[0, 1]
    if prev_qga_df is not None:
        bars = ax2.bar(cust_labels, df["gain_vs_old_qga_pct"], color="#2ecc71")
        ax2.set_ylabel("Distance Reduction (%)")
        ax2.set_title("New Q-Cluster-TSP Distance Gain vs Old Q-HGA")
        ax2.grid(True, linestyle="--", alpha=0.5)
        for bar in bars:
            yval = bar.get_height()
            if not np.isnan(yval):
                ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 1.0, f"+{yval:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Panel 3: Execution Runtime Breakdown
    ax3 = axes[1, 0]
    ax3.bar(cust_labels, df["dijkstra_time_s"], label="Dijkstra Precompute (s)", color="#34495e")
    ax3.bar(cust_labels, df["q_cluster_time_s"], bottom=df["dijkstra_time_s"], label="Q-Cluster Evolution (s)", color="#9b59b6")
    ax3.set_ylabel("Time (seconds)")
    ax3.set_title("Execution Runtime Breakdown")
    ax3.legend()
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Violations
    ax4 = axes[1, 1]
    colors = ["#2ecc71" if r['is_valid'] else "#e74c3c" for r in results]
    ax4.bar(cust_labels, df["violations"], color=colors)
    ax4.set_ylabel("Violation Count")
    ax4.set_title("Constraint Violations (Green = 100% Valid)")
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "qcluster_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"[VISUALIZATION] Comparison charts saved to: {plot_path}")
    print("=" * 84)
    print("   TWO-LEVEL QUANTUM CLUSTER-TSP BENCHMARK COMPLETE!")
    print("=" * 84)

if __name__ == "__main__":
    main()
