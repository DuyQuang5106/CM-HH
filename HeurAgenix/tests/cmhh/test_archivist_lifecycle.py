from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cmhh.archivist import (
    AdmissionCriteria,
    ArchivistTransactionResult,
    CapacityOverflowError,
    DefaultArchivist,
    EvictionPolicy,
    ProtectionPolicy,
)
from cmhh.memory import MemoryStore, WorkingBuffer
from cmhh.models import HeuristicArtifact
from cmhh.tasks import TaskSpec


class DummyTask:
    task_id = "tsp_20"
    problem = "tsp"
    size_tier = "n20"
    distribution = "uniform"


class DummyArtifact:
    def __init__(self, heuristic_id: str) -> None:
        self.heuristic_id = heuristic_id
        self.code_path = Path(f"/tmp/{heuristic_id}.py")
        self.code_hash = f"hash_{heuristic_id}"
        self.generation = 1


class ArchivistLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = DummyTask()

    def test_admission_gate_selects_top_elite_candidates(self) -> None:
        archivist = DefaultArchivist(
            admission=AdmissionCriteria(elite_validation_rank=2),
            eviction=EvictionPolicy(max_capacity=10),
        )
        buffer = WorkingBuffer()
        for i in range(5):
            buffer.add_experience(DummyArtifact(f"h_{i}"), {"score": float(i)}, self.task)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = MemoryStore(Path(tmp_dir) / "memory.jsonl")
            result = archivist.process_transaction(buffer, store, self.task)

            self.assertEqual(2, len(result.admitted_ids))
            items = store.load_all()
            self.assertEqual(2, len(items))
            scores = {item.metadata.validation_score for item in items}
            self.assertEqual({4.0, 3.0}, scores)

    def test_protection_policy_marks_best_candidate_protected(self) -> None:
        archivist = DefaultArchivist(
            admission=AdmissionCriteria(elite_validation_rank=3),
            protection=ProtectionPolicy(protect_best_per_task=True),
        )
        buffer = WorkingBuffer()
        buffer.add_experience(DummyArtifact("h_best"), {"score": 10.0}, self.task)
        buffer.add_experience(DummyArtifact("h_other"), {"score": 5.0}, self.task)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = MemoryStore(Path(tmp_dir) / "memory.jsonl")
            result = archivist.process_transaction(buffer, store, self.task)

            self.assertEqual(1, len(result.protected_ids))
            items = store.load_all()
            protected_items = [item for item in items if item.metadata.protected]
            self.assertEqual(1, len(protected_items))
            self.assertEqual("h_best", protected_items[0].artifact_id)

    def test_capacity_overflow_error_when_protected_items_exceed_capacity(self) -> None:
        archivist = DefaultArchivist(
            admission=AdmissionCriteria(elite_validation_rank=1),
            protection=ProtectionPolicy(protect_best_per_task=True),
            eviction=EvictionPolicy(max_capacity=1),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = MemoryStore(Path(tmp_dir) / "memory.jsonl")

            # Task 1 transaction
            buffer1 = WorkingBuffer()
            buffer1.add_experience(DummyArtifact("h_t1"), {"score": 10.0}, self.task)
            archivist.process_transaction(buffer1, store, self.task)

            # Task 2 transaction (protected count becomes 2 > capacity 1)
            task2 = DummyTask()
            task2.task_id = "tsp_50"
            buffer2 = WorkingBuffer()
            buffer2.add_experience(DummyArtifact("h_t2"), {"score": 12.0}, task2)

            with self.assertRaises(CapacityOverflowError):
                archivist.process_transaction(buffer2, store, task2)

    def test_eviction_removes_lowest_utility_non_protected_items(self) -> None:
        archivist = DefaultArchivist(
            admission=AdmissionCriteria(elite_validation_rank=3),
            protection=ProtectionPolicy(protect_best_per_task=False),
            eviction=EvictionPolicy(max_capacity=2),
        )
        buffer = WorkingBuffer()
        buffer.add_experience(DummyArtifact("h_low"), {"score": 1.0}, self.task)
        buffer.add_experience(DummyArtifact("h_mid"), {"score": 5.0}, self.task)
        buffer.add_experience(DummyArtifact("h_high"), {"score": 10.0}, self.task)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = MemoryStore(Path(tmp_dir) / "memory.jsonl")
            result = archivist.process_transaction(buffer, store, self.task)

            self.assertEqual(3, len(result.admitted_ids))
            self.assertEqual(1, len(result.evicted_ids))
            items = store.load_all()
            self.assertEqual(2, len(items))
            remaining_ids = {item.artifact_id for item in items}
            self.assertNotIn("h_low", remaining_ids)
            self.assertIn("h_high", remaining_ids)


if __name__ == "__main__":
    unittest.main()
