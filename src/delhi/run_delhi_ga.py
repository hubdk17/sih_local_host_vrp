"""
run_delhi_ga.py

Main execution script for the Multi-Depot Vehicle Routing Problem (MDVRP)
on Delhi's OpenStreetMap road network graph using Genetic Algorithm (GA).

Supports command line options:
  --seed N          (Random seed, default: 1)
  --pop_size N      (Population size, default: 100)
  --generations N   (Number of generations, default: 200)
  --penalty N       (Violation penalty weight, default: 5000.0)
"""

import argparse
import csv
import json
import os
import sys
import time
import matplotlib.pyplot as plt
import osmnx as ox

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.delhi.delhi_mdvrp_instance import DelhiMDVRPInstance
from src.scaled.mdvrp_route_evaluator import MDVRPRouteEvaluator
from src.scaled.mdvrp_ga_optimizer import MDVRPGeneticAlgorithm

CONFIG_PATH = os.path.join(BASE_DIR, "data", "delhi", "delhi_mdvrp_config.json")
GRAPHML_PATH = os.path.join(BASE_DIR, "data", "delhi", "delhi_road_network.graphml")

# 10 Route Colors for Vehicles
ROUTE_COLORS = [
    "#e74c3c", "#2980b9", "#2ecc71", "#9b59b6", "#e67e22",
    "#1abc9c", "#d35400", "#c0392b", "#16a085", "#8e44ad"
]
DEPOT_COLORS = ["#27ae60", "#c0392b", "#8e44ad", "#2c3e50"]
DEPOT_MARKERS = ["*", "D", "P", "X"]


def parse_args():
    parser = argparse.ArgumentParser(description="Delhi Multi-Depot VRP GA Experiment")
    parser.add_argument("--seed", type=int, default=1, help="Random seed (default: 1)")
    parser.add_argument("--pop_size", type=int, default=100, help="Population size (default: 100)")
    parser.add_argument("--generations", type=int, default=200, help="Number of generations (default: 200)")
    parser.add_argument("--penalty", type=float, default=5000.0, help="Violation penalty weight (default: 5000)")
    return parser.parse_args()


def plot_delhi_distribution(instance: DelhiMDVRPInstance, save_path: str):
    """Plot customer and depot distribution on the Delhi road network graph."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    fig, ax = ox.plot_graph(
        G, show=False, close=False, save=False,
        node_size=2, node_color="#bdc3c7", edge_color="#ecf0f1",
        edge_linewidth=0.5, bgcolor="#ffffff"
    )

    # Draw Depots
    for d in instance.depots_info:
        idx = d["id"]
        ax.scatter(
            [d["node_longitude"]], [d["node_latitude"]],
            color=DEPOT_COLORS[idx % len(DEPOT_COLORS)],
            s=220, marker=DEPOT_MARKERS[idx % len(DEPOT_MARKERS)],
            edgecolors="black", linewidths=1.2, zorder=6,
            label=f"Depot {idx+1}: {d['name'].split('—')[1].strip() if '—' in d['name'] else d['name']}"
        )
        ax.annotate(
            f" D{idx+1}", (d["node_longitude"], d["node_latitude"]),
            fontsize=8, fontweight="bold", color=DEPOT_COLORS[idx % len(DEPOT_COLORS)], zorder=7
        )

    # Draw Customers
    for c in instance.customers_info:
        ax.scatter(
            [c["node_longitude"]], [c["node_latitude"]],
            color="#2980b9", s=30, marker="o",
            edgecolors="white", linewidths=0.4, zorder=5
        )

    ax.set_title("Delhi Multi-Depot VRP: 4 Depots & 50 Customer Locations", fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none", fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Delhi distribution plot saved to: {save_path}")
    plt.close(fig)


def plot_delhi_routes(instance: DelhiMDVRPInstance, evaluation: dict, save_path: str):
    """Plot optimized vehicle routes on the Delhi road network graph."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    fig, ax = ox.plot_graph(
        G, show=False, close=False, save=False,
        node_size=2, node_color="#bdc3c7", edge_color="#ecf0f1",
        edge_linewidth=0.5, bgcolor="#ffffff"
    )

    # Draw Vehicle Routes
    for i, (node_path, edge_path) in enumerate(
        zip(evaluation["vehicle_full_node_paths"], evaluation["vehicle_full_edge_paths"])
    ):
        if len(node_path) < 2:
            continue
        color = ROUTE_COLORS[i % len(ROUTE_COLORS)]
        lons = [G.nodes[n]["x"] for n in node_path]
        lats = [G.nodes[n]["y"] for n in node_path]
        depot_id = evaluation["vehicle_depot_ids"][i]
        ax.plot(
            lons, lats, color=color, linewidth=1.8, alpha=0.85,
            label=f"V{i+1} (Depot {depot_id+1})", zorder=3
        )

    # Draw Depots
    for d in instance.depots_info:
        idx = d["id"]
        ax.scatter(
            [d["node_longitude"]], [d["node_latitude"]],
            color=DEPOT_COLORS[idx % len(DEPOT_COLORS)],
            s=220, marker=DEPOT_MARKERS[idx % len(DEPOT_MARKERS)],
            edgecolors="black", linewidths=1.2, zorder=6,
            label=f"Depot {idx+1}",
        )
        ax.annotate(
            f" D{idx+1}", (d["node_longitude"], d["node_latitude"]),
            fontsize=8, fontweight="bold", color=DEPOT_COLORS[idx % len(DEPOT_COLORS)], zorder=7
        )

    # Draw Customers
    for c in instance.customers_info:
        ax.scatter(
            [c["node_longitude"]], [c["node_latitude"]],
            color="#2980b9", s=25, marker="o",
            edgecolors="white", linewidths=0.3, zorder=5
        )

    ax.set_title(
        f"Delhi MDVRP GA Routes ({instance.num_customers} Customers, {instance.num_depots} Depots, {instance.num_vehicles} Vehicles)",
        fontsize=12, fontweight="bold", pad=10
    )
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Delhi MDVRP route map saved to: {save_path}")
    plt.close(fig)


