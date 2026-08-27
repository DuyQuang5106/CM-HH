from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cmhh.config import DataConfig, ExperimentConfig, SearchBudget
from cmhh.data import generate_data_for_tasks
from cmhh.models import EvaluationBudget
from cmhh.tasks import TaskMetric, TaskReference, TaskRegistry, TaskSpec, TaskSplits

try:
    from problems.cvrp.env import Env as CvrpEnv
except ImportError:
    CvrpEnv = None

try:
    from problems.dposp.env import Env as DpospEnv
except ImportError:
    DpospEnv = None

try:
    from problems.jssp.env import Env as JsspEnv
except ImportError:
    JsspEnv = None

try:
    from problems.max_cut.env import Env as MaxCutEnv
except ImportError:
    MaxCutEnv = None

try:
    from problems.mkp.env import Env as MkpEnv
except ImportError:
    MkpEnv = None

try:
    from problems.tsp.env import Env as TspEnv
except ImportError:
    TspEnv = None


class TestDataGenerators(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        ref = TaskReference(type="none")
        metric = TaskMetric(name="relative_gap", objective="minimize")

        # Setup mock task specs for all 7 problems
        self.tasks = {
            "tsp_test": TaskSpec(
                task_id="tsp_test",
                problem="tsp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/tsp/train",
                    validation=self.root / "data/tsp/validation",
                    test=self.root / "data/tsp/test",
                    smoke=self.root / "data/tsp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"nodes": 20},
            ),
            "cvrp_test": TaskSpec(
                task_id="cvrp_test",
                problem="cvrp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/cvrp/train",
                    validation=self.root / "data/cvrp/validation",
                    test=self.root / "data/cvrp/test",
                    smoke=self.root / "data/cvrp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"nodes": 20},
            ),
            "jssp_test": TaskSpec(
                task_id="jssp_test",
                problem="jssp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/jssp/train",
                    validation=self.root / "data/jssp/validation",
                    test=self.root / "data/jssp/test",
                    smoke=self.root / "data/jssp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"jobs": 10, "machines": 5},
            ),
            "dposp_test": TaskSpec(
                task_id="dposp_test",
                problem="dposp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/dposp/train",
                    validation=self.root / "data/dposp/validation",
                    test=self.root / "data/dposp/test",
                    smoke=self.root / "data/dposp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"orders": 10, "lines": 3, "products": 5},
            ),
            "mkp_test": TaskSpec(
                task_id="mkp_test",
                problem="mkp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/mkp/train",
                    validation=self.root / "data/mkp/validation",
                    test=self.root / "data/mkp/test",
                    smoke=self.root / "data/mkp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"items": 15, "resources": 5},
            ),
            "max_cut_test": TaskSpec(
                task_id="max_cut_test",
                problem="max_cut",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/max_cut/train",
                    validation=self.root / "data/max_cut/validation",
                    test=self.root / "data/max_cut/test",
                    smoke=self.root / "data/max_cut/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"nodes": 15, "density": 0.4},
            ),
            "obp_test": TaskSpec(
                task_id="obp_test",
                problem="obp",
                size_tier="n20",
                distribution="uniform",
                splits=TaskSplits(
                    train=self.root / "data/obp/train",
                    validation=self.root / "data/obp/validation",
                    test=self.root / "data/obp/test",
                    smoke=self.root / "data/obp/smoke",
                ),
                reference=ref,
                metric=metric,
                implemented_in_heuragenix=True,
                metadata={"items": 20, "bin_capacity": 100},
            ),
        }

        self.registry = TaskRegistry(list(self.tasks.values()))
        self.experiment = ExperimentConfig(
            name="test_exp",
            condition="test",
            output_root=self.root / "results",
            seeds=(42,),
            data=DataConfig(42, 0, 10000, {"train": 1, "validation": 1, "test": 1, "smoke": 1}),
            search=SearchBudget(1, 2, 2),
            evaluation=EvaluationBudget(1.0, 10.0),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_generate_data_all_problems(self) -> None:
        task_ids = tuple(self.tasks.keys())
        manifests = generate_data_for_tasks(self.registry, task_ids, self.experiment, seed=42)

        self.assertEqual(len(manifests), len(task_ids))
        for manifest_path in manifests:
            self.assertTrue(manifest_path.exists())

    def test_env_parsers_compatibility(self) -> None:
        generate_data_for_tasks(self.registry, tuple(self.tasks.keys()), self.experiment, seed=42)

        # 1. Test TSP parser
        if TspEnv is not None:
            tsp_file = next((self.root / "data/tsp/smoke").glob("*.tsp"))
            tsp_data = TspEnv.__new__(TspEnv).load_data(str(tsp_file))
            self.assertEqual(tsp_data["node_num"], 20)

        # 2. Test CVRP parser
        if CvrpEnv is not None:
            cvrp_file = next((self.root / "data/cvrp/smoke").glob("*.vrp"))
            cvrp_data = CvrpEnv.__new__(CvrpEnv).load_data(str(cvrp_file))
            self.assertEqual(cvrp_data["node_num"], 20)
            self.assertGreaterEqual(cvrp_data["vehicle_num"], 2)

        # 3. Test JSSP parser
        if JsspEnv is not None:
            jssp_file = next((self.root / "data/jssp/smoke").glob("*.txt"))
            jssp_data = JsspEnv.__new__(JsspEnv).load_data(str(jssp_file))
            self.assertEqual(jssp_data["job_num"], 10)
            self.assertEqual(jssp_data["machine_num"], 5)

        # 4. Test DPOSP parser
        if DpospEnv is not None:
            dposp_dir = next((self.root / "data/dposp/smoke").iterdir())
            dposp_data = DpospEnv.__new__(DpospEnv).load_data(str(dposp_dir))
            self.assertEqual(dposp_data["order_num"], 10)

        # 5. Test MKP parser
        if MkpEnv is not None:
            mkp_file = next((self.root / "data/mkp/smoke").glob("*.txt"))
            mkp_data = MkpEnv.__new__(MkpEnv).load_data(str(mkp_file))
            self.assertEqual(mkp_data["item_num"], 15)
            self.assertEqual(mkp_data["resource_num"], 5)

        # 6. Test MaxCut parser
        if MaxCutEnv is not None:
            max_cut_file = next((self.root / "data/max_cut/smoke").glob("*.txt"))
            max_cut_data = MaxCutEnv.__new__(MaxCutEnv).load_data(str(max_cut_file))
            self.assertEqual(max_cut_data["node_num"], 15)


if __name__ == "__main__":
    unittest.main()
