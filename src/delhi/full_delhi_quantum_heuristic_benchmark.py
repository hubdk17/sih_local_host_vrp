"""
full_delhi_quantum_heuristic_benchmark.py

Applies Heuristic GA (H-GA) and Quantum-Inspired Heuristic GA (Q-HGA)
on the complete road network of the National Capital Territory of Delhi, India.

Graph: 9,607 nodes, 18,683 edges (Span: 49.3 km N-S x 47.6 km E-W)
Covers all districts: North, South, East, West, Central, Shahdara, Dwarka, Rohini.

Evaluates performance across 6 scale points:
  1. 20 Customers   | 4 Vehicles   | 1 Central Depot
  2. 50 Customers   | 5 Vehicles   | 1 Central Depot
  3. 100 Customers  | 10 Vehicles  | 1 Central Depot
  4. 200 Customers  | 20 Vehicles  | 1 Central Depot
  5. 500 Customers  | 25 Vehicles  | 1 Central Depot
  6. 1,000 Customers | 50 Vehicles  | 1 Central Depot

Saves:
  - CSV report: outputs/ga/delhi/full_delhi_benchmark_summary.csv
  - Performance Plot: outputs/ga/delhi/full_delhi_performance_comparison.png
  - Best Routes on Full City Map: outputs/ga/delhi/full_delhi_best_routes_map.png
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
    {"name": "20_cust",   "num_customers": 20,   "num_vehicles": 4,  "capacity": 20, "max_duration": 10800.0},
    {"name": "50_cust",   "num_customers": 50,   "num_vehicles": 5,  "capacity": 25, "max_duration": 14400.0},
    {"name": "100_cust",  "num_customers": 100,  "num_vehicles": 10, "capacity": 25, "max_duration": 18000.0},
    {"name": "200_cust",  "num_customers": 200,  "num_vehicles": 20, "capacity": 25, "max_duration": 21600.0},
    {"name": "500_cust",  "num_customers": 500,  "num_vehicles": 25, "capacity": 45, "max_duration": 28800.0},
    {"name": "1000_cust", "num_customers": 1000, "num_vehicles": 50, "capacity": 45, "max_duration": 36000.0},
]

POP_SIZE = 100
GENERATIONS = 200
SEED = 42

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "delhi")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "delhi")
GRAPHML_PATH = os.path.join(DATA_DIR, "full_delhi_road_network.graphml")

# -----------------------------------------------------------------------------
# Graph & Precomputation
# -----------------------------------------------------------------------------
def load_full_delhi_graph():
    if not os.path.exists(GRAPHML_PATH):
        raise FileNotFoundError(f"Full Delhi graph not found at: {GRAPHML_PATH}")
    print(f"[GRAPH] Loading Full Delhi Road Network from: {GRAPHML_PATH}...")
    G = ox.load_graphml(GRAPHML_PATH)
    print(f"[GRAPH] Loaded successfully: {len(G.nodes)} nodes, {len(G.edges)} edges\n")
    return G

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
# Quantum Qubit Operations & Algorithms
# -----------------------------------------------------------------------------
class QuantumQubitChromosome:
    def __init__(self, num_customers, theta=None):
        self.num_customers = num_customers
        self.theta = np.full(num_customers, math.pi / 4.0, dtype=np.float32) if theta is None else np.array(theta, dtype=np.float32)

    @property
    def beta(self):
        return np.sin(self.theta)

    def observe(self):
        probabilities = np.square(self.beta)
        quantum_measurement = probabilities + np.random.normal(0, 0.02, size=self.num_customers)
        return (np.argsort(quantum_measurement) + 1).tolist()

    def apply_rotation_gate(self, best_theta, gen, total_generations, step_size=0.05 * math.pi):
        decay = 1.0 - (gen / float(total_generations))
        dTheta = np.sign(best_theta - self.theta) * (step_size * decay)
        self.theta += dTheta
        self.theta = np.clip(self.theta, 0.01, (math.pi / 2.0) - 0.01)

    def apply_hadamard_mutation(self, prob=0.05):
        mask = np.random.random(size=self.num_customers) < prob
        self.theta[mask] = math.pi / 4.0

def generate_heuristic_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat):
    population = []
    cust_indices = list(range(1, num_customers + 1))
    num_random = int(pop_size * 0.20)
    num_greedy = int(pop_size * 0.20)
    num_nn = pop_size - num_random - num_greedy

    # 1. Random
    for _ in range(num_random):
        population.append(np.random.permutation(cust_indices).tolist())

    # 2. Greedy Sector
    depot_y, depot_x = G.nodes[depot_node]['y'], G.nodes[depot_node]['x']
    angles = [math.atan2(G.nodes[c]['y'] - depot_y, G.nodes[c]['x'] - depot_x) for c in customer_nodes]
    sector_sorted = [idx for _, idx in sorted(zip(angles, cust_indices))]
    for _ in range(num_greedy):
        ind = list(sector_sorted)
        if random.random() < 0.7:
            for _ in range(random.randint(1, max(2, num_customers // 10))):
                idx1, idx2 = random.sample(range(num_customers), 2)
                ind[idx1], ind[idx2] = ind[idx2], ind[idx1]
        population.append(ind)

    # 3. Nearest Neighbor
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
        population.append(nn_tour)

    return population

def run_hga(evaluator, num_customers, G, depot_node, customer_nodes, time_mat, pop_size=100, generations=200):
    t0 = time.time()
    population = generate_heuristic_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat)
    best_chrom = None
    best_fit, best_time, best_dist, best_violations = float("inf"), float("inf"), float("inf"), 0

    for gen in range(generations):
        evals = [evaluator.evaluate(ind) for ind in population]
        fitnesses = [e[0] for e in evals]
        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_chrom = population[min_idx]
            _, best_time, best_dist, best_violations = evals[min_idx]

        new_pop = [population[i] for i in np.argsort(fitnesses)[:2]]
        while len(new_pop) < pop_size:
            i1, i2 = random.sample(range(pop_size), 2)
            p1 = population[i1] if fitnesses[i1] < fitnesses[i2] else population[i2]
            i3, i4 = random.sample(range(pop_size), 2)
            p2 = population[i3] if fitnesses[i3] < fitnesses[i4] else population[i4]

            if random.random() < 0.85:
                cx1, cx2 = sorted(random.sample(range(len(p1)), 2))
                child = [-1] * len(p1)
                child[cx1:cx2] = p1[cx1:cx2]
                fill_vals = [item for item in p2 if item not in child[cx1:cx2]]
                fill_idx = 0
                for i in range(len(p1)):
                    if child[i] == -1:
                        child[i] = fill_vals[fill_idx]
                        fill_idx += 1
            else:
                child = list(p1)

            if random.random() < 0.25:
                m1, m2 = random.sample(range(len(child)), 2)
                child[m1], child[m2] = child[m2], child[m1]

            new_pop.append(child)
        population = new_pop

    runtime = time.time() - t0
    return best_chrom, best_time, best_dist / 1000.0, best_violations, runtime

def run_qhga(evaluator, num_customers, G, depot_node, customer_nodes, time_mat, pop_size=100, generations=200):
    t0 = time.time()
    h_pop = generate_heuristic_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat)
    q_population = []
    for p in h_pop:
        norm_vals = np.array(p, dtype=np.float32) / float(num_customers + 1)
        theta = np.arcsin(np.sqrt(norm_vals))
        q_population.append(QuantumQubitChromosome(num_customers, theta=theta))

    best_chrom = None
    best_q_theta = None
    best_fit, best_time, best_dist, best_violations = float("inf"), float("inf"), float("inf"), 0

    for gen in range(generations):
        observed = [q_ind.observe() for q_ind in q_population]
        evals = [evaluator.evaluate(p) for p in observed]
        fitnesses = [e[0] for e in evals]
        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_chrom = observed[min_idx]
            best_q_theta = np.copy(q_population[min_idx].theta)
            _, best_time, best_dist, best_violations = evals[min_idx]

        for q_ind in q_population:
            q_ind.apply_rotation_gate(best_q_theta, gen, generations)
            if random.random() < 0.2:
                q_ind.apply_hadamard_mutation()

    runtime = time.time() - t0
    return best_chrom, best_time, best_dist / 1000.0, best_violations, runtime

# -----------------------------------------------------------------------------
# Route Plotting on Full Delhi Road Network
# -----------------------------------------------------------------------------
def plot_routes_on_full_delhi(G, depot_node, customer_nodes, best_chrom, num_vehicles, scale_name):
    print(f"[PLOT] Rendering vehicle routes on Full Delhi Road Network ({scale_name})...")
    routes = np.array_split(best_chrom, num_vehicles)
    
    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=False,
        node_size=1.5,
        node_color="#bdc3c7",
        edge_color="#7f8c8d",
        edge_linewidth=0.4,
        edge_alpha=0.6,
        bgcolor="#ffffff"
    )

    depot_x, depot_y = G.nodes[depot_node]['x'], G.nodes[depot_node]['y']
    ax.scatter([depot_x], [depot_y], c="#e74c3c", s=140, marker="*", zorder=6, label="Central Depot (Connaught Place/ISBT)")

    # Color palette for vehicle routes
    colors = [plt.cm.tab20(i % 20) for i in range(num_vehicles)]

    all_cust_nodes = [customer_nodes[c - 1] for c in best_chrom]
    cust_xs = [G.nodes[n]['x'] for n in all_cust_nodes]
    cust_ys = [G.nodes[n]['y'] for n in all_cust_nodes]
    ax.scatter(cust_xs, cust_ys, c="#2980b9", s=25, zorder=5, alpha=0.85, label="Customers")

    # Connect routes
    for v_idx, r in enumerate(routes):
        if len(r) == 0: continue
        route_nodes = [depot_node] + [customer_nodes[c - 1] for c in r] + [depot_node]
        r_xs = [G.nodes[n]['x'] for n in route_nodes]
        r_ys = [G.nodes[n]['y'] for n in route_nodes]
        ax.plot(r_xs, r_ys, color=colors[v_idx % len(colors)], linewidth=1.8, alpha=0.85, zorder=4)

    ax.set_title(f"Full Delhi City VRP Route Map ({scale_name} - {len(customer_nodes)} Customers, {num_vehicles} Vehicles)", fontsize=13, fontweight="bold", pad=10)
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()

    out_path = os.path.join(OUTPUT_DIR, f"full_delhi_{scale_name}_routes_map.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[PLOT] Saved route map: {out_path}")

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 82)
    print("      FULL DELHI CITY ROAD NETWORK VRP BENCHMARK")
    print("=" * 82)

    G = load_full_delhi_graph()

    # Pick a Central Depot Node (highest degree central node in core Delhi)
    degrees = dict(G.degree())
    depot_node = max(degrees.keys(), key=lambda n: degrees[n])
    depot_x, depot_y = G.nodes[depot_node]['x'], G.nodes[depot_node]['y']
    print(f"Selected Central Depot Node: {depot_node} (Lat: {depot_y:.4f}° N, Lon: {depot_x:.4f}° E, Degree: {degrees[depot_node]})")

    candidate_nodes = [n for n in G.nodes() if n != depot_node]
    results = []

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print("\n" + "-" * 82)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | Full Delhi NCT Map")
        print("-" * 82)

        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        print(f"  [Dijkstra] Computing shortest path matrix for {num_cust + 1} locations on 9,607-node graph...")
        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)

        evaluator = FastSingleDepotEvaluator(time_mat, dist_mat, demands, num_veh, capacity, max_duration)

        # Run H-GA
        print(f"  [H-GA] Running Heuristic GA over {GENERATIONS} generations...")
        h_chrom, h_time_s, h_dist_km, h_viol, h_runtime = run_hga(
            evaluator, num_cust, G, depot_node, customer_nodes, time_mat, POP_SIZE, GENERATIONS
        )

        # Run Q-HGA
        print(f"  [Q-HGA] Running Quantum-Inspired Heuristic GA over {GENERATIONS} generations...")
        q_chrom, q_time_s, q_dist_km, q_viol, q_runtime = run_qhga(
            evaluator, num_cust, G, depot_node, customer_nodes, time_mat, POP_SIZE, GENERATIONS
        )

        print(f"  --> H-GA   : Distance = {h_dist_km:.2f} km | Runtime = {h_runtime:.2f}s | Violations = {h_viol}")
        print(f"  --> Q-HGA  : Distance = {q_dist_km:.2f} km | Runtime = {q_runtime:.2f}s | Violations = {q_viol}")
        print(f"  --> Dijkstra Precompute Time: {dijkstra_time:.2f} s")

        # Plot routes for best solution at this scale
        best_chrom = h_chrom if h_dist_km <= q_dist_km else q_chrom
        plot_routes_on_full_delhi(G, depot_node, customer_nodes, best_chrom, num_veh, scale_name)

        results.append({
            "scale_name": scale_name,
            "num_customers": num_cust,
            "num_vehicles": num_veh,
            "dijkstra_time_s": round(dijkstra_time, 2),
            "hga_distance_km": round(h_dist_km, 2),
            "hga_runtime_s": round(h_runtime, 2),
            "hga_violations": int(h_viol),
            "qhga_distance_km": round(q_dist_km, 2),
            "qhga_runtime_s": round(q_runtime, 2),
            "qhga_violations": int(q_viol),
            "total_hga_runtime_s": round(dijkstra_time + h_runtime, 2),
            "total_qhga_runtime_s": round(dijkstra_time + q_runtime, 2)
        })

    # Save summary CSV
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "full_delhi_benchmark_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Full Delhi benchmark summary saved to: {csv_path}")

    # Plot Comparison Charts
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Full Delhi City VRP Benchmark: H-GA vs Q-HGA Performance", fontsize=14, fontweight="bold")

    cust_labels = [f"{r['num_customers']} Cust\n({r['num_vehicles']} Veh)" for r in results]

    # Panel 1: Route Distance Comparison
    ax1 = axes[0, 0]
    ax1.plot(cust_labels, df["hga_distance_km"], marker="s", color="#3498db", linewidth=2.5, label="Heuristic GA (H-GA)")
    ax1.plot(cust_labels, df["qhga_distance_km"], marker="^", color="#2ecc71", linewidth=2.5, label="Quantum Heuristic GA (Q-HGA)")
    ax1.set_ylabel("Total Distance (km)")
    ax1.set_title("Route Distance across Full Delhi Map (Lower is Better)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: GA Execution Speed (Runtime)
    ax2 = axes[0, 1]
    ax2.plot(cust_labels, df["hga_runtime_s"], marker="s", color="#3498db", linewidth=2.0, label="H-GA Evolution Time (s)")
    ax2.plot(cust_labels, df["qhga_runtime_s"], marker="^", color="#2ecc71", linewidth=2.0, label="Q-HGA Evolution Time (s)")
    ax2.set_ylabel("Time (seconds)")
    ax2.set_title("Algorithm Evolution Runtime (200 Generations)")
    ax2.legend()
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Panel 3: Precomputation vs Evolution Runtime
    ax3 = axes[1, 0]
    ax3.bar(cust_labels, df["dijkstra_time_s"], label="Dijkstra Shortest Path Precompute (s)", color="#34495e")
    ax3.bar(cust_labels, df["hga_runtime_s"], bottom=df["dijkstra_time_s"], label="H-GA Runtime (s)", color="#3498db")
    ax3.set_ylabel("Time (seconds)")
    ax3.set_title("Total Execution Runtime Breakdown")
    ax3.legend()
    ax3.grid(True, linestyle="--", alpha=0.5)

    # Panel 4: Violations
    ax4 = axes[1, 1]
    ax4.bar(cust_labels, df["hga_violations"], color="#3498db", width=0.4, label="H-GA Violations", align="center")
    ax4.set_ylabel("Violation Count")
    ax4.set_title("Constraint Violations across Problem Scales")
    ax4.legend()
    ax4.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    comp_plot_path = os.path.join(OUTPUT_DIR, "full_delhi_performance_comparison.png")
    fig.savefig(comp_plot_path, dpi=300)
    plt.close(fig)
    print(f"[VISUALIZATION] Comparison charts saved to: {comp_plot_path}")

    print("=" * 82)
    print("      FULL DELHI ROAD NETWORK VRP BENCHMARK COMPLETE!")
    print("=" * 82)

if __name__ == "__main__":
    main()
