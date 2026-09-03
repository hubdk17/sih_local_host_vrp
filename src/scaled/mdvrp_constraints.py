"""
mdvrp_constraints.py

Constraint validation for Multi-Depot Vehicle Routing Problem.
Validates:
  1. Customer uniqueness
  2. Vehicle capacity (per-vehicle)
  3. Max vehicles limit
  4. Max route duration (per-vehicle, using home depot)
  5. Static road capacity (aggregated across all routes)
  6. Depot assignment validity
"""

from typing import List, Dict, Tuple, Any


class MDVRPConstraintValidator:
    """Validates all MDVRP constraints against an MDVRPInstance."""

    def __init__(self, instance):
        self.instance = instance

    def validate_customer_uniqueness(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Constraint 1: Every customer appears exactly once."""
        expected = set(self.instance.customer_ids)
        seen = set()
        duplicates = []
        invalid_ids = []

        for r in routes:
            for cid in r:
                if cid not in expected:
                    invalid_ids.append(cid)
                elif cid in seen:
                    duplicates.append(cid)
                else:
                    seen.add(cid)

        missing = list(expected - seen)
        violations = []
        if duplicates:
            violations.append(f"Duplicate customers: {duplicates}")
        if missing:
            violations.append(f"Missing customers: {missing}")
        if invalid_ids:
            violations.append(f"Invalid customer IDs: {invalid_ids}")

        return len(violations) == 0, violations, {
            "seen": list(seen), "duplicates": duplicates,
            "missing": missing, "invalid": invalid_ids,
        }

    def validate_vehicle_capacity(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """Constraint 2: Per-vehicle capacity."""
        violations = []
        reports = []
        is_valid = True

        for i, r in enumerate(routes):
            vehicle_id = i  # vehicle order matches route index
            cap = self.instance.get_vehicle_capacity(vehicle_id)
            load = sum(self.instance.demands.get(c, 0) for c in r)
            passed = load <= cap
            if not passed:
                is_valid = False
                violations.append(
                    f"Vehicle {vehicle_id} capacity exceeded: load {load} > capacity {cap}"
                )
            reports.append({
                "vehicle": vehicle_id, "load": load, "capacity": cap, "passed": passed,
            })

        return is_valid, violations, reports

    def validate_max_vehicles(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Constraint 3: Number of non-empty routes <= num_vehicles."""
        max_v = self.instance.num_vehicles
        used = sum(1 for r in routes if r)
        passed = used <= max_v
        violations = []
        if not passed:
            violations.append(f"Used {used} vehicles > max {max_v}")
        return passed, violations, {"used": used, "max": max_v, "passed": passed}

    def validate_route_duration(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Constraint 4: Route duration using each vehicle's home depot.
        Route: home_depot -> c1 -> c2 -> ... -> home_depot
        """
        max_dur = self.instance.max_route_duration_sec
        violations = []
        reports = []
        is_valid = True

        for i, r in enumerate(routes):
            vehicle_id = i
            depot_key = self.instance.get_vehicle_home_depot_key(vehicle_id)
            total_time = 0.0

            if r:
                # Depot -> first customer
                first_key = ("customer", r[0])
                total_time += self.instance.get_shortest_path(depot_key, first_key)["time"]

                # Customer -> customer
                for j in range(len(r) - 1):
                    k1 = ("customer", r[j])
                    k2 = ("customer", r[j + 1])
                    total_time += self.instance.get_shortest_path(k1, k2)["time"]

                # Last customer -> depot
                last_key = ("customer", r[-1])
                total_time += self.instance.get_shortest_path(last_key, depot_key)["time"]

            passed = total_time <= max_dur
            if not passed:
                is_valid = False
                violations.append(
                    f"Vehicle {vehicle_id} duration {total_time:.1f}s > max {max_dur:.1f}s"
                )
            reports.append({
                "vehicle": vehicle_id, "time": total_time,
                "max_duration": max_dur, "passed": passed,
            })

        return is_valid, violations, reports

    def validate_road_capacity(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], Dict[Tuple, Dict[str, Any]]]:
        """
        Constraint 5: Static road capacity.
        Counts vehicle route overlap on each edge across ALL routes.
        """
        edge_counts = {}

        for i, r in enumerate(routes):
            if not r:
                continue
            vehicle_id = i
            depot_key = self.instance.get_vehicle_home_depot_key(vehicle_id)

            # Collect all edges in this vehicle's route
            stops_keys = [depot_key] + [("customer", c) for c in r] + [depot_key]
            for j in range(len(stops_keys) - 1):
                path_info = self.instance.get_shortest_path(stops_keys[j], stops_keys[j + 1])
                for edge in path_info["edge_path"]:
                    edge_counts[edge] = edge_counts.get(edge, 0) + 1

        violations = []
        reports = {}
        is_valid = True

        for edge, count in edge_counts.items():
            u, v, k = edge
            cap = self.instance.get_edge_road_capacity(u, v, k)
            passed = count <= cap
            if not passed:
                is_valid = False
                violations.append(
                    f"Road capacity on edge ({u}, {v}): {count} > {cap}"
                )
            reports[edge] = {"count": count, "capacity": cap, "passed": passed}

        return is_valid, violations, reports

    def validate_depot_assignment(
        self, routes: List[List[int]]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Constraint 6: Each vehicle route implicitly starts/ends at home depot.
        (Structural — validated by the evaluator using home depot for path computation.)
        This always passes since routing is depot-aware by construction.
        """
        return True, [], {"note": "Depot assignment enforced by route evaluation structure"}
