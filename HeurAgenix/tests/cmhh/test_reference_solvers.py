from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.data.cvrp_generator import generate_cvrp_instance, write_cvrplib
from cmhh.data.jssp_generator import generate_jssp_instance, write_jssp
from cmhh.data.manifest import sha256_file
from cmhh.data.references import ReferenceRecord, load_reference_set, write_reference_set
from cmhh.data.tsp_generator import generate_tsp_instance, write_tsplib
from cmhh.references.base import ReferenceResult, SolverConfig
from cmhh.references.cvrp_solver import CVRPSolverAdapter
from cmhh.references.jssp_solver import JSSPSolverAdapter
from cmhh.references.ortools_cpsat_solver import ORToolsCPSATSolverAdapter
from cmhh.references.pipeline import generate_task_references
from cmhh.references.pyvrp_solver import PyVRPSolverAdapter
from cmhh.references.registry import ReferenceSolverRegistry
from cmhh.references.tsp_solver import TSPSolverAdapter
from cmhh.references.verification import verify_task_references
from cmhh.tasks import TaskMetric, TaskReference, TaskSpec, TaskSplits
from src.problems.cvrp.variant import OVRP_PROFILE, VRPTW_PROFILE


class ReferenceSolversSmokeTests(unittest.TestCase):
    def test_pyvrp_import_and_version(self) -> None:
        import pyvrp
        from pyvrp import Model
        self.assertIsNotNone(Model)

    def test_ortools_cpsat_import_and_model(self) -> None:
        import ortools
        from ortools.sat.python import cp_model
        model = cp_model.CpModel()
        self.assertIsNotNone(model)

    def test_registry_resolves_all_reference_solvers(self) -> None:
        tsp_solver = ReferenceSolverRegistry.get_solver("tsp")
        cvrp_solver = ReferenceSolverRegistry.get_solver("cvrp")
        jssp_solver = ReferenceSolverRegistry.get_solver("jssp")
        pyvrp_solver = ReferenceSolverRegistry.get_solver("pyvrp")
        ovrp_solver = ReferenceSolverRegistry.get_solver("ovrp")
        ovrptw_solver = ReferenceSolverRegistry.get_solver("ovrptw")
        vrptw_solver = ReferenceSolverRegistry.get_solver("vrptw")
        cpsat_solver = ReferenceSolverRegistry.get_solver("ortools_cpsat")

        self.assertIsInstance(tsp_solver, TSPSolverAdapter)
        self.assertIsInstance(cvrp_solver, (CVRPSolverAdapter, PyVRPSolverAdapter))
        self.assertIsInstance(jssp_solver, (JSSPSolverAdapter, ORToolsCPSATSolverAdapter))
        self.assertIsInstance(pyvrp_solver, PyVRPSolverAdapter)
        self.assertIsInstance(ovrp_solver, PyVRPSolverAdapter)
        self.assertIsInstance(ovrptw_solver, PyVRPSolverAdapter)
        self.assertIsInstance(vrptw_solver, PyVRPSolverAdapter)
        self.assertIsInstance(cpsat_solver, ORToolsCPSATSolverAdapter)


