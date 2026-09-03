"""
test_constraints.py

Unit tests for VRP constraint validation module.
Includes deterministic tests for:
  1. Duplicate customer
  2. Missing customer
  3. Vehicle overload
  4. Too many vehicles
  5. Excessive route duration
  6. Road capacity violation
  7. Completely valid solution
"""

import unittest
import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.vrp_instance import VRPInstance
from src.route_evaluator import RouteEvaluator
from src.constraints import ConstraintValidator

class TestVRPConstraints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config_path = os.path.join(PROJECT_ROOT, "data", "vrp_config.json")
        cls.graphml_path = os.path.join(PROJECT_ROOT, "data", "raw", "chandigarh_subset.graphml")
        cls.instance = VRPInstance(config_path=cls.config_path, graphml_path=cls.graphml_path)
        cls.evaluator = RouteEvaluator(cls.instance)
        cls.validator = ConstraintValidator(cls.instance)

    def test_completely_valid_solution(self):
        """Test a completely valid solution [3, 1, 5, 2, 4, 8, 6, 7]."""
        # Vehicle 1: [3, 1, 5, 2] -> Demand: 1+2+2+3 = 8 <= 10
        # Vehicle 2: [4, 8, 6, 7] -> Demand: 4+1+3+2 = 10 <= 10
        valid_permutation = [3, 1, 5, 2, 4, 8, 6, 7]
        result = self.evaluator.evaluate(valid_permutation)

        self.assertTrue(result["is_valid"], f"Expected valid solution, but got violations: {result['all_violations']}")
        self.assertEqual(result["total_violations"], 0)
        self.assertTrue(result["uniqueness"]["valid"])
        self.assertTrue(result["capacity"]["valid"])
        self.assertTrue(result["vehicles_count"]["valid"])
        self.assertTrue(result["duration"]["valid"])

    def test_duplicate_customer(self):
        """Test solution containing duplicate customer ID."""
        dup_routes = [[3, 1, 5, 2], [4, 8, 6, 3]] # Customer 3 appears twice, customer 7 missing
        result = self.evaluator.evaluate(dup_routes)

        self.assertFalse(result["is_valid"])
        self.assertFalse(result["uniqueness"]["valid"])
        self.assertIn(3, result["uniqueness"]["details"]["duplicates"])

    def test_missing_customer(self):
        """Test solution with missing customer ID."""
        missing_routes = [[3, 1, 5, 2], [4, 8, 6]] # Customer 7 missing
        result = self.evaluator.evaluate(missing_routes)

        self.assertFalse(result["is_valid"])
        self.assertFalse(result["uniqueness"]["valid"])
        self.assertIn(7, result["uniqueness"]["details"]["missing"])

    def test_vehicle_overload(self):
        """Test vehicle capacity overload constraint."""
        # Vehicle 1: [4, 6, 2, 5] -> Demand: 4 + 3 + 3 + 2 = 12 > capacity 10
        overload_routes = [[4, 6, 2, 5], [1, 3, 7, 8]]
        result = self.evaluator.evaluate(overload_routes)

        self.assertFalse(result["is_valid"])
        self.assertFalse(result["capacity"]["valid"])
        self.assertGreater(result["capacity"]["reports"][0]["load"], self.instance.vehicle_capacity)

    def test_too_many_vehicles(self):
        """Test exceeding maximum number of vehicles constraint."""
        # 3 routes provided when max allowed is 2
        three_routes = [[3, 1], [5, 2, 4], [8, 6, 7]]
        v_valid, v_viols, v_details = self.validator.validate_max_vehicles(three_routes)

        self.assertFalse(v_valid)
        self.assertEqual(v_details["used_vehicles"], 3)
        self.assertEqual(v_details["max_vehicles"], 2)

    def test_excessive_route_duration(self):
        """Test maximum route duration violation."""
        # Temporarily set max_route_duration_sec to 5.0 seconds
        original_duration = self.instance.max_route_duration_sec
        try:
            self.instance.max_route_duration_sec = 5.0
            valid_permutation = [3, 1, 5, 2, 4, 8, 6, 7]
            result = self.evaluator.evaluate(valid_permutation)

            self.assertFalse(result["is_valid"])
            self.assertFalse(result["duration"]["valid"])
        finally:
            self.instance.max_route_duration_sec = original_duration

    def test_road_capacity_violation(self):
        """Test static road capacity violation on a shared road edge."""
        valid_permutation = [3, 1, 5, 2, 4, 8, 6, 7]
        result = self.evaluator.evaluate(valid_permutation)
        
        road_reports = result["road_capacity"]["reports"]
        if not road_reports:
            self.skipTest("No road edges traversed in test solution")

        # Pick an edge used by both routes, or artificially reduce capacity of a traversed edge to 0
        target_edge = list(road_reports.keys())[0]
        u, v, k = target_edge

        # Set road capacity attribute to 0
        orig_cap = self.instance.graph[u][v][k].get("road_capacity", 3)
        try:
            self.instance.graph[u][v][k]["road_capacity"] = 0
            
            # Re-evaluating should trigger road capacity violation
            r_valid, r_viols, r_reports = self.validator.validate_road_capacity(result["routes"])
            self.assertFalse(r_valid)
            self.assertIn(target_edge, r_reports)
            self.assertFalse(r_reports[target_edge]["passed"])
        finally:
            self.instance.graph[u][v][k]["road_capacity"] = orig_cap


if __name__ == "__main__":
    unittest.main()
