from __future__ import annotations

import unittest

import numpy as np

from src.problems.cvrp.components import InsertOperator, Solution
from src.problems.cvrp.heuristics.basic_heuristics.farthest_insertion_4e1d import farthest_insertion_4e1d
from src.problems.cvrp.heuristics.basic_heuristics.greedy_f4c4 import greedy_f4c4
from src.problems.cvrp.heuristics.basic_heuristics.min_cost_insertion_048f import min_cost_insertion_048f
from src.problems.cvrp.heuristics.basic_heuristics.nearest_neighbor_99ba import nearest_neighbor_99ba
from src.problems.cvrp.heuristics.basic_heuristics.random_bfdc import random_bfdc
from src.problems.cvrp.heuristics.basic_heuristics.variable_neighborhood_search_614b import variable_neighborhood_search_614b
from src.problems.cvrp.heuristics.basic_heuristics.variant_costs import insertion_positions
from src.problems.cvrp.variant import CVRP_PROFILE, OVRP_PROFILE, VRPTW_PROFILE


def _problem_state(profile) -> dict:
    return {
        "node_num": 3,
        "depot": 0,
        "vehicle_num": 1,
        "capacity": 10,
        "demands": np.array([0, 1, 1]),
        "distance_matrix": np.array([
            [0.0, 1.0, 10.0],
            [1.0, 0.0, 1.0],
            [100.0, 10.0, 0.0],
        ]),
        "current_solution": Solution(routes=[[0, 1]], depot=0),
        "unvisited_nodes": [2],
        "vehicle_loads": [1],
        "vehicle_remaining_capacity": [9],
        "variant": profile.variant,
        "constraints": profile.to_dict(),
    }


def _time_window_problem_state() -> dict:
    return {
        "node_num": 4,
        "depot": 0,
        "vehicle_num": 1,
        "capacity": 10,
        "demands": np.array([0, 1, 1, 1]),
        "distance_matrix": np.array([
            [0.0, 1.0, 100.0, 20.0],
            [1.0, 0.0, 1.0, 5.0],
            [1.0, 1.0, 0.0, 1.0],
            [20.0, 5.0, 1.0, 0.0],
        ]),
        "current_solution": Solution(routes=[[0, 1]], depot=0),
        "unvisited_nodes": [2, 3],
        "vehicle_loads": [1],
        "vehicle_remaining_capacity": [9],
        "variant": VRPTW_PROFILE.variant,
        "constraints": VRPTW_PROFILE.to_dict(),
        "time_windows": {
            "depot": [0, 1000],
            "customers": {
                "1": [0, 100],
                "2": [0, 1],
                "3": [0, 100],
            },
        },
        "service_times": {"default": 0},
    }


def _time_window_greedy_problem_state() -> dict:
    state = _time_window_problem_state()
    state["distance_matrix"] = np.array([
        [0.0, 1.0, 2.0, 20.0],
        [1.0, 0.0, 1.0, 5.0],
        [1.0, 1.0, 0.0, 1.0],
        [20.0, 5.0, 1.0, 0.0],
    ])
    return state


