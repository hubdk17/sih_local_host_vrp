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
    DeltaWellQPSO, ClassicalGABaseline, ExactSolver, HQGLSSolver, CITY_GRAPHS
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


@app.route("/api/cities")
def get_cities():
    """Return list of pre-cached cities with availability status."""
    result = []
    for c in CITIES_META:
        available = c["key"] in CITY_GRAPHS and os.path.exists(CITY_GRAPHS[c["key"]])
        result.append({**c, "available": available})
    return jsonify(result)


@app.route("/api/solve", methods=["POST"])
def solve():
    """Start a VRP solve job. Returns a job_id for polling."""
    data = request.get_json()
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
        city_key = data.get("city_key")
        depot_lat = data.get("depot_lat")
        depot_lon = data.get("depot_lon")
        num_vehicles = int(data.get("num_vehicles", 6))
        num_customers = min(int(data.get("num_customers", 50)), 200)
        capacity = int(data.get("capacity", 40))
        algorithms = data.get("algorithms", ["hq_gls", "qpso", "ga", "exact"])
        seed = int(data.get("seed", 42))

        # Limit exact solver to 100 customers (OR-Tools Guided Local Search with 15s limit)
        exact_cust_limit = 100

        # 1. Load Graph
        jobs[job_id]["progress"] = "Loading road network..."
        if city_key and city_key in CITY_GRAPHS:
            G = load_or_download_graph(city_key=city_key)
            if depot_lat is None:
                meta = next((c for c in CITIES_META if c["key"] == city_key), None)
                if meta:
                    depot_lat, depot_lon = meta["lat"], meta["lon"]
        else:
            if depot_lat is None or depot_lon is None:
                jobs[job_id] = {"status": "error", "progress": "No location specified", "results": None}
                return
            jobs[job_id]["progress"] = "Downloading road network from OpenStreetMap..."
            G = load_or_download_graph(lat=depot_lat, lon=depot_lon, radius_km=4.0)

        # 2. Find depot node and sample customers
        jobs[job_id]["progress"] = "Sampling customer locations..."
        depot_node = ox.distance.nearest_nodes(G, X=depot_lon, Y=depot_lat)
        depot_coord = (G.nodes[depot_node]["y"], G.nodes[depot_node]["x"])

        node_list = list(G.nodes)
        candidate_nodes = [n for n in node_list if n != depot_node]

        random.seed(seed)
        np.random.seed(seed)

        if num_customers > len(candidate_nodes):
            num_customers = min(len(candidate_nodes), num_customers)

        cust_nodes = random.sample(candidate_nodes, num_customers)
        demands = [random.randint(1, 3) for _ in range(num_customers)]
        cust_coords = [(G.nodes[c]["y"], G.nodes[c]["x"]) for c in cust_nodes]

        # 3. Build Dijkstra Matrices
        jobs[job_id]["progress"] = "Computing shortest path matrices (Dijkstra)..."
        sample_nodes = [depot_node] + cust_nodes
        d_time, d_len = build_dijkstra_matrices(G, sample_nodes)

        # Prepare response data
        response = {
            "depot": {"lat": depot_coord[0], "lon": depot_coord[1]},
            "customers": [{"lat": c[0], "lon": c[1], "demand": int(demands[i])} for i, c in enumerate(cust_coords)],
            "config": {
                "city_key": city_key,
                "num_vehicles": num_vehicles,
                "num_customers": num_customers,
                "capacity": capacity,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "algorithms": {}
        }

        # 4. Run Algorithms
        # Quantum HQ-GLS (SOTA Flagship Solver)
        if "hq_gls" in algorithms:
            jobs[job_id]["progress"] = "Running Quantum HQ-GLS (Quantum Tunneling + Cross-Exchange)..."
            hqgls = HQGLSSolver(d_time, d_len, demands, num_vehicles, capacity,
                                depot_coord, cust_coords, time_limit=3.0)
            result = hqgls.solve()
            result["route_coords"] = _routes_to_coords(result["routes"], depot_coord, cust_coords)
            result["route_metrics"] = _compute_route_metrics(result["routes"], demands, d_len, d_time, capacity)
            response["algorithms"]["hq_gls"] = result

        # Delta-Well QPSO
        if "qpso" in algorithms:
            jobs[job_id]["progress"] = "Running Delta-Well QPSO optimization..."
            qpso = DeltaWellQPSO(d_time, d_len, demands, num_vehicles, capacity,
                                 depot_coord, cust_coords, pop_size=35, max_iter=50)
            result = qpso.solve()
            result["route_coords"] = _routes_to_coords(result["routes"], depot_coord, cust_coords)
            result["route_metrics"] = _compute_route_metrics(result["routes"], demands, d_len, d_time, capacity)
            response["algorithms"]["qpso"] = result

        # Classical GA
        if "ga" in algorithms:
            jobs[job_id]["progress"] = "Running Classical Heuristic GA..."
            ga = ClassicalGABaseline(d_time, d_len, demands, num_vehicles, capacity,
                                     depot_coord, cust_coords, pop_size=30, generations=50)
            result = ga.solve()
            result["route_coords"] = _routes_to_coords(result["routes"], depot_coord, cust_coords)
            result["route_metrics"] = _compute_route_metrics(result["routes"], demands, d_len, d_time, capacity)
            response["algorithms"]["ga"] = result

        # Exact Solver (limited to 100 customers)
        if "exact" in algorithms:
            if num_customers <= exact_cust_limit:
                jobs[job_id]["progress"] = "Running Exact Solver (OR-Tools)..."
                exact = ExactSolver(d_time, d_len, demands, num_vehicles, capacity, time_limit=15)
                result = exact.solve()
                result["route_coords"] = _routes_to_coords(result["routes"], depot_coord, cust_coords)
                result["route_metrics"] = _compute_route_metrics(result["routes"], demands, d_len, d_time, capacity)
                response["algorithms"]["exact"] = result
            else:
                response["algorithms"]["exact"] = {
                    "algorithm": "Exact Solver (OR-Tools)",
                    "distance_km": -1, "time_sec": -1, "runtime_sec": 0,
                    "routes": [], "violations": 0, "convergence": [],
                    "route_coords": [],
                    "route_metrics": [],
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


def _routes_to_coords(routes, depot_coord, cust_coords):
    """Convert route indices to lat/lng coordinate arrays for map rendering."""
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
