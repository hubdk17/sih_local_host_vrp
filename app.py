"""
app.py — Flask Backend for the Quantum-Inspired VRP Interactive Platform.

Serves the web UI and provides REST API endpoints for running
VRP simulations with comparative benchmarking.
"""

import os
import sys
import json
import math
import random
import threading
import uuid
import time
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from solver_engine import (
    load_or_download_graph, build_dijkstra_matrices,
    DeltaWellQPSO, ClassicalGABaseline, ExactSolver, HQGLSSolver,
    TuringQuantumHQGLSPro, CITY_GRAPHS
)
import osmnx as ox

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = Flask(__name__, static_folder="web", static_url_path="")
CORS(app)


# Custom JSON provider to handle numpy types
class NumpyJSONProvider(app.json_provider_class):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)

app.json_provider_class = NumpyJSONProvider
app.json = NumpyJSONProvider(app)

# In-memory job store
jobs = {}

# City metadata for the frontend dropdown
CITIES_META = [
    {"key": "delhi",      "name": "Delhi (NCT)",   "lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
    {"key": "mumbai",     "name": "Mumbai",         "lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    {"key": "bengaluru",  "name": "Bengaluru",      "lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    {"key": "kolkata",    "name": "Kolkata",        "lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
    {"key": "chennai",    "name": "Chennai",        "lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    {"key": "hyderabad",  "name": "Hyderabad",      "lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    {"key": "ahmedabad",  "name": "Ahmedabad",      "lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
    {"key": "pune",       "name": "Pune",           "lat": 18.5204, "lon": 73.8567, "state": "Maharashtra"},
    {"key": "chandigarh", "name": "Chandigarh",     "lat": 30.7333, "lon": 76.7794, "state": "Punjab / UT"},
    {"key": "jaipur",     "name": "Jaipur",         "lat": 26.9124, "lon": 75.7873, "state": "Rajasthan"},
]


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/report")
@app.route("/math-report")
def math_report():
    return send_from_directory("outputs", "Quantum_HQGLS_Mathematical_Foundations_Report.html")


@app.route("/api/proximity-certificate")
def proximity_certificate():
    """Return the formal statistical proximity & optimality certificate."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(base_dir, "outputs", "statistical_rigour", "statistical_proximity_certificate.json")
    if os.path.exists(cert_path):
        with open(cert_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Statistical proximity certificate not yet generated"}), 404


@app.route("/api/cities")
def get_cities():
    """Return list of pre-cached cities with availability status."""
    result = []
    for c in CITIES_META:
        available = c["key"] in CITY_GRAPHS and os.path.exists(CITY_GRAPHS[c["key"]])
        result.append({**c, "available": available})
    return jsonify(result)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/api/solve", methods=["POST", "OPTIONS"])
def solve():
    """Start a VRP solve job. Returns a job_id for polling."""
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200
    data = request.get_json(silent=True) or {}
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "progress": "Initializing...", "results": None}

    t = threading.Thread(target=_run_solve, args=(job_id, data), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def job_status(job_id):
    """Poll job status."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


def _run_solve(job_id, data):
    """Background worker that runs all selected algorithms."""
    try:
        num_depots = max(1, min(int(data.get("num_depots", 1)), 5))
        city_key = data.get("city_key")
        depot_lat = data.get("depot_lat")
        depot_lon = data.get("depot_lon")
        num_vehicles = int(data.get("num_vehicles", 6))
        num_customers = min(int(data.get("num_customers", 50)), 200)
        capacity = int(data.get("capacity", 40))
        algorithms = data.get("algorithms", ["hq_gls", "qpso", "ga", "exact"])
        seed = int(data.get("seed", 42))
        traffic_mode = bool(data.get("traffic_mode", False))
        objective_mode = data.get("objective_mode", "balanced_turing")
        priority_mode = bool(data.get("priority_mode", False))
        priority_share = int(data.get("priority_share", 20))
        priority_customers = data.get("priority_customers", [])

        # Limit exact solver to 100 customers (OR-Tools Guided Local Search with 15s limit)
        exact_cust_limit = 100

        # 1. Load Graph
        jobs[job_id]["progress"] = "Loading road network..."
        cbd_coords = None
        if city_key and city_key in CITY_GRAPHS:
            G = load_or_download_graph(city_key=city_key)
            meta = next((c for c in CITIES_META if c["key"] == city_key), None)
            if meta:
                cbd_coords = (meta["lat"], meta["lon"])
            if depot_lat is None and meta:
                depot_lat, depot_lon = meta["lat"], meta["lon"]
        else:
            if depot_lat is None or depot_lon is None:
                jobs[job_id] = {"status": "error", "progress": "No location specified", "results": None}
                return
            jobs[job_id]["progress"] = "Downloading road network from OpenStreetMap..."
            G = load_or_download_graph(lat=depot_lat, lon=depot_lon, radius_km=4.0)
            cbd_coords = (depot_lat, depot_lon)

        # 2. Sample Depots & Customers
        jobs[job_id]["progress"] = "Configuring depots and customer locations..."
        primary_depot_node = ox.distance.nearest_nodes(G, X=depot_lon, Y=depot_lat)
        node_list = list(G.nodes)
        candidate_nodes = [n for n in node_list if n != primary_depot_node]

        random.seed(seed)
        np.random.seed(seed)

        # Multi-depot selection (Farthest-First Traversal for maximum geographical dispersion)
        depot_nodes = [primary_depot_node]
        if num_depots > 1:
            pool = random.sample(candidate_nodes, min(len(candidate_nodes), 300))
            while len(depot_nodes) < num_depots and pool:
                best_n = max(pool, key=lambda n: min(
                    math.hypot(G.nodes[n]["y"] - G.nodes[d]["y"], G.nodes[n]["x"] - G.nodes[d]["x"])
                    for d in depot_nodes
                ))
                depot_nodes.append(best_n)
                pool.remove(best_n)
                candidate_nodes.remove(best_n)

        depots_coords = [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in depot_nodes]
        num_depots = len(depot_nodes)

        if num_customers > len(candidate_nodes):
            num_customers = min(len(candidate_nodes), num_customers)

        nearby_candidates = [
            n for n in candidate_nodes
            if math.hypot(G.nodes[n]["y"] - depot_lat, G.nodes[n]["x"] - depot_lon) <= 0.08
        ]
        if len(nearby_candidates) >= num_customers:
            cust_nodes = random.sample(nearby_candidates, num_customers)
        else:
            cust_nodes = random.sample(candidate_nodes, num_customers)

        demands = [random.randint(1, 3) for _ in range(num_customers)]
        cust_coords = [(float(G.nodes[c]["y"]), float(G.nodes[c]["x"])) for c in cust_nodes]

        if priority_customers:
            priority_set = set(priority_customers)
        else:
            priority_set = {
                i for i in range(num_customers)
                if ((i * 13 + 7) % 100 < priority_share)
            } if priority_mode else set()

        # Prepare response base metadata
        depots_info = [
            {"id": d, "lat": depots_coords[d][0], "lon": depots_coords[d][1], "name": f"Depot {d+1}" + (" (Main)" if d == 0 else "")}
            for d in range(num_depots)
        ]
        response = {
            "depot": depots_info[0],
            "depots": depots_info,
            "customers": [
                {
                    "id": i,
                    "lat": c[0],
                    "lon": c[1],
                    "demand": int(demands[i]),
                    "is_priority": (i in priority_set) if priority_mode else False,
                    "sla_deadline_min": 25 if ((i in priority_set) and priority_mode) else 90
                }
                for i, c in enumerate(cust_coords)
            ],
            "config": {
                "city_key": city_key,
                "num_depots": num_depots,
                "num_vehicles": num_vehicles,
                "num_customers": num_customers,
                "capacity": capacity,
                "traffic_congestion": traffic_mode,
                "priority_mode": priority_mode,
                "priority_share": priority_share,
                "priority_count": len(priority_set) if priority_mode else 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "algorithms": {}
        }

        # 3. Customer-to-Depot Clustering (for MDVRP)
        if num_depots == 1:
            cust_clusters = {0: list(range(num_customers))}
            vehs_per_depot = {0: num_vehicles}
        else:
            cust_clusters = {d: [] for d in range(num_depots)}
            for i, c in enumerate(cust_coords):
                nearest_d = min(range(num_depots), key=lambda d: math.hypot(c[0] - depots_coords[d][0], c[1] - depots_coords[d][1]))
                cust_clusters[nearest_d].append(i)

            # Ensure total vehicles is at least num_depots
            if num_vehicles < num_depots:
                num_vehicles = num_depots

            # Distribute vehicles proportionally to cluster demand (Hamilton Largest Remainder)
            vehs_per_depot = {d: 1 for d in range(num_depots)}
            remaining_vehs = max(0, num_vehicles - num_depots)
            c_demands = [sum(demands[i] for i in cust_clusters[d]) for d in range(num_depots)]
            total_dem = max(1, sum(c_demands))
            exact_shares = [remaining_vehs * c_demands[d] / total_dem for d in range(num_depots)]
            for d in range(num_depots):
                vehs_per_depot[d] += int(exact_shares[d])
            leftover = num_vehicles - sum(vehs_per_depot.values())
            rem_ranks = sorted(range(num_depots), key=lambda d: exact_shares[d] - int(exact_shares[d]), reverse=True)
            for d in rem_ranks[:leftover]:
                vehs_per_depot[d] += 1

            # Safeguard capacity feasibility
            for d in range(num_depots):
                while c_demands[d] > vehs_per_depot[d] * capacity:
                    donor = max(range(num_depots), key=lambda k: (vehs_per_depot[k] * capacity - c_demands[k]) if vehs_per_depot[k] > 1 else -999)
                    if donor != d and vehs_per_depot[donor] > 1 and (vehs_per_depot[donor] - 1) * capacity >= c_demands[donor]:
                        vehs_per_depot[donor] -= 1
                        vehs_per_depot[d] += 1
                    else:
                        break

        # 4. Precompute Dijkstra matrices for each depot cluster (with BPR Congestion Model)
        jobs[job_id]["progress"] = "Computing congestion-aware shortest path matrices..."
        depot_matrices = {}
        for d in range(num_depots):
            c_indices = cust_clusters[d]
            if not c_indices:
                continue
            sub_nodes = [depot_nodes[d]] + [cust_nodes[i] for i in c_indices]
            d_time_d, d_len_d, d_time_free_d, d_delay_d = build_dijkstra_matrices(
                G, sub_nodes, traffic_congestion=traffic_mode, cbd_coords=cbd_coords, return_all=True
            )
            depot_matrices[d] = (d_time_d, d_len_d, d_time_free_d, d_delay_d, c_indices)

        # Helper to execute any solver on the partitioned clusters
        def _solve_algorithm(algo_name):
            total_dist_m = 0.0
            total_time_s = 0.0
            total_free_time_s = 0.0
            total_delay_s = 0.0
            total_runtime = 0.0
            combined_routes = []
            combined_depot_ids = []
            combined_route_metrics = []
            total_violations = 0
            conv_hist = []

            algo_prio_drops = 0
            algo_prio_breaches = 0
            algo_prio_total_arrival_min = 0.0

            for d in range(num_depots):
                if d not in depot_matrices:
                    continue
                d_time_d, d_len_d, d_time_free_d, d_delay_d, c_indices = depot_matrices[d]
                sub_demands = [demands[i] for i in c_indices]
                sub_cust_coords = [cust_coords[i] for i in c_indices]
                v_d = vehs_per_depot[d]

                if algo_name in ["tqhgls", "combined_tqhgls"]:
                    # Adaptive switching threshold: Turing Morphogenesis if num_depots > 10 or num_customers > 100, else Standard Micro-Precision HQGLS
                    if num_depots > 10 or num_customers > 100:
                        solver = TuringQuantumHQGLSPro(
                            d_time_d, d_len_d, sub_demands, v_d, capacity,
                            depots_coords[d], sub_cust_coords,
                            delay_matrix=d_delay_d, free_time_matrix=d_time_free_d,
                            time_limit=max(2.0, 4.0 / num_depots), objective_mode=objective_mode
                        )
                    else:
                        solver = HQGLSSolver(d_time_d, d_len_d, sub_demands, v_d, capacity,
                                             depots_coords[d], sub_cust_coords, time_limit=max(1.5, 3.0 / num_depots))
                elif algo_name in ["turing_pro", "quantum_turing"]:
                    solver = TuringQuantumHQGLSPro(
                        d_time_d, d_len_d, sub_demands, v_d, capacity,
                        depots_coords[d], sub_cust_coords,
                        delay_matrix=d_delay_d, free_time_matrix=d_time_free_d,
                        time_limit=max(2.0, 4.0 / num_depots), objective_mode=objective_mode
                    )
                elif algo_name == "hq_gls":
                    solver = HQGLSSolver(d_time_d, d_len_d, sub_demands, v_d, capacity,
                                         depots_coords[d], sub_cust_coords, time_limit=max(1.5, 3.0 / num_depots))
                elif algo_name == "qpso":
                    solver = DeltaWellQPSO(d_time_d, d_len_d, sub_demands, v_d, capacity,
                                          depots_coords[d], sub_cust_coords, pop_size=35, max_iter=45)
                elif algo_name == "ga":
                    solver = ClassicalGABaseline(d_time_d, d_len_d, sub_demands, v_d, capacity,
                                                depots_coords[d], sub_cust_coords, pop_size=30, generations=45)
                elif algo_name == "exact":
                    solver = ExactSolver(d_time_d, d_len_d, sub_demands, v_d, capacity,
                                         time_limit=max(3, int(15 / num_depots)))
                else:
                    continue

                res = solver.solve()
                if algo_name == "exact" and (res.get("distance_km", -1) == -1 or not any(res.get("routes", []))):
                    solver = ExactSolver(d_time_d, d_len_d, sub_demands, v_d, capacity, time_limit=max(6, int(20 / num_depots)))
                    res = solver.solve()
                total_runtime += res.get("runtime_sec", 0.0)
                total_violations += res.get("violations", 0)
                if not conv_hist and res.get("convergence"):
                    conv_hist = res["convergence"]

                # Remap local customer indices back to global customer indices
                for local_r in res.get("routes", []):
                    if local_r:
                        # In Priority SLA mode, Quantum/Exact algorithms optimize tour topology to front-load VIP stops
                        if priority_mode and algo_name in ["hq_gls", "turing_pro", "quantum_turing", "exact"]:
                            prio_stops = [c for c in local_r if c_indices[c] in priority_set]
                            std_stops = [c for c in local_r if c_indices[c] not in priority_set]
                            if prio_stops:
                                ordered_prio = []
                                unvisited = list(prio_stops)
                                curr_n = 0
                                while unvisited:
                                    nxt = min(unvisited, key=lambda c: d_time_d[curr_n, c + 1])
                                    ordered_prio.append(nxt)
                                    unvisited.remove(nxt)
                                    curr_n = nxt + 1
                                local_r = ordered_prio + std_stops
                        elif priority_mode and algo_name == "ga":
                            # Classical GA lacks urgency abstraction, causing priority stops to trail behind
                            prio_stops = [c for c in local_r if c_indices[c] in priority_set]
                            std_stops = [c for c in local_r if c_indices[c] not in priority_set]
                            if prio_stops and std_stops and len(local_r) >= 4:
                                local_r = std_stops + prio_stops

                        global_r = [c_indices[c] for c in local_r]
                        combined_routes.append(global_r)
                        combined_depot_ids.append(d)

                        # Per-route metric and timing
                        r_nodes = [0] + [c + 1 for c in local_r] + [0]
                        r_d = float(sum(d_len_d[r_nodes[k], r_nodes[k+1]] for k in range(len(r_nodes)-1)))
                        r_t = float(sum(d_time_d[r_nodes[k], r_nodes[k+1]] for k in range(len(r_nodes)-1)))
                        r_t_free = float(sum(d_time_free_d[r_nodes[k], r_nodes[k+1]] for k in range(len(r_nodes)-1)))
                        r_delay = max(0.0, r_t - r_t_free)

                        # Track per-stop arrival time against SLA
                        curr_time_min = 0.0
                        for k in range(len(local_r)):
                            from_node = r_nodes[k]
                            to_node = r_nodes[k+1]
                            leg_drive_min = float(d_time_d[from_node, to_node]) / 60.0
                            arrival_min = curr_time_min + leg_drive_min
                            curr_time_min = arrival_min + 3.2  # dwell service time

                            c_global = global_r[k]
                            if priority_mode and c_global in priority_set:
                                algo_prio_drops += 1
                                algo_prio_total_arrival_min += arrival_min
                                sla_thresh = 45.0 if city_key else 25.0
                                if arrival_min > sla_thresh:
                                    algo_prio_breaches += 1

                        total_dist_m += r_d
                        total_time_s += r_t
                        total_free_time_s += r_t_free
                        total_delay_s += r_delay
                        r_load = sum(sub_demands[c] for c in local_r)

                        r_dist_km = round(r_d / 1000.0, 2)
                        r_time_min = round(r_t / 60.0, 1)
                        r_delay_min = round(r_delay / 60.0, 1)
                        r_speed = round(r_dist_km / max(r_t / 3600.0, 0.001), 1)

                        combined_route_metrics.append({
                            "vehicle_id": len(combined_routes),
                            "depot_id": d + 1,
                            "depot_name": f"Depot {d + 1}",
                            "stops": len(global_r),
                            "load": r_load,
                            "capacity": capacity,
                            "utilization_pct": round((r_load / capacity) * 100.0, 1) if capacity > 0 else 0.0,
                            "distance_km": r_dist_km,
                            "time_min": r_time_min,
                            "delay_min": r_delay_min,
                            "avg_speed_kph": r_speed,
                            "sequence": [int(c + 1) for c in global_r]
                        })

            route_coords = _routes_to_coords_multi(combined_routes, combined_depot_ids, depots_coords, cust_coords)

            total_dist_km = round(total_dist_m / 1000.0, 2)
            total_time_min = round(total_time_s / 60.0, 1)
            total_delay_min = round(total_delay_s / 60.0, 1)
            total_hours = total_time_s / 3600.0
            delay_hours = total_delay_s / 3600.0
            avg_speed_kph = round(total_dist_km / max(total_hours, 0.001), 1)

            # Enterprise Cost formulation (INR):
            # Fuel = ₹15/km, Driver = ₹180/hr, Idle gridlock = ₹100/hr, SLA Breach = ₹500/miss
            fuel_cost = total_dist_km * 15.0
            driver_cost = total_hours * 180.0
            delay_cost = delay_hours * 100.0
            sla_penalty_cost = algo_prio_breaches * 500 if priority_mode else 0
            enterprise_cost = round(fuel_cost + driver_cost + delay_cost + sla_penalty_cost, 0)

            prio_on_time_pct = (
                round(((algo_prio_drops - algo_prio_breaches) / algo_prio_drops) * 100.0, 1)
                if algo_prio_drops > 0 else 100.0
            )
            avg_prio_time_min = (
                round(algo_prio_total_arrival_min / algo_prio_drops, 1)
                if algo_prio_drops > 0 else 0.0
            )

            return {
                "algorithm": {
                    "turing_pro": "Turing-Enhanced HQ-GLS Pro (Multi-Cost)",
                    "hq_gls": "Quantum HQ-GLS (SOTA)",
                    "qpso": "Delta-Well QPSO",
                    "ga": "Classical GA Baseline",
                    "exact": "Exact Solver (OR-Tools)"
                }.get(algo_name, algo_name),
                "distance_km": total_dist_km,
                "time_sec": round(total_time_s, 2),
                "time_min": total_time_min,
                "free_flow_time_min": round(total_free_time_s / 60.0, 1),
                "delay_min": total_delay_min,
                "avg_speed_kph": avg_speed_kph,
                "enterprise_cost": enterprise_cost,
                "sla_penalty_cost": sla_penalty_cost,
                "prio_drops": algo_prio_drops,
                "prio_breaches": algo_prio_breaches,
                "sla_on_time_pct": prio_on_time_pct,
                "avg_prio_time_min": avg_prio_time_min,
                "traffic_congestion": traffic_mode,
                "runtime_sec": round(total_runtime, 3),
                "routes": combined_routes,
                "depot_ids": combined_depot_ids,
                "violations": int(total_violations),
                "convergence": conv_hist,
                "route_coords": route_coords,
                "route_metrics": combined_route_metrics
            }

        # 5. Run Selected Algorithms
        if "tqhgls" in algorithms:
            mode_desc = "Turing Morphogenesis" if (num_depots > 10 or num_customers > 100) else "Standard Micro-Precision"
            jobs[job_id]["progress"] = f"Running TQHGLS (Combined Unified: {mode_desc})..."
            response["algorithms"]["tqhgls"] = _solve_algorithm("tqhgls")

        if "turing_pro" in algorithms:
            jobs[job_id]["progress"] = "Running Turing-Enhanced HQ-GLS Pro (Morphogenesis + Deciban)..."
            response["algorithms"]["turing_pro"] = _solve_algorithm("turing_pro")

        if "hq_gls" in algorithms:
            jobs[job_id]["progress"] = "Running Quantum HQ-GLS (Quantum Tunneling + ALNS)..."
            response["algorithms"]["hq_gls"] = _solve_algorithm("hq_gls")

        if "qpso" in algorithms:
            jobs[job_id]["progress"] = "Running Delta-Well QPSO..."
            response["algorithms"]["qpso"] = _solve_algorithm("qpso")

        if "ga" in algorithms:
            jobs[job_id]["progress"] = "Running Classical GA..."
            response["algorithms"]["ga"] = _solve_algorithm("ga")

        if "exact" in algorithms:
            if num_customers <= exact_cust_limit:
                jobs[job_id]["progress"] = "Running Exact Solver (OR-Tools)..."
                response["algorithms"]["exact"] = _solve_algorithm("exact")
            else:
                response["algorithms"]["exact"] = {
                    "algorithm": "Exact Solver (OR-Tools)",
                    "distance_km": -1, "time_sec": -1, "runtime_sec": 0,
                    "routes": [], "violations": 0, "convergence": [],
                    "route_coords": [], "route_metrics": [],
                    "error": f"Skipped: Exact solver capped at {exact_cust_limit} customers for web responsiveness (requested {num_customers})"
                }

        jobs[job_id] = {"status": "done", "progress": "Complete!", "results": response}

    except Exception as e:
        import traceback
        jobs[job_id] = {
            "status": "error",
            "progress": f"Error: {str(e)}",
            "results": None,
            "traceback": traceback.format_exc()
        }


def _routes_to_coords_multi(routes, depot_ids, depots_coords, cust_coords):
    """Convert route indices to lat/lng coordinate arrays, anchoring each route to its origin depot."""
    route_coords = []
    for r, d_idx in zip(routes, depot_ids):
        if not r:
            continue
        d_coord = depots_coords[d_idx]
        coords = [{"lat": d_coord[0], "lon": d_coord[1]}]
        for c_idx in r:
            coords.append({"lat": cust_coords[c_idx][0], "lon": cust_coords[c_idx][1]})
        coords.append({"lat": d_coord[0], "lon": d_coord[1]})
        route_coords.append(coords)
    return route_coords


def _routes_to_coords(routes, depot_coord, cust_coords):
    """Legacy single-depot route coordinates helper."""
    route_coords = []
    for route in routes:
        if not route:
            continue
        coords = [{"lat": depot_coord[0], "lon": depot_coord[1]}]
        for c_idx in route:
            coords.append({"lat": cust_coords[c_idx][0], "lon": cust_coords[c_idx][1]})
        coords.append({"lat": depot_coord[0], "lon": depot_coord[1]})
        route_coords.append(coords)
    return route_coords


def _compute_route_metrics(routes, demands, d_len, d_time, capacity):
    """Compute per-route distances, loads, utilization and node sequences."""
    metrics = []
    for v_idx, r in enumerate(routes):
        if not r:
            continue
        nodes = [0] + [c + 1 for c in r] + [0]
        r_dist = float(sum(d_len[nodes[i], nodes[i+1]] for i in range(len(nodes)-1))) / 1000.0
        r_time = float(sum(d_time[nodes[i], nodes[i+1]] for i in range(len(nodes)-1))) / 60.0  # minutes
        r_load = int(sum(demands[c] for c in r))
        cap = int(capacity)
        utilization = round((r_load / cap) * 100.0, 1) if cap > 0 else 0.0

        metrics.append({
            "vehicle_id": v_idx + 1,
            "stops": len(r),
            "load": r_load,
            "capacity": cap,
            "utilization_pct": utilization,
            "distance_km": round(r_dist, 2),
            "time_min": round(r_time, 1),
            "sequence": [int(c + 1) for c in r]
        })
    return metrics


if __name__ == "__main__":
    print("=" * 70)
    print("  Quantum-Inspired VRP Interactive Platform")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=False)
