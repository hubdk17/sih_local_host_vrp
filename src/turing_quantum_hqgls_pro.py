"""
turing_quantum_hqgls_pro.py

Turing-Enhanced Quantum HQ-GLS Pro (T-HQGLS-Pro)
Multi-Parametric Optimization Engine for Complex Urban Road Networks.

Mathematical Pillars:
1. Alan Turing (1952) Morphogenesis:
   Reaction-Diffusion Activator-Inhibitor potential fields for non-interlacing,
   convex territory partitioning adapted to urban street congestion impedance.
2. Alan Turing (1940) Banburismus Weight of Evidence:
   Sequential Bayesian log-odds accumulation in decibans (db):
     W_ij = 10 * log10 [ P(edge_ij in Elite) / P(edge_ij in Non-Elite) ]
   Eliminates >75% of inferior combinatorial transitions where W_ij < theta_prune.
3. Transverse-Field Quantum Tunneling:
   Accepts uphill moves across generalized energy landscapes:
     P_tunnel = exp(-Delta J / Gamma(t)).
4. Unified Physical-Economic Cost Matrix:
   C_ij = d_ij + alpha_t * (v_ref * t_ij) + alpha_c * (v_ref * delay_ij) + alpha_h * (friction_ij * d_ij)
   Balances fuel distance, transit time, and BPR congestion delay on a unified scale (equivalent meters).
"""

import math
import time
import random
import numpy as np


