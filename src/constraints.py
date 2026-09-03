"""
constraints.py

Independent constraint validation module for VRP solutions.
Validates:
  1. Customer uniqueness (no duplicates, no missing, valid IDs)
  2. Vehicle capacity (route load <= vehicle capacity)
  3. Max vehicles limit (non-empty routes <= num_vehicles)
  4. Max route duration (route travel time <= max_route_duration)
  5. Static road capacity (edge vehicle count <= road capacity limit)
"""

from typing import List, Dict, Tuple, Any

class ConstraintValidator:
    """
    Validates all VRP constraints against a VRPInstance.
    """

    def __init__(self, instance):
        self.instance = instance

    def validate_customer_uniqueness(self, routes: List[List[int]]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Constraint 1: Customer Uniqueness
        Checks if every configured customer (1..N) appears exactly once.
        """
        all_customers = self.instance.customer_ids
        expected_set = set(all_customers)

        seen = set()
        duplicates = []
        invalid_ids = []

        flat_list = []
        for r in routes:
            for cust_id in r:
                flat_list.append(cust_id)
                if cust_id not in expected_set:
                    invalid_ids.append(cust_id)
                elif cust_id in seen:
                    duplicates.append(cust_id)
                else:
                    seen.add(cust_id)

        missing = list(expected_set - seen)

        violations = []
        if duplicates:
            violations.append(f"Duplicate customers detected: {duplicates}")
        if missing:
            violations.append(f"Missing customers detected: {missing}")
        if invalid_ids:
            violations.append(f"Invalid customer IDs detected: {invalid_ids}")

        is_valid = len(violations) == 0
        details = {
            "seen": list(seen),
            "duplicates": duplicates,
            "missing": missing,
            "invalid": invalid_ids
        }
        return is_valid, violations, details

    def validate_vehicle_capacity(self, routes: List[List[int]]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Constraint 2: Vehicle Capacity
        Checks if route load <= vehicle capacity for every route.
        """
        max_cap = self.instance.vehicle_capacity
        demands = self.instance.demands

        violations = []
        route_reports = []
        is_valid = True

        for i, r in enumerate(routes):
            load = sum(demands.get(c, 0) for c in r)
            passed = load <= max_cap
            if not passed:
                is_valid = False
                violations.append(f"Vehicle {i+1} capacity exceeded: load {load} > max capacity {max_cap}")
            
            route_reports.append({
                "vehicle": i + 1,
                "load": load,
                "capacity": max_cap,
                "passed": passed
            })

        return is_valid, violations, route_reports

    def validate_max_vehicles(self, routes: List[List[int]]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Constraint 3: Maximum Number of Vehicles
        Checks if number of non-empty routes <= num_vehicles.
        """
        max_v = self.instance.num_vehicles
        active_routes = [r for r in routes if len(r) > 0]
        used = len(active_routes)

        passed = used <= max_v
        violations = []
        if not passed:
            violations.append(f"Exceeded vehicle limit: used {used} vehicles > max {max_v}")

        details = {"used_vehicles": used, "max_vehicles": max_v, "passed": passed}
        return passed, violations, details

    def validate_max_route_duration(self, routes: List[List[int]]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Constraint 4: Maximum Route Duration
        Checks if travel time for Depot -> C_1 -> ... -> C_k -> Depot <= max_route_duration_sec.
        Uses actual shortest path travel times from Chandigarh OSM graph.
        """
        max_duration = self.instance.max_route_duration_sec

        violations = []
        duration_reports = []
        is_valid = True

        for i, r in enumerate(routes):
            # Calculate total travel time along route
            total_time = 0.0
            if r:
                # Depot -> C1
                total_time += self.instance.get_shortest_path(0, r[0])["time"]
                # C_j -> C_{j+1}
                for j in range(len(r) - 1):
                    total_time += self.instance.get_shortest_path(r[j], r[j+1])["time"]
                # C_k -> Depot
                total_time += self.instance.get_shortest_path(r[-1], 0)["time"]

            passed = total_time <= max_duration
            if not passed:
                is_valid = False
                violations.append(f"Vehicle {i+1} duration exceeded: time {total_time:.2f}s > max {max_duration:.2f}s")

            duration_reports.append({
                "vehicle": i + 1,
                "time": total_time,
                "max_duration": max_duration,
                "passed": passed
            })

        return is_valid, violations, duration_reports

    def validate_road_capacity(self, routes: List[List[int]]) -> Tuple[bool, List[str], Dict[Tuple[int, int, int], Dict[str, Any]]]:
        """
        Constraint 5: Static Road Capacity
        Approximation: Counts how many vehicle routes traverse each edge (u, v, k)
        on their shortest paths.
        Requires: vehicle_count[e] <= road_capacity[e].

        NOTE: This is a static route-overlap approximation (solution-wide count),
        not a simultaneous/time-dependent dynamic traffic flow model.
        """
        edge_counts = {}

        for r in routes:
            if not r:
                continue

            # Trace shortest paths for this vehicle route
            stops = [0] + r + [0]
            for j in range(len(stops) - 1):
                path_info = self.instance.get_shortest_path(stops[j], stops[j+1])
                for edge in path_info["edge_path"]:
                    edge_counts[edge] = edge_counts.get(edge, 0) + 1

        violations = []
        edge_reports = {}
        is_valid = True

        for edge, count in edge_counts.items():
            u, v, k = edge
            cap = self.instance.get_edge_road_capacity(u, v, k)
            passed = count <= cap
            if not passed:
                is_valid = False
                violations.append(f"Road capacity violation on edge ({u}, {v}): count {count} > capacity {cap}")
            
            edge_reports[edge] = {
                "count": count,
                "capacity": cap,
                "passed": passed
            }

        return is_valid, violations, edge_reports
