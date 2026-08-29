from __future__ import annotations

from cmhh.archivist.base import Archivist, ArchivistTransactionResult
from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryScope,
    MemoryStore,
    MemoryValue,
    WorkingBuffer,
    create_memory_unit,
)
from cmhh.tasks import TaskSpec


class NaiveMemoryManager(Archivist):
    """Uncurated persistent memory baseline.

    This intentionally avoids managed-memory behavior: no protection, no
    selective admission gate, no distillation, and no utility update. When
    capacity is bounded, newer records overwrite older records deterministically.
    """

    def __init__(self, max_capacity: int | None = 20) -> None:
        self.max_capacity = max_capacity

    def process_transaction(
        self,
        working_buffer: WorkingBuffer,
        memory_store: MemoryStore,
        task: TaskSpec,
    ) -> ArchivistTransactionResult:
        admitted_ids: list[str] = []
        for exp in working_buffer.get_experiences():
            artifact = exp["artifact"]
            summary = exp["validation_summary"]
            unit = create_memory_unit(
                scope=MemoryScope(
                    problem=task.problem,
                    task_id=task.task_id,
                    heuristic_family=artifact.heuristic_id,
                    generation=getattr(artifact, "generation", 0),
                ),
                key=MemoryKey(
                    applicability=f"Uncurated {task.problem} memory from {task.task_id}",
                    task_signature={
                        "problem": task.problem,
                        "task_id": task.task_id,
                        "size_tier": task.size_tier,
                        "distribution": task.distribution,
                    },
                ),
                value=MemoryValue(
                    type="trajectory",
                    content=f"Raw selected candidate {artifact.heuristic_id} from {task.task_id}",
                ),
                evidence=MemoryEvidence(
                    source_artifacts=(str(artifact.code_path),),
                    validation_after=summary,
                    code_hashes=(artifact.code_hash,),
                ),
            )
            memory_store.upsert(unit)
            admitted_ids.append(unit.id)

        evicted_ids: list[str] = []
        if self.max_capacity is not None:
            items = memory_store.load_all()
            if len(items) > self.max_capacity:
                kept = sorted(
                    items,
                    key=lambda item: (item.metadata.created_at, item.id),
                    reverse=True,
                )[: self.max_capacity]
                kept_ids = {item.id for item in kept}
                evicted_ids = [item.id for item in items if item.id not in kept_ids]
                memory_store.save_all(kept)

        return ArchivistTransactionResult(
            admitted_ids=tuple(admitted_ids),
            evicted_ids=tuple(evicted_ids),
            protected_ids=(),
        )
