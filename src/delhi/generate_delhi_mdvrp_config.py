"""
generate_delhi_mdvrp_config.py

Generates the Multi-Depot VRP configuration file for the Delhi road network experiment.

Creates:
  - 4 depots at major Delhi logistics/transport hubs
  - 50 customers distributed across Delhi commercial & residential hubs
  - 10 vehicles (assigned across 4 depots)

Maps all locations to nearest valid nodes in the Delhi OSM graph.
"""

import json
import os
import sys
import random
import networkx as nx
import osmnx as ox

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

GRAPHML_PATH = os.path.join(BASE_DIR, "data", "delhi", "delhi_road_network.graphml")
CONFIG_PATH = os.path.join(BASE_DIR, "data", "delhi", "delhi_mdvrp_config.json")

RANDOM_SEED = 42

# 4 Major Delhi Logistics & Transport Hubs
DELHI_DEPOT_SPECS = [
    {
        "id": 0,
        "name": "Depot 1 — ISBT Kashmere Gate (North Hub)",
        "lat": 28.6672,
        "lon": 77.2284,
    },
    {
        "id": 1,
        "name": "Depot 2 — Connaught Place (Central Logistics Hub)",
        "lat": 28.6315,
        "lon": 77.2167,
    },
    {
        "id": 2,
        "name": "Depot 3 — AIIMS / Ring Road (South-Central Hub)",
        "lat": 28.5672,
        "lon": 77.2100,
    },
    {
        "id": 3,
        "name": "Depot 4 — Lajpat Nagar / Okhla (South-East Hub)",
        "lat": 28.5685,
        "lon": 77.2435,
    },
]

# 25 Prominent Delhi Localities / Commercial Hubs (2 customers per locality = 50 customers)
DELHI_LOCALITIES = [
    ("Connaught Place", (28.6315, 77.2167)),
    ("Khan Market", (28.6002, 77.2270)),
    ("Karol Bagh", (28.6514, 77.1907)),
    ("Lajpat Nagar", (28.5685, 77.2435)),
    ("Saket Commercial Hub", (28.5244, 77.2185)),
    ("Hauz Khas Village", (28.5529, 77.1944)),
    ("Nehru Place Financial Center", (28.5492, 77.2517)),
    ("Greater Kailash I", (28.5532, 77.2343)),
    ("Chanakyapuri Embassy Area", (28.5983, 77.1923)),
    ("Dhaula Kuan Junction", (28.5919, 77.1616)),
    ("Nizamuddin East", (28.5912, 77.2492)),
    ("Defense Colony", (28.5728, 77.2309)),
    ("Green Park Commercial", (28.5584, 77.2062)),
    ("Malviya Nagar Market", (28.5360, 77.2105)),
    ("Sarojini Nagar Market", (28.5760, 77.1979)),
    ("Lodhi Estate", (28.5925, 77.2195)),
    ("Vasant Vihar Hub", (28.5570, 77.1620)),
    ("R.K. Puram Sector 1", (28.5660, 77.1760)),
    ("South Extension Market", (28.5700, 77.2200)),
    ("Moti Bagh Commercial", (28.5830, 77.1700)),
    ("Kalkaaji Market", (28.5440, 77.2580)),
    ("Munirka Market", (28.5550, 77.1730)),
    ("Chirag Delhi Junction", (28.5410, 77.2260)),
    ("Panchsheel Park", (28.5450, 77.2150)),
    ("Jangpura Hub", (28.5800, 77.2450)),
]


