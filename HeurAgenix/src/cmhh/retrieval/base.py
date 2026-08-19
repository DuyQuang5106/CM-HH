from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from cmhh.memory import MemoryUnit


@dataclass(frozen=True)
class RetrievalQuery:
    problem: str
    task_id: str
    task_signature: dict[str, Any] = field(default_factory=dict)
    heuristic_interface: str | None = None


@dataclass(frozen=True)
class RetrievalBudget:
    top_k: int = 5
    token_budget: int | None = None


@dataclass(frozen=True)
class RetrievedItem:
    unit: MemoryUnit
    score: float
    rank: int


class Retriever(ABC):
    """Abstract base class for all CMHH Retrievers.
    
    The Retriever is an independent selection component that answers:
    Given a current retrieval query q and long-term memory M, which stored memory items
    are most relevant and useful now?
    """

    @abstractmethod
    def retrieve(
        self,
        query: RetrievalQuery,
        memory: Sequence[MemoryUnit],
        budget: RetrievalBudget | None = None,
    ) -> list[RetrievedItem]:
        """Select and rank memory items for the given query."""
        pass
