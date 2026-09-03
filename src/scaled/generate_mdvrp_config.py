"""
generate_mdvrp_config.py

Generates the Multi-Depot VRP configuration file for the 20-sector scaled experiment.

Creates:
  - 4 depots at geographically distributed Chandigarh locations
  - 40 customers (2 per sector across 20 sectors)
  - 8 vehicles (2 per depot)

All locations are mapped to actual OSM graph nodes.
"""

import json
import os
import sys
import random
import networkx as nx
import osmnx as ox
import networkx as nx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

GRAPHML_PATH = os.path.join(BASE_DIR, "data", "scaled", "chandigarh_20_sectors.graphml")
CONFIG_PATH = os.path.join(BASE_DIR, "data", "scaled", "mdvrp_config.json")

# Reproducible random seed
RANDOM_SEED = 42

# 20 sectors used in the experiment
SECTOR_NAMES = [
    "Sector 7", "Sector 8", "Sector 9", "Sector 10", "Sector 11",
    "Sector 15", "Sector 16", "Sector 17", "Sector 18", "Sector 19",
    "Sector 20", "Sector 21", "Sector 22", "Sector 23", "Sector 24",
    "Sector 25", "Sector 26", "Sector 27", "Sector 34", "Sector 35",
]

# Approximate center coordinates for each sector (lat, lon)
# Used to sample nearby graph nodes for customers
SECTOR_CENTERS = {
    "Sector 7":  (30.7550, 76.7880),
    "Sector 8":  (30.7530, 76.7760),
    "Sector 9":  (30.7530, 76.8010),
    "Sector 10": (30.7460, 76.8010),
    "Sector 11": (30.7460, 76.7760),
    "Sector 15": (30.7430, 76.7780),
    "Sector 16": (30.7430, 76.7680),
    "Sector 17": (30.7350, 76.7850),
    "Sector 18": (30.7250, 76.7830),
    "Sector 19": (30.7290, 76.7920),
    "Sector 20": (30.7270, 76.7900),
    "Sector 21": (30.7200, 76.7870),
    "Sector 22": (30.7330, 76.7650),
    "Sector 23": (30.7290, 76.7640),
    "Sector 24": (30.7190, 76.7770),
    "Sector 25": (30.7150, 76.7680),
    "Sector 26": (30.7100, 76.7780),
    "Sector 27": (30.7100, 76.7880),
    "Sector 34": (30.7080, 76.7650),
    "Sector 35": (30.7050, 76.7780),
}

# 4 Depot locations — geographically distributed logistics-like sites
DEPOT_SPECS = [
    {
        "id": 0,
        "name": "Depot 1 — Sector 17 ISBT (North-Central)",
        "lat": 30.7398,
        "lon": 76.7827,
    },
    {
        "id": 1,
        "name": "Depot 2 — Sector 22 (West)",
        "lat": 30.7330,
        "lon": 76.7650,
    },
    {
        "id": 2,
        "name": "Depot 3 — Sector 26 (South)",
        "lat": 30.7100,
        "lon": 76.7780,
    },
    {
        "id": 3,
        "name": "Depot 4 — Sector 9 (North-East)",
        "lat": 30.7530,
        "lon": 76.8010,
    },
]


