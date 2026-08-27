from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.agents.generator import BaselineGenerator
from cmhh.config import (
    DataConfig,
    EvaluationBudget,
    ExperimentConfig,
    SearchBudget,
    StreamConfig,
    TrackingConfig,
    WandbConfig,
    load_experiment_config,
)
from cmhh.evaluation.evaluator import Evaluator
from cmhh.runner import StreamRunner
from cmhh.tasks import TaskMetric, TaskReference, TaskRegistry, TaskSpec, TaskSplits
from cmhh.tracking import NoOpTracker, WandbTracker, create_tracker


class TrackingTests(unittest.TestCase):
    def test_noop_tracker_handles_all_calls_without_error(self) -> None:
        tracker = NoOpTracker()
        tracker.log_config({"test_key": "test_val"})
        tracker.log_metrics({"metric/gap": 0.15}, step=0)
        tracker.log_event("probe_event", {"task": "tsp20"}, step=0)
        tracker.log_performance_matrix({0: {0: 0.15}}, ("task_1",))
        tracker.log_summary({"bwt": 0.02, "fwt": 0.05})
        tracker.finish()

    def test_tracking_config_parsing_defaults_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            yaml_path = root / "exp_tracking.yaml"
            yaml_path.write_text("""
version: 1
experiment:
  name: tracking_test
  condition: independent_seed
  output_root: results/tracking_test
  seeds: [42]
data:
  seed: 42
  coordinate_min: 0
  coordinate_max: 10000
  splits: {train: 1, validation: 1, test: 1, smoke: 1}
search: {generations: 1, candidates_per_generation: 1, max_llm_calls: 1}
evaluation: {instance_timeout_seconds: 1, batch_timeout_seconds: 10, invalid_policy: fail_batch}
tracking:
  wandb:
    enabled: true
    project: cmhh_custom
    entity: my_team
    mode: offline
    tags: [pilot, test]
    run_name: custom_run_name
""", encoding="utf-8")
            config = load_experiment_config(yaml_path, root)
            self.assertTrue(config.tracking.wandb.enabled)
            self.assertEqual("cmhh_custom", config.tracking.wandb.project)
            self.assertEqual("my_team", config.tracking.wandb.entity)
            self.assertEqual("offline", config.tracking.wandb.mode)
            self.assertEqual(("pilot", "test"), config.tracking.wandb.tags)
            self.assertEqual("custom_run_name", config.tracking.wandb.run_name)

    def test_create_tracker_returns_noop_when_disabled(self) -> None:
        cfg = TrackingConfig(wandb=WandbConfig(enabled=False))
        tracker = create_tracker(cfg, run_id="test_run")
        self.assertIsInstance(tracker, NoOpTracker)

        cfg_mode_disabled = TrackingConfig(wandb=WandbConfig(enabled=True, mode="disabled"))
        tracker2 = create_tracker(cfg_mode_disabled, run_id="test_run")
        self.assertIsInstance(tracker2, NoOpTracker)

    def test_wandb_tracker_disabled_mode_is_safe(self) -> None:
        tracker = WandbTracker(mode="disabled", run_id="disabled_run")
        tracker.log_config({"param": 1})
        tracker.log_metrics({"gap": 0.1}, step=1)
        tracker.log_performance_matrix({0: {0: 0.1}}, ["t1"])
        tracker.log_summary({"bwt": 0.0})
        tracker.finish()

    def test_wandb_offline_tracking_end_to_end(self) -> None:
        tracker = WandbTracker(
            project="cmhh_test",
            mode="offline",
            run_id="test_offline_run",
            extra_config={"test_meta": "value"},
        )
        tracker.log_config({"learning_rate": 0.01})
        tracker.log_metrics({"performance/optimality_gap": 0.12}, step=0)
        tracker.log_event("task_finished", {"task_id": "tsp_n20"}, step=0)
        tracker.log_performance_matrix({0: {0: 0.12}}, ("tsp_n20",))
        tracker.log_summary({"continual/bwt": 0.05})
        tracker.finish()

    def test_runner_preserves_local_artifacts_with_tracking(self) -> None:
        class SimpleEvaluator:
            def __init__(self, repo_root):
                self.repo_root = Path(repo_root)

            def evaluate(self, artifact, task, split):
                from cmhh.models import EvaluationResult, InstanceEvaluation
                return EvaluationResult(artifact.heuristic_id, task.task_id, split, (
                    InstanceEvaluation("i0", "ok", 100.0, 100.0, "optimal", 0.0, 0.01),
                ))

        class SimpleGenerator:
            def generate(self, task, seed_population, budget, seed, memory_context=None):
                return seed_population

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heuristic_dir = root / "src/problems/tsp/heuristics/basic_heuristics"
            heuristic_dir.mkdir(parents=True, exist_ok=True)
            baseline_file = heuristic_dir / "h0.py"
            baseline_file.write_text("def solve(): pass", encoding="utf-8")

            split = root / "split"
            split.mkdir()
            task = TaskSpec(
                "task_0", "tsp", "n3", "uniform",
                TaskSplits(split, split, split, split),
                TaskReference("optimal"), TaskMetric("relative_gap", "minimize"), True,
                {"heuristic_dir": "basic_heuristics", "seed_heuristics": ["h0"]},
                {"nodes": 3},
            )
            registry = TaskRegistry([task])
            stream = StreamConfig("stream_test", ("task_0",))
            experiment = ExperimentConfig(
                "exp_test", "isolated", root / "results", (42,),
                DataConfig(42, 0, 10000, {"train": 1, "validation": 1, "test": 1, "smoke": 1}),
                SearchBudget(1, 1, 1), EvaluationBudget(1, 10),
            )

            # Run with mock tracker
            mock_tracker = MagicMock()
            runner = StreamRunner(
                registry=registry,
                stream=stream,
                experiment=experiment,
                evaluator=SimpleEvaluator(root),
                generator=SimpleGenerator(),
                run_dir=root / "run_tracked",
                seed=42,
                tracker=mock_tracker,
            )
            runner.run()

            # Check that local artifacts were written
            self.assertTrue((root / "run_tracked" / "metrics.json").exists())
            self.assertTrue((root / "run_tracked" / "performance_matrix.csv").exists())
            self.assertTrue((root / "run_tracked" / "events.jsonl").exists())
            self.assertTrue((root / "run_tracked" / "checkpoints" / "latest.json").exists())

            # Verify tracker was called
            mock_tracker.log_config.assert_called_once()
            mock_tracker.log_metrics.assert_called()
            mock_tracker.log_performance_matrix.assert_called_once()
            mock_tracker.log_summary.assert_called_once()
            mock_tracker.finish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
