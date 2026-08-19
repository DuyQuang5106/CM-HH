from __future__ import annotations

import json
import tempfile
import unittest
import hashlib
from pathlib import Path

from cmhh.audit import audit_run
from cmhh.config import DataConfig, ExperimentConfig, SearchBudget, StreamConfig
from cmhh.evaluation.evaluator import Evaluator
from cmhh.models import EvaluationBudget, EvaluationResult, HeuristicArtifact, InstanceEvaluation
from cmhh.runner import StreamRunner
from cmhh.tasks import TaskMetric, TaskReference, TaskRegistry, TaskSpec, TaskSplits


class SyntheticEvaluator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def evaluate(self, artifact: HeuristicArtifact, task: TaskSpec, split: str) -> EvaluationResult:
        # Mock objective based on task size tier and heuristic id
        base_obj = 100.0 if "20" in task.task_id else (200.0 if "50" in task.task_id else 400.0)
        heuristic_mult = 1.0 if "best" in artifact.heuristic_id else 1.2
        objective = base_obj * heuristic_mult
        gap = (objective - base_obj) / base_obj

        return EvaluationResult(
            heuristic_id=artifact.heuristic_id,
            task_id=task.task_id,
            split=split,
            instances=(
                InstanceEvaluation(
                    instance_id="inst_1",
                    status="ok",
                    objective=objective,
                    reference_objective=base_obj,
                    reference_status="optimal",
                    relative_gap=gap,
                    runtime_seconds=0.01,
                ),
            ),
        )


class SyntheticGenerator:
    def __init__(self, artifacts: dict[str, HeuristicArtifact]) -> None:
        self.artifacts = artifacts

    def generate(
        self,
        task: TaskSpec,
        seed_population: list[HeuristicArtifact],
        budget: SearchBudget,
        seed: int,
        memory_context: list | None = None,
    ) -> list[HeuristicArtifact]:
        del budget, seed, memory_context
        best_id = f"h_best_{task.task_id}"
        other_id = f"h_other_{task.task_id}"

        # Create dummy artifacts dynamically if needed
        for hid in (best_id, other_id):
            if hid not in self.artifacts:
                code_path = task.splits.train.parent / f"{hid}.py"
                code_path.write_text(f"def {hid}(): pass\n", encoding="utf-8")
                self.artifacts[hid] = HeuristicArtifact(
                    heuristic_id=hid,
                    problem=task.problem,
                    code_path=code_path,
                    code_hash=hashlib.sha256(code_path.read_bytes()).hexdigest(),
                    task_id=task.task_id,
                )
        return [self.artifacts[best_id], self.artifacts[other_id]] + seed_population


class EndToEndStreamIntegrationTests(unittest.TestCase):
    def test_full_3task_stream_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            heuristic_dir = root / "src/problems/tsp/heuristics/basic_heuristics"
            heuristic_dir.mkdir(parents=True)
            seed_path = heuristic_dir / "seed.py"
            seed_path.write_text("def seed(): pass\n", encoding="utf-8")

            split_dir = root / "split"
            split_dir.mkdir()
            (split_dir / "inst_1.tsp").write_text("NAME: inst_1\n", encoding="utf-8")

            tasks = []
            task_ids = ("tsp_20", "tsp_50", "tsp_100")
            for task_id in task_ids:
                tasks.append(TaskSpec(
                    task_id=task_id,
                    problem="tsp",
                    size_tier=task_id.split("_")[1],
                    distribution="uniform",
                    splits=TaskSplits(split_dir, split_dir, split_dir, split_dir),
                    reference=TaskReference("optimal"),
                    metric=TaskMetric("relative_gap", "minimize"),
                    implemented_in_heuragenix=True,
                    baseline_pool={"heuristic_dir": "basic_heuristics", "seed_heuristics": ["seed"]},
                    metadata={"nodes": int(task_id.split("_")[1])},
                ))

            experiment = ExperimentConfig(
                name="e2e_test",
                condition="naive_memory_sequential",
                output_root=root / "results",
                seeds=(42,),
                data=DataConfig(42, 0, 10000, {"train": 1, "validation": 1, "test": 1, "smoke": 1}),
                search=SearchBudget(1, 2, 2),
                evaluation=EvaluationBudget(1.0, 10.0),
            )

            registry = TaskRegistry(tasks)
            stream = StreamConfig(stream_id="e2e_stream", task_ids=task_ids)
            run_dir = root / "results" / "run_e2e"

            seed_artifact = HeuristicArtifact(
                heuristic_id="seed",
                problem="tsp",
                code_path=seed_path,
                code_hash=hashlib.sha256(seed_path.read_bytes()).hexdigest(),
            )
            generator = SyntheticGenerator({"seed": seed_artifact})
            evaluator = SyntheticEvaluator(root)

            runner = StreamRunner(
                registry=registry,
                stream=stream,
                experiment=experiment,
                evaluator=evaluator,
                generator=generator,
                run_dir=run_dir,
                seed=42,
            )
            matrix = runner.run()

            # Assert 3x3 matrix structure
            self.assertEqual(3, len(matrix))
            self.assertEqual(1, len(matrix[0]))
            self.assertEqual(2, len(matrix[1]))
            self.assertEqual(3, len(matrix[2]))

            # Assert generated files
            self.assertTrue((run_dir / "performance_matrix.csv").exists())
            self.assertTrue((run_dir / "metrics.json").exists())
            self.assertTrue((run_dir / "memory" / "memory.jsonl").exists())
            self.assertTrue((run_dir / "memory" / "diagnostics.json").exists())
            self.assertTrue((run_dir / "events.jsonl").exists())

            # Assert memory diagnostics structure
            diagnostics = json.loads((run_dir / "memory" / "diagnostics.json").read_text(encoding="utf-8"))
            self.assertEqual(1, diagnostics["schema_version"])
            self.assertGreater(diagnostics["retrieval_events"], 0)
            self.assertIn("eviction_lineage", diagnostics)

            # Assert events schema version 1 and read-only probe events
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
            probe_events = [e for e in events if "probe" in e["event"]]
            self.assertGreater(len(probe_events), 0)
            for event in events:
                self.assertEqual(1, event["schema_version"])


if __name__ == "__main__":
    unittest.main()
