from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cmhh.memory import (
    ApplicabilityDescriptor,
    KnowledgeAbstraction,
    MemoryItem,
    MemoryKey,
    MemoryMetadata,
    MemoryScope,
    MemoryStore,
    MemoryUnit,
    MemoryValue,
    WorkingBuffer,
    create_memory_unit,
)
from cmhh.retrieval import RetrievalBudget, RetrievalQuery, RetrieverV0


class Memory3LayerTests(unittest.TestCase):
    def test_memory_item_3layer_serialization(self) -> None:
        item = MemoryItem(
            id="mem_test_123",
            artifact_id="h_euc_1",
            code_path="/tmp/h_euc_1.py",
            code_hash="sha256_hash",
            applicability=ApplicabilityDescriptor(
                problem_family="tsp",
                task_id="tsp_100",
                size_tier="n100",
                distribution="euclidean_uniform",
                heuristic_interface="tsp_constructive_v1",
                task_signature={"nodes": 100},
            ),
            abstraction=KnowledgeAbstraction(
                abstraction_type="procedural_skill",
                summary="Constructive nearest neighbor with local 2-opt refinement",
            ),
            metadata=MemoryMetadata(
                origin_task_id="tsp_100",
                origin_generation=2,
                validation_score=-95.5,
                validation_summary={"score": -95.5, "objective": 95.5},
            ),
            schema_version=1,
        )
        serialized = item.to_dict()
        self.assertEqual(1, serialized["schema_version"])
        self.assertEqual("tsp_constructive_v1", serialized["applicability"]["heuristic_interface"])

        deserialized = MemoryItem.from_dict(serialized)
        self.assertEqual(item.id, deserialized.id)
        self.assertEqual(item.applicability.heuristic_interface, deserialized.applicability.heuristic_interface)
        self.assertEqual(item.metadata.validation_score, deserialized.metadata.validation_score)

    def test_legacy_memory_unit_upgrade(self) -> None:
        legacy = create_memory_unit(
            scope=MemoryScope(problem="tsp", task_id="tsp_20", heuristic_family="h1"),
            key=MemoryKey(
                applicability="TSP n20 uniform",
                task_signature={"problem": "tsp", "size_tier": "n20"},
            ),
            value=MemoryValue(type="procedural_skill", content="legacy unit"),
            evidence=None,
        )
        serialized = legacy.to_dict()
        upgraded = MemoryItem.from_dict(serialized)
        self.assertEqual(1, upgraded.schema_version)
        self.assertEqual("tsp", upgraded.applicability.problem_family)
        self.assertEqual("tsp_20", upgraded.applicability.task_id)

    def test_memory_store_persists_3layer_items(self) -> None:
        item = MemoryItem(
            id="mem_store_1",
            artifact_id="h1",
            code_path="/tmp/h1.py",
            code_hash="hash1",
            applicability=ApplicabilityDescriptor(problem_family="tsp", task_id="tsp_50"),
            abstraction=KnowledgeAbstraction(summary="test skill"),
            metadata=MemoryMetadata(origin_task_id="tsp_50", validation_score=-50.0),
            schema_version=1,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "memory.jsonl"
            store = MemoryStore(store_path)
            store.upsert(item)

            loaded = store.load_all()
            self.assertEqual(1, len(loaded))
            self.assertEqual(1, loaded[0].schema_version)
            self.assertEqual("mem_store_1", loaded[0].id)
            self.assertEqual(-50.0, loaded[0].metadata.validation_score)


class WorkingBufferTests(unittest.TestCase):
    def test_working_buffer_capacity_and_operations(self) -> None:
        buffer = WorkingBuffer(capacity=3)
        self.assertEqual(0, buffer.size())

        class DummyTask:
            task_id = "tsp_20"
            problem = "tsp"

        class DummyArtifact:
            heuristic_id = "h1"

        task = DummyTask()
        for i in range(5):
            artifact = DummyArtifact()
            artifact.heuristic_id = f"h_{i}"
            buffer.add_experience(artifact, {"score": -10.0 * i}, task)

        self.assertEqual(3, buffer.size())
        experiences = buffer.get_experiences()
        self.assertEqual("h_2", experiences[0]["artifact"].heuristic_id)
        self.assertEqual("h_4", experiences[-1]["artifact"].heuristic_id)

        buffer.clear()
        self.assertEqual(0, buffer.size())


if __name__ == "__main__":
    unittest.main()
