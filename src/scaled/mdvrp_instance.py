"""
mdvrp_instance.py

Multi-Depot Vehicle Routing Problem (MDVRP) Instance class.
Handles multiple depots, per-vehicle depot assignments, graph annotation,
and shortest-path precomputation between all depots and customers.
"""

import json
import os
import networkx as nx
import osmnx as ox
from typing import Dict, List, Tuple, Any


class MDVRPInstance:
    """
    Manages a Multi-Depot VRP instance with:
      - Multiple depots
      - Per-vehicle depot assignments
      - Customer demands
      - OSM road graph with travel times and road capacities
      - Precomputed shortest paths
    """

    def __init__(self, config_path: str, graphml_path: str):
        self.config_path = config_path
        self.graphml_path = graphml_path

        # 1. Load config
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # 2. Load graph
        if not os.path.exists(graphml_path):
            raise FileNotFoundError(f"GraphML not found: {graphml_path}")
        G_full = ox.load_graphml(graphml_path)

        # Use largest strongly connected component to guarantee pairwise reachability
        largest_scc = max(nx.strongly_connected_components(G_full), key=len)
        self.graph = G_full.subgraph(largest_scc).copy()

        # 3. Parse config
        self.instance_name = self.config.get("instance_name", "MDVRP")
        self.sectors_used = self.config.get("sectors_used", [])

        # Depots
        self.depots_info = self.config["depots"]
        self.num_depots = len(self.depots_info)
        self.depot_map = {d["id"]: d for d in self.depots_info}

        # Customers
        self.customers_info = self.config["customers"]
        self.num_customers = len(self.customers_info)
        self.customer_ids = [c["id"] for c in self.customers_info]
        self.demands = {c["id"]: c["demand"] for c in self.customers_info}
        self.customer_map = {c["id"]: c for c in self.customers_info}

        # Vehicles
        veh_config = self.config["vehicles"]
        self.vehicles_list = veh_config["list"]
        self.num_vehicles = veh_config["count"]
        self.max_route_duration_sec = veh_config["max_route_duration_sec"]
        self.default_vehicle_capacity = veh_config.get("default_capacity", 20)

        # Build vehicle lookup: vehicle_id -> {home_depot_id, capacity}
        self.vehicle_map = {}
        for v in self.vehicles_list:
            self.vehicle_map[v["id"]] = {
                "home_depot_id": v["home_depot_id"],
                "capacity": v.get("capacity", self.default_vehicle_capacity),
            }

        # Build depot -> vehicles mapping
        self.depot_vehicles = {}
        for v in self.vehicles_list:
            dep_id = v["home_depot_id"]
            self.depot_vehicles.setdefault(dep_id, []).append(v["id"])

        # Road config
        self.road_capacities_config = self.config.get("road_capacities", {})
        self.road_speeds_kmh = self.config.get("road_speeds_kmh", {})

        # Build location_nodes: maps ("depot", depot_id) and ("customer", cust_id) to graph node IDs
        self.location_nodes = {}
        for d in self.depots_info:
            self.location_nodes[("depot", d["id"])] = d["nearest_node_id"]
        for c in self.customers_info:
            self.location_nodes[("customer", c["id"])] = c["nearest_node_id"]

        # 4. Annotate graph edges
        self._annotate_graph_edges()

        # 5. Precompute shortest paths
        self._precompute_shortest_paths()

    def _annotate_graph_edges(self):
        """Annotate each edge with travel_time (seconds) and road_capacity."""
        default_speed = self.road_speeds_kmh.get("default", 20.0)
        default_cap = self.road_capacities_config.get("default", 3)

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            length_m = float(data.get("length", 10.0))
            highway = data.get("highway", "default")
            if isinstance(highway, list):
                highway = highway[0]

            speed_kmh = self.road_speeds_kmh.get(highway, default_speed)
            if "maxspeed" in data:
                try:
                    ms = data["maxspeed"]
                    if isinstance(ms, list):
                        ms = ms[0]
                    speed_kmh = float(str(ms).replace("km/h", "").strip())
                except (ValueError, TypeError):
                    pass

            speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0)
            data["travel_time"] = length_m / speed_mps
            data["road_capacity"] = self.road_capacities_config.get(highway, default_cap)

    def _precompute_shortest_paths(self):
        """
        Precompute shortest paths between all location pairs:
        (depot_i, customer_j), (customer_i, customer_j), (customer_j, depot_i)
        """
        self.shortest_paths = {}

        # Collect all unique graph nodes
        all_loc_keys = list(self.location_nodes.keys())
        unique_nodes = {}
        for key in all_loc_keys:
            node_id = self.location_nodes[key]
            unique_nodes[node_id] = key  # may overwrite, that's fine

        # For each unique source node, run single-source Dijkstra
        node_to_keys = {}
        for key, node_id in self.location_nodes.items():
            node_to_keys.setdefault(node_id, []).append(key)

        unique_node_ids = list(set(self.location_nodes.values()))

        print(f"[MDVRP] Precomputing shortest paths for {len(unique_node_ids)} unique nodes...")

        dijkstra_cache = {}
        for node_id in unique_node_ids:
            times_dict, paths_dict = nx.single_source_dijkstra(
                self.graph, source=node_id, weight="travel_time"
            )
            dijkstra_cache[node_id] = (times_dict, paths_dict)

        # Build all pairwise paths
        for key1 in all_loc_keys:
            node1 = self.location_nodes[key1]
            times_dict, paths_dict = dijkstra_cache[node1]

            for key2 in all_loc_keys:
                if key1 == key2:
                    self.shortest_paths[(key1, key2)] = {
                        "distance": 0.0,
                        "time": 0.0,
                        "node_path": [node1],
                        "edge_path": [],
                    }
                    continue

                node2 = self.location_nodes[key2]
                if node2 not in paths_dict:
                    raise RuntimeError(
                        f"No path from {key1} (node {node1}) to {key2} (node {node2})"
                    )

                node_path = paths_dict[node2]
                path_time = times_dict[node2]

                path_dist = 0.0
                edge_path = []
                for i in range(len(node_path) - 1):
                    u_node = node_path[i]
                    v_node = node_path[i + 1]
                    edge_dict = self.graph[u_node][v_node]
                    min_k = min(edge_dict.keys(), key=lambda k: edge_dict[k].get("travel_time", 0.0))
                    edge_data = edge_dict[min_k]
                    path_dist += float(edge_data.get("length", 0.0))
                    edge_path.append((u_node, v_node, min_k))

                self.shortest_paths[(key1, key2)] = {
                    "distance": path_dist,
                    "time": path_time,
                    "node_path": node_path,
                    "edge_path": edge_path,
                }

        print(f"[MDVRP] Precomputed {len(self.shortest_paths)} shortest path pairs.\n")

    def get_shortest_path(self, loc_key1: Tuple, loc_key2: Tuple) -> dict:
        """Retrieve precomputed shortest path between two location keys."""
        return self.shortest_paths[(loc_key1, loc_key2)]

    def get_edge_road_capacity(self, u: int, v: int, key: int = 0) -> int:
        """Get road capacity for edge (u, v, key)."""
        if self.graph.has_edge(u, v, key):
            return self.graph[u][v][key].get(
                "road_capacity", self.road_capacities_config.get("default", 3)
            )
        return self.road_capacities_config.get("default", 3)

    def get_vehicle_home_depot_key(self, vehicle_id: int) -> Tuple:
        """Return the location key for a vehicle's home depot."""
        depot_id = self.vehicle_map[vehicle_id]["home_depot_id"]
        return ("depot", depot_id)

    def get_vehicle_capacity(self, vehicle_id: int) -> int:
        """Return the capacity for a specific vehicle."""
        return self.vehicle_map[vehicle_id]["capacity"]
