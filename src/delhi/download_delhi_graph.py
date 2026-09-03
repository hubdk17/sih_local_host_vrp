"""
download_delhi_graph.py

Downloads and caches a drivable road network graph for a major region of Delhi, India
(covering Central, New Delhi, and South Delhi hubs) using OSMnx.

Extracts the largest strongly connected component (SCC) to guarantee 100% routing reachability.
"""

import os
import sys
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "delhi")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "delhi")
GRAPHML_PATH = os.path.join(DATA_DIR, "delhi_road_network.graphml")
VIZ_PATH = os.path.join(OUTPUT_DIR, "delhi_base_network.png")

# Geographic Bounding Box covering Central & South-Central Delhi (Connaught Place to Saket/AIIMS)
# North: 28.6400, South: 28.5300, East: 77.2500, West: 77.1800
BBOX_DELHI = (28.6400, 28.5300, 77.2500, 77.1800)

PLACES_DELHI = [
    "New Delhi, India",
    "Central Delhi, India",
    "South Delhi, India"
]


def load_or_download_graph() -> nx.MultiDiGraph:
    """Load cached Delhi GraphML or download from OpenStreetMap using OSMnx."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(GRAPHML_PATH):
        print(f"[CACHE] Loading existing Delhi road network from: {GRAPHML_PATH}")
        G_full = ox.load_graphml(GRAPHML_PATH)
        print("[CACHE] Loaded from local cache.\n")
    else:
        print("[DOWNLOAD] Downloading drivable road network for New Delhi, India...")
        G_full = ox.graph_from_place("New Delhi, India", network_type="drive")

        # Filter to largest strongly connected component (SCC) to guarantee reachability
        largest_scc = max(nx.strongly_connected_components(G_full), key=len)
        G_full = G_full.subgraph(largest_scc).copy()

        ox.save_graphml(G_full, GRAPHML_PATH)
        print(f"[SAVE] Delhi road network graph saved to: {GRAPHML_PATH}\n")

    # Extract largest SCC for routing guarantee
    largest_scc = max(nx.strongly_connected_components(G_full), key=len)
    G = G_full.subgraph(largest_scc).copy()
    return G


def compute_statistics(G: nx.MultiDiGraph) -> dict:
    """Compute and display detailed statistics of the Delhi road graph."""
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)

    scc_count = nx.number_strongly_connected_components(G)
    wcc_count = nx.number_weakly_connected_components(G)

    lengths = [float(d["length"]) for _, _, _, d in G.edges(keys=True, data=True) if "length" in d]
    lats = [float(d["y"]) for _, d in G.nodes(data=True) if "y" in d]
    lons = [float(d["x"]) for _, d in G.nodes(data=True) if "x" in d]

    stats = {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "scc": scc_count,
        "wcc": wcc_count,
        "min_edge_m": min(lengths) if lengths else 0.0,
        "max_edge_m": max(lengths) if lengths else 0.0,
        "mean_edge_m": sum(lengths) / len(lengths) if lengths else 0.0,
        "lat_range": (min(lats), max(lats)) if lats else (0.0, 0.0),
        "lon_range": (min(lons), max(lons)) if lons else (0.0, 0.0),
    }

    print("==================================================")
    print("      DELHI ROAD NETWORK GRAPH STATISTICS         ")
    print("==================================================")
    print(f"Number of Nodes                : {num_nodes}")
    print(f"Number of Edges                : {num_edges}")
    print(f"Strongly Connected Components  : {scc_count}")
    print(f"Weakly Connected Components    : {wcc_count}")
    print(f"Edge Length (meters)           : Min={stats['min_edge_m']:.1f}m, Mean={stats['mean_edge_m']:.1f}m, Max={stats['max_edge_m']:.1f}m")
    print(f"Latitude Range                 : {stats['lat_range'][0]:.5f}° N to {stats['lat_range'][1]:.5f}° N")
    print(f"Longitude Range                : {stats['lon_range'][0]:.5f}° E to {stats['lon_range'][1]:.5f}° E")
    print("==================================================\n")

    return stats


def visualize_network(G: nx.MultiDiGraph):
    """Render and save Delhi base road network visualization."""
    print("[VISUALIZATION] Rendering Delhi road network plot...")
    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=False,
        node_size=3,
        node_color="#e74c3c",
        edge_color="#2c3e50",
        edge_linewidth=0.6,
        bgcolor="#ffffff"
    )

    ax.set_title("Delhi Major Road Network (Central & South Delhi Region)", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(VIZ_PATH, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Saved to: {VIZ_PATH}")

    try:
        if sys.flags.interactive or hasattr(sys, 'ps1'):
            plt.show()
        else:
            plt.show(block=False)
            plt.pause(0.5)
    except Exception:
        pass
    finally:
        plt.close(fig)


def main():
    print("==================================================")
    print("      DOWNLOAD DELHI ROAD NETWORK GRAPH           ")
    print("==================================================\n")

    G = load_or_download_graph()
    stats = compute_statistics(G)
    visualize_network(G)

    print("[SUCCESS] Delhi road network download & processing complete.")


if __name__ == "__main__":
    main()