def generate_config():
    random.seed(RANDOM_SEED)

    print("[LOAD] Loading Delhi road graph...")
    if not os.path.exists(GRAPHML_PATH):
        print(f"[ERROR] GraphML file not found at: {GRAPHML_PATH}. Run download_delhi_graph.py first.")
        sys.exit(1)

    G_full = ox.load_graphml(GRAPHML_PATH)
    largest_scc = max(nx.strongly_connected_components(G_full), key=len)
    G = G_full.subgraph(largest_scc).copy()

    print(f"[LOAD] Graph loaded: {len(G_full.nodes)} total nodes -> {len(G.nodes)} in largest SCC, {len(G.edges)} edges\n")

    # --- Map depots to high-capacity major road junction nodes ---
    # Find all nodes where all connected edges are primary/secondary/trunk (capacity >= 10)
    high_cap_nodes = set()
    for n in G.nodes:
        # Check incident edges
        incident_edges = list(G.in_edges(n, data=True)) + list(G.out_edges(n, data=True))
        if not incident_edges:
            continue
        all_high = True
        for u_e, v_e, data in incident_edges:
            hw = data.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0]
            if hw not in ["primary", "secondary", "trunk", "motorway"]:
                all_high = False
                break
        if all_high:
            high_cap_nodes.add(n)

    if not high_cap_nodes:
        # Fallback to any node with at least one primary edge
        for u, v, k, data in G.edges(keys=True, data=True):
            hw = data.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0]
            if hw in ["primary", "secondary", "trunk", "motorway"]:
                high_cap_nodes.add(u)
                high_cap_nodes.add(v)

    if not high_cap_nodes:
        high_cap_nodes = set(G.nodes)

    depots = []
    used_nodes = set()
    for spec in DELHI_DEPOT_SPECS:
        # Find nearest node among high capacity major road nodes
        cand_list = list(high_cap_nodes - used_nodes)
        def node_dist(n):
            nd = G.nodes[n]
            return (float(nd["y"]) - spec["lat"]) ** 2 + (float(nd["x"]) - spec["lon"]) ** 2
        nearest = min(cand_list, key=node_dist)

        node_data = G.nodes[nearest]
        depots.append({
            "id": spec["id"],
            "name": spec["name"],
            "latitude": spec["lat"],
            "longitude": spec["lon"],
            "nearest_node_id": nearest,
            "node_latitude": float(node_data["y"]),
            "node_longitude": float(node_data["x"]),
        })
        used_nodes.add(nearest)
        print(f"  Depot {spec['id']}: {spec['name']} -> primary/secondary node {nearest}")

    # Generate 50 Customers (2 per locality across 25 localities)
    customers = []
    cust_id = 1
    all_nodes = list(G.nodes)

    for loc_name, (center_lat, center_lon) in DELHI_LOCALITIES:
        def node_dist(n):
            nd = G.nodes[n]
            return (float(nd["y"]) - center_lat) ** 2 + (float(nd["x"]) - center_lon) ** 2

        sorted_nodes = sorted(all_nodes, key=node_dist)

        picked = 0
        for candidate in sorted_nodes:
            if candidate in used_nodes:
                continue
            nd = G.nodes[candidate]
            demand = random.randint(1, 5)
            customers.append({
                "id": cust_id,
                "name": f"Customer {cust_id} ({loc_name})",
                "locality": loc_name,
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

    print(f"\n  Generated {len(customers)} customers across {len(DELHI_LOCALITIES)} Delhi localities")

    # Generate 10 Vehicles (2 to 3 per depot)
    vehicles = []
    vehicle_id = 0
    # Depots 0 and 1 get 3 vehicles, Depots 2 and 3 get 2 vehicles (Total = 10 vehicles)
    depot_veh_counts = [3, 3, 2, 2]
    for depot_idx, count in enumerate(depot_veh_counts):
        for _ in range(count):
            vehicles.append({
                "id": vehicle_id,
                "home_depot_id": depot_idx,
                "capacity": 20,
            })
            vehicle_id += 1

    print(f"  Generated {len(vehicles)} vehicles across {len(depots)} depots")

    config = {
        "instance_name": "Delhi_50_Customer_MDVRP",
        "description": "Multi-Depot VRP on Delhi road network. 4 depots, 50 customers, 10 vehicles.",
        "localities_used": [loc for loc, _ in DELHI_LOCALITIES],
        "depots": depots,
        "customers": customers,
        "vehicles": {
            "list": vehicles,
            "count": len(vehicles),
            "default_capacity": 20,
            "max_route_duration_sec": 7200.0,
        },
        "road_capacities": {
            "primary": 15,
            "secondary": 10,
            "tertiary": 8,
            "residential": 6,
            "service": 4,
            "default": 6,
        },
        "road_speeds_kmh": {
            "primary": 45.0,
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
    total_demand = sum(c["demand"] for c in customers)
    total_capacity = sum(v["capacity"] for v in vehicles)
    print(f"  Total demand   : {total_demand}")
    print(f"  Total capacity : {total_capacity}")
    print(f"  Utilization    : {total_demand / total_capacity * 100:.1f}%")

    return config


if __name__ == "__main__":
    print("==================================================")
    print("   GENERATE DELHI MULTI-DEPOT VRP CONFIG          ")
    print("==================================================\n")
    generate_config()
    print("\n[SUCCESS] Delhi MDVRP config generated successfully.")
