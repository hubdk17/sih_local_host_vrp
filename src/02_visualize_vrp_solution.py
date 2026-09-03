"""
02_visualize_vrp_solution.py

Milestone 2: Visualize VRP problem model and candidate solution routes
mapped onto the real Chandigarh OpenStreetMap road network graph.
"""

import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import matplotlib.pyplot as plt
import osmnx as ox

from src.vrp_instance import VRPInstance
from src.route_evaluator import RouteEvaluator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "data", "vrp_config.json")
GRAPHML_PATH = os.path.join(BASE_DIR, "data", "raw", "chandigarh_subset.graphml")
OUTPUT_VIZ_PATH = os.path.join(BASE_DIR, "outputs", "vrp_solution_visualization.png")


def visualize_vrp_solution(instance: VRPInstance, evaluation: dict, save_path: str = OUTPUT_VIZ_PATH):
    """
    Plot Chandigarh road graph with depot, customer locations,
    vehicle routes along graph shortest paths, and road capacity violations.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    # 1. Base plot of Chandigarh road graph
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

    # Vehicle route colors
    route_colors = ["#e74c3c", "#2980b9", "#2ecc71", "#9b59b6"] # Red, Blue, Green, Purple

    # 2. Plot vehicle route paths on graph
    for i, (node_path, edge_path) in enumerate(zip(evaluation["vehicle_full_node_paths"], evaluation["vehicle_full_edge_paths"])):
        if len(node_path) < 2:
            continue
        
        color = route_colors[i % len(route_colors)]

        # Extract lat/lons for the route node path
        route_lons = [G.nodes[n]["x"] for n in node_path]
        route_lats = [G.nodes[n]["y"] for n in node_path]

        ax.plot(
            route_lons,
            route_lats,
            color=color,
            linewidth=2.5,
            alpha=0.85,
            label=f"Vehicle {i+1} Route",
            zorder=3
        )

    # 3. Highlight road capacity violations if present
    road_reports = evaluation["road_capacity"]["reports"]
    violation_edges = [edge for edge, data in road_reports.items() if not data["passed"]]

    if violation_edges:
        viol_lons = []
        viol_lats = []
        for u, v, k in violation_edges:
            viol_lons.extend([G.nodes[u]["x"], G.nodes[v]["x"], None])
            viol_lats.extend([G.nodes[u]["y"], G.nodes[v]["y"], None])
        
        ax.plot(
            viol_lons,
            viol_lats,
            color="#f39c12",
            linestyle="--",
            linewidth=4.0,
            label="Road Capacity Violation",
            zorder=4
        )

    # 4. Plot Depot marker
    depot_lat = instance.depot_info["node_latitude"]
    depot_lon = instance.depot_info["node_longitude"]
    ax.scatter(
        [depot_lon],
        [depot_lat],
        color="#27ae60",
        s=180,
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

    # 5. Plot Customer markers
    for c in instance.customers_info:
        c_id = c["id"]
        c_lat = c["node_latitude"]
        c_lon = c["node_longitude"]
        demand = c["demand"]

        ax.scatter(
            [c_lon],
            [c_lat],
            color="#2980b9",
            s=90,
            marker="o",
            edgecolors="white",
            linewidths=1.0,
            zorder=5
        )
        ax.annotate(
            f" C{c_id} (d={demand})",
            (c_lon, c_lat),
            fontsize=8,
            fontweight="bold",
            color="#1a5276",
            zorder=6
        )

    ax.set_title(
        "Chandigarh VRP Model: Route Shortest Paths on Real Road Graph",
        fontsize=13,
        fontweight="bold",
        pad=12
    )
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none", fontsize=9)

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] VRP solution visualization saved to: {save_path}")

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
    print("      MILESTONE 2: VRP MODEL & CONSTRAINTS       ")
    print("==================================================\n")

    # 1. Load VRP Instance
    instance = VRPInstance(config_path=CONFIG_PATH, graphml_path=GRAPHML_PATH)
    evaluator = RouteEvaluator(instance)

    # 2. Example Permutation Solution: [3, 1, 5, 2, 4, 8, 6, 7]
    example_permutation = [3, 1, 5, 2, 4, 8, 6, 7]
    print(f"Candidate Permutation Solution: {example_permutation}\n")

    # 3. Evaluate solution
    evaluation = evaluator.evaluate(example_permutation)

    # 4. Print Structured Constraint Report
    report = evaluator.format_constraint_report(evaluation)
    print(report)

    # 5. Visualize VRP Solution on Chandigarh Graph
    visualize_vrp_solution(instance, evaluation, OUTPUT_VIZ_PATH)


if __name__ == "__main__":
    main()
