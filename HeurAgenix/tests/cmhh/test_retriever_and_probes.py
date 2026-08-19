from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryScope,
    MemoryUnit,
    MemoryValue,
    create_memory_unit,
)
from cmhh.retrieval import RetrievalBudget, RetrievalQuery, RetrieverV0


class RetrieverV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.retriever = RetrieverV0(alpha=0.7, beta=0.3)
        self.unit_tsp_n20 = create_memory_unit(
            scope=MemoryScope(problem="tsp", task_id="tsp_20", heuristic_family="h1"),
            key=MemoryKey(
                applicability="TSP n20 uniform",
                task_signature={"problem": "tsp", "size_tier": "n20"},
            ),
            value=MemoryValue(type="trajectory", content="TSP 20 heuristic"),
            evidence=MemoryEvidence(validation_after={"score": 0.8}),
        )
        self.unit_tsp_n100 = create_memory_unit(
            scope=MemoryScope(problem="tsp", task_id="tsp_100", heuristic_family="h2"),
            key=MemoryKey(
                applicability="TSP n100 uniform",
                task_signature={"problem": "tsp", "size_tier": "n100"},
            ),
            value=MemoryValue(type="trajectory", content="TSP 100 heuristic"),
            evidence=MemoryEvidence(validation_after={"score": 0.95}),
        )
        self.unit_cvrp = create_memory_unit(
            scope=MemoryScope(problem="cvrp", task_id="cvrp_50", heuristic_family="h3"),
            key=MemoryKey(
                applicability="CVRP 50",
                task_signature={"problem": "cvrp"},
            ),
            value=MemoryValue(type="trajectory", content="CVRP heuristic"),
            evidence=MemoryEvidence(validation_after={"score": 0.99}),
        )

    def test_structural_filtering_excludes_incompatible_problem(self) -> None:
        query = RetrievalQuery(
            problem="tsp",
            task_id="tsp_20",
            task_signature={"problem": "tsp", "size_tier": "n20"},
        )
        retrieved = self.retriever.retrieve(
            query,
            [self.unit_tsp_n20, self.unit_cvrp],
            RetrievalBudget(top_k=5),
        )
        self.assertEqual(1, len(retrieved))
        self.assertEqual(self.unit_tsp_n20.id, retrieved[0].unit.id)

    def test_top_k_budget_limit(self) -> None:
        query = RetrievalQuery(
            problem="tsp",
            task_id="tsp_20",
            task_signature={"problem": "tsp"},
        )
        retrieved = self.retriever.retrieve(
            query,
            [self.unit_tsp_n20, self.unit_tsp_n100],
            RetrievalBudget(top_k=1),
        )
        self.assertEqual(1, len(retrieved))

    def test_ranking_incorporates_similarity_and_utility(self) -> None:
        query = RetrievalQuery(
            problem="tsp",
            task_id="tsp_100",
            task_signature={"problem": "tsp", "size_tier": "n100"},
        )
        retrieved = self.retriever.retrieve(
            query,
            [self.unit_tsp_n20, self.unit_tsp_n100],
            RetrievalBudget(top_k=2),
        )
        self.assertEqual(2, len(retrieved))
        # tsp_n100 matches task_signature ("size_tier": "n100"), so it should rank first
        self.assertEqual(self.unit_tsp_n100.id, retrieved[0].unit.id)
        self.assertEqual(1, retrieved[0].rank)


if __name__ == "__main__":
    unittest.main()
