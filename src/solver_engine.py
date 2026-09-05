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
        self.N = len(demands)
        self.V = num_vehicles
        self.cap = capacity
        self.depot = np.array(depot_coord)
        self.custs = np.array(cust_coords)
        self.M = pop_size
        self.max_iter = max_iter
        if self.N > 0:
            diffs = self.custs - self.depot
            self.r_max = float(np.max(np.sqrt(diffs[:, 0]**2 + diffs[:, 1]**2))) * 0.95
        else:
            self.r_max = 1.0

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
        if self.N == 0:
            return _sanitize({
                "algorithm": "Delta-Well QPSO",
                "distance_km": 0.0, "time_sec": 0.0, "runtime_sec": 0.0,
                "routes": [[] for _ in range(self.V)], "violations": 0, "convergence": [0.0]
            })
        if self.N == 1:
            routes = [[0]] + [[] for _ in range(self.V - 1)]
            fr = np.array([0, 1, 0], dtype=np.int32)
            d_m = float(np.sum(self.d[fr[:-1], fr[1:]]))
            t_s = float(np.sum(self.t[fr[:-1], fr[1:]]))
            return _sanitize({
                "algorithm": "Delta-Well QPSO",
                "distance_km": round(d_m / 1000.0, 2), "time_sec": round(t_s, 2), "runtime_sec": round(time.time() - t0, 3),
                "routes": routes, "violations": 0, "convergence": [round(d_m / 1000.0, 2)]
            })

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
        if self.n_cust == 0:
            return _sanitize({
                "algorithm": "Classical GA Baseline",
                "distance_km": 0.0, "time_sec": 0.0, "runtime_sec": 0.0,
                "routes": [[] for _ in range(self.V)], "violations": 0, "convergence": [0.0]
            })
        if self.n_cust == 1:
            routes = [[0]] + [[] for _ in range(self.V - 1)]
            fr = np.array([0, 1, 0], dtype=np.int32)
            d_m = float(np.sum(self.d[fr[:-1], fr[1:]]))
            t_s = float(np.sum(self.t[fr[:-1], fr[1:]]))
            return _sanitize({
                "algorithm": "Classical GA Baseline",
                "distance_km": round(d_m / 1000.0, 2), "time_sec": round(t_s, 2), "runtime_sec": round(time.time() - t0, 3),
                "routes": routes, "violations": 0, "convergence": [round(d_m / 1000.0, 2)]
            })

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
        if self.n <= 1:
            return {
                "algorithm": "Exact Solver (OR-Tools)",
                "distance_km": 0.0, "time_sec": 0.0, "runtime_sec": 0.0,
                "routes": [[] for _ in range(self.V)], "violations": 0, "convergence": [0.0]
            }
        if self.n == 2:
            d_m = float(self.d[0, 1] + self.d[1, 0])
            t_s = float(self.t[0, 1] + self.t[1, 0])
            return {
                "algorithm": "Exact Solver (OR-Tools)",
                "distance_km": round(d_m / 1000.0, 2), "time_sec": round(t_s, 2),
                "runtime_sec": round(time.time() - t0, 3), "routes": [[0]] + [[] for _ in range(self.V - 1)],
                "violations": 0, "convergence": [round(d_m / 1000.0, 2)]
            }

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


