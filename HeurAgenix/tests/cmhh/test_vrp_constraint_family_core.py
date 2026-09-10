from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cmhh.data.cvrp_generator import write_cvrplib
from src.problems.cvrp.components import Solution
from src.problems.cvrp.constraints import validate_solution
from src.problems.cvrp.env import Env
from src.problems.cvrp.route_metrics import compute_route_metrics, total_solution_distance
from src.problems.cvrp.variant import (
    CVRP_PROFILE,
    OVRP_PROFILE,
    OVRPTW_PROFILE,
    VRPTW_PROFILE,
    constraint_vector,
    diff_constraint_profiles,
    hamming_distance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def tiny_instance(profile=CVRP_PROFILE) -> dict:
    return {
        "node_num": 3,
        "depot": 0,
        "vehicle_num": 1,
        "capacity": 10,
        "demands": np.array([0, 4, 5]),
        "distance_matrix": np.array([
            [0.0, 3.0, 10.0],
            [3.0, 0.0, 4.0],
            [10.0, 4.0, 0.0],
        ]),
        "constraint_profile": profile,
        "constraints": profile.to_dict(),
        "variant": profile.variant,
        "time_windows": {
            "depot": [0, 1000],
            "customers": {
                "1": [10, 20],
                "2": [14, 30],
            },
        },
        "service_times": {"default": 0},
    }


class VRPConstraintFamilyCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = Path.cwd()
        os.chdir(REPO_ROOT)

    def tearDown(self) -> None:
        os.chdir(self._cwd)

    def test_closed_and_open_route_costs_share_same_route_representation(self) -> None:
        solution = Solution(routes=[[0, 1, 2]], depot=0)

        self.assertEqual(17.0, total_solution_distance(solution, tiny_instance(CVRP_PROFILE), CVRP_PROFILE))
        self.assertEqual(7.0, total_solution_distance(solution, tiny_instance(OVRP_PROFILE), OVRP_PROFILE))

    def test_capacity_constraint_remains_active_for_all_v1_variants(self) -> None:
        for profile in [CVRP_PROFILE, OVRP_PROFILE, OVRPTW_PROFILE, VRPTW_PROFILE]:
            instance = tiny_instance(profile)
            instance["capacity"] = 8
            solution = Solution(routes=[[0, 1, 2]], depot=0)

            results = validate_solution(solution, instance, profile)
            capacity = next(result for result in results if result.name == "capacity")
            self.assertFalse(capacity.feasible, profile.variant)

    def test_time_windows_allow_waiting_for_early_arrival(self) -> None:
        instance = tiny_instance(VRPTW_PROFILE)
        solution = Solution(routes=[[0, 1, 2]], depot=0)

        metrics = compute_route_metrics(solution.routes[0], 0, instance, VRPTW_PROFILE)

        self.assertEqual([3.0, 14.0, 24.0], metrics.arrival_times)
        self.assertEqual([10.0, 14.0, 24.0], metrics.service_start_times)
        self.assertEqual(7.0, metrics.waiting_time)
        self.assertTrue(metrics.time_window_feasible)

    def test_time_windows_mark_late_service_invalid(self) -> None:
        instance = tiny_instance(VRPTW_PROFILE)
        instance["time_windows"]["customers"]["2"] = [0, 13]
        solution = Solution(routes=[[0, 1, 2]], depot=0)

        results = validate_solution(solution, instance, VRPTW_PROFILE)
        tw = next(result for result in results if result.name == "time_windows")

        self.assertFalse(tw.feasible)

    def test_env_default_preserves_legacy_closed_cvrp_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            coords = [(0, 0), (3, 0), (3, 4)]
            demands = [0, 4, 5]
            instance_path = write_cvrplib(root / "tiny.vrp", "tiny", coords, demands, capacity=10, vehicle_num=1)

            env = Env(str(instance_path))
            env.current_solution = Solution(routes=[[0, 1, 2]], depot=0)

            self.assertEqual("cvrp", env.constraint_profile.variant)
            self.assertAlmostEqual(12.0, env.key_value)
            self.assertTrue(env.validation_solution())

    def test_env_can_select_open_route_from_meta_without_changing_problem_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            coords = [(0, 0), (3, 0), (3, 4)]
            demands = [0, 4, 5]
            instance_path = write_cvrplib(root / "tiny.vrp", "tiny", coords, demands, capacity=10, vehicle_num=1)
            meta_path = instance_path.with_suffix(".meta.json")
            meta_path.write_text(
                json.dumps({"variant": "ovrp", "constraints": OVRP_PROFILE.to_dict()}),
                encoding="utf-8",
            )

            env = Env(str(instance_path))
            env.current_solution = Solution(routes=[[0, 1, 2]], depot=0)

            self.assertEqual("ovrp", env.constraint_profile.variant)
            self.assertAlmostEqual(7.0, env.key_value)
            self.assertTrue(env.validation_solution())

    def test_constraint_delta_and_graycode_helpers(self) -> None:
        delta = diff_constraint_profiles(CVRP_PROFILE, OVRP_PROFILE)

        self.assertEqual(("open_route",), delta.added)
        self.assertEqual(1, hamming_distance(constraint_vector(CVRP_PROFILE), constraint_vector(OVRP_PROFILE)))
        self.assertEqual(1, hamming_distance(constraint_vector(OVRP_PROFILE), constraint_vector(OVRPTW_PROFILE)))
        self.assertEqual(1, hamming_distance(constraint_vector(OVRPTW_PROFILE), constraint_vector(VRPTW_PROFILE)))


if __name__ == "__main__":
    unittest.main()
