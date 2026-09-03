"""
download_mumbai_graph.py

Downloads and caches the complete road network graph covering Mumbai, Maharashtra, India.
Extracts the largest Strongly Connected Component (SCC) to guarantee 100% reachability.
Annotates edges with length, speed, and travel times.
"""

import os
import sys
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "mumbai")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ga", "mumbai")
GRAPHML_PATH = os.path.join(DATA_DIR, "mumbai_road_network.graphml")
VIZ_PATH = os.path.join(OUTPUT_DIR, "mumbai_network_map.png")

def download_or_load_mumbai():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(GRAPHML_PATH):
        print(f"[CACHE] Loading cached Mumbai road network from: {GRAPHML_PATH}", flush=True)
        G = ox.load_graphml(GRAPHML_PATH)
        print(f"[CACHE] Loaded: {len(G.nodes)} nodes, {len(G.edges)} edges\n", flush=True)
        return G

    print("[DOWNLOAD] Querying OpenStreetMap via OSMnx for Mumbai, Maharashtra, India...", flush=True)
    custom_filter = '["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified"]'

    # Bounding box format in OSMnx: (left, bottom, right, top) = (west, south, east, north)
    # Mumbai Peninsula: West 72.77, South 18.89 (Colaba), East 72.99 (Thane Creek), North 19.27 (Dahisar)
    mumbai_bbox = (72.77, 18.89, 72.99, 19.27)
    print(f"[DOWNLOAD] Fetching Mumbai road graph with bounding box {mumbai_bbox}...", flush=True)
    G_raw = ox.graph_from_bbox(bbox=mumbai_bbox, custom_filter=custom_filter, simplify=True)

    print(f"[RAW] Downloaded: {len(G_raw.nodes)} nodes, {len(G_raw.edges)} edges", flush=True)

    print("[PROCESSING] Extracting largest strongly connected component (SCC)...", flush=True)
    largest_scc = max(nx.strongly_connected_components(G_raw), key=len)
    G = G_raw.subgraph(largest_scc).copy()

    # Annotate edges with length, speed, and travel times
    for u, v, k, data in G.edges(keys=True, data=True):
        length_m = float(data.get("length", 10.0))
        speed_kmh = 30.0  # Urban traffic speed in Mumbai
        if "maxspeed" in data:
            try:
                ms = data["maxspeed"]
                if isinstance(ms, list): ms = ms[0]
                speed_kmh = float(str(ms).replace("km/h", "").strip())
            except (ValueError, TypeError):
                pass
        speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0)
        data["travel_time"] = length_m / speed_mps
        data["speed_kph"] = speed_kmh

    print(f"[PROCESSED] Mumbai SCC Graph: {len(G.nodes)} nodes, {len(G.edges)} edges", flush=True)

    # Save GraphML
    ox.save_graphml(G, GRAPHML_PATH)
    print(f"[SAVE] Cached Mumbai road network to: {GRAPHML_PATH}", flush=True)

    # Generate base network visualization
    print("[VIZ] Rendering Mumbai road network map...", flush=True)
    fig, ax = plt.subplots(figsize=(10, 14))
    for u, v, data in G.edges(data=True):
        ux, uy = G.nodes[u]['x'], G.nodes[u]['y']
        vx, vy = G.nodes[v]['x'], G.nodes[v]['y']
        ax.plot([ux, vx], [uy, vy], color='#2c3e50', linewidth=0.6, alpha=0.7)

    degrees = dict(G.degree())
    hub_node = max(degrees.keys(), key=lambda n: degrees[n])
    hub_x, hub_y = G.nodes[hub_node]['x'], G.nodes[hub_node]['y']
    ax.scatter(hub_x, hub_y, color='#e74c3c', s=180, marker='*', edgecolor='black', linewidth=1.5,
               label=f"Central Hub Node {hub_node} (Degree={degrees[hub_node]})", zorder=5)

    ax.set_title("Mumbai Road Network Graph (OSMnx Drive Network)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc='lower right')
    ax.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(VIZ_PATH, dpi=300)
    plt.close()
    print(f"[SAVE] Mumbai network map saved to: {VIZ_PATH}", flush=True)

    return G

if __name__ == "__main__":
    download_or_load_mumbai()
