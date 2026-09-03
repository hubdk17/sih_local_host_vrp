"""
mdvrp_route_evaluator.py

Route evaluation for Multi-Depot VRP.
Each vehicle starts/ends at its home depot.
"""

from typing import Union, List, Dict, Any
from src.scaled.mdvrp_route_splitter import parse_mdvrp_solution
from src.scaled.mdvrp_constraints import MDVRPConstraintValidator


class MDVRPRouteEvaluator:
    """Evaluates candidate MDVRP solutions on the Chandigarh road network."""

    def __init__(self, instance):
        self.instance = instance
        self.validator = MDVRPConstraintValidator(instance)

    def evaluate(self, solution: Union[List[int], List[List[int]]]) -> Dict[str, Any]:
        """
        Evaluate a candidate MDVRP solution.
        Each vehicle route i uses vehicle i's home depot for start/end.
        """
        routes = parse_mdvrp_solution(solution, self.instance.num_vehicles)

        route_distances = []
        route_travel_times = []
        route_loads = []
        vehicle_full_node_paths = []
        vehicle_full_edge_paths = []
        vehicle_depot_ids = []

        for i, r in enumerate(routes):
            vehicle_id = i
            depot_key = self.instance.get_vehicle_home_depot_key(vehicle_id)
            depot_id = self.instance.vehicle_map[vehicle_id]["home_depot_id"]
            vehicle_depot_ids.append(depot_id)

            r_dist = 0.0
            r_time = 0.0
            r_load = sum(self.instance.demands.get(c, 0) for c in r)
            node_path = []
            edge_path = []

            if r:
                stops_keys = [depot_key] + [("customer", c) for c in r] + [depot_key]
                for j in range(len(stops_keys) - 1):
                    sp = self.instance.get_shortest_path(stops_keys[j], stops_keys[j + 1])
                    r_dist += sp["distance"]
                    r_time += sp["time"]

                    if not node_path:
                        node_path.extend(sp["node_path"])
                    else:
                        node_path.extend(sp["node_path"][1:])
                    edge_path.extend(sp["edge_path"])

            route_distances.append(r_dist)
            route_travel_times.append(r_time)
            route_loads.append(r_load)
            vehicle_full_node_paths.append(node_path)
            vehicle_full_edge_paths.append(edge_path)

        total_distance = sum(route_distances)
        total_travel_time = sum(route_travel_times)

        # Run constraint validations
        u_valid, u_viols, u_details = self.validator.validate_customer_uniqueness(routes)
        c_valid, c_viols, c_reports = self.validator.validate_vehicle_capacity(routes)
        v_valid, v_viols, v_details = self.validator.validate_max_vehicles(routes)
        d_valid, d_viols, d_reports = self.validator.validate_route_duration(routes)
        r_valid, r_viols, r_reports = self.validator.validate_road_capacity(routes)
        da_valid, da_viols, da_details = self.validator.validate_depot_assignment(routes)

        all_violations = u_viols + c_viols + v_viols + d_viols + r_viols + da_viols
        is_valid = u_valid and c_valid and v_valid and d_valid and r_valid and da_valid

        return {
            "routes": routes,
            "total_distance": total_distance,
            "total_travel_time": total_travel_time,
            "route_distances": route_distances,
            "route_travel_times": route_travel_times,
            "route_loads": route_loads,
            "vehicle_depot_ids": vehicle_depot_ids,
            "vehicle_full_node_paths": vehicle_full_node_paths,
            "vehicle_full_edge_paths": vehicle_full_edge_paths,
            "uniqueness": {"valid": u_valid, "violations": u_viols, "details": u_details},
            "capacity": {"valid": c_valid, "violations": c_viols, "reports": c_reports},
            "vehicles_count": {"valid": v_valid, "violations": v_viols, "details": v_details},
            "duration": {"valid": d_valid, "violations": d_viols, "reports": d_reports},
            "road_capacity": {"valid": r_valid, "violations": r_viols, "reports": r_reports},
            "depot_assignment": {"valid": da_valid, "violations": da_viols, "details": da_details},
            "total_violations": len(all_violations),
            "all_violations": all_violations,
            "is_valid": is_valid,
        }

    def format_constraint_report(self, res: Dict[str, Any]) -> str:
        """Format evaluation result into a structured text report."""
        lines = []
        status = "VALID" if res["is_valid"] else "INVALID"
        lines.append(f"SOLUTION STATUS: {status}")
        lines.append("=" * 50)

        for i, r in enumerate(res["routes"]):
            depot_id = res["vehicle_depot_ids"][i]
            depot_name = self.instance.depot_map[depot_id]["name"]
            lines.append(f"\nVehicle {i} (Depot {depot_id}: {depot_name}):")
            route_str = " -> ".join(map(str, r)) if r else "Empty"
            lines.append(f"  Route: Depot -> {route_str} -> Depot")
            lines.append(f"  load: {res['route_loads'][i]} / {res['capacity']['reports'][i]['capacity']}")
            lines.append(f"  distance: {res['route_distances'][i]:.2f} m")
            lines.append(f"  time: {res['route_travel_times'][i]:.2f} s")
            dur_pass = "PASS" if res["duration"]["reports"][i]["passed"] else "VIOLATION"
            lines.append(f"  duration: {dur_pass}")

        lines.append("\nRoad capacity:")
        road_reports = res["road_capacity"]["reports"]
        violations_only = [e for e, d in road_reports.items() if not d["passed"]]
        if not violations_only:
            lines.append("  All edges: PASS")
        else:
            for edge in violations_only:
                d = road_reports[edge]
                lines.append(f"  edge ({edge[0]}, {edge[1]}): {d['count']} / {d['capacity']} VIOLATION")

        lines.append("\nCustomer uniqueness:")
        lines.append(f"  {'PASS' if res['uniqueness']['valid'] else 'VIOLATION'}")

        lines.append(f"\nOverall: {status}")
        lines.append(f"  violations = {res['total_violations']}")
        lines.append("=" * 50)

        return "\n".join(lines)
