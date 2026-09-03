"""
quantum_heuristic_ga_benchmark.py

Quantum-Inspired Heuristic Genetic Algorithm (Q-HGA) for Single-Depot VRP.

Mathematical Framework:
  1. Qubit Representation: Each chromosome is represented by an N-length vector of Quantum Phase Angles
     Theta = [theta_1, theta_2, ..., theta_N] in [0, pi/2], with probability amplitudes:
       alpha_i = cos(theta_i),  beta_i = sin(theta_i)   such that |alpha_i|^2 + |beta_i|^2 = 1.
  2. Quantum Superposition Observation: A quantum state is collapsed into a deterministic permutation by
     ranking probability amplitudes |beta_i|^2 = sin^2(theta_i) + quantum phase noise.
  3. Quantum Rotation Gate Update: Qubits evolve via 2D unitary rotation matrices:
       [alpha_i^(t+1)] = [cos(dTheta_i)  -sin(dTheta_i)] [alpha_i^(t)]
       [beta_i^(t+1) ]   [sin(dTheta_i)   cos(dTheta_i)] [beta_i^(t) ]
     where dTheta_i = -sign(sin(theta_i - theta_best_i)) * theta_step * (1 - t/T).
  4. Quantum Interference & Mutation: Applies Hadamard phase shift gates to prevent premature collapse.
  5. Heuristic Quantum Initialization: Maps Random, Greedy Sector, and Nearest-Neighbor tours into
     quantum phase angle matrices.

Evaluates scalability across 6 scale points:
  1. 20 Customers   | 4 Vehicles   | 1 Depot
  2. 50 Customers   | 5 Vehicles   | 1 Depot
  3. 100 Customers  | 10 Vehicles  | 1 Depot
  4. 200 Customers  | 20 Vehicles  | 1 Depot
  5. 500 Customers  | 25 Vehicles  | 1 Depot
  6. 1,000 Customers | 50 Vehicles  | 1 Depot

Saves outputs to:
  - CSV report: outputs/ga/quantum_single_depot/qga_summary.csv
  - Visualizations: outputs/ga/quantum_single_depot/qga_vs_hga_comparison.png
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
SEED = 42

# Quantum Parameters
QUANTUM_ROTATION_STEP = 0.05 * math.pi  # Rotation angle step size (radians)
QUANTUM_MUTATION_PROB = 0.05           # Hadamard phase shift mutation probability

OUTPUT_DIR = os.path.join("outputs", "ga", "quantum_single_depot")

# -----------------------------------------------------------------------------
# Graph & Matrix Helpers
# -----------------------------------------------------------------------------
def load_road_graph():
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
# Fast Single-Depot Vectorized Evaluator
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
# Quantum-Inspired Mathematics & Qubit Chromosome Operations
# -----------------------------------------------------------------------------
class QuantumQubitChromosome:
    """
    Represents an N-customer quantum chromosome defined by an N-dimensional
    vector of Quantum Phase Angles theta_i in [0, pi/2].
    """
    def __init__(self, num_customers, theta=None):
        self.num_customers = num_customers
        if theta is None:
            # Equal superposition state: alpha = beta = 1/sqrt(2), theta = pi/4
            self.theta = np.full(num_customers, math.pi / 4.0, dtype=np.float32)
        else:
            self.theta = np.array(theta, dtype=np.float32)

    @property
    def alpha(self):
        """Probability amplitude alpha = cos(theta)."""
        return np.cos(self.theta)

    @property
    def beta(self):
        """Probability amplitude beta = sin(theta)."""
        return np.sin(self.theta)

    def observe(self):
        """
        Quantum Measurement / Collapse:
        Observes the quantum superposition state |psi> = cos(theta)|0> + sin(theta)|1>
        into a deterministic customer permutation [p_1, p_2, ..., p_N] by ranking
        quantum probability amplitudes |beta_i|^2 = sin^2(theta_i) + random phase noise.
        """
        probabilities = np.square(self.beta)
        # Add slight quantum measurement fluctuation
        quantum_measurement = probabilities + np.random.normal(0, 0.02, size=self.num_customers)
        # Order customer indices 1..N based on quantum measurement ranking
        perm_indices = np.argsort(quantum_measurement)
        permutation = (perm_indices + 1).tolist()
        return permutation

    def apply_rotation_gate(self, best_theta, gen, total_generations):
        """
        Quantum Rotation Gate Update R(dTheta):
          [alpha_i^(t+1)] = [cos(dTheta_i)  -sin(dTheta_i)] [alpha_i^(t)]
          [beta_i^(t+1) ]   [sin(dTheta_i)   cos(dTheta_i)] [beta_i^(t) ]

        Or in phase angle representation:
          theta_i^(t+1) = theta_i^(t) + dTheta_i
        where dTheta_i attracts qubit phase towards global best state theta_best_i.
        """
        # Adaptive rotation step size (decaying with generation)
        decay = 1.0 - (gen / float(total_generations))
        step = QUANTUM_ROTATION_STEP * decay

        # Direction vector towards best quantum phase angle
        diff = best_theta - self.theta
        dTheta = np.sign(diff) * step

        # Update quantum phase angles
        self.theta += dTheta
        # Enforce quantum state boundary [0.01, pi/2 - 0.01]
        self.theta = np.clip(self.theta, 0.01, (math.pi / 2.0) - 0.01)

    def apply_hadamard_mutation(self):
        """
        Quantum Hadamard Mutation:
        Applies a Hadamard gate H to random qubits, resetting them into equal superposition
        (theta = pi/4), restoring quantum diversity and preventing state collapse.
        """
        mask = np.random.random(size=self.num_customers) < QUANTUM_MUTATION_PROB
        self.theta[mask] = math.pi / 4.0

# -----------------------------------------------------------------------------
# Heuristic Quantum Initializer
# -----------------------------------------------------------------------------
def encode_permutation_to_quantum_theta(permutation, num_customers):
    """
    Encodes a discrete customer permutation [p_1, p_2, ..., p_N] into continuous
    quantum phase angles theta_i in [0, pi/2] such that:
      sin^2(theta_i) = p_i / (N + 1)
      theta_i = arcsin( sqrt(p_i / (N + 1)) )
    """
    norm_vals = np.array(permutation, dtype=np.float32) / float(num_customers + 1)
    theta = np.arcsin(np.sqrt(norm_vals))
    return theta

def initialize_quantum_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat):
    """
    Encodes 3-tier Heuristic Initial Population (Random, Greedy Sector, Nearest Neighbor)
    into Quantum Qubit Chromosomes theta_i.
    """
    q_population = []
    cust_indices = list(range(1, num_customers + 1))

    # Generate heuristic permutations
    num_random = int(pop_size * 0.20)
    num_greedy = int(pop_size * 0.20)
    num_nn = pop_size - num_random - num_greedy

    perms = []
    # 1. Random Permutations
    for _ in range(num_random):
        perms.append(np.random.permutation(cust_indices).tolist())

    # 2. Greedy Sector Permutations
    depot_y, depot_x = G.nodes[depot_node]['y'], G.nodes[depot_node]['x']
    angles = [math.atan2(G.nodes[c]['y'] - depot_y, G.nodes[c]['x'] - depot_x) for c in customer_nodes]
    sector_sorted = [idx for _, idx in sorted(zip(angles, cust_indices))]
    for _ in range(num_greedy):
        ind = list(sector_sorted)
        if random.random() < 0.7:
            for _ in range(random.randint(1, max(2, num_customers // 10))):
                idx1, idx2 = random.sample(range(num_customers), 2)
                ind[idx1], ind[idx2] = ind[idx2], ind[idx1]
        perms.append(ind)

    # 3. Nearest Neighbor Tours
    for i in range(num_nn):
        unvisited = set(cust_indices)
        curr = 0 if i == 0 else random.choice(cust_indices)
        if curr != 0: unvisited.remove(curr)
        nn_tour = [] if curr == 0 else [curr]
        while unvisited:
            next_cust = min(unvisited, key=lambda c: time_mat[curr, c])
            nn_tour.append(next_cust)
            unvisited.remove(next_cust)
            curr = next_cust
        perms.append(nn_tour)

    # Encode permutations into Quantum Qubit Chromosomes
    for p in perms:
        q_theta = encode_permutation_to_quantum_theta(p, num_customers)
        q_population.append(QuantumQubitChromosome(num_customers, theta=q_theta))

    return q_population

# -----------------------------------------------------------------------------
# Quantum-Inspired Heuristic GA Engine
# -----------------------------------------------------------------------------
def run_quantum_heuristic_ga(evaluator, num_customers, G, depot_node, customer_nodes, time_mat, pop_size=100, generations=200):
    t0 = time.time()

    # 1. Initialize Quantum Population
    q_population = initialize_quantum_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat)

    best_q_theta = None
    best_fit = float("inf")
    best_time = float("inf")
    best_dist = float("inf")
    best_violations = 0

    for gen in range(generations):
        # 2. Quantum Collapse / Measurement: Observe continuous qubit angles into discrete permutations
        observed_perms = [q_ind.observe() for q_ind in q_population]

        # 3. Evaluate observed permutations
        evals = [evaluator.evaluate(p) for p in observed_perms]
        fitnesses = [e[0] for e in evals]

        # Track global best quantum state
        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_q_theta = np.copy(q_population[min_idx].theta)
            _, best_time, best_dist, best_violations = evals[min_idx]

        # 4. Quantum Gate Evolution: Apply Quantum Rotation Gates towards best_q_theta
        for q_ind in q_population:
            q_ind.apply_rotation_gate(best_q_theta, gen, generations)

            # 5. Quantum Hadamard Mutation
            if random.random() < 0.2:
                q_ind.apply_hadamard_mutation()

    ga_time = time.time() - t0
    ms_per_gen = (ga_time / generations) * 1000.0
    best_dist_km = best_dist / 1000.0
    return best_time, best_dist_km, best_violations, ga_time, ms_per_gen

# -----------------------------------------------------------------------------
# Main Execution Benchmark
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 82)
    print("   QUANTUM-INSPIRED HEURISTIC GA (Q-HGA) SINGLE-DEPOT VRP BENCHMARK SUITE")
    print("=" * 82)

    G = load_road_graph()
    annotate_graph_edges(G)

    node_degrees = dict(G.degree())
    depot_node = max(node_degrees.keys(), key=lambda n: node_degrees[n])
    print(f"\nDepot Node selected: {depot_node} (Degree = {node_degrees[depot_node]})")

    candidate_nodes = [n for n in G.nodes() if n != depot_node]

    # Load baseline files for 3-way comparison
    rand_csv = os.path.join("outputs", "ga", "single_depot", "single_depot_summary.csv")
    hga_csv = os.path.join("outputs", "ga", "heuristic_single_depot", "hga_summary.csv")

    rand_df = pd.read_csv(rand_csv) if os.path.exists(rand_csv) else None
    hga_df = pd.read_csv(hga_csv) if os.path.exists(hga_csv) else None

    results = []

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print(f"\n" + "-" * 82)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | 1 Depot")
        print(f"-" * 82)

        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        # Precompute shortest path matrices
        print(f"  [Dijkstra] Precomputing shortest paths for {num_cust + 1} locations...")
        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)

        evaluator = FastSingleDepotEvaluator(time_mat, dist_mat, demands, num_veh, capacity, max_duration)

        # Run Quantum-Inspired Heuristic GA
        print(f"  [Q-HGA] Evolving Qubit Chromosomes with Quantum Rotation Gates over {GENERATIONS} gen...")
        best_time_s, best_dist_km, violations, ga_time, ms_per_gen = run_quantum_heuristic_ga(
            evaluator, num_cust, G, depot_node, customer_nodes, time_mat, POP_SIZE, GENERATIONS
        )

        total_runtime = dijkstra_time + ga_time
        is_valid = (violations == 0)

        # Retrieve comparisons
        rand_dist = rand_df[rand_df["scale_name"] == scale_name]["best_distance_km"].values[0] if rand_df is not None else np.nan
        hga_dist = hga_df[hga_df["scale_name"] == scale_name]["best_distance_km"].values[0] if hga_df is not None else np.nan

        gain_vs_rand = ((rand_dist - best_dist_km) / rand_dist) * 100.0 if not np.isnan(rand_dist) else np.nan
        gain_vs_hga = ((hga_dist - best_dist_km) / hga_dist) * 100.0 if not np.isnan(hga_dist) else np.nan

        print(f"  --> Total Runtime   : {total_runtime:.2f} s (Dijkstra: {dijkstra_time:.2f}s, Q-HGA: {ga_time:.2f}s)")
        print(f"  --> Speed           : {ms_per_gen:.2f} ms / generation")
        print(f"  --> Best Travel Time: {best_time_s:.1f} s ({best_time_s/3600.0:.2f} hrs)")
        print(f"  --> Best Distance   : {best_dist_km:.2f} km")
        if not np.isnan(gain_vs_rand):
            print(f"  --> Gain vs Random  : {gain_vs_rand:+.2f}% distance reduction (vs {rand_dist:.2f} km)")
        if not np.isnan(gain_vs_hga):
            print(f"  --> Gain vs H-GA    : {gain_vs_hga:+.2f}% distance reduction (vs {hga_dist:.2f} km)")
        print(f"  --> Violations      : {violations} ({'VALID' if is_valid else 'INVALID'})")

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "num_depots": 1,
            "total_runtime_s": round(total_runtime, 2),
            "dijkstra_time_s": round(dijkstra_time, 2),
            "qhga_time_s": round(ga_time, 2),
            "ms_per_gen": round(ms_per_gen, 2),
            "best_travel_time_s": round(best_time_s, 1),
            "best_distance_km": round(best_dist_km, 2),
            "random_ga_dist_km": round(rand_dist, 2),
            "hga_dist_km": round(hga_dist, 2),
            "gain_vs_random_pct": round(gain_vs_rand, 2),
            "gain_vs_hga_pct": round(gain_vs_hga, 2),
            "violations": int(violations),
            "is_valid": is_valid
        })

    # Save summary CSV
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "qga_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Summary report saved to: {csv_path}")

    # Plot 3-Way Algorithm Comparison Chart
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Quantum-Inspired Heuristic GA (Q-HGA) vs Heuristic GA vs Random GA", fontsize=13, fontweight="bold")

    cust_labels = [f"{r['num_customers']} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: 3-Way Distance Comparison
    ax1 = axes[0, 0]
    if rand_df is not None:
        ax1.plot(cust_labels, df["random_ga_dist_km"], marker="o", color="#e74c3c", linestyle="--", linewidth=2, label="Standard Random GA")
    if hga_df is not None:
        ax1.plot(cust_labels, df["hga_dist_km"], marker="s", color="#3498db", linestyle="-.", linewidth=2, label="Heuristic GA (H-GA)")
    ax1.plot(cust_labels, df["best_distance_km"], marker="^", color="#2ecc71", linewidth=2.5, label="Quantum-Inspired H-GA (Q-HGA)")
    ax1.set_ylabel("Total Distance (km)")
    ax1.set_title("Best Route Distance (Lower is Better)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Q-HGA Distance Gain (%) vs Random GA
    ax2 = axes[0, 1]
    bars = ax2.bar(cust_labels, df["gain_vs_random_pct"], color="#2ecc71")
    ax2.set_ylabel("Distance Reduction (%)")
    ax2.set_title("Q-HGA Distance Gain vs Standard Random GA")
    ax2.grid(True, linestyle="--", alpha=0.5)
    for bar in bars:
        yval = bar.get_height()
        if not np.isnan(yval):
            ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"+{yval:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Panel 3: Execution Time Breakdown
    ax3 = axes[1, 0]
    ax3.bar(cust_labels, df["dijkstra_time_s"], label="Dijkstra Precompute (s)", color="#34495e")
    ax3.bar(cust_labels, df["qhga_time_s"], bottom=df["dijkstra_time_s"], label="Q-HGA Evolution (s)", color="#9b59b6")
    ax3.set_ylabel("Time (seconds)")
    ax3.set_title("Q-HGA Execution Runtime Breakdown")
    ax3.legend()
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Violations
    ax4 = axes[1, 1]
    colors = ["#2ecc71" if r['is_valid'] else "#e74c3c" for r in results]
    ax4.bar(cust_labels, df["violations"], color=colors)
    ax4.set_ylabel("Violation Count")
    ax4.set_title("Q-HGA Constraint Violations (Green = 100% Valid)")
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "qga_vs_hga_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"[VISUALIZATION] Comparison charts saved to: {plot_path}")
    print("=" * 82)
    print("   QUANTUM-INSPIRED HEURISTIC GA BENCHMARK SUITE COMPLETE!")
    print("=" * 82)

if __name__ == "__main__":
    main()
