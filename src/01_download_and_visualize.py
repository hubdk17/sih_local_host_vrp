"""
01_download_and_visualize.py

Milestone 1: Download, validate, and visualize Chandigarh's road network graph
from OpenStreetMap using OSMnx.

Geographic scope: Sectors 17, 18, 19, and 20 of Chandigarh, India.
Network type: 'drive' (directed drivable road network).
"""

import os
import sys
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

# Define directory paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
GRAPHML_PATH = os.path.join(DATA_DIR, "chandigarh_subset.graphml")
VIZ_PATH = os.path.join(OUTPUT_DIR, "chandigarh_road_network.png")

# Target sectors in Chandigarh
SECTORS = [
    "Sector 17, Chandigarh, India",
    "Sector 18, Chandigarh, India",
    "Sector 19, Chandigarh, India",
    "Sector 20, Chandigarh, India"
]

# Fallback bounding box (North, South, East, West) in case sector name geocoding fails
BBOX_BOUNDS = (30.7500, 30.7150, 76.8100, 76.7700)


def load_or_download_graph() -> nx.MultiDiGraph:
    """Load existing GraphML file if cached; otherwise download from OSMnx."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(GRAPHML_PATH):
        print(f"[CACHE] Loading existing road network graph from: {GRAPHML_PATH}")
        G = ox.load_graphml(GRAPHML_PATH)
        print("[CACHE] Graph successfully loaded from local cache.\n")
    else:
        print("[DOWNLOAD] Downloading drivable road network for Chandigarh Sectors 17, 18, 19, 20...")
        try:
            G = ox.graph_from_place(SECTORS, network_type="drive")
        except Exception as e:
            print(f"[WARNING] Place query failed with error: {e}")
            print(f"[FALLBACK] Querying by bounding box: {BBOX_BOUNDS}...")
            G = ox.graph_from_bbox(bbox=BBOX_BOUNDS, network_type="drive")

        # Save graph locally for reproducibility
        ox.save_graphml(G, GRAPHML_PATH)
        print(f"[SAVE] Downloaded graph saved locally to: {GRAPHML_PATH}\n")

    return G


def compute_statistics(G: nx.MultiDiGraph) -> dict:
    """Compute and print detailed graph statistics."""
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)

    scc_count = nx.number_strongly_connected_components(G)
    wcc_count = nx.number_weakly_connected_components(G)

    lengths = []
    for _, _, _, data in G.edges(keys=True, data=True):
        if 'length' in data:
            try:
                lengths.append(float(data['length']))
            except (ValueError, TypeError):
                pass

    min_len = min(lengths) if lengths else 0.0
    max_len = max(lengths) if lengths else 0.0
    mean_len = sum(lengths) / len(lengths) if lengths else 0.0

    lats = [float(data['y']) for _, data in G.nodes(data=True) if 'y' in data]
    lons = [float(data['x']) for _, data in G.nodes(data=True) if 'x' in data]

    min_lat, max_lat = (min(lats), max(lats)) if lats else (0.0, 0.0)
    min_lon, max_lon = (min(lons), max(lons)) if lons else (0.0, 0.0)

    stats = {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "strongly_connected_components": scc_count,
        "weakly_connected_components": wcc_count,
        "min_edge_length_m": min_len,
        "max_edge_length_m": max_len,
        "mean_edge_length_m": mean_len,
        "bounding_box": {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon
        }
    }

    print("==================================================")
    print("           ROAD NETWORK GRAPH STATISTICS          ")
    print("==================================================")
    print(f"Number of Nodes                : {num_nodes}")
    print(f"Number of Edges                : {num_edges}")
    print(f"Strongly Connected Components  : {scc_count}")
    print(f"Weakly Connected Components    : {wcc_count}")
    print(f"Minimum Edge Length (meters)   : {min_len:.2f} m")
    print(f"Maximum Edge Length (meters)   : {max_len:.2f} m")
    print(f"Mean Edge Length (meters)      : {mean_len:.2f} m")
    print(f"Geographic Bounding Box        :")
    print(f"  Latitude  (South -> North)   : {min_lat:.5f}° N to {max_lat:.5f}° N")
    print(f"  Longitude (West  -> East)    : {min_lon:.5f}° E to {max_lon:.5f}° E")
    print("==================================================\n")

    return stats


def validate_graph(G: nx.MultiDiGraph, stats: dict) -> bool:
    """Validate that the graph meets routing requirements."""
    print("==================================================")
    print("             GRAPH VALIDATION REPORT              ")
    print("==================================================")

    checks = []

    # 1. Non-empty check
    non_empty = stats["num_nodes"] > 0 and stats["num_edges"] > 0
    checks.append(("Graph non-empty check", non_empty, f"Nodes={stats['num_nodes']}, Edges={stats['num_edges']}"))

    # 2. Edge length check
    has_lengths = all('length' in d for _, _, _, d in G.edges(keys=True, data=True))
    checks.append(("Edge length information present", has_lengths, f"All {stats['num_edges']} edges have length attribute"))

    # 3. Node coordinates check
    has_coords = all('x' in d and 'y' in d for _, d in G.nodes(data=True))
    checks.append(("Node latitude/longitude available", has_coords, f"All {stats['num_nodes']} nodes have x/y coordinates"))

    # 4. Driving network / directed check
    is_directed = G.is_directed()
    checks.append(("Directed routing graph suitable for driving", is_directed, f"is_directed={is_directed}"))

    # 5. Coordinate sanity check for Chandigarh area
    bbox = stats["bounding_box"]
    coords_valid = (30.5 <= bbox["min_lat"] <= bbox["max_lat"] <= 31.0) and (76.5 <= bbox["min_lon"] <= bbox["max_lon"] <= 77.2)
    checks.append(("Coordinates within valid Chandigarh bounds", coords_valid, f"Lat: [{bbox['min_lat']:.4f}, {bbox['max_lat']:.4f}], Lon: [{bbox['min_lon']:.4f}, {bbox['max_lon']:.4f}]"))

    all_passed = True
    for name, passed, detail in checks:
        status = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"{status} {name}: {detail}")

    print("--------------------------------------------------")
    print(f"Overall Validation Status: {'[PASSED]' if all_passed else '[FAILED]'}")
    print("==================================================\n")

    return all_passed


def visualize_network(G: nx.MultiDiGraph):
    """Plot and save the road network visualization cleanly."""
    print(f"[VISUALIZATION] Generating road network plot...")
    
    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=True,
        filepath=VIZ_PATH,
        dpi=300,
        node_size=12,
        node_color="#e74c3c",
        edge_color="#2c3e50",
        edge_linewidth=1.2,
        bgcolor="#ffffff"
    )
    
    ax.set_title("Chandigarh Road Network (Sectors 17, 18, 19, 20)", fontsize=14, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(VIZ_PATH, dpi=300, bbox_inches="tight")
    print(f"[VISUALIZATION] Road network visualization saved to: {VIZ_PATH}")

    # Display plot interactively if run in an interactive environment
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
    print("Starting Milestone 1: Chandigarh Road Network Download & Visualization\n")
    
    # 1. Load or download network graph
    G = load_or_download_graph()

    # 2. Compute graph statistics
    stats = compute_statistics(G)

    # 3. Validate graph integrity
    valid = validate_graph(G, stats)

    # 4. Generate & display visualization
    visualize_network(G)

    if valid:
        print("[SUCCESS] Milestone 1 completed successfully.")
    else:
        print("[WARNING] Milestone 1 completed with validation warnings.")


if __name__ == "__main__":
    main()