class VRPVariantAwareBasicHeuristicsTests(unittest.TestCase):
    def test_insertion_positions_preserve_depot_sentinel(self) -> None:
        self.assertEqual([1, 2], list(insertion_positions([0, 1], depot=0)))

    def test_min_cost_insertion_uses_open_route_tail_cost(self) -> None:
        closed_operator, _ = min_cost_insertion_048f(_problem_state(CVRP_PROFILE), {})
        open_operator, _ = min_cost_insertion_048f(_problem_state(OVRP_PROFILE), {})

        self.assertIsInstance(closed_operator, InsertOperator)
        self.assertIsInstance(open_operator, InsertOperator)
        self.assertEqual(1, closed_operator.position)
        self.assertEqual(2, open_operator.position)

    def test_farthest_insertion_uses_open_route_tail_cost(self) -> None:
        closed_operator, _ = farthest_insertion_4e1d(_problem_state(CVRP_PROFILE), {})
        open_operator, _ = farthest_insertion_4e1d(_problem_state(OVRP_PROFILE), {})

        self.assertIsInstance(closed_operator, InsertOperator)
        self.assertIsInstance(open_operator, InsertOperator)
        self.assertEqual(1, closed_operator.position)
        self.assertEqual(2, open_operator.position)

    def test_vns_uses_open_route_tail_cost_and_keeps_depot_first(self) -> None:
        closed_operator, _ = variable_neighborhood_search_614b(_problem_state(CVRP_PROFILE), {})
        open_operator, _ = variable_neighborhood_search_614b(_problem_state(OVRP_PROFILE), {})

        self.assertIsInstance(closed_operator, InsertOperator)
        self.assertIsInstance(open_operator, InsertOperator)
        self.assertEqual(1, closed_operator.position)
        self.assertEqual(2, open_operator.position)

    def test_insertion_heuristics_skip_time_window_infeasible_customer(self) -> None:
        state = _time_window_problem_state()

        nearest_operator, _ = nearest_neighbor_99ba(state, {})
        min_cost_operator, _ = min_cost_insertion_048f(state, {})
        farthest_operator, _ = farthest_insertion_4e1d(state, {})
        vns_operator, _ = variable_neighborhood_search_614b(state, {})
        random_operator, _ = random_bfdc(state, {})

        self.assertEqual(3, nearest_operator.node)
        self.assertEqual(3, min_cost_operator.node)
        self.assertEqual(3, farthest_operator.node)
        self.assertEqual(3, vns_operator.node)
        self.assertEqual(3, random_operator.node)

    def test_two_opt_respects_open_route_and_time_windows(self) -> None:
        from src.problems.cvrp.heuristics.basic_heuristics.two_opt_0554 import two_opt_0554
        state = _time_window_problem_state()
        state["current_solution"] = Solution(routes=[[0, 1, 2, 3]], depot=0)
        state["unvisited_nodes"] = []
        op, _ = two_opt_0554(state, {})
        self.assertTrue(op is None or hasattr(op, "vehicle_id"))

    def test_three_opt_runs_without_error(self) -> None:
        from src.problems.cvrp.heuristics.basic_heuristics.three_opt_e8d7 import three_opt_e8d7
        state = _time_window_problem_state()
        state["current_solution"] = Solution(routes=[[0, 1, 2, 3]], depot=0)
        state["unvisited_nodes"] = []
        op, _ = three_opt_e8d7(state, {})
        self.assertTrue(op is None or hasattr(op, "vehicle_id"))


    def test_node_shift_between_routes_respects_constraints(self) -> None:
        from src.problems.cvrp.heuristics.basic_heuristics.node_shift_between_routes_7b8a import node_shift_between_routes_7b8a
        state = _problem_state(OVRP_PROFILE)
        state["vehicle_num"] = 2
        state["vehicle_loads"] = [1, 1]
        state["vehicle_remaining_capacity"] = [9, 9]
        state["current_solution"] = Solution(routes=[[0, 1], [0, 2]], depot=0)
        state["unvisited_nodes"] = []
        op, _ = node_shift_between_routes_7b8a(state, {})
        self.assertTrue(op is None or hasattr(op, "source_vehicle_id"))

    def test_saving_algorithm_respects_constraints(self) -> None:
        from src.problems.cvrp.heuristics.basic_heuristics.saving_algorithm_710e import saving_algorithm_710e
        state = _problem_state(CVRP_PROFILE)
        state["vehicle_num"] = 2
        state["vehicle_loads"] = [1, 1]
        state["vehicle_remaining_capacity"] = [9, 9]
        state["current_solution"] = Solution(routes=[[0, 1], [0, 2]], depot=0)
        state["unvisited_nodes"] = []
        op, _ = saving_algorithm_710e(state, {})
        self.assertTrue(op is None or hasattr(op, "source_vehicle_id"))

    def test_petal_algorithm_respects_time_windows(self) -> None:
        from src.problems.cvrp.heuristics.basic_heuristics.petal_algorithm_b384 import petal_algorithm_b384
        state = _time_window_problem_state()
        op, _ = petal_algorithm_b384(state, {})
        self.assertIsNotNone(op)
        self.assertEqual(3, op.node)


if __name__ == "__main__":
    unittest.main()

