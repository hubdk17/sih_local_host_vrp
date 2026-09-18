"""
multidepot_scaling_benchmark.py

Depot Scalability Benchmark Suite:
Scales depots from 2 to 10 depots on real OpenStreetMap network (Delhi metropolis, 9,607 nodes),
evaluating Quantum HQ-GLS against Exact (Google OR-Tools Guided Local Search),
Delta-Well QPSO, and Classical GA.

Parameters:
  - Depots: D in [2, 3, 4, 5, 6, 7, 8, 9, 10]
  - Customers: 80 customers
  - Vehicles: 10 vehicles partitioned proportionally
  - Capacity: 35 units per vehicle
"""

import os
import sys
import time
import math
import random
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.solver_engine import (
    load_or_download_graph, build_dijkstra_matrices,
    HQGLSSolver, DeltaWellQPSO, ClassicalGABaseline, ExactSolver
)

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "national_benchmark")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NUM_CUSTOMERS = 80
NUM_VEHICLES = 10
CAPACITY = 35
DEPOT_COUNTS = list(range(2, 11))
SEED = 42

def run_depot_scaling_benchmark():
    print("=" * 80)
    print("  MULTI-DEPOT SCALABILITY BENCHMARK SUITE: 2 TO 10 DEPOTS")
    print("  Comparing Quantum HQ-GLS vs Exact (OR-Tools) vs QPSO vs GA")
    print(f"  Configuration: {NUM_CUSTOMERS} Customers, {NUM_VEHICLES} Vehicles, Capacity {CAPACITY}")
    print("=" * 80)

    # 1. Load Road Graph
    t0 = time.time()
    city_key = "delhi"
    print(f"\n[1/2] Loading road graph for {city_key.upper()}...", flush=True)
    G = load_or_download_graph(city_key=city_key)
    node_list = list(G.nodes)
    print(f"  Loaded road network: {len(node_list):,} nodes in {time.time()-t0:.1f}s", flush=True)

    # 2. Fix Customers and Demands across all depot configurations for strict fairness
    random.seed(SEED)
    np.random.seed(SEED)
    center_node = node_list[len(node_list) // 2]
    all_candidates = [n for n in node_list if n != center_node]
    cust_nodes = random.sample(all_candidates, NUM_CUSTOMERS)
    demands = [random.randint(1, 3) for _ in range(NUM_CUSTOMERS)]
    cust_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in cust_nodes]
    available_depot_pool = [n for n in all_candidates if n not in cust_nodes]

    # Pre-select 10 maximally dispersed depots via Farthest-First Traversal
    master_depot_nodes = [center_node]
    pool_sample = random.sample(available_depot_pool, min(len(available_depot_pool), 400))
    while len(master_depot_nodes) < 10 and pool_sample:
        best_n = max(pool_sample, key=lambda n: min(
            math.hypot(G.nodes[n]["y"] - G.nodes[d]["y"], G.nodes[n]["x"] - G.nodes[d]["x"])
            for d in master_depot_nodes
        ))
        master_depot_nodes.append(best_n)
        pool_sample.remove(best_n)

    master_depot_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in master_depot_nodes]

    records = []

    print(f"\n[2/2] Running Multi-Depot scaling from 2 to 10 depots...\n")

    for D in DEPOT_COUNTS:
        print(f"--- Benchmarking D = {D} Depots ---", flush=True)
        depots_coords = master_depot_coords[:D]
        depot_nodes = master_depot_nodes[:D]

        # Customer-to-Depot Nearest Clustering
        cust_clusters = {d: [] for d in range(D)}
        for i, c_pt in enumerate(cust_coords):
            nearest_d = min(range(D), key=lambda d: math.hypot(c_pt[0] - depots_coords[d][0], c_pt[1] - depots_coords[d][1]))
            cust_clusters[nearest_d].append(i)

        # Proportional Vehicle Allocation with Guaranteed Capacity Feasibility
        c_demands = [sum(demands[i] for i in cust_clusters[d]) for d in range(D)]
        active_depots = [d for d in range(D) if len(cust_clusters[d]) > 0]
        vehs_per_depot = {d: 0 for d in range(D)}

        # 1. Base assignment: Every active depot receives minimum vehicles to satisfy capacity
        for d in active_depots:
            vehs_per_depot[d] = max(1, math.ceil(c_demands[d] / CAPACITY))

        # 2. Distribute remaining vehicles to active depots with highest demand/vehicle load
        rem_vehs = NUM_VEHICLES - sum(vehs_per_depot.values())
        if rem_vehs > 0:
            for _ in range(rem_vehs):
                d_pick = max(active_depots, key=lambda d: c_demands[d] / vehs_per_depot[d])
                vehs_per_depot[d_pick] += 1

        print(f"  Depot customer distribution: {[len(cust_clusters[d]) for d in range(D)]}", flush=True)
        print(f"  Fleet distribution:          {[vehs_per_depot[d] for d in range(D)]} vehicles", flush=True)

        # Precompute Sub-Dijkstra matrices per active depot
        depot_matrices = {}
        for d in range(D):
            c_idx = cust_clusters[d]
            if not c_idx:
                continue
            sub_nodes = [depot_nodes[d]] + [cust_nodes[i] for i in c_idx]
            d_time_d, d_len_d = build_dijkstra_matrices(G, sub_nodes)
            depot_matrices[d] = (d_time_d, d_len_d, c_idx)

        # Solver runner across depots
        def _solve(algo_name):
            tot_dist_m = 0.0
            tot_time = 0.0
            tot_viols = 0

            for d in range(D):
                if d not in depot_matrices:
                    continue
                d_time_d, d_len_d, c_idx = depot_matrices[d]
                sub_dem = [demands[i] for i in c_idx]
                sub_coords = [cust_coords[i] for i in c_idx]
                v_d = vehs_per_depot[d]

                if algo_name == "hq_gls":
                    solver = HQGLSSolver(d_time_d, d_len_d, sub_dem, v_d, CAPACITY,
                                         depots_coords[d], sub_coords, time_limit=1.5)
                elif algo_name == "qpso":
                    solver = DeltaWellQPSO(d_time_d, d_len_d, sub_dem, v_d, CAPACITY,
                                          depots_coords[d], sub_coords, pop_size=35, max_iter=35)
                elif algo_name == "ga":
                    solver = ClassicalGABaseline(d_time_d, d_len_d, sub_dem, v_d, CAPACITY,
                                                depots_coords[d], sub_coords, pop_size=30, generations=35)
                elif algo_name == "exact":
                    solver = ExactSolver(d_time_d, d_len_d, sub_dem, v_d, CAPACITY, time_limit=3)

                res = solver.solve()
                if algo_name == "exact" and (res.get("distance_km", -1) == -1 or not any(res.get("routes", []))):
                    solver = ExactSolver(d_time_d, d_len_d, sub_dem, v_d, CAPACITY, time_limit=6)
                    res = solver.solve()

                tot_time += res.get("runtime_sec", 0.0)
                tot_viols += res.get("violations", 0)
                for local_r in res.get("routes", []):
                    if local_r:
                        r_nodes = [0] + [x + 1 for x in local_r] + [0]
                        tot_dist_m += float(sum(d_len_d[r_nodes[k], r_nodes[k+1]] for k in range(len(r_nodes)-1)))

            return round(tot_dist_m / 1000.0, 2), round(tot_time, 2), tot_viols

        # 1. Quantum HQ-GLS
        hq_d, hq_t, hq_v = _solve("hq_gls")
        print(f"    -> Quantum HQ-GLS:   {hq_d} km in {hq_t}s (viol: {hq_v})", flush=True)

        # 2. Exact Solver
        ex_d, ex_t, ex_v = _solve("exact")
        print(f"    -> Exact (OR-Tools): {ex_d} km in {ex_t}s (viol: {ex_v})", flush=True)

        # 3. Delta-Well QPSO
        qp_d, qp_t, qp_v = _solve("qpso")
        print(f"    -> Delta-Well QPSO:  {qp_d} km in {qp_t}s (viol: {qp_v})", flush=True)

        # 4. Classical GA
        ga_d, ga_t, ga_v = _solve("ga")
        print(f"    -> Classical GA:     {ga_d} km in {ga_t}s (viol: {ga_v})", flush=True)

        gap_pct = round(((hq_d - ex_d) / ex_d) * 100.0, 2)
        speedup = round(ex_t / max(0.01, hq_t), 1)
        print(f"  => D={D} Outcome: Gap vs Exact: {gap_pct:+.2f}% | Speedup: {speedup}x\n", flush=True)

        records.append({
            "depots": D,
            "customers": NUM_CUSTOMERS,
            "vehicles": NUM_VEHICLES,
            "capacity": CAPACITY,
            "hq_dist_km": hq_d,
            "exact_dist_km": ex_d,
            "qpso_dist_km": qp_d,
            "ga_dist_km": ga_d,
            "hq_vs_exact_pct": gap_pct,
            "hq_time_s": hq_t,
            "exact_time_s": ex_t,
            "qpso_time_s": qp_t,
            "ga_time_s": ga_t,
            "speedup_vs_exact": speedup,
            "hq_violations": hq_v,
            "exact_violations": ex_v
        })

    df = pd.DataFrame(records)
    csv_path = os.path.join(OUTPUT_DIR, "depot_scaling_2to10_results.csv")
    json_path = os.path.join(OUTPUT_DIR, "depot_scaling_2to10_results.json")
    df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(records, f, indent=2)

    # 3. Generate Publication Comparison Chart
    _plot_depot_scaling(df)

    # 4. Summary Scorecard
    print("=" * 80)
    print("  MULTI-DEPOT SCALABILITY SUMMARY SCORECARD (2 TO 10 DEPOTS)")
    print("=" * 80)
    summary_cols = ["depots", "hq_dist_km", "exact_dist_km", "qpso_dist_km", "ga_dist_km", "hq_vs_exact_pct", "speedup_vs_exact"]
    print(df[summary_cols].to_string(index=False))

    avg_gap = df["hq_vs_exact_pct"].mean()
    avg_speedup = df["speedup_vs_exact"].mean()
    print(f"\nAverage Gap vs Exact across D=2..10: {avg_gap:+.2f}%")
    print(f"Average Speedup vs Exact: {avg_speedup:.1f}x faster")
    print(f"Saved results to: {csv_path}")

