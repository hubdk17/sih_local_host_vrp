"""
vrp_instance.py

VRP Instance class for loading configuration, graph data, mapping customer
locations to OSM graph nodes, and computing shortest paths & travel times.
"""

import json
import os
import networkx as nx
import osmnx as ox

class VRPInstance:
    """
    Manages VRP problem instance parameters, Chandigarh road graph,
    location node mappings, and shortest path precomputations.
    """

    def __init__(self, config_path: str = "data/vrp_config.json", graphml_path: str = "data/raw/chandigarh_subset.graphml"):
        self.config_path = config_path
        self.graphml_path = graphml_path

        # 1. Load config JSON
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # 2. Load GraphML
        if not os.path.exists(graphml_path):
            raise FileNotFoundError(f"GraphML file not found at: {graphml_path}")
        self.graph = ox.load_graphml(graphml_path)

        # Extract parameters
        self.instance_name = self.config.get("instance_name", "Chandigarh_VRP")
        self.depot_info = self.config["depot"]
        self.customers_info = self.config["customers"]
        self.vehicle_config = self.config["vehicles"]
        self.road_capacities_config = self.config.get("road_capacities", {})
        self.road_speeds_kmh = self.config.get("road_speeds_kmh", {})

        self.num_vehicles = self.vehicle_config["count"]
        self.vehicle_capacity = self.vehicle_config["capacity"]
        self.max_route_duration_sec = self.vehicle_config["max_route_duration_sec"]

        # Build customer lookups
        self.num_customers = len(self.customers_info)
        self.customer_ids = [c["id"] for c in self.customers_info]
        self.demands = {c["id"]: c["demand"] for c in self.customers_info}
        self.customer_map = {c["id"]: c for c in self.customers_info}

        # Map locations to graph node IDs
        self.depot_node = self.depot_info["nearest_node_id"]
        self.location_nodes = {0: self.depot_node}
        for c in self.customers_info:
            self.location_nodes[c["id"]] = c["nearest_node_id"]

        # 3. Annotate graph edges with travel times & road capacities
        self._annotate_graph_edges()

        # 4. Precompute shortest paths between all locations (0=depot, 1..N=customers)
        self._precompute_shortest_paths()

    def _annotate_graph_edges(self):
        """Annotate each edge with travel_time (seconds) and static road_capacity."""
        default_speed_kmh = self.road_speeds_kmh.get("default", 20.0)
        default_capacity = self.road_capacities_config.get("default", 3)

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            # Length in meters
            length_m = float(data.get("length", 10.0))

            # Determine speed (m/s)
            highway = data.get("highway", "default")
            if isinstance(highway, list):
                highway = highway[0]
            
            speed_kmh = self.road_speeds_kmh.get(highway, default_speed_kmh)
            
            # Check if OSM maxspeed is present
            if "maxspeed" in data:
                try:
                    maxspeed_val = data["maxspeed"]
                    if isinstance(maxspeed_val, list):
                        maxspeed_val = maxspeed_val[0]
                    speed_kmh = float(str(maxspeed_val).replace("km/h", "").strip())
                except (ValueError, TypeError):
                    pass

            speed_mps = max(speed_kmh * (1000.0 / 3600.0), 1.0) # at least 1 m/s
            travel_time_sec = length_m / speed_mps

            # Road capacity attribute
            capacity = self.road_capacities_config.get(highway, default_capacity)

            data["travel_time"] = travel_time_sec
            data["road_capacity"] = capacity

    def _precompute_shortest_paths(self):
        """Precompute shortest path distance, travel time, and node sequence between all location pairs."""
        self.shortest_paths = {}

        all_loc_ids = [0] + self.customer_ids
        
        for loc1 in all_loc_ids:
            node1 = self.location_nodes[loc1]
            # Fast single-source Dijkstra for node1
            times_dict, paths_dict = nx.single_source_dijkstra(self.graph, source=node1, weight="travel_time")

            for loc2 in all_loc_ids:
                if loc1 == loc2:
                    self.shortest_paths[(loc1, loc2)] = {
                        "distance": 0.0,
                        "time": 0.0,
                        "node_path": [node1],
                        "edge_path": []
                    }
                    continue

                node2 = self.location_nodes[loc2]
                if node2 not in paths_dict:
                    raise RuntimeError(f"No path found between location {loc1} (node {node1}) and location {loc2} (node {node2})")

                node_path = paths_dict[node2]
                path_time = times_dict[node2]
                
                # Calculate path distance and edge path
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

                self.shortest_paths[(loc1, loc2)] = {
                    "distance": path_dist,
                    "time": path_time,
                    "node_path": node_path,
                    "edge_path": edge_path
                }

    def get_shortest_path(self, loc1: int, loc2: int) -> dict:
        """Retrieve precomputed shortest path dict for (loc1, loc2)."""
        return self.shortest_paths[(loc1, loc2)]

    def get_edge_road_capacity(self, u: int, v: int, key: int = 0) -> int:
        """Get road capacity for edge (u, v, key)."""
        if self.graph.has_edge(u, v, key):
            return self.graph[u][v][key].get("road_capacity", self.road_capacities_config.get("default", 3))
        return self.road_capacities_config.get("default", 3)
