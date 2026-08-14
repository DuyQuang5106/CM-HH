from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cmhh.agents.generator import Generator
from cmhh.baselines import baseline_artifacts
from cmhh.checkpoint import load_checkpoint, save_checkpoint
from cmhh.config import ExperimentConfig, StreamConfig
from cmhh.data.manifest import write_json_atomic
from cmhh.evaluation.evaluator import Evaluator
from cmhh.metrics.continual import average_final_performance, backward_transfer, forward_transfer
from cmhh.models import HeuristicArtifact
from cmhh.reporting import write_evaluation
from cmhh.tasks import TaskRegistry


class StreamRunner:
    def __init__(
        self,
        registry: TaskRegistry,
        stream: StreamConfig,
        experiment: ExperimentConfig,
        evaluator: Evaluator,
        generator: Generator,
        run_dir: str | Path,
        seed: int,
        cold_start_scores: dict[int, float] | None = None,
    ) -> None:
        self.registry = registry
        self.stream = stream
        self.experiment = experiment
        self.evaluator = evaluator
        self.generator = generator
        self.run_dir = Path(run_dir)
        self.seed = seed
        self.cold_start_scores = cold_start_scores

    def run(self) -> dict[int, dict[int, float]]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.run_dir / "checkpoints" / "latest.json"
        checkpoint = load_checkpoint(checkpoint_path) or {
            "completed_tasks": 0,
            "selected": {},
            "matrix": {},
        }
        selected = dict(checkpoint["selected"])
        matrix = {
            int(row): {int(column): float(value) for column, value in values.items()}
            for row, values in checkpoint["matrix"].items()
        }

        for k in range(int(checkpoint["completed_tasks"]), len(self.stream.task_ids)):
            task = self.registry.get(self.stream.task_ids[k])
            seeds = baseline_artifacts(task, self.evaluator.repo_root)
            candidates = self.generator.generate(task, seeds, self.experiment.search, self.seed + k)
            best = self._select_on_validation(task, candidates, k)
            selected[task.task_id] = best.to_dict()
            self._event("candidate_selected", task_id=task.task_id, heuristic_id=best.heuristic_id)
            matrix[k] = {}
            for j, prior_task_id in enumerate(self.stream.task_ids[: k + 1]):
                prior_task = self.registry.get(prior_task_id)
                artifact = _artifact_from_dict(selected[prior_task_id])
                self._event(
                    "test_evaluation_started",
                    task_id=prior_task_id,
                    heuristic_id=artifact.heuristic_id,
                    after_task_index=k,
                )
                result = self.evaluator.evaluate(artifact, prior_task, "test")
                write_evaluation(
                    self.run_dir / "evaluations" / f"after_{k}" / f"{prior_task_id}.json",
                    result,
                )
                if result.mean_score is None:
                    raise RuntimeError(
                        f"Cannot build performance matrix for {prior_task_id}: certified or "
                        "best-known references are missing"
                    )
                matrix[k][j] = result.mean_score
            save_checkpoint(checkpoint_path, {
                "completed_tasks": k + 1,
                "selected": selected,
                "matrix": matrix,
            })
            self._write_matrix(matrix)
        self._write_metrics(matrix)
        return matrix

    def _select_on_validation(
        self,
        task,
        candidates: list[HeuristicArtifact],
        task_index: int,
    ) -> HeuristicArtifact:
        ranked = []
        for candidate in candidates:
            smoke = self.evaluator.evaluate(candidate, task, "smoke")
            if smoke.failure_rate > 0:
                continue
            result = self.evaluator.evaluate(candidate, task, "validation")
            write_evaluation(
                self.run_dir / "evaluations" / f"task_{task_index}_validation" / f"{candidate.heuristic_id}.json",
                result,
            )
            objectives = [item.objective for item in result.successful if item.objective is not None]
            if result.failure_rate == 0 and objectives:
                mean_objective = sum(objectives) / len(objectives)
                mean_runtime = sum(item.runtime_seconds for item in result.successful) / len(result.successful)
                ranked.append((mean_objective, result.failure_rate, mean_runtime, candidate.heuristic_id, candidate))
        if not ranked:
            raise RuntimeError(f"No valid candidate for {task.task_id}")
        return min(ranked, key=lambda item: item[:4])[4]

    def _event(self, event: str, **content) -> None:
        path = self.run_dir / "events.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **content,
        }
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, sort_keys=True) + "\n")

    def _write_matrix(self, matrix: dict[int, dict[int, float]]) -> None:
        path = self.run_dir / "performance_matrix.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(["after_task", *self.stream.task_ids])
            for row in range(len(self.stream.task_ids)):
                if row not in matrix:
                    continue
                writer.writerow([
                    self.stream.task_ids[row],
                    *[matrix[row].get(column, "") for column in range(len(self.stream.task_ids))],
                ])

    def _write_metrics(self, matrix: dict[int, dict[int, float]]) -> None:
        count = len(self.stream.task_ids)
        metrics = {
            "average_final_performance": average_final_performance(matrix, count),
            "backward_transfer": backward_transfer(matrix, count),
            "score_convention": "higher_is_better; score=-relative_gap",
        }
        if self.cold_start_scores is not None:
            metrics["forward_transfer"] = forward_transfer(matrix, self.cold_start_scores, count)
        write_json_atomic(self.run_dir / "metrics.json", metrics)


def _artifact_from_dict(raw: dict) -> HeuristicArtifact:
    return HeuristicArtifact(
        heuristic_id=raw["heuristic_id"],
        problem=raw["problem"],
        code_path=Path(raw["code_path"]),
        code_hash=raw["code_hash"],
        strategy=raw.get("strategy"),
        parent_ids=tuple(raw.get("parent_ids", [])),
        generation=int(raw.get("generation", 0)),
        task_id=raw.get("task_id"),
        prompt_hash=raw.get("prompt_hash"),
        model=raw.get("model"),
        llm_call_index=raw.get("llm_call_index"),
    )