def generate_config():
    random.seed(RANDOM_SEED)

    print("[LOAD] Loading 20-sector graph...")
    if not os.path.exists(GRAPHML_PATH):
        print(f"[ERROR] Graph not found at {GRAPHML_PATH}. Run download_20_sector_graph.py first.")
        sys.exit(1)

    G_full = ox.load_graphml(GRAPHML_PATH)
    # Use largest strongly connected component for guaranteed reachability
    largest_scc = max(nx.strongly_connected_components(G_full), key=len)
    G = G_full.subgraph(largest_scc).copy()
    print(f"[LOAD] Graph loaded: {len(G_full.nodes)} total nodes -> {len(G.nodes)} in largest SCC, {len(G.edges)} edges\n")

    # --- Map depots to nearest graph nodes ---
    depots = []
    used_nodes = set()
    for spec in DEPOT_SPECS:
        nearest = ox.distance.nearest_nodes(G, X=spec["lon"], Y=spec["lat"])
        node_data = G.nodes[nearest]
        depots.append({
            "id": spec["id"],
            "name": spec["name"],
            "latitude": spec["lat"],
            "longitude": spec["lon"],
            "nearest_node_id": nearest,
            "node_latitude": node_data["y"],
            "node_longitude": node_data["x"],
        })
        used_nodes.add(nearest)
        print(f"  Depot {spec['id']}: {spec['name']} -> node {nearest}")

    # --- Generate customers (2 per sector = 40 total) ---
    customers = []
    cust_id = 1
    for sector in SECTOR_NAMES:
        center_lat, center_lon = SECTOR_CENTERS[sector]

        # Find graph nodes near this sector center
        nearest_node = ox.distance.nearest_nodes(G, X=center_lon, Y=center_lat)

        # Get nearby nodes within a small radius for diversity
        all_nodes = list(G.nodes)
        # Sort all nodes by distance to center
        def node_dist(n):
            nd = G.nodes[n]
            return (float(nd["y"]) - center_lat) ** 2 + (float(nd["x"]) - center_lon) ** 2

        sorted_nodes = sorted(all_nodes, key=node_dist)

        # Pick 2 distinct nodes not already used
        picked = 0
        for candidate in sorted_nodes:
            if candidate in used_nodes:
                continue
            nd = G.nodes[candidate]
            demand = random.randint(1, 5)
            customers.append({
                "id": cust_id,
                "name": f"Customer {cust_id} ({sector})",
                "sector": sector,
                "latitude": float(nd["y"]),
                "longitude": float(nd["x"]),
                "demand": demand,
                "nearest_node_id": candidate,
                "node_latitude": float(nd["y"]),
                "node_longitude": float(nd["x"]),
            })
            used_nodes.add(candidate)
            cust_id += 1
            picked += 1
            if picked >= 2:
                break

    print(f"\n  Generated {len(customers)} customers across {len(SECTOR_NAMES)} sectors")

    # --- Vehicles: 2 per depot = 8 total ---
    vehicles = []
    vehicle_id = 0
    for depot in depots:
        for v_idx in range(2):
            vehicles.append({
                "id": vehicle_id,
                "home_depot_id": depot["id"],
                "capacity": 20,
            })
            vehicle_id += 1

    print(f"  Generated {len(vehicles)} vehicles (2 per depot)")

    # --- Build config ---
    config = {
        "instance_name": "Chandigarh_20_Sector_MDVRP",
        "description": (
            "Multi-Depot VRP on 20 Chandigarh sectors. "
            "4 depots, 40 customers, 8 vehicles. "
            f"Sectors: {', '.join(SECTOR_NAMES)}"
        ),
        "sectors_used": SECTOR_NAMES,
        "depots": depots,
        "customers": customers,
        "vehicles": {
            "list": vehicles,
            "count": len(vehicles),
            "default_capacity": 20,
            "max_route_duration_sec": 5400.0,
        },
        "road_capacities": {
            "primary": 10,
            "secondary": 7,
            "tertiary": 5,
            "residential": 3,
            "service": 2,
            "default": 3,
        },
        "road_speeds_kmh": {
            "primary": 40.0,
            "secondary": 35.0,
            "tertiary": 30.0,
            "residential": 20.0,
            "service": 15.0,
            "default": 20.0,
        },
    }

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVE] Config saved to: {CONFIG_PATH}")

    # Print summary
    total_demand = sum(c["demand"] for c in customers)
    total_capacity = sum(v["capacity"] for v in vehicles)
    print(f"\n  Total customer demand : {total_demand}")
    print(f"  Total vehicle capacity: {total_capacity}")
    print(f"  Utilization ratio     : {total_demand / total_capacity * 100:.1f}%")

    return config


if __name__ == "__main__":
    print("==================================================")
    print("  GENERATE MULTI-DEPOT VRP CONFIGURATION          ")
    print("==================================================\n")
    generate_config()
    print("\n[SUCCESS] MDVRP configuration generated.")
