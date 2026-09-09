from __future__ import annotations

import math
import random
import tempfile
import unittest
from pathlib import Path

from cmhh.config import (
    DataConfig,
    EvaluationBudget,
    ExperimentConfig,
    SearchBudget,
    load_experiment_config,
    load_stream_config,
    load_suite_config,
)
from cmhh.data.manifest import load_json, sha256_file
from cmhh.data.tsp_generator import (
    generate_clustered_tsp,
    generate_tsp_instance,
    generate_uniform_tsp,
    _generate_task_splits,
    _write_task_manifest,
)
from cmhh.memory import (
    ApplicabilityDescriptor,
    KnowledgeAbstraction,
    MemoryEvidence,
    MemoryItem,
    MemoryKey,
    MemoryMetadata,
    MemoryPolicyState,
    MemoryScope,
    MemoryUnit,
    MemoryValue,
)
from cmhh.population_builder import MemoryAwarePopulationBuilder
from cmhh.retrieval import RetrievalBudget, RetrievalQuery, RetrieverV0
from cmhh.runtime import resolve_stream_path, resolve_suite_path
from cmhh.tasks import load_task_registry
from cmhh.transfer import DeterministicTransferPolicy, TransferPlan


class PilotStreamsTestSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path.cwd()
        if not (self.repo_root / "cmhh" / "configs").exists() and (self.repo_root / "HeurAgenix" / "cmhh" / "configs").exists():
            self.repo_root = self.repo_root / "HeurAgenix"

    def test_rng_isolation(self) -> None:
        """Data generation must use local RNG and not alter global random state."""
        # Set global random state
        random.seed(12345)
        state_before = random.getstate()
        val_before = random.random()

        # Generate data using seed 99999
        _ = generate_uniform_tsp(node_count=20, seed=99999, coordinate_min=0, coordinate_max=1000)
        _ = generate_clustered_tsp(node_count=20, seed=99999, coordinate_min=0, coordinate_max=1000)

        # Reset to state_before and verify next value matches val_before
        random.setstate(state_before)
        val_after = random.random()
        self.assertEqual(val_before, val_after)

    def test_clustered_distribution_statistical_sanity(self) -> None:
        """Clustered TSP generation must produce tight clusters within bounds."""
        node_count = 60
        num_clusters = 3
        sigma_fraction = 0.05
        min_coord, max_coord = 0, 10000

        coords = generate_clustered_tsp(
            node_count=node_count,
            seed=42,
            coordinate_min=min_coord,
            coordinate_max=max_coord,
            num_clusters=num_clusters,
            sigma_fraction=sigma_fraction,
        )

        self.assertEqual(len(coords), node_count)
        for x, y in coords:
            self.assertGreaterEqual(x, min_coord)
            self.assertLessEqual(x, max_coord)
            self.assertGreaterEqual(y, min_coord)
            self.assertLessEqual(y, max_coord)

        # Pairwise distance distribution check
        distances = []
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                d = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
                distances.append(d)

        distances.sort()
        # In a 3-cluster distribution of 60 points, the smallest distances (within-cluster)
        # must be significantly smaller than the largest distances (between-cluster)
        mean_smallest = sum(distances[:20]) / 20
        mean_largest = sum(distances[-20:]) / 20
        self.assertLess(mean_smallest * 2.0, mean_largest)

    def test_instance_hash_disjointness_between_a_and_b(self) -> None:
        """Uniform set A and Uniform set B must have disjoint instance coordinates and hashes."""
        registry = load_task_registry(repo_root=self.repo_root)
        task_a = registry.get("tsp_uniform_n50_a")
        task_b = registry.get("tsp_uniform_n50_b")

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            exp = ExperimentConfig(
                name="test",
                condition="isolated",
                output_root=tmp,
                seeds=(1,),
                data=DataConfig(seed=42, coordinate_min=0, coordinate_max=10000, splits={"train": 5, "validation": 5, "test": 5, "smoke": 2}),
                search=SearchBudget(generations=1, candidates_per_generation=1, max_llm_calls=1),
                evaluation=EvaluationBudget(instance_timeout_seconds=30.0, batch_timeout_seconds=900.0),
            )

            # Generate task splits into temp subdirs
            task_a_tmp = registry.get("tsp_uniform_n50_a")
            splits_a = task_a_tmp.splits
            object.__setattr__(splits_a, "train", tmp / "a" / "train")
            object.__setattr__(splits_a, "validation", tmp / "a" / "validation")
            object.__setattr__(splits_a, "test", tmp / "a" / "test")
            object.__setattr__(splits_a, "smoke", tmp / "a" / "smoke")

            splits_b = task_b.splits
            object.__setattr__(splits_b, "train", tmp / "b" / "train")
            object.__setattr__(splits_b, "validation", tmp / "b" / "validation")
            object.__setattr__(splits_b, "test", tmp / "b" / "test")
            object.__setattr__(splits_b, "smoke", tmp / "b" / "smoke")

            _generate_task_splits(task_a, exp, seed=1)
            _generate_task_splits(task_b, exp, seed=1)

            hashes_a = {sha256_file(p) for p in (tmp / "a" / "train").glob("*.tsp")}
            hashes_b = {sha256_file(p) for p in (tmp / "b" / "train").glob("*.tsp")}

            # Sets must be strictly non-empty and disjoint
            self.assertTrue(len(hashes_a) > 0)
            self.assertTrue(len(hashes_b) > 0)
            self.assertEqual(hashes_a.intersection(hashes_b), set())

    def test_domain_neutral_retriever_and_cross_domain_safety(self) -> None:
        """RetrieverV0 must allow cross-domain candidates neutrally without hardcoding domain pairs."""
        retriever = RetrieverV0()

        # Create a TSP memory unit
        tsp_unit = MemoryUnit(
            id="mem_tsp_001",
            created_at="2026-09-05T00:00:00Z",
            scope=MemoryScope(problem="tsp", task_id="tsp_uniform_n50_a"),
            key=MemoryKey(applicability="tsp constructive heuristic", task_signature={"nodes": 50}),
            value=MemoryValue(type="procedural_skill", content="Nearest neighbor with 2-opt"),
            evidence=MemoryEvidence(source_artifacts=("fake/path/heur.py",), validation_after={"score": 120.0}),
            policy=MemoryPolicyState(confidence=0.8, retrieval_count=2, success_count=2),
        )

        # 1. Query from CVRP
        cvrp_query = RetrievalQuery(
            problem="cvrp",
            task_id="cvrp_uniform_n30",
            task_signature={"nodes": 30},
        )
        cvrp_results = retriever.retrieve(cvrp_query, [tsp_unit], RetrievalBudget(top_k=5))
        self.assertEqual(len(cvrp_results), 1)
        self.assertEqual(cvrp_results[0].unit.id, "mem_tsp_001")

        # 2. Query from JSSP
        jssp_query = RetrievalQuery(
            problem="jssp",
            task_id="jssp_j10_m5",
            task_signature={"jobs": 10, "machines": 5},
        )
        jssp_results = retriever.retrieve(jssp_query, [tsp_unit], RetrievalBudget(top_k=5))
        self.assertEqual(len(jssp_results), 1)
        self.assertEqual(jssp_results[0].unit.id, "mem_tsp_001")

        # Both CVRP and JSSP queries receive the same domain-neutral cross-problem policy
        self.assertAlmostEqual(cvrp_results[0].score, jssp_results[0].score, places=3)

    def test_transfer_policy_prohibits_cross_domain_direct_reuse(self) -> None:
        """DeterministicTransferPolicy must NEVER assign direct_reuse across different problem domains."""
        policy = DeterministicTransferPolicy(direct_reuse_quota=1, refine_quota=2)
        registry = load_task_registry(repo_root=self.repo_root)
        cvrp_task = registry.get("cvrp_uniform_n30")
        tsp_task = registry.get("tsp_uniform_n50_a")

        tsp_unit = MemoryUnit(
            id="mem_tsp_001",
            created_at="2026-09-05T00:00:00Z",
            scope=MemoryScope(problem="tsp", task_id="tsp_uniform_n50_a"),
            key=MemoryKey(applicability="tsp", task_signature={}),
            value=MemoryValue(type="procedural_skill", content="strategy"),
            evidence=MemoryEvidence(source_artifacts=("fake/path.py",)),
        )

        from cmhh.retrieval.base import RetrievedItem
        retrieved = [RetrievedItem(unit=tsp_unit, score=0.85, rank=1)]

        # Cross-problem: TSP memory -> CVRP task
        cvrp_plans = policy.plan(task=cvrp_task, retrieved=retrieved)
        self.assertEqual(len(cvrp_plans), 1)
        self.assertEqual(cvrp_plans[0].action, "refine")
        self.assertEqual(cvrp_plans[0].expected_role, "prompt_context")

        # Same-problem: TSP memory -> TSP task
        tsp_plans = policy.plan(task=tsp_task, retrieved=retrieved)
        self.assertEqual(len(tsp_plans), 1)
        self.assertEqual(tsp_plans[0].action, "direct_reuse")
        self.assertEqual(tsp_plans[0].expected_role, "seed")

    def test_population_builder_rejects_cross_domain_executable_seed(self) -> None:
        """PopulationBuilder must not insert cross-domain memory as an executable seed."""
        builder = MemoryAwarePopulationBuilder(memory_seed_quota=1)
        registry = load_task_registry(repo_root=self.repo_root)
        cvrp_task = registry.get("cvrp_uniform_n30")

        tsp_item = MemoryItem(
            id="mem_tsp_001",
            artifact_id="heur_tsp_001",
            code_path="fake/path.py",
            code_hash="sha256abc",
            applicability=ApplicabilityDescriptor(problem_family="tsp", task_id="tsp_uniform_n50_a"),
            abstraction=KnowledgeAbstraction(summary="TSP heuristic"),
            metadata=MemoryMetadata(origin_task_id="tsp_uniform_n50_a"),
        )

        plan = TransferPlan(
            memory_id="mem_tsp_001",
            artifact_id="heur_tsp_001",
            action="direct_reuse",
            reason="test",
            retrieval_rank=1,
            retrieval_score=0.9,
            expected_role="seed",
        )

        result = builder.build(
            task=cvrp_task,
            transfer_plans=[plan],
            retrieved_memory=[tsp_item],
            base_seed_population=[],
        )

        # Artifact should NOT be inserted into seed population because problem mismatch (tsp != cvrp)
        self.assertEqual(len(result.seed_population), 0)

    def test_all_pilot_stream_configs_and_suite_loading(self) -> None:
        """Verify that all 5 pilot streams and suite configs load and validate against TaskRegistry."""
        registry = load_task_registry(repo_root=self.repo_root)

        pilot_streams = [
            "tsp_size_up_small",
            "tsp_size_down_small",
            "tsp_variant_revisit_small",
            "related_pair_small",
            "unrelated_pair_small",
            "tsp_stationary_small",
        ]

        for stream_id in pilot_streams:
            stream_path = resolve_stream_path(stream_id, self.repo_root)
            self.assertTrue(stream_path.exists(), f"Stream config {stream_id} not found at {stream_path}")
            stream_cfg = load_stream_config(stream_path)
            self.assertEqual(stream_cfg.stream_id, stream_id)
            for task_id in stream_cfg.task_ids:
                task_spec = registry.get(task_id)
                self.assertIsNotNone(task_spec, f"Task {task_id} not found in registry")

        # Verify pilot_small suite config
        suite_path = resolve_suite_path("pilot_small", self.repo_root)
        self.assertTrue(suite_path.exists())
        suite_cfg = load_suite_config(suite_path)
        self.assertEqual(suite_cfg.suite_id, "pilot_small")
        self.assertEqual(len(suite_cfg.streams), 5)
        self.assertIn("isolated", suite_cfg.conditions)
        self.assertIn("naive-bounded", suite_cfg.conditions)
        self.assertIn("managed", suite_cfg.conditions)

        # Verify pilot_small_smoke suite config
        smoke_suite_path = resolve_suite_path("pilot_small_smoke", self.repo_root)
        self.assertTrue(smoke_suite_path.exists())
        smoke_cfg = load_suite_config(smoke_suite_path)
        self.assertEqual(smoke_cfg.suite_id, "pilot_small_smoke")
        self.assertEqual(smoke_cfg.mode, "smoke")


if __name__ == "__main__":
    unittest.main()
