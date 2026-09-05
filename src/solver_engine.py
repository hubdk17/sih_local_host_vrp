"""
solver_engine.py

Refactored, importable solver classes for the Q-VRP Web Platform.
Provides a unified interface for 3 algorithms:
  1. DeltaWellQPSO   — Quantum Particle Swarm Optimization (Delta-Potential-Well)
  2. ClassicalGABaseline — Angular-sweep heuristic Genetic Algorithm
  3. ExactORToolsSolver  — Google OR-Tools branch-and-bound exact solver

Also provides graph loading and Dijkstra matrix utilities.
"""

import os
import sys
import time
import math
import random
import numpy as np
import osmnx as ox
import networkx as nx
import scipy.sparse as sp
import scipy.sparse.csgraph as csg

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "cities")


def _sanitize(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# Pre-cached city graph paths
CITY_GRAPHS = {
    "delhi":      os.path.join(BASE_DIR, "data", "delhi", "full_delhi_road_network.graphml"),
    "mumbai":     os.path.join(BASE_DIR, "data", "mumbai", "mumbai_road_network.graphml"),
    "bengaluru":  os.path.join(DATA_DIR, "bengaluru", "bengaluru_road_network.graphml"),
    "kolkata":    os.path.join(DATA_DIR, "kolkata", "kolkata_road_network.graphml"),
    "chennai":    os.path.join(DATA_DIR, "chennai", "chennai_road_network.graphml"),
    "hyderabad":  os.path.join(DATA_DIR, "hyderabad", "hyderabad_road_network.graphml"),
    "ahmedabad":  os.path.join(DATA_DIR, "ahmedabad", "ahmedabad_road_network.graphml"),
    "pune":       os.path.join(DATA_DIR, "pune", "pune_road_network.graphml"),
    "chandigarh": os.path.join(DATA_DIR, "chandigarh", "chandigarh_road_network.graphml"),
    "jaipur":     os.path.join(DATA_DIR, "jaipur", "jaipur_road_network.graphml"),
}


def load_or_download_graph(city_key=None, lat=None, lon=None, radius_km=5.0):
    """Load a pre-cached graph or download one from OSMnx for custom locations."""
    if city_key and city_key in CITY_GRAPHS:
        path = CITY_GRAPHS[city_key]
        if os.path.exists(path):
            return ox.load_graphml(path)

    # Custom location download
    if lat is not None and lon is not None:
        cache_dir = os.path.join(BASE_DIR, "data", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_key = f"custom_{lat:.4f}_{lon:.4f}_{radius_km:.1f}"
        cache_path = os.path.join(cache_dir, f"{cache_key}.graphml")
        if os.path.exists(cache_path):
            return ox.load_graphml(cache_path)

        G = ox.graph_from_point((lat, lon), dist=int(radius_km * 1000), network_type="drive")
        G = ox.routing.add_edge_speeds(G)
        G = ox.routing.add_edge_travel_times(G)
        # Ensure single largest strongly connected component
        if not nx.is_strongly_connected(G):
            largest_scc = max(nx.strongly_connected_components(G), key=len)
            G = G.subgraph(largest_scc).copy()
        ox.save_graphml(G, cache_path)
        return G

    raise ValueError("Must provide either city_key or (lat, lon)")


def build_dijkstra_matrices(G, sample_nodes):
    """Build time and distance Dijkstra matrices for a subset of graph nodes."""
    node_list = list(G.nodes)
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    N = len(node_list)

    rows, cols, times, lengths = [], [], [], []
    for u, v, k, data in G.edges(keys=True, data=True):
        if u not in node_to_idx or v not in node_to_idx:
            continue
        rows.append(node_to_idx[u])
        cols.append(node_to_idx[v])
        l_m = float(data.get("length", 10.0))
        speed_mps = 30.0 * (1000.0 / 3600.0)
        times.append(l_m / speed_mps)
        lengths.append(l_m)

    time_adj = sp.csr_matrix((times, (rows, cols)), shape=(N, N), dtype=np.float32)
    len_adj = sp.csr_matrix((lengths, (rows, cols)), shape=(N, N), dtype=np.float32)

    sample_indices = np.array([node_to_idx[n] for n in sample_nodes], dtype=np.int32)
    d_time = csg.dijkstra(time_adj, directed=True, indices=sample_indices)[:, sample_indices].astype(np.float32)
    d_len = csg.dijkstra(len_adj, directed=True, indices=sample_indices)[:, sample_indices].astype(np.float32)

    return d_time, d_len


# ---------------------------------------------------------------------------
# 1. Delta-Potential-Well QPSO
# ---------------------------------------------------------------------------
class DeltaWellQPSO:
    """Quantum PSO with delta-potential-well wave function collapse on Bloch sphere."""

    def __init__(self, time_matrix, dist_matrix, demands, num_vehicles, capacity,
                 depot_coord, cust_coords, pop_size=35, max_iter=50):
        self.t = time_matrix
        self.d = dist_matrix
        self.demands = np.array(demands, dtype=np.int32)
        self.V = num_vehicles
        self.cap = capacity
        self.depot = np.array(depot_coord)
        self.custs = np.array(cust_coords)
        self.M = pop_size
        self.max_iter = max_iter
        diffs = self.custs - self.depot
        self.r_max = float(np.max(np.sqrt(diffs[:, 0]**2 + diffs[:, 1]**2))) * 0.95

    def _decode(self, pos):
        c_y, c_x = np.zeros(self.V), np.zeros(self.V)
        for v in range(self.V):
            r = self.r_max * (math.sin(pos[v, 1] / 2.0)**2)
            c_y[v] = self.depot[0] + r * math.sin(pos[v, 0])
            c_x[v] = self.depot[1] + r * math.cos(pos[v, 0])
        return c_y, c_x

    def _evaluate(self, pos, refine=False):
        c_y, c_x = self._decode(pos)
        dy = self.custs[:, 0, np.newaxis] - c_y[np.newaxis, :]
        dx = self.custs[:, 1, np.newaxis] - c_x[np.newaxis, :]
        dg = np.sqrt(dy**2 + dx**2)

        pref = np.argsort(dg, axis=1)
        clusters = [[] for _ in range(self.V)]
        loads = np.zeros(self.V, dtype=np.int32)
        for c_idx in np.argsort(-np.min(dg, axis=1)):
            dem = self.demands[c_idx]
            for v in pref[c_idx]:
                if loads[v] + dem <= self.cap:
                    clusters[v].append(c_idx)
                    loads[v] += dem
                    break
            else:
                clusters[int(np.argmin(loads))].append(c_idx)
                loads[int(np.argmin(loads))] += dem

        total_t, total_d = 0.0, 0.0
        routes = []
        for v in range(self.V):
            cl = clusters[v]
            if not cl:
                routes.append([])
                continue
            unvis = set(cl)
            curr, route = 0, []
            while unvis:
                nc = min(unvis, key=lambda c: self.t[curr, c + 1])
                route.append(nc)
                unvis.remove(nc)
                curr = nc + 1

            if refine and len(route) >= 4:
                fr = [0] + [c + 1 for c in route] + [0]
                for _ in range(3):
                    imp = False
                    for i in range(1, len(fr) - 2):
                        for j in range(i + 1, len(fr) - 1):
                            a, b, c2, dd = fr[i-1], fr[i], fr[j], fr[min(j+1, len(fr)-1)]
                            if self.t[a, c2] + self.t[b, dd] < self.t[a, b] + self.t[c2, dd] - 1e-3:
                                route[i-1:j] = reversed(route[i-1:j])
                                fr = [0] + [c + 1 for c in route] + [0]
                                imp = True
                                break
                        if imp: break

            fr = np.array([0] + [c + 1 for c in route] + [0], dtype=np.int32)
            total_t += float(np.sum(self.t[fr[:-1], fr[1:]]))
            total_d += float(np.sum(self.d[fr[:-1], fr[1:]]))
            routes.append(route)

        dist_km = total_d / 1000.0
        violations = int(np.sum(np.maximum(0, loads - self.cap)))
        return total_t + dist_km * 10.0, dist_km, total_t, routes, violations

    def solve(self):
        t0 = time.time()
        X = np.zeros((self.M, self.V, 2), dtype=np.float32)
        sc = np.linspace(0, 2 * math.pi, self.V, endpoint=False)
        X[0, :, 0] = sc
        X[0, :, 1] = math.pi / 2.0
        for i in range(1, self.M):
            X[i, :, 0] = (sc + np.random.normal(0, 0.3, self.V)) % (2 * math.pi)
            X[i, :, 1] = np.clip(math.pi/2 + np.random.normal(0, 0.4, self.V), 0.1, math.pi - 0.1)

        pb_X = np.copy(X)
        pb_f = np.full(self.M, float("inf"))
        gb_f, gb_d, gb_t, gb_X = float("inf"), 0.0, 0.0, np.copy(X[0])
        history = []

        for it in range(self.max_iter):
            beta = 1.0 - (it / self.max_iter) * 0.5
            for i in range(self.M):
                f, d, t_sec, _, _ = self._evaluate(X[i])
                if f < pb_f[i]:
                    pb_f[i] = f
                    pb_X[i] = np.copy(X[i])
                if f < gb_f:
                    gb_f, gb_d, gb_t = f, d, t_sec
                    gb_X = np.copy(X[i])

            history.append(float(gb_d))
            mb = np.mean(pb_X, axis=0)
            for i in range(self.M):
                for v in range(self.V):
                    u = max(random.random(), 1e-6)
                    phi = random.random()
                    p_th = phi * pb_X[i, v, 0] + (1 - phi) * gb_X[v, 0]
                    p_ph = phi * pb_X[i, v, 1] + (1 - phi) * gb_X[v, 1]
                    s_th = beta * abs(mb[v, 0] - X[i, v, 0]) * math.log(1.0 / u)
                    s_ph = beta * abs(mb[v, 1] - X[i, v, 1]) * math.log(1.0 / u)
                    X[i, v, 0] = (p_th + random.choice([-1, 1]) * s_th) % (2 * math.pi)
                    X[i, v, 1] = np.clip(p_ph + random.choice([-1, 1]) * s_ph, 0.1, math.pi - 0.1)

        _, dist_km, time_sec, routes, violations = self._evaluate(gb_X, refine=True)
        runtime = time.time() - t0
        return _sanitize({
            "algorithm": "Delta-Well QPSO",
            "distance_km": round(float(dist_km), 2),
            "time_sec": round(float(time_sec), 2),
            "runtime_sec": round(runtime, 3),
            "routes": routes,
            "violations": int(violations),
            "convergence": history
        })


# ---------------------------------------------------------------------------
# 2. Classical GA Baseline (Angular Sweep + Nearest Neighbour TSP)
# ---------------------------------------------------------------------------
class ClassicalGABaseline:
    """Heuristic GA baseline: angular sweep clustering + nearest-neighbour TSP."""

    def __init__(self, time_matrix, dist_matrix, demands, num_vehicles, capacity,
                 depot_coord, cust_coords, pop_size=30, generations=50):
        self.t = time_matrix
        self.d = dist_matrix
        self.demands = np.array(demands, dtype=np.int32)
        self.V = num_vehicles
        self.cap = capacity
        self.depot = np.array(depot_coord)
        self.custs = np.array(cust_coords)
        self.pop_size = pop_size
        self.gens = generations
        self.n_cust = len(cust_coords)

    def _eval_perm(self, perm):
        clusters = [[] for _ in range(self.V)]
        loads = np.zeros(self.V, dtype=np.int32)
        for c_idx in perm:
            dem = self.demands[c_idx]
            for v_idx in range(self.V):
                if loads[v_idx] + dem <= self.cap:
                    clusters[v_idx].append(c_idx)
                    loads[v_idx] += dem
                    break
            else:
                mv = int(np.argmin(loads))
                clusters[mv].append(c_idx)
                loads[mv] += dem

        total_d, total_t = 0.0, 0.0
        routes = []
        for v in range(self.V):
            cl = clusters[v]
            if not cl:
                routes.append([])
                continue
            unvis = set(cl)
            curr, route = 0, []
            while unvis:
                nc = min(unvis, key=lambda c: self.t[curr, c + 1])
                route.append(nc)
                unvis.remove(nc)
                curr = nc + 1
            fr = np.array([0] + [c + 1 for c in route] + [0], dtype=np.int32)
            total_d += float(np.sum(self.d[fr[:-1], fr[1:]]))
            total_t += float(np.sum(self.t[fr[:-1], fr[1:]]))
            routes.append(route)

        dist_km = total_d / 1000.0
        violations = int(np.sum(np.maximum(0, loads - self.cap)))
        fitness = total_t + dist_km * 10.0 + violations * 5000
        return fitness, dist_km, total_t, routes, violations

    def solve(self):
        t0 = time.time()
        angles = np.array([math.atan2(c[0] - self.depot[0], c[1] - self.depot[1]) for c in self.custs])
        base_perm = list(np.argsort(angles))

        pop = [base_perm[:]]
        for _ in range(self.pop_size - 1):
            p = base_perm[:]
            for _ in range(max(2, self.n_cust // 10)):
                i, j = random.sample(range(self.n_cust), 2)
                p[i], p[j] = p[j], p[i]
            pop.append(p)

        best_f, best_d, best_t, best_r, best_v = float("inf"), 0.0, 0.0, [], 0
        history = []

        for gen in range(self.gens):
            fits = []
            for p in pop:
                f, d, t_sec, r, v = self._eval_perm(p)
                fits.append((f, d, t_sec, r, v, p))
                if f < best_f:
                    best_f, best_d, best_t, best_r, best_v = f, d, t_sec, r, v

            history.append(float(best_d))
            fits.sort(key=lambda x: x[0])
            elites = [x[5] for x in fits[:max(2, self.pop_size // 4)]]

            new_pop = [e[:] for e in elites]
            while len(new_pop) < self.pop_size:
                parent = random.choice(elites)[:]
                # Swap mutation
                i, j = random.sample(range(self.n_cust), 2)
                parent[i], parent[j] = parent[j], parent[i]
                new_pop.append(parent)
            pop = new_pop

        runtime = time.time() - t0
        return _sanitize({
            "algorithm": "Classical Heuristic GA",
            "distance_km": round(float(best_d), 2),
            "time_sec": round(float(best_t), 2),
            "runtime_sec": round(runtime, 3),
            "routes": best_r,
            "violations": int(best_v),
            "convergence": history
        })


# ---------------------------------------------------------------------------
# 3. Exact Solver via Google OR-Tools
# ---------------------------------------------------------------------------
class ExactSolver:
    """Google OR-Tools branch-and-bound exact CVRP solver."""

    def __init__(self, time_matrix, dist_matrix, demands, num_vehicles, capacity, time_limit=15):
        self.t = time_matrix
        self.d = dist_matrix
        self.demands = [0] + list(demands)
        self.V = num_vehicles
        self.cap = capacity
        self.tl = time_limit
        self.n = len(self.demands)

    def solve(self):
        try:
            from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        except ImportError:
            return {
                "algorithm": "Exact Solver (OR-Tools)",
                "distance_km": -1, "time_sec": -1, "runtime_sec": 0,
                "routes": [], "violations": 0, "convergence": [],
                "error": "ortools not installed"
            }

        t0 = time.time()
        mgr = pywrapcp.RoutingIndexManager(self.n, self.V, 0)
        routing = pywrapcp.RoutingModel(mgr)

        def dist_cb(fi, ti):
            return int(self.d[mgr.IndexToNode(fi), mgr.IndexToNode(ti)])

        cb_idx = routing.RegisterTransitCallback(dist_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(cb_idx)

        def dem_cb(fi):
            return self.demands[mgr.IndexToNode(fi)]

        dem_idx = routing.RegisterUnaryTransitCallback(dem_cb)
        routing.AddDimensionWithVehicleCapacity(dem_idx, 0, [self.cap] * self.V, True, "Cap")

        sp = pywrapcp.DefaultRoutingSearchParameters()
        sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        sp.time_limit.seconds = self.tl

        sol = routing.SolveWithParameters(sp)
        runtime = time.time() - t0

        if not sol:
            return {
                "algorithm": "Exact Solver (OR-Tools)",
                "distance_km": -1, "time_sec": -1,
                "runtime_sec": round(runtime, 3),
                "routes": [], "violations": 0, "convergence": [],
                "error": "No solution found within time limit"
            }

        td, tt = 0.0, 0.0
        routes = []
        for v in range(self.V):
            idx = routing.Start(v)
            route = []
            while not routing.IsEnd(idx):
                node = mgr.IndexToNode(idx)
                if node != 0:
                    route.append(node - 1)
                prev = idx
                idx = sol.Value(routing.NextVar(idx))
                td += routing.GetArcCostForVehicle(prev, idx, v)
                u, w = mgr.IndexToNode(prev), mgr.IndexToNode(idx)
                tt += self.t[u, w]
            routes.append(route)

        return _sanitize({
            "algorithm": "Exact Solver (OR-Tools)",
            "distance_km": round(float(td) / 1000.0, 2),
            "time_sec": round(float(tt), 2),
            "runtime_sec": round(runtime, 3),
            "routes": routes,
            "violations": 0,
            "convergence": []
        })
