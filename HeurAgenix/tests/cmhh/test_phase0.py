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
from cmhh.config import ArchiveConfig, DataConfig, ExperimentConfig, StreamConfig, load_experiment_config
from cmhh.runner import StreamRunner
from cmhh.references.concorde import ConcordeConfig, SolverFailure, solve_instance
from cmhh.references.tour import parse_concorde_tour, tour_objective
from cmhh.audit import audit_run
from cmhh.llm.budgeted_client import BudgetedLLMClient, LLMBudgetExceeded
from cmhh.llm.config import llm_config_fingerprint, sanitized_llm_config
from cmhh.archivist import AdmissionCriteria, DefaultArchivist, EvictionPolicy, ProtectionPolicy
from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryScope,
    MemoryStore,
    MemoryUnit,
    MemoryValue,
    WorkingBuffer,
    create_memory_unit,
    utc_now,
)


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

            def generate(self, task, seed_population, budget, seed, memory_context=None):
                del memory_context
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
                "test", "independent_seed", root / "results", (1,), DataConfig(42, 0, 10000, {
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

    def test_population_carryover_seeds_next_task_from_ranked_population(self) -> None:
        class FakeEvaluator:
            def __init__(self, repo_root):
                self.repo_root = Path(repo_root)

            def evaluate(self, artifact, task, split):
                objective = {
                    "baseline": 300.0,
                    "candidate_good": 100.0,
                    "candidate_bad": 200.0,
                }[artifact.heuristic_id]
                return EvaluationResult(artifact.heuristic_id, task.task_id, split, (
                    InstanceEvaluation(
                        "instance", "ok", objective, 100.0, "optimal",
                        (objective - 100.0) / 100.0, 0.01
                    ),
                ))

        class CarryoverRecordingGenerator:
            def __init__(self, artifacts):
                self.artifacts = artifacts
                self.seed_ids_by_task = {}

            def generate(self, task, seed_population, budget, seed, memory_context=None):
                del budget, seed, memory_context
                self.seed_ids_by_task[task.task_id] = [
                    artifact.heuristic_id for artifact in seed_population
                ]
                if task.task_id == "tsp_a":
                    return [self.artifacts["candidate_bad"], self.artifacts["candidate_good"]]
                return seed_population

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heuristic_dir = root / "src/problems/tsp/heuristics/basic_heuristics"
            heuristic_dir.mkdir(parents=True)
            paths = {}
            for heuristic_id in ("baseline", "candidate_good", "candidate_bad"):
                path = heuristic_dir / f"{heuristic_id}.py"
                path.write_text(f"def {heuristic_id}():\n    return None\n", encoding="utf-8")
                paths[heuristic_id] = path
            split = root / "split"
            split.mkdir()
            tasks = []
            for task_id in ("tsp_a", "tsp_b"):
                tasks.append(TaskSpec(
                    task_id, "tsp", "n20", "uniform",
                    TaskSplits(split, split, split, split),
                    TaskReference("optimal"), TaskMetric("relative_gap", "minimize"), True,
                    {"heuristic_dir": "basic_heuristics", "seed_heuristics": ["baseline"]},
                    {"nodes": 20},
                ))
            experiment = ExperimentConfig(
                "test", "population_carryover", root / "results", (1,),
                DataConfig(42, 0, 10000, {
                    "train": 1, "validation": 1, "test": 1, "smoke": 1
                }),
                SearchBudget(1, 1, 1), EvaluationBudget(1, 10)
            )
            artifacts = {
                heuristic_id: HeuristicArtifact(
                    heuristic_id, "tsp", path, hashlib.sha256(path.read_bytes()).hexdigest()
                )
                for heuristic_id, path in paths.items()
            }
            generator = CarryoverRecordingGenerator(artifacts)
            StreamRunner(
                TaskRegistry(tasks), StreamConfig("carryover", ("tsp_a", "tsp_b")),
                experiment, FakeEvaluator(root), generator, root / "run", 1,
            ).run()
            self.assertEqual(["baseline"], generator.seed_ids_by_task["tsp_a"])
            self.assertEqual(
                ["candidate_good", "candidate_bad"],
                generator.seed_ids_by_task["tsp_b"],
            )

    def test_naive_memory_preserves_carryover_and_retrieves_memory(self) -> None:
        class FakeEvaluator:
            def __init__(self, repo_root):
                self.repo_root = Path(repo_root)

            def evaluate(self, artifact, task, split):
                objective = {
                    "baseline": 300.0,
                    "candidate_good": 100.0,
                    "candidate_bad": 200.0,
                }[artifact.heuristic_id]
                return EvaluationResult(artifact.heuristic_id, task.task_id, split, (
                    InstanceEvaluation(
                        "instance", "ok", objective, 100.0, "optimal",
                        (objective - 100.0) / 100.0, 0.01
                    ),
                ))

        class MemoryRecordingGenerator:
            def __init__(self, artifacts):
                self.artifacts = artifacts
                self.seed_ids_by_task = {}
                self.memory_counts_by_task = {}

            def generate(self, task, seed_population, budget, seed, memory_context=None):
                del budget, seed
                self.seed_ids_by_task[task.task_id] = [
                    artifact.heuristic_id for artifact in seed_population
                ]
                self.memory_counts_by_task[task.task_id] = len(memory_context or [])
                if task.task_id == "tsp_a":
                    return [self.artifacts["candidate_bad"], self.artifacts["candidate_good"]]
                return seed_population

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heuristic_dir = root / "src/problems/tsp/heuristics/basic_heuristics"
            heuristic_dir.mkdir(parents=True)
            paths = {}
            for heuristic_id in ("baseline", "candidate_good", "candidate_bad"):
                path = heuristic_dir / f"{heuristic_id}.py"
                path.write_text(f"def {heuristic_id}():\n    return None\n", encoding="utf-8")
                paths[heuristic_id] = path
            split = root / "split"
            split.mkdir()
            tasks = []
            for task_id in ("tsp_a", "tsp_b"):
                tasks.append(TaskSpec(
                    task_id, "tsp", "n20", "uniform",
                    TaskSplits(split, split, split, split),
                    TaskReference("optimal"), TaskMetric("relative_gap", "minimize"), True,
                    {"heuristic_dir": "basic_heuristics", "seed_heuristics": ["baseline"]},
                    {"nodes": 20},
                ))
            experiment = ExperimentConfig(
                "test", "naive_memory_sequential", root / "results", (1,),
                DataConfig(42, 0, 10000, {
                    "train": 1, "validation": 1, "test": 1, "smoke": 1
                }),
                SearchBudget(1, 1, 1), EvaluationBudget(1, 10)
            )
            artifacts = {
                heuristic_id: HeuristicArtifact(
                    heuristic_id, "tsp", path, hashlib.sha256(path.read_bytes()).hexdigest()
                )
                for heuristic_id, path in paths.items()
            }
            generator = MemoryRecordingGenerator(artifacts)
            run_dir = root / "run"
            StreamRunner(
                TaskRegistry(tasks), StreamConfig("memory", ("tsp_a", "tsp_b")),
                experiment, FakeEvaluator(root), generator, run_dir, 1,
            ).run()
            self.assertEqual(
                ["candidate_good", "candidate_bad"],
                generator.seed_ids_by_task["tsp_b"],
            )
            self.assertEqual(0, generator.memory_counts_by_task["tsp_a"])
            self.assertGreater(generator.memory_counts_by_task["tsp_b"], 0)
            self.assertTrue((run_dir / "memory" / "memory.jsonl").exists())
            diagnostics = json.loads(
                (run_dir / "memory" / "diagnostics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(2, diagnostics["retrieval_events"])
            self.assertEqual(1, diagnostics["retrieval_events_with_results"])
            self.assertGreater(diagnostics["retrieval_coverage"], 0)
            self.assertEqual(0.0, diagnostics["post_reuse_validation_delta_mean"])


class MemoryModelTests(unittest.TestCase):
    def test_memory_unit_round_trips_through_dict(self) -> None:
        unit = MemoryUnit(
            id="mem-1",
            created_at=utc_now(),
            scope=MemoryScope(problem="tsp", task_id="tsp_n20_uniform"),
            key=MemoryKey(
                applicability="Use for compact Euclidean TSP instances",
                task_signature={"nodes": 20},
                bottleneck_type="construction_bias",
            ),
            value=MemoryValue(
                type="insight",
                content="Nearest-neighbor seeds need insertion refinement on dispersed points.",
            ),
        )
        self.assertEqual(unit, MemoryUnit.from_dict(unit.to_dict()))

    def test_memory_id_is_deterministic(self) -> None:
        kwargs = {
            "scope": MemoryScope(problem="tsp", task_id="tsp_n20_uniform"),
            "key": MemoryKey(
                applicability="Use for compact Euclidean TSP instances",
                task_signature={"nodes": 20},
            ),
            "value": MemoryValue("insight", "Prefer insertion refinement after NN."),
        }
        first = create_memory_unit(**kwargs, created_at="2026-01-01T00:00:00Z")
        second = create_memory_unit(**kwargs, created_at="2026-02-01T00:00:00Z")
        self.assertEqual(first.id, second.id)

    def test_memory_store_persists_jsonl_and_updates_validation_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.jsonl")
            unit = create_memory_unit(
                scope=MemoryScope(problem="tsp", task_id="tsp_n20_uniform"),
                key=MemoryKey(applicability="Use on small Euclidean TSP"),
                value=MemoryValue("warning", "Do not overuse raw trajectories."),
                created_at="2026-01-01T00:00:00Z",
            )
            store.upsert(unit)
            self.assertEqual([unit], store.load_all())

            updated = store.update_validation_evidence(
                unit.id,
                split="validation",
                validation_after={"score": -0.1},
            )
            self.assertEqual({"score": -0.1}, updated.evidence.validation_after)
            self.assertEqual([updated], store.load_all())

            with self.assertRaises(ValueError):
                store.update_validation_evidence(
                    unit.id,
                    split="test",
                    validation_after={"score": 1.0},
                )

    def test_archive_config_parsing_bounded_and_unbounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bounded_yaml = Path(directory) / "bounded.yaml"
            bounded_yaml.write_text("""
version: 1
experiment:
  name: bounded
  condition: naive_memory_sequential
  output_root: results
  seeds: [1]
archive:
  policy: naive_overwrite
  capacity: 20
  top_k: 5
data:
  seed: 42
  coordinate_min: 0
  coordinate_max: 10000
  splits: {train: 1, validation: 1, test: 1, smoke: 1}
search: {generations: 1, candidates_per_generation: 1, max_llm_calls: 1}
evaluation: {instance_timeout_seconds: 1, batch_timeout_seconds: 10, invalid_policy: fail_batch}
""", encoding="utf-8")
            cfg_bounded = load_experiment_config(bounded_yaml, directory)
            self.assertEqual(20, cfg_bounded.archive.capacity)
            self.assertEqual(5, cfg_bounded.archive.top_k)
            self.assertEqual("naive_overwrite", cfg_bounded.archive.policy)

            unbounded_yaml = Path(directory) / "unbounded.yaml"
            unbounded_yaml.write_text("""
version: 1
experiment:
  name: unbounded
  condition: naive_memory_sequential
  output_root: results
  seeds: [1]
archive:
  policy: naive_unbounded
  capacity: null
  top_k: 8
data:
  seed: 42
  coordinate_min: 0
  coordinate_max: 10000
  splits: {train: 1, validation: 1, test: 1, smoke: 1}
search: {generations: 1, candidates_per_generation: 1, max_llm_calls: 1}
evaluation: {instance_timeout_seconds: 1, batch_timeout_seconds: 10, invalid_policy: fail_batch}
""", encoding="utf-8")
            cfg_unbounded = load_experiment_config(unbounded_yaml, directory)
            self.assertIsNone(cfg_unbounded.archive.capacity)
            self.assertEqual(8, cfg_unbounded.archive.top_k)
            self.assertEqual("naive_unbounded", cfg_unbounded.archive.policy)

    def test_runner_enforces_capacity_only_when_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = TaskSpec(
                "tsp_a", "tsp", "n20", "uniform",
                TaskSplits(root, root, root, root),
                TaskReference("optimal"), TaskMetric("relative_gap", "minimize"), True,
                {"heuristic_dir": "basic_heuristics", "seed_heuristics": ["baseline"]},
                {"nodes": 20},
            )

            # 1. Bounded Archivist (capacity = 3)
            store_bounded = MemoryStore(root / "memory_bounded.jsonl")
            buffer_bounded = WorkingBuffer(capacity=50)
            for index in range(5):
                code_file = root / f"h_{index}.py"
                code_file.write_text("def solve(): pass", encoding="utf-8")
                artifact = HeuristicArtifact(f"h_{index}", "tsp", code_file, "hash")
                buffer_bounded.add_experience(artifact, {"score": float(index)}, task)

            archivist_bounded = DefaultArchivist(
                admission=AdmissionCriteria(elite_validation_rank=5),
                protection=ProtectionPolicy(protect_best_per_task=False),
                eviction=EvictionPolicy(max_capacity=3),
            )
            archivist_bounded.process_transaction(buffer_bounded, store_bounded, task)
            self.assertEqual(3, len(store_bounded.load_all()))

            # 2. Unbounded Archivist (capacity = None)
            store_unbounded = MemoryStore(root / "memory_unbounded.jsonl")
            buffer_unbounded = WorkingBuffer(capacity=50)
            for index in range(5):
                code_file = root / f"h_{index}.py"
                artifact = HeuristicArtifact(f"h_{index}", "tsp", code_file, "hash")
                buffer_unbounded.add_experience(artifact, {"score": float(index)}, task)

            archivist_unbounded = DefaultArchivist(
                admission=AdmissionCriteria(elite_validation_rank=5),
                protection=ProtectionPolicy(protect_best_per_task=False),
                eviction=EvictionPolicy(max_capacity=None),
            )
            archivist_unbounded.process_transaction(buffer_unbounded, store_unbounded, task)
            self.assertEqual(5, len(store_unbounded.load_all()))



if __name__ == "__main__":
    unittest.main()
