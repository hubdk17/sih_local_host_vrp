"""
test_annealed_turing_20depots.py

Validates Annealed Turing-GLS on the 20-depot, 500-customer benchmark
to verify closure of the distance gap against Google OR-Tools.
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

from src.solver_engine import load_or_download_graph, build_dijkstra_matrices
from src.annealed_turing_hqgls import AnnealedTuringHQGLS

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ultra_scale_20depot")
ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c"

NUM_DEPOTS = 20
NUM_CUSTOMERS = 500
TOTAL_VEHICLES = 45
VEHICLE_CAPACITY = 35
SEED = 42

def run_annealed_test():
    print("=" * 80)
    print("  TESTING ANNEALED TURING-GLS ON 20 DEPOTS & 500 CUSTOMERS")
    print("=" * 80)

    # 1. Load Road Graph
    G = load_or_download_graph(city_key="delhi")
    node_list = list(G.nodes)

    # 2. Select exactly the same 20 depots & 500 customers
    random.seed(SEED)
    np.random.seed(SEED)
    center_node = node_list[len(node_list) // 2]
    all_candidates = [n for n in node_list if n != center_node]

    depot_nodes = [center_node]
    sample_pool = random.sample(all_candidates, min(len(all_candidates), 1000))
    while len(depot_nodes) < NUM_DEPOTS and sample_pool:
        best_n = max(sample_pool, key=lambda n: min(
            math.hypot(G.nodes[n]["y"] - G.nodes[d]["y"], G.nodes[n]["x"] - G.nodes[d]["x"])
            for d in depot_nodes
        ))
        depot_nodes.append(best_n)
        sample_pool.remove(best_n)

    depot_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in depot_nodes]
    available_cust_pool = [n for n in all_candidates if n not in depot_nodes]
    cust_nodes = random.sample(available_cust_pool, NUM_CUSTOMERS)
    demands = [random.randint(1, 3) for _ in range(NUM_CUSTOMERS)]
    cust_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in cust_nodes]

    # 3. Clustering & Fleet
    cust_clusters = {d: [] for d in range(NUM_DEPOTS)}
    for i, c_pt in enumerate(cust_coords):
        nearest_d = min(range(NUM_DEPOTS), key=lambda d: math.hypot(c_pt[0] - depot_coords[d][0], c_pt[1] - depot_coords[d][1]))
        cust_clusters[nearest_d].append(i)

    vehs_per_depot = {}
    for d in range(NUM_DEPOTS):
        d_dem = sum(demands[i] for i in cust_clusters[d])
        needed = max(1, math.ceil(d_dem / (VEHICLE_CAPACITY * 0.85)))
        vehs_per_depot[d] = needed

    assigned_v = sum(vehs_per_depot.values())
    if assigned_v < TOTAL_VEHICLES:
        rem = TOTAL_VEHICLES - assigned_v
        top_load_depots = sorted(range(NUM_DEPOTS), key=lambda d: len(cust_clusters[d]), reverse=True)
        for d in top_load_depots[:rem]:
            vehs_per_depot[d] += 1

    # Previous baseline numbers
    exact_baseline = 1116.22
    std_hq_baseline = 1138.31
    old_turing_baseline = 1235.84

    # 4. Run Annealed Turing-GLS
    results = []
    t_start = time.time()
    for d in range(NUM_DEPOTS):
        c_idx = cust_clusters[d]
        if not c_idx: continue

        d_demands = [demands[i] for i in c_idx]
        d_coords = [cust_coords[i] for i in c_idx]
        sub_nodes = [depot_nodes[d]] + [cust_nodes[i] for i in c_idx]
        v_d = vehs_per_depot[d]

        d_time, d_len = build_dijkstra_matrices(G, sub_nodes)

        solver = AnnealedTuringHQGLS(
            d_time, d_len, d_demands, v_d, VEHICLE_CAPACITY,
            depot_coords[d], d_coords, time_limit=0.6
        )
        res = solver.solve()
        dist_km = _calc_dist(res.get("routes", []), d_len)
        results.append({
            "depot_id": d + 1,
            "dist_km": dist_km,
            "runtime_s": res.get("runtime_sec", 0.0),
            "violations": res.get("violations", 0)
        })

    total_time = time.time() - t_start
    df = pd.DataFrame(results)
    new_turing_dist = float(df["dist_km"].sum())
    gap_vs_exact = ((new_turing_dist - exact_baseline) / exact_baseline) * 100.0
    gap_vs_std = ((new_turing_dist - std_hq_baseline) / std_hq_baseline) * 100.0

    print("\n" + "=" * 80)
    print("  ANNEALED TURING-GLS PERFORMANCE VERIFICATION")
    print("=" * 80)
    print(f"  Google OR-Tools (Exact):     {exact_baseline:>8.2f} km  [Baseline]")
    print(f"  Old Turing-Enhanced:         {old_turing_baseline:>8.2f} km  (+10.72% DRIFT)")
    print(f"  Standard Quantum HQ-GLS:     {std_hq_baseline:>8.2f} km  (+1.98% gap)")
    print(f"  NEW Annealed Turing-GLS:     {new_turing_dist:>8.2f} km  (Gap vs Exact: {gap_vs_exact:+.2f}%)")
    print(f"  Total Wall-Clock Time:       {total_time:>8.2f} seconds")
    print(f"  Distance Squeezed:           {old_turing_baseline - new_turing_dist:+.2f} km recovered!")
    print("=" * 80)

    # Plot comparison chart
    _plot_comparison(exact_baseline, std_hq_baseline, old_turing_baseline, new_turing_dist, total_time)

def _calc_dist(routes, d_len):
    tot = 0.0
    for r in routes:
        if r:
            nodes = [0] + [c + 1 for c in r] + [0]
            tot += sum(d_len[nodes[k], nodes[k+1]] for k in range(len(nodes)-1))
    return round(tot / 1000.0, 2)

def _plot_comparison(exact, std_hq, old_tur, new_tur, run_t):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), facecolor='white')

    labels = ['Old Turing\n(Pruned -10dB)', 'Google OR-Tools\n(Exact Baseline)', 'Standard\nQuantum HQ-GLS', 'NEW Annealed\nTuring-GLS']
    distances = [old_tur, exact, std_hq, new_tur]
    colors = ['#94a3b8', '#f59e0b', '#0ea5e9', '#0284c7']

    bars = ax1.bar(labels, distances, color=colors, width=0.55, edgecolor='#334155', linewidth=1.2)
    ax1.set_title("Total Distance Comparison (20 Depots, 500 Customers) — Lower is Better", fontsize=11, fontweight='bold', color='#0f172a', pad=10)
    ax1.set_ylabel("Total Fleet Distance (km)", fontsize=10, fontweight='bold', color='#1e293b')
    ax1.grid(True, axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
    ax1.set_facecolor('white')
    for bar, d in zip(bars, distances):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(distances)*0.015, f"{d:,.1f} km",
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#0f172a')

    # Panel 2: Distance Gap vs Exact (%)
    gaps = [((d - exact) / exact) * 100.0 for d in distances]
    bar_cols = ['#ef4444', '#f59e0b', '#10b981', '#0284c7']
    bars2 = ax2.bar(labels, gaps, color=bar_cols, width=0.55, edgecolor='#334155', linewidth=1.2)
    ax2.set_title("Optimality Gap vs Google OR-Tools (%) — Near 0% is Optimal", fontsize=11, fontweight='bold', color='#0f172a', pad=10)
    ax2.set_ylabel("Gap vs Exact (%)", fontsize=10, fontweight='bold', color='#1e293b')
    ax2.axhline(0, color='#334155', linestyle='-', linewidth=1.0)
    ax2.grid(True, axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
    ax2.set_facecolor('white')
    for bar, g in zip(bars2, gaps):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.3 if g >= 0 else -0.8), f"{g:+.2f}%",
                 ha='center', va='bottom' if g >= 0 else 'top', fontsize=9.5, fontweight='bold', color='#0f172a')

    fig.suptitle("Closing the Turing Gap: Annealed Turing-GLS Performance (White Background)",
                 fontsize=13, fontweight='bold', color='#0f172a', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    plot_path = os.path.join(OUTPUT_DIR, "annealed_turing_gap_closed_white.png")
    fig.savefig(plot_path, dpi=300, facecolor='white')
    artifact_plot = os.path.join(ARTIFACT_DIR, "annealed_turing_gap_closed_white.png")
    fig.savefig(artifact_plot, dpi=300, facecolor='white')
    plt.close(fig)
    print(f"  Chart saved: {plot_path}")

if __name__ == "__main__":
    run_annealed_test()
