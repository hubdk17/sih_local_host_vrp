"""
route_evaluator.py

Route Evaluation module that takes candidate solutions, computes actual
Chandigarh road network shortest paths, distances, travel times, and invokes
ConstraintValidator to produce evaluation reports.
"""

from typing import Union, List, Dict, Any
from src.route_splitter import parse_solution
from src.constraints import ConstraintValidator

class RouteEvaluator:
    """
    Evaluates candidate VRP solutions on the Chandigarh road network.
    """

    def __init__(self, instance):
        self.instance = instance
        self.validator = ConstraintValidator(instance)

    def evaluate(self, solution: Union[List[int], List[List[int]]]) -> Dict[str, Any]:
        """
        Evaluate a candidate solution (permutation or list of vehicle routes).
        """
        routes = parse_solution(solution, self.instance.num_vehicles)

        # 1. Evaluate per-vehicle routes
        route_distances = []
        route_travel_times = []
        route_loads = []
        vehicle_full_node_paths = []
        vehicle_full_edge_paths = []

        for r in routes:
            r_dist = 0.0
            r_time = 0.0
            r_load = sum(self.instance.demands.get(c, 0) for c in r)
            node_path = []
            edge_path = []

            if r:
                stops = [0] + r + [0]
                for j in range(len(stops) - 1):
                    sp = self.instance.get_shortest_path(stops[j], stops[j+1])
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

        # 2. Run Constraint Validations
        u_valid, u_viols, u_details = self.validator.validate_customer_uniqueness(routes)
        c_valid, c_viols, c_reports = self.validator.validate_vehicle_capacity(routes)
        v_valid, v_viols, v_details = self.validator.validate_max_vehicles(routes)
        d_valid, d_viols, d_reports = self.validator.validate_max_route_duration(routes)
        r_valid, r_viols, r_reports = self.validator.validate_road_capacity(routes)

        all_violations = u_viols + c_viols + v_viols + d_viols + r_viols
        is_valid = (u_valid and c_valid and v_valid and d_valid and r_valid)

        result = {
            "routes": routes,
            "total_distance": total_distance,
            "total_travel_time": total_travel_time,
            "route_distances": route_distances,
            "route_travel_times": route_travel_times,
            "route_loads": route_loads,
            "vehicle_full_node_paths": vehicle_full_node_paths,
            "vehicle_full_edge_paths": vehicle_full_edge_paths,
            "uniqueness": {"valid": u_valid, "violations": u_viols, "details": u_details},
            "capacity": {"valid": c_valid, "violations": c_viols, "reports": c_reports},
            "vehicles_count": {"valid": v_valid, "violations": v_viols, "details": v_details},
            "duration": {"valid": d_valid, "violations": d_viols, "reports": d_reports},
            "road_capacity": {"valid": r_valid, "violations": r_viols, "reports": r_reports},
            "total_violations": len(all_violations),
            "all_violations": all_violations,
            "is_valid": is_valid
        }

        return result

    def format_constraint_report(self, res: Dict[str, Any]) -> str:
        """Format evaluation result into structured text report."""
        lines = []
        status_header = "VALID" if res["is_valid"] else "INVALID"
        lines.append(f"SOLUTION STATUS: {status_header}")
        lines.append("=" * 45)

        for i, r in enumerate(res["routes"]):
            lines.append(f"\nVehicle {i+1}:")
            lines.append(f"  Route: Depot -> {' -> '.join(map(str, r)) if r else 'Empty'} -> Depot")
            lines.append(f"  load: {res['route_loads'][i]} / {res['capacity']['reports'][i]['capacity']}")
            lines.append(f"  distance: {res['route_distances'][i]:.2f} m")
            lines.append(f"  time: {res['route_travel_times'][i]:.2f} s")
            dur_pass = "PASS" if res["duration"]["reports"][i]["passed"] else "VIOLATION"
            lines.append(f"  duration constraint: {dur_pass}")

        lines.append("\nRoad capacity:")
        road_reports = res["road_capacity"]["reports"]
        if not road_reports:
            lines.append("  (No road edges traversed)")
        else:
            violations_only = [e for e, data in road_reports.items() if not data["passed"]]
            if not violations_only:
                lines.append("  All traversed edges: PASS")
            else:
                for edge in violations_only:
                    data = road_reports[edge]
                    lines.append(f"  edge ({edge[0]}, {edge[1]}): {data['count']} / {data['capacity']} VIOLATION")

        lines.append("\nCustomer uniqueness:")
        uniq_pass = "PASS" if res["uniqueness"]["valid"] else f"VIOLATION ({', '.join(res['uniqueness']['violations'])})"
        lines.append(f"  {uniq_pass}")

        lines.append("\nOverall:")
        lines.append(f"  {'VALID' if res['is_valid'] else 'INVALID'}")
        lines.append(f"  violations = {res['total_violations']}")
        lines.append("=" * 45)

        return "\n".join(lines)
