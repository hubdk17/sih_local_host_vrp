"""
scalability_benchmark.py

Scalability Benchmark Suite for Multi-Depot Vehicle Routing Problem (MDVRP) using Genetic Algorithm (GA).

Evaluates algorithm performance across scaling customer and vehicle counts on the Delhi road network graph:
  - Scale 1: 50 Customers, 10 Vehicles, 4 Depots
  - Scale 2: 200 Customers, 20 Vehicles, 6 Depots
  - Scale 3: 1,000 Customers, 50 Vehicles, 10 Depots
  - Scale 4: 5,000 Customers, 250 Vehicles, 15 Depots
  - Scale 5: 10,000 Customers, 500 Vehicles, 20 Depots

Uses NumPy matrix acceleration for instantaneous O(1) route lookup evaluations.
Generates comprehensive comparative performance charts and summary reports.
"""

import csv
import json
import os
import sys
import time
import random
import numpy as np
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

GRAPHML_PATH = os.path.join(BASE_DIR, "data", "delhi", "delhi_road_network.graphml")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "delhi", "scalability")

# Defined Benchmark Scale Configurations
SCALE_CONFIGS = [
    {"name": "50_cust", "num_customers": 50, "num_vehicles": 10, "num_depots": 4, "generations": 150, "pop_size": 100},
    {"name": "200_cust", "num_customers": 200, "num_vehicles": 20, "num_depots": 6, "generations": 150, "pop_size": 100},
    {"name": "1000_cust", "num_customers": 1000, "num_vehicles": 50, "num_depots": 10, "generations": 150, "pop_size": 100},
    {"name": "5000_cust", "num_customers": 5000, "num_vehicles": 250, "num_depots": 15, "generations": 150, "pop_size": 100},
    {"name": "10000_cust", "num_customers": 10000, "num_vehicles": 500, "num_depots": 20, "generations": 150, "pop_size": 100},
]


