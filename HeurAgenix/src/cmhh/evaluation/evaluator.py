from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from cmhh.data.manifest import sha256_file
from cmhh.data.references import ReferenceSet, load_reference_set
from cmhh.metrics.objective import relative_gap
from cmhh.models import EvaluationBudget, EvaluationResult, HeuristicArtifact, InstanceEvaluation
from cmhh.tasks import TaskSpec


from cmhh.evaluation.problem_adapter import ProblemRegistry


class Evaluator:
    def __init__(self, repo_root: str | Path, budget: EvaluationBudget) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.budget = budget

    def evaluate(
        self,
        heuristic: HeuristicArtifact,
        task: TaskSpec,
        split: str,
    ) -> EvaluationResult:
        split_path = getattr(task.splits, split)
        if split_path is None or not split_path.exists():
            raise FileNotFoundError(f"Missing {split} data for {task.task_id}: {split_path}")
        adapter = ProblemRegistry.get(task.problem)
        instances = adapter.discover_instances(split_path)

        references = self._load_references(task)
        started = time.monotonic()
        results: list[InstanceEvaluation] = []
        for instance in instances:
            elapsed = time.monotonic() - started
            if elapsed >= self.budget.batch_timeout_seconds:
                results.append(InstanceEvaluation(
                    instance_id=instance.stem,
                    status="batch_timeout",
                    objective=None,
                    reference_objective=None,
                    reference_status=None,
                    relative_gap=None,
                    runtime_seconds=0.0,
                    error="Batch timeout exceeded before instance execution",
                ))
                continue
            results.append(self._evaluate_instance(heuristic, task, instance, references))
        return EvaluationResult(heuristic.heuristic_id, task.task_id, split, tuple(results))

    def _load_references(self, task: TaskSpec) -> ReferenceSet | None:
        path = task.reference.path
        return load_reference_set(path) if path is not None and path.exists() else None

    def _evaluate_instance(
        self,
        heuristic: HeuristicArtifact,
        task: TaskSpec,
        instance: Path,
        references: ReferenceSet | None,
    ) -> InstanceEvaluation:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="cmhh_eval_") as temp_dir:
            result_path = Path(temp_dir) / "result.json"
            command = [
                sys.executable,
                "-m",
                "cmhh.evaluation.worker",
                "--problem", task.problem,
                "--instance", str(instance),
                "--heuristic", str(heuristic.code_path),
                "--result", str(result_path),
            ]
            environment = dict(__import__("os").environ)
            repo_path = str(self.repo_root)
            source_path = str(self.repo_root / "src")
            environment["PYTHONPATH"] = (
                repo_path
                + __import__("os").pathsep
                + source_path
                + __import__("os").pathsep
                + environment.get("PYTHONPATH", "")
            )

            try:
                completed = subprocess.run(
                    command,
                    cwd=self.repo_root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=self.budget.instance_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return InstanceEvaluation(
                    instance.stem, "timeout", None, None, None, None,
                    time.perf_counter() - started, "Instance timeout exceeded"
                )
            if not result_path.exists():
                error = (completed.stderr or completed.stdout or "Worker produced no result")[-4000:]
                return InstanceEvaluation(
                    instance.stem, "worker_failure", None, None, None, None,
                    time.perf_counter() - started, error
                )
            raw = json.loads(result_path.read_text(encoding="utf-8"))

        reference = references.get_optional(instance.stem) if references else None
        if reference and reference.instance_sha256 != sha256_file(instance):
            return InstanceEvaluation(
                instance.stem, "reference_mismatch", raw.get("objective"), reference.objective,
                reference.status, None, time.perf_counter() - started,
                "Reference checksum does not match the evaluated instance",
            )
        objective = raw.get("objective")
        gap = (
            relative_gap(float(objective), reference.objective, objective=task.metric.objective)
            if objective is not None and reference
            else None
        )

        return InstanceEvaluation(
            instance_id=instance.stem,
            status=raw["status"],
            objective=float(objective) if objective is not None else None,
            reference_objective=reference.objective if reference else None,
            reference_status=reference.status if reference else None,
            relative_gap=gap,
            runtime_seconds=float(raw.get("runtime_seconds", time.perf_counter() - started)),
            error=raw.get("error"),
        )

