from __future__ import annotations

import tempfile
import unittest
import hashlib
import sys
import json
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.data.tsp_io import load_euc2d_graph, read_euc2d_coordinates
from cmhh.data.tsp_generator import generate_tsp_instance, write_tsplib
from cmhh.metrics.continual import average_final_performance, backward_transfer, forward_transfer
from cmhh.metrics.objective import relative_gap, score_from_gap
from cmhh.evaluation.evaluator import Evaluator
from cmhh.models import EvaluationBudget, HeuristicArtifact
from cmhh.models import EvaluationResult, InstanceEvaluation, SearchBudget
from cmhh.tasks import TaskMetric, TaskReference, TaskSpec, TaskSplits
from cmhh.tasks import TaskRegistry
from cmhh.config import DataConfig, ExperimentConfig, StreamConfig
from cmhh.runner import StreamRunner
from cmhh.references.concorde import ConcordeConfig, SolverFailure, solve_instance
from cmhh.references.tour import parse_concorde_tour, tour_objective
from cmhh.audit import audit_run
from cmhh.llm.budgeted_client import BudgetedLLMClient, LLMBudgetExceeded
from cmhh.llm.config import llm_config_fingerprint, sanitized_llm_config


class TspGeneratorTests(unittest.TestCase):
    def test_generation_is_deterministic_and_unique(self) -> None:
        first = generate_tsp_instance(20, 42, 0, 10000)
        second = generate_tsp_instance(20, 42, 0, 10000)
        self.assertEqual(first, second)
        self.assertEqual(20, len(set(first)))

    def test_generated_file_loads_with_tsplib(self) -> None:
        coordinates = generate_tsp_instance(20, 42, 0, 10000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.tsp"
            write_tsplib(path, "sample", coordinates)
            self.assertEqual(20, len(read_euc2d_coordinates(path)))
            self.assertEqual(20, len(load_euc2d_graph(path)))
            self.assertEqual(sha256_file(path), sha256_file(path))


class MetricTests(unittest.TestCase):
    def test_relative_gap_and_score(self) -> None:
        self.assertAlmostEqual(0.1, relative_gap(110.0, 100.0))
        self.assertAlmostEqual(-0.1, score_from_gap(0.1))

    def test_continual_metrics(self) -> None:
        matrix = {
            0: {0: 0.8},
            1: {0: 0.7, 1: 0.6},
            2: {0: 0.6, 1: 0.5, 2: 0.9},
        }
        self.assertAlmostEqual(2.0 / 3.0, average_final_performance(matrix, 3))
        self.assertAlmostEqual(-0.15, backward_transfer(matrix, 3))
        self.assertAlmostEqual(0.05, forward_transfer(matrix, {1: 0.5, 2: 0.9}, 3))


class EvaluatorTests(unittest.TestCase):
    def test_infinite_heuristic_is_terminated(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        heuristic_path = Path(__file__).parent / "fixtures" / "infinite_loop.py"
        with tempfile.TemporaryDirectory() as directory:
            split = Path(directory) / "smoke"
            instance = split / "timeout_case.tsp"
            write_tsplib(instance, "timeout_case", generate_tsp_instance(20, 7, 0, 10000))
            task = TaskSpec(
                task_id="tsp_timeout_test",
                problem="tsp",
                size_tier="n20",
                distribution="euclidean_uniform",
                splits=TaskSplits(split, split, split, split),
                reference=TaskReference("best_known"),
                metric=TaskMetric("relative_gap", "minimize"),
                implemented_in_heuragenix=True,
            )
            artifact = HeuristicArtifact(
                "infinite_loop", "tsp", heuristic_path,
                hashlib.sha256(heuristic_path.read_bytes()).hexdigest(),
            )
            evaluator = Evaluator(
                repo_root,
                EvaluationBudget(instance_timeout_seconds=0.5, batch_timeout_seconds=2),
            )
            result = evaluator.evaluate(artifact, task, "smoke")
            self.assertEqual("timeout", result.instances[0].status)
            self.assertEqual(1.0, result.failure_rate)


class ConcordeAdapterTests(unittest.TestCase):
    def test_solver_output_is_parsed_and_recomputed(self) -> None:
        fake_solver = Path(__file__).parent / "fixtures" / "fake_concorde.py"
        config = ConcordeConfig(
            command_prefix=(sys.executable, str(fake_solver)),
            arguments=("-x", "-o", "{tour_path}", "{instance_path}"),
            max_workers=1,
            timeouts={"n20": 5.0},
        )
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "sample.tsp"
            tour_path = Path(directory) / "sample.tour"
            write_tsplib(instance, "sample", generate_tsp_instance(20, 13, 0, 10000))
            result = solve_instance(instance, "n20", config, tour_path)
            self.assertNotIsInstance(result, SolverFailure)
            self.assertEqual("optimal", result.status)
            tour = parse_concorde_tour(tour_path, 20)
            self.assertEqual(result.objective, tour_objective(instance, tour))


class LLMInfrastructureTests(unittest.TestCase):
    def test_secret_is_redacted_and_does_not_affect_fingerprint(self) -> None:
        first = {"type": "api_model", "model": "x", "api_key": "secret-a"}
        second = {"type": "api_model", "model": "x", "api_key": "secret-b"}
        self.assertEqual("<redacted>", sanitized_llm_config(first)["api_key"])
        self.assertEqual(llm_config_fingerprint(first), llm_config_fingerprint(second))

    def test_provider_retries_consume_hard_budget(self) -> None:
        class FailingDelegate:
            max_attempts = 10
            sleep_time = 0
            messages = []

            def chat_once(self):
                raise RuntimeError("provider failure")

            def indirect_chat(self):
                return self.chat()

        client = BudgetedLLMClient(FailingDelegate(), max_calls=2)
        with self.assertRaises(LLMBudgetExceeded):
            client.delegate.indirect_chat()
        self.assertEqual(2, client.calls_used)


class AuditTests(unittest.TestCase):
    def test_valid_minimal_run_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = root / "candidate.py"
            code.write_text("def candidate():\n    return None\n", encoding="utf-8")
            digest = hashlib.sha256(code.read_bytes()).hexdigest()
            (root / "checkpoints").mkdir()
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            (root / "checkpoints/latest.json").write_text(json.dumps({
                "selected": {"tsp": {"code_path": str(code), "code_hash": digest}}
            }), encoding="utf-8")
            (root / "events.jsonl").write_text(
                json.dumps({"event": "candidate_selected", "task_id": "tsp"}) + "\n" +
                json.dumps({"event": "test_evaluation_started", "task_id": "tsp"}) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(audit_run(root).valid)


class RunnerResumeTests(unittest.TestCase):
    def test_resume_skips_completed_task(self) -> None:
        class FakeEvaluator:
            def __init__(self, repo_root):
                self.repo_root = Path(repo_root)

            def evaluate(self, artifact, task, split):
                return EvaluationResult(artifact.heuristic_id, task.task_id, split, (
                    InstanceEvaluation(
                        "instance", "ok", 110.0, 100.0, "optimal", 0.1, 0.01
                    ),
                ))

        class RecordingGenerator:
            def __init__(self, fail_on=None):
                self.calls = []
                self.fail_on = fail_on

            def generate(self, task, seed_population, budget, seed):
                self.calls.append(task.task_id)
                if task.task_id == self.fail_on:
                    raise RuntimeError("intentional interruption")
                return seed_population

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heuristic_dir = root / "src/problems/tsp/heuristics/basic_heuristics"
            heuristic_dir.mkdir(parents=True)
            heuristic = heuristic_dir / "seed.py"
            heuristic.write_text("def seed():\n    return None\n", encoding="utf-8")
            split = root / "split"
            split.mkdir()
            tasks = []
            for task_id in ("tsp_a", "tsp_b"):
                tasks.append(TaskSpec(
                    task_id, "tsp", "n20", "uniform",
                    TaskSplits(split, split, split, split),
                    TaskReference("optimal"), TaskMetric("relative_gap", "minimize"), True,
                    {"heuristic_dir": "basic_heuristics", "seed_heuristics": ["seed"]},
                    {"nodes": 20},
                ))
            experiment = ExperimentConfig(
                "test", root / "results", (1,), DataConfig(42, 0, 10000, {
                    "train": 1, "validation": 1, "test": 1, "smoke": 1
                }), SearchBudget(1, 1, 1), EvaluationBudget(1, 10)
            )
            stream = StreamConfig("resume", ("tsp_a", "tsp_b"))
            run_dir = root / "run"
            interrupted = RecordingGenerator(fail_on="tsp_b")
            runner = StreamRunner(
                TaskRegistry(tasks), stream, experiment, FakeEvaluator(root),
                interrupted, run_dir, 1,
            )
            with self.assertRaises(RuntimeError):
                runner.run()
            self.assertEqual(["tsp_a", "tsp_b"], interrupted.calls)
            resumed = RecordingGenerator()
            StreamRunner(
                TaskRegistry(tasks), stream, experiment, FakeEvaluator(root),
                resumed, run_dir, 1,
            ).run()
            self.assertEqual(["tsp_b"], resumed.calls)


if __name__ == "__main__":
    unittest.main()
