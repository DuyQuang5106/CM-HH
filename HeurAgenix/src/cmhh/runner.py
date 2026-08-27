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
from cmhh.logging import EventRecord, EventWriter
from cmhh.archivist import Archivist, DefaultArchivist, EvictionPolicy
from cmhh.memory import (
    MemoryEvidence,
    MemoryItem,
    MemoryKey,
    MemoryScope,
    MemoryStore,
    MemoryUnit,
    MemoryValue,
    WorkingBuffer,
    create_memory_unit,
)
from cmhh.memory_diagnostics import build_memory_diagnostics
from cmhh.metrics.continual import average_final_performance, backward_transfer, forward_transfer
from cmhh.models import HeuristicArtifact
from cmhh.reporting import write_evaluation
from cmhh.retrieval import RetrievalBudget, RetrievalQuery, Retriever, RetrieverV0
from cmhh.tasks import TaskRegistry
from cmhh.tracking import ExperimentTracker, create_tracker


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
        retriever: Retriever | None = None,
        archivist: Archivist | None = None,
        tracker: ExperimentTracker | None = None,
    ) -> None:
        self.registry = registry
        self.stream = stream
        self.experiment = experiment
        self.evaluator = evaluator
        self.generator = generator
        self.run_dir = Path(run_dir)
        self.seed = seed
        self.cold_start_scores = cold_start_scores
        self.retriever = retriever or RetrieverV0()
        self.archivist = archivist or DefaultArchivist(
            eviction=EvictionPolicy(max_capacity=self.naive_memory_capacity)
        )
        self.working_buffer = WorkingBuffer(capacity=50)
        self.tracker = tracker or create_tracker(
            getattr(experiment, "tracking", None),
            run_id=self.run_dir.name,
            run_dir=self.run_dir,
            stream_id=stream.stream_id,
            experiment_name=experiment.name,
        )

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

        try:
            self.tracker.log_config({
                "experiment_name": self.experiment.name,
                "condition": self.experiment.condition,
                "stream_id": self.stream.stream_id,
                "task_ids": list(self.stream.task_ids),
                "seed": self.seed,
                "archive_policy": getattr(self.experiment.archive, "policy", "naive_overwrite"),
                "archive_capacity": self.naive_memory_capacity,
                "archive_top_k": self.naive_memory_top_k,
            })

            for k in range(int(checkpoint["completed_tasks"]), len(self.stream.task_ids)):
                task = self.registry.get(self.stream.task_ids[k])
                
                # Executed read-only Pre-learning Probe (A) on task Tk using M_{k-1} state
                self._run_pre_learning_probe(k, task)
                
                seeds = self._seed_population(task, carryover_population)
                memory_context = self._retrieve_memory_context(task) if self._uses_naive_memory else []
                carryover_validation_score = (
                    self._score_seed_population_on_validation(task, seeds, k)
                    if self._uses_naive_memory else None
                )
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
                    self._log_memory_reuse_outcome(
                        task,
                        memory_context,
                        validation_summaries[best.heuristic_id],
                        carryover_validation_score,
                    )
                selected[task.task_id] = best.to_dict()
                self._event("candidate_selected", task_id=task.task_id, heuristic_id=best.heuristic_id)

                # Execute read-only Retention Probe (C) on tasks T_1..T_k using Retriever & M_k
                self._run_retention_probe(k, selected, matrix)

                # Track task-level step metrics
                step_metrics: dict[str, float] = {
                    "stream_step": k,
                    "performance/validation_score": float(validation_summaries[best.heuristic_id].get("score", float("nan"))),
                }
                if k in matrix and k in matrix[k]:
                    step_metrics["performance/current_task_gap"] = matrix[k][k]
                if self._uses_naive_memory:
                    store = self._memory_store()
                    step_metrics["memory/size"] = len(store.load_all())
                self.tracker.log_metrics(step_metrics, step=k)

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
            
            metrics = self._write_metrics(matrix)
            self.tracker.log_performance_matrix(matrix, self.stream.task_ids)
            if metrics:
                self.tracker.log_summary(metrics)
            if self._uses_naive_memory:
                self._write_memory_diagnostics()
            return matrix
        finally:
            self.tracker.finish()

    def _run_pre_learning_probe(self, k: int, task) -> None:
        self._event(
            "pre_learning_probe_started",
            task_id=task.task_id,
            task_index=k,
            read_only=True,
        )
        retrieved_ids = []
        if self._uses_naive_memory:
            store = self._memory_store()
            query = RetrievalQuery(
                problem=task.problem,
                task_id=task.task_id,
                task_signature=self._task_signature(task),
            )
            retrieved = self.retriever.retrieve(query, store.load_all(), RetrievalBudget(top_k=1))
            retrieved_ids = [item.unit.id for item in retrieved]
        self._event(
            "pre_learning_probe_completed",
            task_id=task.task_id,
            task_index=k,
            retrieved_memory_ids=retrieved_ids,
            read_only=True,
        )

    def _run_retention_probe(
        self,
        k: int,
        selected: dict[str, dict],
        matrix: dict[int, dict[int, float]],
    ) -> None:
        matrix[k] = {}
        store = self._memory_store() if self._uses_naive_memory else None
        memory_units = store.load_all() if store else []

        for j, prior_task_id in enumerate(self.stream.task_ids[: k + 1]):
            prior_task = self.registry.get(prior_task_id)
            artifact = None

            if memory_units:
                query = RetrievalQuery(
                    problem=prior_task.problem,
                    task_id=prior_task.task_id,
                    task_signature=self._task_signature(prior_task),
                )
                retrieved = self.retriever.retrieve(query, memory_units, RetrievalBudget(top_k=1))
                if retrieved and retrieved[0].unit.evidence.source_artifacts:
                    code_path = Path(retrieved[0].unit.evidence.source_artifacts[0])
                    if code_path.exists():
                        artifact = HeuristicArtifact(
                            heuristic_id=retrieved[0].unit.scope.heuristic_family or code_path.stem,
                            problem=prior_task.problem,
                            code_path=code_path,
                            code_hash=retrieved[0].unit.evidence.code_hashes[0] if retrieved[0].unit.evidence.code_hashes else "",
                            task_id=prior_task_id,
                        )

            if artifact is None:
                artifact = _artifact_from_dict(selected[prior_task_id])

            self._event(
                "retention_probe_started",
                task_id=prior_task_id,
                heuristic_id=artifact.heuristic_id,
                after_task_index=k,
                read_only=True,
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
            self._event(
                "retention_probe_completed",
                task_id=prior_task_id,
                heuristic_id=artifact.heuristic_id,
                after_task_index=k,
                mean_score=result.mean_score,
                read_only=True,
            )

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

    @property
    def naive_memory_capacity(self) -> int | None:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.capacity
        return self.NAIVE_MEMORY_CAPACITY

    @property
    def naive_memory_top_k(self) -> int:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.top_k
        return self.NAIVE_MEMORY_TOP_K

    def _memory_store(self) -> MemoryStore:
        return MemoryStore(self.run_dir / "memory" / "memory.jsonl")

    def _retrieve_memory_context(self, task) -> list[MemoryUnit]:
        store = self._memory_store()
        query = RetrievalQuery(
            problem=task.problem,
            task_id=task.task_id,
            task_signature=self._task_signature(task),
        )
        budget = RetrievalBudget(top_k=self.naive_memory_top_k)
        retrieved = self.retriever.retrieve(query, store.load_all(), budget)
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
        self.working_buffer.clear()
        for artifact in ranked_population:
            summary = validation_summaries[artifact.heuristic_id]
            self.working_buffer.add_experience(artifact, summary, task)

        store = self._memory_store()
        result = self.archivist.process_transaction(self.working_buffer, store, task)

        for memory_id in result.admitted_ids:
            self._event(
                "memory_written",
                task_id=task.task_id,
                memory_id=memory_id,
            )
        for memory_id in result.protected_ids:
            self._event(
                "memory_protected",
                task_id=task.task_id,
                memory_id=memory_id,
            )
        for memory_id in result.evicted_ids:
            self._event(
                "memory_evicted",
                task_id=task.task_id,
                memory_id=memory_id,
            )

    def _score_seed_population_on_validation(
        self,
        task,
        seed_population: list[HeuristicArtifact],
        task_index: int,
    ) -> float | None:
        best_score = None
        for seed in seed_population:
            smoke = self.evaluator.evaluate(seed, task, "smoke")
            if smoke.failure_rate > 0:
                continue
            validation = self.evaluator.evaluate(seed, task, "validation")
            write_evaluation(
                self.run_dir / "evaluations" / f"task_{task_index}_carryover_seed_validation" / f"{seed.heuristic_id}.json",
                validation,
            )
            objectives = [
                item.objective
                for item in validation.successful
                if item.objective is not None
            ]
            if validation.failure_rate == 0 and objectives:
                score = -(sum(objectives) / len(objectives))
                best_score = score if best_score is None else max(best_score, score)
        return best_score

    def _log_memory_reuse_outcome(
        self,
        task,
        memory_context: list[MemoryUnit],
        selected_validation_summary: dict,
        carryover_validation_score: float | None,
    ) -> None:
        selected_score = selected_validation_summary.get("score")
        delta = (
            None
            if not memory_context or carryover_validation_score is None or selected_score is None
            else float(selected_score) - carryover_validation_score
        )
        self._event(
            "memory_reuse_outcome",
            task_id=task.task_id,
            memory_ids=[unit.id for unit in memory_context],
            selected_validation_score=selected_score,
            carryover_validation_score=carryover_validation_score,
            post_reuse_validation_delta=delta,
        )

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
        writer = EventWriter(path)
        record = EventRecord(
            event=event,
            task_id=content.get("task_id"),
            payload=content,
            schema_version=1,
        )
        writer.write_event(record)

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

    def _write_metrics(self, matrix: dict[int, dict[int, float]]) -> dict[str, Any]:
        count = len(self.stream.task_ids)
        metrics: dict[str, Any] = {
            "average_final_performance": average_final_performance(matrix, count),
            "score_convention": "higher_is_better; score=-relative_gap",
        }
        if count >= 2:
            try:
                metrics["backward_transfer"] = backward_transfer(matrix, count)
            except Exception:
                metrics["backward_transfer"] = None
        else:
            metrics["backward_transfer"] = None

        if self.cold_start_scores is not None and count >= 2:
            try:
                metrics["forward_transfer"] = forward_transfer(matrix, self.cold_start_scores, count)
            except Exception:
                metrics["forward_transfer"] = None

        write_json_atomic(self.run_dir / "metrics.json", metrics)
        return metrics

    def _write_memory_diagnostics(self) -> None:
        diagnostics = build_memory_diagnostics(self.run_dir, self.stream.task_ids)
        write_json_atomic(self.run_dir / "memory" / "diagnostics.json", diagnostics)


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