def _plot_depot_scaling(df):
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10), facecolor='#0B0F19')
    ax1.set_facecolor('#0E1526')
    ax2.set_facecolor('#0E1526')

    depots = df["depots"].values
    x = np.arange(len(depots))

    # Panel 1: Route Distance vs Depots
    ax1.plot(depots, df["hq_dist_km"], marker='o', linewidth=2.5, color='#00E5FF', label='Quantum HQ-GLS (SOTA)', zorder=5)
    ax1.plot(depots, df["exact_dist_km"], marker='s', linewidth=2.2, linestyle='--', color='#F59E0B', label='Exact Solver (OR-Tools GLS)', zorder=4)
    ax1.plot(depots, df["qpso_dist_km"], marker='^', linewidth=2.0, color='#10B981', label='Delta-Well QPSO', zorder=3)
    ax1.plot(depots, df["ga_dist_km"], marker='d', linewidth=2.0, color='#EF4444', label='Classical GA Baseline', zorder=2)

    for i, d in enumerate(depots):
        gap = df["hq_vs_exact_pct"].iloc[i]
        color = '#00E5FF' if gap <= 0.5 else '#E0E7FF'
        ax1.annotate(f"{gap:+.1f}%", (d, df["hq_dist_km"].iloc[i]),
                     textcoords="offset points", xytext=(0, 10), ha='center',
                     fontsize=9, fontweight='bold', color=color)

    ax1.set_title("Multi-Depot VRP Scalability: Total Fleet Distance vs Depots (80 Customers, 10 Vehicles)",
                  fontsize=13, fontweight='bold', color='#FFFFFF', pad=12)
    ax1.set_ylabel("Total Fleet Distance (km)", fontsize=11, fontweight='bold', color='#E0E7FF')
    ax1.set_xticks(depots)
    ax1.set_xlabel("Number of Depots (D)", fontsize=11, fontweight='bold', color='#E0E7FF')
    ax1.grid(True, linestyle='--', alpha=0.2, color='#64748B')
    ax1.legend(loc='upper right', framealpha=0.8, facecolor='#1E293B', edgecolor='#00E5FF')

    # Panel 2: Compute Runtime vs Depots
    ax2.plot(depots, df["hq_time_s"], marker='o', linewidth=2.5, color='#00E5FF', label='Quantum HQ-GLS Runtime', zorder=5)
    ax2.plot(depots, df["exact_time_s"], marker='s', linewidth=2.2, color='#F59E0B', label='Exact Solver Runtime', zorder=4)

    for i, d in enumerate(depots):
        sp = df["speedup_vs_exact"].iloc[i]
        ax2.annotate(f"{sp:.1f}x faster", (d, df["hq_time_s"].iloc[i]),
                     textcoords="offset points", xytext=(0, 8), ha='center',
                     fontsize=9, fontweight='bold', color='#00E5FF')

    ax2.set_title("Multi-Depot Compute Runtime: Quantum HQ-GLS vs Exact Solver (OR-Tools)",
                  fontsize=13, fontweight='bold', color='#FFFFFF', pad=12)
    ax2.set_ylabel("Compute Runtime (seconds)", fontsize=11, fontweight='bold', color='#E0E7FF')
    ax2.set_xlabel("Number of Depots (D)", fontsize=11, fontweight='bold', color='#E0E7FF')
    ax2.set_xticks(depots)
    ax2.grid(True, linestyle='--', alpha=0.2, color='#64748B')
    ax2.legend(loc='upper right', framealpha=0.8, facecolor='#1E293B', edgecolor='#F59E0B')

    plt.tight_layout()
    chart_path = os.path.join(OUTPUT_DIR, "depot_scaling_2to10_comparison.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"  Chart saved to: {chart_path}", flush=True)

if __name__ == "__main__":
    run_depot_scaling_benchmark()
