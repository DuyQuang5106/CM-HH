from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from cmhh.data.cvrp_generator import (
    CVRPConstraintVariant,
    generate_cvrp_base_instance,
    generate_cvrp_constraint_regimes,
    generate_cvrp_splits_for_regimes,
)
from cmhh.data.manifest import load_json, sha256_file


class TestCVRPConstraintRegimes(unittest.TestCase):
    def test_base_instance_generation_properties(self) -> None:
        """Base CVRP instance generation generates valid coordinates and demands."""
        base = generate_cvrp_base_instance(
            node_count=50,
            seed=42,
            demand_min=1,
            demand_max=10,
            coordinate_min=0,
            coordinate_max=1000,
        )
        self.assertEqual(len(base.coords), 50)  # depot + 49 customers
        self.assertEqual(len(base.demands), 50)
        self.assertEqual(base.demands[0], 0)  # depot demand is 0
        self.assertTrue(all(1 <= d <= 10 for d in base.demands[1:]))
        self.assertGreater(base.total_demand, 0)
        self.assertEqual(base.total_demand, sum(base.demands[1:]))

    def test_capacity_tightness_ordering_and_hash_invariance(self) -> None:
        """Constraint regimes Loose, Medium, Tight must share coordinates/demands and have Q_L > Q_M > Q_T."""
        regimes = generate_cvrp_constraint_regimes(
            node_count=50,
            seed=101,
            fleet_size=8,
            demand_min=1,
            demand_max=10,
        )
        self.assertIn("loose", regimes)
        self.assertIn("medium", regimes)
        self.assertIn("tight", regimes)

        loose = regimes["loose"]
        medium = regimes["medium"]
        tight = regimes["tight"]

        # 1. Base coordinates and demands must match exactly
        self.assertEqual(loose.coords, medium.coords)
        self.assertEqual(medium.coords, tight.coords)
        self.assertEqual(loose.demands, medium.demands)
        self.assertEqual(medium.demands, tight.demands)
        self.assertEqual(loose.coordinate_hash, medium.coordinate_hash)
        self.assertEqual(loose.demand_hash, tight.demand_hash)

        # 2. Capacity formula: Q = ceil(total_demand / (K * rho))
        total_d = loose.total_demand
        k = 8
        expected_q_loose = math.ceil(total_d / (k * 0.55))
        expected_q_medium = math.ceil(total_d / (k * 0.75))
        expected_q_tight = math.ceil(total_d / (k * 0.90))

        self.assertEqual(loose.capacity, expected_q_loose)
        self.assertEqual(medium.capacity, expected_q_medium)
        self.assertEqual(tight.capacity, expected_q_tight)

        # 3. Capacity ordering Q_loose > Q_medium > Q_tight
        self.assertGreater(loose.capacity, medium.capacity)
        self.assertGreater(medium.capacity, tight.capacity)

        # 4. Invariant: capacity must exceed max customer demand
        max_d = max(loose.demands[1:])
        self.assertGreaterEqual(tight.capacity, max_d)

    def test_split_generation_and_manifest_metadata(self) -> None:
        """Generating splits on disk creates paired files with rich metadata."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_output_dir = Path(tmp_dir)
            split_counts = {"train": 3, "validation": 2, "test": 2, "smoke": 1}

            written_paths = generate_cvrp_splits_for_regimes(
                base_output_dir=base_output_dir,
                node_count=50,
                base_seed=53050,
                fleet_size=8,
                split_counts=split_counts,
            )

            for regime in ["loose", "medium", "tight"]:
                manifest_path = base_output_dir / f"cvrp_uniform_n50_{regime}" / "manifest.json"
                self.assertTrue(manifest_path.exists(), f"Manifest missing for {regime}")
                manifest = load_json(manifest_path)

                self.assertEqual(manifest["task_id"], f"cvrp_uniform_n50_{regime}")
                self.assertEqual(manifest["fleet_size"], 8)
                self.assertEqual(manifest["constraint_regime"], regime)
                self.assertEqual(manifest["total_instances"], sum(split_counts.values()))

                # Inspect individual instance metadata in manifest
                train_meta = manifest["splits"]["train"]
                self.assertEqual(len(train_meta), 3)
                for entry in train_meta:
                    self.assertIn("coordinate_hash", entry)
                    self.assertIn("demand_hash", entry)
                    self.assertIn("total_demand", entry)
                    self.assertIn("capacity", entry)
                    self.assertIn("capacity_tightness", entry)


if __name__ == "__main__":
    unittest.main()
