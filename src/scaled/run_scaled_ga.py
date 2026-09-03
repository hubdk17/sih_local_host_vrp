"""
run_scaled_ga.py

Main runner for the scaled 20-sector Multi-Depot VRP GA experiment.

Usage:
    python src/scaled/run_scaled_ga.py --seed 1 --pop_size 100 --generations 200
"""

import argparse
import csv
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.scaled.mdvrp_instance import MDVRPInstance
from src.scaled.mdvrp_route_evaluator import MDVRPRouteEvaluator
from src.scaled.mdvrp_ga_optimizer import MDVRPGeneticAlgorithm
from src.scaled.mdvrp_visualizer import plot_convergence, plot_routes, plot_customer_depot_distribution

CONFIG_PATH = os.path.join(BASE_DIR, "data", "scaled", "mdvrp_config.json")
GRAPHML_PATH = os.path.join(BASE_DIR, "data", "scaled", "chandigarh_20_sectors.graphml")


def parse_args():
    parser = argparse.ArgumentParser(description="Scaled MDVRP GA Experiment")
    parser.add_argument("--seed", type=int, default=1, help="Random seed (default: 1)")
    parser.add_argument("--pop_size", type=int, default=100, help="Population size (default: 100)")
    parser.add_argument("--generations", type=int, default=200, help="Number of generations (default: 200)")
    parser.add_argument("--penalty", type=float, default=5000.0, help="Penalty per violation (default: 5000)")
    return parser.parse_args()


def main():
    args = parse_args()

    output_dir = os.path.join(
        BASE_DIR, "outputs", "ga", "scale_20_sectors", f"seed_{args.seed}"
    )
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  SCALED MDVRP GA EXPERIMENT — 20 SECTORS")
    print("=" * 60)
    print(f"  Seed          : {args.seed}")
    print(f"  Pop Size      : {args.pop_size}")
    print(f"  Generations   : {args.generations}")
    print(f"  Penalty       : {args.penalty}")
    print(f"  Output Dir    : {output_dir}")
    print("=" * 60 + "\n")

    # 1. Load MDVRP Instance
    print("[1/5] Loading MDVRP instance...")
    t0 = time.time()
    instance = MDVRPInstance(config_path=CONFIG_PATH, graphml_path=GRAPHML_PATH)
    load_time = time.time() - t0
    print(f"  Loaded in {load_time:.1f}s")
    print(f"  Graph : {len(instance.graph.nodes)} nodes, {len(instance.graph.edges)} edges")
    print(f"  Sectors: {len(instance.sectors_used)}")
    print(f"  Depots : {instance.num_depots}")
    print(f"  Customers: {instance.num_customers}")
    print(f"  Vehicles: {instance.num_vehicles}")
    print(f"  Total demand: {sum(instance.demands.values())}")
    total_cap = sum(v["capacity"] for v in instance.vehicles_list)
    print(f"  Total capacity: {total_cap}")
    print()

    # 2. Plot customer/depot distribution
    print("[2/5] Generating distribution plot...")
    dist_path = os.path.join(output_dir, "distribution.png")
    plot_customer_depot_distribution(instance, dist_path)

    # 3. Run GA
    print("[3/5] Running GA optimization...")
    evaluator = MDVRPRouteEvaluator(instance)

    ga = MDVRPGeneticAlgorithm(
        instance=instance,
        pop_size=args.pop_size,
        generations=args.generations,
        penalty_per_violation=args.penalty,
        random_seed=args.seed,
    )

    t_start = time.time()
    results = ga.optimize()
    runtime = time.time() - t_start

    best_eval = results["best_evaluation"]
    history = results["history"]

    # 4. Print Results
    print("=" * 60)
    print("  MDVRP GA OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"  Runtime             : {runtime:.2f} s")
    print(f"  Best Travel Time    : {best_eval['total_travel_time']:.2f} s")
    print(f"  Best Distance       : {best_eval['total_distance']:.2f} m")
    print(f"  Violations          : {best_eval['total_violations']}")
    print(f"  Valid               : {'YES' if best_eval['is_valid'] else 'NO'}")
    print("=" * 60 + "\n")

    report = evaluator.format_constraint_report(best_eval)
    print(report)

    # 5. Save outputs
    print("\n[4/5] Saving outputs...")

    # 5a. CSV history
    csv_path = os.path.join(output_dir, "history.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(history.keys())
        for row in zip(*history.values()):
            writer.writerow(row)
    print(f"  History CSV: {csv_path}")

    # 5b. Convergence plot
    conv_path = os.path.join(output_dir, "convergence.png")
    plot_convergence(history, conv_path)

    # 5c. Route map
    route_path = os.path.join(output_dir, "best_route.png")
    plot_routes(instance, best_eval, route_path)

    # 5d. Result JSON
    # Determine convergence generation (first gen where best_violations == final best_violations)
    final_viols = history["best_violations"][-1]
    convergence_gen = args.generations
    for i, v in enumerate(history["best_violations"]):
        if v == final_viols:
            convergence_gen = history["generation"][i]
            break

    result_json = {
        "experiment": "scaled_20_sector_mdvrp_ga",
        "seed": args.seed,
        "num_sectors": len(instance.sectors_used),
        "sectors": instance.sectors_used,
        "num_graph_nodes": len(instance.graph.nodes),
        "num_graph_edges": len(instance.graph.edges),
        "num_customers": instance.num_customers,
        "num_depots": instance.num_depots,
        "num_vehicles": instance.num_vehicles,
        "vehicle_capacities": [instance.get_vehicle_capacity(v) for v in range(instance.num_vehicles)],
        "max_route_duration_sec": instance.max_route_duration_sec,
        "total_demand": sum(instance.demands.values()),
        "total_capacity": total_cap,
        "ga_parameters": {
            "pop_size": args.pop_size,
            "generations": args.generations,
            "crossover_prob": 0.85,
            "mutation_prob": 0.25,
            "tournament_size": 3,
            "elitism_count": 2,
            "penalty_per_violation": args.penalty,
        },
        "results": {
            "runtime_seconds": round(runtime, 2),
            "best_travel_time_s": round(best_eval["total_travel_time"], 2),
            "best_distance_m": round(best_eval["total_distance"], 2),
            "total_violations": best_eval["total_violations"],
            "is_valid": best_eval["is_valid"],
            "convergence_generation": convergence_gen,
            "initial_unique_permutations": history["unique_permutations"][0] if history["unique_permutations"] else 0,
            "final_unique_permutations": history["unique_permutations"][-1] if history["unique_permutations"] else 0,
            "initial_diversity": round(history["population_diversity"][0], 2) if history["population_diversity"] else 0,
            "final_diversity": round(history["population_diversity"][-1], 2) if history["population_diversity"] else 0,
        },
        "best_permutation": results["best_individual"],
    }

    json_path = os.path.join(output_dir, "result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2, ensure_ascii=False)
    print(f"  Result JSON: {json_path}")

    print("\n[5/5] Experiment complete.")
    print(f"\n  All outputs in: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