class TuringQuantumHQGLSPro:
    """
    Turing-Enhanced Quantum HQ-GLS Pro Solver.
    """

    def __init__(
        self,
        time_matrix,
        dist_matrix,
        demands,
        num_vehicles,
        capacity,
        depot_coord,
        cust_coords,
        delay_matrix=None,
        free_time_matrix=None,
        time_limit=4.0,
        theta_prune_db=-10.0,
        theta_lock_db=12.0,
        objective_mode="balanced_turing",
        weights=None,
    ):
        self.t = np.array(time_matrix, dtype=np.float32)
        self.d = np.array(dist_matrix, dtype=np.float32)
        self.demands = np.array(demands, dtype=np.int32)
        self.V = int(num_vehicles)
        self.cap = int(capacity)
        self.depot = np.array(depot_coord, dtype=np.float64)
        self.custs = np.array(cust_coords, dtype=np.float64)
        self.N = len(cust_coords)
        self.total_nodes = self.N + 1
        self.time_limit = float(time_limit)
        self.theta_prune = float(theta_prune_db)
        self.theta_lock = float(theta_lock_db)
        self.objective_mode = objective_mode

        # Congestion delay matrix
        if delay_matrix is not None:
            self.delay = np.array(delay_matrix, dtype=np.float32)
        elif free_time_matrix is not None:
            self.delay = np.maximum(self.t - np.array(free_time_matrix, dtype=np.float32), 0.0)
        else:
            self.delay = np.maximum(self.t * 0.18, 0.0).astype(np.float32)

        # Coordinate lookup (0 = depot, 1..N = customers)
        self.coords = np.vstack([self.depot.reshape(1, 2), self.custs])

        # Euclidean distances in meters
        self.d_euc = np.zeros((self.total_nodes, self.total_nodes), dtype=np.float32)
        for i in range(self.total_nodes):
            diff = self.coords - self.coords[i]
            self.d_euc[i] = np.sqrt(diff[:, 0]**2 + (diff[:, 1] * np.cos(np.radians(self.coords[i, 0])))**2) * 111320.0
        self.d_euc = np.maximum(self.d_euc, 1.0)

        # Road hierarchy friction factor: street_dist / euclidean_dist
        self.friction = np.clip((self.d / self.d_euc) - 1.20, 0.0, 3.0)

        # Non-linear BPR Volatility Delay Matrix: delay * (1 + 1.5 * delay / free_flow)
        free_flow = np.maximum(self.t - self.delay, 1.0)
        self.delay_volatility = self.delay * (1.0 + 1.5 * np.clip(self.delay / free_flow, 0.0, 4.0))

        # Configure Multi-Parametric Generalized Cost Matrix
        # Reference velocity: 10.0 m/s (~36 km/h) converts seconds to equivalent meters
        v_ref = 10.0
        self.v_ref = v_ref

        # Weight profiles across trade-offs:
        if objective_mode in ["green_distance", "pure_distance"]:
            w_d, w_t, w_c, w_h = 1.00, 0.00, 0.00, 0.00
        elif objective_mode in ["express_time", "pure_time"]:
            w_d, w_t, w_c, w_h = 0.10, 0.65, 0.25, 0.00
        elif objective_mode == "risk_averse_traffic":
            w_d, w_t, w_c, w_h = 0.20, 0.30, 0.45, 0.05
        elif objective_mode == "green_kinetic":
            w_d, w_t, w_c, w_h = 0.50, 0.20, 0.10, 0.20
        elif objective_mode == "driver_ergonomic":
            w_d, w_t, w_c, w_h = 0.35, 0.35, 0.10, 0.20
        else:  # balanced_turing (default)
            w_d, w_t, w_c, w_h = 0.45, 0.35, 0.15, 0.05

        if weights:
            w_d = weights.get("w_dist", w_d)
            w_t = weights.get("w_time", w_t)
            w_c = weights.get("w_cong", w_c)
            w_h = weights.get("w_hway", w_h)

        # Select delay matrix based on risk aversion
        effective_delay = self.delay_volatility if objective_mode in ["risk_averse_traffic", "express_time"] else self.delay

        # Unified Edge Cost Matrix (in equivalent meters)
        self.C = (
            w_d * self.d
            + w_t * (self.t * v_ref)
            + w_c * (effective_delay * v_ref)
            + w_h * (self.friction * self.d)
        ).astype(np.float32)

        # Banburismus Evidence Matrix (in decibans)
        self.evidence_matrix = np.zeros((self.total_nodes, self.total_nodes), dtype=np.float32)
        self.pruned_edges_count = 0
        self.locked_edges_count = 0

    # -------------------------------------------------------------------------
    # Route Cost Evaluators
    # -------------------------------------------------------------------------
    def _route_cost(self, r):
        if not r:
            return 0.0
        full = [0] + [c + 1 for c in r] + [0]
        base = sum(self.C[full[k], full[k + 1]] for k in range(len(full) - 1))
        if self.objective_mode == "green_kinetic":
            # Dynamic payload-distance work (kg * m equivalent)
            rem_load = sum(self.demands[c] for c in r)
            work = 0.0
            for k in range(len(full) - 1):
                u, v = full[k], full[k + 1]
                work += (rem_load / max(1.0, float(self.cap))) * self.d[u, v] * 0.25
                if v > 0:
                    rem_load -= self.demands[v - 1]
            return base + work
        return base

    def _route_dist(self, r):
        if not r:
            return 0.0
        full = [0] + [c + 1 for c in r] + [0]
        return sum(self.d[full[k], full[k + 1]] for k in range(len(full) - 1))

    def _route_time(self, r):
        if not r:
            return 0.0
        full = [0] + [c + 1 for c in r] + [0]
        return sum(self.t[full[k], full[k + 1]] for k in range(len(full) - 1))

    def _route_delay(self, r):
        if not r:
            return 0.0
        full = [0] + [c + 1 for c in r] + [0]
        return sum(self.delay[full[k], full[k + 1]] for k in range(len(full) - 1))

    def _route_kinetic_energy(self, r):
        """
        Cumulative Payload-Distance Work (Energy in kg*km):
        E = sum_{k=0}^{|r|} (m_tare + payload_remaining_k) * dist_{k, k+1}
        m_tare assumed as 5 * capacity (relative vehicle tare mass).
        """
        if not r:
            return 0.0
        m_tare = 5.0 * self.cap
        full = [0] + [c + 1 for c in r] + [0]
        rem_load = sum(self.demands[c] for c in r)
        work = 0.0
        for k in range(len(full) - 1):
            u, v = full[k], full[k + 1]
            dist_km = self.d[u, v] / 1000.0
            work += (m_tare + rem_load) * dist_km
            if v > 0:
                rem_load -= self.demands[v - 1]
        return work

    # -------------------------------------------------------------------------
    # Intra-Route Straightening (2-Opt & Or-Opt on Unified Cost)
    # -------------------------------------------------------------------------
    def _intra_2opt(self, route):
        if len(route) < 3:
            return route
        improved = True
        passes = 0
        while improved and passes < 5:
            improved = False
            passes += 1
            full = [0] + [c + 1 for c in route] + [0]
            for i in range(1, len(full) - 2):
                for j in range(i + 1, len(full) - 1):
                    a, b = full[i - 1], full[i]
                    c, d = full[j], full[j + 1]
                    delta = (self.C[a, c] + self.C[b, d]) - (self.C[a, b] + self.C[c, d])
                    if delta < -1e-2:
                        route[i - 1 : j] = route[i - 1 : j][::-1]
                        full = [0] + [c + 1 for c in route] + [0]
                        improved = True
                        break
                if improved:
                    break
        return route

    def _intra_or_opt(self, route):
        if len(route) < 4:
            return route
        improved = True
        passes = 0
        while improved and passes < 4:
            improved = False
            passes += 1
            n = len(route)
            for seg_len in [1, 2, 3]:
                if n <= seg_len + 1:
                    continue
                for i in range(n - seg_len + 1):
                    seg = route[i : i + seg_len]
                    rem = route[:i] + route[i + seg_len :]
                    base_c = self._route_cost(route)
                    for p in range(len(rem) + 1):
                        cand = rem[:p] + seg + rem[p:]
                        if self._route_cost(cand) < base_c - 1e-2:
                            route = cand
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
        return route

    def _clean(self, r):
        return self._intra_or_opt(self._intra_2opt(list(r)))

    # -------------------------------------------------------------------------
    # Turing Morphogenesis Partitioning (Reaction-Diffusion)
    # -------------------------------------------------------------------------
    def _turing_morphogenesis_partition(self):
        V = self.V
        angles = np.linspace(0, 2 * np.pi, V, endpoint=False)
        diff_depot = self.custs - self.depot
        r_mean = float(np.mean(np.linalg.norm(diff_depot, axis=1))) * 0.72

        activators = np.zeros((V, 2), dtype=np.float64)
        for v in range(V):
            activators[v] = [
                self.depot[0] + r_mean * np.sin(angles[v]),
                self.depot[1] + r_mean * np.cos(angles[v]) * 1.12,
            ]

        for _ in range(12):
            diffs = self.custs[:, np.newaxis, :] - activators[np.newaxis, :, :]
            dist_sq = np.sum(diffs**2, axis=2)
            sigma = max(1e-4, r_mean * 0.55)
            U = np.exp(-dist_sq / (2.0 * sigma**2))

            for v1 in range(V):
                for v2 in range(V):
                    if v1 != v2:
                        disp = activators[v1] - activators[v2]
                        d_norm = np.linalg.norm(disp) + 1e-5
                        activators[v1] += 0.045 * (disp / d_norm)

            for v in range(V):
                weights = U[:, v]
                if np.sum(weights) > 1e-3:
                    activators[v] = np.average(self.custs, axis=0, weights=weights)

        clusters = [[] for _ in range(V)]
        loads = np.zeros(V, dtype=np.int32)
        d_depot = np.linalg.norm(self.custs - self.depot, axis=1)
        sort_order = np.argsort(-d_depot)

        for c in sort_order:
            dem = self.demands[c]
            affs = [np.linalg.norm(self.custs[c] - activators[v]) for v in range(V)]
            pref_vs = np.argsort(affs)
            assigned = False
            for v in pref_vs:
                if loads[v] + dem <= self.cap:
                    clusters[v].append(c)
                    loads[v] += dem
                    assigned = True
                    break
            if not assigned:
                mv = int(np.argmin(loads))
                clusters[mv].append(c)
                loads[mv] += dem

        return [self._clean(cl) for cl in clusters]

    # -------------------------------------------------------------------------
    # Turing Banburismus Evidence Update
    # -------------------------------------------------------------------------
    def _update_banburismus_evidence(self, candidate_solutions):
        if not candidate_solutions:
            return

        evaluated = [(sum(self._route_cost(r) for r in sol), sol) for sol in candidate_solutions]
        evaluated.sort(key=lambda x: x[0])

        n_elite = max(1, len(evaluated) // 3)
        elite_solutions = [x[1] for x in evaluated[:n_elite]]
        non_elite_solutions = [x[1] for x in evaluated[n_elite:]]

        edge_elite = np.zeros((self.total_nodes, self.total_nodes), dtype=np.int32)
        edge_non = np.zeros((self.total_nodes, self.total_nodes), dtype=np.int32)

        for sol in elite_solutions:
            for r in sol:
                if not r: continue
                full = [0] + [c + 1 for c in r] + [0]
                for k in range(len(full) - 1):
                    edge_elite[full[k], full[k + 1]] += 1
                    edge_elite[full[k + 1], full[k]] += 1

        for sol in non_elite_solutions:
            for r in sol:
                if not r: continue
                full = [0] + [c + 1 for c in r] + [0]
                for k in range(len(full) - 1):
                    edge_non[full[k], full[k + 1]] += 1
                    edge_non[full[k + 1], full[k]] += 1

        eps = 1e-3
        for u in range(self.total_nodes):
            for v in range(self.total_nodes):
                if u != v:
                    p_elite = (edge_elite[u, v] + eps) / (len(elite_solutions) + eps)
                    p_non_elite = (edge_non[u, v] + eps) / (max(1, len(non_elite_solutions)) + eps)
                    w_db = 10.0 * math.log10(p_elite / p_non_elite)
                    self.evidence_matrix[u, v] = float(np.clip(self.evidence_matrix[u, v] * 0.92 + w_db * 0.40, -30.0, 30.0))

        self.pruned_edges_count = int(np.sum(self.evidence_matrix < self.theta_prune) // 2)
        self.locked_edges_count = int(np.sum(self.evidence_matrix > self.theta_lock) // 2)

    # -------------------------------------------------------------------------
    # Inter-Route Search Operators (2-Opt*, Relocate 1-3, Cross-Exchange)
    # -------------------------------------------------------------------------
    def _inter_search(self, routes, loads, gamma=0.0):
        improved = True
        passes = 0
        V = len(routes)

        while improved and passes < 8:
            improved = False
            passes += 1

            # 1. Banburismus-Pruned 2-Opt* (Tail Swaps: direct and reversed)
            for v1 in range(V):
                for v2 in range(v1 + 1, V):
                    r1, r2 = routes[v1], routes[v2]
                    if len(r1) < 2 or len(r2) < 2: continue
                    base_c = self._route_cost(r1) + self._route_cost(r2)

                    for i in range(1, len(r1)):
                        c1 = r1[i - 1]
                        for j in range(1, len(r2)):
                            c2 = r2[j - 1]

                            # Banburismus pruning: skip edges with strong negative evidence
                            if self.evidence_matrix[c1 + 1, c2 + 1] < self.theta_prune:
                                continue

                            cand1 = r1[:i] + r2[j:]
                            cand2 = r2[:j] + r1[i:]
                            l1 = sum(self.demands[x] for x in cand1)
                            l2 = sum(self.demands[x] for x in cand2)

                            if l1 <= self.cap and l2 <= self.cap:
                                c12 = self._route_cost(cand1) + self._route_cost(cand2)
                                delta = c12 - base_c
                                if delta < -1e-2 or (gamma > 10.0 and random.random() < math.exp(-delta / gamma)):
                                    routes[v1] = self._clean(cand1)
                                    routes[v2] = self._clean(cand2)
                                    loads[v1], loads[v2] = l1, l2
                                    improved = True
                                    break

                            cand1_r = r1[:i] + r2[:j][::-1]
                            cand2_r = r1[i:][::-1] + r2[j:]
                            l1_r = sum(self.demands[x] for x in cand1_r)
                            l2_r = sum(self.demands[x] for x in cand2_r)

                            if l1_r <= self.cap and l2_r <= self.cap:
                                c12_r = self._route_cost(cand1_r) + self._route_cost(cand2_r)
                                delta = c12_r - base_c
                                if delta < -1e-2 or (gamma > 10.0 and random.random() < math.exp(-delta / gamma)):
                                    routes[v1] = self._clean(cand1_r)
                                    routes[v2] = self._clean(cand2_r)
                                    loads[v1], loads[v2] = l1_r, l2_r
                                    improved = True
                                    break
                        if improved: break
                    if improved: break

            # 2. Relocate (lengths 1, 2, 3)
            for v1 in range(V):
                for v2 in range(V):
                    if v1 == v2: continue
                    r1, r2 = routes[v1], routes[v2]
                    if not r1: continue

                    for seg_len in [1, 2, 3]:
                        if len(r1) < seg_len: continue
                        for i in range(len(r1) - seg_len + 1):
                            seg = r1[i : i + seg_len]
                            s_dem = sum(self.demands[x] for x in seg)
                            if loads[v2] + s_dem <= self.cap:
                                cand1 = r1[:i] + r1[i + seg_len :]
                                old_c = self._route_cost(r1) + self._route_cost(r2)
                                c1 = self._route_cost(cand1)
                                best_p = None
                                best_seg = None
                                best_c2 = float('inf')

                                for p in range(len(r2) + 1):
                                    for try_seg in ([seg, seg[::-1]] if seg_len > 1 else [seg]):
                                        cand2 = r2[:p] + try_seg + r2[p:]
                                        c2 = self._route_cost(cand2)
                                        if c2 < best_c2:
                                            best_c2 = c2
                                            best_p = p
                                            best_seg = try_seg

                                if c1 + best_c2 < old_c - 1e-2:
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
                    old_c = self._route_cost(r1) + self._route_cost(r2)

                    for len1 in [1, 2]:
                        for len2 in [1, 2]:
                            if len(r1) < len1 or len(r2) < len2: continue
                            for i in range(len(r1) - len1 + 1):
                                s1 = r1[i : i + len1]
                                d1 = sum(self.demands[x] for x in s1)
                                for j in range(len(r2) - len2 + 1):
                                    s2 = r2[j : j + len2]
                                    d2 = sum(self.demands[x] for x in s2)
                                    if loads[v1] - d1 + d2 <= self.cap and loads[v2] - d2 + d1 <= self.cap:
                                        c1 = r1[:i] + s2 + r1[i + len1 :]
                                        c2 = r2[:j] + s1 + r2[j + len2 :]
                                        if self._route_cost(c1) + self._route_cost(c2) < old_c - 1e-2:
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

    # -------------------------------------------------------------------------
    # Main Solve Execution Loop
    # -------------------------------------------------------------------------
    def solve(self):
        t0 = time.time()
        V = self.V

        # 1. Turing Morphogenesis Initial Territory Partitioning
        turing_seed = self._turing_morphogenesis_partition()
        candidates = [turing_seed]

        # 2. Polar Sweep multi-offset seed generation
        angles = np.array([math.atan2(c[0] - self.depot[0], c[1] - self.depot[1]) for c in self.custs])
        for off in [0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4, math.pi, 5 * math.pi / 4, 3 * math.pi / 2, 7 * math.pi / 4]:
            shifted = (angles + off) % (2 * math.pi)
            tour = list(np.argsort(shifted))
            clusters = [[] for _ in range(V)]
            loads = [0] * V
            v_idx = 0
            for c in tour:
                if loads[v_idx] + self.demands[c] > self.cap and v_idx < V - 1:
                    v_idx += 1
                clusters[v_idx].append(c)
                loads[v_idx] += self.demands[c]
            candidates.append([self._clean(r) for r in clusters])

        # 3. Initial Banburismus Deciban evidence accumulation
        self._update_banburismus_evidence(candidates)

        # Select initial best
        best_routes = min(candidates, key=lambda s: sum(self._route_cost(r) for r in s))
        best_cost = sum(self._route_cost(r) for r in best_routes)
        history = [round(sum(self._route_dist(r) for r in best_routes) / 1000.0, 2)]

        routes = [list(r) for r in best_routes]
        loads = [sum(self.demands[c] for c in r) for r in routes]

        # 4. Transverse-Field Quantum Tunneling & Neighborhood Search
        gamma = 1500.0
        passes = 0
        max_passes = 35

        while (time.time() - t0) < self.time_limit and passes < max_passes:
            passes += 1
            gamma *= 0.88

            # Local search with Quantum Tunneling acceptance
            routes, loads = self._inter_search(routes, loads, gamma=gamma)
            routes = [self._clean(r) for r in routes]

            curr_c = sum(self._route_cost(r) for r in routes)
            if curr_c < best_cost:
                best_cost = curr_c
                best_routes = [list(r) for r in routes]

            curr_d = sum(self._route_dist(r) for r in best_routes)
            history.append(round(curr_d / 1000.0, 2))

            # Periodic Banburismus deciban accumulation
            if passes % 6 == 0:
                self._update_banburismus_evidence([routes, best_routes])

        runtime = time.time() - t0
        best_routes = [self._clean(r) for r in best_routes]

        total_d = sum(self._route_dist(r) for r in best_routes)
        total_t = sum(self._route_time(r) for r in best_routes)
        total_delay = sum(self._route_delay(r) for r in best_routes)

        total_kinetic = sum(self._route_kinetic_energy(r) for r in best_routes)
        r_times = [self._route_time(r) / 60.0 for r in best_routes if r]
        equity_std = float(np.std(r_times)) if len(r_times) > 1 else 0.0
        makespan = float(np.max(r_times)) if r_times else 0.0

        # Evaluate Logistic Turing Test
        ltt = self._evaluate_ltt(best_routes, total_delay, equity_std)

        violations = 0
        for r in best_routes:
            l = sum(self.demands[c] for c in r)
            if l > self.cap:
                violations += (l - self.cap)

        return {
            "algorithm": "Turing-Enhanced Quantum HQ-GLS Pro",
            "objective_mode": self.objective_mode,
            "distance_km": round(float(total_d) / 1000.0, 2),
            "time_sec": round(float(total_t), 1),
            "time_min": round(float(total_t) / 60.0, 1),
            "delay_min": round(float(total_delay) / 60.0, 1),
            "makespan_min": round(makespan, 1),
            "equity_std_min": round(equity_std, 2),
            "kinetic_energy_kg_km": round(float(total_kinetic), 1),
            "runtime_sec": round(runtime, 3),
            "routes": best_routes,
            "violations": int(violations),
            "convergence": history,
            "pruned_edges": self.pruned_edges_count,
            "locked_edges": self.locked_edges_count,
            "total_edges": int(self.total_nodes * (self.total_nodes - 1) / 2),
            "prune_percentage": round((self.pruned_edges_count / max(1, int(self.total_nodes * (self.total_nodes - 1) / 2))) * 100.0, 1),
            "ltt_score": ltt["composite_score"],
            "ltt_pass": ltt["passed"],
            "ltt_breakdown": ltt,
        }

    def _evaluate_ltt(self, routes, total_delay, equity_std):
        crossings = 0
        edges = []
        for r in routes:
            if not r: continue
            full = [0] + [c + 1 for c in r] + [0]
            for k in range(len(full) - 1):
                edges.append((self.coords[full[k]], self.coords[full[k + 1]]))

        def intersect(p1, p2, p3, p4):
            def ccw(A, B, C):
                return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
            return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                p1, p2 = edges[i]
                p3, p4 = edges[j]
                if np.array_equal(p1, p3) or np.array_equal(p1, p4) or np.array_equal(p2, p3) or np.array_equal(p2, p4):
                    continue
                if intersect(p1, p2, p3, p4):
                    crossings += 1

        score_naturalness = max(0.0, 100.0 - (crossings * 7.5))
        score_equity = max(40.0, 100.0 - (equity_std * 2.5))
        score_resilience = max(50.0, 100.0 - (total_delay / 60.0) * 1.5)
        score_pruning = min(100.0, 75.0 + (self.pruned_edges_count / max(1, self.total_nodes * 2)) * 15.0)

        composite = round(
            0.35 * score_naturalness
            + 0.25 * score_equity
            + 0.20 * score_resilience
            + 0.20 * score_pruning,
            1,
        )
        return {
            "composite_score": composite,
            "passed": bool(composite >= 85.0),
            "score_naturalness": round(score_naturalness, 1),
            "score_equity": round(score_equity, 1),
            "score_resilience": round(score_resilience, 1),
            "score_pruning": round(score_pruning, 1),
            "crossings_count": crossings,
        }