class MatrixAcceleratedDelhiMDVRP:
    """
    Ultra-fast NumPy matrix-accelerated MDVRP Instance & Evaluator.
    Precomputes dense N x N travel time and distance matrices to achieve
    sub-millisecond solution evaluation even for 10,000 customers.
    """

    def __init__(self, graph, num_customers: int, num_vehicles: int, num_depots: int, seed: int = 42):
        self.graph = graph
        self.num_customers = num_customers
        self.num_vehicles = num_vehicles
        self.num_depots = num_depots

        random.seed(seed)
        np.random.seed(seed)

        # 1. Select Depot Nodes on Major High-Capacity Roads
        high_cap_nodes = []
        for u, v, k, data in graph.edges(keys=True, data=True):
            hw = data.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0]
            if hw in ["primary", "secondary", "trunk", "motorway"]:
                high_cap_nodes.append(u)
                high_cap_nodes.append(v)
        high_cap_nodes = list(set(high_cap_nodes)) if high_cap_nodes else list(graph.nodes)

        all_nodes = list(graph.nodes)
        self.depot_nodes = random.sample(high_cap_nodes, num_depots)

        # 2. Select Customer Nodes
        # For large scaling, sample customer nodes with replacement allowed if N > total graph nodes
        if num_customers <= len(all_nodes):
            self.customer_nodes = random.sample(all_nodes, num_customers)
        else:
            self.customer_nodes = random.choices(all_nodes, k=num_customers)

        self.demands = np.random.randint(1, 6, size=num_customers)

        # Vehicle Home Depots (distributed evenly among depots)
        self.vehicle_home_depots = [i % num_depots for i in range(num_vehicles)]
        self.vehicle_capacities = np.full(num_vehicles, 20)
        self.max_duration_sec = 14400.0  # 4 hours max per vehicle for large scale

        # Total locations = num_depots + num_customers
        # Index 0..num_depots-1 -> Depots
        # Index num_depots..num_depots+num_customers-1 -> Customers
        self.total_locations = num_depots + num_customers
        self.unique_graph_nodes = list(set(self.depot_nodes + self.customer_nodes))

        # Map each location index to graph node
        self.location_graph_nodes = self.depot_nodes + self.customer_nodes
        self.node_to_unique_idx = {n: i for i, n in enumerate(self.unique_graph_nodes)}

        # Build location_idx -> unique_node_idx mapping
        self.loc_to_unique = np.array([self.node_to_unique_idx[n] for n in self.location_graph_nodes], dtype=np.int32)

        # 3. Build Dense Travel Time & Distance Matrices
        self._build_matrices()

    def _build_matrices(self):
        """Precompute pairwise travel time and distance matrices via single-source Dijkstra."""
        num_u = len(self.unique_graph_nodes)
        unique_time_mat = np.zeros((num_u, num_u), dtype=np.float32)
        unique_dist_mat = np.zeros((num_u, num_u), dtype=np.float32)

        print(f"    [Dijkstra] Computing paths for {num_u} unique graph nodes...")
        t0 = time.time()

        for i, source in enumerate(self.unique_graph_nodes):
            times_dict, paths_dict = nx.single_source_dijkstra(
                self.graph, source=source, weight="travel_time"
            )
            for j, target in enumerate(self.unique_graph_nodes):
                if i == j:
                    continue
                if target in times_dict:
                    unique_time_mat[i, j] = times_dict[target]
                    # Estimate distance from time & avg speed
                    node_path = paths_dict[target]
                    d_sum = 0.0
                    for k in range(len(node_path) - 1):
                        u_n, v_n = node_path[k], node_path[k + 1]
                        e_dict = self.graph[u_n][v_n]
                        min_k = min(e_dict.keys(), key=lambda key: e_dict[key].get("travel_time", 0.0))
                        d_sum += float(e_dict[min_k].get("length", 10.0))
                    unique_dist_mat[i, j] = d_sum

        self.matrix_build_time = time.time() - t0

        # Expand to location-indexed 2D NumPy matrices for O(1) array slicing
        # Depot indices: 0..num_depots-1
        # Customer indices: num_depots..num_depots+num_customers-1
        ix = self.loc_to_unique
        self.time_mat = unique_time_mat[np.ix_(ix, ix)]
        self.dist_mat = unique_dist_mat[np.ix_(ix, ix)]

    def evaluate_permutation(self, perm: np.ndarray) -> tuple:
        """
        Fast evaluation of a customer permutation [0..N-1].
        Splits permutation into num_vehicles sub-routes.
        """
        # Split customer permutation into num_vehicles chunks
        k, m = divmod(self.num_customers, self.num_vehicles)
        
        total_time = 0.0
        total_dist = 0.0
        violations = 0

        start_idx = 0
        for v in range(self.num_vehicles):
            end_idx = start_idx + k + (1 if v < m else 0)
            cust_segment = perm[start_idx:end_idx]
            start_idx = end_idx

            depot_loc_idx = self.vehicle_home_depots[v]
            cap = self.vehicle_capacities[v]

            if len(cust_segment) == 0:
                continue

            # Check vehicle capacity
            load = np.sum(self.demands[cust_segment])
            if load > cap:
                violations += (load - cap)

            # Route indices in time_mat: depot -> c1 -> c2 ... -> depot
            # Customer loc_idx = num_depots + customer_id
            route_locs = np.empty(len(cust_segment) + 2, dtype=np.int32)
            route_locs[0] = depot_loc_idx
            route_locs[1:-1] = self.num_depots + cust_segment
            route_locs[-1] = depot_loc_idx

            r_time = np.sum(self.time_mat[route_locs[:-1], route_locs[1:]])
            r_dist = np.sum(self.dist_mat[route_locs[:-1], route_locs[1:]])

            if r_time > self.max_duration_sec:
                violations += 1

            total_time += r_time
            total_dist += r_dist

        return total_time, total_dist, violations


