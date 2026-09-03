"""
population_distribution_experiment.py

Systematic Population Initialization Ratio Experiment for Single-Depot VRP GA.
Compares 5 Population Ratios (Random : Greedy Sector : Nearest Neighbor):
  - Ratio A (Balanced 34/33/33) : 34% Random | 33% Greedy | 33% NN
  - Ratio B (Heuristic Heavy 10/45/45) : 10% Random | 45% Greedy | 45% NN
  - Ratio C (Greedy Heavy 20/60/20)    : 20% Random | 60% Greedy | 20% NN
  - Ratio D (NN Heavy 20/20/60)        : 20% Random | 20% Greedy | 60% NN
  - Ratio E (Exploratory 60/20/20)     : 60% Random | 20% Greedy | 20% NN

Saves outputs to:
  - CSV report: outputs/ga/population_distribution/distribution_experiment_summary.csv
  - Visualizations: outputs/ga/population_distribution/distribution_comparison.png
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
# Test Scale Points & Distribution Ratios
# -----------------------------------------------------------------------------
RATIOS = [
    {"name": "Balanced (34/33/33)",      "rand_pct": 0.34, "greedy_pct": 0.33, "nn_pct": 0.33},
    {"name": "Heuristic Heavy (10/45/45)", "rand_pct": 0.10, "greedy_pct": 0.45, "nn_pct": 0.45},
    {"name": "Greedy Heavy (20/60/20)",    "rand_pct": 0.20, "greedy_pct": 0.60, "nn_pct": 0.20},
    {"name": "NN Heavy (20/20/60)",        "rand_pct": 0.20, "greedy_pct": 0.20, "nn_pct": 0.60},
    {"name": "Exploratory (60/20/20)",     "rand_pct": 0.60, "greedy_pct": 0.20, "nn_pct": 0.20},
]

BENCHMARK_SCALES = [
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

OUTPUT_DIR = os.path.join("outputs", "ga", "population_distribution")

# -----------------------------------------------------------------------------
# Graph & Distance Matrix Helper Functions
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
# Vectorized Evaluator
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
# Population Generator using Parameterized Ratio
# -----------------------------------------------------------------------------
def generate_ratio_population(pop_size, num_customers, G, depot_node, customer_nodes, time_mat, rand_pct, greedy_pct, nn_pct):
    population = []
    cust_indices = list(range(1, num_customers + 1))

    num_random = int(pop_size * rand_pct)
    num_greedy = int(pop_size * greedy_pct)
    num_nn = pop_size - num_random - num_greedy

    # 1. Random Individuals
    for _ in range(num_random):
        population.append(np.random.permutation(cust_indices).tolist())

    # 2. Greedy Sector Sweeping
    depot_y = G.nodes[depot_node]['y']
    depot_x = G.nodes[depot_node]['x']
    angles = [math.atan2(G.nodes[c]['y'] - depot_y, G.nodes[c]['x'] - depot_x) for c in customer_nodes]
    sector_sorted = [idx for _, idx in sorted(zip(angles, cust_indices))]

    for _ in range(num_greedy):
        ind = list(sector_sorted)
        if random.random() < 0.7:
            for _ in range(random.randint(1, max(2, num_customers // 10))):
                idx1, idx2 = random.sample(range(num_customers), 2)
                ind[idx1], ind[idx2] = ind[idx2], ind[idx1]
        population.append(ind)

    # 3. Nearest Neighbor Tours
    for i in range(num_nn):
        unvisited = set(cust_indices)
        curr = 0 if i == 0 else random.choice(cust_indices)
        if curr != 0:
            unvisited.remove(curr)
        nn_tour = [] if curr == 0 else [curr]

        while unvisited:
            next_cust = min(unvisited, key=lambda c: time_mat[curr, c])
            nn_tour.append(next_cust)
            unvisited.remove(next_cust)
            curr = next_cust

        population.append(nn_tour)

    return population

# -----------------------------------------------------------------------------
# GA Engine for Ratio Testing
# -----------------------------------------------------------------------------
def run_ga_with_ratio(evaluator, num_customers, G, depot_node, customer_nodes, time_mat, ratio_config, pop_size=100, generations=200):
    t0 = time.time()

    population = generate_ratio_population(
        pop_size, num_customers, G, depot_node, customer_nodes, time_mat,
        ratio_config["rand_pct"], ratio_config["greedy_pct"], ratio_config["nn_pct"]
    )

    # Measure Gen 0 fitness
    evals_g0 = [evaluator.evaluate(ind) for ind in population]
    g0_best_dist = min([e[2] for e in evals_g0]) / 1000.0
    g0_avg_dist = np.mean([e[2] for e in evals_g0]) / 1000.0

    best_chrom = None
    best_fit = float("inf")
    best_time = float("inf")
    best_dist = float("inf")
    best_violations = 0

    for gen in range(generations):
        evals = [evaluator.evaluate(ind) for ind in population]
        fitnesses = [e[0] for e in evals]

        min_idx = np.argmin(fitnesses)
        if fitnesses[min_idx] < best_fit:
            best_fit = fitnesses[min_idx]
            best_chrom = population[min_idx]
            _, best_time, best_dist, best_violations = evals[min_idx]

        new_pop = []
        sorted_indices = np.argsort(fitnesses)
        for e_idx in range(ELITISM):
            new_pop.append(population[sorted_indices[e_idx]])

        while len(new_pop) < pop_size:
            i1, i2 = random.sample(range(pop_size), 2)
            parent1 = population[i1] if fitnesses[i1] < fitnesses[i2] else population[i2]
            
            i3, i4 = random.sample(range(pop_size), 2)
            parent2 = population[i3] if fitnesses[i3] < fitnesses[i4] else population[i4]

            # OX Crossover
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
    best_dist_km = best_dist / 1000.0
    return g0_best_dist, g0_avg_dist, best_dist_km, best_time, best_violations, ga_time

# -----------------------------------------------------------------------------
# Main Experiment Execution
# -----------------------------------------------------------------------------
def main():
    random.seed(SEED)
    np.random.seed(SEED)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 80)
    print("   POPULATION INITIALIZATION RATIO EXPERIMENT (Random vs Greedy vs NN)")
    print("=" * 80)

    G = load_road_graph()
    annotate_graph_edges(G)

    node_degrees = dict(G.degree())
    depot_node = max(node_degrees.keys(), key=lambda n: node_degrees[n])
    candidate_nodes = [n for n in G.nodes() if n != depot_node]

    results = []

    for scale in BENCHMARK_SCALES:
        scale_name = scale["name"]
        num_cust = scale["num_customers"]
        num_veh = scale["num_vehicles"]
        capacity = scale["capacity"]
        max_duration = scale["max_duration"]

        print(f"\n" + "-" * 80)
        print(f"  SCALE: {num_cust} Customers | {num_veh} Vehicles | 1 Depot")
        print(f"-" * 80)

        customer_nodes = random.sample(candidate_nodes, num_cust)
        demands = [random.randint(1, 4) for _ in range(num_cust)]

        time_mat, dist_mat, dijkstra_time = precompute_matrices(G, depot_node, customer_nodes)
        evaluator = FastSingleDepotEvaluator(time_mat, dist_mat, demands, num_veh, capacity, max_duration)

        for ratio in RATIOS:
            ratio_name = ratio["name"]
            print(f"  [Testing Ratio] {ratio_name}...")

            g0_best_km, g0_avg_km, final_best_km, best_time_s, violations, ga_time = run_ga_with_ratio(
                evaluator, num_cust, G, depot_node, customer_nodes, time_mat, ratio, POP_SIZE, GENERATIONS
            )

            print(f"    -> Gen 0 Best: {g0_best_km:.2f} km | Gen 200 Best: {final_best_km:.2f} km | Violations: {violations}")

            results.append({
                "scale_name": scale_name,
                "num_customers": num_cust,
                "num_vehicles": num_veh,
                "ratio_name": ratio_name,
                "rand_pct": ratio["rand_pct"],
                "greedy_pct": ratio["greedy_pct"],
                "nn_pct": ratio["nn_pct"],
                "gen0_best_km": round(g0_best_km, 2),
                "gen0_avg_km": round(g0_avg_km, 2),
                "gen200_best_km": round(final_best_km, 2),
                "best_time_s": round(best_time_s, 1),
                "ga_time_s": round(ga_time, 2),
                "violations": int(violations),
                "is_valid": (violations == 0)
            })

    # Save Results CSV
    df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "distribution_experiment_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVE] Experiment summary saved to: {csv_path}")

    # Plot Distribution Comparison
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Comparison of Population Initialization Ratios (Random : Greedy : NN)", fontsize=13, fontweight="bold")

    pivot_final = df.pivot(index="num_customers", columns="ratio_name", values="gen200_best_km")
    pivot_g0 = df.pivot(index="num_customers", columns="ratio_name", values="gen0_best_km")

    # Panel 1: Final Gen 200 Best Distance across Scale
    pivot_final.plot(kind="line", marker="o", ax=axes[0, 0], linewidth=2)
    axes[0, 0].set_ylabel("Best Distance at Gen 200 (km)")
    axes[0, 0].set_title("Final Solution Quality by Ratio (Lower is Better)")
    axes[0, 0].grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Gen 0 Starting Quality
    pivot_g0.plot(kind="line", marker="s", ax=axes[0, 1], linewidth=2)
    axes[0, 1].set_ylabel("Gen 0 Best Distance (km)")
    axes[0, 1].set_title("Initial Starting Fitness at Gen 0")
    axes[0, 1].grid(True, linestyle="--", alpha=0.5)

    # Panel 3: Bar Chart of Distance at 1000 Customers
    df_1000 = df[df["num_customers"] == 1000]
    bars = axes[1, 0].bar(df_1000["ratio_name"], df_1000["gen200_best_km"], color="#3498db")
    axes[1, 0].set_ylabel("Distance at 1,000 Customers (km)")
    axes[1, 0].set_title("1,000 Customer Scalability Performance")
    plt.setp(axes[1, 0].get_xticklabels(), rotation=25, ha="right", fontsize=8)
    for bar in bars:
        yval = bar.get_height()
        axes[1, 0].text(bar.get_x() + bar.get_width()/2.0, yval + 10, f"{yval:.1f}km", ha="center", va="bottom", fontsize=8)

    # Panel 4: Distance Optimization Gain (% Improvement over Balanced)
    balanced_dist = df[df["ratio_name"] == "Balanced (34/33/33)"].set_index("num_customers")["gen200_best_km"]
    df["balanced_ref"] = df["num_customers"].map(balanced_dist)
    df["pct_gain"] = ((df["balanced_ref"] - df["gen200_best_km"]) / df["balanced_ref"]) * 100.0
    pivot_gain = df.pivot(index="num_customers", columns="ratio_name", values="pct_gain")
    
    pivot_gain.plot(kind="bar", ax=axes[1, 1], width=0.8)
    axes[1, 1].set_ylabel("Relative Gain (%) vs Balanced")
    axes[1, 1].set_title("Performance Gain vs Balanced Baseline")
    axes[1, 1].axhline(0, color="black", linewidth=1)
    axes[1, 1].grid(True, linestyle="--", alpha=0.5)
    plt.setp(axes[1, 1].get_xticklabels(), rotation=0)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = os.path.join(OUTPUT_DIR, "distribution_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"[VISUALIZATION] Comparison plots saved to: {plot_path}")
    print("=" * 80)
    print("   POPULATION INITIALIZATION EXPERIMENT COMPLETE!")
    print("=" * 80)

if __name__ == "__main__":
    main()
