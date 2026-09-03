"""
route_splitter.py

Decoupled route splitting logic for converting a customer permutation
into vehicle routes.
"""

from typing import List, Union

def split_permutation(permutation: List[int], num_vehicles: int = 2) -> List[List[int]]:
    """
    Split a customer permutation into a list of vehicle routes.
    
    Example:
      permutation: [3, 1, 5, 2, 4, 8, 6, 7]
      num_vehicles: 2
      Output: [[3, 1, 5, 2], [4, 8, 6, 7]]
    """
    if not permutation:
        return [[] for _ in range(num_vehicles)]

    n = len(permutation)
    if num_vehicles <= 1:
        return [list(permutation)]

    # Calculate sublist size
    k, m = divmod(n, num_vehicles)
    routes = []
    start = 0

    for i in range(num_vehicles):
        # Distribute remainder elements among first m routes
        end = start + k + (1 if i < m else 0)
        routes.append(list(permutation[start:end]))
        start = end

    return routes

def parse_solution(solution: Union[List[int], List[List[int]]], num_vehicles: int = 2) -> List[List[int]]:
    """
    Parse a candidate solution into a list of vehicle routes.
    Accepts either a flat permutation [3, 1, 5, 2, 4, 8, 6, 7] or explicit routes [[3, 1, 5, 2], [4, 8, 6, 7]].
    """
    if not solution:
        return [[] for _ in range(num_vehicles)]

    if isinstance(solution[0], list):
        return [list(r) for r in solution]
    elif isinstance(solution[0], int):
        return split_permutation(solution, num_vehicles)
    else:
        raise ValueError(f"Invalid solution format: {solution}")
