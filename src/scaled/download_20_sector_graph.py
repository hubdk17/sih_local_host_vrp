"""
download_20_sector_graph.py

Downloads a 20-sector Chandigarh road network graph from OpenStreetMap
and saves it as a GraphML file for the scaled MDVRP experiment.

Selected 20 sectors (contiguous central-to-south block):
  Sectors 7, 8, 9, 10, 11, 15, 16, 17, 18, 19,
          20, 21, 22, 23, 24, 25, 26, 27, 34, 35
"""

import os
import sys
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "scaled")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "scale_20_sectors")
GRAPHML_PATH = os.path.join(DATA_DIR, "chandigarh_20_sectors.graphml")
VIZ_PATH = os.path.join(OUTPUT_DIR, "chandigarh_20_sectors_network.png")

# 20 contiguous Chandigarh sectors
SECTORS = [
    "Sector 7, Chandigarh, India",
    "Sector 8, Chandigarh, India",
    "Sector 9, Chandigarh, India",
    "Sector 10, Chandigarh, India",
    "Sector 11, Chandigarh, India",
    "Sector 15, Chandigarh, India",
    "Sector 16, Chandigarh, India",
    "Sector 17, Chandigarh, India",
    "Sector 18, Chandigarh, India",
    "Sector 19, Chandigarh, India",
    "Sector 20, Chandigarh, India",
    "Sector 21, Chandigarh, India",
    "Sector 22, Chandigarh, India",
    "Sector 23, Chandigarh, India",
    "Sector 24, Chandigarh, India",
    "Sector 25, Chandigarh, India",
    "Sector 26, Chandigarh, India",
    "Sector 27, Chandigarh, India",
    "Sector 34, Chandigarh, India",
    "Sector 35, Chandigarh, India",
]

# Fallback bounding box covering the full 20-sector region
# North: ~30.76, South: ~30.69, East: ~76.83, West: ~76.75
BBOX_BOUNDS = (30.7650, 30.6900, 76.8350, 76.7450)


def load_or_download_graph() -> nx.MultiDiGraph:
    """Load existing GraphML file if cached; otherwise download from OSMnx."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(GRAPHML_PATH):
        print(f"[CACHE] Loading existing 20-sector graph from: {GRAPHML_PATH}")
        G = ox.load_graphml(GRAPHML_PATH)
        print("[CACHE] Graph successfully loaded from local cache.\n")
    else:
        print("[DOWNLOAD] Downloading drivable road network for 20 Chandigarh sectors...")
        print(f"  Sectors: {[s.split(',')[0] for s in SECTORS]}")
        try:
            G = ox.graph_from_place(SECTORS, network_type="drive")
        except Exception as e:
            print(f"[WARNING] Place query failed: {e}")
            print(f"[FALLBACK] Querying by bounding box: {BBOX_BOUNDS}...")
            G = ox.graph_from_bbox(bbox=BBOX_BOUNDS, network_type="drive")

        ox.save_graphml(G, GRAPHML_PATH)
        print(f"[SAVE] Graph saved to: {GRAPHML_PATH}\n")

    return G


def compute_and_print_stats(G: nx.MultiDiGraph) -> dict:
    """Compute and print detailed graph statistics."""
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)
    scc = nx.number_strongly_connected_components(G)
    wcc = nx.number_weakly_connected_components(G)

    lengths = []
    for _, _, _, data in G.edges(keys=True, data=True):
        if "length" in data:
            try:
                lengths.append(float(data["length"]))
            except (ValueError, TypeError):
                pass

    lats = [float(d["y"]) for _, d in G.nodes(data=True) if "y" in d]
    lons = [float(d["x"]) for _, d in G.nodes(data=True) if "x" in d]

    stats = {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "scc": scc,
        "wcc": wcc,
        "min_edge_m": min(lengths) if lengths else 0,
        "max_edge_m": max(lengths) if lengths else 0,
        "mean_edge_m": sum(lengths) / len(lengths) if lengths else 0,
        "lat_range": (min(lats), max(lats)) if lats else (0, 0),
        "lon_range": (min(lons), max(lons)) if lons else (0, 0),
    }

    print("==================================================")
    print("    20-SECTOR ROAD NETWORK GRAPH STATISTICS       ")
    print("==================================================")
    print(f"Number of Nodes                : {num_nodes}")
    print(f"Number of Edges                : {num_edges}")
    print(f"Strongly Connected Components  : {scc}")
    print(f"Weakly Connected Components    : {wcc}")
    print(f"Edge Length (m) — min/mean/max  : {stats['min_edge_m']:.1f} / {stats['mean_edge_m']:.1f} / {stats['max_edge_m']:.1f}")
    print(f"Latitude  Range                : {stats['lat_range'][0]:.5f}° to {stats['lat_range'][1]:.5f}°")
    print(f"Longitude Range                : {stats['lon_range'][0]:.5f}° to {stats['lon_range'][1]:.5f}°")
    print("==================================================\n")

    return stats


def visualize_network(G: nx.MultiDiGraph):
    """Plot and save the 20-sector road network."""
    print("[VISUALIZATION] Generating 20-sector road network plot...")

    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=False,
        node_size=5,
        node_color="#e74c3c",
        edge_color="#2c3e50",
        edge_linewidth=0.8,
        bgcolor="#ffffff",
    )

    ax.set_title(
        "Chandigarh Road Network — 20 Sectors (Scaled Experiment)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    fig.tight_layout()
    fig.savefig(VIZ_PATH, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Saved to: {VIZ_PATH}")

    try:
        if sys.flags.interactive or hasattr(sys, "ps1"):
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
    print("  DOWNLOAD 20-SECTOR CHANDIGARH ROAD NETWORK      ")
    print("==================================================\n")

    G = load_or_download_graph()
    stats = compute_and_print_stats(G)
    visualize_network(G)

    print("[SUCCESS] 20-sector road network ready.")
    print(f"  GraphML path : {GRAPHML_PATH}")
    print(f"  Nodes: {stats['num_nodes']}  Edges: {stats['num_edges']}")


if __name__ == "__main__":
    main()
