from __future__ import annotations

import unittest
from pathlib import Path

from cmhh.config import load_stream_config, load_suite_config
from cmhh.pilot_validator import validate_pilot_suite_structure
from cmhh.runtime import resolve_stream_path, resolve_suite_path
from cmhh.tasks import load_task_registry


class TestPilot4Streams(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path.cwd()
        if not (self.repo_root / "cmhh" / "configs").exists() and (self.repo_root / "HeurAgenix" / "cmhh" / "configs").exists():
            self.repo_root = self.repo_root / "HeurAgenix"

    def test_pilot_suite_config(self) -> None:
        """Verify pilot_4streams.yaml suite definition contains all 4 streams, 5 conditions, and 3 seeds."""
        suite_path = resolve_suite_path("pilot_4streams", self.repo_root)
        self.assertTrue(suite_path.exists(), f"Suite config not found: {suite_path}")

        suite = load_suite_config(suite_path)
        self.assertEqual(suite.suite_id, "pilot_4streams")
        self.assertEqual(
            list(suite.streams),
            [
                "s1_tsp_scale",
                "s2_cvrp_constraint",
                "s3_related_cross_problem",
                "s4_unrelated_cross_problem",
            ],
        )
        self.assertEqual(
            list(suite.conditions),
            ["isolated", "population", "naive-bounded", "naive-unbounded", "managed"],
        )
        self.assertEqual(suite.seeds, (1, 2, 3))

    def test_pilot_stream_definitions(self) -> None:
        """Verify the 4 active pilot streams resolve properly and have valid task sequences."""
        registry = load_task_registry(repo_root=self.repo_root)

        # S1: TSP Scale
        s1_path = resolve_stream_path("s1_tsp_scale", self.repo_root)
        self.assertTrue(s1_path.exists())
        s1 = load_stream_config(s1_path)
        self.assertEqual(list(s1.task_ids), ["tsp_uniform_n20", "tsp_uniform_n50", "tsp_uniform_n100"])
        for tid in s1.task_ids:
            self.assertIn(tid, registry)

        # S2: CVRP Constraint
        s2_path = resolve_stream_path("s2_cvrp_constraint", self.repo_root)
        self.assertTrue(s2_path.exists())
        s2 = load_stream_config(s2_path)
        self.assertEqual(
            list(s2.task_ids),
            ["cvrp_uniform_n50_loose", "cvrp_uniform_n50_medium", "cvrp_uniform_n50_tight"],
        )
        for tid in s2.task_ids:
            self.assertIn(tid, registry)

        # S3: Related Cross-Problem
        s3_path = resolve_stream_path("s3_related_cross_problem", self.repo_root)
        self.assertTrue(s3_path.exists())
        s3 = load_stream_config(s3_path)
        self.assertEqual(
            list(s3.task_ids),
            ["tsp_uniform_n50_a", "cvrp_uniform_n50_medium", "tsp_uniform_n50_b"],
        )
        for tid in s3.task_ids:
            self.assertIn(tid, registry)

        # S4: Unrelated Cross-Problem
        s4_path = resolve_stream_path("s4_unrelated_cross_problem", self.repo_root)
        self.assertTrue(s4_path.exists())
        s4 = load_stream_config(s4_path)
        self.assertEqual(
            list(s4.task_ids),
            ["tsp_uniform_n50_a", "jssp_j10_m5", "tsp_uniform_n50_b"],
        )
        for tid in s4.task_ids:
            self.assertIn(tid, registry)

    def test_anchor_parity_and_separation(self) -> None:
        """S3 and S4 must share identical TSP-A (Task 1) and TSP-B (Task 3), while A != B."""
        registry = load_task_registry(repo_root=self.repo_root)
        task_a = registry.get("tsp_uniform_n50_a")
        task_b = registry.get("tsp_uniform_n50_b")

        self.assertIsNotNone(task_a)
        self.assertIsNotNone(task_b)
        self.assertNotEqual(task_a.task_id, task_b.task_id)

        seed_a = task_a.metadata.get("dataset_seed")
        seed_b = task_b.metadata.get("dataset_seed")
        self.assertIsNotNone(seed_a)
        self.assertIsNotNone(seed_b)
        self.assertNotEqual(seed_a, seed_b)

    def test_pilot_suite_preflight_validator(self) -> None:
        """Pre-flight validator passes with zero errors."""
        report = validate_pilot_suite_structure(self.repo_root, "pilot_4streams")
        self.assertTrue(report.is_valid, f"Validation failed: {report.summary_lines}")


if __name__ == "__main__":
    unittest.main()
