from __future__ import annotations

from typing import Sequence

from cmhh.memory import MemoryUnit
from cmhh.retrieval.base import RetrievalBudget, RetrievalQuery, RetrievedItem, Retriever


class RetrieverV0(Retriever):
    """Retriever v0 implementation for CMHH experiments.
    
    Performs Stage 1 structural compatibility filtering followed by Stage 2 structural
    similarity calculation and Stage 3 min-max utility normalization.
    """

    def __init__(self, alpha: float = 0.7, beta: float = 0.3) -> None:
        self.alpha = alpha
        self.beta = beta

    def retrieve(
        self,
        query: RetrievalQuery,
        memory: Sequence[MemoryUnit],
        budget: RetrievalBudget | None = None,
    ) -> list[RetrievedItem]:
        budget = budget or RetrievalBudget()
        
        # Stage 1: Hard structural compatibility filter
        compatible: list[tuple[float, float, MemoryUnit]] = []
        for unit in memory:
            if not self._is_structurally_compatible(query, unit):
                continue
            sim = self._structural_similarity(query, unit)
            if sim > 0:
                raw_u = self._raw_utility_score(unit)
                compatible.append((sim, raw_u, unit))

        if not compatible:
            return []

        # Stage 3: Normalize utility across compatible candidate pool
        raw_utilities = [item[1] for item in compatible]
        u_min, u_max = min(raw_utilities), max(raw_utilities)

        scored: list[tuple[float, MemoryUnit]] = []
        for sim, raw_u, unit in compatible:
            u_norm = (raw_u - u_min) / (u_max - u_min) if u_max > u_min else 0.5
            sim_norm = min(1.0, sim / 2.75) if sim > 0 else 0.0
            score = self.alpha * sim_norm + self.beta * u_norm
            scored.append((score, unit))

        # Sort descending by score, tie-break by unit.id
        sorted_items = sorted(scored, key=lambda item: (-item[0], item[1].id))
        top_k_items = sorted_items[: budget.top_k]

        return [
            RetrievedItem(unit=unit, score=score, rank=index + 1)
            for index, (score, unit) in enumerate(top_k_items)
        ]

    def _is_structurally_compatible(self, query: RetrievalQuery, unit: MemoryUnit) -> bool:
        if unit.scope.problem and unit.scope.problem.lower() != query.problem.lower():
            return False
        return True

    def _structural_similarity(self, query: RetrievalQuery, unit: MemoryUnit) -> float:
        sim = 0.0
        if unit.scope.problem.lower() == query.problem.lower():
            sim += 1.0
        for key, value in query.task_signature.items():
            if unit.key.task_signature.get(key) == value:
                sim += 0.5
        if query.problem.lower() in unit.key.applicability.lower():
            sim += 0.25
        return sim

    def _raw_utility_score(self, unit: MemoryUnit) -> float:
        val_after = unit.evidence.validation_after
        score = float(val_after.get("score", 0.0)) if isinstance(val_after, dict) else 0.0
        if unit.policy.retrieval_count > 0:
            success_rate = unit.policy.success_count / unit.policy.retrieval_count
            score += 0.1 * success_rate
        return score