def plot_delhi_convergence(history: dict, save_path: str):
    """Plot convergence curves for travel time, distance, and population diversity."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    gens = history["generation"]

    # 1. Travel Time
    ax = axes[0, 0]
    ax.plot(gens, history["best_travel_time"], color="#e74c3c", lw=2, label="Best Travel Time")
    ax.set_title("Delhi MDVRP: Travel Time Convergence", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Total Travel Time (seconds)")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # 2. Distance
    ax = axes[0, 1]
    ax.plot(gens, history["best_distance"], color="#2980b9", lw=2, label="Best Distance")
    ax.set_title("Delhi MDVRP: Total Distance Convergence", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Total Distance (meters)")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # 3. Validity
    ax = axes[1, 0]
    ax.plot(gens, history["num_valid"], color="#27ae60", lw=2, label="Valid Solutions")
    ax.plot(gens, history["num_invalid"], color="#e74c3c", lw=2, label="Invalid Solutions")
    ax.set_title("Population Feasibility Breakdown", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Count")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # 4. Diversity
    ax = axes[1, 1]
    ax.plot(gens, history["population_diversity"], color="#8e44ad", lw=2, label="Hamming Diversity")
    ax2 = ax.twinx()
    ax2.plot(gens, history["unique_permutations"], color="#e67e22", lw=2, ls="--", label="Unique Permutations")
    ax.set_title("Population Diversity & Unique Solutions", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Avg Hamming Distance")
    ax2.set_ylabel("Unique Count")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax.grid(True, ls="--", alpha=0.5)

    fig.suptitle("Delhi Multi-Depot VRP GA Optimization Convergence", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Delhi convergence plot saved to: {save_path}")
    plt.close(fig)


def main():
    args = parse_args()

    output_dir = os.path.join(BASE_DIR, "outputs", "ga", "delhi", f"seed_{args.seed}")
    os.makedirs(output_dir, exist_ok=True)

    print("==========================================================")
    print("      DELHI MULTI-DEPOT VRP GA OPTIMIZATION RUNNER        ")
    print("==========================================================")
    print(f"  Seed          : {args.seed}")
    print(f"  Pop Size      : {args.pop_size}")
    print(f"  Generations   : {args.generations}")
    print(f"  Penalty       : {args.penalty}")
    print(f"  Output Dir    : {output_dir}")
    print("==========================================================\n")

    # 1. Load Delhi MDVRP Instance
    print("[1/5] Loading Delhi MDVRP instance & graph...")
    t0 = time.time()
    instance = DelhiMDVRPInstance(config_path=CONFIG_PATH, graphml_path=GRAPHML_PATH)
    load_time = time.time() - t0

    print(f"  Loaded in {load_time:.1f}s")
    print(f"  Graph         : {len(instance.graph.nodes)} nodes, {len(instance.graph.edges)} edges")
    print(f"  Depots        : {instance.num_depots}")
    print(f"  Customers     : {instance.num_customers}")
    print(f"  Vehicles      : {instance.num_vehicles}")
    print(f"  Total Demand  : {sum(instance.demands.values())} units")
    total_cap = sum(v["capacity"] for v in instance.vehicles_list)
    print(f"  Total Capacity: {total_cap} units\n")

    # 2. Render Location Distribution Plot
    print("[2/5] Rendering Delhi customer & depot distribution plot...")
    dist_path = os.path.join(output_dir, "distribution.png")
    plot_delhi_distribution(instance, dist_path)

    # 3. Execute GA Optimization
    print("[3/5] Starting GA optimization loop...")
    evaluator = MDVRPRouteEvaluator(instance)

    ga = MDVRPGeneticAlgorithm(
        instance=instance,
        pop_size=args.pop_size,
        generations=args.generations,
        penalty_per_violation=args.penalty,
        random_seed=args.seed,
    )

    t_start = time.time()
    results = ga.optimize()
    runtime = time.time() - t_start

    best_eval = results["best_evaluation"]
    history = results["history"]

    # 4. Display Results & Structured Report
    print("==========================================================")
    print("           DELHI MDVRP GA OPTIMIZATION RESULTS            ")
    print("==========================================================")
    print(f"  Runtime             : {runtime:.2f} s")
    print(f"  Best Travel Time    : {best_eval['total_travel_time']:.2f} s")
    print(f"  Best Total Distance : {best_eval['total_distance']:.2f} m")
    print(f"  Constraint Violations: {best_eval['total_violations']}")
    print(f"  Solution Status     : {'VALID' if best_eval['is_valid'] else 'INVALID'}")
    print("==========================================================\n")

    report = evaluator.format_constraint_report(best_eval)
    print(report)

    # 5. Save Artifacts (CSV, Convergence Plot, Route Map, JSON)
    print("\n[4/5] Saving experiment output artifacts...")

    # CSV History
    csv_path = os.path.join(output_dir, "history.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(history.keys())
        for row in zip(*history.values()):
            writer.writerow(row)
    print(f"  History CSV      : {csv_path}")

    # Convergence Plot
    conv_path = os.path.join(output_dir, "convergence.png")
    plot_delhi_convergence(history, conv_path)

    # Route Map
    route_path = os.path.join(output_dir, "best_route.png")
    plot_delhi_routes(instance, best_eval, route_path)

    # Result JSON Report
    final_viols = history["best_violations"][-1]
    conv_gen = args.generations
    for i, v in enumerate(history["best_violations"]):
        if v == final_viols:
            conv_gen = history["generation"][i]
            break

    result_json = {
        "experiment": "delhi_mdvrp_ga",
        "seed": args.seed,
        "region": "Central & South Delhi, India",
        "num_graph_nodes": len(instance.graph.nodes),
        "num_graph_edges": len(instance.graph.edges),
        "num_customers": instance.num_customers,
        "num_depots": instance.num_depots,
        "num_vehicles": instance.num_vehicles,
        "total_demand": sum(instance.demands.values()),
        "total_capacity": total_cap,
        "ga_parameters": {
            "pop_size": args.pop_size,
            "generations": args.generations,
            "crossover_prob": 0.85,
            "mutation_prob": 0.25,
            "penalty_per_violation": args.penalty,
        },
        "results": {
            "runtime_seconds": round(runtime, 2),
            "best_travel_time_s": round(best_eval["total_travel_time"], 2),
            "best_distance_m": round(best_eval["total_distance"], 2),
            "total_violations": best_eval["total_violations"],
            "is_valid": best_eval["is_valid"],
            "convergence_generation": conv_gen,
            "final_diversity": round(history["population_diversity"][-1], 2) if history["population_diversity"] else 0,
        },
        "best_permutation": results["best_individual"],
    }

    json_path = os.path.join(output_dir, "result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2, ensure_ascii=False)
    print(f"  Result JSON      : {json_path}")

    print("\n[5/5] Delhi experiment execution complete.")
    print(f"  All outputs saved in: {output_dir}")
    print("==========================================================")


if __name__ == "__main__":
    main()