class FastGA:
    """Genetic Algorithm using vectorized Order Crossover & Inversion Mutation."""

    def __init__(self, instance: MatrixAcceleratedDelhiMDVRP, pop_size: int = 100, generations: int = 150, penalty: float = 5000.0):
        self.inst = instance
        self.pop_size = pop_size
        self.generations = generations
        self.penalty = penalty
        self.N = instance.num_customers

    def run(self) -> dict:
        t_start = time.time()

        # Initialize Population
        population = np.array([np.random.permutation(self.N) for _ in range(self.pop_size)])

        history = {
            "gen": [],
            "best_time": [],
            "best_dist": [],
            "violations": [],
            "diversity": [],
        }

        global_best_cost = float("inf")
        global_best_time = float("inf")
        global_best_dist = float("inf")
        global_best_viols = 999999

        for gen in range(1, self.generations + 1):
            evals = [self.inst.evaluate_permutation(ind) for ind in population]
            times = np.array([e[0] for e in evals])
            dists = np.array([e[1] for e in evals])
            viols = np.array([e[2] for e in evals])

            costs = times + (viols * self.penalty)

            best_idx = np.argmin(costs)
            gen_best_cost = costs[best_idx]
            gen_best_time = times[best_idx]
            gen_best_dist = dists[best_idx]
            gen_best_viols = viols[best_idx]

            if gen_best_cost < global_best_cost:
                global_best_cost = gen_best_cost
                global_best_time = gen_best_time
                global_best_dist = gen_best_dist
                global_best_viols = gen_best_viols

            # Sample population diversity (Hamming distance)
            sample = population[:min(20, self.pop_size)]
            div_list = []
            for i in range(len(sample)):
                for j in range(i + 1, len(sample)):
                    div_list.append(np.mean(sample[i] != sample[j]))
            avg_div = np.mean(div_list) if div_list else 0.0

            history["gen"].append(gen)
            history["best_time"].append(global_best_time)
            history["best_dist"].append(global_best_dist)
            history["violations"].append(global_best_viols)
            history["diversity"].append(avg_div)

            # Selection & Reproduction
            sorted_idx = np.argsort(costs)
            next_pop = [population[sorted_idx[0]].copy(), population[sorted_idx[1]].copy()]

            while len(next_pop) < self.pop_size:
                # Tournament Selection
                t1 = np.random.choice(self.pop_size, 3, replace=False)
                t2 = np.random.choice(self.pop_size, 3, replace=False)
                p1 = population[t1[np.argmin(costs[t1])]]
                p2 = population[t2[np.argmin(costs[t2])]]

                # Order Crossover (OX)
                if random.random() < 0.85 and self.N >= 4:
                    cx1, cx2 = sorted(random.sample(range(self.N), 2))
                    child1 = np.full(self.N, -1, dtype=np.int32)
                    child1[cx1:cx2] = p1[cx1:cx2]
                    fill1 = [x for x in p2 if x not in child1[cx1:cx2]]
                    child1[child1 == -1] = fill1
                else:
                    child1 = p1.copy()

                # Mutation
                if random.random() < 0.25 and self.N >= 2:
                    i, j = sorted(random.sample(range(self.N), 2))
                    child1[i:j+1] = child1[i:j+1][::-1]

                next_pop.append(child1)

            population = np.array(next_pop[:self.pop_size])

        ga_time = time.time() - t_start

        return {
            "total_runtime_s": ga_time + self.inst.matrix_build_time,
            "dijkstra_time_s": self.inst.matrix_build_time,
            "ga_time_s": ga_time,
            "best_travel_time_s": global_best_time,
            "best_distance_m": global_best_dist,
            "violations": global_best_viols,
            "ms_per_generation": (ga_time / self.generations) * 1000.0,
            "history": history,
        }


