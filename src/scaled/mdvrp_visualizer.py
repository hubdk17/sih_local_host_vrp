"""
mdvrp_visualizer.py

Visualization utilities for Multi-Depot VRP solutions on Chandigarh road network.
"""

import os
import sys
import matplotlib.pyplot as plt
import osmnx as ox


# 8 distinguishable route colors for up to 8 vehicles
ROUTE_COLORS = [
    "#e74c3c", "#2980b9", "#2ecc71", "#9b59b6",
    "#e67e22", "#1abc9c", "#f1c40f", "#34495e",
]

DEPOT_COLORS = ["#27ae60", "#c0392b", "#8e44ad", "#2c3e50"]
DEPOT_MARKERS = ["*", "D", "P", "X"]


def plot_convergence(history: dict, save_path: str):
    """Plot GA convergence curves for MDVRP."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    gens = history["generation"]

    # Travel Time
    ax = axes[0, 0]
    ax.plot(gens, history["best_travel_time"], color="#e74c3c", lw=2, label="Best Travel Time")
    ax.set_title("Travel Time Convergence", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Time (s)")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # Distance
    ax = axes[0, 1]
    ax.plot(gens, history["best_distance"], color="#2980b9", lw=2, label="Best Distance")
    ax.set_title("Distance Convergence", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Distance (m)")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # Valid vs Invalid
    ax = axes[1, 0]
    ax.plot(gens, history["num_valid"], color="#27ae60", lw=2, label="Valid")
    ax.plot(gens, history["num_invalid"], color="#e74c3c", lw=2, label="Invalid")
    ax.set_title("Population Validity", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Count")
    ax.grid(True, ls="--", alpha=0.5)
    ax.legend()

    # Diversity
    ax = axes[1, 1]
    ax.plot(gens, history["population_diversity"], color="#8e44ad", lw=2, label="Avg Hamming Dist")
    ax2 = ax.twinx()
    ax2.plot(gens, history["unique_permutations"], color="#e67e22", lw=2, ls="--", label="Unique Perms")
    ax.set_title("Population Diversity", fontweight="bold")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Hamming Distance")
    ax2.set_ylabel("Unique Count")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax.grid(True, ls="--", alpha=0.5)

    fig.suptitle("MDVRP GA Scalability — Convergence Diagnostics", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VIZ] Convergence plot saved: {save_path}")

    try:
        plt.show(block=False)
        plt.pause(0.5)
    except Exception:
        pass
    finally:
        plt.close(fig)


def plot_routes(instance, evaluation: dict, save_path: str):
    """Plot optimized MDVRP routes on the road network."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    fig, ax = ox.plot_graph(
        G, show=False, close=False, save=False,
        node_size=3, node_color="#d5d8dc", edge_color="#ecf0f1",
        edge_linewidth=0.6, bgcolor="#ffffff",
    )

    # Draw vehicle routes
    for i, (node_path, edge_path) in enumerate(
        zip(evaluation["vehicle_full_node_paths"], evaluation["vehicle_full_edge_paths"])
    ):
        if len(node_path) < 2:
            continue
        color = ROUTE_COLORS[i % len(ROUTE_COLORS)]
        lons = [G.nodes[n]["x"] for n in node_path]
        lats = [G.nodes[n]["y"] for n in node_path]
        depot_id = evaluation["vehicle_depot_ids"][i]
        ax.plot(lons, lats, color=color, lw=2.0, alpha=0.8,
                label=f"V{i} (Depot {depot_id})", zorder=3)

    # Draw depots
    for d in instance.depots_info:
        idx = d["id"]
        color = DEPOT_COLORS[idx % len(DEPOT_COLORS)]
        marker = DEPOT_MARKERS[idx % len(DEPOT_MARKERS)]
        ax.scatter(
            [d["node_longitude"]], [d["node_latitude"]],
            color=color, s=200, marker=marker,
            edgecolors="black", linewidths=1.2, zorder=6,
            label=f"Depot {idx}",
        )
        ax.annotate(
            f" D{idx}", (d["node_longitude"], d["node_latitude"]),
            fontsize=9, fontweight="bold", color=color, zorder=7,
        )

    # Draw customers
    for c in instance.customers_info:
        ax.scatter(
            [c["node_longitude"]], [c["node_latitude"]],
            color="#2980b9", s=30, marker="o",
            edgecolors="white", linewidths=0.4, zorder=5,
        )
        ax.annotate(
            f"C{c['id']}", (c["node_longitude"], c["node_latitude"]),
            fontsize=5, fontweight="bold", color="#1a5276", zorder=6,
        )

    ax.set_title(
        f"MDVRP GA Routes — {instance.num_customers} Customers, "
        f"{instance.num_depots} Depots, {instance.num_vehicles} Vehicles",
        fontsize=12, fontweight="bold", pad=10,
    )
    ax.legend(loc="upper left", frameon=True, facecolor="white",
              edgecolor="none", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VIZ] Route map saved: {save_path}")

    try:
        plt.show(block=False)
        plt.pause(0.5)
    except Exception:
        pass
    finally:
        plt.close(fig)


def plot_customer_depot_distribution(instance, save_path: str):
    """Plot customer and depot distribution on the road network."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    G = instance.graph

    fig, ax = ox.plot_graph(
        G, show=False, close=False, save=False,
        node_size=2, node_color="#d5d8dc", edge_color="#ecf0f1",
        edge_linewidth=0.5, bgcolor="#ffffff",
    )

    # Depots
    for d in instance.depots_info:
        idx = d["id"]
        ax.scatter(
            [d["node_longitude"]], [d["node_latitude"]],
            color=DEPOT_COLORS[idx % len(DEPOT_COLORS)],
            s=250, marker=DEPOT_MARKERS[idx % len(DEPOT_MARKERS)],
            edgecolors="black", linewidths=1.5, zorder=6,
            label=d["name"],
        )

    # Customers colored by sector
    sectors = list(set(c.get("sector", "?") for c in instance.customers_info))
    sector_colors = plt.cm.tab20(range(len(sectors)))
    sector_color_map = {s: sector_colors[i] for i, s in enumerate(sectors)}

    for c in instance.customers_info:
        sec = c.get("sector", "?")
        ax.scatter(
            [c["node_longitude"]], [c["node_latitude"]],
            color=sector_color_map[sec], s=40, marker="o",
            edgecolors="white", linewidths=0.5, zorder=5,
        )
        ax.annotate(
            f"C{c['id']}", (c["node_longitude"], c["node_latitude"]),
            fontsize=5, color="#2c3e50", zorder=6,
        )

    ax.set_title(
        f"Customer & Depot Distribution — {len(instance.sectors_used)} Sectors",
        fontsize=12, fontweight="bold", pad=10,
    )
    ax.legend(loc="upper left", frameon=True, facecolor="white",
              edgecolor="none", fontsize=7)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"[VIZ] Distribution plot saved: {save_path}")

    try:
        plt.show(block=False)
        plt.pause(0.5)
    except Exception:
        pass
    finally:
        plt.close(fig)
