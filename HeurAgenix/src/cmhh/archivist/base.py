from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from cmhh.memory import MemoryItem, MemoryStore, WorkingBuffer
from cmhh.tasks import TaskSpec


class CapacityOverflowError(RuntimeError):
    """Raised when the number of protected anchor items exceeds maximum memory capacity."""
    pass


@dataclass(frozen=True)
class AdmissionCriteria:
    elite_validation_rank: int = 3
    min_validation_score: float | None = None


@dataclass(frozen=True)
class ProtectionPolicy:
    protect_best_per_task: bool = True


@dataclass(frozen=True)
class EvictionPolicy:
    max_capacity: int = 20
    utility_weight: float = 0.7
    recency_weight: float = 0.3


@dataclass(frozen=True)
class ArchivistTransactionResult:
    admitted_ids: tuple[str, ...] = ()
    evicted_ids: tuple[str, ...] = ()
    protected_ids: tuple[str, ...] = ()


class Archivist(ABC):
    """Abstract base class for CMHH Archivist lifecycle management.
    
    The Archivist is a selective consolidation gate governing:
    - admission of working experiences into long-term memory
    - distillation of raw trajectories into structured memory units
    - protection of key task anchor heuristics
    - utility and evidence updates
    - capacity management and eviction of low-value memories
    """

    @abstractmethod
    def process_transaction(
        self,
        working_buffer: WorkingBuffer,
        memory_store: MemoryStore,
        task: TaskSpec,
    ) -> ArchivistTransactionResult:
        """Process recent search experiences in working_buffer and update memory_store."""
        pass
