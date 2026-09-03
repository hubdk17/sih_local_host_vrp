"""
download_full_delhi_graph.py

Downloads and caches the complete road network graph covering the entire
National Capital Territory (NCT) of Delhi, India.

Covers all 11 revenue districts:
  - North Delhi, North West Delhi, North East Delhi
  - Central Delhi, New Delhi
  - South Delhi, South West Delhi, South East Delhi
  - East Delhi, West Delhi, Shahdara

Uses major drivable road classifications (motorway, trunk, primary, secondary, tertiary, unclassified)
and extracts the largest Strongly Connected Component (SCC) to ensure 100% routing reachability.
"""

import os
import sys
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "delhi")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "delhi")
GRAPHML_PATH = os.path.join(DATA_DIR, "full_delhi_road_network.graphml")
VIZ_PATH = os.path.join(OUTPUT_DIR, "full_delhi_network_map.png")

def download_or_load_full_delhi():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(GRAPHML_PATH):
        print(f"[CACHE] Loading cached Full Delhi road network from: {GRAPHML_PATH}")
        G = ox.load_graphml(GRAPHML_PATH)
        print(f"[CACHE] Successfully loaded: {len(G.nodes)} nodes, {len(G.edges)} edges\n")
        return G

    print("[DOWNLOAD] Querying OpenStreetMap via OSMnx for Full Delhi, India...")
    print("           Target: All major & connecting drivable routes across entire NCT of Delhi.")
    
    # Custom filter to capture all significant drivable roads across the entire state of Delhi
    custom_filter = '["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified"]'
    
    try:
        G_raw = ox.graph_from_place("Delhi, India", custom_filter=custom_filter, simplify=True)
    except Exception as e:
        print(f"[WARN] Place query failed ({e}), falling back to wide bounding box for Delhi NCT...")
        # Bounding box covering full Delhi NCT: North: 28.88, South: 28.40, East: 77.35, West: 76.84
        G_raw = ox.graph_from_bbox(bbox=(28.88, 28.40, 77.35, 76.84), custom_filter=custom_filter, simplify=True)

    print(f"[RAW] Downloaded: {len(G_raw.nodes)} nodes, {len(G_raw.edges)} edges")

    # Extract largest Strongly Connected Component (SCC) to guarantee routing reachability
    print("[PROCESSING] Extracting largest strongly connected component (SCC)...")
    largest_scc = max(nx.strongly_connected_components(G_raw), key=len)
    G = G_raw.subgraph(largest_scc).copy()

    # Annotate edges with length, speed, and travel times
    for u, v, k, data in G.edges(keys=True, data=True):
        length_m = float(data.get("length", 10.0))
        speed_kmh = 35.0
        if "maxspeed" in data:
            try:
                ms = data["maxspeed"]
                if isinstance(ms, list): ms = ms[0]
                speed_kmh = float(str(ms).replace("km/h", "").strip())
            except (ValueError, TypeError):
                pass
        speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0)
        data["travel_time"] = length_m / speed_mps

    print(f"[CLEAN] Final Largest SCC: {len(G.nodes)} nodes, {len(G.edges)} edges")

    # Save to GraphML
    ox.save_graphml(G, GRAPHML_PATH)
    print(f"[SAVE] Full Delhi road network saved to: {GRAPHML_PATH}\n")
    return G

def plot_network(G):
    print("[VISUALIZATION] Rendering Full Delhi road network visualization...")
    fig, ax = ox.plot_graph(
        G,
        show=False,
        close=False,
        save=False,
        node_size=2,
        node_color="#3498db",
        edge_color="#2c3e50",
        edge_linewidth=0.5,
        bgcolor="#ffffff"
    )

    ax.set_title("Full Delhi Road Network Graph (Entire NCT of Delhi)", fontsize=14, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(VIZ_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[VISUALIZATION] Full network map saved to: {VIZ_PATH}")

def main():
    print("=" * 70)
    print("       FULL DELHI ROAD NETWORK DOWNLOAD & EXTRACTION")
    print("=" * 70)
    G = download_or_load_full_delhi()
    
    # Print geographical statistics
    lats = [float(d["y"]) for _, d in G.nodes(data=True) if "y" in d]
    lons = [float(d["x"]) for _, d in G.nodes(data=True) if "x" in d]
    print(f"Total Nodes: {len(G.nodes)}")
    print(f"Total Edges: {len(G.edges)}")
    print(f"Latitude Extent : {min(lats):.4f}° N to {max(lats):.4f}° N (Span: ~{(max(lats)-min(lats))*111:.1f} km)")
    print(f"Longitude Extent: {min(lons):.4f}° E to {max(lons):.4f}° E (Span: ~{(max(lons)-min(lons))*98:.1f} km)")
    
    plot_network(G)
    print("=" * 70)
    print("       FULL DELHI ROAD NETWORK READY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
