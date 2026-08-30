from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cmhh.evaluation.evaluator import Evaluator
from cmhh.evaluation.problem_adapter import ProblemAdapter, ProblemRegistry
from cmhh.metrics.objective import relative_gap
from cmhh.models import EvaluationBudget, HeuristicArtifact
from cmhh.tasks import TaskMetric, TaskReference, TaskSpec, TaskSplits


class MultiProblemEvaluatorTests(unittest.TestCase):
    def test_problem_registry_resolves_all_problems(self) -> None:
        self.assertIn("tsp", ProblemRegistry.registered_problems())
        self.assertIn("cvrp", ProblemRegistry.registered_problems())
        self.assertIn("jssp", ProblemRegistry.registered_problems())

        tsp_adapter = ProblemRegistry.get("tsp")
        self.assertEqual((".tsp",), tsp_adapter.instance_extensions)
        self.assertEqual("minimize", tsp_adapter.objective_sense)

        cvrp_adapter = ProblemRegistry.get("cvrp")
        self.assertEqual((".vrp",), cvrp_adapter.instance_extensions)
        self.assertEqual("minimize", cvrp_adapter.objective_sense)

        jssp_adapter = ProblemRegistry.get("jssp")
        self.assertEqual((".txt",), jssp_adapter.instance_extensions)
        self.assertEqual("minimize", jssp_adapter.objective_sense)

    def test_instance_discovery_by_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "inst1.tsp").write_text("dummy", encoding="utf-8")
            (root / "inst2.vrp").write_text("dummy", encoding="utf-8")
            (root / "inst3.txt").write_text("dummy", encoding="utf-8")
            (root / "other.dat").write_text("dummy", encoding="utf-8")

            tsp_files = ProblemRegistry.get("tsp").discover_instances(root)
            self.assertEqual(["inst1.tsp"], [p.name for p in tsp_files])

            cvrp_files = ProblemRegistry.get("cvrp").discover_instances(root)
            self.assertEqual(["inst2.vrp"], [p.name for p in cvrp_files])

            jssp_files = ProblemRegistry.get("jssp").discover_instances(root)
            self.assertEqual(["inst3.txt"], [p.name for p in jssp_files])

    def test_relative_gap_senses(self) -> None:
        # Minimization: candidate=120, ref=100 -> gap = 0.20
        gap_min = relative_gap(120.0, 100.0, objective="minimize")
        self.assertAlmostEqual(0.20, gap_min)

        # Maximization: candidate=80, ref=100 -> gap = 0.20 (worse by 20%)
        gap_max = relative_gap(80.0, 100.0, objective="maximize")
        self.assertAlmostEqual(0.20, gap_max)

        # Maximization: candidate=120, ref=100 -> gap = -0.20 (better by 20%)
        gap_better_max = relative_gap(120.0, 100.0, objective="maximize")
        self.assertAlmostEqual(-0.20, gap_better_max)

    def test_cvrp_environment_loading_and_evaluation(self) -> None:
        from cmhh.data.cvrp_generator import generate_cvrp_instance, write_cvrplib
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            split_dir = root / "validation"
            split_dir.mkdir(parents=True)
            coords, demands, capacity, vehicle_num = generate_cvrp_instance(
                node_count=10,
                seed=42,
                coordinate_min=0,
                coordinate_max=1000,
            )
            inst_path = write_cvrplib(split_dir / "cvrp_test.vrp", "cvrp_test", coords, demands, capacity, vehicle_num)

            heuristic_path = repo_root / "src/problems/cvrp/heuristics/basic_heuristics/nearest_neighbor_99ba.py"
            if not heuristic_path.exists():
                self.skipTest("CVRP nearest_neighbor heuristic not found")

            task = TaskSpec(
                task_id="cvrp_test_task",
                problem="cvrp",
                size_tier="n10",
                distribution="euclidean_uniform",
                splits=TaskSplits(split_dir, split_dir, split_dir, split_dir),
                reference=TaskReference("pending"),
                metric=TaskMetric("relative_gap", "minimize"),
                implemented_in_heuragenix=True,
            )
            artifact = HeuristicArtifact(
                heuristic_id="nearest_neighbor_99ba",
                problem="cvrp",
                code_path=heuristic_path,
                code_hash="dummy",
                task_id=task.task_id,
            )


            evaluator = Evaluator(
                repo_root=repo_root,
                budget=EvaluationBudget(instance_timeout_seconds=15, batch_timeout_seconds=60),
            )
            result = evaluator.evaluate(artifact, task, "validation")
            self.assertEqual(1, len(result.instances))
            self.assertEqual("ok", result.instances[0].status)
            self.assertIsNotNone(result.instances[0].objective)
            self.assertGreater(result.instances[0].objective, 0)

    def test_jssp_environment_loading_and_evaluation(self) -> None:
        from cmhh.data.jssp_generator import generate_jssp_instance, write_jssp
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            split_dir = root / "validation"
            split_dir.mkdir(parents=True)
            seq, times = generate_jssp_instance(job_count=5, machine_count=3, seed=42)
            write_jssp(split_dir / "jssp_test.txt", seq, times)

            heuristic_path = repo_root / "src/problems/jssp/heuristics/basic_heuristics/shortest_processing_time_first_c374.py"
            if not heuristic_path.exists():
                self.skipTest("JSSP SPT heuristic not found")

            task = TaskSpec(
                task_id="jssp_test_task",
                problem="jssp",
                size_tier="j5_m3",
                distribution="uniform_processing_times",
                splits=TaskSplits(split_dir, split_dir, split_dir, split_dir),
                reference=TaskReference("pending"),
                metric=TaskMetric("relative_gap", "minimize"),
                implemented_in_heuragenix=True,
            )
            artifact = HeuristicArtifact(
                heuristic_id="shortest_processing_time_first_c374",
                problem="jssp",
                code_path=heuristic_path,
                code_hash="dummy",
                task_id=task.task_id,
            )

            evaluator = Evaluator(
                repo_root=repo_root,
                budget=EvaluationBudget(instance_timeout_seconds=15, batch_timeout_seconds=60),
            )

            result = evaluator.evaluate(artifact, task, "validation")
            self.assertEqual(1, len(result.instances))
            self.assertEqual("ok", result.instances[0].status)
            self.assertIsNotNone(result.instances[0].objective)
            self.assertGreater(result.instances[0].objective, 0)


if __name__ == "__main__":
    unittest.main()
