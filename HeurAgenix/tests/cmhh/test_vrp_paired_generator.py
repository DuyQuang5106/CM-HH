from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from cmhh.config import DataConfig, ExperimentConfig
from cmhh.config import load_stream_config, load_suite_config
from cmhh.data.cvrp_generator import generate_cvrp_splits
from cmhh.data.dispatch import generate_data_for_tasks
from cmhh.data.vrp_generator import generate_vrp_variant_splits
from cmhh.models import EvaluationBudget, SearchBudget
from cmhh.references.base import SolverConfig
from cmhh.references.pipeline import generate_task_references
from cmhh.references.verification import verify_task_references
from cmhh.runtime import resolve_stream_path, resolve_suite_path
from cmhh.runner import _vrp_constraint_transition
from cmhh.tasks import TaskMetric, TaskReference, TaskSpec, TaskSplits
from cmhh.tasks import load_task_registry
from cmhh.tasks import TaskRegistry
from cmhh.validation import validate_configuration
from src.problems.cvrp.components import Solution
from src.problems.cvrp.env import Env
from src.problems.cvrp.variant import constraint_vector, hamming_distance, profile_from_config


REPO_ROOT = Path(__file__).resolve().parents[2]


class VRPPairedGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = Path.cwd()
        os.chdir(REPO_ROOT)

    def tearDown(self) -> None:
        os.chdir(self._cwd)

    def test_paired_variants_share_base_instance_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            experiment = _experiment(root, split_count=2)
            tasks = [_task(root, variant) for variant in ("cvrp", "ovrp", "ovrptw", "vrptw")]

            for task in tasks:
                generate_vrp_variant_splits(task, experiment, seed=99)

            metas = {
                task.metadata["vrp_variant"]: _first_meta(task.splits.train)
                for task in tasks
            }

            first = metas["cvrp"]
            for variant, meta in metas.items():
                self.assertEqual(first["pair_group_id"], meta["pair_group_id"], variant)
                self.assertEqual(first["coordinate_hash"], meta["coordinate_hash"], variant)
                self.assertEqual(first["demand_hash"], meta["demand_hash"], variant)
                self.assertEqual(first["fleet_size"], meta["fleet_size"], variant)
                self.assertEqual(first["capacity"], meta["capacity"], variant)
                self.assertEqual(first["time_windows"], meta["time_windows"], variant)
                self.assertEqual(first["service_times"], meta["service_times"], variant)

            self.assertFalse(metas["cvrp"]["constraints"]["open_route"])
            self.assertFalse(metas["cvrp"]["constraints"]["time_windows"])
            self.assertTrue(metas["ovrp"]["constraints"]["open_route"])
            self.assertFalse(metas["ovrp"]["constraints"]["time_windows"])
            self.assertTrue(metas["ovrptw"]["constraints"]["open_route"])
            self.assertTrue(metas["ovrptw"]["constraints"]["time_windows"])
            self.assertFalse(metas["vrptw"]["constraints"]["open_route"])
            self.assertTrue(metas["vrptw"]["constraints"]["time_windows"])

    def test_generated_tw_anchor_routes_are_valid_for_tw_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            experiment = _experiment(root, split_count=1)

            for variant in ("ovrptw", "vrptw"):
                task = _task(root, variant)
                generate_vrp_variant_splits(task, experiment, seed=99)
                instance_path = next(task.splits.smoke.glob("*.vrp"))
                meta = json.loads(instance_path.with_suffix(".meta.json").read_text(encoding="utf-8"))

                env = Env(str(instance_path))
                env.current_solution = Solution(
                    routes=[[env.instance_data["depot"], *route] for route in meta["time_window_generation"]["anchor_routes"]],
                    depot=env.instance_data["depot"],
                )

                self.assertTrue(env.validation_solution(), variant)
                self.assertTrue(env.is_complete_solution, variant)

    def test_generate_cvrp_splits_delegates_for_vrp_variant_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            experiment = _experiment(root, split_count=1)
            task = _task(root, "ovrp")

            generate_cvrp_splits(task, experiment, seed=99)

            meta = _first_meta(task.splits.train)
            self.assertEqual("ovrp", meta["variant"])
            self.assertTrue(meta["constraints"]["open_route"])

    def test_dispatch_preserves_vrp_rich_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            experiment = _experiment(root, split_count=1)
            task = _task(root, "ovrptw")
            registry = TaskRegistry([task])

            manifests = generate_data_for_tasks(registry, (task.task_id,), experiment, seed=99)

            self.assertEqual([task.splits.train.parent / "manifest.json"], manifests)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual("vrp", manifest["family"])
            self.assertEqual("ovrptw", manifest["variant"])
            self.assertTrue(manifest["constraints"]["open_route"])
            self.assertTrue(manifest["constraints"]["time_windows"])
            self.assertIn("pair_group_id", manifest["splits"]["train"][0])

    def test_forward_and_reverse_graycode_sequences_have_one_bit_transitions(self) -> None:
        forward = ["cvrp", "ovrp", "ovrptw", "vrptw"]
        reverse = list(reversed(forward))

        for sequence in (forward, reverse):
            profiles = [profile_from_config(variant) for variant in sequence]
            distances = [
                hamming_distance(constraint_vector(left), constraint_vector(right))
                for left, right in zip(profiles, profiles[1:])
            ]
            self.assertEqual([1, 1, 1], distances)

    def test_registered_vrp_constraint_streams_load_and_are_graycode(self) -> None:
        registry = load_task_registry(repo_root=REPO_ROOT)
        suite_path = resolve_suite_path("vrp_constraint_transfer", REPO_ROOT)
        suite = load_suite_config(suite_path)

        self.assertEqual("vrp_constraint_transfer", suite.suite_id)
        self.assertEqual(
            ("vrp_constraint_graycode", "vrp_constraint_graycode_reverse"),
            suite.streams,
        )

        for stream_id in suite.streams:
            stream = load_stream_config(resolve_stream_path(stream_id, REPO_ROOT))
            profiles = []
            pair_family_ids = set()
            for task_id in stream.task_ids:
                task = registry.get(task_id)
                self.assertIsNotNone(task, task_id)
                self.assertEqual("cvrp", task.problem)
                self.assertEqual("vrp", task.metadata["constraint_family"])
                profiles.append(profile_from_config(task.metadata["vrp_variant"]))
                pair_family_ids.add(task.metadata["pair_family_id"])

            self.assertEqual({"vrp_constraint_uniform_n50_medium"}, pair_family_ids)
            distances = [
                hamming_distance(constraint_vector(left), constraint_vector(right))
                for left, right in zip(profiles, profiles[1:])
            ]
            self.assertEqual([1, 1, 1], distances, stream_id)

    def test_vrp_graycode_stream_passes_configuration_validation(self) -> None:
        registry = load_task_registry(repo_root=REPO_ROOT)
        stream = load_stream_config(resolve_stream_path("vrp_constraint_graycode", REPO_ROOT))
        report = validate_configuration(registry, stream, _experiment(REPO_ROOT / "tmp", split_count=1), REPO_ROOT)

        self.assertEqual([], report.errors)

    def test_vrp_constraint_transition_labels(self) -> None:
        registry = load_task_registry(repo_root=REPO_ROOT)
        expected = {
            ("cvrp_uniform_n50_medium", "ovrp_uniform_n50_medium"): "remove_route_closure",
            ("ovrp_uniform_n50_medium", "ovrptw_uniform_n50_medium"): "add_time_windows",
            ("ovrptw_uniform_n50_medium", "vrptw_uniform_n50_medium"): "add_route_closure",
        }

        for (source_id, target_id), relationship in expected.items():
            transition = _vrp_constraint_transition(registry.get(source_id), registry.get(target_id))
            self.assertIsNotNone(transition)
            self.assertEqual(relationship, transition["relationship"])

    def test_generated_variant_references_roundtrip_through_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            experiment = _experiment(root, split_count=1)

            for variant in ("ovrp", "vrptw"):
                task = _task(root, variant)
                generate_vrp_variant_splits(task, experiment, seed=99)

                records, failures = generate_task_references(
                    task,
                    "validation",
                    SolverConfig(timeout_seconds=5.0, max_workers=1, solver_name="pyvrp", seed=7),
                )
                report = verify_task_references(task, "validation")

                self.assertEqual([], failures, variant)
                self.assertEqual(1, len(records), variant)
                self.assertEqual(variant, records[0].metadata["variant"])
                self.assertEqual(profile_from_config(variant).to_dict(), records[0].metadata["constraints"])
                self.assertTrue(records[0].metadata["internal_validation_feasible"])
                self.assertTrue(report.valid, report.errors)


