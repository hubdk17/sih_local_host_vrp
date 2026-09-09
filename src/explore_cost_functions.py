"""
explore_cost_functions.py

In-depth Multi-Parametric Cost Function Exploration for Turing-Enhanced Quantum HQ-GLS Pro.
Investigates how altering the mathematical objective landscape impacts:
- Physical street distance (km)
- Congested travel time (min)
- BPR non-linear gridlock delay (min)
- Driver workload disparity / equity (min std)
- Route makespan / max shift duration (min)
- Green kinetic energy payload-distance integral (kg*km)
- Logistic Turing Test (LTT) realism & geometric crossing score

Tested on Delhi's real-world OpenStreetMap road network under BPR congestion.
"""

import os
import sys
import json
import time
import random
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.solver_engine import load_or_download_graph, build_dijkstra_matrices
from src.turing_quantum_hqgls_pro import TuringQuantumHQGLSPro


def run_cost_function_exploration():
    print("=" * 78)
    print("  EXPLORING MULTI-PARAMETRIC COST FUNCTION FORMULATIONS IN TURING HQ-GLS")
    print("=" * 78)

    # 1. Load Delhi Road Network
    print("\n[1/4] Loading Delhi metropolitan road network...")
    G = load_or_download_graph(city_key="delhi")
    print(f"      Graph loaded with {len(G.nodes)} nodes and {len(G.edges)} edges.")

    # 2. Configure 50 Customers and 6 Vehicles
    random.seed(42)
    np.random.seed(42)

    depot_coord = (28.6139, 77.2090)  # Central Delhi
    depot_node = min(
        G.nodes,
        key=lambda n: (G.nodes[n]["y"] - depot_coord[0])**2 + (G.nodes[n]["x"] - depot_coord[1])**2
    )

    candidate_nodes = [n for n in G.nodes if n != depot_node]
    sample_nodes = random.sample(candidate_nodes, 50)
    sample_demands = [random.randint(1, 3) for _ in range(50)]
    sample_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in sample_nodes]

    num_vehicles = 6
    capacity = 40
    all_nodes = [depot_node] + sample_nodes

    print("\n[2/4] Building BPR Congestion & Free-flow Dijkstra Shortest Path Matrices...")
    time_matrix, dist_matrix, free_time_matrix, delay_matrix = build_dijkstra_matrices(
        G, all_nodes, traffic_congestion=True, cbd_coords=depot_coord, return_all=True
    )
    print(f"      Matrices built successfully: {dist_matrix.shape}")

    # 3. Formulations to Explore
    formulations = [
        {
            "key": "pure_distance",
            "name": "Pure Distance (Shortest Path)",
            "desc": "Classical metric: C = dist_ij. Ignores congestion and driver hours.",
            "mode": "pure_distance"
        },
        {
            "key": "pure_time",
            "name": "Pure Time (Fastest Transit)",
            "desc": "C = v_ref * time_ij. Aggressively prioritizes speed, may add distance.",
            "mode": "pure_time"
        },
        {
            "key": "risk_averse_traffic",
            "name": "BPR Risk-Averse (Traffic Averse)",
            "desc": "C = dist + time + delay*(1+1.5*delay/t_free)^2. Avoids gridlocked choke points.",
            "mode": "risk_averse_traffic"
        },
        {
            "key": "green_kinetic",
            "name": "Green Kinetic (Payload-Distance)",
            "desc": "C = base + sum(m_tare + load_k)*dist. Drops heavy packages early to save energy.",
            "mode": "green_kinetic"
        },
        {
            "key": "driver_ergonomic",
            "name": "Driver Ergonomic & Equity",
            "desc": "C = unified + highway smoothness + active driver workload parity.",
            "mode": "driver_ergonomic"
        },
        {
            "key": "balanced_turing",
            "name": "Turing Multi-Parametric (Balanced)",
            "desc": "Unified physical-economic cost with Morphogenesis & Banburismus Deciban pruning.",
            "mode": "balanced_turing"
        },
    ]

    print("\n[3/4] Solving across 6 Mathematical Cost Landscape Formulations...")
    results = []

    for f in formulations:
        print(f"\n--> Running Formulation: {f['name']} ({f['key']})...")
        t_start = time.time()
        solver = TuringQuantumHQGLSPro(
            time_matrix=time_matrix,
            dist_matrix=dist_matrix,
            demands=sample_demands,
            num_vehicles=num_vehicles,
            capacity=capacity,
            depot_coord=depot_coord,
            cust_coords=sample_coords,
            delay_matrix=delay_matrix,
            free_time_matrix=free_time_matrix,
            time_limit=3.5,
            objective_mode=f["mode"]
        )
        sol = solver.solve()
        elapsed = time.time() - t_start

        sol["formulation_key"] = f["key"]
        sol["formulation_name"] = f["name"]
        sol["formulation_desc"] = f["desc"]
        sol["actual_runtime_sec"] = round(elapsed, 3)

        results.append(sol)
        print(f"    Done in {elapsed:.2f}s | Dist: {sol['distance_km']} km | Time: {sol['time_min']} min | "
              f"Delay: {sol['delay_min']} min | Kinetic: {sol['kinetic_energy_kg_km']} kg*km | "
              f"Equity Std: {sol['equity_std_min']} min | LTT: {sol['ltt_score']}/100")

    # 4. Save Results
    out_dir = os.path.join(BASE_DIR, "outputs", "cost_function_exploration")
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "cost_functions_comparison.json")
    def _sanitize(o):
        if isinstance(o, (np.integer, np.int32, np.int64)):
            return int(o)
        if isinstance(o, (np.floating, np.float32, np.float64)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    with open(json_path, "w") as fp:
        json.dump(results, fp, indent=2, default=_sanitize)

    df = pd.DataFrame([{
        "Formulation": r["formulation_name"],
        "Mode": r["formulation_key"],
        "Distance_km": r["distance_km"],
        "Time_min": r["time_min"],
        "Delay_min": r["delay_min"],
        "Makespan_min": r["makespan_min"],
        "Equity_Std_min": r["equity_std_min"],
        "Kinetic_kg_km": r["kinetic_energy_kg_km"],
        "LTT_Score": r["ltt_score"],
        "Pruned_Pct": r["prune_percentage"],
        "Runtime_sec": r["runtime_sec"]
    } for r in results])

    csv_path = os.path.join(out_dir, "cost_functions_comparison.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[4/4] Data saved to {json_path} and {csv_path}")

    # 5. Plot Clean Scientific White-Theme Figure
    plot_path = os.path.join(out_dir, "cost_functions_multi_parametric_tradeoffs.png")
    plot_multi_parametric_comparison(results, plot_path)
    print(f"      Figure generated: {plot_path}")

    # Copy to artifacts directory
    artifact_dir = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c"
    if os.path.exists(artifact_dir):
        shutil.copy2(plot_path, os.path.join(artifact_dir, "cost_functions_multi_parametric_tradeoffs.png"))
        print(f"      Copied figure to IDE brain artifacts directory.")

    print("\n" + "=" * 78)
    print("  COST FUNCTION EXPLORATION COMPLETED SUCCESSFULLY")
    print("=" * 78)


def plot_multi_parametric_comparison(results, save_path):
    plt.style.use('default')
    fig, axs = plt.subplots(2, 2, figsize=(16, 12), dpi=300)
    fig.patch.set_facecolor('#ffffff')

    labels = [r["formulation_name"].split(" (")[0] for r in results]
    colors = ['#dc2626', '#2563eb', '#d97706', '#16a34a', '#9333ea', '#0284c7']

    # Subplot 1: Distance vs Travel Time Pareto Trade-off
    ax1 = axs[0, 0]
    ax1.set_facecolor('#f8fafc')
    dists = [r["distance_km"] for r in results]
    times = [r["time_min"] for r in results]

    for i, (d, t, c, lab) in enumerate(zip(dists, times, colors, labels)):
        ax1.scatter(d, t, color=c, s=180, edgecolors='#0f172a', linewidths=1.8, zorder=5)
        offset_y = 12 if i % 2 == 0 else -18
        offset_x = 0
        ax1.annotate(
            lab, (d, t), xytext=(offset_x, offset_y), textcoords="offset points",
            ha='center', fontsize=9.5, fontweight='bold', color=c,
            bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec=c, lw=1.2, alpha=0.92)
        )

    ax1.set_title("A. Distance vs Congested Travel Time Pareto Frontier", fontsize=12, fontweight='bold', pad=12, color='#0f172a')
    ax1.set_xlabel("Total Street Distance (km)", fontsize=10, fontweight='bold', color='#334155')
    ax1.set_ylabel("Congested Travel Time (min)", fontsize=10, fontweight='bold', color='#334155')
    ax1.grid(True, linestyle='--', alpha=0.5, color='#cbd5e1')

    # Subplot 2: Congestion Delay vs Driver Workload Equity Disparity
    ax2 = axs[0, 1]
    ax2.set_facecolor('#f8fafc')
    delays = [r["delay_min"] for r in results]
    equities = [r["equity_std_min"] for r in results]

    x_pos = np.arange(len(labels))
    width = 0.38
    b1 = ax2.bar(x_pos - width/2, delays, width, label="Congestion Delay (min)", color='#f97316', edgecolor='#9a3412', lw=1.2)
    b2 = ax2.bar(x_pos + width/2, equities, width, label="Driver Disparity (Std min)", color='#8b5cf6', edgecolor='#5b21b6', lw=1.2)

    for bar in b1:
        y = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, y + 2, f"{y:.0f}", ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#9a3412')
    for bar in b2:
        y = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, y + 2, f"{y:.1f}", ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#5b21b6')

    ax2.set_title("B. Congestion Avoidance vs Driver Workload Parity", fontsize=12, fontweight='bold', pad=12, color='#0f172a')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels([l.replace(" ", "\n") for l in labels], fontsize=8.5, fontweight='bold')
    ax2.set_ylabel("Duration (minutes)", fontsize=10, fontweight='bold', color='#334155')
    ax2.legend(frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)
    ax2.grid(True, axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')

    # Subplot 3: Green Kinetic Work (Payload-Distance Integral) vs Distance
    ax3 = axs[1, 0]
    ax3.set_facecolor('#f8fafc')
    kinetics = [r["kinetic_energy_kg_km"] / 1000.0 for r in results]  # in tonne-km

    bars3 = ax3.bar(x_pos, kinetics, width=0.55, color=colors, edgecolor='#0f172a', lw=1.2)
    for bar, val in zip(bars3, kinetics):
        ax3.text(bar.get_x() + bar.get_width()/2, val + 1.2, f"{val:.1f}t·km", ha='center', va='bottom', fontsize=9, fontweight='bold', color='#0f172a')

    ax3.set_title("C. Green Logistics: Cumulative Payload-Distance Work", fontsize=12, fontweight='bold', pad=12, color='#0f172a')
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels([l.replace(" ", "\n") for l in labels], fontsize=8.5, fontweight='bold')
    ax3.set_ylabel("Kinetic Work Integral (tonne · km)", fontsize=10, fontweight='bold', color='#334155')
    ax3.grid(True, axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')

    # Subplot 4: Logistic Turing Test (LTT) Composite Score
    ax4 = axs[1, 1]
    ax4.set_facecolor('#f8fafc')
    ltt_scores = [r["ltt_score"] for r in results]
    prunes = [r["prune_percentage"] for r in results]

    bars4 = ax4.bar(x_pos, ltt_scores, width=0.55, color=['#cbd5e1' if s < 70 else '#38bdf8' if s < 85 else '#10b981' for s in ltt_scores], edgecolor='#0f172a', lw=1.2)
    ax4.axhline(85.0, color='#10b981', linestyle='--', linewidth=1.5, label='LTT Pass Threshold (85/100)')

    for bar, s in zip(bars4, ltt_scores):
        ax4.text(bar.get_x() + bar.get_width()/2, s + 1.2, f"{s:.1f}", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#0f172a')

    ax4.set_title("D. Logistic Turing Test (LTT) Naturalness & Feasibility Score", fontsize=12, fontweight='bold', pad=12, color='#0f172a')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([l.replace(" ", "\n") for l in labels], fontsize=8.5, fontweight='bold')
    ax4.set_ylabel("LTT Score (/100)", fontsize=10, fontweight='bold', color='#334155')
    ax4.set_ylim(0, 105)
    ax4.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)
    ax4.grid(True, axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')

    plt.suptitle("Multi-Parametric Cost Function Exploration: Turing Quantum HQ-GLS Pro on Delhi Network",
                 fontsize=15, fontweight='bold', y=0.98, color='#0f172a')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(save_path, dpi=300, facecolor='#ffffff', bbox_inches='tight')
    plt.close()


if __name__ == "__main__":
    run_cost_function_exploration()
