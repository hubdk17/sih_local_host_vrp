"""
03_run_ga_optimization.py

Runs Genetic Algorithm (GA) optimization for Vehicle Routing Problem (VRP)
over Chandigarh's OpenStreetMap road network graph.
Generates metrics report, GA convergence plot, and final VRP route map.
"""

import os
import sys
import matplotlib.pyplot as plt
import osmnx as ox

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.vrp_instance import VRPInstance
from src.route_evaluator import RouteEvaluator
from src.ga_optimizer import GeneticAlgorithmVRP

CONFIG_PATH = os.path.join(BASE_DIR, "data", "vrp_config.json")
GRAPHML_PATH = os.path.join(BASE_DIR, "data", "raw", "chandigarh_subset.graphml")
CONVERGENCE_PATH = os.path.join(BASE_DIR, "outputs", "ga_convergence.png")
MAP_VIZ_PATH = os.path.join(BASE_DIR, "outputs", "ga_vrp_solution_visualization.png")


def plot_convergence(history_time: list, history_distance: list, save_path: str):
    """Plot GA convergence curves for travel time and distance."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    gens = range(1, len(history_time) + 1)

    # Plot Travel Time
    ax1.plot(gens, history_time, color="#e74c3c", linewidth=2.0, label="Best Travel Time")
    ax1.set_title("GA Optimization: Travel Time Convergence", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Generation")
    ax1.set_ylabel("Total Travel Time (seconds)")
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend()

    # Plot Distance
    ax2.plot(gens, history_distance, color="#2980b9", linewidth=2.0, label="Best Distance")
    ax2.set_title("GA Optimization: Distance Convergence", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Generation")
    ax2.set_ylabel("Total Distance (meters)")
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] GA Convergence plot saved to: {save_path}")

    try:
        if sys.flags.interactive or hasattr(sys, 'ps1'):
            plt.show()
        else:
            plt.show(block=False)
            plt.pause(0.5)
    except Exception as e:
        print(f"[NOTE] Interactive display skipped ({e}). Plot saved to file.")
    finally:
        plt.close(fig)


def visualize_ga_routes(instance: VRPInstance, evaluation: dict, save_path: str):
    """Plot optimized GA routes on the Chandigarh road network graph."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=False,
        node_size=5,
        node_color="#bdc3c7",
        edge_color="#ecf0f1",
        edge_linewidth=0.8,
        bgcolor="#ffffff"
    )

    route_colors = ["#e74c3c", "#2980b9", "#2ecc71", "#9b59b6", "#e67e22"]

    # 1. Draw vehicle routes along graph shortest paths
    for i, (node_path, edge_path) in enumerate(zip(evaluation["vehicle_full_node_paths"], evaluation["vehicle_full_edge_paths"])):
        if len(node_path) < 2:
            continue
        
        color = route_colors[i % len(route_colors)]
        route_lons = [G.nodes[n]["x"] for n in node_path]
        route_lats = [G.nodes[n]["y"] for n in node_path]

        ax.plot(
            route_lons,
            route_lats,
            color=color,
            linewidth=2.5,
            alpha=0.85,
            label=f"Vehicle {i+1} GA Route",
            zorder=3
        )

    # 2. Draw Depot
    depot_lat = instance.depot_info["node_latitude"]
    depot_lon = instance.depot_info["node_longitude"]
    ax.scatter(
        [depot_lon],
        [depot_lat],
        color="#27ae60",
        s=220,
        marker="*",
        edgecolors="black",
        linewidths=1.2,
        label="Depot (Sec 17 ISBT)",
        zorder=5
    )
    ax.annotate(
        " Depot",
        (depot_lon, depot_lat),
        fontsize=10,
        fontweight="bold",
        color="#1e8449",
        zorder=6
    )

    # 3. Draw Customers
    for c in instance.customers_info:
        c_id = c["id"]
        c_lat = c["node_latitude"]
        c_lon = c["node_longitude"]
        demand = c["demand"]

        ax.scatter(
            [c_lon],
            [c_lat],
            color="#2980b9",
            s=50,
            marker="o",
            edgecolors="white",
            linewidths=0.5,
            zorder=5
        )
        ax.annotate(
            f"C{c_id}",
            (c_lon, c_lat),
            fontsize=6,
            fontweight="bold",
            color="#1a5276",
            zorder=6
        )

    ax.set_title(
        "GA-Optimized 50-Customer VRP Routes (Chandigarh Road Graph)",
        fontsize=13,
        fontweight="bold",
        pad=12
    )
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none", fontsize=8)

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Optimized GA route map saved to: {save_path}")

    try:
        if sys.flags.interactive or hasattr(sys, 'ps1'):
            plt.show()
        else:
            plt.show(block=False)
            plt.pause(0.5)
    except Exception as e:
        print(f"[NOTE] Interactive display skipped ({e}). Plot saved to file.")
    finally:
        plt.close(fig)


def main():
    print("==================================================")
    print("   MILESTONE 3: 50-CUSTOMER GA VRP OPTIMIZER     ")
    print("==================================================\n")

    # 1. Initialize VRP Instance
    instance = VRPInstance(config_path=CONFIG_PATH, graphml_path=GRAPHML_PATH)
    evaluator = RouteEvaluator(instance)

    # 2. Initialize and Run GA Optimizer
    ga = GeneticAlgorithmVRP(
        instance=instance,
        pop_size=100,
        generations=300,
        crossover_prob=0.85,
        mutation_prob=0.30,
        tournament_size=4,
        elitism_count=2,
        random_seed=42
    )

    ga_results = ga.optimize()

    best_individual = ga_results["best_individual"]
    best_eval = ga_results["best_evaluation"]

    print("==================================================")
    print("             GA OPTIMIZATION RESULTS              ")
    print("==================================================")
    print(f"Best Permutation Individual : {best_individual}")
    print(f"Total Travel Time (seconds) : {best_eval['total_travel_time']:.2f} s")
    print(f"Total Distance (meters)     : {best_eval['total_distance']:.2f} m")
    print(f"Constraint Violations       : {best_eval['total_violations']}")
    print(f"Solution Validity           : {'VALID' if best_eval['is_valid'] else 'INVALID'}")
    print("==================================================\n")

    # 3. Print Detailed Constraint Report
    report = evaluator.format_constraint_report(best_eval)
    print(report)

    # 4. Plot & Save Convergence Curves
    plot_convergence(
        ga_results["history_best_time"],
        ga_results["history_best_distance"],
        CONVERGENCE_PATH
    )

    # 5. Plot & Save GA Route Map Visualization
    visualize_ga_routes(instance, best_eval, MAP_VIZ_PATH)

    print("\n[SUCCESS] GA Optimization completed successfully.")


if __name__ == "__main__":
    main()
