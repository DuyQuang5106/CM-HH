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
from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryScope,
    MemoryStore,
    MemoryUnit,
    MemoryValue,
    create_memory_unit,
    retrieve_naive,
)
from cmhh.metrics.continual import average_final_performance, backward_transfer, forward_transfer
from cmhh.models import HeuristicArtifact
from cmhh.reporting import write_evaluation
from cmhh.tasks import TaskRegistry


class StreamRunner:
    NAIVE_MEMORY_CAPACITY = 20
    NAIVE_MEMORY_TOP_K = 5

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
            "carryover_population": [],
            "matrix": {},
        }
        selected = dict(checkpoint["selected"])
        carryover_population = [
            _artifact_from_dict(raw)
            for raw in checkpoint.get("carryover_population", [])
        ]
        matrix = {
            int(row): {int(column): float(value) for column, value in values.items()}
            for row, values in checkpoint["matrix"].items()
        }

        for k in range(int(checkpoint["completed_tasks"]), len(self.stream.task_ids)):
            task = self.registry.get(self.stream.task_ids[k])
            seeds = self._seed_population(task, carryover_population)
            memory_context = self._retrieve_memory_context(task) if self._uses_naive_memory else []
            candidates = self.generator.generate(
                task,
                seeds,
                self.experiment.search,
                self.seed + k,
                memory_context=memory_context,
            )
            ranked_population, validation_summaries = self._rank_on_validation(task, candidates, k)
            best = ranked_population[0]
            if self._uses_population_carryover:
                carryover_population = ranked_population
            if self._uses_naive_memory:
                self._write_naive_memory(task, ranked_population, validation_summaries)
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
                "carryover_population": [
                    artifact.to_dict()
                    for artifact in carryover_population
                ],
                "matrix": matrix,
            })
            self._write_matrix(matrix)
        self._write_metrics(matrix)
        return matrix

    def _seed_population(
        self,
        task,
        carryover_population: list[HeuristicArtifact],
    ) -> list[HeuristicArtifact]:
        if self._uses_population_carryover and carryover_population:
            compatible = [
                artifact
                for artifact in carryover_population
                if artifact.problem == task.problem
            ]
            if compatible:
                self._event(
                    "population_carried_over",
                    task_id=task.task_id,
                    seed_count=len(compatible),
                    source_heuristic_ids=[artifact.heuristic_id for artifact in compatible],
                )
                return compatible
        return baseline_artifacts(task, self.evaluator.repo_root)

    @property
    def _uses_population_carryover(self) -> bool:
        return self.experiment.condition in {"population_carryover", "naive_memory_sequential"}

    @property
    def _uses_naive_memory(self) -> bool:
        return self.experiment.condition == "naive_memory_sequential"

    def _memory_store(self) -> MemoryStore:
        return MemoryStore(self.run_dir / "memory" / "memory.jsonl")

    def _retrieve_memory_context(self, task) -> list[MemoryUnit]:
        store = self._memory_store()
        retrieved = retrieve_naive(
            store.load_all(),
            problem=task.problem,
            task_signature=self._task_signature(task),
            top_k=self.NAIVE_MEMORY_TOP_K,
        )
        keys = [item.unit.key.applicability for item in retrieved]
        duplicate_key_rate = (
            0.0 if not keys else 1.0 - (len(set(keys)) / len(keys))
        )
        self._event(
            "memory_retrieved",
            task_id=task.task_id,
            memory_ids=[item.unit.id for item in retrieved],
            retrieval_ranks=[item.rank for item in retrieved],
            retrieval_scores=[item.score for item in retrieved],
            source_tasks=[item.unit.scope.task_id for item in retrieved],
            duplicate_key_rate=duplicate_key_rate,
            used_in_generation=True,
        )
        return [item.unit for item in retrieved]

    def _write_naive_memory(
        self,
        task,
        ranked_population: list[HeuristicArtifact],
        validation_summaries: dict[str, dict],
    ) -> None:
        store = self._memory_store()
        for artifact in ranked_population:
            summary = validation_summaries[artifact.heuristic_id]
            unit = create_memory_unit(
                scope=MemoryScope(
                    problem=task.problem,
                    task_id=task.task_id,
                    heuristic_family=artifact.heuristic_id.split("_")[0],
                    generation=artifact.generation,
                ),
                key=MemoryKey(
                    applicability=(
                        f"Uncurated {task.problem} memory from {task.task_id} "
                        f"for size {task.size_tier} and distribution {task.distribution}"
                    ),
                    task_signature=self._task_signature(task),
                ),
                value=MemoryValue(
                    type="trajectory",
                    content=(
                        f"Heuristic {artifact.heuristic_id} survived smoke and validation "
                        f"on {task.task_id}; reuse cautiously as naive external memory."
                    ),
                ),
                evidence=MemoryEvidence(
                    source_artifacts=(str(artifact.code_path),),
                    validation_after=summary,
                    code_hashes=(artifact.code_hash,),
                ),
            )
            store.upsert(unit)
            self._event(
                "memory_written",
                task_id=task.task_id,
                memory_id=unit.id,
                heuristic_id=artifact.heuristic_id,
                validation_score=summary["score"],
            )
        self._enforce_naive_memory_capacity(store)

    def _enforce_naive_memory_capacity(self, store: MemoryStore) -> None:
        units = store.load_all()
        if len(units) <= self.NAIVE_MEMORY_CAPACITY:
            return
        ordered = sorted(
            units,
            key=lambda unit: (
                unit.evidence.validation_after.get("score", float("-inf")),
                unit.created_at,
                unit.id,
            ),
            reverse=True,
        )
        kept = ordered[:self.NAIVE_MEMORY_CAPACITY]
        evicted = ordered[self.NAIVE_MEMORY_CAPACITY:]
        store.save_all(kept)
        for unit in evicted:
            self._event("memory_evicted", memory_id=unit.id, task_id=unit.scope.task_id)

    def _task_signature(self, task) -> dict:
        signature = {
            "problem": task.problem,
            "size_tier": task.size_tier,
            "distribution": task.distribution,
        }
        signature.update(task.metadata)
        return signature

    def _rank_on_validation(
        self,
        task,
        candidates: list[HeuristicArtifact],
        task_index: int,
    ) -> tuple[list[HeuristicArtifact], dict[str, dict]]:
        ranked = []
        summaries = {}
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
                summaries[candidate.heuristic_id] = {
                    "split": "validation",
                    "objective": mean_objective,
                    "score": -mean_objective,
                    "failure_rate": result.failure_rate,
                    "runtime_seconds": mean_runtime,
                }
                ranked.append((mean_objective, result.failure_rate, mean_runtime, candidate.heuristic_id, candidate))
        if not ranked:
            raise RuntimeError(f"No valid candidate for {task.task_id}")
        return [
            item[4]
            for item in sorted(ranked, key=lambda item: item[:4])
        ], summaries

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
