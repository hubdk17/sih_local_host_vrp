"""
mdvrp_route_splitter.py

Route splitting for Multi-Depot VRP.
Converts a flat customer permutation into per-vehicle routes,
where each vehicle starts/ends at its home depot.
"""

from typing import List, Tuple


def split_mdvrp_permutation(
    permutation: List[int],
    num_vehicles: int,
) -> List[List[int]]:
    """
    Split a flat customer permutation into num_vehicles route segments.
    Each segment is a list of customer IDs assigned to that vehicle.

    The split is even (with remainder distributed to first vehicles),
    identical to the existing single-depot splitter.

    Returns:
        List of routes, one per vehicle (indexed by vehicle order 0..num_vehicles-1).
    """
    if not permutation:
        return [[] for _ in range(num_vehicles)]

    n = len(permutation)
    if num_vehicles <= 1:
        return [list(permutation)]

    k, m = divmod(n, num_vehicles)
    routes = []
    start = 0
    for i in range(num_vehicles):
        end = start + k + (1 if i < m else 0)
        routes.append(list(permutation[start:end]))
        start = end

    return routes


def parse_mdvrp_solution(
    solution,
    num_vehicles: int,
) -> List[List[int]]:
    """
    Parse a candidate MDVRP solution.
    Accepts either:
      - A flat permutation [c1, c2, ..., cN]
      - A list of per-vehicle routes [[c1, c2], [c3, c4], ...]
    """
    if not solution:
        return [[] for _ in range(num_vehicles)]

    if isinstance(solution[0], list):
        return [list(r) for r in solution]
    elif isinstance(solution[0], int):
        return split_mdvrp_permutation(solution, num_vehicles)
    else:
        raise ValueError(f"Invalid MDVRP solution format: {solution}")