class CVRPSolverTests(unittest.TestCase):
    def test_pyvrp_cvrp_reference_solver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coords, demands, cap, veh = generate_cvrp_instance(6, 42, 0, 100)
            instance_path = write_cvrplib(Path(temp_dir) / "test_cvrp.vrp", "test_cvrp", coords, demands, cap, veh)

            solver = PyVRPSolverAdapter()
            config = SolverConfig(timeout_seconds=5.0, seed=42)
            res = solver.solve(instance_path, config)

            self.assertEqual("test_cvrp-k3", res.instance_id)
            self.assertIsNotNone(res.objective)
            self.assertGreater(res.objective, 0.0)
            self.assertEqual("best_known", res.status)
            self.assertFalse(res.proven_optimal)
            self.assertEqual("pyvrp", res.solver)
            self.assertIn("routes", res.metadata)
            self.assertIn("solver_version", res.metadata)
            self.assertIn("seed", res.metadata)

    def test_cvrp_adapter_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coords, demands, cap, veh = generate_cvrp_instance(6, 42, 0, 100)
            instance_path = write_cvrplib(Path(temp_dir) / "test_cvrp.vrp", "test_cvrp", coords, demands, cap, veh)

            solver = CVRPSolverAdapter()
            config = SolverConfig(timeout_seconds=5.0, seed=42)
            res = solver.solve(instance_path, config)

            self.assertEqual("test_cvrp-k3", res.instance_id)
            self.assertGreater(res.objective, 0.0)
            self.assertEqual("best_known", res.status)
            self.assertFalse(res.proven_optimal)

    def test_pyvrp_ovrp_reference_solver_uses_open_route_objective(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coords = [(0, 0), (1, 0), (2, 0), (3, 0)]
            demands = [0, 1, 1, 1]
            instance_path = write_cvrplib(Path(temp_dir) / "test_ovrp.vrp", "test_ovrp", coords, demands, 10, 1)
            instance_path.with_suffix(".meta.json").write_text(
                json.dumps({"variant": "ovrp", "constraints": OVRP_PROFILE.to_dict()}),
                encoding="utf-8",
            )

            res = PyVRPSolverAdapter().solve(instance_path, SolverConfig(timeout_seconds=5.0, seed=42))

            self.assertEqual("best_known", res.status)
            self.assertEqual("ovrp", res.metadata["variant"])
            self.assertAlmostEqual(3.0, res.objective)
            self.assertAlmostEqual(res.objective, res.metadata["internal_objective"])
            self.assertTrue(res.metadata["internal_validation_feasible"])

    def test_pyvrp_vrptw_reference_solver_validates_internally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coords = [(0, 0), (1, 0), (2, 0), (3, 0)]
            demands = [0, 1, 1, 1]
            instance_path = write_cvrplib(Path(temp_dir) / "test_vrptw.vrp", "test_vrptw", coords, demands, 10, 1)
            instance_path.with_suffix(".meta.json").write_text(
                json.dumps({
                    "variant": "vrptw",
                    "constraints": VRPTW_PROFILE.to_dict(),
                    "time_windows": {
                        "depot": [0, 100],
                        "customers": {
                            "1": [0, 100],
                            "2": [0, 100],
                            "3": [0, 100],
                        },
                    },
                    "service_times": {"default": 0},
                }),
                encoding="utf-8",
            )

            res = PyVRPSolverAdapter().solve(instance_path, SolverConfig(timeout_seconds=5.0, seed=42))

            self.assertEqual("best_known", res.status)
            self.assertEqual("vrptw", res.metadata["variant"])
            self.assertTrue(res.metadata["constraints"]["time_windows"])
            self.assertTrue(res.metadata["internal_validation_feasible"])


class JSSPSolverTests(unittest.TestCase):
    def test_ortools_cpsat_jssp_reference_solver_optimal(self) -> None:
        # Small deterministic 2-job 2-machine instance with known optimal makespan
        with tempfile.TemporaryDirectory() as temp_dir:
            instance_path = Path(temp_dir) / "tiny_jssp.txt"
            seq = [[0, 1], [1, 0]]
            times = [[3, 2], [2, 4]]
            write_jssp(instance_path, seq, times)

            solver = ORToolsCPSATSolverAdapter()
            config = SolverConfig(timeout_seconds=5.0, seed=42, num_workers=1)
            res = solver.solve(instance_path, config)

            self.assertEqual("tiny_jssp", res.instance_id)
            self.assertIsNotNone(res.objective)
            self.assertEqual(7.0, res.objective)
            self.assertEqual("optimal", res.status)
            self.assertTrue(res.proven_optimal)
            self.assertEqual("ortools_cpsat", res.solver)
            self.assertEqual("OPTIMAL", res.metadata.get("solver_status"))
            self.assertEqual(7.0, res.metadata.get("best_objective_bound"))

    def test_cpsat_status_mapping(self) -> None:
        solver = ORToolsCPSATSolverAdapter()

        with tempfile.TemporaryDirectory() as temp_dir:
            instance_path = Path(temp_dir) / "tiny_jssp.txt"
            seq = [[0, 1], [1, 0]]
            times = [[3, 2], [2, 4]]
            write_jssp(instance_path, seq, times)

            from ortools.sat.python import cp_model

            # Test FEASIBLE mapping
            with patch("ortools.sat.python.cp_model.CpSolver.Solve", return_value=cp_model.FEASIBLE), \
                 patch("ortools.sat.python.cp_model.CpSolver.ObjectiveValue", return_value=12.0), \
                 patch("ortools.sat.python.cp_model.CpSolver.BestObjectiveBound", return_value=10.0), \
                 patch("ortools.sat.python.cp_model.CpSolver.StatusName", return_value="FEASIBLE"):
                res = solver.solve(instance_path, SolverConfig(timeout_seconds=5.0))
                self.assertEqual("best_known", res.status)
                self.assertFalse(res.proven_optimal)
                self.assertEqual(12.0, res.objective)

            # Test UNKNOWN/TIMEOUT mapping without feasible solution
            with patch("ortools.sat.python.cp_model.CpSolver.Solve", return_value=cp_model.UNKNOWN), \
                 patch("ortools.sat.python.cp_model.CpSolver.StatusName", return_value="UNKNOWN"):
                res = solver.solve(instance_path, SolverConfig(timeout_seconds=5.0))
                self.assertEqual("failed", res.status)
                self.assertIsNone(res.objective)
                self.assertFalse(res.proven_optimal)


class ReferenceSchemaAndContractTests(unittest.TestCase):
    def test_reference_result_to_record_optimal(self) -> None:
        res = ReferenceResult(
            instance_id="inst_1",
            objective=42.0,
            status="optimal",
            solver="concorde",
            instance_sha256="abc123",
            runtime_seconds=1.5,
            proven_optimal=True,
            metadata={"seed": 1},
        )
        rec = res.to_reference_record()
        self.assertEqual("optimal", rec.status)
        self.assertEqual(42.0, rec.objective)
        self.assertEqual("concorde", rec.solver)
        self.assertEqual({"seed": 1}, rec.metadata)

    def test_reference_result_to_record_best_known(self) -> None:
        res = ReferenceResult(
            instance_id="inst_2",
            objective=123.45,
            status="best_known",
            solver="pyvrp",
            instance_sha256="def456",
            runtime_seconds=2.5,
            proven_optimal=False,
            metadata={"routes": [[1, 2]]},
        )
        rec = res.to_reference_record()
        self.assertEqual("best_known", rec.status)
        self.assertEqual(123.45, rec.objective)
        self.assertEqual("pyvrp", rec.solver)

    def test_reference_result_to_record_failed(self) -> None:
        res = ReferenceResult(
            instance_id="inst_3",
            objective=None,
            status="failed",
            solver="pyvrp",
            instance_sha256="ghi789",
            runtime_seconds=10.0,
            proven_optimal=False,
            metadata={"error": "timeout"},
        )
        rec = res.to_reference_record()
        self.assertEqual("failed", rec.status)
        self.assertTrue(math.isnan(rec.objective))
        self.assertEqual("pyvrp", rec.solver)

    def test_reference_set_json_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ref_path = Path(temp_dir) / "references.json"
            records = [
                ReferenceRecord(
                    instance_id="inst_001",
                    objective=100.0,
                    status="optimal",
                    solver="concorde",
                    instance_sha256="hash1",
                    runtime_seconds=1.2,
                ),
                ReferenceRecord(
                    instance_id="inst_002",
                    objective=250.5,
                    status="best_known",
                    solver="pyvrp",
                    instance_sha256="hash2",
                    runtime_seconds=3.4,
                    metadata={"iterations": 500},
                ),
            ]
            write_reference_set(ref_path, "test_task", records)

            loaded = load_reference_set(ref_path)
            self.assertEqual("test_task", loaded.task_id)
            self.assertEqual(2, len(loaded.records))
            r1 = loaded.get_optional("inst_001")
            self.assertIsNotNone(r1)
            self.assertEqual("optimal", r1.status)
            self.assertEqual(100.0, r1.objective)

            r2 = loaded.get_optional("inst_002")
            self.assertIsNotNone(r2)
            self.assertEqual("best_known", r2.status)
            self.assertEqual(250.5, r2.objective)

    def test_reference_cache_invalidates_when_solver_backend_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            split_dir = root / "validation"
            ref_path = root / "references" / "reference.json"
            split_dir.mkdir(parents=True)
            ref_path.parent.mkdir(parents=True)

            coords, demands, cap, veh = generate_cvrp_instance(6, 42, 0, 100)
            instance_path = write_cvrplib(split_dir / "cache_case.vrp", "cache_case", coords, demands, cap, veh)
            old_record = ReferenceRecord(
                instance_id=instance_path.stem,
                objective=999999.0,
                status="best_known",
                solver="cvrp_clarke_wright_local_search",
                instance_sha256=sha256_file(instance_path),
                runtime_seconds=0.01,
            )
            write_reference_set(ref_path, "cvrp_cache_test", [old_record])

            task = TaskSpec(
                task_id="cvrp_cache_test",
                problem="cvrp",
                size_tier="n20",
                distribution="euclidean_uniform",
                splits=TaskSplits(split_dir, split_dir, split_dir, split_dir),
                reference=TaskReference("best_known", ref_path),
                metric=TaskMetric("relative_gap", "minimize"),
                implemented_in_heuragenix=True,
            )
            records, failures = generate_task_references(
                task,
                "validation",
                config={"name": "pyvrp", "time_limit_seconds": 5, "seed": 42, "max_workers": 1},
            )

            self.assertEqual([], failures)
            self.assertEqual(1, len(records))
            self.assertEqual("pyvrp", records[0].solver)
            self.assertNotEqual(999999.0, records[0].objective)

    def test_reference_cache_invalidates_stale_vrp_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            split_dir = root / "validation"
            ref_path = root / "references" / "reference.json"
            split_dir.mkdir(parents=True)
            ref_path.parent.mkdir(parents=True)

            coords = [(0, 0), (1, 0), (2, 0), (3, 0)]
            demands = [0, 1, 1, 1]
            instance_path = write_cvrplib(split_dir / "ovrp_case.vrp", "ovrp_case", coords, demands, 10, 1)
            instance_path.with_suffix(".meta.json").write_text(
                json.dumps({"variant": "ovrp", "constraints": OVRP_PROFILE.to_dict()}),
                encoding="utf-8",
            )
            stale_record = ReferenceRecord(
                instance_id=instance_path.stem,
                objective=6.0,
                status="best_known",
                solver="pyvrp",
                instance_sha256=sha256_file(instance_path),
                runtime_seconds=0.01,
                metadata={
                    "variant": "cvrp",
                    "constraints": {
                        "capacitated": True,
                        "open_route": False,
                        "time_windows": False,
                    },
                    "internal_objective": 6.0,
                    "internal_validation_feasible": True,
                },
            )
            write_reference_set(ref_path, "ovrp_task", [stale_record])
            task = _vrp_task(split_dir, ref_path, "ovrp_task", "ovrp")
            replacement = ReferenceResult(
                instance_id=instance_path.stem,
                objective=3.0,
                status="best_known",
                solver="pyvrp",
                instance_sha256=sha256_file(instance_path),
                runtime_seconds=0.01,
                metadata={
                    "variant": "ovrp",
                    "constraints": OVRP_PROFILE.to_dict(),
                    "internal_objective": 3.0,
                    "internal_validation_feasible": True,
                },
            )

            with patch("cmhh.references.pyvrp_solver.PyVRPSolverAdapter.solve", return_value=replacement) as solve:
                records, failures = generate_task_references(
                    task,
                    "validation",
                    config={"name": "pyvrp", "time_limit_seconds": 5, "seed": 42, "max_workers": 1},
                )

            self.assertEqual([], failures)
            solve.assert_called_once()
            self.assertEqual(1, len(records))
            self.assertEqual(3.0, records[0].objective)
            self.assertEqual("ovrp", records[0].metadata["variant"])


class ReferenceVerificationTests(unittest.TestCase):
    def test_vrp_reference_verification_requires_variant_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            split_dir = root / "validation"
            ref_path = root / "references" / "reference.json"
            split_dir.mkdir(parents=True)
            ref_path.parent.mkdir(parents=True)

            coords = [(0, 0), (1, 0), (2, 0), (3, 0)]
            demands = [0, 1, 1, 1]
            instance_path = write_cvrplib(split_dir / "ovrp_case.vrp", "ovrp_case", coords, demands, 10, 1)
            instance_path.with_suffix(".meta.json").write_text(
                json.dumps({"variant": "ovrp", "constraints": OVRP_PROFILE.to_dict()}),
                encoding="utf-8",
            )
            write_reference_set(ref_path, "ovrp_task", [
                ReferenceRecord(
                    instance_id=instance_path.stem,
                    objective=3.0,
                    status="best_known",
                    solver="pyvrp",
                    instance_sha256=sha256_file(instance_path),
                    runtime_seconds=0.01,
                    metadata={
                        "variant": "ovrp",
                        "constraints": OVRP_PROFILE.to_dict(),
                        "internal_objective": 3.0,
                        "internal_validation_feasible": True,
                    },
                )
            ])
            task = _vrp_task(split_dir, ref_path, "ovrp_task", "ovrp")

            report = verify_task_references(task, "validation")

            self.assertTrue(report.valid, report.errors)
            self.assertEqual(1, report.best_known)

    def test_vrp_reference_verification_rejects_stale_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            split_dir = root / "validation"
            ref_path = root / "references" / "reference.json"
            split_dir.mkdir(parents=True)
            ref_path.parent.mkdir(parents=True)

            coords = [(0, 0), (1, 0), (2, 0), (3, 0)]
            demands = [0, 1, 1, 1]
            instance_path = write_cvrplib(split_dir / "ovrp_case.vrp", "ovrp_case", coords, demands, 10, 1)
            instance_path.with_suffix(".meta.json").write_text(
                json.dumps({"variant": "ovrp", "constraints": OVRP_PROFILE.to_dict()}),
                encoding="utf-8",
            )
            write_reference_set(ref_path, "ovrp_task", [
                ReferenceRecord(
                    instance_id=instance_path.stem,
                    objective=6.0,
                    status="best_known",
                    solver="pyvrp",
                    instance_sha256=sha256_file(instance_path),
                    runtime_seconds=0.01,
                    metadata={
                        "variant": "cvrp",
                        "constraints": {
                            "capacitated": True,
                            "open_route": False,
                            "time_windows": False,
                        },
                        "internal_objective": 6.0,
                        "internal_validation_feasible": True,
                    },
                )
            ])
            task = _vrp_task(split_dir, ref_path, "ovrp_task", "ovrp")

            report = verify_task_references(task, "validation")

            self.assertFalse(report.valid)
            self.assertEqual(0, report.best_known)
            self.assertTrue(any("variant mismatch" in error for error in report.errors))
            self.assertTrue(any("constraints mismatch" in error for error in report.errors))


def _vrp_task(split_dir: Path, ref_path: Path, task_id: str, variant: str) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        problem="cvrp",
        size_tier="n20",
        distribution="euclidean_uniform",
        splits=TaskSplits(split_dir, split_dir, split_dir, split_dir),
        reference=TaskReference("best_known", ref_path),
        metric=TaskMetric("relative_gap", "minimize"),
        implemented_in_heuragenix=True,
        metadata={
            "constraint_family": "vrp",
            "vrp_variant": variant,
            "base_dataset_id": "vrp_test_base",
            "dataset_seed": 42,
        },
    )


if __name__ == "__main__":
    unittest.main()
