from __future__ import annotations

from typing import Sequence

from cmhh.archivist.base import (
    AdmissionCriteria,
    Archivist,
    ArchivistTransactionResult,
    CapacityOverflowError,
    EvictionPolicy,
    ProtectionPolicy,
)
from cmhh.memory import (
    ApplicabilityDescriptor,
    KnowledgeAbstraction,
    MemoryEvidence,
    MemoryItem,
    MemoryKey,
    MemoryMetadata,
    MemoryScope,
    MemoryStore,
    MemoryValue,
    WorkingBuffer,
    create_memory_unit,
)
from cmhh.tasks import TaskSpec


class DefaultArchivist(Archivist):
    """Default Archivist lifecycle manager for CMHH.
    
    Implements:
    - Admission filtering based on validation performance ranking.
    - Anchor protection for top-performing heuristic per task.
    - Capacity invariant check (raising CapacityOverflowError if protected items > capacity).
    - Eviction ranking based on utility and recency.
    """

    def __init__(
        self,
        admission: AdmissionCriteria | None = None,
        protection: ProtectionPolicy | None = None,
        eviction: EvictionPolicy | None = None,
    ) -> None:
        self.admission = admission or AdmissionCriteria()
        self.protection = protection or ProtectionPolicy()
        self.eviction = eviction or EvictionPolicy()

    def process_transaction(
        self,
        working_buffer: WorkingBuffer,
        memory_store: MemoryStore,
        task: TaskSpec,
    ) -> ArchivistTransactionResult:
        experiences = working_buffer.get_experiences()
        if not experiences:
            return ArchivistTransactionResult()

        # Step 1: Admission - sort experiences by validation score descending
        sorted_experiences = sorted(
            experiences,
            key=lambda exp: exp["validation_summary"].get("score", float("-inf")),
            reverse=True,
        )
        admitted_experiences = sorted_experiences[: self.admission.elite_validation_rank]

        admitted_items: list[MemoryItem] = []
        protected_ids: list[str] = []
        admitted_ids: list[str] = []

        for rank, exp in enumerate(admitted_experiences):
            artifact = exp["artifact"]
            summary = exp["validation_summary"]
            is_best = (rank == 0) and self.protection.protect_best_per_task

            unit = create_memory_unit(
                scope=MemoryScope(
                    problem=task.problem,
                    task_id=task.task_id,
                    heuristic_family=artifact.heuristic_id,
                    generation=getattr(artifact, "generation", 0),
                ),
                key=MemoryKey(
                    applicability=f"Uncurated {task.problem} memory from {task.task_id}",
                    task_signature={"problem": task.problem, "task_id": task.task_id},
                ),
                value=MemoryValue(
                    type="procedural_skill",
                    content=f"Heuristic {artifact.heuristic_id} on {task.task_id}",
                ),
                evidence=MemoryEvidence(
                    source_artifacts=(str(artifact.code_path),),
                    validation_after=summary,
                    code_hashes=(artifact.code_hash,),
                ),
                parent_memory_ids=tuple(exp.get("parent_memory_ids", ())),
            )
            
            if is_best:
                metadata = MemoryMetadata(
                    origin_task_id=unit.metadata.origin_task_id,
                    origin_generation=unit.metadata.origin_generation,
                    parent_ids=unit.metadata.parent_ids,
                    validation_score=unit.metadata.validation_score,
                    validation_summary=unit.metadata.validation_summary,
                    retrieval_count=unit.metadata.retrieval_count,
                    success_count=unit.metadata.success_count,
                    transfer_history=unit.metadata.transfer_history,
                    protected=True,
                    created_at=unit.metadata.created_at,
                    updated_at=unit.metadata.updated_at,
                )
                unit = MemoryItem(
                    id=unit.id,
                    artifact_id=unit.artifact_id,
                    code_path=unit.code_path,
                    code_hash=unit.code_hash,
                    applicability=unit.applicability,
                    abstraction=unit.abstraction,
                    metadata=metadata,
                    schema_version=1,
                )
                protected_ids.append(unit.id)

            memory_store.upsert(unit)
            admitted_items.append(unit)
            admitted_ids.append(unit.id)

        # Step 2: Capacity check & Eviction
        all_items = memory_store.load_all()
        evicted_ids: list[str] = []

        if self.eviction.max_capacity is not None and self.eviction.max_capacity > 0:
            protected_count = sum(1 for item in all_items if item.metadata.protected)
            if protected_count > self.eviction.max_capacity:
                raise CapacityOverflowError(
                    f"Protected memory anchor count ({protected_count}) exceeds "
                    f"maximum capacity ({self.eviction.max_capacity})"
                )

            if len(all_items) > self.eviction.max_capacity:
                protected_items = [item for item in all_items if item.metadata.protected]
                non_protected_items = [item for item in all_items if not item.metadata.protected]

                ranked_non_protected = sorted(
                    non_protected_items,
                    key=lambda item: (
                        item.metadata.validation_score,
                        item.metadata.created_at,
                        item.id,
                    ),
                    reverse=True,
                )
                allowed_non_protected = self.eviction.max_capacity - len(protected_items)
                kept_non_protected = ranked_non_protected[:allowed_non_protected]
                evicted_non_protected = ranked_non_protected[allowed_non_protected:]

                evicted_ids = [item.id for item in evicted_non_protected]
                kept_all = protected_items + kept_non_protected
                memory_store.save_all(kept_all)

        return ArchivistTransactionResult(
            admitted_ids=tuple(admitted_ids),
            evicted_ids=tuple(evicted_ids),
            protected_ids=tuple(protected_ids),
        )