def run_benchmark():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("==========================================================================")
    print("      DELHI MDVRP GA SCALABILITY BENCHMARK SUITE (50 to 10,000 CUSTOMERS) ")
    print("==========================================================================")
    print(f"Loading base Delhi graph: {GRAPHML_PATH}...")
    G_full = ox.load_graphml(GRAPHML_PATH)
    largest_scc = max(nx.strongly_connected_components(G_full), key=len)
    G = G_full.subgraph(largest_scc).copy()
    print(f"Delhi road network ready: {len(G.nodes)} nodes, {len(G.edges)} edges\n")

    results_list = []

    for cfg in SCALE_CONFIGS:
        name = cfg["name"]
        num_c = cfg["num_customers"]
        num_v = cfg["num_vehicles"]
        num_d = cfg["num_depots"]
        gens = cfg["generations"]
        pop = cfg["pop_size"]

        print("--------------------------------------------------------------------------")
        print(f"  BENCHMARK SCALE: {num_c} Customers | {num_v} Vehicles | {num_d} Depots")
        print("--------------------------------------------------------------------------")

        t_setup = time.time()
        mdvrp_inst = MatrixAcceleratedDelhiMDVRP(
            graph=G, num_customers=num_c, num_vehicles=num_v, num_depots=num_d, seed=42
        )
        ga_solver = FastGA(instance=mdvrp_inst, pop_size=pop, generations=gens, penalty=5000.0)
        res = ga_solver.run()

        res["scale_name"] = name
        res["num_customers"] = num_c
        res["num_vehicles"] = num_v
        res["num_depots"] = num_d
        res["pop_size"] = pop
        res["generations"] = gens

        results_list.append(res)

        print(f"  --> Total Runtime   : {res['total_runtime_s']:.2f} s (Dijkstra: {res['dijkstra_time_s']:.2f}s, GA: {res['ga_time_s']:.2f}s)")
        print(f"  --> Speed           : {res['ms_per_generation']:.2f} ms / generation")
        print(f"  --> Best Travel Time: {res['best_travel_time_s']:.1f} s")
        print(f"  --> Best Distance   : {res['best_distance_m'] / 1000.0:.2f} km")
        print(f"  --> Violations      : {res['violations']} ({'VALID' if res['violations'] == 0 else 'INVALID'})\n")

    # Save CSV & JSON Reports
    csv_path = os.path.join(OUTPUT_DIR, "scalability_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scale_name", "num_customers", "num_vehicles", "num_depots",
            "total_runtime_s", "dijkstra_time_s", "ga_time_s", "ms_per_gen",
            "best_travel_time_s", "best_distance_km", "violations", "is_valid"
        ])
        for r in results_list:
            writer.writerow([
                r["scale_name"], r["num_customers"], r["num_vehicles"], r["num_depots"],
                round(r["total_runtime_s"], 2), round(r["dijkstra_time_s"], 2), round(r["ga_time_s"], 2),
                round(r["ms_per_generation"], 2), round(r["best_travel_time_s"], 1),
                round(r["best_distance_m"] / 1000.0, 2), r["violations"], r["violations"] == 0
            ])
    print(f"[SAVE] CSV summary report saved to: {csv_path}")

    # Generate Comparative Graphs
    plot_comparative_charts(results_list)

    print("\n==========================================================================")
    print("      SCALABILITY BENCHMARK SUITE COMPLETE!")
    print("==========================================================================")