def _experiment(root: Path, split_count: int) -> ExperimentConfig:
    return ExperimentConfig(
        name="vrp-test",
        condition="isolated_task",
        output_root=root,
        seeds=(1,),
        data=DataConfig(
            seed=99,
            coordinate_min=0,
            coordinate_max=1000,
            splits={"train": split_count, "validation": split_count, "test": split_count, "smoke": 1},
        ),
        search=SearchBudget(generations=1, candidates_per_generation=1, max_llm_calls=1),
        evaluation=EvaluationBudget(instance_timeout_seconds=10, batch_timeout_seconds=30),
    )


def _task(root: Path, variant: str) -> TaskSpec:
    task_id = f"{variant}_uniform_n12_medium"
    task_root = root / task_id
    return TaskSpec(
        task_id=task_id,
        problem="cvrp",
        size_tier="n12",
        distribution="euclidean_uniform",
        splits=TaskSplits(
            train=task_root / "train",
            validation=task_root / "validation",
            test=task_root / "test",
            smoke=task_root / "smoke",
        ),
        reference=TaskReference("best_known", task_root / "reference.json"),
        metric=TaskMetric("relative_gap", "minimize"),
        implemented_in_heuragenix=True,
        metadata={
            "nodes": 12,
            "customers": 12,
            "fleet_size": 3,
            "constraint_family": "vrp",
            "vrp_variant": variant,
            "constraint_regime": "medium",
            "capacity_tightness": 0.75,
            "time_window_regime": "medium",
            "base_dataset_id": "vrp_uniform_n12_medium_base",
            "dataset_seed": 9912,
        },
    )


def _first_meta(directory: Path) -> dict:
    instance_path = next(directory.glob("*.vrp"))
    return json.loads(instance_path.with_suffix(".meta.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
