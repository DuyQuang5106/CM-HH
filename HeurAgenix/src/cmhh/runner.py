from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cmhh.agents.generator import Generator
from cmhh.baselines import baseline_artifacts
from cmhh.candidate_extractor import TopKCandidateExtractor
from cmhh.checkpoint import load_checkpoint, save_checkpoint
from cmhh.config import ExperimentConfig, StreamConfig
from cmhh.data.manifest import write_json_atomic
from cmhh.evaluation.evaluator import Evaluator
from cmhh.logging import EventRecord, EventWriter
from cmhh.archivist import Archivist, DefaultArchivist, EvictionPolicy, NaiveMemoryManager
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
from cmhh.metrics.continual import (
    average_final_performance,
    backward_transfer,
    zero_shot_forward_transfer,
)
from cmhh.models import HeuristicArtifact
from cmhh.population_builder import MemoryAwarePopulationBuilder, PopulationBuildResult
from cmhh.reporting import write_evaluation
from cmhh.retrieval import RetrievalBudget, RetrievalQuery, RetrievedItem, Retriever, RetrieverV0
from cmhh.tasks import TaskRegistry
from cmhh.tracking import ExperimentTracker, create_tracker
from cmhh.transfer import DeterministicTransferPolicy, TransferPlan, TransferRecord


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
        candidate_extractor: TopKCandidateExtractor | None = None,
        transfer_policy: DeterministicTransferPolicy | None = None,
        population_builder: MemoryAwarePopulationBuilder | None = None,
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
        self.archivist = archivist or self._default_memory_manager()
        self.candidate_extractor = candidate_extractor or TopKCandidateExtractor(top_k=self.memory_candidate_top_k)
        self.transfer_policy = transfer_policy or DeterministicTransferPolicy(
            direct_reuse_quota=self.direct_reuse_quota,
            refine_quota=self.refine_quota,
        )
        self.population_builder = population_builder or MemoryAwarePopulationBuilder(
            memory_seed_quota=self.memory_seed_quota,
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
            "pre_learning_scores": {},
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
        pre_learning_scores = {
            int(index): (None if value is None else float(value))
            for index, value in checkpoint.get("pre_learning_scores", {}).items()
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
                "archive_candidate_top_k": self.memory_candidate_top_k,
                "memory_seed_quota": self.memory_seed_quota,
                "direct_reuse_quota": self.direct_reuse_quota,
                "refine_quota": self.refine_quota,
            })

            for k in range(int(checkpoint["completed_tasks"]), len(self.stream.task_ids)):
                task = self.registry.get(self.stream.task_ids[k])

                if k not in pre_learning_scores:
                    pre_learning_scores[k] = self._run_pre_learning_probe(
                        k,
                        task,
                        selected,
                        carryover_population,
                    )
                    self._write_pre_learning_scores(pre_learning_scores)

                base_seeds = self._seed_population(task, carryover_population)
                retrieved_memory = self._retrieve_memory(task) if self._uses_persistent_memory else []
                transfer_plans = (
                    self._plan_memory_transfer(task, retrieved_memory)
                    if self._uses_persistent_memory else []
                )
                population_build = (
                    self._build_initial_population(task, transfer_plans, retrieved_memory, base_seeds)
                    if self._uses_persistent_memory
                    else PopulationBuildResult(
                        seed_population=list(base_seeds),
                        memory_context=[],
                        transfer_records=[],
                    )
                )
                carryover_validation_score = (
                    self._score_seed_population_on_validation(task, base_seeds, k)
                    if self._uses_persistent_memory else None
                )
                candidates = self.generator.generate(
                    task,
                    population_build.seed_population,
                    self.experiment.search,
                    self.seed + k,
                    memory_context=population_build.memory_context,
                )
                ranked_population, validation_summaries = self._rank_on_validation(task, candidates, k)
                best = ranked_population[0]
                transfer_records = self._annotate_transfer_records(
                    task,
                    population_build.transfer_records,
                    ranked_population,
                    best,
                    validation_summaries[best.heuristic_id],
                    carryover_validation_score,
                )
                if self._uses_population_carryover:
                    carryover_population = ranked_population
                if self._uses_persistent_memory:
                    self._log_memory_reuse_outcome(
                        task,
                        transfer_records,
                        validation_summaries[best.heuristic_id],
                        carryover_validation_score,
                    )
                    self._update_memory_transfer_feedback(
                        task,
                        transfer_records,
                        validation_summaries[best.heuristic_id],
                        carryover_validation_score,
                    )
                    self._write_memory(
                        task,
                        ranked_population,
                        validation_summaries,
                        transfer_records,
                    )
                selected[task.task_id] = best.to_dict()
                self._event("candidate_selected", task_id=task.task_id, heuristic_id=best.heuristic_id)

                # Execute read-only Retention Probe (C) on tasks T_1..T_k using Retriever & M_k
                self._run_retention_probe(k, selected, carryover_population, matrix)

                # Track task-level step metrics
                step_metrics: dict[str, float] = {
                    "stream_step": k,
                    "performance/validation_score": float(validation_summaries[best.heuristic_id].get("score", float("nan"))),
                }
                if k in matrix and k in matrix[k]:
                    step_metrics["performance/current_task_gap"] = matrix[k][k]
                if self._uses_persistent_memory:
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
                    "pre_learning_scores": pre_learning_scores,
                })
                self._write_matrix(matrix)

            metrics = self._write_metrics(matrix, pre_learning_scores)
            self.tracker.log_performance_matrix(matrix, self.stream.task_ids)
            if metrics:
                self.tracker.log_summary(metrics)
            if self._uses_persistent_memory:
                self._write_memory_diagnostics()
            return matrix
        finally:
            self.tracker.finish()

    def _run_pre_learning_probe(
        self,
        k: int,
        task,
        selected: dict[str, dict],
        carryover_population: list[HeuristicArtifact],
    ) -> float | None:
        before_hash = self._learner_state_hash(selected, carryover_population)
        artifact, retrieved_ids = self._select_probe_artifact(task, selected, carryover_population)
        self._event(
            "pre_learning_probe_started",
            task_id=task.task_id,
            task_index=k,
            heuristic_id=artifact.heuristic_id if artifact else None,
            retrieved_memory_ids=retrieved_ids,
            read_only=True,
        )
        score = None
        if artifact is not None:
            result = self.evaluator.evaluate(artifact, task, "test")
            write_evaluation(
                self.run_dir / "evaluations" / "pre_learning" / f"{task.task_id}.json",
                result,
            )
            score = result.mean_score
        self._event(
            "pre_learning_probe_completed",
            task_id=task.task_id,
            task_index=k,
            heuristic_id=artifact.heuristic_id if artifact else None,
            retrieved_memory_ids=retrieved_ids,
            mean_score=score,
            read_only=True,
        )
        after_hash = self._learner_state_hash(selected, carryover_population)
        self._assert_probe_read_only("pre_learning", task.task_id, before_hash, after_hash)
        return score

    def _run_retention_probe(
        self,
        k: int,
        selected: dict[str, dict],
        carryover_population: list[HeuristicArtifact],
        matrix: dict[int, dict[int, float]],
    ) -> None:
        before_hash = self._learner_state_hash(selected, carryover_population)
        matrix[k] = {}
        store = self._memory_store() if self._uses_persistent_memory else None
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

        after_hash = self._learner_state_hash(selected, carryover_population)
        self._assert_probe_read_only("retention", self.stream.task_ids[k], before_hash, after_hash)

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
        return self.experiment.condition in {
            "population_carryover",
            "naive_memory_sequential",
            "archivist_managed",
            "managed_archivist",
        }

    @property
    def _uses_naive_memory(self) -> bool:
        return self.experiment.condition == "naive_memory_sequential"

    @property
    def _uses_managed_memory(self) -> bool:
        return self.experiment.condition in {"archivist_managed", "managed_archivist"}

    @property
    def _uses_persistent_memory(self) -> bool:
        return self._uses_naive_memory or self._uses_managed_memory

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

    @property
    def memory_candidate_top_k(self) -> int:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.candidate_top_k or self.experiment.archive.top_k
        return self.NAIVE_MEMORY_TOP_K

    @property
    def memory_seed_quota(self) -> int:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.memory_seed_quota
        return 1

    @property
    def direct_reuse_quota(self) -> int:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.direct_reuse_quota
        return 1

    @property
    def refine_quota(self) -> int | None:
        if hasattr(self.experiment, "archive") and self.experiment.archive is not None:
            return self.experiment.archive.refine_quota
        return None

    def _default_memory_manager(self) -> Archivist:
        if self._uses_naive_memory:
            return NaiveMemoryManager(max_capacity=self.naive_memory_capacity)
        return DefaultArchivist(eviction=EvictionPolicy(max_capacity=self.naive_memory_capacity))

    def _memory_store(self) -> MemoryStore:
        return MemoryStore(self.run_dir / "memory" / "memory.jsonl")

    def _retrieve_memory(self, task) -> list[RetrievedItem]:
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
            used_in_generation=bool(retrieved),
        )
        return retrieved

    def _plan_memory_transfer(
        self,
        task,
        retrieved_memory: list[RetrievedItem],
    ) -> list[TransferPlan]:
        plans = self.transfer_policy.plan(task=task, retrieved=retrieved_memory)
        self._event(
            "memory_transfer_planned",
            task_id=task.task_id,
            plans=[plan.to_dict() for plan in plans],
        )
        return plans

    def _build_initial_population(
        self,
        task,
        transfer_plans: list[TransferPlan],
        retrieved_memory: list[RetrievedItem],
        base_seeds: list[HeuristicArtifact],
    ) -> PopulationBuildResult:
        result = self.population_builder.build(
            task=task,
            transfer_plans=transfer_plans,
            retrieved_memory=[item.unit for item in retrieved_memory],
            base_seed_population=base_seeds,
        )
        self._event(
            "memory_inserted_into_population",
            task_id=task.task_id,
            seed_heuristic_ids=[artifact.heuristic_id for artifact in result.seed_population],
            memory_context_ids=[unit.id for unit in result.memory_context],
            transfer_records=[record.to_dict() for record in result.transfer_records],
        )
        return result

    def _annotate_transfer_records(
        self,
        task,
        transfer_records: list[TransferRecord],
        ranked_population: list[HeuristicArtifact],
        selected: HeuristicArtifact,
        selected_validation_summary: dict,
        baseline_validation_score: float | None,
    ) -> list[TransferRecord]:
        if not transfer_records:
            return []

        ranked_ids = {artifact.heuristic_id for artifact in ranked_population}
        child_parent_ids = {
            parent_id
            for artifact in ranked_population
            for parent_id in artifact.parent_ids
        }
        selected_parent_ids = set(selected.parent_ids)
        selected_score = selected_validation_summary.get("score")
        delta = (
            None
            if selected_score is None or baseline_validation_score is None
            else float(selected_score) - baseline_validation_score
        )

        annotated: list[TransferRecord] = []
        for record in transfer_records:
            survived = record.artifact_id in ranked_ids
            produced_child = record.artifact_id in child_parent_ids or record.memory_id in child_parent_ids
            produced_selected_child = (
                record.artifact_id in selected_parent_ids
                or record.memory_id in selected_parent_ids
                or selected.heuristic_id == record.artifact_id
            )
            updated = replace(
                record,
                survived_selection=survived,
                produced_child=produced_child,
                produced_selected_child=produced_selected_child,
                validation_delta=delta if (survived or produced_child or produced_selected_child) else None,
            )
            annotated.append(updated)
            self._event(
                "memory_survived_selection",
                task_id=task.task_id,
                memory_id=updated.memory_id,
                artifact_id=updated.artifact_id,
                action=updated.action,
                survived_selection=updated.survived_selection,
                produced_child=updated.produced_child,
                produced_selected_child=updated.produced_selected_child,
                validation_delta=updated.validation_delta,
            )
        return annotated

    def _write_memory(
        self,
        task,
        ranked_population: list[HeuristicArtifact],
        validation_summaries: dict[str, dict],
        transfer_records: list[TransferRecord] | None = None,
    ) -> None:
        self.working_buffer.clear()
        parent_memory_by_artifact = self._parent_memory_by_artifact(transfer_records or [])
        memory_candidates = self.candidate_extractor.extract(
            task=task,
            final_population=ranked_population,
            validation_summaries=validation_summaries,
            parent_memory_by_artifact=parent_memory_by_artifact,
        )
        self._event(
            "memory_candidate_extracted",
            task_id=task.task_id,
            candidates=[candidate.to_dict() for candidate in memory_candidates],
        )
        for candidate in memory_candidates:
            if candidate.parent_memory_ids:
                self._event(
                    "memory_offspring_created",
                    task_id=task.task_id,
                    heuristic_id=candidate.artifact.heuristic_id,
                    parent_memory_ids=list(candidate.parent_memory_ids),
                    parent_artifact_ids=list(candidate.parent_artifact_ids),
                )
            self.working_buffer.add_experience(
                candidate.artifact,
                candidate.validation_summary,
                task,
                parent_memory_ids=candidate.parent_memory_ids,
            )

        store = self._memory_store()
        result = self.archivist.process_transaction(self.working_buffer, store, task)

        for memory_id in result.admitted_ids:
            self._event(
                "memory_written",
                task_id=task.task_id,
                memory_id=memory_id,
                manager="managed_archivist" if self._uses_managed_memory else "naive",
            )
            self._event(
                "memory_admitted",
                task_id=task.task_id,
                memory_id=memory_id,
                manager="managed_archivist" if self._uses_managed_memory else "naive",
            )
        for memory_id in result.protected_ids:
            self._event(
                "memory_protected",
                task_id=task.task_id,
                memory_id=memory_id,
                manager="managed_archivist",
            )
        for memory_id in result.evicted_ids:
            self._event(
                "memory_evicted",
                task_id=task.task_id,
                memory_id=memory_id,
                manager="managed_archivist" if self._uses_managed_memory else "naive",
            )
        self._event(
            "archivist_transaction_committed",
            task_id=task.task_id,
            admitted_ids=list(result.admitted_ids),
            protected_ids=list(result.protected_ids),
            evicted_ids=list(result.evicted_ids),
            manager="managed_archivist" if self._uses_managed_memory else "naive",
        )

    def _parent_memory_by_artifact(
        self,
        transfer_records: list[TransferRecord],
    ) -> dict[str, tuple[str, ...]]:
        mapping: dict[str, list[str]] = {}
        for record in transfer_records:
            if not (record.inserted_as_seed or record.included_in_context):
                continue
            mapping.setdefault(record.artifact_id, [])
            if record.memory_id not in mapping[record.artifact_id]:
                mapping[record.artifact_id].append(record.memory_id)
        return {
            artifact_id: tuple(memory_ids)
            for artifact_id, memory_ids in mapping.items()
        }

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
        transfer_records: list[TransferRecord],
        selected_validation_summary: dict,
        carryover_validation_score: float | None,
    ) -> None:
        selected_score = selected_validation_summary.get("score")
        used_records = [
            record
            for record in transfer_records
            if record.inserted_as_seed or record.included_in_context
        ]
        delta = (
            None
            if not used_records or carryover_validation_score is None or selected_score is None
            else float(selected_score) - carryover_validation_score
        )
        self._event(
            "memory_reuse_outcome",
            task_id=task.task_id,
            memory_ids=[record.memory_id for record in used_records],
            transfer_records=[record.to_dict() for record in transfer_records],
            selected_validation_score=selected_score,
            carryover_validation_score=carryover_validation_score,
            post_reuse_validation_delta=delta,
        )

    def _update_memory_transfer_feedback(
        self,
        task,
        transfer_records: list[TransferRecord],
        selected_validation_summary: dict,
        carryover_validation_score: float | None,
    ) -> None:
        used_memory_ids = [
            record.memory_id
            for record in transfer_records
            if record.inserted_as_seed or record.included_in_context
        ]
        if not used_memory_ids:
            return
        selected_score = selected_validation_summary.get("score")
        updated = self._memory_store().record_transfer_feedback(
            used_memory_ids,
            split="validation",
            task_id=task.task_id,
            selected_validation_score=None if selected_score is None else float(selected_score),
            baseline_validation_score=carryover_validation_score,
        )
        self._event(
            "memory_transfer_feedback",
            task_id=task.task_id,
            memory_ids=[item.id for item in updated],
            split="validation",
            selected_validation_score=selected_score,
            baseline_validation_score=carryover_validation_score,
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

    def _write_pre_learning_scores(self, scores: dict[int, float | None]) -> None:
        write_json_atomic(
            self.run_dir / "pre_learning_scores.json",
            {str(index): value for index, value in sorted(scores.items())},
        )

    def _select_probe_artifact(
        self,
        task,
        selected: dict[str, dict],
        carryover_population: list[HeuristicArtifact],
    ) -> tuple[HeuristicArtifact | None, list[str]]:
        retrieved_ids: list[str] = []
        if self._uses_persistent_memory:
            query = RetrievalQuery(
                problem=task.problem,
                task_id=task.task_id,
                task_signature=self._task_signature(task),
            )
            retrieved = self.retriever.retrieve(
                query,
                self._memory_store().load_all(),
                RetrievalBudget(top_k=1),
            )
            retrieved_ids = [item.unit.id for item in retrieved]
            if retrieved:
                artifact = self._artifact_from_memory(retrieved[0].unit, task.task_id)
                if artifact is not None:
                    return artifact, retrieved_ids

        compatible = [
            artifact
            for artifact in carryover_population
            if artifact.problem == task.problem and artifact.code_path.exists()
        ]
        if compatible:
            return compatible[0], retrieved_ids

        if task.task_id in selected:
            return _artifact_from_dict(selected[task.task_id]), retrieved_ids
        return None, retrieved_ids

    def _artifact_from_memory(self, unit: MemoryUnit, task_id: str) -> HeuristicArtifact | None:
        if not unit.evidence.source_artifacts:
            return None
        code_path = Path(unit.evidence.source_artifacts[0])
        if not code_path.exists():
            return None
        return HeuristicArtifact(
            heuristic_id=unit.scope.heuristic_family or code_path.stem,
            problem=unit.scope.problem,
            code_path=code_path,
            code_hash=unit.evidence.code_hashes[0] if unit.evidence.code_hashes else "",
            task_id=task_id,
        )

    def _learner_state_hash(
        self,
        selected: dict[str, dict],
        carryover_population: list[HeuristicArtifact],
    ) -> str:
        memory = (
            [item.to_dict() for item in self._memory_store().load_all()]
            if self._uses_persistent_memory
            else []
        )
        payload = {
            "selected": selected,
            "carryover_population": [artifact.to_dict() for artifact in carryover_population],
            "memory": memory,
        }
        encoded = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _assert_probe_read_only(
        self,
        probe_name: str,
        task_id: str,
        before_hash: str,
        after_hash: str,
    ) -> None:
        if before_hash != after_hash:
            raise RuntimeError(
                f"{probe_name} probe mutated learner-visible state for {task_id}"
            )

    def _write_metrics(
        self,
        matrix: dict[int, dict[int, float]],
        pre_learning_scores: dict[int, float | None],
    ) -> dict[str, Any]:
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
                metrics["forward_transfer"] = zero_shot_forward_transfer(
                    pre_learning_scores,
                    self.cold_start_scores,
                    count,
                )
                metrics["forward_transfer_source"] = "pre_learning_probe"
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