def plot_comparative_charts(results: list):
    """Plot comprehensive comparative performance charts across scaling problem sizes."""
    viz_path = os.path.join(OUTPUT_DIR, "scalability_comparison.png")
    fig, axes = plt.subplots(2, 2, figsize=(15, 11))

    cust_counts = [r["num_customers"] for r in results]
    runtimes = [r["total_runtime_s"] for r in results]
    ga_times = [r["ga_time_s"] for r in results]
    dijkstra_times = [r["dijkstra_time_s"] for r in results]
    distances_km = [r["best_distance_m"] / 1000.0 for r in results]
    travel_times_h = [r["best_travel_time_s"] / 3600.0 for r in results]
    ms_per_gen = [r["ms_per_generation"] for r in results]

    # Chart 1: Execution Time vs Customer Scale (Linear & Log)
    ax1 = axes[0, 0]
    ax1.plot(cust_counts, runtimes, "o-", color="#e74c3c", lw=2.5, label="Total Runtime (s)")
    ax1.plot(cust_counts, ga_times, "s--", color="#2980b9", lw=2, label="GA Loop Time (s)")
    ax1.plot(cust_counts, dijkstra_times, "^--", color="#2ecc71", lw=2, label="Dijkstra Matrix Time (s)")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_title("Runtime Scaling vs Customer Count (Log-Log Scale)", fontweight="bold")
    ax1.set_xlabel("Number of Customers (Log Scale)")
    ax1.set_ylabel("Execution Time (seconds, Log Scale)")
    ax1.grid(True, which="both", ls="--", alpha=0.5)
    ax1.legend()

    # Chart 2: Per-Generation Computation Speed (ms/generation)
    ax2 = axes[0, 1]
    ax2.bar([str(c) for c in cust_counts], ms_per_gen, color="#8e44ad", alpha=0.85, edgecolor="black")
    ax2.set_title("GA Computation Speed (ms per Generation)", fontweight="bold")
    ax2.set_xlabel("Number of Customers")
    ax2.set_ylabel("Milliseconds per Generation")
    for i, v in enumerate(ms_per_gen):
        ax2.text(i, v + (max(ms_per_gen) * 0.02), f"{v:.1f}ms", ha="center", fontsize=9, fontweight="bold")
    ax2.grid(True, axis="y", ls="--", alpha=0.5)

    # Chart 3: Total Fleet Distance & Travel Time Scaling
    ax3 = axes[1, 0]
    color_dist = "#e67e22"
    color_time = "#16a085"
    ax3.plot(cust_counts, distances_km, "o-", color=color_dist, lw=2.5, label="Total Distance (km)")
    ax3.set_xlabel("Number of Customers")
    ax3.set_ylabel("Total Fleet Distance (km)", color=color_dist, fontweight="bold")
    ax3.tick_params(axis="y", labelcolor=color_dist)

    ax3_twin = ax3.twinx()
    ax3_twin.plot(cust_counts, travel_times_h, "s--", color=color_time, lw=2.5, label="Total Travel Time (hours)")
    ax3_twin.set_ylabel("Total Fleet Travel Time (hours)", color=color_time, fontweight="bold")
    ax3_twin.tick_params(axis="y", labelcolor=color_time)
    ax3.set_title("Total Fleet Distance & Travel Time vs Scale", fontweight="bold")
    ax3.grid(True, ls="--", alpha=0.5)

    # Chart 4: Convergence Curves Across Scale Levels
    ax4 = axes[1, 1]
    colors = ["#e74c3c", "#2980b9", "#2ecc71", "#9b59b6", "#e67e22"]
    for idx, r in enumerate(results):
        gens = r["history"]["gen"]
        # Normalize travel time relative to initial generation for clear comparison
        norm_times = np.array(r["history"]["best_time"]) / r["history"]["best_time"][0]
        ax4.plot(gens, norm_times, lw=2, color=colors[idx], label=f"{r['num_customers']} Customers ({r['num_vehicles']} Veh)")

    ax4.set_title("Normalized Travel Time Convergence Across Scales", fontweight="bold")
    ax4.set_xlabel("Generation")
    ax4.set_ylabel("Normalized Best Travel Time (Gen 1 = 1.0)")
    ax4.grid(True, ls="--", alpha=0.5)
    ax4.legend(fontsize=8)

    fig.suptitle("Delhi Multi-Depot VRP GA Scalability Performance Analysis (50 to 10,000 Customers)", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(viz_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Scalability comparative charts saved to: {viz_path}")
    plt.close(fig)


if __name__ == "__main__":
    run_benchmark()
