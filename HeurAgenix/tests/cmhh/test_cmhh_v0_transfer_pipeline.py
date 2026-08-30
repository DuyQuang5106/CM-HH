from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cmhh.candidate_extractor import TopKCandidateExtractor
from cmhh.memory import (
    MemoryEvidence,
    MemoryKey,
    MemoryScope,
    MemoryStore,
    MemoryValue,
    create_memory_unit,
)
from cmhh.models import HeuristicArtifact
from cmhh.population_builder import MemoryAwarePopulationBuilder
from cmhh.retrieval import RetrievedItem
from cmhh.tasks import TaskMetric, TaskReference, TaskSpec, TaskSplits
from cmhh.transfer import DeterministicTransferPolicy


def _task(root: Path, task_id: str = "tsp_50") -> TaskSpec:
    split = root / "split"
    split.mkdir(exist_ok=True)
    return TaskSpec(
        task_id=task_id,
        problem="tsp",
        size_tier="50",
        distribution="uniform",
        splits=TaskSplits(split, split, split, split),
        reference=TaskReference("optimal"),
        metric=TaskMetric("relative_gap", "minimize"),
        implemented_in_heuragenix=True,
        baseline_pool={"heuristic_dir": "basic_heuristics", "seed_heuristics": ["seed"]},
        metadata={"nodes": 50},
    )


def _artifact(root: Path, heuristic_id: str, parent_ids: tuple[str, ...] = ()) -> HeuristicArtifact:
    path = root / f"{heuristic_id}.py"
    path.write_text("def select_next_node(*args, **kwargs):\n    return 0\n", encoding="utf-8")
    return HeuristicArtifact(
        heuristic_id=heuristic_id,
        problem="tsp",
        code_path=path,
        code_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        parent_ids=parent_ids,
        task_id="tsp_50",
    )


def _memory_item(root: Path, memory_id_hint: str):
    artifact = _artifact(root, f"h_{memory_id_hint}")
    return create_memory_unit(
        scope=MemoryScope(
            problem="tsp",
            task_id="tsp_20",
            heuristic_family=artifact.heuristic_id,
        ),
        key=MemoryKey(
            applicability="TSP uniform memory",
            task_signature={"problem": "tsp", "size_tier": "20", "distribution": "uniform"},
        ),
        value=MemoryValue(type="procedural_skill", content=f"memory {memory_id_hint}"),
        evidence=MemoryEvidence(
            source_artifacts=(str(artifact.code_path),),
            validation_after={"score": -0.1},
            code_hashes=(artifact.code_hash,),
        ),
    )


class CMHHV0TransferPipelineTests(unittest.TestCase):
    def test_candidate_extractor_uses_deterministic_top_k(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = _task(root)
            h1 = _artifact(root, "h1")
            h2 = _artifact(root, "h2")
            h3 = _artifact(root, "h3")

            extractor = TopKCandidateExtractor(top_k=2)
            candidates = extractor.extract(
                task=task,
                final_population=[h1, h2, h3],
                validation_summaries={
                    "h1": {"score": -0.2},
                    "h2": {"score": -0.1},
                    "h3": {"score": -0.1},
                },
            )

            self.assertEqual(["h2", "h3"], [item.artifact.heuristic_id for item in candidates])
            self.assertEqual([1, 2], [item.rank for item in candidates])

    def test_candidate_extractor_preserves_parent_memory_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = _task(root)
            child = _artifact(root, "child", parent_ids=("memory_seed_artifact",))

            candidates = TopKCandidateExtractor(top_k=1).extract(
                task=task,
                final_population=[child],
                validation_summaries={"child": {"score": -0.1}},
                parent_memory_by_artifact={"memory_seed_artifact": ("mem_parent",)},
            )

            self.assertEqual(("mem_parent",), candidates[0].parent_memory_ids)

    def test_transfer_policy_and_population_builder_make_reuse_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = _task(root)
            m1 = _memory_item(root, "m1")
            m2 = _memory_item(root, "m2")
            base = _artifact(root, "fresh_seed")

            retrieved = [
                RetrievedItem(unit=m1, score=0.9, rank=1),
                RetrievedItem(unit=m2, score=0.8, rank=2),
            ]
            plans = DeterministicTransferPolicy(direct_reuse_quota=1).plan(
                task=task,
                retrieved=retrieved,
            )
            self.assertEqual(["direct_reuse", "refine"], [plan.action for plan in plans])

            result = MemoryAwarePopulationBuilder(memory_seed_quota=1).build(
                task=task,
                transfer_plans=plans,
                retrieved_memory=[m1, m2],
                base_seed_population=[base],
            )

            self.assertEqual(m1.artifact_id, result.seed_population[0].heuristic_id)
            self.assertEqual("fresh_seed", result.seed_population[1].heuristic_id)
            self.assertEqual([m1.id, m2.id], [unit.id for unit in result.memory_context])
            self.assertTrue(result.transfer_records[0].inserted_as_seed)
            self.assertTrue(result.transfer_records[1].included_in_context)

    def test_transfer_feedback_is_validation_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = MemoryStore(root / "memory.jsonl")
            item = _memory_item(root, "feedback")
            store.upsert(item)

            with self.assertRaises(ValueError):
                store.record_transfer_feedback(
                    [item.id],
                    split="test",
                    task_id="tsp_50",
                    selected_validation_score=-0.05,
                    baseline_validation_score=-0.10,
                )

            updated = store.record_transfer_feedback(
                [item.id],
                split="validation",
                task_id="tsp_50",
                selected_validation_score=-0.05,
                baseline_validation_score=-0.10,
            )
            self.assertEqual(1, updated[0].metadata.retrieval_count)
            self.assertEqual(1, updated[0].metadata.success_count)
            self.assertEqual("tsp_50", updated[0].metadata.transfer_history[0]["task_id"])

    def test_annotate_transfer_records_survival_and_descendants(self) -> None:
        from cmhh.transfer import TransferRecord
        from cmhh.runner import StreamRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = _task(root)
            seed_art = _artifact(root, "m1_art")
            child_art = _artifact(root, "child_art", parent_ids=("m1_art",))
            other_art = _artifact(root, "other_art")

            records = [
                TransferRecord(
                    memory_id="mem_1",
                    artifact_id="m1_art",
                    action="direct_reuse",
                    inserted_as_seed=True,
                ),
                TransferRecord(
                    memory_id="mem_2",
                    artifact_id="m2_art",
                    action="refine",
                    included_in_context=True,
                ),
            ]

            runner = object.__new__(StreamRunner)
            runner.events = []
            runner._event = lambda *args, **kwargs: None

            annotated = runner._annotate_transfer_records(
                task=task,
                transfer_records=records,
                ranked_population=[child_art, seed_art],
                selected=child_art,
                selected_validation_summary={"score": -0.05},
                baseline_validation_score=-0.10,
            )

            self.assertEqual(2, len(annotated))
            # mem_1 seed survived and produced the selected child
            self.assertTrue(annotated[0].survived_selection)
            self.assertTrue(annotated[0].produced_child)
            self.assertTrue(annotated[0].produced_selected_child)
            self.assertAlmostEqual(0.05, annotated[0].validation_delta)

            # mem_2 was not retained in population and produced no children
            self.assertFalse(annotated[1].survived_selection)
            self.assertFalse(annotated[1].produced_child)
            self.assertFalse(annotated[1].produced_selected_child)
            self.assertIsNone(annotated[1].validation_delta)


if __name__ == "__main__":
    unittest.main()