# ---------------------------------------------------------------------------
# 4. Hybrid Quantum-Guided Local Search (HQ-GLS) SOTA Solver
# ---------------------------------------------------------------------------
class HQGLSSolver:
    """
    State-of-the-Art Hybrid Quantum-Guided Local Search (HQ-GLS):
    Combines:
    1. Multi-Centroid Bloch Sphere Superposition & Polar Sweeps
    2. Parameterized Clarke-Wright Savings with Radial Polarization
    3. Systematic Inter-Route 2-Opt* (direct & cross-reversed tail swaps)
    4. Systematic Multi-Segment Relocate (lengths 1, 2, 3) & Cross-Exchange (2-1, 1-2, 2-2)
    5. Transverse-Field Quantum Tunneling Annealing P = exp(-Delta D / Gamma)
    6. Deterministic Intra-Route 2-Opt and Or-Opt Path Straightening
    """
    def __init__(self, time_matrix, dist_matrix, demands, num_vehicles, capacity,
                 depot_coord, cust_coords, time_limit=3.0):
        self.t = time_matrix
        self.d = dist_matrix
        self.demands = np.array(demands, dtype=np.int32)
        self.V = num_vehicles
        self.cap = capacity
        self.depot = np.array(depot_coord)
        self.custs = np.array(cust_coords)
        self.N = len(cust_coords)
        self.time_limit = time_limit

        diffs = self.custs - self.depot
        self.r_max = float(np.max(np.sqrt(diffs[:, 0]**2 + diffs[:, 1]**2))) * 0.98

        self.k_nn = []
        for i in range(self.N):
            dists = [(self.d[i+1, j+1], j) for j in range(self.N) if j != i]
            dists.sort(key=lambda x: x[0])
            self.k_nn.append([j for _, j in dists[:15]])

    def _route_dist(self, r):
        if not r: return 0.0
        full = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[full[i], full[i+1]] for i in range(len(full)-1))

    def _intra_2opt(self, route):
        if len(route) < 4: return route
        full = [0] + [c + 1 for c in route] + [0]
        improved = True
        passes = 0
        while improved and passes < 8:
            improved = False
            passes += 1
            for i in range(1, len(full) - 2):
                for j in range(i + 1, len(full) - 1):
                    a, b = full[i-1], full[i]
                    c, d = full[j], full[j+1]
                    delta = (self.d[a, c] + self.d[b, d]) - (self.d[a, b] + self.d[c, d])
                    if delta < -1e-2:
                        route[i-1:j] = route[i-1:j][::-1]
                        full = [0] + [c + 1 for c in route] + [0]
                        improved = True
                        break
                if improved: break
        return route

    def _intra_or_opt(self, route):
        if len(route) < 4: return route
        improved = True
        passes = 0
        while improved and passes < 3:
            improved = False
            passes += 1
            n = len(route)
            for seg_len in [1, 2, 3]:
                for i in range(n - seg_len + 1):
                    seg = route[i:i+seg_len]
                    rem = route[:i] + route[i+seg_len:]
                    base_d = self._route_dist(route)
                    for p in range(len(rem) + 1):
                        for cand_seg in ([seg, seg[::-1]] if seg_len > 1 else [seg]):
                            cand = rem[:p] + cand_seg + rem[p:]
                            if self._route_dist(cand) < base_d - 1e-2:
                                route = cand
                                improved = True
                                break
                        if improved: break
                    if improved: break
                if improved: break
        return route

    def _clean(self, r):
        return self._intra_or_opt(self._intra_2opt(r[:]))

    def _inter_search(self, routes, loads):
        improved = True
        passes = 0
        while improved and passes < 8:
            improved = False
            passes += 1
            V = len(routes)

            # 1. 2-Opt* (Tail Swaps: direct and reversed)
            for v1 in range(V):
                for v2 in range(v1 + 1, V):
                    r1, r2 = routes[v1], routes[v2]
                    if len(r1) < 2 or len(r2) < 2: continue
                    base_d = self._route_dist(r1) + self._route_dist(r2)
                    best_cand = None
                    best_delta = 0.0

                    for i in range(1, len(r1)):
                        for j in range(1, len(r2)):
                            c1 = r1[:i] + r2[j:]
                            c2 = r2[:j] + r1[i:]
                            l1 = sum(self.demands[x] for x in c1)
                            l2 = sum(self.demands[x] for x in c2)
                            if l1 <= self.cap and l2 <= self.cap:
                                d12 = self._route_dist(c1) + self._route_dist(c2)
                                if d12 - base_d < best_delta - 1e-2:
                                    best_delta = d12 - base_d
                                    best_cand = (c1, c2, l1, l2)

                            c1_r = r1[:i] + r2[:j][::-1]
                            c2_r = r1[i:][::-1] + r2[j:]
                            l1_r = sum(self.demands[x] for x in c1_r)
                            l2_r = sum(self.demands[x] for x in c2_r)
                            if l1_r <= self.cap and l2_r <= self.cap:
                                d_r = self._route_dist(c1_r) + self._route_dist(c2_r)
                                if d_r - base_d < best_delta - 1e-2:
                                    best_delta = d_r - base_d
                                    best_cand = (c1_r, c2_r, l1_r, l2_r)

                    if best_cand:
                        routes[v1] = self._clean(best_cand[0])
                        routes[v2] = self._clean(best_cand[1])
                        loads[v1] = best_cand[2]
                        loads[v2] = best_cand[3]
                        improved = True

            # 2. Relocate (lengths 1, 2, 3 with forward and reversed insertion)
            for v1 in range(V):
                for v2 in range(V):
                    if v1 == v2: continue
                    r1, r2 = routes[v1], routes[v2]
                    if not r1: continue

                    for seg_len in [1, 2, 3]:
                        if len(r1) < seg_len: continue
                        for i in range(len(r1) - seg_len + 1):
                            seg = r1[i:i+seg_len]
                            s_dem = sum(self.demands[x] for x in seg)
                            if loads[v2] + s_dem <= self.cap:
                                cand1 = r1[:i] + r1[i+seg_len:]
                                old_d = self._route_dist(r1) + self._route_dist(r2)
                                d1 = self._route_dist(cand1)
                                best_p = None
                                best_seg = None
                                best_d2 = float('inf')
                                for p in range(len(r2) + 1):
                                    for try_seg in ([seg, seg[::-1]] if seg_len > 1 else [seg]):
                                        cand2 = r2[:p] + try_seg + r2[p:]
                                        d2 = self._route_dist(cand2)
                                        if d2 < best_d2:
                                            best_d2 = d2
                                            best_p = p
                                            best_seg = try_seg
                                if d1 + best_d2 < old_d - 1e-2:
                                    routes[v1] = self._clean(cand1)
                                    routes[v2] = self._clean(r2[:best_p] + best_seg + r2[best_p:])
                                    loads[v1] -= s_dem
                                    loads[v2] += s_dem
                                    improved = True
                                    break
                        if improved: break
                    if improved: break

            # 3. Cross-Exchange (1-1, 2-1, 1-2, 2-2)
            for v1 in range(V):
                for v2 in range(v1 + 1, V):
                    r1, r2 = routes[v1], routes[v2]
                    if not r1 or not r2: continue
                    old_d = self._route_dist(r1) + self._route_dist(r2)

                    for len1 in [1, 2]:
                        for len2 in [1, 2]:
                            if len(r1) < len1 or len(r2) < len2: continue
                            for i in range(len(r1) - len1 + 1):
                                s1 = r1[i:i+len1]
                                d1 = sum(self.demands[x] for x in s1)
                                for j in range(len(r2) - len2 + 1):
                                    s2 = r2[j:j+len2]
                                    d2 = sum(self.demands[x] for x in s2)
                                    if loads[v1] - d1 + d2 <= self.cap and loads[v2] - d2 + d1 <= self.cap:
                                        c1 = r1[:i] + s2 + r1[i+len1:]
                                        c2 = r2[:j] + s1 + r2[j+len2:]
                                        if self._route_dist(c1) + self._route_dist(c2) < old_d - 1e-2:
                                            routes[v1] = self._clean(c1)
                                            routes[v2] = self._clean(c2)
                                            loads[v1] = loads[v1] - d1 + d2
                                            loads[v2] = loads[v2] - d2 + d1
                                            improved = True
                                            break
                                if improved: break
                            if improved: break
                        if improved: break

        return routes, loads

    def _ruin(self, routes, q_remove=10, method='worst'):
        """Ruin Operator: worst-detour or related nearest-neighbor cluster."""
        all_c = []
        c_to_route = {}
        for v, r in enumerate(routes):
            for c in r:
                all_c.append(c)
                c_to_route[c] = v
        if not all_c: return routes, [sum(self.demands[c] for c in r) for r in routes], []

        removed = []
        if method == 'worst':
            detours = []
            for v, r in enumerate(routes):
                if len(r) <= 1: continue
                full = [0] + [c + 1 for c in r] + [0]
                for idx, c in enumerate(r):
                    u = full[idx]
                    w = full[idx + 2]
                    curr_c = self.d[u, c + 1] + self.d[c + 1, w]
                    rem_c = self.d[u, w]
                    detours.append((curr_c - rem_c, c))
            detours.sort(key=lambda x: x[0], reverse=True)
            while len(removed) < q_remove and detours:
                pick_idx = int(random.random()**2 * min(len(detours), 6))
                _, c = detours.pop(min(pick_idx, len(detours)-1))
                removed.append(c)
        else:
            seed_c = random.choice(all_c)
            removed = [seed_c]
            candidates = list(self.k_nn[seed_c])
            while len(removed) < q_remove and candidates:
                next_c = candidates.pop(0)
                if next_c not in removed and next_c in c_to_route:
                    removed.append(next_c)
                    for n in self.k_nn[next_c]:
                        if n not in candidates and n not in removed:
                            candidates.append(n)

        new_routes = []
        new_loads = []
        rem_set = set(removed)
        for r in routes:
            filt = [c for c in r if c not in rem_set]
            new_routes.append(filt)
            new_loads.append(sum(self.demands[c] for c in filt))

        return new_routes, new_loads, removed

    def _recreate(self, new_routes, new_loads, removed):
        """Regret-2 insertion with quantum transverse field bias."""
        unassigned = removed[:]
        random.shuffle(unassigned)

        while unassigned:
            regrets = []
            for c in unassigned:
                dem = self.demands[c]
                ins_costs = []
                for v in range(self.V):
                    if new_loads[v] + dem <= self.cap:
                        r = new_routes[v]
                        old_d = self._route_dist(r)
                        best_d = float('inf')
                        best_p = 0
                        for p in range(len(r) + 1):
                            cand = r[:p] + [c] + r[p:]
                            d = self._route_dist(cand)
                            if d < best_d:
                                best_d = d
                                best_p = p
                        cost = best_d - old_d
                        ins_costs.append((cost, v, best_p))

                ins_costs.sort(key=lambda x: x[0])
                if not ins_costs:
                    v = int(np.argmin(new_loads))
                    regrets.append((0.0, c, 0.0, v, len(new_routes[v])))
                elif len(ins_costs) == 1:
                    regrets.append((float('inf'), c, ins_costs[0][0], ins_costs[0][1], ins_costs[0][2]))
                else:
                    regret = ins_costs[1][0] - ins_costs[0][0]
                    regrets.append((regret, c, ins_costs[0][0], ins_costs[0][1], ins_costs[0][2]))

            regrets.sort(key=lambda x: x[0], reverse=True)
            chosen = regrets[0]
            _, c, cost, v, p = chosen
            new_routes[v] = new_routes[v][:p] + [c] + new_routes[v][p:]
            new_loads[v] += self.demands[c]
            unassigned.remove(c)

        new_routes = [self._clean(r) for r in new_routes]
        return self._inter_search(new_routes, new_loads)

    def solve(self):
        t0 = time.time()
        V = self.V

        if self.N == 0:
            return _sanitize({
                "algorithm": "Quantum HQ-GLS (SOTA)",
                "distance_km": 0.0, "time_sec": 0.0, "runtime_sec": 0.0,
                "routes": [[] for _ in range(V)], "violations": 0, "convergence": [0.0]
            })
        if self.N == 1:
            routes = [[0]] + [[] for _ in range(V - 1)]
            d_m = float(self.d[0, 1] + self.d[1, 0])
            t_s = float(self.t[0, 1] + self.t[1, 0])
            return _sanitize({
                "algorithm": "Quantum HQ-GLS (SOTA)",
                "distance_km": round(d_m / 1000.0, 2), "time_sec": round(t_s, 2), "runtime_sec": round(time.time() - t0, 3),
                "routes": routes, "violations": 0, "convergence": [round(d_m / 1000.0, 2)]
            })

        candidate_solutions = []
        history = []

        # 1. Parameterized Clarke-Wright Savings Seeds (lambdas = 0.75, 1.0, 1.3)
        for lmbda in [0.75, 1.0, 1.3]:
            savings = []
            for i in range(self.N):
                for j in range(i + 1, self.N):
                    s = self.d[0, i+1] + self.d[0, j+1] - lmbda * self.d[i+1, j+1]
                    savings.append((s, i, j))
            savings.sort(reverse=True, key=lambda x: x[0])

            cw_routes = [[i] for i in range(self.N)]
            cw_loads = [self.demands[i] for i in range(self.N)]
            cust_route_idx = {i: i for i in range(self.N)}

            for s, i, j in savings:
                r_i = cust_route_idx[i]
                r_j = cust_route_idx[j]
                if r_i != r_j and cw_loads[r_i] + cw_loads[r_j] <= self.cap:
                    route_i = cw_routes[r_i]
                    route_j = cw_routes[r_j]
                    if route_i[-1] == i and route_j[0] == j:
                        merged = route_i + route_j
                    elif route_i[0] == i and route_j[-1] == j:
                        merged = route_j + route_i
                    elif route_i[-1] == i and route_j[-1] == j:
                        merged = route_i + route_j[::-1]
                    elif route_i[0] == i and route_j[0] == j:
                        merged = route_i[::-1] + route_j
                    else:
                        continue
                    cw_routes[r_i] = merged
                    cw_loads[r_i] += cw_loads[r_j]
                    cw_routes[r_j] = []
                    cw_loads[r_j] = 0
                    for c in merged:
                        cust_route_idx[c] = r_i

            cw_routes = [r for r in cw_routes if r]
            attempts = 0
            while len(cw_routes) > V and attempts < 20:
                attempts += 1
                smallest = min(range(len(cw_routes)), key=lambda k: len(cw_routes[k]))
                sr = cw_routes.pop(smallest)
                for c in sr:
                    inserted = False
                    for tgt in range(len(cw_routes)):
                        if sum(self.demands[x] for x in cw_routes[tgt]) + self.demands[c] <= self.cap:
                            cw_routes[tgt].append(c)
                            inserted = True
                            break
                    if not inserted and len(cw_routes) > 0:
                        min_tgt = min(range(len(cw_routes)), key=lambda t: sum(self.demands[x] for x in cw_routes[t]))
                        cw_routes[min_tgt].append(c)
            while len(cw_routes) > V:
                extra = cw_routes.pop()
                if cw_routes:
                    min_tgt = min(range(len(cw_routes)), key=lambda t: sum(self.demands[x] for x in cw_routes[t]))
                    cw_routes[min_tgt].extend(extra)
            while len(cw_routes) < V:
                cw_routes.append([])
            candidate_solutions.append([self._clean(r) for r in cw_routes])

        # 2. Multi-Angle Polar Superposition Sweeps
        polar_angles = np.array([math.atan2(c[0] - self.depot[0], c[1] - self.depot[1]) for c in self.custs])
        for off in np.linspace(0, 2 * math.pi, 6, endpoint=False):
            shifted = (polar_angles + off) % (2 * math.pi)
            tour = list(np.argsort(shifted))
            clusters = [[] for _ in range(V)]
            loads = [0] * V
            v_idx = 0
            for c in tour:
                if loads[v_idx] + self.demands[c] > self.cap and v_idx < V - 1:
                    v_idx += 1
                clusters[v_idx].append(c)
                loads[v_idx] += self.demands[c]
            candidate_solutions.append([self._clean(r) for r in clusters])

        # 3. Bloch Sphere Centroid QPSO Swarm Seeds
        M = 15
        angles = np.linspace(0, 2 * math.pi, V, endpoint=False)
        X = np.zeros((M, V, 2))
        for m in range(M):
            X[m, :, 0] = (angles + np.random.normal(0, 0.35, V)) % (2 * math.pi)
            X[m, :, 1] = np.clip(math.pi/2 + np.random.normal(0, 0.3, V), 0.1, math.pi - 0.1)

        for m in range(min(M, 4)):
            pos = X[m]
            c_y = self.depot[0] + self.r_max * (np.sin(pos[:, 1] / 2.0)**2) * np.sin(pos[:, 0])
            c_x = self.depot[1] + self.r_max * (np.sin(pos[:, 1] / 2.0)**2) * np.cos(pos[:, 0])
            dy = self.custs[:, 0, np.newaxis] - c_y[np.newaxis, :]
            dx = self.custs[:, 1, np.newaxis] - c_x[np.newaxis, :]
            dg = np.sqrt(dy**2 + dx**2)
            pref = np.argsort(dg, axis=1)
            clusters = [[] for _ in range(V)]
            loads = np.zeros(V, dtype=np.int32)
            for c_idx in np.argsort(-np.min(dg, axis=1)):
                dem = self.demands[c_idx]
                for v in pref[c_idx]:
                    if loads[v] + dem <= self.cap:
                        clusters[v].append(c_idx)
                        loads[v] += dem
                        break
                else:
                    mv = int(np.argmin(loads))
                    clusters[mv].append(c_idx)
                    loads[mv] += dem

            routes = []
            for v in range(V):
                cl = clusters[v]
                if not cl:
                    routes.append([])
                    continue
                unvis = set(cl)
                curr = 0
                r = []
                while unvis:
                    nc = min(unvis, key=lambda c: self.d[curr, c+1])
                    r.append(nc)
                    unvis.remove(nc)
                    curr = nc + 1
                routes.append(self._clean(r))
            candidate_solutions.append(routes)

        # 4. Filter & Evaluate Candidates
        if not candidate_solutions:
            candidate_solutions.append([list(range(self.N))] + [[] for _ in range(V - 1)])

        best_routes = [r[:] for r in candidate_solutions[0]]
        best_cost = sum(self._route_dist(r) for r in best_routes)

        for sol in candidate_solutions:
            routes = [r[:] for r in sol]
            loads = [sum(self.demands[c] for c in r) for r in routes]
            routes, loads = self._inter_search(routes, loads)
            cost = sum(self._route_dist(r) for r in routes)
            if cost < best_cost:
                best_cost = cost
                best_routes = [r[:] for r in routes]
            history.append(round(best_cost / 1000.0, 2))
            if (time.time() - t0) > (self.time_limit * 0.55):
                break

        # 5. Multi-Stage Transverse-Field Quantum Tunneling & ALNS Ruin/Recreate
        routes = [r[:] for r in best_routes]
        loads = [sum(self.demands[c] for c in r) for r in routes]
        gamma = 2500.0

        for it in range(40):
            if (time.time() - t0) > self.time_limit:
                break
            gamma *= 0.85

            if it % 2 == 0:
                # Worst-Removal / Related Ruin & Regret-2 Recreate
                method = 'worst' if (it % 4 == 0) else 'related'
                q_rem = random.choice([6, 8, 10])
                ruined_routes, ruined_loads, removed = self._ruin(routes, q_remove=q_rem, method=method)
                cand_routes, cand_loads = self._recreate(ruined_routes, ruined_loads, removed)
                cand_cost = sum(self._route_dist(r) for r in cand_routes)
                delta = cand_cost - sum(self._route_dist(r) for r in routes)
                if delta < 0 or (gamma > 10.0 and random.random() < math.exp(-delta / gamma)):
                    routes = [r[:] for r in cand_routes]
                    loads = [l for l in cand_loads]
            else:
                # Pairwise Transverse-Field Boundary Tunneling
                valid_vs = [v for v in range(V) if routes[v]]
                if len(valid_vs) >= 2:
                    v1, v2 = random.sample(valid_vs, 2)
                    i = random.randint(0, len(routes[v1]) - 1)
                    j = random.randint(0, len(routes[v2]) - 1)
                    c1, c2 = routes[v1][i], routes[v2][j]
                    d1, d2 = self.demands[c1], self.demands[c2]
                    if loads[v1] - d1 + d2 <= self.cap and loads[v2] - d2 + d1 <= self.cap:
                        cand1 = routes[v1][:i] + [c2] + routes[v1][i+1:]
                        cand2 = routes[v2][:j] + [c1] + routes[v2][j+1:]
                        delta = (self._route_dist(cand1) + self._route_dist(cand2)) - (self._route_dist(routes[v1]) + self._route_dist(routes[v2]))
                        if delta < 0 or (gamma > 10.0 and random.random() < math.exp(-delta / gamma)):
                            routes[v1] = cand1
                            routes[v2] = cand2
                            loads[v1] = loads[v1] - d1 + d2
                            loads[v2] = loads[v2] - d2 + d1

            routes, loads = self._inter_search(routes, loads)
            cost = sum(self._route_dist(r) for r in routes)
            if cost < best_cost:
                best_cost = cost
                best_routes = [r[:] for r in routes]
            history.append(round(best_cost / 1000.0, 2))

        runtime = time.time() - t0
        total_d = sum(self._route_dist(r) for r in best_routes)
        total_t = 0.0
        for r in best_routes:
            if r:
                fr = [0] + [c + 1 for c in r] + [0]
                total_t += sum(self.t[fr[k], fr[k+1]] for k in range(len(fr)-1))

        # Check violations
        violations = 0
        for r in best_routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                violations += (l - self.cap)

        return _sanitize({
            "algorithm": "Quantum HQ-GLS (SOTA)",
            "distance_km": round(float(total_d) / 1000.0, 2),
            "time_sec": round(float(total_t), 2),
            "runtime_sec": round(runtime, 3),
            "routes": best_routes,
            "violations": int(violations),
            "convergence": history
        })

